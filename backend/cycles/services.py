from datetime import timedelta

from .models import CycleActivity, CycleTask


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

def generate_cycle_tasks(cycle):
    """Copy every TEMPLATE_TASK on the cycle's template into runtime CYCLE_TASK records."""
    created_tasks = []

    for template_task in cycle.template.template_tasks.all():
        start, end = calculate_task_dates(
            cycle.start_date,
            template_task.day_offset,
            template_task.duration_days,
        )
        created_tasks.append(
            CycleTask.objects.create(
                cycle=cycle,
                template_task=template_task,
                task_name=template_task.task_name,
                calculated_start_date=start,
                calculated_end_date=end,
                is_mandatory=template_task.is_mandatory,
                is_fixed_date=template_task.is_fixed_date,
                reminder_lead_days=template_task.reminder_lead_days,
                note_text=template_task.note_text,
            )
        )

    return created_tasks


def generate_cycle_activities(cycle):
    """Copy every TEMPLATE_ACTIVITY on the cycle's template into runtime CYCLE_ACTIVITY records."""
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
    """Generate both runtime tasks and activities for a freshly created cycle (FR-4)."""
    created_activities = generate_cycle_activities(cycle)

    activity_map = {
        activity.template_activity_id: activity
        for activity in created_activities
    }

    created_tasks = []

    for template_task in cycle.template.template_tasks.all():
        start, end = calculate_task_dates(
            cycle.start_date,
            template_task.day_offset,
            template_task.duration_days,
        )

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

    return {
        "cycle_tasks": created_tasks,
        "cycle_activities": created_activities,
    }