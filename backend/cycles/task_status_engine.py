from datetime import date

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
    "in_progress": {"completed", "skipped"},
    "overdue": {"in_progress", "completed", "skipped"},
    "completed": set(),
    "skipped": set(),
}


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
    changes, no date shifts, no activity edits. Only a running cycle can
    be modified. Matches the "422 cycle not running" case already
    described for the shift endpoint in the Design Doc (API-02), applied
    consistently everywhere a cycle's contents can be edited.
    """
    if cycle.status != "running":
        raise CycleNotRunning(
            f"Cycle '{cycle.cycle_name}' is {cycle.get_status_display()}, it can no longer be modified."
        )


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

    allowed = ALLOWED_TRANSITIONS.get(cycle_task.status, set())
    if new_status not in allowed:
        raise InvalidStatusTransition(
            f"Task '{cycle_task.task_name}' cannot move from '{cycle_task.status}' to '{new_status}'."
        )


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