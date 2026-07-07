"""
templates_mgmt/scheduling.py

Single, authoritative implementation of "what day does a task
actually start on, once its dependency chain is accounted for."

This exists because the same question gets asked in three
different places — creating a cycle from a template, recalculating
a running cycle after a delay, and previewing a template's timeline
before it's ever been saved — and having three separate
hand-written graph walks (as this codebase used to) is exactly how
they silently disagree with each other.

Model, matching the Requirements Collection / Process Design docs:
  - Start-driven (default): a task's effective start is pushed to
    at least the latest end date of everything it depends on.
    "delay to Task A shifts all downstream dependent tasks... chains
    propagate automatically."
  - Fixed-end-date: never shifted by a dependency. If a dependency
    would require a later start than the fixed offset allows, that's
    reported as a conflict rather than silently moved or rejected —
    matching the Process Design event-response diagram's
    "Check fixed-end-date constraint -> Conflict warning" branch.
  - Circular dependencies: detected and reported rather than causing
    infinite recursion. The involved task falls back to its own raw
    offset (no dependency adjustment) since no valid order exists.
"""


def resolve_effective_offsets(nodes, edges):
    """
    nodes: {task_id: {"offset": int, "duration": int, "fixed": bool}}
    edges: {task_id: [depends_on_task_id, ...]}

    Returns (effective, circular, conflicts):
      effective: {task_id: (effective_start, effective_end)}
      circular: set of task_ids where a circular dependency was detected
      conflicts: set of fixed-offset task_ids whose dependency chain
                 would require a later start than their fixed offset allows
    """
    effective = {}
    circular = set()
    conflicts = set()

    def resolve(task_id, visiting):
        if task_id in effective:
            return effective[task_id]

        node = nodes.get(task_id)
        if node is None:
            return None

        if task_id in visiting:
            circular.add(task_id)
            start = node["offset"]
            end = start + node["duration"]
            effective[task_id] = (start, end)
            return effective[task_id]

        max_dep_end = None
        for dep_id in edges.get(task_id, []):
            dep_result = resolve(dep_id, visiting | {task_id})
            if dep_result is None:
                continue
            _, dep_end = dep_result
            if max_dep_end is None or dep_end > max_dep_end:
                max_dep_end = dep_end

        if node["fixed"]:
            start = node["offset"]
            if max_dep_end is not None and max_dep_end > start:
                conflicts.add(task_id)
        else:
            start = max(node["offset"], max_dep_end) if max_dep_end is not None else node["offset"]

        end = start + node["duration"]
        effective[task_id] = (start, end)
        return effective[task_id]

    for task_id in nodes:
        resolve(task_id, frozenset())

    return effective, circular, conflicts