<!-- /frontend/src/views/DashboardView.vue -->

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import SmartSearch from '@/components/search/SmartSearch.vue'
import { useOnboardingStore } from '@/stores/onboarding'
import { getCycles, getCycleTasks, getCycleActivities } from '@/api/cycles'

const router = useRouter()
const onboardingStore = useOnboardingStore()

const cycles = ref([])
const cycleTasksMap = ref({}) // cycleId -> tasks[]
const cycleActivitiesMap = ref({}) // cycleId -> activities[]
const loading = ref(true)
const error = ref('')
const ganttScrollEl = ref(null)

const today = new Date()
today.setHours(0, 0, 0, 0)
const todayStr = today.toISOString().split('T')[0]

async function loadDashboard() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getCycles()
    cycles.value = Array.isArray(data) ? data : (data.results || [])

    // Load tasks AND activities for all running cycles in parallel
    const running = cycles.value.filter(c => c.status === 'running')
    const [taskResults, activityResults] = await Promise.all([
      Promise.all(running.map(c => getCycleTasks(c.cycle_id).then(r => ({
        cycleId: c.cycle_id,
        tasks: Array.isArray(r.data) ? r.data : (r.data.results || [])
      })))),
      Promise.all(running.map(c => getCycleActivities(c.cycle_id).then(r => ({
        cycleId: c.cycle_id,
        activities: Array.isArray(r.data) ? r.data : (r.data.results || [])
      })))),
    ])
    const taskMap = {}
    for (const { cycleId, tasks } of taskResults) taskMap[cycleId] = tasks
    cycleTasksMap.value = taskMap
    const activityMap = {}
    for (const { cycleId, activities } of activityResults) activityMap[cycleId] = activities
    cycleActivitiesMap.value = activityMap
  } catch (e) {
    error.value = 'Failed to load dashboard data.'
  } finally {
    loading.value = false
  }
}

// ── STATS ──────────────────────────────────────────────────
const runningCycles = computed(() => cycles.value.filter(c => c.status === 'running'))
const overdueCycles = computed(() => cycles.value.filter(c => c.status === 'overdue'))
const completedCycles = computed(() => cycles.value.filter(c => c.status === 'shut_down' || c.status === 'completed'))

// ── UPCOMING TASKS (next 14 days across all running cycles) ──
const upcomingTasks = computed(() => {
  const result = []
  const cutoff = new Date(today)
  cutoff.setDate(cutoff.getDate() + 14)

  for (const cycle of runningCycles.value) {
    const tasks = cycleTasksMap.value[cycle.cycle_id] || []
    for (const task of tasks) {
      if (task.status === 'completed') continue
      const start = new Date(task.calculated_start_date)
      start.setHours(0, 0, 0, 0)
      if (start >= today && start <= cutoff) {
        result.push({ ...task, cycleName: cycle.cycle_name, cycleId: cycle.cycle_id })
      }
    }
  }
  return result.sort((a, b) => new Date(a.calculated_start_date) - new Date(b.calculated_start_date))
})

// ── OVERDUE TASKS across all running cycles ──
const overdueTasksList = computed(() => {
  const result = []
  for (const cycle of runningCycles.value) {
    const tasks = cycleTasksMap.value[cycle.cycle_id] || []
    for (const task of tasks) {
      const end = new Date(task.calculated_end_date)
      end.setHours(0, 0, 0, 0)
      if (end < today && task.status !== 'completed' && task.status !== 'skipped') {
        result.push({ ...task, cycleName: cycle.cycle_name, cycleId: cycle.cycle_id })
      }
    }
  }
  return result.sort((a, b) => new Date(a.calculated_end_date) - new Date(b.calculated_end_date))
})

// ── GANTT DATA ──────────────────────────────────────────────
const GANTT_PX_PER_DAY = 16

const ganttData = computed(() => {
  if (runningCycles.value.length === 0) return null

  // Collect all dates to find global min/max
  const allDates = []
  for (const cycle of runningCycles.value) {
    allDates.push(new Date(cycle.start_date))
    const tasks = cycleTasksMap.value[cycle.cycle_id] || []
    for (const task of tasks) {
      if (task.calculated_start_date) allDates.push(new Date(task.calculated_start_date))
      if (task.calculated_end_date) allDates.push(new Date(task.calculated_end_date))
    }
  }
  if (allDates.length === 0) return null

  // Extend range: start 7 days before earliest, end 30 days after latest
  const minDate = new Date(Math.min(...allDates.map(d => d.getTime())))
  minDate.setDate(minDate.getDate() - 7)
  const maxDate = new Date(Math.max(...allDates.map(d => d.getTime())))
  maxDate.setDate(maxDate.getDate() + 30)
  const totalDays = Math.max(Math.round((maxDate - minDate) / (1000 * 60 * 60 * 24)), 1)

  // Today position, in days from minDate
  const todayOffsetDays = Math.max(0, Math.min(totalDays, (today - minDate) / (1000 * 60 * 60 * 24)))

  // Tick marks — a "nice" interval so the label density stays
  // readable whether the range is a few weeks or several months.
  const targetTickCount = 10
  const rawInterval = totalDays / targetTickCount
  const niceSteps = [1, 2, 5, 7, 10, 14, 30, 60, 90]
  const tickIntervalDays = niceSteps.find((step) => step >= rawInterval) || Math.ceil(rawInterval / 30) * 30
  const ticks = []
  for (let d = 0; d <= totalDays; d += tickIntervalDays) {
    const date = new Date(minDate)
    date.setDate(date.getDate() + d)
    ticks.push({ dayOffset: d, label: date.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }) })
  }

  function dateToDayOffset(dateStr) {
    if (!dateStr) return 0
    const d = new Date(dateStr)
    return Math.max(0, (d - minDate) / (1000 * 60 * 60 * 24))
  }

  function dateDurationDays(startStr, endStr) {
    if (!startStr || !endStr) return 1
    const s = new Date(startStr)
    const e = new Date(endStr)
    return Math.max(1, (e - s) / (1000 * 60 * 60 * 24))
  }

  // Build cycle groups
  const groups = runningCycles.value.map(cycle => {
    const tasks = cycleTasksMap.value[cycle.cycle_id] || []
    const activities = cycleActivitiesMap.value[cycle.cycle_id] || []

    // Cycle bar — from start_date to last task end_date
    const taskEndDates = tasks.map(t => t.calculated_end_date).filter(Boolean).sort()
    const cycleEnd = taskEndDates.length > 0 ? taskEndDates[taskEndDates.length - 1] : cycle.start_date

    const cycleBar = {
      dayOffset: dateToDayOffset(cycle.start_date),
      durationDays: dateDurationDays(cycle.start_date, cycleEnd),
    }

    // Activity bars — this cycle's own activities, same violet bar
    // style used on the per-cycle Gantt view.
    const activityBars = [...activities]
      .sort((a, b) => new Date(a.calculated_start_date) - new Date(b.calculated_start_date))
      .map(act => ({
        id: act.cycle_activity_id,
        name: act.activity_name,
        dayOffset: dateToDayOffset(act.calculated_start_date),
        durationDays: dateDurationDays(act.calculated_start_date, act.calculated_end_date),
        startDate: act.calculated_start_date,
        endDate: act.calculated_end_date,
      }))

    // Task bars — sort by start date. Completed/skipped tasks are
    // never "overdue" regardless of their end date — that status is
    // exclusively about tasks still actually open past their date.
    const taskBars = [...tasks]
      .sort((a, b) => new Date(a.calculated_start_date) - new Date(b.calculated_start_date))
      .map(task => {
        const isOverdue = task.status !== 'completed' && task.status !== 'skipped'
          && new Date(task.calculated_end_date) < today
        const isToday = task.calculated_start_date === todayStr
        return {
          id: task.cycle_task_id,
          name: task.task_name,
          dayOffset: dateToDayOffset(task.calculated_start_date),
          durationDays: dateDurationDays(task.calculated_start_date, task.calculated_end_date),
          status: task.status,
          isOverdue,
          isToday,
          isMandatory: task.is_mandatory,
          startDate: task.calculated_start_date,
          endDate: task.calculated_end_date,
        }
      })

    // Progress — completed AND skipped both count as "done" for a
    // cycle's progress, matching the per-cycle detail page's own
    // definition (a cycle finishes once every mandatory task is
    // completed or skipped).
    const done = tasks.filter(t => t.status === 'completed' || t.status === 'skipped').length
    const progress = tasks.length > 0 ? Math.round((done / tasks.length) * 100) : 0

    return {
      cycleId: cycle.cycle_id,
      cycleName: cycle.cycle_name,
      startDate: cycle.start_date,
      cycleBar,
      activityBars,
      taskBars,
      progress,
      taskCount: tasks.length,
    }
  })

  return { groups, ticks, todayOffsetDays, totalDays, pxPerDay: GANTT_PX_PER_DAY, totalWidth: totalDays * GANTT_PX_PER_DAY }
})

// Auto-scroll the shared timeline so "today" starts near the left
// edge instead of wherever the combined date range happens to begin
// — without this, a cycle whose dates sit far from the earliest
// cycle's start can end up scrolled completely out of view, looking
// like its bars never rendered at all.
function scrollGanttToToday() {
  if (!ganttScrollEl.value || !ganttData.value) return
  const targetLeft = Math.max(0, ganttData.value.todayOffsetDays * ganttData.value.pxPerDay - 80)
  ganttScrollEl.value.scrollLeft = targetLeft
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })
}

function taskBarClass(bar) {
  if (bar.status === 'completed') return 'tb-completed'
  if (bar.status === 'skipped') return 'tb-skipped'
  if (bar.isOverdue) return 'tb-overdue'
  if (bar.status === 'in_progress') return 'tb-in-progress'
  if (bar.isMandatory) return 'tb-mandatory'
  return 'tb-pending'
}

onMounted(async () => {
  await loadDashboard()
  await nextTick()
  scrollGanttToToday()
  if (onboardingStore.hasCompleted('sidebar')) {
    onboardingStore.maybeAutoStart('dashboard')
  }
})
</script>

<template>
  <AppLayout>
    <template #topbar>
      <span class="topbar-title">Dashboard</span>
      <span class="topbar-date">{{ new Date().toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) }}</span>
      <div class="topbar-actions">
        <SmartSearch
          context="dashboard"
          :default-scopes="['all']"
          placeholder="Search dashboard items..."
        />
        <button type="button" class="page-help-btn" title="Show tips for this page" @click="onboardingStore.startTour('dashboard')">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        </button>
        <BaseButton variant="primary" size="sm" @click="router.push({ name: 'cycle-create' })">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          New Cycle
        </BaseButton>
      </div>
    </template>

    <div class="dashboard">

      <div v-if="loading" class="loading-msg">Loading dashboard...</div>
      <div v-else-if="error" class="error-banner">{{ error }}</div>

      <template v-else>

        <!-- STAT CARDS -->
        <div class="stats-row" data-tour="dash-stats">
          <div class="stat-card">
            <div class="stat-icon" style="background:#EDE9FE;">
              <svg viewBox="0 0 24 24" fill="none" stroke="#7C3AED" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
              </svg>
            </div>
            <div>
              <div class="stat-value">{{ runningCycles.length }}</div>
              <div class="stat-label">Running cycles</div>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon" style="background:#FEF2F2;">
              <svg viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
            </div>
            <div>
              <div class="stat-value">{{ overdueTasksList.length }}</div>
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
              <div class="stat-value">{{ upcomingTasks.length }}</div>
              <div class="stat-label">Due in 14 days</div>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon" style="background:#EFF6FF;">
              <svg viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
            </div>
            <div>
              <div class="stat-value">{{ cycles.length }}</div>
              <div class="stat-label">Total cycles</div>
            </div>
          </div>
        </div>

        <!-- EMPTY STATE -->
        <div v-if="cycles.length === 0" class="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
          </svg>
          <div class="empty-title">No cycles yet</div>
          <div class="empty-desc">Create a template first, then start a cycle from it.</div>
          <div style="display:flex; gap:10px;">
            <BaseButton variant="secondary" size="sm" @click="router.push({ name: 'template-create' })">Create template</BaseButton>
            <BaseButton variant="primary" size="sm" @click="router.push({ name: 'cycle-create' })">Start a cycle</BaseButton>
          </div>
        </div>

        <template v-else>

          <!-- OVERDUE ALERT -->
          <div v-if="overdueTasksList.length > 0" class="alert-box" data-tour="dash-alert">
            <svg viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <div>
              <div class="alert-title">{{ overdueTasksList.length }} overdue task{{ overdueTasksList.length > 1 ? 's' : '' }} across your running cycles</div>
              <div class="alert-desc">
                <span v-for="(task, i) in overdueTasksList.slice(0, 3)" :key="task.cycle_task_id">
                  {{ task.task_name }} ({{ task.cycleName }}){{ i < Math.min(overdueTasksList.length, 3) - 1 ? ', ' : '' }}
                </span>
                <span v-if="overdueTasksList.length > 3"> and {{ overdueTasksList.length - 3 }} more.</span>
              </div>
            </div>
          </div>

          <!-- GANTT CHART -->
          <div v-if="ganttData" class="gantt-section" data-tour="dash-cycles">
            <div class="section-header">
              <div class="section-title">Running cycles timeline · activities &amp; tasks</div>
              <div class="gantt-legend">
                <span class="gl-item"><span class="gl-dot" style="background:#7C3AED;opacity:0.4;"></span>Cycle span</span>
                <span class="gl-item"><span class="gl-dot" style="background:#7C3AED;"></span>Activity</span>
                <span class="gl-item"><span class="gl-dot" style="background:#CBD5E1;"></span>Pending</span>
                <span class="gl-item"><span class="gl-dot" style="background:#F59E0B;"></span>In progress</span>
                <span class="gl-item"><span class="gl-dot" style="background:#EF4444;"></span>Overdue</span>
                <span class="gl-item"><span class="gl-dot" style="background:#22C55E;"></span>Completed</span>
                <span class="gl-item"><span class="gl-dot" style="background:#94A3B8;"></span>Skipped</span>
              </div>
            </div>

            <div class="gantt-card">
              <div class="gantt-scroll-row" ref="ganttScrollEl">

                <!-- STICKY SIDEBAR: every row's label, top to bottom -->
                <div class="gantt-sidebar">
                  <div class="gantt-side-cell" style="height: 28px;"></div>
                  <template v-for="group in ganttData.groups" :key="'side-' + group.cycleId">
                    <div
                      class="gantt-side-cell gantt-cycle-label"
                      style="height: 34px;"
                      @click="router.push({ name: 'cycle-detail', params: { id: group.cycleId } })"
                    >
                      <span class="gantt-cycle-name">{{ group.cycleName }}</span>
                      <span class="gantt-cycle-progress">{{ group.progress }}%</span>
                    </div>
                    <div
                      v-for="bar in group.activityBars"
                      :key="'act-' + bar.id"
                      class="gantt-side-cell gantt-activity-label"
                      style="height: 24px;"
                      :title="bar.name"
                      @click="router.push({ name: 'cycle-detail', params: { id: group.cycleId } })"
                    >{{ bar.name }}</div>
                    <div
                      v-for="bar in group.taskBars"
                      :key="bar.id"
                      class="gantt-side-cell gantt-task-label"
                      style="height: 28px;"
                      :title="bar.name"
                      @click="router.push({ name: 'cycle-detail', params: { id: group.cycleId } })"
                    >{{ bar.name }}</div>
                    <div class="gantt-side-cell" style="height: 13px;"></div>
                  </template>
                </div>

                <!-- CONTENT: ticks + bars, same row heights as the sidebar -->
                <div class="gantt-content" :style="{ width: ganttData.totalWidth + 'px' }">
                  <div class="gantt-tick-row" style="height: 28px;">
                    <div v-for="tick in ganttData.ticks" :key="tick.label" class="gantt-tick" :style="{ left: (tick.dayOffset * ganttData.pxPerDay) + 'px' }">
                      <div class="gantt-tick-line"></div>
                      <span class="gantt-tick-label">{{ tick.label }}</span>
                    </div>
                    <!-- TODAY MARKER -->
                    <div class="gantt-today" :style="{ left: (ganttData.todayOffsetDays * ganttData.pxPerDay) + 'px' }">
                      <div class="gantt-today-line"></div>
                      <span class="gantt-today-label">Today</span>
                    </div>
                  </div>

                  <template v-for="group in ganttData.groups" :key="'content-' + group.cycleId">
                    <div
                      class="gantt-content-cell"
                      style="height: 34px;"
                      @click="router.push({ name: 'cycle-detail', params: { id: group.cycleId } })"
                    >
                      <div
                        class="gantt-bar gantt-bar-cycle"
                        :style="{ left: (group.cycleBar.dayOffset * ganttData.pxPerDay) + 'px', width: Math.max(group.cycleBar.durationDays * ganttData.pxPerDay, 6) + 'px' }"
                      ></div>
                    </div>
                    <div
                      v-for="bar in group.activityBars"
                      :key="'act-content-' + bar.id"
                      class="gantt-content-cell"
                      style="height: 24px;"
                      @click="router.push({ name: 'cycle-detail', params: { id: group.cycleId } })"
                    >
                      <div
                        class="gantt-bar gantt-bar-activity"
                        :style="{ left: (bar.dayOffset * ganttData.pxPerDay) + 'px', width: Math.max(bar.durationDays * ganttData.pxPerDay, 6) + 'px' }"
                        :title="`${bar.name}: ${formatDate(bar.startDate)} → ${formatDate(bar.endDate)}`"
                      ></div>
                    </div>
                    <div
                      v-for="bar in group.taskBars"
                      :key="bar.id"
                      class="gantt-content-cell"
                      style="height: 28px;"
                      @click="router.push({ name: 'cycle-detail', params: { id: group.cycleId } })"
                    >
                      <div
                        class="gantt-bar gantt-bar-task"
                        :class="taskBarClass(bar)"
                        :style="{ left: (bar.dayOffset * ganttData.pxPerDay) + 'px', width: Math.max(bar.durationDays * ganttData.pxPerDay, 6) + 'px' }"
                        :title="`${bar.name}: ${formatDate(bar.startDate)} → ${formatDate(bar.endDate)}`"
                      ></div>
                    </div>
                    <div class="gantt-content-cell gantt-group-divider-cell" style="height: 13px;"></div>
                  </template>
                </div>

              </div>
            </div>
          </div>

          <!-- TWO COLUMN: Upcoming + Running cycles list -->
          <div class="two-col" data-tour="dash-upcoming">

            <!-- UPCOMING TASKS -->
            <div class="col-upcoming">
              <div class="section-title">Coming up soon <span class="section-count">{{ upcomingTasks.length }}</span></div>
              <div v-if="upcomingTasks.length === 0" class="empty-section">No tasks due in the next 14 days.</div>
              <div v-else class="upcoming-list">
                <div v-for="task in upcomingTasks.slice(0, 8)" :key="task.cycle_task_id" class="upcoming-row" @click="router.push({ name: 'cycle-detail', params: { id: task.cycleId } })">
                  <div class="upcoming-date-badge" :class="task.isToday ? 'badge-today' : ''">
                    <div class="upcoming-date-day">{{ new Date(task.calculated_start_date).toLocaleDateString('en-AU', { day: 'numeric' }) }}</div>
                    <div class="upcoming-date-month">{{ new Date(task.calculated_start_date).toLocaleDateString('en-AU', { month: 'short' }) }}</div>
                  </div>
                  <div class="upcoming-info">
                    <div class="upcoming-task-name">{{ task.task_name }}</div>
                    <div class="upcoming-cycle-name">{{ task.cycleName }}</div>
                  </div>
                  <span v-if="task.isMandatory" class="upcoming-mandatory">M</span>
                </div>
                <div v-if="upcomingTasks.length > 8" class="upcoming-more" @click="router.push({ name: 'cycles' })">
                  +{{ upcomingTasks.length - 8 }} more — view all cycles →
                </div>
              </div>
            </div>

            <!-- RUNNING CYCLES LIST -->
            <div class="col-cycles">
              <div class="section-title">Running cycles <span class="section-count">{{ runningCycles.length }}</span></div>
              <div v-if="runningCycles.length === 0" class="empty-section">No running cycles.</div>
              <div v-else class="cycle-cards">
                <div v-for="cycle in runningCycles" :key="cycle.cycle_id" class="cycle-card" @click="router.push({ name: 'cycle-detail', params: { id: cycle.cycle_id } })">
                  <div class="cc-top">
                    <div class="cc-name">{{ cycle.cycle_name }}</div>
                    <span class="badge badge-running">● Running</span>
                  </div>
                  <div class="cc-progress-row">
                    <div class="progress-bar-bg">
                      <div class="progress-bar-fill" :style="{ width: (cycleTasksMap[cycle.cycle_id] ? Math.round((cycleTasksMap[cycle.cycle_id].filter(t => t.status === 'completed').length / Math.max(cycleTasksMap[cycle.cycle_id].length, 1)) * 100) : 0) + '%' }"></div>
                    </div>
                    <span class="cc-pct">{{ cycleTasksMap[cycle.cycle_id] ? Math.round((cycleTasksMap[cycle.cycle_id].filter(t => t.status === 'completed').length / Math.max(cycleTasksMap[cycle.cycle_id].length, 1)) * 100) : 0 }}%</span>
                  </div>
                  <div class="cc-meta">Started {{ formatDate(cycle.start_date) }}</div>
                </div>
              </div>
            </div>

          </div>

        </template>
      </template>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ── TOPBAR ── */
.topbar-title { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); }
.topbar-date { font-size: var(--font-label); color: var(--text-secondary); }
.topbar-actions { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.page-help-btn { width: 34px; height: 34px; border-radius: var(--radius-md); border: 1px solid var(--border-light); background: var(--white); display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-muted); }
.page-help-btn:hover { background: var(--violet-bg); color: var(--violet); }

/* ── PAGE ── */
.dashboard { display: flex; flex-direction: column; gap: 24px; }
.loading-msg { font-size: var(--font-body); color: var(--text-muted); padding: 40px 0; }
.error-banner { background: var(--danger-bg); border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 12px 16px; font-size: var(--font-body); color: #B91C1C; }

/* ── STAT CARDS ── */
.stats-row { display: flex; gap: 14px; }
.stat-card { flex: 1; background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 16px 18px; display: flex; align-items: center; gap: 14px; }
.stat-icon { width: 42px; height: 42px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.stat-icon svg { width: 20px; height: 20px; }
.stat-value { font-size: var(--font-display); font-weight: 600; color: var(--text-primary); line-height: 1; margin-bottom: 2px; }
.stat-label { font-size: var(--font-label); color: var(--text-secondary); }

/* ── EMPTY ── */
.empty-state { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 60px 0; }
.empty-state svg { width: 40px; height: 40px; stroke: var(--border-light); }
.empty-title { font-size: var(--font-title); font-weight: 600; color: var(--text-primary); }
.empty-desc { font-size: var(--font-body); color: var(--text-muted); }
.empty-section { font-size: var(--font-body); color: var(--text-muted); padding: 16px 0; }

/* ── ALERT ── */
.alert-box { background: var(--danger-bg); border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 12px 16px; display: flex; gap: 10px; align-items: flex-start; }
.alert-box svg { width: 16px; height: 16px; flex-shrink: 0; margin-top: 2px; }
.alert-title { font-size: var(--font-body); font-weight: 600; color: #B91C1C; margin-bottom: 3px; }
.alert-desc { font-size: var(--font-label); color: #991B1B; }

/* ── SECTION HEADERS ── */
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.section-title { font-size: var(--font-title); font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 8px; }
.section-count { font-size: var(--font-upper); font-weight: 600; background: var(--violet-bg); color: var(--violet); padding: 2px 10px; border-radius: 20px; }

/* ── GANTT ── */
.gantt-section { display: flex; flex-direction: column; gap: 12px; }
.gantt-legend { display: flex; gap: 14px; flex-wrap: wrap; }
.gl-item { display: flex; align-items: center; gap: 5px; font-size: var(--font-label); color: var(--text-secondary); }
.gl-dot { width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }

.gantt-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); overflow: hidden; }

/* This is the actual scrolling element. Sidebar and content MUST
   stay direct children of THIS, never nested in a per-row wrapper —
   position:sticky reliably fails in this app's target browsers
   whenever the sticky element is wrapped in any intermediate
   element before reaching the scrolling ancestor (confirmed
   empirically — see GanttChart.vue for the full note). */
.gantt-scroll-row { display: flex; align-items: flex-start; padding: 16px 20px; overflow-x: auto; }

.gantt-sidebar { position: sticky; left: 0; z-index: 3; flex-shrink: 0; width: 160px; background: var(--white); }
.gantt-side-cell { display: flex; align-items: center; box-sizing: border-box; }
.gantt-cycle-label { justify-content: space-between; gap: 8px; padding: 0 12px 0 0; cursor: pointer; }
.gantt-cycle-name { font-size: var(--font-label); font-weight: 600; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 110px; }
.gantt-cycle-progress { font-size: var(--font-hint); font-weight: 600; color: var(--violet); flex-shrink: 0; }
.gantt-task-label { font-size: var(--font-hint); color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding: 0 12px; cursor: pointer; }
.gantt-activity-label { font-size: var(--font-hint); font-weight: 500; color: var(--violet); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding: 0 12px; cursor: pointer; }

.gantt-content { flex-shrink: 0; position: relative; }
.gantt-content-cell { position: relative; box-sizing: border-box; cursor: pointer; }
.gantt-content-cell:hover { background: rgba(124, 58, 237, 0.03); }
.gantt-group-divider-cell { cursor: default; }
.gantt-group-divider-cell::after { content: ''; position: absolute; left: 0; right: 0; top: 6px; height: 1px; background: var(--border-light); }

.gantt-tick-row { position: relative; }

/* TICK MARKS */
.gantt-tick { position: absolute; top: 0; display: flex; flex-direction: column; align-items: center; transform: translateX(-50%); }
.gantt-tick-line { width: 1px; height: 8px; background: var(--border-light); }
.gantt-tick-label { font-size: var(--font-hint); color: var(--text-muted); white-space: nowrap; margin-top: 2px; }

/* TODAY MARKER */
.gantt-today { position: absolute; top: 0; bottom: 0; transform: translateX(-50%); display: flex; flex-direction: column; align-items: center; z-index: 2; }
.gantt-today-line { width: 2px; height: 100%; background: var(--danger); opacity: 0.7; }
.gantt-today-label { font-size: var(--font-hint); font-weight: 600; color: var(--danger); white-space: nowrap; position: absolute; top: -18px; }

/* BARS */
.gantt-bar { position: absolute; top: 50%; transform: translateY(-50%); border-radius: 4px; transition: opacity 0.15s; }
.gantt-bar:hover { opacity: 0.85; }

.gantt-bar-cycle { height: 20px; background: var(--violet); opacity: 0.15; border-radius: 4px; }
.gantt-bar-activity { height: 16px; background: linear-gradient(90deg, #7C3AED 0%, #A78BFA 100%); box-shadow: 0 1px 2px rgba(0,0,0,0.12); }
.gantt-bar-task { height: 16px; }

.tb-pending { background: #CBD5E1; }
.tb-in-progress { background: #F59E0B; }
.tb-completed { background: #22C55E; }
.tb-overdue { background: #EF4444; }
.tb-skipped { background: #94A3B8; }
.tb-mandatory { background: #7C3AED; }

/* ── TWO COL ── */
.two-col { display: flex; gap: 20px; align-items: flex-start; }
.col-upcoming { flex: 1; min-width: 0; }
.col-cycles { width: 340px; flex-shrink: 0; }

/* ── UPCOMING LIST ── */
.upcoming-list { display: flex; flex-direction: column; gap: 6px; }
.upcoming-row { display: flex; align-items: center; gap: 12px; padding: 10px 14px; background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-md); cursor: pointer; transition: border-color var(--transition-fast); }
.upcoming-row:hover { border-color: #C4B5FD; }

.upcoming-date-badge { width: 44px; flex-shrink: 0; text-align: center; background: var(--violet-bg); border-radius: var(--radius-md); padding: 5px 4px; }
.upcoming-date-badge.badge-today { background: var(--violet); }
.upcoming-date-day { font-size: var(--font-title); font-weight: 700; color: var(--violet); line-height: 1; }
.badge-today .upcoming-date-day { color: white; }
.upcoming-date-month { font-size: var(--font-hint); color: var(--violet); text-transform: uppercase; letter-spacing: 0.04em; }
.badge-today .upcoming-date-month { color: white; }
.upcoming-info { flex: 1; min-width: 0; }
.upcoming-task-name { font-size: var(--font-body); font-weight: 500; color: var(--text-primary); margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.upcoming-cycle-name { font-size: var(--font-label); color: var(--text-secondary); }
.upcoming-mandatory { font-size: var(--font-hint); font-weight: 700; color: var(--danger); background: var(--danger-bg); padding: 2px 6px; border-radius: 3px; flex-shrink: 0; }
.upcoming-more { font-size: var(--font-label); color: var(--violet); cursor: pointer; padding: 10px 14px; text-align: center; }

/* ── RUNNING CYCLES LIST ── */
.cycle-cards { display: flex; flex-direction: column; gap: 10px; }
.cycle-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 14px 16px; cursor: pointer; transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
.cycle-card:hover { border-color: #C4B5FD; box-shadow: var(--shadow-sm); }
.cc-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; gap: 10px; }
.cc-name { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); }
.badge { font-size: var(--font-badge); font-weight: 500; padding: 4px 11px; border-radius: 20px; flex-shrink: 0; }
.badge-running { background: var(--success-bg); color: #15803D; }
.cc-progress-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.progress-bar-bg { flex: 1; height: 5px; border-radius: 3px; background: var(--border-light); }
.progress-bar-fill { height: 5px; border-radius: 3px; background: var(--violet); }
.cc-pct { font-size: var(--font-label); font-weight: 500; color: var(--text-primary); flex-shrink: 0; width: 36px; text-align: right; }
.cc-meta { font-size: var(--font-label); color: var(--text-secondary); }
</style>
