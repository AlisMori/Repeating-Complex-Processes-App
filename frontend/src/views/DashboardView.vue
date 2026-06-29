<!-- /frontend/src/views/DashboardView.vue -->

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const router = useRouter()

// ── MOCK DATA (replace with API calls later) ──────────────
const loading = ref(false)

const stats = ref({
  runningCycles: 4,
  dueToday: 3,
  overdueTasks: 2,
  completedThisWeek: 12,
})

const cycles = ref([
  {
    id: 1,
    name: 'ICT302 S2 2026',
    template: 'Unit Coordination Template v3',
    startDate: '2 Jun 2026',
    endDate: '30 Nov 2026',
    progress: 62,
    status: 'overdue',
    tasks: { completed: 8, inProgress: 3, overdue: 1, pending: 5 },
  },
  {
    id: 2,
    name: 'Breeding Cycle 2026',
    template: "Cole's Advanced Breeding Template v2",
    startDate: '15 May 2026',
    endDate: '15 Dec 2026',
    progress: 45,
    status: 'overdue',
    tasks: { completed: 5, inProgress: 2, overdue: 1, pending: 8 },
  },
  {
    id: 3,
    name: 'Garden Planting 2026',
    template: 'Annual Planting Template v1',
    startDate: '1 Jun 2026',
    endDate: '30 Sep 2026',
    progress: 30,
    status: 'running',
    tasks: { completed: 3, inProgress: 1, overdue: 0, pending: 8 },
  },
  {
    id: 4,
    name: 'ICT302 TJA 2026',
    template: 'Unit Coordination Template v3',
    startDate: '5 Jun 2026',
    endDate: '15 Nov 2026',
    progress: 18,
    status: 'running',
    tasks: { completed: 2, inProgress: 1, overdue: 0, pending: 10 },
  },
])

const upcomingTasks = ref([
  { id: 1, name: 'Submit Exam Paper', cycle: 'ICT302 S2 2026', due: '2 days ago', dueType: 'overdue', mandatory: true },
  { id: 2, name: 'Order Husbandry Supplies', cycle: 'Breeding Cycle 2026', due: '1 day ago', dueType: 'overdue', mandatory: true },
  { id: 3, name: 'Update LMS Content', cycle: 'ICT302 TJA 2026', due: 'Today', dueType: 'today', mandatory: false },
  { id: 4, name: 'Prepare Seedling Beds', cycle: 'Garden Planting 2026', due: 'Today', dueType: 'today', mandatory: false },
  { id: 5, name: 'Write Assignment Brief', cycle: 'ICT302 S2 2026', due: 'In 3 days', dueType: 'soon', mandatory: true },
])

const activeActivities = ref([
  { id: 1, name: 'Teaching the Unit', cycle: 'ICT302 S2 2026', day: 9, totalDays: 180 },
  { id: 2, name: 'Growing seedlings', cycle: 'Garden Planting 2026', day: 10, totalDays: 42 },
  { id: 3, name: 'Mating period', cycle: 'Breeding Cycle 2026', day: 12, totalDays: 21 },
])

const overdueCycles = computed(() => cycles.value.filter(c => c.status === 'overdue'))

function openCycle(id) {
  router.push({ name: 'cycle-detail', params: { id } })
}

function progressColor(pct) {
  if (pct >= 75) return '#22C55E'
  if (pct >= 40) return '#7C3AED'
  return '#7C3AED'
}
</script>

<template>
  <AppLayout>

    <!-- TOPBAR -->
    <template #topbar>
      <span class="topbar-title">Dashboard</span>
      <span class="topbar-date">{{ new Date().toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) }}</span>
      <div style="margin-left: auto; display: flex; gap: 10px;">
        <BaseButton variant="primary" size="sm" @click="router.push({ name: 'cycle-create' })">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          New Cycle
        </BaseButton>
      </div>
    </template>

    <!-- CONTENT -->
    <div class="dashboard">

      <!-- STAT CARDS -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-icon" style="background:#F5F3FF;">
            <svg viewBox="0 0 24 24" fill="none" stroke="#7C3AED" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
          </div>
          <div>
            <div class="stat-value">{{ stats.runningCycles }}</div>
            <div class="stat-label">Running cycles</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon" style="background:#FFFBEB;">
            <svg viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
          </div>
          <div>
            <div class="stat-value">{{ stats.dueToday }}</div>
            <div class="stat-label">Due today</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon" style="background:#FEF2F2;">
            <svg viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
          </div>
          <div>
            <div class="stat-value" style="color: var(--danger);">{{ stats.overdueTasks }}</div>
            <div class="stat-label">Overdue tasks</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon" style="background:#F0FDF4;">
            <svg viewBox="0 0 24 24" fill="none" stroke="#22C55E" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          </div>
          <div>
            <div class="stat-value" style="color: var(--success);">{{ stats.completedThisWeek }}</div>
            <div class="stat-label">Completed this week</div>
          </div>
        </div>
      </div>

      <!-- OVERDUE ALERT -->
      <div v-if="overdueCycles.length" class="alert-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <div>
          <div class="alert-title">{{ stats.overdueTasks }} overdue tasks require your attention</div>
          <div class="alert-desc">Submit Exam Paper (ICT302 S2 2026) is 2 days overdue · Order Husbandry Supplies (Breeding Cycle 2026) is 1 day overdue</div>
        </div>
      </div>

      <!-- TWO COLUMN -->
      <div class="two-col">

        <!-- LEFT: RUNNING CYCLES -->
        <div class="col-main">
          <div class="section-header">
            <span class="section-title">Running cycles</span>
            <span class="section-link" @click="router.push({ name: 'cycles' })">View all →</span>
          </div>

          <div class="cycles-list">
            <div
              v-for="cycle in cycles"
              :key="cycle.id"
              class="cycle-card"
              @click="openCycle(cycle.id)"
            >
              <div class="cycle-top">
                <div>
                  <div class="cycle-name">{{ cycle.name }}</div>
                  <div class="cycle-meta">{{ cycle.template }} · Started {{ cycle.startDate }}</div>
                </div>
                <span class="cycle-badge" :class="cycle.status === 'overdue' ? 'badge-overdue' : 'badge-running'">
                  {{ cycle.status === 'overdue' ? '⚠ Overdue task' : '● Running' }}
                </span>
              </div>

              <!-- Progress bar -->
              <div class="progress-row">
                <div class="progress-bg">
                  <div class="progress-fill" :style="{ width: cycle.progress + '%', background: progressColor(cycle.progress) }"></div>
                </div>
                <span class="progress-pct">{{ cycle.progress }}%</span>
              </div>

              <!-- Task chips -->
              <div class="task-chips">
                <span class="chip"><span class="chip-dot" style="background:var(--success);"></span>{{ cycle.tasks.completed }} completed</span>
                <span class="chip"><span class="chip-dot" style="background:var(--warning);"></span>{{ cycle.tasks.inProgress }} in progress</span>
                <span v-if="cycle.tasks.overdue" class="chip"><span class="chip-dot" style="background:var(--danger);"></span>{{ cycle.tasks.overdue }} overdue</span>
                <span class="chip"><span class="chip-dot" style="background:var(--border);"></span>{{ cycle.tasks.pending }} pending</span>
              </div>

              <div class="cycle-dates">
                <span>{{ cycle.startDate }} → {{ cycle.endDate }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- RIGHT: UPCOMING + ACTIVITIES -->
        <div class="col-side">

          <!-- Upcoming tasks -->
          <div class="section-header">
            <span class="section-title">Upcoming tasks</span>
            <span class="section-link" @click="router.push({ name: 'cycles' })">See all</span>
          </div>

          <div class="task-list">
            <div v-for="task in upcomingTasks" :key="task.id" class="task-row">
              <div class="task-checkbox"></div>
              <div class="task-info">
                <div class="task-name">{{ task.name }}</div>
                <div class="task-cycle">{{ task.cycle }}</div>
              </div>
              <span class="task-due" :class="`due-${task.dueType}`">{{ task.due }}</span>
              <span v-if="task.mandatory" class="task-req">REQ</span>
            </div>
          </div>

          <!-- Active activities -->
          <div class="section-header" style="margin-top: 20px;">
            <span class="section-title">Active activities</span>
          </div>

          <div class="activity-list">
            <div v-for="act in activeActivities" :key="act.id" class="activity-row">
              <div class="activity-name">{{ act.name }}</div>
              <div class="activity-meta">{{ act.cycle }} · Day {{ act.day }} of {{ act.totalDays }}</div>
              <div class="activity-bar-bg">
                <div class="activity-bar-fill" :style="{ width: (act.day / act.totalDays * 100) + '%' }"></div>
              </div>
            </div>
          </div>

        </div>
      </div>

    </div>
  </AppLayout>
</template>

<style scoped>
.topbar-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.topbar-date { font-size: 13px; color: var(--text-muted); }

.dashboard { display: flex; flex-direction: column; gap: 20px; }

/* STATS */
.stats-row { display: flex; gap: 14px; }

.stat-card {
  flex: 1;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: 14px 18px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-icon {
  width: 36px; height: 36px;
  border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}

.stat-icon svg { width: 17px; height: 17px; }

.stat-value { font-size: 22px; font-weight: 600; color: var(--text-primary); line-height: 1; margin-bottom: 2px; }
.stat-label { font-size: 12px; color: var(--text-muted); }

/* ALERT */
.alert-box {
  background: var(--danger-bg);
  border: 1px solid #FECACA;
  border-radius: var(--radius-md);
  padding: 11px 14px;
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.alert-box svg { width: 15px; height: 15px; flex-shrink: 0; margin-top: 1px; }
.alert-title { font-size: 13px; font-weight: 600; color: #B91C1C; margin-bottom: 2px; }
.alert-desc { font-size: 12px; color: #991B1B; }

/* TWO COLUMN */
.two-col { display: flex; gap: 20px; align-items: flex-start; }
.col-main { flex: 1; min-width: 0; }
.col-side { width: 280px; flex-shrink: 0; }

/* SECTION HEADER */
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.section-title { font-size: 13.5px; font-weight: 600; color: var(--text-primary); }
.section-link { font-size: 12.5px; color: var(--violet); cursor: pointer; }
.section-link:hover { text-decoration: underline; }

/* CYCLE CARDS */
.cycles-list { display: flex; flex-direction: column; gap: 10px; }

.cycle-card {
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: 14px 18px;
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.cycle-card:hover { border-color: #C4B5FD; box-shadow: var(--shadow-sm); }

.cycle-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.cycle-name { font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 2px; }
.cycle-meta { font-size: 12px; color: var(--text-muted); }

.cycle-badge { font-size: 11.5px; font-weight: 500; padding: 3px 10px; border-radius: 20px; flex-shrink: 0; }
.badge-running { background: var(--success-bg); color: #15803D; }
.badge-overdue { background: var(--danger-bg); color: #B91C1C; }

.progress-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.progress-bg { flex: 1; height: 6px; border-radius: 3px; background: var(--border-light); }
.progress-fill { height: 6px; border-radius: 3px; transition: width 0.3s ease; }
.progress-pct { font-size: 12px; font-weight: 500; color: var(--text-secondary); flex-shrink: 0; width: 32px; text-align: right; }

.task-chips { display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 8px; }

.chip {
  display: flex; align-items: center; gap: 4px;
  font-size: 11.5px; padding: 3px 8px;
  border-radius: 5px; border: 1px solid var(--border-light);
  color: var(--text-secondary); background: var(--bg-page);
}

.chip-dot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }

.cycle-dates { font-size: 11.5px; color: var(--text-muted); }

/* UPCOMING TASKS */
.task-list { display: flex; flex-direction: column; gap: 7px; margin-bottom: 4px; }

.task-row {
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.task-checkbox {
  width: 15px; height: 15px;
  border-radius: 4px; border: 1.5px solid var(--border);
  flex-shrink: 0;
}

.task-info { flex: 1; min-width: 0; }
.task-name { font-size: 13px; font-weight: 500; color: var(--text-primary); }
.task-cycle { font-size: 11px; color: var(--text-muted); margin-top: 1px; }

.task-due { font-size: 11px; font-weight: 500; padding: 2px 7px; border-radius: 4px; flex-shrink: 0; }
.due-overdue { background: var(--danger-bg); color: #B91C1C; }
.due-today   { background: var(--warning-bg); color: #92400E; }
.due-soon    { background: var(--info-bg); color: #1E40AF; }

.task-req { font-size: 10px; font-weight: 600; color: var(--danger); flex-shrink: 0; }

/* ACTIVITIES */
.activity-list { display: flex; flex-direction: column; gap: 8px; }

.activity-row {
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 10px 12px;
}

.activity-name { font-size: 13px; font-weight: 500; color: var(--text-primary); margin-bottom: 2px; }
.activity-meta { font-size: 11.5px; color: var(--text-muted); margin-bottom: 7px; }
.activity-bar-bg { height: 4px; border-radius: 2px; background: var(--violet-mid); }
.activity-bar-fill { height: 4px; border-radius: 2px; background: var(--violet); }

/* Responsive */
@media (max-width: 1024px) {
  .stats-row { flex-wrap: wrap; }
  .stats-row .stat-card { min-width: calc(50% - 7px); }
  .two-col { flex-direction: column; }
  .col-side { width: 100%; }
}
</style>
