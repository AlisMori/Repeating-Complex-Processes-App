import csv
import io
import json

from cycles.models import TaskDependency

try:
    import openpyxl
except ImportError:
    openpyxl = None


# Export
#
# All three formats (JSON, CSV, XLSX) are written from the same
# intermediate shape, a plain dict, so there is exactly one place that
# turns a Template into that shape (template_to_intermediate). The
# formats only differ in how that dict gets written out, never in what
# a template's data actually is. Same "one canonical implementation"
# approach as scheduling.py and dependency_engine.py.
#
# local_id exists so a downloaded file's cross-references (a task's
# activity, a dependency's two ends) are self-contained and readable
# on their own, rather than leaking internal database primary keys
# that mean nothing outside this system.

SUPPORTED_FORMATS = ("json", "csv", "xlsx")


def template_to_intermediate(template):
    """Template -> the canonical dict every export format is built from."""
    activities = list(template.template_activities.all())
    tasks = list(template.template_tasks.all())
    dependencies = TaskDependency.objects.filter(task__template=template).select_related(
        "task", "depends_on_task"
    )

    activity_local_id = {a.template_activity_id: f"A{a.template_activity_id}" for a in activities}
    task_local_id = {t.template_task_id: f"T{t.template_task_id}" for t in tasks}

    return {
        "template": {
            "template_name": template.template_name,
            "description": template.description or "",
            "is_public": template.is_public,
        },
        "activities": [
            {
                "local_id": activity_local_id[a.template_activity_id],
                "activity_name": a.activity_name,
                "description": a.description or "",
                "start_offset_days": a.start_offset_days,
                "end_offset_days": a.end_offset_days,
                "note_text": a.note_text or "",
            }
            for a in activities
        ],
        "tasks": [
            {
                "local_id": task_local_id[t.template_task_id],
                "task_name": t.task_name,
                "description": t.description or "",
                "day_offset": t.day_offset,
                "duration_days": t.duration_days,
                "is_mandatory": t.is_mandatory,
                "is_fixed_date": t.is_fixed_date,
                "reminder_lead_days": t.reminder_lead_days or [],
                "note_text": t.note_text or "",
                "activity_local_id": activity_local_id.get(t.template_activity_id, ""),
            }
            for t in tasks
        ],
        "dependencies": [
            {
                "task_local_id": task_local_id[d.task_id],
                "depends_on_local_id": task_local_id[d.depends_on_task_id],
            }
            for d in dependencies
        ],
    }


def write_json(data):
    return json.dumps(data, indent=2).encode("utf-8")


def write_csv(data):
    # One flat table, a row_type column says what each row is, and only
    # the columns that type actually uses are filled in. The single
    # file format, everything else needs either multiple files or
    # multiple sheets, this fits in one.
    buffer = io.StringIO()
    fieldnames = [
        "row_type", "local_id", "name", "description",
        "day_offset", "duration_days", "start_offset_days", "end_offset_days",
        "is_mandatory", "is_fixed_date", "reminder_lead_days", "note_text",
        "activity_local_id", "depends_on_local_id", "is_public",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()

    writer.writerow({
        "row_type": "template",
        "name": data["template"]["template_name"],
        "description": data["template"]["description"],
        "is_public": data["template"]["is_public"],
    })

    for activity in data["activities"]:
        writer.writerow({
            "row_type": "activity",
            "local_id": activity["local_id"],
            "name": activity["activity_name"],
            "description": activity["description"],
            "start_offset_days": activity["start_offset_days"],
            "end_offset_days": activity["end_offset_days"],
            "note_text": activity["note_text"],
        })

    for task in data["tasks"]:
        writer.writerow({
            "row_type": "task",
            "local_id": task["local_id"],
            "name": task["task_name"],
            "description": task["description"],
            "day_offset": task["day_offset"],
            "duration_days": task["duration_days"] if task["duration_days"] is not None else "",
            "is_mandatory": task["is_mandatory"],
            "is_fixed_date": task["is_fixed_date"],
            "reminder_lead_days": ";".join(str(d) for d in task["reminder_lead_days"]),
            "note_text": task["note_text"],
            "activity_local_id": task["activity_local_id"],
        })

    for dependency in data["dependencies"]:
        writer.writerow({
            "row_type": "dependency",
            "local_id": dependency["task_local_id"],
            "depends_on_local_id": dependency["depends_on_local_id"],
        })

    return buffer.getvalue().encode("utf-8")


def write_xlsx(data):
    if openpyxl is None:
        raise RuntimeError("openpyxl is not installed, xlsx export is unavailable.")

    workbook = openpyxl.Workbook()

    template_sheet = workbook.active
    template_sheet.title = "Template"
    template_sheet.append(["template_name", "description", "is_public"])
    template_sheet.append([
        data["template"]["template_name"],
        data["template"]["description"],
        data["template"]["is_public"],
    ])

    activities_sheet = workbook.create_sheet("Activities")
    activities_sheet.append([
        "local_id", "activity_name", "description",
        "start_offset_days", "end_offset_days", "note_text",
    ])
    for activity in data["activities"]:
        activities_sheet.append([
            activity["local_id"], activity["activity_name"], activity["description"],
            activity["start_offset_days"], activity["end_offset_days"], activity["note_text"],
        ])

    tasks_sheet = workbook.create_sheet("Tasks")
    tasks_sheet.append([
        "local_id", "task_name", "description", "day_offset", "duration_days",
        "is_mandatory", "is_fixed_date", "reminder_lead_days", "note_text",
        "activity_local_id",
    ])
    for task in data["tasks"]:
        tasks_sheet.append([
            task["local_id"], task["task_name"], task["description"],
            task["day_offset"], task["duration_days"],
            task["is_mandatory"], task["is_fixed_date"],
            ";".join(str(d) for d in task["reminder_lead_days"]),
            task["note_text"], task["activity_local_id"],
        ])

    dependencies_sheet = workbook.create_sheet("Dependencies")
    dependencies_sheet.append(["task_local_id", "depends_on_local_id"])
    for dependency in data["dependencies"]:
        dependencies_sheet.append([dependency["task_local_id"], dependency["depends_on_local_id"]])

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


WRITERS = {"json": write_json, "csv": write_csv, "xlsx": write_xlsx}