# Frontend Integration Guide: Cycles (Cycle Instances, Tasks, Activities)

For Daria. Covers everything under `/api/cycles/`, `/api/cycle-tasks/`,
`/api/cycle-activities/`, and `/api/task-dependencies/`, built across
Module 7 (Cycle Instance Engine), Module 8 (Dependency Recalculation
Engine), and Module 9 (Runtime Task Management).

All endpoints require a JWT, same as everything else in the app. All
list/retrieve endpoints only ever return objects the authenticated user
owns or has shared access to, a request for someone else's object
returns 404, not 403.

## The three cycle statuses

A `CycleInstance.status` is one of `running`, `completed`, `shut_down`.

- **running**: the only status where anything inside the cycle can be
  edited. Created with this status automatically.
- **completed**: set automatically by the system, never by a direct
  request, once every mandatory task in the cycle reaches `completed` or
  `skipped`. Optional tasks don't block this.
- **shut_down**: set by calling the `shut_down` action manually, for
  ending a cycle early regardless of task state.

**Once a cycle is `completed` or `shut_down`, everything inside it is
frozen.** No task status changes, no date shifts, no activity edits.
Every one of those requests returns **422** with a message naming the
cycle and its status. Build the UI to disable all edit controls the
moment `cycle.status !== "running"`, don't rely on the backend rejection
alone for the UX.

---

## 1. Cycle Instances, `/api/cycles/`

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/cycles/` | Create a cycle from a template |
| GET | `/api/cycles/` | List the user's cycles |
| GET | `/api/cycles/{id}/` | Retrieve one cycle |
| POST | `/api/cycles/{id}/shut_down/` | End a cycle early |
| GET | `/api/cycles/{id}/export/` | Cycle plus all its tasks and activities |

### Create a cycle

```
POST /api/cycles/
{
  "template": 4,
  "cycle_name": "July Cohort",
  "start_date": "2026-07-01"
}
```
This one call also generates every `CycleTask` and `CycleActivity` for
the cycle behind the scenes, from the template's day offsets. Nothing
else needs to be created separately.

Read-only on this object always: `cycle_id`, `user`, `status`,
`created_at`. `status` can never be set on create or via `PATCH`, only
through `shut_down` or automatically on completion.

### Shut down

```
POST /api/cycles/{id}/shut_down/
```
No body needed. Idempotent, calling it again on an already shut-down
cycle just returns the current state, doesn't error.

### Export

```
GET /api/cycles/{id}/export/
```
Returns the cycle plus `cycle_tasks` and `cycle_activities` arrays in one
response, useful for a full cycle detail screen in one call instead of
three.

---

## 2. Cycle Tasks, `/api/cycle-tasks/`

This is the bulk of what changed recently, read this section closely.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/cycle-tasks/` | List (filterable by cycle, search on name/status/note) |
| GET | `/api/cycle-tasks/{id}/` | Retrieve one task |
| PATCH | `/api/cycle-tasks/{id}/` | Change status, **only** status |
| GET | `/api/cycle-tasks/{id}/available_statuses/` | What this task can move to right now |
| POST | `/api/cycle-tasks/{id}/shift_preview/` | Preview a date change, no writes |
| POST | `/api/cycle-tasks/{id}/shift/` | Actually change the task's dates |

### Only `status` is writable via PATCH

Every other field, `task_name`, `is_mandatory`, `is_fixed_date`,
`reminder_lead_days`, `note_text`, `cycle`, `template_task`, is read-only.
Sending them in a PATCH doesn't error, they're just silently ignored.
Dates are also read-only here on purpose, they only ever change through
`shift`, see below, this is what keeps the dependency graph consistent.

### Status state machine

```
pending ------> in_progress ------> completed
   |                  |
   +---------------> skipped <------+

overdue --> in_progress / completed / skipped   (system sets "overdue", never the user)
```

| Current status | Can move to |
| --- | --- |
| `pending` | `in_progress`, `skipped` |
| `in_progress` | `completed`, `skipped` |
| `overdue` | `in_progress`, `completed`, `skipped` |
| `completed` | nothing, terminal |
| `skipped` | nothing, terminal |

Setting `overdue` directly is always rejected (400), that status is only
ever set by a background job checking dates against today. Setting the
same status a task already has is always accepted as a harmless no-op.

**Use `available_statuses` to drive the UI** instead of hardcoding this
table client-side:
```
GET /api/cycle-tasks/{id}/available_statuses/
-> { "current_status": "pending", "available_statuses": ["in_progress", "skipped"] }
```
Call this whenever a task's detail view opens, and only show buttons for
whatever comes back. If the array is empty, the task is done, show no
action buttons at all.

### Changing a status

```
PATCH /api/cycle-tasks/{id}/
{ "status": "in_progress" }
```
200 with the updated task on success. 400 with `{"status": [...]}` if the
transition isn't allowed. 422 if the cycle isn't running.

Completing or skipping a task may cause its parent cycle to auto-complete
in the same request, if it was the last mandatory task pending. Worth
refetching the cycle (or just watching the cycle's status in whatever
state store you're using) after any status change that could plausibly
be the last one, no separate signal is sent for this, it just happens
silently server-side.

### Previewing a date change, before committing

```
POST /api/cycle-tasks/{id}/shift_preview/
{ "delay_days": 3 }
```
or `{ "new_start_date": "2026-07-10" }` or `{ "new_end_date": "2026-07-12" }`,
exactly one of the three, always.

Response:
```json
{
  "cycle_task_id": 301,
  "planned_start_date": "2026-07-13",
  "planned_end_date": "2026-07-15",
  "max_safe_delay_days": 0,
  "upstream_conflict": null,
  "single_possible": false,
  "single_blocking_task": "Sign contract",
  "cascade_possible": true,
  "cascade_plan": [
    {"cycle_task_id": 305, "task_name": "Send welcome kit", "shiftable": true, "new_start_date": "2026-07-15", "new_end_date": "2026-07-16"},
    {"cycle_task_id": 309, "task_name": "Final delivery", "shiftable": false, "blocking_reason": "fixed_date"}
  ]
}
```
This is a read-only call, nothing is saved. Use it to:
- Grey out the "shift this task only" option when `single_possible` is
  `false`, and show `single_blocking_task` as the reason why.
- Grey out the "shift dependent tasks" toggle entirely only when
  `cascade_possible` is `false`, otherwise leave it enabled, some
  branches can still move even if others are blocked.
- Show `max_safe_delay_days` as a hint, "up to N days needs no other
  tasks to move."
- List `cascade_plan` so the user can see exactly what will move and what
  won't before committing, each blocked entry explains why
  (`blocking_reason`).
- If `upstream_conflict` is not `null`, the proposed change is invalid
  outright regardless of scope, show that message and don't let the user
  proceed with either option.

### Committing a date change

```
POST /api/cycle-tasks/{id}/shift/
{
  "delay_days": 3,
  "scope": "cascade",
  "override_fixed": false
}
```
Same three date fields as preview, exactly one required. `scope` is
`"single"` or `"cascade"` (defaults to `"single"` if omitted, but send it
explicitly). `override_fixed` only matters if this specific task
`is_fixed_date`, it does not let a cascade push through a *different*
fixed task further down the chain, that's always blocked no matter what.

Success (200):
```json
{
  "cycle_task_id": 301,
  "scope": "cascade",
  "shifted_tasks": [
    {"cycle_task_id": 301, "task_name": "Sign contract", "old_start_date": "...", "old_end_date": "...", "new_start_date": "...", "new_end_date": "..."}
  ],
  "warnings": [
    {"error": "fixed_end_date_conflict", "task_id": 309, "message": "Task 'Final delivery' was not shifted because it has a fixed date; downstream tasks past it were left unchanged."}
  ]
}
```
`warnings` is not an error, the request still succeeded, `shifted_tasks`
lists everything that actually moved, `warnings` lists branches that
didn't, with a reason to show the user. Always render both.

Failure (409), the root task itself couldn't move at all:
```json
{ "error": "fixed_task_locked", "task_id": 301, "message": "Task 'Sign contract' has a fixed date and cannot be shifted; pass override_fixed=true to move it anyway." }
```
Possible `error` values: `fixed_task_locked`, `insufficient_gap`,
`upstream_conflict`, `circular_dependency`. Show `message` directly, it's
already written for a human to read.

Failure (422): the cycle isn't `running`. Failure (400): missing or more
than one of the three date fields, or an invalid `scope` value.

### A note on direct date edits vs delay

All three work through the same endpoint, `delay_days` shifts both dates
by N days keeping duration fixed, `new_start_date` moves the start and
keeps duration fixed (end follows), `new_end_date` moves only the end
(changes duration, start stays put). Pick whichever matches the UI
control the user interacted with, a date picker on the start field should
send `new_start_date`, one on the end field should send `new_end_date`, a
"+N days" control should send `delay_days`.

---

## 3. Cycle Activities, `/api/cycle-activities/`

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/cycle-activities/` | List |
| GET | `/api/cycle-activities/{id}/` | Retrieve one |
| PATCH | `/api/cycle-activities/{id}/` | Change dates, **only** dates |

Much simpler than tasks, activities have no status, no dependencies, and
no cascade engine involved at all.

```
PATCH /api/cycle-activities/{id}/
{ "calculated_start_date": "2026-07-05", "calculated_end_date": "2026-07-07" }
```
Only `calculated_start_date` and `calculated_end_date` are writable,
directly, no shift/preview step needed, there's nothing to cascade to.
Everything else (`activity_name`, `note_text`, `cycle`, `template_activity`)
is read-only. 200 on success, 422 if the parent cycle isn't `running`.

---

## 4. Task Dependencies, `/api/task-dependencies/`

This is template-level, not cycle-level, it defines the dependency graph
a template's tasks follow, which every cycle created from that template
inherits. Only relevant to a template-editing screen, not a running
cycle's screen, listed here for completeness since it's the same app.

```
POST /api/task-dependencies/
{ "task": 12, "depends_on_task": 10 }
```
`task` is the dependent, `depends_on_task` is the prerequisite. Rejected
(400) if it would create a circular chain, if the prerequisite already
has 2 direct dependents (the fan-out cap), or if the dependent task's
offset already falls before the prerequisite would finish.

---

## Quick reference: what's editable where

| Object | Editable fields | How |
| --- | --- | --- |
| CycleInstance | `status` | Only via `shut_down`, or automatic on completion |
| CycleTask | `status` | `PATCH`, validated transitions |
| CycleTask | dates | `shift` / `shift_preview` only, never raw `PATCH` |
| CycleActivity | dates | `PATCH`, direct, no engine |
| Everything else | nothing | Fixed at creation from the template |

## Error status codes, summary

| Code | Meaning |
| --- | --- |
| 400 | Bad input, invalid status transition, missing/extra shift fields |
| 403 / 404 | Not the owner (404 is used for cross-user access, not 403) |
| 409 | Shift conflict (fixed task, insufficient gap, upstream conflict, circular) |
| 422 | Cycle isn't running, everything in it is frozen |
