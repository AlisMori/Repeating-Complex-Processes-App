from dataclasses import dataclass

from django.db.models import Q
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import accessible_templates_q, owned_cycles_q
from cycles.models import CycleActivity, CycleInstance, CycleTask
from templates_mgmt.models import Template, TemplateActivity, TemplateTask


VALID_SCOPES = ("templates", "cycles", "tasks", "activities", "notes")
SCOPE_LABELS = {
    "templates": "Templates",
    "cycles": "Cycles",
    "tasks": "Tasks",
    "activities": "Activities",
    "notes": "Notes",
}
DEFAULT_SCOPES_BY_CONTEXT = {
    "dashboard": list(VALID_SCOPES),
    "cycles": ["cycles", "tasks", "activities", "notes"],
    "templates": ["templates", "tasks", "activities", "notes"],
    "global": list(VALID_SCOPES),
}
VALID_CONTEXTS = set(DEFAULT_SCOPES_BY_CONTEXT.keys())


@dataclass(frozen=True)
class SearchResult:
    id: int
    type: str
    title: str
    matched_field: str
    snippet: str
    parent: dict | None
    url: str
    sort_key: str


def normalize_query(raw_query):
    return (raw_query or "").strip()


def parse_limit(raw_limit):
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return 5
    return max(1, min(limit, 25))


def parse_context(raw_context):
    context = (raw_context or "").strip().lower() or "global"
    if context not in VALID_CONTEXTS:
        return "global"
    return context


def parse_scopes(raw_scopes, context):
    if not raw_scopes:
        return DEFAULT_SCOPES_BY_CONTEXT[context]

    requested = {
        item.strip().lower()
        for item in raw_scopes.split(",")
        if item.strip()
    }
    if not requested:
        return DEFAULT_SCOPES_BY_CONTEXT[context]
    if "all" in requested:
        return list(VALID_SCOPES)
    parsed = [scope for scope in VALID_SCOPES if scope in requested]
    return parsed or DEFAULT_SCOPES_BY_CONTEXT[context]


def build_empty_response(query, context, scopes):
    return {
        "query": query,
        "context": context,
        "scopes": scopes,
        "total_count": 0,
        "groups": [],
    }


def build_search_q(fields, query):
    combined = Q()
    for field in fields:
        combined |= Q(**{f"{field}__icontains": query})
    return combined


def find_match(fields, query):
    lowered = query.lower()
    for field_name, field_value in fields:
        if field_value and lowered in field_value.lower():
            return field_name, field_value
    return None, ""


def build_snippet(text, query, length=90):
    if not text:
        return ""

    clean_text = " ".join(str(text).split())
    lowered = clean_text.lower()
    match_index = lowered.find(query.lower())
    if match_index < 0 or len(clean_text) <= length:
        return clean_text[:length]

    start = max(0, match_index - 25)
    end = min(len(clean_text), match_index + max(len(query), 20))

    while start > 0 and clean_text[start] != " ":
        start -= 1
    while end < len(clean_text) and clean_text[end - 1] != " ":
        end += 1

    snippet = clean_text[start:end].strip()
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(clean_text):
        snippet = f"{snippet}..."
    return snippet


def accessible_templates_queryset(user, context):
    queryset = Template.objects.filter(accessible_templates_q(user)).distinct()
    if context == "dashboard":
        return queryset.filter(cycle_instances__user=user, cycle_instances__status="running").distinct()
    return queryset


def cycle_queryset(user, context):
    queryset = CycleInstance.objects.filter(owned_cycles_q(user))
    if context == "dashboard":
        return queryset.filter(status="running")
    return queryset


def template_task_queryset(user, context):
    queryset = TemplateTask.objects.filter(
        template__in=accessible_templates_queryset(user, context)
    ).select_related("template")
    return queryset.distinct()


def template_activity_queryset(user, context):
    queryset = TemplateActivity.objects.filter(
        template__in=accessible_templates_queryset(user, context)
    ).select_related("template")
    return queryset.distinct()


def cycle_task_queryset(user, context):
    queryset = CycleTask.objects.filter(
        cycle__in=cycle_queryset(user, context)
    ).select_related("cycle")
    if context == "dashboard":
        queryset = queryset.filter(status__in=("pending", "in_progress", "overdue"))
    return queryset.distinct()


def cycle_activity_queryset(user, context):
    queryset = CycleActivity.objects.filter(
        cycle__in=cycle_queryset(user, context)
    ).select_related("cycle")
    return queryset.distinct()


def serialize_template_result(template, query):
    matched_field, matched_value = find_match(
        [("template_name", template.template_name), ("description", template.description or "")],
        query,
    )
    return SearchResult(
        id=template.template_id,
        type="template",
        title=template.template_name,
        matched_field=matched_field or "template_name",
        snippet=build_snippet(matched_value or template.template_name, query),
        parent=None,
        url=f"/templates/{template.template_id}",
        sort_key=template.template_name.lower(),
    )


def serialize_cycle_result(cycle, query):
    matched_field, matched_value = find_match([("cycle_name", cycle.cycle_name)], query)
    return SearchResult(
        id=cycle.cycle_id,
        type="cycle",
        title=cycle.cycle_name,
        matched_field=matched_field or "cycle_name",
        snippet=build_snippet(matched_value or cycle.cycle_name, query),
        parent=None,
        url=f"/cycles/{cycle.cycle_id}",
        sort_key=cycle.cycle_name.lower(),
    )


def serialize_template_task_result(task, query):
    matched_field, matched_value = find_match(
        [
            ("task_name", task.task_name),
            ("description", task.description or ""),
            ("note_text", task.note_text or ""),
        ],
        query,
    )
    return SearchResult(
        id=task.template_task_id,
        type="task",
        title=task.task_name,
        matched_field=matched_field or "task_name",
        snippet=build_snippet(matched_value or task.task_name, query),
        parent={
            "type": "template",
            "id": task.template.template_id,
            "title": task.template.template_name,
        },
        url=f"/templates/{task.template.template_id}",
        sort_key=task.task_name.lower(),
    )


def serialize_cycle_task_result(task, query):
    matched_field, matched_value = find_match(
        [("task_name", task.task_name), ("note_text", task.note_text or "")],
        query,
    )
    return SearchResult(
        id=task.cycle_task_id,
        type="task",
        title=task.task_name,
        matched_field=matched_field or "task_name",
        snippet=build_snippet(matched_value or task.task_name, query),
        parent={
            "type": "cycle",
            "id": task.cycle.cycle_id,
            "title": task.cycle.cycle_name,
        },
        url=f"/cycles/{task.cycle.cycle_id}",
        sort_key=task.task_name.lower(),
    )


def serialize_template_activity_result(activity, query):
    matched_field, matched_value = find_match(
        [
            ("activity_name", activity.activity_name),
            ("description", activity.description or ""),
            ("note_text", activity.note_text or ""),
        ],
        query,
    )
    return SearchResult(
        id=activity.template_activity_id,
        type="activity",
        title=activity.activity_name,
        matched_field=matched_field or "activity_name",
        snippet=build_snippet(matched_value or activity.activity_name, query),
        parent={
            "type": "template",
            "id": activity.template.template_id,
            "title": activity.template.template_name,
        },
        url=f"/templates/{activity.template.template_id}",
        sort_key=activity.activity_name.lower(),
    )


def serialize_cycle_activity_result(activity, query):
    matched_field, matched_value = find_match(
        [("activity_name", activity.activity_name), ("note_text", activity.note_text or "")],
        query,
    )
    return SearchResult(
        id=activity.cycle_activity_id,
        type="activity",
        title=activity.activity_name,
        matched_field=matched_field or "activity_name",
        snippet=build_snippet(matched_value or activity.activity_name, query),
        parent={
            "type": "cycle",
            "id": activity.cycle.cycle_id,
            "title": activity.cycle.cycle_name,
        },
        url=f"/cycles/{activity.cycle.cycle_id}",
        sort_key=activity.activity_name.lower(),
    )


def as_payload(result):
    return {
        "id": result.id,
        "type": result.type,
        "title": result.title,
        "matched_field": result.matched_field,
        "snippet": result.snippet,
        "parent": result.parent,
        "url": result.url,
    }


def group_payload(group_type, results):
    return {
        "type": group_type,
        "label": SCOPE_LABELS[group_type],
        "count": len(results["all"]),
        "has_more": len(results["all"]) > len(results["visible"]),
        "results": [as_payload(result) for result in results["visible"]],
    }


def search_templates(user, query, context, limit):
    queryset = accessible_templates_queryset(user, context).filter(
        build_search_q(("template_name", "description"), query)
    ).order_by("template_name")
    all_results = [serialize_template_result(template, query) for template in queryset]
    return {"all": all_results, "visible": all_results[:limit]}


def search_cycles(user, query, context, limit):
    queryset = cycle_queryset(user, context).filter(
        build_search_q(("cycle_name",), query)
    ).order_by("cycle_name")
    all_results = [serialize_cycle_result(cycle, query) for cycle in queryset]
    return {"all": all_results, "visible": all_results[:limit]}


def search_tasks(user, query, context, limit):
    results = []
    if context in ("templates", "global"):
        template_tasks = template_task_queryset(user, context).filter(
            build_search_q(("task_name", "description", "note_text"), query)
        ).order_by("task_name")
        results.extend(serialize_template_task_result(task, query) for task in template_tasks)
    if context in ("dashboard", "cycles", "global"):
        cycle_tasks = cycle_task_queryset(user, context).filter(
            build_search_q(("task_name", "note_text"), query)
        ).order_by("task_name")
        results.extend(serialize_cycle_task_result(task, query) for task in cycle_tasks)

    results.sort(key=lambda item: item.sort_key)
    return {"all": results, "visible": results[:limit]}


def search_activities(user, query, context, limit):
    results = []
    if context in ("templates", "global"):
        template_activities = template_activity_queryset(user, context).filter(
            build_search_q(("activity_name", "description", "note_text"), query)
        ).order_by("activity_name")
        results.extend(
            serialize_template_activity_result(activity, query)
            for activity in template_activities
        )
    if context in ("dashboard", "cycles", "global"):
        cycle_activities = cycle_activity_queryset(user, context).filter(
            build_search_q(("activity_name", "note_text"), query)
        ).order_by("activity_name")
        results.extend(
            serialize_cycle_activity_result(activity, query)
            for activity in cycle_activities
        )

    results.sort(key=lambda item: item.sort_key)
    return {"all": results, "visible": results[:limit]}


def search_notes(user, query, context, limit):
    results = []

    if context in ("templates", "global"):
        templates = accessible_templates_queryset(user, context).filter(
            Q(description__icontains=query)
        ).order_by("template_name")
        for template in templates:
            results.append(
                SearchResult(
                    id=template.template_id,
                    type="note",
                    title=template.template_name,
                    matched_field="description",
                    snippet=build_snippet(template.description or "", query),
                    parent=None,
                    url=f"/templates/{template.template_id}",
                    sort_key=template.template_name.lower(),
                )
            )

        template_tasks = template_task_queryset(user, context).filter(
            Q(description__icontains=query) | Q(note_text__icontains=query)
        ).order_by("task_name")
        for task in template_tasks:
            matched_field, matched_value = find_match(
                [("description", task.description or ""), ("note_text", task.note_text or "")],
                query,
            )
            results.append(
                SearchResult(
                    id=task.template_task_id,
                    type="note",
                    title=task.task_name,
                    matched_field=matched_field or "note_text",
                    snippet=build_snippet(matched_value, query),
                    parent={
                        "type": "template",
                        "id": task.template.template_id,
                        "title": task.template.template_name,
                    },
                    url=f"/templates/{task.template.template_id}",
                    sort_key=task.task_name.lower(),
                )
            )

        template_activities = template_activity_queryset(user, context).filter(
            Q(description__icontains=query) | Q(note_text__icontains=query)
        ).order_by("activity_name")
        for activity in template_activities:
            matched_field, matched_value = find_match(
                [("description", activity.description or ""), ("note_text", activity.note_text or "")],
                query,
            )
            results.append(
                SearchResult(
                    id=activity.template_activity_id,
                    type="note",
                    title=activity.activity_name,
                    matched_field=matched_field or "note_text",
                    snippet=build_snippet(matched_value, query),
                    parent={
                        "type": "template",
                        "id": activity.template.template_id,
                        "title": activity.template.template_name,
                    },
                    url=f"/templates/{activity.template.template_id}",
                    sort_key=activity.activity_name.lower(),
                )
            )

    if context in ("dashboard", "cycles", "global"):
        cycle_tasks = cycle_task_queryset(user, context).filter(
            Q(note_text__icontains=query)
        ).order_by("task_name")
        for task in cycle_tasks:
            results.append(
                SearchResult(
                    id=task.cycle_task_id,
                    type="note",
                    title=task.task_name,
                    matched_field="note_text",
                    snippet=build_snippet(task.note_text or "", query),
                    parent={
                        "type": "cycle",
                        "id": task.cycle.cycle_id,
                        "title": task.cycle.cycle_name,
                    },
                    url=f"/cycles/{task.cycle.cycle_id}",
                    sort_key=task.task_name.lower(),
                )
            )

        cycle_activities = cycle_activity_queryset(user, context).filter(
            Q(note_text__icontains=query)
        ).order_by("activity_name")
        for activity in cycle_activities:
            results.append(
                SearchResult(
                    id=activity.cycle_activity_id,
                    type="note",
                    title=activity.activity_name,
                    matched_field="note_text",
                    snippet=build_snippet(activity.note_text or "", query),
                    parent={
                        "type": "cycle",
                        "id": activity.cycle.cycle_id,
                        "title": activity.cycle.cycle_name,
                    },
                    url=f"/cycles/{activity.cycle.cycle_id}",
                    sort_key=activity.activity_name.lower(),
                )
            )

    results.sort(key=lambda item: item.sort_key)
    return {"all": results, "visible": results[:limit]}


SEARCHERS = {
    "templates": search_templates,
    "cycles": search_cycles,
    "tasks": search_tasks,
    "activities": search_activities,
    "notes": search_notes,
}


class SearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = normalize_query(request.query_params.get("q"))
        context = parse_context(request.query_params.get("context"))
        scopes = parse_scopes(request.query_params.get("scopes"), context)
        limit = parse_limit(request.query_params.get("limit"))

        if len(query) < 2:
            return Response(build_empty_response(query, context, scopes))

        groups = []
        total_count = 0

        for scope in scopes:
            group_results = SEARCHERS[scope](request.user, query, context, limit)
            if not group_results["all"]:
                continue
            groups.append(group_payload(scope, group_results))
            total_count += len(group_results["all"])

        return Response(
            {
                "query": query,
                "context": context,
                "scopes": scopes,
                "total_count": total_count,
                "groups": groups,
            }
        )
