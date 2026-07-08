<!-- /frontend/src/views/CycleDetailView.vue -->

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import { useToastStore } from '@/stores/toast'
import { getCycle, getCycleTasks, getCycleActivities } from '@/api/cycles'
import api from '@/api/axios'

const route = useRoute()
const router = useRouter()
const cycleId = route.params.id
const toast = useToastStore()

const shutdownModal = ref(false)
const shutdownLoading = ref(false)
const delayModal = ref({ open: false, taskId: null, days: '' })
const delayLoading = ref(false)

const cycle = ref(null)
const tasks = ref([])
const activities = ref([])
const loading = ref(true)
const error = ref('')

const today = new Date()
today.setHours(0, 0, 0, 0)

function parseDate(dateStr) {
  if (!dateStr) return null
  const d = new Date(dateStr)
  d.setHours(0, 0, 0, 0)
  return d
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })
}

function isToday(dateStr) {
  const d = parseDate(dateStr)
  return d && d.getTime() === today.getTime()
}

function isOverdue(task) {
  const end = parseDate(task.calculated_end_date)
  return end && end < today && task.status !== 'completed' && task.status !== 'skipped'
}

function isDueToday(task) {
  return isToday(task.calculated_start_date) && task.status !== 'completed'
}

function isUpcoming(task) {
  const start = parseDate(task.calculated_start_date)
  return start && start > today && task.status !== 'completed'
}

const overdueTasks = computed(() => tasks.value.filter(isOverdue))
const todayTasks = computed(() => tasks.value.filter(t => !isOverdue(t) && isDueToday(t)))
const upcomingTasks = computed(() => tasks.value.filter(t => !isOverdue(t) && !isDueToday(t) && isUpcoming(t)))
const completedTasks = computed(() => tasks.value.filter(t => t.status === 'completed'))

const progress = computed(() => {
  if (tasks.value.length === 0) return 0
  return Math.round((completedTasks.value.length / tasks.value.length) * 100)
})

const endDate = computed(() => {
  if (tasks.value.length === 0) return null
  const dates = tasks.value.map(t => t.calculated_end_date).filter(Boolean)
  if (dates.length === 0) return null
  return dates.sort().reverse()[0]
})

async function loadCycle() {
  loading.value = true
  error.value = ''
  try {
    const [cycleRes, tasksRes, activitiesRes] = await Promise.all([
      getCycle(cycleId),
      getCycleTasks(cycleId),
      getCycleActivities(cycleId),
    ])
    cycle.value = cycleRes.data
    tasks.value = Array.isArray(tasksRes.data) ? tasksRes.data : (tasksRes.data.results || [])
    activities.value = Array.isArray(activitiesRes.data) ? activitiesRes.data : (activitiesRes.data.results || [])
  } catch {
    error.value = 'Failed to load cycle. Please try again.'
  } finally {
    loading.value = false
  }
}

async function updateTaskStatus(taskId, newStatus) {
  try {
    await api.patch(`/cycle-tasks/${taskId}/`, { status: newStatus })
    await loadCycle()
    toast.success('Task status updated.')
  } catch {
    toast.error('Failed to update task status.')
  }
}

function openDelayModal(taskId) {
  delayModal.value = { open: true, taskId, days: '' }
}

async function confirmRecordDelay() {
  const n = parseInt(delayModal.value.days, 10)
  if (isNaN(n) || n < 0) {
    toast.error('Please enter a valid number of days.')
    return
  }
  delayLoading.value = true
  try {
    const { data } = await api.post(`/cycle-tasks/${delayModal.value.taskId}/record_delay/`, { delay_days: n })
    delayModal.value.open = false
    await loadCycle()
    if (data.schedule_warnings?.fixed_date_conflicts?.length) {
      toast.error(`Delay recorded, but conflicts with a fixed date: ${data.schedule_warnings.fixed_date_conflicts.join(', ')}`)
    } else {
      toast.success('Delay recorded and dependent tasks recalculated.')
    }
  } catch {
    toast.error('Failed to record delay.')
  } finally {
    delayLoading.value = false
  }
}

async function confirmShutdownCycle() {
  shutdownLoading.value = true
  try {
    await api.post(`/cycles/${cycleId}/shut_down/`)
    shutdownModal.value = false
    await loadCycle()
    toast.success('Cycle shut down.')
  } catch {
    toast.error('Failed to shut down cycle.')
  } finally {
    shutdownLoading.value = false
  }
}

function statusClass(status) {
  if (status === 'completed') return 'status-completed'
  if (status === 'in_progress') return 'status-in-progress'
  if (status === 'delayed') return 'status-delayed'
  if (status === 'overdue') return 'status-overdue'
  return 'status-pending'
}

function statusLabel(status) {
  const map = { pending: 'Pending', in_progress: 'In Progress', completed: 'Completed', overdue: 'Overdue', delayed: 'Delayed' }
  return map[status] || status
}

onMounted(loadCycle)
</script>

<template>
  <AppLayout>
    <template #topbar>
      <div class="breadcrumb">
        <span class="breadcrumb-link" @click="router.push({ name: 'cycles' })">Cycles</span>
        <span class="breadcrumb-sep">›</span>
        <span class="breadcrumb-current">{{ cycle?.cycle_name || 'Loading...' }}</span>
      </div>
      <div v-if="cycle" style="margin-left: auto; display: flex; gap: 10px;">
        <BaseButton variant="secondary" size="sm" @click="router.push({ name: 'cycle-create' })">Start new cycle</BaseButton>
        <BaseButton v-if="cycle.status === 'running'" variant="danger" size="sm" @click="shutdownModal = true">Shut Down Cycle</BaseButton>
      </div>
    </template>

    <div class="detail-page">
      <div v-if="loading" class="loading-msg">Loading cycle...</div>
      <div v-else-if="error" class="error-banner">{{ error }}</div>

      <template v-else-if="cycle">
        <div class="cycle-header">
          <div class="cycle-header-top">
            <div>
              <div class="cycle-title">{{ cycle.cycle_name }}</div>
              <div class="cycle-subtitle">Started {{ formatDate(cycle.start_date) }}</div>
            </div>
            <div class="cycle-badges">
              <span class="badge" :class="cycle.status === 'running' ? 'badge-running' : 'badge-shutdown'">
                {{ cycle.status === 'running' ? '● Running' : cycle.status === 'shut_down' ? 'Shut down' : 'Completed' }}
              </span>
            </div>
          </div>
          <div class="cycle-progress-row">
            <div class="progress-bar-bg"><div class="progress-bar-fill" :style="{ width: progress + '%' }"></div></div>
            <span class="progress-label">{{ progress }}% · {{ completedTasks.length }} of {{ tasks.length }} tasks done</span>
          </div>
          <div class="cycle-meta-row">
            <div class="meta-item"><div class="meta-label">Start</div><div class="meta-value">{{ formatDate(cycle.start_date) }}</div></div>
            <div class="meta-item"><div class="meta-label">End</div><div class="meta-value">{{ formatDate(endDate) }}</div></div>
            <div class="meta-item"><div class="meta-label">Tasks</div><div class="meta-value">{{ tasks.length }}</div></div>
            <div class="meta-item"><div class="meta-label">Activities</div><div class="meta-value">{{ activities.length }}</div></div>
            <div class="meta-item"><div class="meta-label">Overdue</div><div class="meta-value" :class="overdueTasks.length > 0 ? 'danger' : ''">{{ overdueTasks.length }}</div></div>
          </div>
        </div>

        <div v-if="overdueTasks.length > 0" class="alert-box">
          <svg viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <div>
            <div class="alert-title">{{ overdueTasks.length }} overdue task{{ overdueTasks.length > 1 ? 's' : '' }} require attention</div>
            <div class="alert-desc">Update the status or record a delay for the tasks below.</div>
          </div>
        </div>

        <div class="two-col">
          <div class="col-main">

            <div v-if="activities.length > 0">
              <div class="timeline-label violet">Active Activities</div>
              <div v-for="act in activities" :key="act.cycle_activity_id" class="activity-card">
                <div class="act-row">
                  <div class="act-name">{{ act.activity_name }}</div>
                  <span class="tc-status status-activity">Activity</span>
                </div>
                <div class="act-dates">{{ formatDate(act.calculated_start_date) }} → {{ formatDate(act.calculated_end_date) }}</div>
                <div v-if="act.note_text" class="act-note">{{ act.note_text }}</div>
              </div>
            </div>

            <div v-if="overdueTasks.length > 0">
              <div class="timeline-label danger">⚠ Overdue</div>
              <div v-for="task in overdueTasks" :key="task.cycle_task_id" class="task-card overdue-card">
                <div class="tc-row">
                  <div class="tc-left">
                    <div class="tc-name">{{ task.task_name }}<span v-if="task.is_mandatory" class="tc-mandatory">MANDATORY</span></div>
                    <div class="tc-dates">{{ formatDate(task.calculated_start_date) }} → {{ formatDate(task.calculated_end_date) }}</div>
                    <div v-if="task.note_text" class="tc-note">{{ task.note_text }}</div>
                  </div>
                  <div class="tc-right">
                    <span class="tc-status status-overdue">Overdue</span>
                    <div class="tc-actions">
                      <button class="action-btn action-complete" @click="updateTaskStatus(task.cycle_task_id, 'completed')">Mark complete</button>
                      <button class="action-btn action-delay" @click="openDelayModal(task.cycle_task_id)">Record delay</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="todayTasks.length > 0">
              <div class="timeline-label">Today</div>
              <div v-for="task in todayTasks" :key="task.cycle_task_id" class="task-card">
                <div class="tc-row">
                  <div class="tc-left">
                    <div class="tc-name">{{ task.task_name }}<span v-if="task.is_mandatory" class="tc-mandatory">MANDATORY</span><span v-if="task.is_fixed_date" class="tc-fixed">FIXED DATE</span></div>
                    <div class="tc-dates">Due {{ formatDate(task.calculated_start_date) }}</div>
                  </div>
                  <div class="tc-right">
                    <span class="tc-status" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span>
                    <BaseSelect
                      class="status-select"
                      :model-value="task.status"
                      @update:model-value="(v) => updateTaskStatus(task.cycle_task_id, v)"
                    >
                      <option value="pending">Pending</option>
                      <option value="in_progress">In Progress</option>
                      <option value="completed">Completed</option>
                      <option value="delayed">Delayed</option>
                    </BaseSelect>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="upcomingTasks.length > 0">
              <div class="timeline-label">Upcoming</div>
              <div v-for="task in upcomingTasks" :key="task.cycle_task_id" class="task-card">
                <div class="tc-row">
                  <div class="tc-left">
                    <div class="tc-name">{{ task.task_name }}<span v-if="task.is_mandatory" class="tc-mandatory">MANDATORY</span><span v-if="task.is_fixed_date" class="tc-fixed">FIXED DATE</span></div>
                    <div class="tc-dates">{{ formatDate(task.calculated_start_date) }} → {{ formatDate(task.calculated_end_date) }}</div>
                  </div>
                  <div class="tc-right">
                    <span class="tc-status status-pending">Pending</span>
                    <button class="action-btn action-complete" @click="updateTaskStatus(task.cycle_task_id, 'completed')">Mark complete</button>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="completedTasks.length > 0">
              <div class="timeline-label">Completed</div>
              <div v-for="task in completedTasks" :key="task.cycle_task_id" class="task-card completed-card">
                <div class="tc-row">
                  <div class="tc-left">
                    <div class="tc-name">{{ task.task_name }}</div>
                    <div class="tc-dates">{{ formatDate(task.calculated_start_date) }}</div>
                  </div>
                  <div class="tc-right">
                    <span class="tc-status status-completed">Completed</span>
                    <button class="action-btn action-undo" @click="updateTaskStatus(task.cycle_task_id, 'pending')">Undo</button>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="tasks.length === 0 && activities.length === 0" class="empty-section">No tasks or activities in this cycle yet.</div>
          </div>

          <div class="col-side">
            <div class="side-card">
              <div class="side-card-title">Status summary</div>
              <div class="legend-item"><div class="legend-dot" style="background:var(--success);"></div><span class="legend-label">Completed</span><span class="legend-count">{{ completedTasks.length }}</span></div>
              <div class="legend-item"><div class="legend-dot" style="background:var(--warning);"></div><span class="legend-label">In progress</span><span class="legend-count">{{ tasks.filter(t => t.status === 'in_progress').length }}</span></div>
              <div class="legend-item"><div class="legend-dot" style="background:var(--danger);"></div><span class="legend-label">Overdue</span><span class="legend-count">{{ overdueTasks.length }}</span></div>
              <div class="legend-item"><div class="legend-dot" style="background:#F59E0B;"></div><span class="legend-label">Delayed</span><span class="legend-count">{{ tasks.filter(t => t.status === 'delayed').length }}</span></div>
              <div class="legend-item"><div class="legend-dot" style="background:var(--border);"></div><span class="legend-label">Pending</span><span class="legend-count">{{ tasks.filter(t => t.status === 'pending').length }}</span></div>
            </div>
            <div class="side-card">
              <div class="side-card-title">Cycle info</div>
              <div class="info-row"><span class="info-label">Status</span><span class="info-value">{{ cycle.status }}</span></div>
              <div class="info-row"><span class="info-label">Start date</span><span class="info-value">{{ formatDate(cycle.start_date) }}</span></div>
              <div class="info-row"><span class="info-label">End date</span><span class="info-value">{{ formatDate(endDate) }}</span></div>
              <div class="info-row"><span class="info-label">Progress</span><span class="info-value">{{ progress }}%</span></div>
            </div>
          </div>
        </div>
      </template>
    </div>
    <!-- SHUT DOWN CONFIRM MODAL -->
    <BaseModal
      v-model="shutdownModal"
      title="Shut down cycle?"
      confirm-label="Shut down"
      confirm-variant="danger"
      :loading="shutdownLoading"
      @confirm="confirmShutdownCycle"
    >
      <p>Are you sure you want to shut down this cycle? This cannot be undone.</p>
    </BaseModal>

    <!-- RECORD DELAY MODAL -->
    <BaseModal
      v-model="delayModal.open"
      title="Record delay"
      confirm-label="Save delay"
      :loading="delayLoading"
      @confirm="confirmRecordDelay"
    >
      <BaseInput
        v-model="delayModal.days"
        type="number"
        label="Delay (days)"
        placeholder="e.g. 3"
        hint="Downstream dependent tasks will be recalculated automatically."
      />
    </BaseModal>

  </AppLayout>
</template>

<style scoped>
/* ── BREADCRUMB ── */
.breadcrumb { display: flex; align-items: center; gap: 6px; font-size: var(--font-label); }
.breadcrumb-link { color: var(--text-muted); cursor: pointer; }
.breadcrumb-link:hover { color: var(--violet); }
.breadcrumb-sep { color: var(--text-muted); }
.breadcrumb-current { color: var(--text-primary); font-weight: 500; }

/* ── PAGE ── */
.detail-page { display: flex; flex-direction: column; gap: 20px; }
.loading-msg { font-size: var(--font-body); color: var(--text-muted); padding: 40px 0; }
.error-banner { background: var(--danger-bg); border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 12px 16px; font-size: var(--font-body); color: #B91C1C; }

/* ── CYCLE HEADER ── */
.cycle-header { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 18px 22px; }
.cycle-header-top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 14px; gap: 16px; }
.cycle-title { font-size: var(--font-heading); font-weight: 600; color: var(--text-primary); letter-spacing: -0.3px; margin-bottom: 3px; }
.cycle-subtitle { font-size: var(--font-label); color: var(--text-secondary); }
.cycle-badges { display: flex; gap: 7px; flex-shrink: 0; }
.badge { font-size: var(--font-badge); font-weight: 500; padding: 4px 11px; border-radius: 20px; }
.badge-running { background: var(--success-bg); color: #15803D; }
.badge-shutdown { background: var(--bg-page); color: var(--text-secondary); border: 1px solid var(--border-light); }

.cycle-progress-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.progress-bar-bg { flex: 1; height: 6px; border-radius: 3px; background: var(--border-light); }
.progress-bar-fill { height: 6px; border-radius: 3px; background: var(--violet); transition: width 0.3s ease; }
.progress-label { font-size: var(--font-label); font-weight: 500; color: var(--text-primary); flex-shrink: 0; }

.cycle-meta-row { display: flex; gap: 24px; padding-top: 12px; border-top: 1px solid var(--border-light); flex-wrap: wrap; }
.meta-label { font-size: var(--font-upper); font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 3px; }
.meta-value { font-size: var(--font-label); font-weight: 600; color: var(--text-primary); }
.meta-value.danger { color: var(--danger); }

/* ── ALERT ── */
.alert-box { background: var(--danger-bg); border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 12px 16px; display: flex; gap: 10px; align-items: flex-start; }
.alert-box svg { width: 16px; height: 16px; flex-shrink: 0; margin-top: 1px; }
.alert-title { font-size: var(--font-body); font-weight: 600; color: #B91C1C; margin-bottom: 2px; }
.alert-desc { font-size: var(--font-label); color: #991B1B; }

/* ── LAYOUT ── */
.two-col { display: flex; gap: 20px; align-items: flex-start; }
.col-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px; }
.col-side { width: 260px; flex-shrink: 0; display: flex; flex-direction: column; gap: 14px; position: sticky; top: 80px; }

/* ── TIMELINE LABELS ── */
.timeline-label { font-size: var(--font-upper); font-weight: 600; color: var(--text-primary); text-transform: uppercase; letter-spacing: 0.07em; padding: 8px 0 6px; }
.timeline-label.danger { color: var(--danger); }
.timeline-label.violet { color: var(--violet); }

/* ── TASK CARDS ── */
.task-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 12px 16px; margin-bottom: 6px; }
.task-card.overdue-card { border-color: #FECACA; background: #FFF8F8; }
.task-card.completed-card { opacity: 0.65; }
.tc-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.tc-left { flex: 1; min-width: 0; }
.tc-name { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); margin-bottom: 3px; display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.tc-dates { font-size: var(--font-label); color: var(--text-secondary); }
.tc-note { font-size: var(--font-label); color: var(--text-secondary); margin-top: 4px; }
.tc-right { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; flex-shrink: 0; }
.tc-mandatory { font-size: var(--font-hint); font-weight: 700; color: var(--danger); }
.tc-fixed { font-size: var(--font-hint); font-weight: 700; color: #92400E; }

/* ── STATUS BADGES ── */
.tc-status { font-size: var(--font-badge); font-weight: 500; padding: 3px 9px; border-radius: 4px; }
.status-completed { background: var(--success-bg); color: #15803D; }
.status-in-progress { background: var(--warning-bg); color: #92400E; }
.status-overdue { background: var(--danger-bg); color: #B91C1C; }
.status-delayed { background: #FEF3C7; color: #92400E; }
.status-pending { background: var(--bg-page); color: var(--text-secondary); border: 1px solid var(--border-light); }
.status-activity { background: var(--violet-bg); color: var(--violet); }

/* ── ACTIONS ── */
.tc-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.action-btn { font-size: var(--font-label); font-weight: 500; padding: 4px 10px; border: none; border-radius: 5px; cursor: pointer; font-family: var(--font-main); }
.action-complete { background: var(--success-bg); color: #15803D; }
.action-delay { background: #FEF3C7; color: #92400E; }
.action-undo { background: var(--bg-page); color: var(--text-secondary); border: 1px solid var(--border-light); }
/* Compact sizing for the inline status dropdown on task rows */
.status-select :deep(.base-select) { height: 34px; padding: 0 26px 0 10px; background: var(--white); }
.status-select :deep(.select-chevron) { right: 8px; width: 13px; height: 13px; }

/* ── ACTIVITY CARD ── */
.activity-card { background: var(--violet-bg); border: 1px solid #DDD6FE; border-radius: var(--radius-md); padding: 12px 16px; margin-bottom: 6px; }
.act-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.act-name { font-size: var(--font-body); font-weight: 600; color: var(--violet); }
.act-dates { font-size: var(--font-label); color: var(--violet-dark); }
.act-note { font-size: var(--font-label); color: var(--violet-dark); margin-top: 4px; opacity: 0.8; }
.empty-section { font-size: var(--font-body); color: var(--text-muted); padding: 24px 0; text-align: center; }

/* ── SIDE CARDS ── */
.side-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 14px 16px; }
.side-card-title { font-size: var(--font-title); font-weight: 600; color: var(--text-primary); margin-bottom: 12px; }
.legend-item { display: flex; align-items: center; gap: 8px; margin-bottom: 9px; }
.legend-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.legend-label { font-size: var(--font-body); color: var(--text-primary); flex: 1; }
.legend-count { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); }
.info-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border-light); }
.info-row:last-child { border-bottom: none; }
.info-label { font-size: var(--font-label); color: var(--text-secondary); }
.info-value { font-size: var(--font-body); font-weight: 500; color: var(--text-primary); }
</style>