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
    metadata: dict | None = None


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
        metadata={
            "template_version": template.template_version,
            "is_current_version": template.is_current_version,
        },
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
        metadata={
            "template_version": task.template.template_version,
            "is_current_version": task.template.is_current_version,
        },
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
        metadata={
            "template_version": activity.template.template_version,
            "is_current_version": activity.template.is_current_version,
        },
    )


def serialize_template_task_note_result(task, query):
    return SearchResult(
        id=task.template_task_id,
        type="note",
        title=task.task_name,
        matched_field="note_text",
        snippet=build_snippet(task.note_text or "", query),
        parent={
            "type": "template",
            "id": task.template.template_id,
            "title": task.template.template_name,
        },
        url=f"/templates/{task.template.template_id}",
        sort_key=task.task_name.lower(),
        metadata={
            "template_version": task.template.template_version,
            "is_current_version": task.template.is_current_version,
            "item_kind": "task_note",
        },
    )


def serialize_template_activity_note_result(activity, query):
    return SearchResult(
        id=activity.template_activity_id,
        type="note",
        title=activity.activity_name,
        matched_field="note_text",
        snippet=build_snippet(activity.note_text or "", query),
        parent={
            "type": "template",
            "id": activity.template.template_id,
            "title": activity.template.template_name,
        },
        url=f"/templates/{activity.template.template_id}",
        sort_key=activity.activity_name.lower(),
        metadata={
            "template_version": activity.template.template_version,
            "is_current_version": activity.template.is_current_version,
            "item_kind": "activity_note",
        },
    )


def template_family_id(template):
    return template.parent_template_id or template.template_id


def reminder_signature(reminder_lead_days):
    if not reminder_lead_days:
        return ()
    return tuple(reminder_lead_days)


def activity_identity_signature(activity):
    return (
        "activity",
        (activity.activity_name or "").strip().lower(),
        activity.start_offset_days,
        activity.end_offset_days,
    )


def task_activity_signature(task):
    if task.template_activity is None:
        return None
    activity = task.template_activity
    return (
        (activity.activity_name or "").strip().lower(),
        activity.start_offset_days,
        activity.end_offset_days,
    )


def task_identity_signature(task):
    return (
        "task",
        (task.task_name or "").strip().lower(),
        task.day_offset,
        task.duration_days or 1,
        bool(task.is_mandatory),
        bool(task.is_fixed_date),
        reminder_signature(task.reminder_lead_days),
        task_activity_signature(task),
    )


def note_identity_signature(item, kind):
    if kind == "task_note":
        return ("task_note",) + task_identity_signature(item)[1:]
    return ("activity_note",) + activity_identity_signature(item)[1:]


def build_version_match_summary(current_match, historical_count):
    if current_match:
        summary = "Matched in current version"
        if historical_count:
            suffix = "version" if historical_count == 1 else "versions"
            summary = f"{summary} and {historical_count} previous {suffix}"
        return summary
    return "No match in current version"


def build_grouped_versioned_results(
    matched_items,
    query,
    serialize_match,
    item_identity_key,
    current_items_by_family,
    current_template_by_family,
    item_kind=None,
):
    results_by_identity = {}
    matched_item_by_identity = {}

    for item in matched_items:
        family_id = template_family_id(item.template)
        identity_key = (family_id, item_identity_key(item))
        result = serialize_match(item, query)
        if item_kind:
            result.metadata["item_kind"] = item_kind
        results_by_identity.setdefault(identity_key, []).append(result)
        matched_item_by_identity.setdefault(identity_key, []).append(item)

    grouped_results = []
    for identity_key, matches in results_by_identity.items():
        family_id, logical_key = identity_key
        current_template = current_template_by_family.get(family_id)
        current_item = current_items_by_family.get(identity_key)
        current_match = next((match for match in matches if current_item and match.id == current_item.pk), None)
        historical_matches = sorted(
            (match for match in matches if match is not current_match),
            key=lambda match: match.metadata["template_version"],
            reverse=True,
        )
        matched_items = matched_item_by_identity[identity_key]
        fallback_item = max(
            matched_items,
            key=lambda item: item.template.template_version,
        )
        top_level_title = current_item and getattr(current_item, "task_name", None) or current_item and getattr(current_item, "activity_name", None)
        if not top_level_title:
            top_level_title = matches[0].title
        parent_title = current_template.template_name if current_template else fallback_item.template.template_name
        current_template_version = current_template.template_version if current_template else fallback_item.template.template_version
        current_template_id = current_template.template_id if current_template else fallback_item.template.template_id

        grouped_results.append(
            SearchResult(
                id=current_item.pk if current_item else fallback_item.pk,
                type=matches[0].type,
                title=top_level_title,
                matched_field=current_match.matched_field if current_match else matches[0].matched_field,
                snippet=current_match.snippet if current_match else "",
                parent={
                    "type": "template",
                    "id": current_template_id,
                    "title": parent_title,
                },
                url=f"/templates/{current_template_id}",
                sort_key=top_level_title.lower(),
                metadata={
                    "template_version": current_template_version,
                    "is_current_version": True,
                    "item_kind": item_kind,
                    "summary": build_version_match_summary(current_match is not None, len(historical_matches)),
                    "current_match": current_match is not None,
                    "historical_match_count": len(historical_matches),
                    "historical_matches": [
                        {
                            "id": match.id,
                            "title": match.title,
                            "matched_field": match.matched_field,
                            "snippet": match.snippet,
                            "url": match.url,
                            "template_version": match.metadata["template_version"],
                        }
                        for match in historical_matches
                    ],
                },
            )
        )

    grouped_results.sort(key=lambda item: item.sort_key)
    return grouped_results


def map_current_template_items_by_identity(current_templates, queryset_builder, item_identity_key):
    current_items = {}
    if not current_templates:
        return current_items

    queryset = queryset_builder([template.template_id for template in current_templates.values()])
    for item in queryset:
        identity_key = (template_family_id(item.template), item_identity_key(item))
        current_items[identity_key] = item
    return current_items


def current_templates_for_families(user, family_ids):
    current_templates = {}
    if not family_ids:
        return current_templates

    queryset = accessible_templates_queryset(user, "global").filter(
        Q(template_id__in=family_ids) | Q(parent_template_id__in=family_ids),
        is_current_version=True,
    )
    for template in queryset:
        current_templates[template_family_id(template)] = template
    return current_templates


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
    payload = {
        "id": result.id,
        "type": result.type,
        "title": result.title,
        "matched_field": result.matched_field,
        "snippet": result.snippet,
        "parent": result.parent,
        "url": result.url,
    }
    if result.metadata is not None:
        payload["metadata"] = result.metadata
    return payload


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
    ).order_by("template_name", "template_version")

    matches_by_family = {}
    matched_templates_by_family = {}
    family_ids = set()
    for template in queryset:
        family_id = template.parent_template_id or template.template_id
        family_ids.add(family_id)
        matches_by_family.setdefault(family_id, []).append(serialize_template_result(template, query))
        matched_templates_by_family.setdefault(family_id, []).append(template)

    current_versions = current_templates_for_families(user, family_ids)

    all_results = []
    for family_id, matches in matches_by_family.items():
        current_template = current_versions.get(family_id)
        if current_template is None:
            current_template = max(
                matched_templates_by_family[family_id],
                key=lambda template: template.template_version,
            )
        current_match = next((match for match in matches if match.id == current_template.template_id), None)
        historical_matches = sorted(
            (match for match in matches if match.id != current_template.template_id),
            key=lambda match: match.metadata["template_version"],
            reverse=True,
        )
        historical_count = len(historical_matches)
        if current_match:
            summary = "Matched in current version"
            if historical_count:
                suffix = "version" if historical_count == 1 else "versions"
                summary = f"{summary} and {historical_count} previous {suffix}"
        else:
            summary = "No match in current version"

        all_results.append(
            SearchResult(
                id=current_template.template_id,
                type="template",
                title=current_template.template_name,
                matched_field=(current_match.matched_field if current_match else matches[0].matched_field),
                snippet=current_match.snippet if current_match else "",
                parent=None,
                url=f"/templates/{current_template.template_id}",
                sort_key=current_template.template_name.lower(),
                metadata={
                    "template_version": current_template.template_version,
                    "is_current_version": True,
                    "summary": summary,
                    "current_match": current_match is not None,
                    "historical_match_count": historical_count,
                    "historical_matches": [
                        {
                            "id": match.id,
                            "title": match.title,
                            "matched_field": match.matched_field,
                            "snippet": match.snippet,
                            "url": match.url,
                            "template_version": match.metadata["template_version"],
                        }
                        for match in historical_matches
                    ],
                },
            )
        )

    all_results.sort(key=lambda item: item.sort_key)
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
        ).select_related("template", "template_activity").order_by("task_name")
        family_ids = {template_family_id(task.template) for task in template_tasks}
        current_templates = current_templates_for_families(user, family_ids)
        current_items = map_current_template_items_by_identity(
            current_templates,
            lambda template_ids: TemplateTask.objects.filter(template_id__in=template_ids).select_related("template", "template_activity"),
            task_identity_signature,
        )
        results.extend(
            build_grouped_versioned_results(
                template_tasks,
                query,
                serialize_template_task_result,
                task_identity_signature,
                current_items,
                current_templates,
                item_kind="task",
            )
        )
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
        ).select_related("template").order_by("activity_name")
        family_ids = {template_family_id(activity.template) for activity in template_activities}
        current_templates = current_templates_for_families(user, family_ids)
        current_items = map_current_template_items_by_identity(
            current_templates,
            lambda template_ids: TemplateActivity.objects.filter(template_id__in=template_ids).select_related("template"),
            activity_identity_signature,
        )
        results.extend(
            build_grouped_versioned_results(
                template_activities,
                query,
                serialize_template_activity_result,
                activity_identity_signature,
                current_items,
                current_templates,
                item_kind="activity",
            )
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
        template_tasks = template_task_queryset(user, context).filter(
            Q(note_text__icontains=query)
        ).select_related("template", "template_activity").order_by("task_name")

        template_activities = template_activity_queryset(user, context).filter(
            Q(note_text__icontains=query)
        ).select_related("template").order_by("activity_name")

        family_ids = {
            *(template_family_id(task.template) for task in template_tasks),
            *(template_family_id(activity.template) for activity in template_activities),
        }
        current_templates = current_templates_for_families(user, family_ids)
        current_task_notes = map_current_template_items_by_identity(
            current_templates,
            lambda template_ids: TemplateTask.objects.filter(template_id__in=template_ids).select_related("template", "template_activity"),
            lambda task: note_identity_signature(task, "task_note"),
        )
        current_activity_notes = map_current_template_items_by_identity(
            current_templates,
            lambda template_ids: TemplateActivity.objects.filter(template_id__in=template_ids).select_related("template"),
            lambda activity: note_identity_signature(activity, "activity_note"),
        )
        results.extend(
            build_grouped_versioned_results(
                template_tasks,
                query,
                serialize_template_task_note_result,
                lambda task: note_identity_signature(task, "task_note"),
                current_task_notes,
                current_templates,
                item_kind="task_note",
            )
        )
        results.extend(
            build_grouped_versioned_results(
                template_activities,
                query,
                serialize_template_activity_note_result,
                lambda activity: note_identity_signature(activity, "activity_note"),
                current_activity_notes,
                current_templates,
                item_kind="activity_note",
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
