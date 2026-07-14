# Bulk template structure save
#
# WHY THIS EXISTS: the original design created one new template
# version per field-level API call (one for each task, one for each
# activity, one for each dependency). Editing a template with 7 tasks
# and 4 dependencies meant 11+ forked versions for a single edit, and
# every one of those calls could independently fail partway through,
# leaving a half-written version behind — that's what caused the
# repeated task/activity duplication bugs and the tag-loss-on-edit
# bug (a freshly CREATED task is not the same row as before, it never
# had a tag assigned to it in the first place).
#
# This module takes the wizard's ENTIRE intended structure (every
# activity, task, tag assignment, and dependency) in one request,
# validates every single part of it up front with nothing written to
# the database, and only if ALL of it is valid does it write
# anything — one new template version, created once, complete and
# correct from the moment it exists. No partial states are ever
# possible, and there's no window for a double-click or a "Back and
# resubmit" to leave duplicate rows behind, because there is exactly
# one write operation per save.
#
# Local ids (arbitrary strings) are how a payload's tasks/activities
# refer to each other, since none of this exists in the database yet
# to have real primary keys.

from django.db import transaction

from cycles.dependency_engine import MAX_DIRECT_DEPENDENTS
from .models import Tag, Template, TemplateActivity, TemplateActivityTag, TemplateTask, TemplateTaskTag
from cycles.models import TaskDependency


def validate_structure_payload(payload, user):
    """Returns a list of error dicts, empty if the payload is entirely
    valid. Never touches the database except read-only tag ownership
    checks — this is the "check everything before writing anything"
    half of the save.
    """
    errors = []
    activities = payload.get("activities") or []
    tasks = payload.get("tasks") or []
    dependencies = payload.get("dependencies") or []

    activity_local_ids = set()
    for a in activities:
        local_id = a.get("local_id")
        if not local_id or local_id in activity_local_ids:
            errors.append({"type": "activity", "local_id": local_id, "message": "Every activity needs a unique local id."})
            continue
        activity_local_ids.add(local_id)
        if not (a.get("activity_name") or "").strip():
            errors.append({"type": "activity", "local_id": local_id, "message": "Activity name is required."})
        start = a.get("start_offset_days")
        end = a.get("end_offset_days")
        if start is None or end is None or int(end) <= int(start):
            errors.append({"type": "activity", "local_id": local_id, "message": "End day must be after start day."})

    task_local_ids = set()
    task_by_local_id = {}
    for t in tasks:
        local_id = t.get("local_id")
        if not local_id or local_id in task_local_ids:
            errors.append({"type": "task", "local_id": local_id, "message": "Every task needs a unique local id."})
            continue
        task_local_ids.add(local_id)
        task_by_local_id[local_id] = t
        if not (t.get("task_name") or "").strip():
            errors.append({"type": "task", "local_id": local_id, "message": "Task name is required."})
        day_offset = t.get("day_offset")
        if day_offset is None or int(day_offset) < 0:
            errors.append({"type": "task", "local_id": local_id, "message": "Day offset cannot be negative."})
            continue

        activity_local_id = t.get("activity_local_id")
        if activity_local_id:
            activity = next((a for a in activities if a.get("local_id") == activity_local_id), None)
            if not activity:
                errors.append({"type": "task", "local_id": local_id, "message": "Grouped under an activity that doesn't exist in this save."})
            else:
                duration = int(t.get("duration_days") or 1)
                task_start = int(day_offset)
                task_end = task_start + duration
                act_start = activity.get("start_offset_days")
                act_end = activity.get("end_offset_days")
                if act_start is not None and act_end is not None and (task_start < int(act_start) or task_end > int(act_end)):
                    errors.append({
                        "type": "task", "local_id": local_id,
                        "message": f"Task '{t.get('task_name')}' (day {task_start}\u2013{task_end}) doesn't fit inside "
                                   f"activity '{activity.get('activity_name')}' (day {act_start}\u2013{act_end}).",
                    })

        tag_ids = t.get("tag_ids") or []
        if tag_ids:
            owned = set(Tag.objects.filter(user=user, tag_id__in=tag_ids).values_list("tag_id", flat=True))
            for tag_id in tag_ids:
                if tag_id not in owned:
                    errors.append({"type": "task", "local_id": local_id, "message": "One of this task's tags doesn't belong to you."})
                    break

    for a in activities:
        tag_ids = a.get("tag_ids") or []
        if tag_ids:
            owned = set(Tag.objects.filter(user=user, tag_id__in=tag_ids).values_list("tag_id", flat=True))
            for tag_id in tag_ids:
                if tag_id not in owned:
                    errors.append({"type": "activity", "local_id": a.get("local_id"), "message": "One of this activity's tags doesn't belong to you."})
                    break

    # Dependencies: self-reference, unknown local ids, circular
    # chains, fan-out cap, and offset conflicts — all checked against
    # the payload's own local-id graph, since none of this exists in
    # the database yet to check against directly.
    graph = {}  # local_id -> set of local_ids it depends on, from THIS payload
    dependent_count = {}  # local_id -> how many things depend on it, from THIS payload
    for d in dependencies:
        task_id = d.get("task_local_id")
        dep_id = d.get("depends_on_local_id")
        if task_id == dep_id:
            errors.append({"type": "dependency", "task_local_id": task_id, "depends_on_local_id": dep_id, "message": "A task cannot depend on itself."})
            continue
        if task_id not in task_by_local_id or dep_id not in task_by_local_id:
            errors.append({"type": "dependency", "task_local_id": task_id, "depends_on_local_id": dep_id, "message": "References a task that doesn't exist in this save."})
            continue

        graph.setdefault(task_id, set()).add(dep_id)
        dependent_count[dep_id] = dependent_count.get(dep_id, 0) + 1

        if dependent_count[dep_id] > MAX_DIRECT_DEPENDENTS:
            dep_task = task_by_local_id[dep_id]
            errors.append({
                "type": "dependency", "task_local_id": task_id, "depends_on_local_id": dep_id,
                "message": f"Task '{dep_task.get('task_name')}' already has {MAX_DIRECT_DEPENDENTS} tasks depending on it directly.",
            })

        task = task_by_local_id[task_id]
        dep_task = task_by_local_id[dep_id]
        upstream_end = int(dep_task.get("day_offset", 0)) + int(dep_task.get("duration_days") or 1)
        if int(task.get("day_offset", 0)) < upstream_end:
            errors.append({
                "type": "dependency", "task_local_id": task_id, "depends_on_local_id": dep_id,
                "message": f"Task '{task.get('task_name')}' is set to start on day {task.get('day_offset')}, "
                           f"before '{dep_task.get('task_name')}' finishes on day {upstream_end}.",
            })

    def has_cycle(start, current, visited):
        for neighbor in graph.get(current, ()):
            if neighbor == start:
                return True
            if neighbor not in visited:
                visited.add(neighbor)
                if has_cycle(start, neighbor, visited):
                    return True
        return False

    for task_id in graph:
        if has_cycle(task_id, task_id, set()):
            errors.append({"type": "dependency", "task_local_id": task_id, "message": "This dependency chain would create a circular loop."})

    return errors


def apply_structure_payload(template, payload, user):
    """Writes the payload as ONE new template version — UNLESS no
    cycle has ever been created from this template yet, in which case
    it writes directly into the existing row instead of forking.
    Forking exists to keep a version a cycle is already using frozen
    and untouched; a template nothing has been created from yet can't
    possibly have a cycle running from it, so there's nothing to
    protect by forking — doing it anyway just leaves a throwaway
    version behind on every single save while a template is still
    being drafted (the first save AND every save after it, until it's
    actually used), which is confusing in a "Versions" view and
    wasteful for no benefit. See get_editable_template/
    template_is_locked in services.py for the same rule applied to
    the single-field task/activity/dependency endpoints.

    Caller must have already validated with validate_structure_payload
    — this function assumes the payload is valid and does not re-check.
    """
    is_locked = (not template.is_current_version) or template.cycle_instances.exists()

    with transaction.atomic():
        if not is_locked:
            target_template = template
            # Not necessarily the first save any more, a second or
            # third draft save reuses this same row too, so whatever
            # it already holds needs clearing before the payload's
            # full intended structure is written. Dependencies and tag
            # assignments cascade-delete with their task/activity, no
            # need to clear them separately.
            TemplateTask.objects.filter(template=target_template).delete()
            TemplateActivity.objects.filter(template=target_template).delete()
        else:
            template.is_current_version = False
            template.save(update_fields=["is_current_version"])

            target_template = Template.objects.create(
                user=template.user,
                parent_template=template.parent_template or template,
                template_version=template.template_version + 1,
                is_current_version=True,
                template_name=template.template_name,
                description=template.description,
                is_public=template.is_public,
                created_by_type=template.created_by_type,
                category=template.category,
            )

        activity_by_local_id = {}
        for a in payload.get("activities") or []:
            activity = TemplateActivity.objects.create(
                template=target_template,
                activity_name=a["activity_name"].strip(),
                description=(a.get("description") or "").strip(),
                start_offset_days=a["start_offset_days"],
                end_offset_days=a["end_offset_days"],
                note_text=(a.get("note_text") or "").strip(),
            )
            activity_by_local_id[a["local_id"]] = activity
            for tag_id in a.get("tag_ids") or []:
                TemplateActivityTag.objects.create(template_activity=activity, tag_id=tag_id)

        task_by_local_id = {}
        for t in payload.get("tasks") or []:
            task = TemplateTask.objects.create(
                template=target_template,
                template_activity=activity_by_local_id.get(t.get("activity_local_id")),
                task_name=t["task_name"].strip(),
                description=(t.get("description") or "").strip(),
                day_offset=t["day_offset"],
                duration_days=t.get("duration_days") or 1,
                is_mandatory=bool(t.get("is_mandatory")),
                is_fixed_date=bool(t.get("is_fixed_date")),
                reminder_lead_days=t.get("reminder_lead_days"),
                note_text=(t.get("note_text") or "").strip(),
            )
            task_by_local_id[t["local_id"]] = task
            for tag_id in t.get("tag_ids") or []:
                TemplateTaskTag.objects.create(template_task=task, tag_id=tag_id)

        for d in payload.get("dependencies") or []:
            TaskDependency.objects.create(
                task=task_by_local_id[d["task_local_id"]],
                depends_on_task=task_by_local_id[d["depends_on_local_id"]],
            )

    return target_template, activity_by_local_id, task_by_local_id