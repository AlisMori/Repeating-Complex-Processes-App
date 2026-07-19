from datetime import date, timedelta

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import owned_cycles_q
from cycles.models import CycleInstance, CycleTask


class DashboardSummaryView(APIView):
    """
    FR-12: aggregates every running cycle (with progress), overdue
    tasks, and upcoming tasks into one payload — the dashboard
    previously fetched raw cycles/tasks/activities separately and
    computed all of this client-side; this does it server-side in
    one call instead.

    FR-12.2: each cycle's progress is computed strictly from ITS OWN
    cycle_tasks, scoped through the cycle foreign key — two
    overlapping running cycles can never mix each other's task
    counts, since every query here is scoped to a single cycle's own
    related tasks, never a global task queryset filtered by date
    range alone.

    This reads from cycles.models (CycleInstance, CycleTask) rather
    than owning any data itself — dashboard is purely an aggregation/
    read layer over data that genuinely lives in the cycles app.
    """

    permission_classes = [permissions.IsAuthenticated]

    # "Upcoming" window is not specified anywhere in FR-12 — 7 days is
    # a reasonable default, not a confirmed requirement. Worth
    # confirming with the team if a specific window is expected.
    UPCOMING_WINDOW_DAYS = 7

    def get(self, request):
        cycles = CycleInstance.objects.filter(
            owned_cycles_q(request.user), status="running"
        ).distinct()

        active_cycles_data = [
            self._serialize_cycle(cycle) for cycle in cycles
        ]

        today = date.today()
        upcoming_cutoff = today + timedelta(days=self.UPCOMING_WINDOW_DAYS)

        overdue_qs = (
            CycleTask.objects.filter(cycle__in=cycles, status="overdue")
            .select_related("cycle")
            .order_by("calculated_end_date")
        )
        upcoming_qs = (
            CycleTask.objects.filter(
                cycle__in=cycles,
                status__in=["pending", "in_progress"],
                calculated_start_date__gte=today,
                calculated_start_date__lte=upcoming_cutoff,
            )
            .select_related("cycle")
            .order_by("calculated_start_date")
        )

        return Response({
            "active_cycles": active_cycles_data,
            "overdue_tasks": [self._serialize_task(t) for t in overdue_qs],
            "upcoming_tasks": [self._serialize_task(t) for t in upcoming_qs],
        })

    def _serialize_cycle(self, cycle):
        tasks = cycle.cycle_tasks.all()
        mandatory_tasks = tasks.filter(is_mandatory=True)
        total_mandatory = mandatory_tasks.count()
        completed_mandatory = mandatory_tasks.filter(status="completed").count()
        progress_percent = (
            round((completed_mandatory / total_mandatory) * 100)
            if total_mandatory > 0 else 0
        )
        return {
            "cycle_id": cycle.cycle_id,
            "cycle_name": cycle.cycle_name,
            "status": cycle.status,
            "start_date": cycle.start_date,
            "total_tasks": tasks.count(),
            "completed_tasks": tasks.filter(status="completed").count(),
            "mandatory_tasks": total_mandatory,
            "completed_mandatory_tasks": completed_mandatory,
            "progress_percent": progress_percent,
        }

    def _serialize_task(self, t):
        return {
            "cycle_task_id": t.cycle_task_id,
            "task_name": t.task_name,
            "cycle_id": t.cycle_id,
            "cycle_name": t.cycle.cycle_name,
            "calculated_start_date": t.calculated_start_date,
            "calculated_end_date": t.calculated_end_date,
            "status": t.status,
        }
