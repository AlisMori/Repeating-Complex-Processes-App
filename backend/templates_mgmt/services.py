from cycles.dependency_engine import copy_dependencies
from .models import Template, TemplateActivity, TemplateTask, UserTemplate


# Copying and versioning
#
# Every structural change to a template's tasks, activities, or
# dependencies creates a new template version, the original is frozen
# (is_current_version=False) and left exactly as it was, a fresh
# Template row gets a full copy plus the one requested change applied
# on top of the copy. Notes are the one exception, editing a note
# never forks a version, see the note actions in views.py.
#
# This is a deliberate, real change in shape from how the API used to
# behave (task/activity edits used to mutate in place). A cycle already
# created from an older version keeps pointing at that version's frozen
# rows forever, template_task on a CycleTask never gets silently
# repointed, so existing cycles are never affected by later template
# edits.

def deep_copy_template_contents(source_template, target_template):
    """Copies every TemplateActivity, TemplateTask, and TaskDependency
    from source_template onto target_template, which must already
    exist and be empty. The one implementation every copy operation
    (new version, duplicate, share) is built on, so they can never
    quietly diverge from each other again the way duplicate and share
    once did.

    Returns (activity_map, task_id_map), old primary key -> new
    instance, for a caller that needs to find the freshly copied
    counterpart of some specific original row afterward.
    """
    activity_map = {}
    for activity in source_template.template_activities.all():
        new_activity = TemplateActivity.objects.create(
            template=target_template,
            activity_name=activity.activity_name,
            description=activity.description,
            start_offset_days=activity.start_offset_days,
            end_offset_days=activity.end_offset_days,
            note_text=activity.note_text,
        )
        activity_map[activity.template_activity_id] = new_activity

    task_id_map = {}
    for task in source_template.template_tasks.all():
        new_task = TemplateTask.objects.create(
            template=target_template,
            template_activity=activity_map.get(task.template_activity_id),
            task_name=task.task_name,
            description=task.description,
            day_offset=task.day_offset,
            duration_days=task.duration_days,
            is_mandatory=task.is_mandatory,
            is_fixed_date=task.is_fixed_date,
            reminder_lead_days=task.reminder_lead_days,
            note_text=task.note_text,
        )
        task_id_map[task.template_task_id] = new_task

    copy_dependencies(source_template, task_id_map)

    return activity_map, task_id_map


def fork_new_version(original_template, user):
    """Creates a new Template row in the same version lineage as
    original_template (same root, template_version + 1), deep copies
    every task, activity, and dependency onto it, and freezes the
    original. This is what every task/activity/dependency mutation
    calls before applying its one specific change.

    Returns (new_template, activity_map, task_id_map).
    """
    original_template.is_current_version = False
    original_template.save(update_fields=["is_current_version"])

    new_template = Template.objects.create(
        user=user,
        parent_template=original_template.parent_template or original_template,
        template_version=original_template.template_version + 1,
        template_name=original_template.template_name,
        description=original_template.description,
        is_public=original_template.is_public,
        created_by_type=original_template.created_by_type,
        is_current_version=True,
    )

    UserTemplate.objects.get_or_create(
        user=user,
        template=new_template,
        defaults={"access_type": "owner"},
    )

    activity_map, task_id_map = deep_copy_template_contents(original_template, new_template)
    return new_template, activity_map, task_id_map


def new_version_payload(new_template):
    """Small block every forking endpoint attaches to its response so
    the frontend always knows a new version now exists and what its id
    is, instead of finding out only because the old id it was using
    stopped working. Part of "return what happened, do not silently
    fail or silently switch things out from under the caller."
    """
    return {
        "template_id": new_template.template_id,
        "template_version": new_template.template_version,
    }


def expand_activity_to_include_task(task):
    """Widen only. A task moved or resized so it now sticks out past
    its activity's current bounds pulls the activity's bound out to
    match, on whichever side, never both unless both sides actually
    need it, and never shrinks the other side. See
    maybe_shrink_activity below for the opposite direction.
    """
    activity = task.template_activity
    if activity is None:
        return

    task_start = task.day_offset
    task_end = task.day_offset + (task.duration_days or 0)

    updated_fields = []
    if task_start < activity.start_offset_days:
        activity.start_offset_days = task_start
        updated_fields.append("start_offset_days")
    if task_end > activity.end_offset_days:
        activity.end_offset_days = task_end
        updated_fields.append("end_offset_days")

    if updated_fields:
        activity.save(update_fields=updated_fields)


def maybe_shrink_activity(activity, old_task_start, old_task_end):
    """Called right after a task belonging to `activity` was deleted,
    unlinked, or moved away from old_task_start/old_task_end (its
    position just before the change). If the activity's own bound on
    a side used to sit exactly at this task's old edge, meaning this
    task specifically was what was holding that side open, pulls the
    bound back in to match whatever the activity's remaining tasks
    actually need now.

    An activity the user deliberately made wider than its tasks
    require is left alone either way, this only ever releases slack
    that a task, not the user, was responsible for.
    """
    if activity is None:
        return

    was_left_edge = old_task_start == activity.start_offset_days
    was_right_edge = old_task_end == activity.end_offset_days
    if not (was_left_edge or was_right_edge):
        return

    remaining = list(activity.template_tasks.all())
    updated_fields = []

    if was_left_edge and remaining:
        tightest_start = min(t.day_offset for t in remaining)
        if tightest_start > activity.start_offset_days:
            activity.start_offset_days = tightest_start
            updated_fields.append("start_offset_days")

    if was_right_edge and remaining:
        tightest_end = max(t.day_offset + (t.duration_days or 0) for t in remaining)
        if tightest_end < activity.end_offset_days:
            activity.end_offset_days = tightest_end
            updated_fields.append("end_offset_days")

    if updated_fields:
        activity.save(update_fields=updated_fields)