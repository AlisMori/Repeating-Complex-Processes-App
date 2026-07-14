from datetime import timedelta

from templates_mgmt.scheduling import resolve_effective_offsets

from .models import CycleActivity, CycleTask, TaskDependency


# Date calculation (7.4)
# Templates store relative day offsets from the cycle start date (FR-4).
# These two functions are the single source of truth for turning those
# offsets into absolute calendar dates, so cascade recalculation (Module 8)
# and runtime generation (below) always agree on how dates are derived.

def calculate_task_dates(cycle_start_date, day_offset, duration_days):
    """Convert a TEMPLATE_TASK's day_offset/duration into absolute dates."""
    start = cycle_start_date + timedelta(days=day_offset)
    end = start + timedelta(days=duration_days or 0)
    return start, end


def calculate_activity_dates(cycle_start_date, start_offset_days, end_offset_days):
    """Convert a TEMPLATE_ACTIVITY's start/end offsets into absolute dates."""
    start = cycle_start_date + timedelta(days=start_offset_days)
    end = cycle_start_date + timedelta(days=end_offset_days)
    return start, end


# Runtime record generation (7.2, 7.3)

def generate_cycle_activities(cycle):
    """Copy every TEMPLATE_ACTIVITY on the cycle's template into runtime
    CYCLE_ACTIVITY records. Activities have no dependency graph of their
    own, so their dates are always a direct offset conversion, nothing
    to resolve here.
    """
    created_activities = []

    for template_activity in cycle.template.template_activities.all():
        start, end = calculate_activity_dates(
            cycle.start_date,
            template_activity.start_offset_days,
            template_activity.end_offset_days,
        )
        created_activities.append(
            CycleActivity.objects.create(
                cycle=cycle,
                template_activity=template_activity,
                activity_name=template_activity.activity_name,
                calculated_start_date=start,
                calculated_end_date=end,
                note_text=template_activity.note_text,
            )
        )

    return created_activities


def generate_cycle_runtime_records(cycle):
    """Generate both runtime tasks and activities for a freshly created
    cycle (FR-4).

    Task dates are resolved through the full dependency chain first,
    using the same resolve_effective_offsets that templates use for
    timeline_preview, instead of converting each task's raw day_offset
    on its own. A template with dependencies would otherwise produce a
    cycle whose starting schedule already violates its own dependency
    graph, only becoming correct the first time something happens to
    trigger a shift. This keeps cycle creation and shift/preview
    agreeing on what "the schedule" means from the very first day.

    Returns a dict with the created rows plus schedule_warnings (None
    if the template's dependency graph resolved cleanly), so a caller
    can surface circular dependencies or fixed-date conflicts that
    existed on the template right away instead of only discovering
    them on the first shift attempt.
    """
    created_activities = generate_cycle_activities(cycle)

    activity_map = {
        activity.template_activity_id: activity
        for activity in created_activities
    }

    template_tasks = list(cycle.template.template_tasks.all())

    nodes = {
        t.template_task_id: {
            "offset": t.day_offset,
            "duration": t.duration_days or 0,
            "fixed": t.is_fixed_date,
        }
        for t in template_tasks
    }
    edges = {}
    for dep in TaskDependency.objects.filter(task__template=cycle.template):
        edges.setdefault(dep.task_id, []).append(dep.depends_on_task_id)

    effective, circular, conflicts = resolve_effective_offsets(nodes, edges)

    created_tasks = []
    for template_task in template_tasks:
        eff_start, eff_end = effective.get(
            template_task.template_task_id,
            (
                template_task.day_offset,
                template_task.day_offset + (template_task.duration_days or 0),
            ),
        )
        start = cycle.start_date + timedelta(days=eff_start)
        end = cycle.start_date + timedelta(days=eff_end)

        created_tasks.append(
            CycleTask.objects.create(
                cycle=cycle,
                template_task=template_task,
                cycle_activity=activity_map.get(template_task.template_activity_id),
                task_name=template_task.task_name,
                calculated_start_date=start,
                calculated_end_date=end,
                is_mandatory=template_task.is_mandatory,
                is_fixed_date=template_task.is_fixed_date,
                reminder_lead_days=template_task.reminder_lead_days,
                note_text=template_task.note_text,
            )
        )

    schedule_warnings = None
    if circular or conflicts:
        id_to_name = {t.template_task_id: t.task_name for t in template_tasks}
        schedule_warnings = {
            "circular_dependency_tasks": [id_to_name.get(tid, tid) for tid in circular],
            "fixed_date_conflicts": [id_to_name.get(tid, tid) for tid in conflicts],
        }

    return {
        "cycle_tasks": created_tasks,
        "cycle_activities": created_activities,
        "schedule_warnings": schedule_warnings,
    }


# Activity bounds validation
# Shared between CycleActivity now and TemplateActivity later, both call
# this with their own child rows' dates, nothing model specific here.

def validate_activity_bounds(new_start_date, new_end_date, child_date_ranges):
    """Checks whether every (start, end) pair in child_date_ranges still
    fits inside [new_start_date, new_end_date]. Used whenever an
    activity's own dates are being moved, shrunk, or widened directly,
    to reject a resize that would leave one of its tasks sticking out
    the edge. Tasks are never touched by this, an activity resize is
    rejected outright rather than pulling its tasks along with it, the
    caller decides which of its tasks it means by "edge tasks".

    Returns the list of (start, end) pairs that would fall outside the
    new range, empty means the resize is safe to save.
    """
    violations = []
    for child_start, child_end in child_date_ranges:
        if child_start < new_start_date or child_end > new_end_date:
            violations.append((child_start, child_end))
    return violations