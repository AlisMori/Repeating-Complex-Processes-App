from datetime import timedelta

from .models import CycleTask, TaskDependency

MAX_DIRECT_DEPENDENTS = 2


# Errors (Module 8)
# Raised by apply_task_shift and caught in views.py to build the 409
# conflict payloads described in the Design Doc (API-02). Each carries
# enough structured data for the frontend to show a concrete message
# without guessing at wording.

class DependencyConflict(Exception):
    def __init__(self, error, message, task_id=None, **extra):
        self.error = error
        self.message = message
        self.task_id = task_id
        self.extra = extra
        super().__init__(message)

    def as_response_payload(self):
        payload = {"error": self.error, "message": self.message}
        if self.task_id is not None:
            payload["task_id"] = self.task_id
        payload.update(self.extra)
        return payload


# Dependency graph helpers
# TaskDependency.task is the dependent (downstream), depends_on_task is the
# prerequisite (upstream). template_task.dependent_tasks therefore gives the
# TEMPLATE_TASKs that directly depend on template_task (its direct downstream).

def get_direct_dependent_template_tasks(template_task):
    """TEMPLATE_TASKs that directly depend on this one (fan-out, max 2)."""
    return [dep.task for dep in template_task.dependent_tasks.select_related("task").all()]


def get_direct_dependent_cycle_tasks(cycle, template_task):
    """CYCLE_TASKs in this cycle whose template task directly depends on template_task."""
    dependent_ids = [t.pk for t in get_direct_dependent_template_tasks(template_task)]
    if not dependent_ids:
        return CycleTask.objects.none()
    return CycleTask.objects.filter(cycle=cycle, template_task_id__in=dependent_ids)


def get_prerequisite_cycle_tasks(cycle, template_task, exclude_cycle_task_id=None):
    """CYCLE_TASKs in this cycle that template_task directly depends on.

    Reverse direction of get_direct_dependent_cycle_tasks. A task can have
    more than one prerequisite (no cap on this side, only fan-out is
    capped), so this always returns a queryset, never assumes just one.
    """
    prerequisite_ids = [
        dep.depends_on_task_id for dep in template_task.dependencies.all()
    ]
    if not prerequisite_ids:
        return CycleTask.objects.none()
    queryset = CycleTask.objects.filter(cycle=cycle, template_task_id__in=prerequisite_ids)
    if exclude_cycle_task_id is not None:
        queryset = queryset.exclude(pk=exclude_cycle_task_id)
    return queryset

def get_allowed_dependency_targets(task):
    """Every TemplateTask in the same template that `task` could validly
    depend on: excludes itself, and anything that would close a
    circular chain if picked. Used to populate a "depends on" dropdown
    in the template editor so the user is never even offered a choice
    the backend would reject for that specific reason.

    Offset conflicts and the fan-out cap are deliberately not filtered
    out here, both depend on values that can still change before the
    user actually submits (this task's own offset, how many other
    dependents a candidate already has), those get checked for real by
    /task-dependencies/validate/ once a specific candidate is picked.
    """
    from templates_mgmt.models import TemplateTask

    candidates = TemplateTask.objects.filter(template_id=task.template_id).exclude(pk=task.pk)
    return [candidate for candidate in candidates if not would_create_cycle(task, candidate)]


def would_create_cycle(task, depends_on_task, visited=None):
    """True if making `task` depend on `depends_on_task` would close a loop.

    Walks forward from `task` through existing dependent_tasks edges; if
    depends_on_task is reachable, the new edge would complete a circle.
    Used by TaskDependencyViewSet before saving a new edge.
    """
    if task.pk == depends_on_task.pk:
        return True

    visited = visited if visited is not None else set()
    for downstream in get_direct_dependent_template_tasks(task):
        if downstream.pk == depends_on_task.pk:
            return True
        if downstream.pk not in visited:
            visited.add(downstream.pk)
            if would_create_cycle(downstream, depends_on_task, visited):
                return True
    return False


def detect_existing_cycle(template_task, visited=None, origin=None):
    """True if template_task sits on a cycle in the graph as it exists now.

    Different from would_create_cycle: this checks already-saved edges,
    used defensively inside apply_task_shift (Module 8 spec requires a
    circular check on every recalculation call, not just at edge creation).
    """
    origin = origin or template_task
    visited = visited if visited is not None else set()
    for downstream in get_direct_dependent_template_tasks(template_task):
        if downstream.pk == origin.pk:
            return True
        if downstream.pk not in visited:
            visited.add(downstream.pk)
            if detect_existing_cycle(downstream, visited, origin):
                return True
    return False


def assert_dependent_capacity(depends_on_task, exclude_dependency_id=None):
    """FR-7.2: a task may have at most MAX_DIRECT_DEPENDENTS direct dependents."""
    existing = TaskDependency.objects.filter(depends_on_task=depends_on_task)
    if exclude_dependency_id is not None:
        existing = existing.exclude(pk=exclude_dependency_id)
    if existing.count() >= MAX_DIRECT_DEPENDENTS:
        raise DependencyConflict(
            error="dependent_capacity_exceeded",
            message=(
                f"Task '{depends_on_task.task_name}' already has "
                f"{MAX_DIRECT_DEPENDENTS} tasks depending on it directly."
            ),
            task_id=depends_on_task.pk,
        )


def check_offset_conflict(task, depends_on_task):
    """Template authoring time: reject a dependency edge whose dependent
    task's own day_offset already falls before its prerequisite would
    finish. Left alone, this produces a schedule that can never be
    satisfied, especially for fixed-date tasks, which can never move to
    fix it later. Checked when the TaskDependency edge is created/edited,
    not when the offset itself changes afterwards (see note in views.py).
    """
    upstream_end = depends_on_task.day_offset + (depends_on_task.duration_days or 0)
    if task.day_offset < upstream_end:
        raise DependencyConflict(
            error="fixed_date_conflict" if task.is_fixed_date else "offset_conflict",
            message=(
                f"Task '{task.task_name}' is set to start on day {task.day_offset}, "
                f"before '{depends_on_task.task_name}' finishes on day {upstream_end}."
            ),
            task_id=task.pk,
        )


def copy_dependencies(source_template, task_id_map, validate_offsets=False, skip_task_ids=None):
    """Rebuild every TaskDependency edge from source_template onto the
    tasks in task_id_map (old TemplateTask.pk -> new TemplateTask
    instance). Used everywhere a template gets copied (new version,
    duplicate, share), none of these copied dependency edges before this,
    every one silently dropped them.

    validate_offsets=True re-checks check_offset_conflict on each copied
    edge, needed when the copy also allows editing offsets (template
    versioning with task overrides). Skip it for a byte-for-byte copy
    (duplicate, share) where offsets never change, nothing to check.

    skip_task_ids excludes tasks whose dependencies are being set
    explicitly elsewhere instead of copied (versioning's depends_on
    override), so this only fills in the ones left untouched.
    """
    skip_task_ids = skip_task_ids or set()
    for dependency in TaskDependency.objects.filter(
        task__template=source_template
    ).select_related("task", "depends_on_task"):
        if dependency.task.template_task_id in skip_task_ids:
            continue
        new_task = task_id_map.get(dependency.task.template_task_id)
        new_depends_on = task_id_map.get(dependency.depends_on_task.template_task_id)
        if new_task is None or new_depends_on is None:
            continue
        if validate_offsets:
            check_offset_conflict(new_task, new_depends_on)
        TaskDependency.objects.create(task=new_task, depends_on_task=new_depends_on)


def revalidate_task_offsets(template_task):
    """Call after a TemplateTask's day_offset/duration_days changes. Re-runs
    check_offset_conflict on every existing edge touching this task, in
    both directions, since moving a task can break a dependency that was
    fine before (it could now start too early, or finish too late for a
    downstream fixed task).
    """
    for dependency in template_task.dependencies.select_related("depends_on_task").all():
        check_offset_conflict(template_task, dependency.depends_on_task)

    for dependency in template_task.dependent_tasks.select_related("task").all():
        check_offset_conflict(dependency.task, template_task)

def collect_dependency_violations(task, depends_on_task, exclude_dependency_id=None):
    """Runs every check a new or edited TaskDependency edge must pass,
    circular chain, offset conflict, fan-out capacity, and returns every
    violation found, not just the first. Used by TaskDependencyViewSet
    (both the real create/update path and the validate dry run) so the
    frontend can show a user every reason a proposed edge would be
    rejected in one response, instead of them fixing one problem,
    resubmitting, and only then discovering the next one.

    Does not call anything new, would_create_cycle, check_offset_conflict,
    and assert_dependent_capacity are unchanged, this only composes them
    and gathers what they report instead of stopping at the first one.

    Returns a list of {"error": ..., "message": ..., ...} dicts, the
    same shape DependencyConflict.as_response_payload() already
    produces. An empty list means the edge is valid.
    """
    violations = []

    if would_create_cycle(task, depends_on_task):
        violations.append({
            "error": "circular_dependency",
            "message": "This dependency would create a circular chain.",
            "task_id": task.pk,
        })

    try:
        check_offset_conflict(task, depends_on_task)
    except DependencyConflict as exc:
        violations.append(exc.as_response_payload())

    try:
        assert_dependent_capacity(depends_on_task, exclude_dependency_id=exclude_dependency_id)
    except DependencyConflict as exc:
        violations.append(exc.as_response_payload())

    return violations

# Date recalculation (FR-6.6, FR-7)

def recalculate_shifted_dates(cycle_task, delay_days=None, new_start_date=None, new_end_date=None):
    """Recompute one task's own start/end pair from exactly one edit type.

    delay_days: shift both dates by N days, duration preserved.
    new_start_date: start moves, duration preserved (end follows).
    new_end_date: end moves only, start stays put (duration changes).
    Returns (new_start, new_end) without saving.
    """
    duration = cycle_task.calculated_end_date - cycle_task.calculated_start_date

    if delay_days is not None:
        new_start = cycle_task.calculated_start_date + timedelta(days=delay_days)
        return new_start, new_start + duration

    if new_start_date is not None:
        return new_start_date, new_start_date + duration

    if new_end_date is not None:
        return cycle_task.calculated_start_date, new_end_date

    raise ValueError("One of delay_days, new_start_date, new_end_date is required.")


def check_single_task_gap(cycle_task, new_end_date):
    """Single-task mode: true only if no direct dependent needs to move.

    A dependent needs to move only if its current start would now fall
    before the edited task's new end date.
    """
    dependents = get_direct_dependent_cycle_tasks(cycle_task.cycle, cycle_task.template_task)
    for dependent in dependents:
        if dependent.calculated_start_date < new_end_date:
            return False, dependent
    return True, None


def check_upstream_feasibility(cycle_task, new_start_date):
    """A task's new start can never fall before any of its own
    prerequisites' current end date in this cycle.

    Only needed for backward moves or direct start/end edits, a forward
    delay is always safe since it only ever moves further past whatever
    already finished. Checked against every prerequisite, not just one,
    since a task can depend on more than one upstream task (fan-out is
    capped at 2, but a task's own number of prerequisites isn't).
    """
    for prerequisite in get_prerequisite_cycle_tasks(cycle_task.cycle, cycle_task.template_task):
        if new_start_date < prerequisite.calculated_end_date:
            raise DependencyConflict(
                error="upstream_conflict",
                message=(
                    f"Task '{cycle_task.task_name}' cannot start on {new_start_date} "
                    f"because it depends on '{prerequisite.task_name}', which does not "
                    f"finish until {prerequisite.calculated_end_date}."
                ),
                task_id=prerequisite.pk,
            )


def max_safe_delay_days(cycle_task):
    """Largest delay (in days) that needs no dependent to move. None if no dependents."""
    dependents = get_direct_dependent_cycle_tasks(cycle_task.cycle, cycle_task.template_task)
    if not dependents:
        return None
    gaps = [(d.calculated_start_date - cycle_task.calculated_end_date).days for d in dependents]
    return max(min(gaps), 0)


# Cascade planning and application (Module 8 core)

def plan_cascade(cycle_task, new_end_date, visited_ids=None, override_fixed=False):
    """Read-only downstream walk. Returns a list of step dicts, one per
    directly and transitively dependent CYCLE_TASK, in traversal order.

    Without override_fixed, traversal stops down a branch once a task
    can't be shifted (fixed): the branch beyond that point is left out
    of the plan entirely, and the step is marked shiftable=False. With
    override_fixed=True, a fixed dependent is included as a normal
    shiftable step (its is_fixed_date flag is untouched, only its
    dates move) and the walk continues past it — this is what makes
    it possible to actually move a fixed downstream milestone instead
    of just being told the whole cascade is blocked by it.
    """
    visited_ids = visited_ids if visited_ids is not None else {cycle_task.pk}
    steps = []

    for dependent in get_direct_dependent_cycle_tasks(cycle_task.cycle, cycle_task.template_task):
        if dependent.pk in visited_ids:
            continue
        visited_ids.add(dependent.pk)

        # A dependent can have more than one prerequisite. new_end_date only
        # reflects the branch we're walking down, if another prerequisite of
        # this dependent finishes even later, that has to win, otherwise
        # we'd shift the dependent to a date that's still invalid.
        other_prerequisite_ends = [
            p.calculated_end_date
            for p in get_prerequisite_cycle_tasks(
                dependent.cycle, dependent.template_task, exclude_cycle_task_id=cycle_task.pk
            )
        ]
        required_start = max([new_end_date] + other_prerequisite_ends)

        if dependent.calculated_start_date >= required_start:
            # Already clear of every prerequisite, nothing to do.
            continue

        if dependent.is_fixed_date and not override_fixed:
            steps.append({
                "cycle_task_id": dependent.pk,
                "task_name": dependent.task_name,
                "shiftable": False,
                "blocking_reason": "fixed_date",
            })
            continue

        duration = dependent.calculated_end_date - dependent.calculated_start_date
        planned_start = required_start
        planned_end = planned_start + duration
        steps.append({
            "cycle_task_id": dependent.pk,
            "task_name": dependent.task_name,
            "shiftable": True,
            "new_start_date": planned_start,
            "new_end_date": planned_end,
            "was_fixed": dependent.is_fixed_date,
        })
        steps.extend(plan_cascade(dependent, planned_end, visited_ids, override_fixed))

    return steps


def preview_task_shift(cycle_task, delay_days=None, new_start_date=None, new_end_date=None):
    """No writes. Everything the frontend needs to enable/disable and label
    the single-task vs cascade choice before the user commits (INT-07).
    """
    new_start, new_end = recalculate_shifted_dates(
        cycle_task, delay_days=delay_days, new_start_date=new_start_date, new_end_date=new_end_date
    )
    try:
        check_upstream_feasibility(cycle_task, new_start)
        upstream_conflict = None
    except DependencyConflict as exc:
        upstream_conflict = exc.as_response_payload()

    single_ok, blocking = check_single_task_gap(cycle_task, new_end)
    cascade_plan = plan_cascade(cycle_task, new_end)

    return {
        "cycle_task_id": cycle_task.pk,
        "planned_start_date": new_start,
        "planned_end_date": new_end,
        "max_safe_delay_days": max_safe_delay_days(cycle_task),
        "upstream_conflict": upstream_conflict,
        "single_possible": single_ok and upstream_conflict is None,
        "single_blocking_task": blocking.task_name if blocking else None,
        # EVERY step must be shiftable, not just some of them — a
        # cascade that would leave even one downstream fixed task
        # stranded (unable to move to keep the dependency valid) is
        # not actually possible without an explicit override.
        "cascade_possible": all(step["shiftable"] for step in cascade_plan) and upstream_conflict is None,
        "cascade_plan": cascade_plan,
    }


def apply_task_shift(cycle_task, scope, delay_days=None, new_start_date=None,
                      new_end_date=None, override_fixed=False):
    """Writes. scope is 'single' or 'cascade'.

    Returns {"shifted": [...], "warnings": [...]}. Raises DependencyConflict
    (caught in views.py -> 409) only when the edited task itself cannot move
    at all (fixed and not overridden, single-mode gap conflict, or an
    existing circular dependency). Blocked branches inside a cascade are
    reported as warnings, not exceptions, so the rest of the path still
    applies.
    """
    if cycle_task.is_fixed_date and not override_fixed:
        raise DependencyConflict(
            error="fixed_task_locked",
            message=(
                f"Task '{cycle_task.task_name}' has a fixed date and cannot be shifted; "
                "pass override_fixed=true to move it anyway."
            ),
            task_id=cycle_task.pk,
        )

    if detect_existing_cycle(cycle_task.template_task):
        # Defensive: should never trigger if TaskDependencyViewSet validation
        # ran correctly at creation time, kept here per Module 8 spec.
        raise DependencyConflict(
            error="circular_dependency",
            message=f"Task '{cycle_task.task_name}' is part of a circular dependency chain.",
            task_id=cycle_task.pk,
        )

    new_start, new_end = recalculate_shifted_dates(
        cycle_task, delay_days=delay_days, new_start_date=new_start_date, new_end_date=new_end_date
    )
    check_upstream_feasibility(cycle_task, new_start)

    shifted = [{
        "cycle_task_id": cycle_task.pk,
        "task_name": cycle_task.task_name,
        "old_start_date": cycle_task.calculated_start_date,
        "old_end_date": cycle_task.calculated_end_date,
        "new_start_date": new_start,
        "new_end_date": new_end,
    }]

    if scope == "single":
        single_ok, blocking = check_single_task_gap(cycle_task, new_end)
        if not single_ok:
            raise DependencyConflict(
                error="insufficient_gap",
                message=(
                    f"Task '{cycle_task.task_name}' cannot be shifted alone because "
                    f"dependent task '{blocking.task_name}' would need to move too; "
                    "use cascade mode to shift the whole path."
                ),
                task_id=blocking.pk,
            )
        cycle_task.calculated_start_date = new_start
        cycle_task.calculated_end_date = new_end
        cycle_task.save(update_fields=["calculated_start_date", "calculated_end_date"])
        return {"shifted": shifted, "warnings": []}

    # scope == "cascade": plan first, and REFUSE the whole operation if
    # any downstream task can't move to keep the dependency valid — a
    # fixed-date dependent that gets left behind while its
    # prerequisite moves past it is not a "warning", it's the
    # dependency itself being violated (the prerequisite now finishes
    # AFTER the thing that's supposed to come after it). override_fixed
    # here means "move that fixed downstream task too", not "silently
    # ignore that it would be stranded".
    plan = plan_cascade(cycle_task, new_end, override_fixed=override_fixed)
    blocked_steps = [step for step in plan if not step["shiftable"]]

    if blocked_steps and not override_fixed:
        blocking = blocked_steps[0]
        raise DependencyConflict(
            error="cascade_blocked_by_fixed_task",
            message=(
                f"Task '{blocking['task_name']}' has a fixed date and would need to move "
                f"to keep this dependency chain valid. Pass override_fixed=true to move it "
                f"too, or reschedule '{blocking['task_name']}' directly first."
            ),
            task_id=blocking["cycle_task_id"],
        )

    cycle_task.calculated_start_date = new_start
    cycle_task.calculated_end_date = new_end
    cycle_task.save(update_fields=["calculated_start_date", "calculated_end_date"])

    warnings = []
    for step in plan:
        dependent = CycleTask.objects.get(pk=step["cycle_task_id"])
        shifted.append({
            "cycle_task_id": dependent.pk,
            "task_name": dependent.task_name,
            "old_start_date": dependent.calculated_start_date,
            "old_end_date": dependent.calculated_end_date,
            "new_start_date": step["new_start_date"],
            "new_end_date": step["new_end_date"],
        })
        dependent.calculated_start_date = step["new_start_date"]
        dependent.calculated_end_date = step["new_end_date"]
        dependent.save(update_fields=["calculated_start_date", "calculated_end_date"])
        if step.get("was_fixed"):
            warnings.append({
                "error": "fixed_date_moved",
                "task_id": dependent.pk,
                "message": f"Task '{dependent.task_name}' has a fixed date and was moved anyway (override_fixed).",
            })

    return {"shifted": shifted, "warnings": warnings}