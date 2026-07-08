from datetime import timedelta

from .models import CycleActivity, CycleTask


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


def generate_cycle_activities(cycle):
    """Copy TEMPLATE_ACTIVITY records into runtime CYCLE_ACTIVITY records."""
    created_activities = []
    activity_map = {}

    for template_activity in cycle.template.template_activities.all():
        start, end = calculate_activity_dates(
            cycle.start_date,
            template_activity.start_offset_days,
            template_activity.end_offset_days,
        )

        cycle_activity = CycleActivity.objects.create(
            cycle=cycle,
            template_activity=template_activity,
            activity_name=template_activity.activity_name,
            calculated_start_date=start,
            calculated_end_date=end,
            note_text=template_activity.note_text,
        )

        created_activities.append(cycle_activity)
        activity_map[template_activity.template_activity_id] = cycle_activity

    return created_activities, activity_map


def generate_cycle_tasks(cycle, activity_map=None):
    """Copy TEMPLATE_TASK records into runtime CYCLE_TASK records."""
    created_tasks = []
    activity_map = activity_map or {}

    for template_task in cycle.template.template_tasks.all():
        start, end = calculate_task_dates(
            cycle.start_date,
            template_task.day_offset,
            template_task.duration_days,
        )

        cycle_activity = None
        if template_task.template_activity_id:
            cycle_activity = activity_map.get(template_task.template_activity_id)

        created_tasks.append(
            CycleTask.objects.create(
                cycle=cycle,
                template_task=template_task,
                cycle_activity=cycle_activity,
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


def generate_cycle_runtime_records(cycle):
    """Generate runtime tasks and activities for a freshly created cycle."""
    cycle_activities, activity_map = generate_cycle_activities(cycle)
    cycle_tasks = generate_cycle_tasks(cycle, activity_map)

    return {
        "cycle_tasks": cycle_tasks,
        "cycle_activities": cycle_activities,
    }