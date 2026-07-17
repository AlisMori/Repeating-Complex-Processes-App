from datetime import date

from .dependency_engine import get_prerequisite_cycle_tasks
from .models import CycleTask

# Statuses the system manages automatically, users can never set these
# directly through the API. Right now that's just "overdue", see
# mark_overdue_tasks below for where it gets set.
SYSTEM_ONLY_STATUSES = {"overdue"}

# FR-6.1, FR-6.4. Keys are a task's current status, values are the
# statuses a user is allowed to move it to directly through the API.
# completed and skipped are treated as terminal, no transition leads back
# out of either one. This is an assumption, not something the R&A states
# outright, worth confirming with the team if a "reopen" flow turns out
# to be needed later.
ALLOWED_TRANSITIONS = {
    "pending": {"in_progress", "skipped"},
    "in_progress": {"completed", "skipped", "pending"},
    "overdue": {"in_progress", "completed", "skipped"},
    "completed": {"pending"},
    "skipped": {"pending"},
}

# The only two statuses a prerequisite can be retroactively closed out
# as, see find_unresolved_prerequisites / apply_prerequisite_resolution
# below. Deliberately not the full ALLOWED_TRANSITIONS set, a
# prerequisite being resolved this way is always being closed out, never
# moved to in_progress.
RESOLVABLE_PREREQUISITE_STATUSES = {"completed", "skipped"}


class InvalidStatusTransition(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


class CycleNotRunning(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def assert_cycle_is_running(cycle):
    """A completed or shut-down cycle is frozen entirely, no status
    changes, no date shifts, no activity edits, no note edits. Only a
    running cycle can be modified. Matches the "422 cycle not running"
    case described for the shift endpoint in the Design Doc (API-02),
    applied consistently everywhere a cycle's contents can be edited.
    """
    if cycle.status != "running":
        raise CycleNotRunning(
            f"Cycle '{cycle.cycle_name}' is {cycle.get_status_display()}, it can no longer be modified."
        )


def effective_status_for_transitions(cycle_task, today=None):
    """The status to use when looking up ALLOWED_TRANSITIONS, which can
    differ from cycle_task.status itself: mark_overdue_tasks is a
    scheduled background job, so a task can sit visually overdue
    (past its own end date) for a while with status still literally
    "pending" until that job next runs. Without this, a user who
    finished a task late has to wait for the job to catch up before
    "Completed" even becomes an option — the actions available to the
    user should match what they can SEE (the task is late), not an
    internal detail of when a cron job last ran.
    """
    today = today or date.today()
    if cycle_task.status == "pending" and cycle_task.calculated_end_date < today:
        return "overdue"
    return cycle_task.status


def validate_status_transition(cycle_task, new_status):
    """FR-6.1, FR-6.4. Raises InvalidStatusTransition if the move isn't
    allowed. Setting the same status again is always a no-op, not an error.
    """
    if new_status == cycle_task.status:
        return

    if new_status in SYSTEM_ONLY_STATUSES:
        raise InvalidStatusTransition(
            f"'{new_status}' is set automatically by the system, it can't be set directly."
        )

    allowed = ALLOWED_TRANSITIONS.get(effective_status_for_transitions(cycle_task), set())
    if new_status not in allowed:
        raise InvalidStatusTransition(
            f"Task '{cycle_task.task_name}' cannot move from '{cycle_task.status}' to '{new_status}'."
        )


def find_unresolved_prerequisites(cycle_task):
    """Direct prerequisites of cycle_task that are not yet completed or
    skipped.

    Used when a task is being marked completed out of order, while
    something it directly depends on is still open. Completing the
    dependent task first would otherwise leave that prerequisite stuck
    with no natural way to close it out, the work it was blocking is
    already done. Only looks at direct prerequisites, not the whole
    upstream chain, matching how the dependency graph is walked
    everywhere else in this module (one hop at a time).
    """
    return list(
        get_prerequisite_cycle_tasks(cycle_task.cycle, cycle_task.template_task)
        .exclude(status__in=RESOLVABLE_PREREQUISITE_STATUSES)
    )


def apply_prerequisite_resolution(cycle_task, new_status):
    """Directly closes out a prerequisite task as completed or skipped.

    Only ever called after the caller has explicitly asked the user to
    choose one of the two, see find_unresolved_prerequisites. This
    bypasses the normal ALLOWED_TRANSITIONS table on purpose, a
    retroactive close-out did not travel through pending -> in_progress
    in the app, it already happened in the real world out of order,
    this just records the outcome the user confirmed.
    """
    if new_status not in RESOLVABLE_PREREQUISITE_STATUSES:
        raise InvalidStatusTransition(
            "A prerequisite left open by an out of order completion can only "
            "be resolved as 'completed' or 'skipped'."
        )
    cycle_task.status = new_status
    cycle_task.save(update_fields=["status"])


def maybe_complete_cycle(cycle):
    """A running cycle moves to completed once every mandatory task is
    done (completed or skipped), optional tasks don't block this (FR-6.7).
    "completed" already existed as a CycleInstance status choice but
    nothing in the codebase ever set it before this.

    A cycle with zero mandatory tasks never auto-completes here, nothing
    to require completion of, it stays running until shut down manually.
    """
    if cycle.status != "running":
        return

    mandatory_tasks = cycle.cycle_tasks.filter(is_mandatory=True)
    if not mandatory_tasks.exists():
        return

    if mandatory_tasks.exclude(status__in=["completed", "skipped"]).exists():
        return

    cycle.status = "completed"
    cycle.save(update_fields=["status"])


def activate_started_tasks(today=None):
    """Background job companion to mark_overdue_tasks. A pending task
    whose start date has arrived moves itself into in_progress on its
    own, the user does not need to remember to flip it by hand the
    moment work actually starts.

    Only touches tasks still sitting in pending, in a running cycle,
    whose calculated_start_date is today or earlier. Never touches
    in_progress, completed, skipped, or overdue tasks. A task whose end
    date has also already passed by the time this runs still gets
    picked up here first, then mark_overdue_tasks catches it in the
    same maintenance pass since in_progress is one of the statuses it
    checks, so nothing is left stuck a full day in the wrong state.
    """
    today = today or date.today()
    candidates = CycleTask.objects.filter(
        cycle__status="running",
        calculated_start_date__lte=today,
        status="pending",
    )
    return candidates.update(status="in_progress")


def mark_overdue_tasks(today=None):
    """Background job, see cycles/management/commands/mark_overdue_tasks.py.
    Design Doc 4.2.17 lists an overdue-check job as scheduler input, this
    is that job's actual logic, kept separate from the command itself so
    it's easy to call directly from tests or from django-q2 either way.

    Only touches tasks in running cycles, and only from statuses a task
    can actually still be in when its date passes, completed/skipped/
    overdue are all left alone.
    """
    today = today or date.today()
    candidates = CycleTask.objects.filter(
        cycle__status="running",
        calculated_end_date__lt=today,
        status__in=["pending", "in_progress"],
    )
    return candidates.update(status="overdue")


def run_scheduled_maintenance(today=None):
    """Single entry point the scheduler actually registers with
    django-q2 (see cycles/management/commands/setup_scheduled_jobs.py).
    Runs activate_started_tasks before mark_overdue_tasks, in that
    order, so a task that starts and is already overdue by the same day
    this runs is caught by the overdue check in the same pass instead
    of waiting another day inside in_progress.
    """
    today = today or date.today()
    activated = activate_started_tasks(today=today)
    overdue = mark_overdue_tasks(today=today)
    return {"activated": activated, "overdue": overdue}