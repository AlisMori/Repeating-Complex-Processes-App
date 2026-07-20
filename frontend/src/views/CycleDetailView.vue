<!-- /frontend/src/views/CycleDetailView.vue -->

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseDatePicker from '@/components/ui/BaseDatePicker.vue'
import CycleGanttChart from '@/components/CycleGanttChart.vue'
import { useToastStore } from '@/stores/toast'
import {
  getCycle, getCycleTasks, getCycleActivities,
  shutdownCycle,
  updateCycleTask, previewTaskShift, applyTaskShift,
  setTaskNote, clearTaskNote,
  updateCycleActivity, setActivityNote, clearActivityNote,
} from '@/api/cycles'
import { getTemplateTaskDetail, getTaskDependencies, getTaskTags, getActivityTags, getTags } from '@/api/templates'
import {
  getErrorMessage, isCycleFrozenError, isPrerequisitesUnresolvedError,
  isDependencyConflictError, getUnresolvedPrerequisites,
} from '@/utils/apiErrors'

const route = useRoute()
const router = useRouter()
const cycleId = route.params.id
const toast = useToastStore()

const shutdownModal = ref(false)
const shutdownLoading = ref(false)

// Overflow "⋯" menu shown per row for secondary actions (note,
// reschedule, edit dates) — only one open at a time, closes on any
// click outside it. `openMenuFor` holds a unique string key per row
// (e.g. 'task-42', 'activity-7') so each row's menu is independent.
const openMenuFor = ref(null)
function toggleMenu(key) {
  openMenuFor.value = openMenuFor.value === key ? null : key
}
function closeMenu() {
  openMenuFor.value = null
}
onMounted(() => document.addEventListener('click', closeMenu))
onUnmounted(() => document.removeEventListener('click', closeMenu))

// Shift modal replaces the old "record delay" modal — it wraps the
// real backend flow (shift_preview then shift), matching what
// dependency shifting/fixed-date locking actually allow.
const shiftModal = ref({ open: false, task: null, mode: 'delay', days: '', newDate: '', scope: 'single', overrideFixed: false, preview: null })
const shiftLoading = ref(false)
const shiftPreviewLoading = ref(false)

const taskDetailModal = ref({ open: false, task: null, templateDetail: null, loading: false })

// One shared note editor for both tasks and activities.
const noteModal = ref({ open: false, kind: null, id: null, text: '' })
const noteLoading = ref(false)

// Resize an in-flight activity's date range.
const activityEditModal = ref({ open: false, activity: null, start: '', end: '' })
const activityEditLoading = ref(false)

// A task is being marked completed but depends on tasks that aren't
// finished — ask the user to resolve each one instead of silently
// failing (see task_status_engine.find_unresolved_prerequisites).
const prereqModal = ref({ open: false, taskId: null, newStatus: null, unresolved: [], choices: {} })
const prereqLoading = ref(false)

const viewMode = ref('list') // 'list' | 'gantt'
const listGroupBy = ref('status') // 'status' | 'tag'

const cycle = ref(null)
const tasks = ref([])
const activities = ref([])
const dependencies = ref([]) // TaskDependency edges for this cycle's template
const tags = ref([])
const taskTags = ref([]) // TemplateTaskTag rows for this cycle's template
const activityTags = ref([]) // TemplateActivityTag rows for this cycle's template
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

function isOverdue(task) {
  const end = parseDate(task.calculated_end_date)
  return end && end < today && task.status !== 'completed' && task.status !== 'skipped'
}

// Mirrors task_status_engine.ALLOWED_TRANSITIONS exactly, keyed by
// the task's REAL status field — not a client-guessed "is this past
// its date" check. That guess used to decide which options showed,
// which could disagree with the actual stored status (overdue is a
// real status the backend sets via a scheduled job, not just "the
// date has passed"), silently hiding valid transitions like
// pending -> in_progress whenever the client's own date math
// disagreed with what was actually in the database.
const ALLOWED_TRANSITIONS = {
  pending: ['in_progress', 'skipped'],
  in_progress: ['completed', 'skipped', 'pending'],
  overdue: ['in_progress', 'completed', 'skipped'],
  completed: ['pending'],
  skipped: ['pending'],
}

function availableStatusOptions(task) {
  // Mirrors the backend's effective_status_for_transitions exactly:
  // mark_overdue_tasks is a scheduled job, so a task can be visually
  // late for a while with status still literally "pending" before
  // that job next runs. Options shown here must match what the task
  // actually looks like, not depend on that job's timing — otherwise
  // "Completed" silently disappears for a task everyone can see is
  // overdue, until the job eventually catches up.
  const effectiveStatus = (task.status === 'pending' && isOverdue(task)) ? 'overdue' : task.status
  const allowed = ALLOWED_TRANSITIONS[effectiveStatus] || []
  return [
    { value: task.status, label: statusLabel(task.status) },
    ...allowed.map(v => ({ value: v, label: statusLabel(v) })),
  ]
}

const overdueTasks = computed(() => tasks.value.filter(isOverdue))
// Pending/In Progress both exclude anything already caught by
// isOverdue — a task whose end date has passed is shown as Overdue
// regardless of its literal stored status (matches the backend's
// effective_status_for_transitions, which is why "Completed" is
// offered directly on these even before mark_overdue_tasks has run).
const pendingTasks = computed(() => tasks.value.filter(t => !isOverdue(t) && t.status === 'pending'))
const inProgressTasks = computed(() => tasks.value.filter(t => !isOverdue(t) && t.status === 'in_progress'))
const completedTasks = computed(() => tasks.value.filter(t => t.status === 'completed'))
const skippedTasks = computed(() => tasks.value.filter(t => t.status === 'skipped'))

const progress = computed(() => {
  if (tasks.value.length === 0) return 0
  return Math.round(((completedTasks.value.length + skippedTasks.value.length) / tasks.value.length) * 100)
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
    {
      const rawActivities = Array.isArray(activitiesRes.data) ? activitiesRes.data : (activitiesRes.data.results || [])
      const seenActivityIds = new Set()
      activities.value = rawActivities.filter(a => {
        if (seenActivityIds.has(a.cycle_activity_id)) return false
        seenActivityIds.add(a.cycle_activity_id)
        return true
      })
    }

    // Dependencies live on the template's tasks, not the cycle's —
    // pull every edge and keep only the ones whose task belongs to
    // this cycle's template, same approach as TemplateDetailView.
    try {
      const depsRes = await getTaskDependencies()
      const templateTaskIds = new Set(tasks.value.map(t => t.template_task))
      const allDeps = Array.isArray(depsRes.data) ? depsRes.data : (depsRes.data.results || [])
      dependencies.value = allDeps.filter(d => templateTaskIds.has(d.task))
    } catch {
      dependencies.value = []
    }

    // Tags also live on the template's tasks/activities, not the
    // cycle's own — a cycle task/activity shows whatever tags its
    // originating template task/activity currently carries.
    try {
      const templateTaskIds = new Set(tasks.value.map(t => t.template_task))
      const templateActivityIds = new Set(activities.value.map(a => a.template_activity))
      const [tagsRes, taskTagsRes, activityTagsRes] = await Promise.all([
        getTags(), getTaskTags(), getActivityTags(),
      ])
      tags.value = Array.isArray(tagsRes.data) ? tagsRes.data : (tagsRes.data.results || [])
      const allTaskTags = Array.isArray(taskTagsRes.data) ? taskTagsRes.data : (taskTagsRes.data.results || [])
      taskTags.value = allTaskTags.filter(tt => templateTaskIds.has(tt.template_task))
      const allActivityTags = Array.isArray(activityTagsRes.data) ? activityTagsRes.data : (activityTagsRes.data.results || [])
      activityTags.value = allActivityTags.filter(at => templateActivityIds.has(at.template_activity))
    } catch {
      tags.value = []
      taskTags.value = []
      activityTags.value = []
    }
  } catch (e) {
    error.value = getErrorMessage(e, 'Failed to load cycle. Please try again.')
  } finally {
    loading.value = false
  }
}

// Looks up the dependency (if any) for a cycle task via its
// template_task id, and resolves it back to the cycle task that
// represents that prerequisite in THIS cycle.
function dependencyForTask(task) {
  const edge = dependencies.value.find(d => d.task === task.template_task)
  if (!edge) return null
  return tasks.value.find(t => t.template_task === edge.depends_on_task) || null
}

function tagsForTask(task) {
  return taskTags.value
    .filter(tt => tt.template_task === task.template_task)
    .map(tt => tags.value.find(t => t.tag_id === tt.tag))
    .filter(Boolean)
}

const hasAnyTaskTag = computed(() => tasks.value.some(t => tagsForTask(t).length > 0))

// Group by tag: a task with more than one tag appears once per tag
// group (matches how the Gantt's own group-by-tag mode works), tasks
// with none land in "Untagged" at the end.
const tagGroups = computed(() => {
  const groups = {}
  for (const t of tasks.value) {
    const taskTagList = tagsForTask(t)
    if (taskTagList.length === 0) {
      groups['Untagged'] = groups['Untagged'] || []
      groups['Untagged'].push(t)
    } else {
      for (const tag of taskTagList) {
        groups[tag.tag_name] = groups[tag.tag_name] || []
        groups[tag.tag_name].push(t)
      }
    }
  }
  return Object.keys(groups)
    .sort((a, b) => {
      if (a === 'Untagged') return 1
      if (b === 'Untagged') return -1
      return a.localeCompare(b)
    })
    .map(name => ({ name, tasks: groups[name] }))
})

function tagsForActivity(activity) {
  return activityTags.value
    .filter(at => at.template_activity === activity.template_activity)
    .map(at => tags.value.find(t => t.tag_id === at.tag))
    .filter(Boolean)
}

// Which activity a task belongs to — makes the task<->activity
// grouping visible on the task card itself, not just on the
// activity's own card.
function activityForTask(task) {
  if (!task.cycle_activity) return null
  return activities.value.find(a => a.cycle_activity_id === task.cycle_activity) || null
}

function tasksForActivity(activity) {
  return tasks.value.filter(t => t.cycle_activity === activity.cycle_activity_id)
}

// Activities are collapsed by default (name/dates/status only) —
// expand one to see its description, note, tags, and every task
// under it in the same place, instead of duplicating that task info
// as always-visible cards mixed in with the status-grouped lists.
const expandedActivityIds = ref(new Set())
function toggleActivityExpanded(activity) {
  const next = new Set(expandedActivityIds.value)
  if (next.has(activity.cycle_activity_id)) {
    next.delete(activity.cycle_activity_id)
  } else {
    next.add(activity.cycle_activity_id)
  }
  expandedActivityIds.value = next
}

async function updateTaskStatus(taskId, newStatus) {
  try {
    const { data } = await updateCycleTask(taskId, newStatus)
    await loadCycle()
    if (data.cycle_just_completed) {
      toast.success('Last task of the cycle completed/skipped — cycle shut down.')
    } else {
      toast.success('Task status updated.')
    }
  } catch (e) {
    if (isPrerequisitesUnresolvedError(e)) {
      prereqModal.value = {
        open: true,
        taskId,
        newStatus,
        unresolved: getUnresolvedPrerequisites(e),
        choices: {},
      }
      return
    }
    if (isCycleFrozenError(e)) {
      toast.error('This cycle is completed or shut down, so its tasks can no longer be changed.')
      return
    }
    toast.error(getErrorMessage(e, 'Failed to update task status.'))
  }
}

async function confirmPrereqResolution() {
  const { taskId, newStatus, unresolved, choices } = prereqModal.value
  const missing = unresolved.filter(t => !choices[t.cycle_task_id])
  if (missing.length) {
    toast.error(`Resolve "${missing[0].task_name}" first — choose completed or skipped.`)
    return
  }
  prereqLoading.value = true
  try {
    await updateCycleTask(taskId, newStatus, choices)
    prereqModal.value.open = false
    await loadCycle()
    toast.success('Prerequisites resolved and task status updated.')
  } catch (e) {
    toast.error(getErrorMessage(e, 'Failed to resolve prerequisites.'))
  } finally {
    prereqLoading.value = false
  }
}

// ── SHIFT (delay / reschedule) ─────────────────────────────

// True if at least one other task in this cycle directly depends on
// this one — shifting it "single" scope only (leaving dependents in
// place) would silently push the schedule out of sync with the
// dependency it's supposed to satisfy, so that option is blocked
// below rather than just risked.
function hasDirectDependents(task) {
  return tasks.value.some(t => dependencyForTask(t)?.cycle_task_id === task.cycle_task_id)
}

function openShiftModal(task) {
  const forceCascade = hasDirectDependents(task)
  shiftModal.value = {
    open: true, task, mode: 'delay', days: '', newDate: task.calculated_end_date,
    scope: forceCascade ? 'cascade' : 'single', overrideFixed: false, preview: null,
    hasDependents: forceCascade, maxSafeDelayDays: null,
  }
  // Fetch the safe-delay ceiling right away (independent of whatever
  // delay value ends up entered) so the input can show/enforce it
  // up front instead of the user finding out only after guessing.
  previewTaskShift(task.cycle_task_id, { delayDays: 0 })
    .then(({ data }) => { shiftModal.value.maxSafeDelayDays = data.max_safe_delay_days ?? null })
    .catch(() => { shiftModal.value.maxSafeDelayDays = null })
}

function shiftPayload() {
  const m = shiftModal.value
  return m.mode === 'delay'
    ? { delayDays: Number(m.days) }
    : { newEndDate: m.newDate }
}

const cascadeBlockedMessage = computed(() => {
  const plan = shiftModal.value.preview?.cascade_plan || []
  const blocked = plan.filter(step => !step.shiftable)
  if (blocked.length === 0) return "This cascade can't proceed as planned."
  const names = blocked.map(s => `"${s.task_name}"`).join(', ')
  return `${names} ${blocked.length > 1 ? 'have' : 'has'} a fixed date and would need to move to keep this dependency chain valid. Check "Move fixed-date tasks too" above, or reschedule ${blocked.length > 1 ? 'them' : 'it'} directly first.`
})

const cascadeOnlyBlockedByFixedDate = computed(() => {
  const blocked = (shiftModal.value.preview?.cascade_plan || []).filter(step => !step.shiftable)
  return blocked.length > 0 && blocked.every(step => step.blocking_reason === 'fixed_date')
})

const canApplyShift = computed(() => {
  const p = shiftModal.value.preview
  if (!p) return false
  if (p.upstream_conflict) return false
  if (shiftModal.value.scope === 'single' && !p.single_possible) return false
  if (shiftModal.value.scope === 'cascade' && !p.cascade_possible) {
    // p.cascade_possible reflects the plan as previewed, WITHOUT the
    // override — the preview endpoint has no override_fixed input,
    // so it can never itself report "possible" once a downstream
    // task is fixed-date. If every blocked step is blocked ONLY by a
    // fixed date (not some other reason), checking "Move fixed-date
    // tasks too" is exactly what makes it possible; without this,
    // ticking that box could never actually unblock Apply.
    if (!(cascadeOnlyBlockedByFixedDate.value && shiftModal.value.overrideFixed)) return false
  }
  return true
})

async function runShiftPreview() {
  const m = shiftModal.value
  if (m.mode === 'delay' && (m.days === '' || isNaN(Number(m.days)) || Number(m.days) < 0)) {
    toast.error('Please enter a valid number of days.')
    return
  }
  if (m.mode === 'delay' && m.scope === 'single' && m.maxSafeDelayDays !== null && Number(m.days) > m.maxSafeDelayDays) {
    toast.error(`Only up to ${m.maxSafeDelayDays} day${m.maxSafeDelayDays !== 1 ? 's' : ''} is safe without moving dependent tasks. Switch to cascade scope for a longer delay.`)
    return
  }
  if (m.mode === 'date' && !m.newDate) {
    toast.error('Please pick a date.')
    return
  }
  shiftPreviewLoading.value = true
  try {
    const { data } = await previewTaskShift(m.task.cycle_task_id, shiftPayload())
    shiftModal.value.preview = data
  } catch (e) {
    if (isCycleFrozenError(e)) {
      toast.error('This cycle is completed or shut down, so its tasks can no longer be rescheduled.')
      shiftModal.value.open = false
      return
    }
    toast.error(getErrorMessage(e, 'Failed to preview this change.'))
  } finally {
    shiftPreviewLoading.value = false
  }
}

async function confirmShift() {
  const m = shiftModal.value
  shiftLoading.value = true
  try {
    const { data } = await applyTaskShift(m.task.cycle_task_id, {
      ...shiftPayload(),
      scope: m.scope,
      overrideFixed: m.overrideFixed,
    })
    shiftModal.value.open = false
    await loadCycle()
    if (data.warnings?.length) {
      toast.warning(data.warnings.map(w => w.message || w).join(' '))
    } else {
      toast.success(m.scope === 'cascade' ? 'Date updated and dependent tasks recalculated.' : 'Date updated.')
    }
  } catch (e) {
    if (isCycleFrozenError(e)) {
      toast.error('This cycle is completed or shut down, so its tasks can no longer be rescheduled.')
      shiftModal.value.open = false
      return
    }
    if (isDependencyConflictError(e)) {
      // Surface the conflict but keep the modal open so the user can
      // switch to cascade scope or override the fixed date.
      toast.error(getErrorMessage(e, 'This change conflicts with a dependency or a fixed-date task.'))
      return
    }
    toast.error(getErrorMessage(e, 'Failed to update the schedule.'))
  } finally {
    shiftLoading.value = false
  }
}

// ── NOTES (tasks and activities share one modal) ───────────

function openNoteModal(kind, item) {
  noteModal.value = { open: true, kind, id: kind === 'task' ? item.cycle_task_id : item.cycle_activity_id, text: item.note_text || '' }
}

async function saveNote() {
  const { kind, id, text } = noteModal.value
  noteLoading.value = true
  try {
    if (!text.trim()) {
      if (kind === 'task') {
        await clearTaskNote(id)
      } else {
        await clearActivityNote(id)
      }
    } else {
      if (kind === 'task') {
        await setTaskNote(id, text.trim())
      } else {
        await setActivityNote(id, text.trim())
      }
    }
    noteModal.value.open = false
    await loadCycle()
    toast.success('Note saved.')
  } catch (e) {
    if (isCycleFrozenError(e)) {
      toast.error('This cycle is completed or shut down, so its notes can no longer be edited.')
      noteModal.value.open = false
      return
    }
    toast.error(getErrorMessage(e, 'Failed to save note.'))
  } finally {
    noteLoading.value = false
  }
}

// ── ACTIVITY DATE EDIT ──────────────────────────────────────

function openActivityEdit(activity) {
  activityEditModal.value = {
    open: true, activity,
    start: activity.calculated_start_date,
    end: activity.calculated_end_date,
  }
}

async function saveActivityEdit() {
  const { activity, start, end } = activityEditModal.value
  if (!start || !end) {
    toast.error('Both a start and end date are required.')
    return
  }
  if (start > end) {
    toast.error('An activity cannot end before it starts.')
    return
  }
  activityEditLoading.value = true
  try {
    await updateCycleActivity(activity.cycle_activity_id, { calculatedStartDate: start, calculatedEndDate: end })
    activityEditModal.value.open = false
    await loadCycle()
    toast.success('Activity dates updated.')
  } catch (e) {
    if (isCycleFrozenError(e)) {
      toast.error('This cycle is completed or shut down, so its activities can no longer be resized.')
      activityEditModal.value.open = false
      return
    }
    // Most common case: a task inside the activity would fall
    // outside the new range — the backend rejects the resize rather
    // than moving tasks, so tell the user exactly that.
    toast.error(getErrorMessage(e, 'Failed to resize this activity.'))
  } finally {
    activityEditLoading.value = false
  }
}

async function confirmShutdownCycle() {
  shutdownLoading.value = true
  try {
    await shutdownCycle(cycleId)
    shutdownModal.value = false
    await loadCycle()
    toast.success('Cycle shut down.')
  } catch (e) {
    toast.error(getErrorMessage(e, 'Failed to shut down cycle.'))
  } finally {
    shutdownLoading.value = false
  }
}

function statusClass(status) {
  if (status === 'completed') return 'status-completed'
  if (status === 'in_progress') return 'status-in-progress'
  if (status === 'skipped') return 'status-skipped'
  if (status === 'overdue') return 'status-overdue'
  return 'status-pending'
}

function statusLabel(status) {
  const map = { pending: 'Pending', in_progress: 'In Progress', completed: 'Completed', overdue: 'Overdue', skipped: 'Skipped' }
  return map[status] || status
}

async function openTaskDetail(task) {
  taskDetailModal.value = { open: true, task, templateDetail: null, loading: true }
  try {
    const { data } = await getTemplateTaskDetail(task.template_task)
    taskDetailModal.value.templateDetail = data
  } catch {
    // If this fails (e.g. the template task was since deleted), the
    // modal still shows everything available directly on the
    // CycleTask itself — just without the original description.
  } finally {
    taskDetailModal.value.loading = false
  }
}

// Feeds the dedicated CycleGanttChart component (grouping, status
// colors, click-to-inspect) — converts the cycle's absolute dates
// into days-from-cycle-start so the chart stays purely relative.
function dayOffset(dateStr) {
  if (!cycle.value?.start_date || !dateStr) return 0
  const start = parseDate(cycle.value.start_date)
  const d = parseDate(dateStr)
  return Math.round((d - start) / (1000 * 60 * 60 * 24))
}

const ganttData = computed(() => {
  if (!cycle.value || (tasks.value.length === 0 && activities.value.length === 0)) return null

  const taskBars = tasks.value.map(t => {
    const depTask = dependencyForTask(t)
    return {
      id: t.cycle_task_id,
      name: t.task_name,
      start: dayOffset(t.calculated_start_date),
      end: dayOffset(t.calculated_end_date),
      startDate: t.calculated_start_date,
      endDate: t.calculated_end_date,
      isMandatory: t.is_mandatory,
      isFixed: t.is_fixed_date,
      status: t.status,
      activityId: t.cycle_activity || null,
      depName: depTask ? depTask.task_name : null,
      dependsOnId: depTask ? depTask.cycle_task_id : null,
      tags: tagsForTask(t),
    }
  })

  const activityBars = activities.value.map(a => ({
    id: a.cycle_activity_id,
    name: a.activity_name,
    start: dayOffset(a.calculated_start_date),
    end: dayOffset(a.calculated_end_date),
    startDate: a.calculated_start_date,
    endDate: a.calculated_end_date,
    tags: tagsForActivity(a),
  }))

  const allEnds = [...taskBars.map(b => b.end), ...activityBars.map(b => b.end)]
  const maxDay = Math.max(...allEnds, 1)

  return { taskBars, activityBars, maxDay }
})

function formatTaskReminders(val) {
  if (!val || (Array.isArray(val) && val.length === 0)) return 'None'
  const list = Array.isArray(val) ? val : [val]
  return list
    .slice()
    .sort((a, b) => b - a)
    .map(d => d === 0 ? 'On the day' : `${d} day${d !== 1 ? 's' : ''} before`)
    .join(', ')
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

        <!-- VIEW MODE TOGGLE -->
        <div class="view-toggle-bar">
          <div class="view-toggle">
            <button type="button" class="view-toggle-btn" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
              List
            </button>
            <button type="button" class="view-toggle-btn" :class="{ active: viewMode === 'gantt' }" @click="viewMode = 'gantt'">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="8" y1="4" x2="8" y2="10"/></svg>
              Gantt
            </button>
          </div>
          <div v-if="viewMode === 'list'" class="view-toggle" style="margin-left: 10px;">
            <span class="view-toggle-label">Group by</span>
            <button type="button" class="view-toggle-btn" :class="{ active: listGroupBy === 'status' }" @click="listGroupBy = 'status'">Status</button>
            <button type="button" class="view-toggle-btn" :class="{ active: listGroupBy === 'tag' }" :disabled="!hasAnyTaskTag" @click="listGroupBy = 'tag'">Tag</button>
          </div>
        </div>

        <!-- GANTT VIEW -->
        <div v-if="viewMode === 'gantt'" class="gantt-card">
          <div class="gantt-header">Timeline · Day 0 = {{ formatDate(cycle.start_date) }}</div>
          <div v-if="!ganttData" class="gantt-empty">No tasks or activities to display.</div>
          <CycleGanttChart v-else :task-bars="ganttData.taskBars" :activity-bars="ganttData.activityBars" :max-day="ganttData.maxDay" :px-per-day="32" />
        </div>

        <!-- LIST VIEW · GROUPED BY TAG -->
        <div v-else-if="listGroupBy === 'tag'" class="two-col">
          <div class="col-main">
            <div v-if="tagGroups.length === 0" class="empty-section">No tags assigned to any task yet.</div>
            <div v-for="group in tagGroups" :key="group.name">
              <div class="timeline-label">{{ group.name }}</div>
              <div v-for="task in group.tasks" :key="task.cycle_task_id" class="task-card" :class="{ 'overdue-card': isOverdue(task), 'completed-card': task.status === 'completed', 'skipped-card': task.status === 'skipped' }" @click="openTaskDetail(task)">
                <div class="tc-row">
                  <div class="tc-left">
                    <div class="tc-name">{{ task.task_name }}<span v-if="task.is_mandatory" class="tc-mandatory">MANDATORY</span><span v-if="task.is_fixed_date" class="tc-fixed">FIXED DATE</span></div>
                    <div class="tc-dates">{{ formatDate(task.calculated_start_date) }} → {{ formatDate(task.calculated_end_date) }}</div>
                    <div v-if="dependencyForTask(task)" class="tc-dep">Depends on: {{ dependencyForTask(task).task_name }}</div>
                    <div v-if="activityForTask(task)" class="tc-activity-badge">Part of: {{ activityForTask(task).activity_name }}</div>
                    <div v-if="tagsForTask(task).length > 0" class="tc-tag-row"><span v-for="tag in tagsForTask(task)" :key="tag.tag_id" class="tc-tag-chip">{{ tag.tag_name }}</span></div>
                  </div>
                  <div class="tc-right" @click.stop>
                    <div class="tc-right-top">
                      <span class="tc-status" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span>
                      <div class="row-menu" @click.stop>
                        <button type="button" class="row-menu-trigger" @click="toggleMenu('tasktag-' + task.cycle_task_id)">
                          <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>
                        </button>
                        <div v-if="openMenuFor === 'tasktag-' + task.cycle_task_id" class="row-menu-dropdown">
                          <button type="button" class="row-menu-item" @click="openNoteModal('task', task); openMenuFor = null">{{ task.note_text ? 'Edit note' : 'Add note' }}</button>
                        </div>
                      </div>
                    </div>
                    <div class="status-actions">
                      <button
                        v-for="opt in availableStatusOptions(task).filter(o => o.value !== task.status)"
                        :key="opt.value"
                        class="status-pill"
                        :class="statusClass(opt.value)"
                        @click="updateTaskStatus(task.cycle_task_id, opt.value)"
                      >{{ opt.label }}</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="col-side">
            <div class="side-card">
              <div class="side-card-title">Status summary</div>
              <div class="legend-item"><div class="legend-dot" style="background:var(--status-pending);"></div><span class="legend-label">Pending</span><span class="legend-count">{{ pendingTasks.length }}</span></div>
              <div class="legend-item"><div class="legend-dot" style="background:var(--warning);"></div><span class="legend-label">In progress</span><span class="legend-count">{{ inProgressTasks.length }}</span></div>
              <div class="legend-item"><div class="legend-dot" style="background:var(--danger);"></div><span class="legend-label">Overdue</span><span class="legend-count">{{ overdueTasks.length }}</span></div>
              <div class="legend-item"><div class="legend-dot" style="background:var(--success);"></div><span class="legend-label">Completed</span><span class="legend-count">{{ completedTasks.length }}</span></div>
              <div class="legend-item"><div class="legend-dot" style="background:var(--status-skipped);"></div><span class="legend-label">Skipped</span><span class="legend-count">{{ skippedTasks.length }}</span></div>
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

        <div v-else class="two-col">
          <div class="col-main">

            <div v-if="activities.length > 0">
              <div class="timeline-label violet">Active Activities</div>
              <div v-for="act in activities" :key="act.cycle_activity_id" class="activity-card" :class="{ 'activity-card-expanded': expandedActivityIds.has(act.cycle_activity_id) }">
                <div class="act-row act-row-clickable" @click="toggleActivityExpanded(act)">
                  <div class="act-name">
                    <svg class="act-chevron" :class="{ 'act-chevron-open': expandedActivityIds.has(act.cycle_activity_id) }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 6 15 12 9 18"/></svg>
                    {{ act.activity_name }}
                    <span class="act-task-count">{{ tasksForActivity(act).length }} task{{ tasksForActivity(act).length !== 1 ? 's' : '' }}</span>
                  </div>
                  <div class="tc-right-top">
                    <span class="tc-status status-activity">Activity</span>
                    <div v-if="cycle.status === 'running'" class="row-menu" @click.stop>
                      <button type="button" class="row-menu-trigger" @click="toggleMenu('activity-' + act.cycle_activity_id)">
                        <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>
                      </button>
                      <div v-if="openMenuFor === 'activity-' + act.cycle_activity_id" class="row-menu-dropdown">
                        <button type="button" class="row-menu-item" @click="openActivityEdit(act); openMenuFor = null">Edit dates</button>
                        <button type="button" class="row-menu-item" @click="openNoteModal('activity', act); openMenuFor = null">{{ act.note_text ? 'Edit note' : 'Add note' }}</button>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="act-dates">{{ formatDate(act.calculated_start_date) }} → {{ formatDate(act.calculated_end_date) }}</div>

                <template v-if="expandedActivityIds.has(act.cycle_activity_id)">
                  <div v-if="act.note_text" class="act-note">{{ act.note_text }}</div>
                  <div v-if="tagsForActivity(act).length > 0" class="tc-tag-row"><span v-for="tag in tagsForActivity(act)" :key="tag.tag_id" class="tc-tag-chip tc-tag-chip-violet">{{ tag.tag_name }}</span></div>

                  <div v-if="tasksForActivity(act).length > 0" class="act-task-list">
                    <div v-for="task in tasksForActivity(act)" :key="task.cycle_task_id" class="act-task-row" @click.stop="openTaskDetail(task)">
                      <span class="act-task-name">{{ task.task_name }}</span>
                      <span class="tc-status" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span>
                    </div>
                  </div>
                  <div v-else class="act-task-empty">No tasks under this activity yet.</div>
                </template>
              </div>
            </div>

            <div v-if="overdueTasks.length > 0">
              <div class="timeline-label danger">⚠ Overdue</div>
              <div v-for="task in overdueTasks" :key="task.cycle_task_id" class="task-card overdue-card" @click="openTaskDetail(task)">
                <div class="tc-row">
                  <div class="tc-left">
                    <div class="tc-name">{{ task.task_name }}<span v-if="task.is_mandatory" class="tc-mandatory">MANDATORY</span></div>
                    <div class="tc-dates">{{ formatDate(task.calculated_start_date) }} → {{ formatDate(task.calculated_end_date) }}</div>
                    <div v-if="dependencyForTask(task)" class="tc-dep">Depends on: {{ dependencyForTask(task).task_name }}</div>
                    <div v-if="activityForTask(task)" class="tc-activity-badge">Part of: {{ activityForTask(task).activity_name }}</div>
                    <div v-if="tagsForTask(task).length > 0" class="tc-tag-row"><span v-for="tag in tagsForTask(task)" :key="tag.tag_id" class="tc-tag-chip">{{ tag.tag_name }}</span></div>
                    <div v-if="task.note_text" class="tc-note">{{ task.note_text }}</div>
                  </div>
                  <div class="tc-right" @click.stop>
                    <div class="tc-right-top">
                      <span class="tc-status" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span>
                      <div class="row-menu" @click.stop>
                        <button type="button" class="row-menu-trigger" @click="toggleMenu('overdue-' + task.cycle_task_id)">
                          <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>
                        </button>
                        <div v-if="openMenuFor === 'overdue-' + task.cycle_task_id" class="row-menu-dropdown">
                          <button type="button" class="row-menu-item" @click="openNoteModal('task', task); openMenuFor = null">{{ task.note_text ? 'Edit note' : 'Add note' }}</button>
                        </div>
                      </div>
                    </div>
                    <div class="status-actions">
                      <button
                        v-for="opt in availableStatusOptions(task).filter(o => o.value !== task.status)"
                        :key="opt.value"
                        class="status-pill"
                        :class="statusClass(opt.value)"
                        @click="updateTaskStatus(task.cycle_task_id, opt.value)"
                      >{{ opt.label }}</button>
                      <button class="status-pill pill-delay" @click.stop="openShiftModal(task)">Reschedule</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="pendingTasks.length > 0">
              <div class="timeline-label">Pending</div>
              <div v-for="task in pendingTasks" :key="task.cycle_task_id" class="task-card" @click="openTaskDetail(task)">
                <div class="tc-row">
                  <div class="tc-left">
                    <div class="tc-name">{{ task.task_name }}<span v-if="task.is_mandatory" class="tc-mandatory">MANDATORY</span><span v-if="task.is_fixed_date" class="tc-fixed">FIXED DATE</span></div>
                    <div class="tc-dates">{{ formatDate(task.calculated_start_date) }} → {{ formatDate(task.calculated_end_date) }}</div>
                    <div v-if="dependencyForTask(task)" class="tc-dep">Depends on: {{ dependencyForTask(task).task_name }}</div>
                    <div v-if="activityForTask(task)" class="tc-activity-badge">Part of: {{ activityForTask(task).activity_name }}</div>
                    <div v-if="tagsForTask(task).length > 0" class="tc-tag-row"><span v-for="tag in tagsForTask(task)" :key="tag.tag_id" class="tc-tag-chip">{{ tag.tag_name }}</span></div>
                  </div>
                  <div class="tc-right" @click.stop>
                    <div class="tc-right-top">
                      <span class="tc-status" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span>
                      <div class="row-menu" @click.stop>
                        <button type="button" class="row-menu-trigger" @click="toggleMenu('pending-' + task.cycle_task_id)">
                          <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>
                        </button>
                        <div v-if="openMenuFor === 'pending-' + task.cycle_task_id" class="row-menu-dropdown">
                          <button type="button" class="row-menu-item" @click="openNoteModal('task', task); openMenuFor = null">{{ task.note_text ? 'Edit note' : 'Add note' }}</button>
                        </div>
                      </div>
                    </div>
                    <div class="status-actions">
                      <button
                        v-for="opt in availableStatusOptions(task).filter(o => o.value !== task.status)"
                        :key="opt.value"
                        class="status-pill"
                        :class="statusClass(opt.value)"
                        @click="updateTaskStatus(task.cycle_task_id, opt.value)"
                      >{{ opt.label }}</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="inProgressTasks.length > 0">
              <div class="timeline-label">In Progress</div>
              <div v-for="task in inProgressTasks" :key="task.cycle_task_id" class="task-card" @click="openTaskDetail(task)">
                <div class="tc-row">
                  <div class="tc-left">
                    <div class="tc-name">{{ task.task_name }}<span v-if="task.is_mandatory" class="tc-mandatory">MANDATORY</span><span v-if="task.is_fixed_date" class="tc-fixed">FIXED DATE</span></div>
                    <div class="tc-dates">{{ formatDate(task.calculated_start_date) }} → {{ formatDate(task.calculated_end_date) }}</div>
                    <div v-if="dependencyForTask(task)" class="tc-dep">Depends on: {{ dependencyForTask(task).task_name }}</div>
                    <div v-if="activityForTask(task)" class="tc-activity-badge">Part of: {{ activityForTask(task).activity_name }}</div>
                    <div v-if="tagsForTask(task).length > 0" class="tc-tag-row"><span v-for="tag in tagsForTask(task)" :key="tag.tag_id" class="tc-tag-chip">{{ tag.tag_name }}</span></div>
                  </div>
                  <div class="tc-right" @click.stop>
                    <div class="tc-right-top">
                      <span class="tc-status" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span>
                      <div class="row-menu" @click.stop>
                        <button type="button" class="row-menu-trigger" @click="toggleMenu('inprogress-' + task.cycle_task_id)">
                          <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>
                        </button>
                        <div v-if="openMenuFor === 'inprogress-' + task.cycle_task_id" class="row-menu-dropdown">
                          <button type="button" class="row-menu-item" @click="openNoteModal('task', task); openMenuFor = null">{{ task.note_text ? 'Edit note' : 'Add note' }}</button>
                        </div>
                      </div>
                    </div>
                    <div class="status-actions">
                      <button
                        v-for="opt in availableStatusOptions(task).filter(o => o.value !== task.status)"
                        :key="opt.value"
                        class="status-pill"
                        :class="statusClass(opt.value)"
                        @click="updateTaskStatus(task.cycle_task_id, opt.value)"
                      >{{ opt.label }}</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="completedTasks.length > 0">
              <div class="timeline-label">Completed</div>
              <div v-for="task in completedTasks" :key="task.cycle_task_id" class="task-card completed-card" @click="openTaskDetail(task)">
                <div class="tc-row">
                  <div class="tc-left">
                    <div class="tc-name">{{ task.task_name }}</div>
                    <div class="tc-dates">{{ formatDate(task.calculated_start_date) }}</div>
                  </div>
                  <div class="tc-right">
                    <span class="tc-status status-completed">Completed</span>
                    <button class="action-btn action-undo" @click.stop="updateTaskStatus(task.cycle_task_id, 'pending')">Undo</button>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="skippedTasks.length > 0">
              <div class="timeline-label">Skipped</div>
              <div v-for="task in skippedTasks" :key="task.cycle_task_id" class="task-card skipped-card" @click="openTaskDetail(task)">
                <div class="tc-row">
                  <div class="tc-left">
                    <div class="tc-name">{{ task.task_name }}</div>
                    <div class="tc-dates">{{ formatDate(task.calculated_start_date) }}</div>
                  </div>
                  <div class="tc-right">
                    <span class="tc-status status-skipped">Skipped</span>
                    <button class="action-btn action-undo" @click.stop="updateTaskStatus(task.cycle_task_id, 'pending')">Undo</button>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="tasks.length === 0 && activities.length === 0" class="empty-section">No tasks or activities in this cycle yet.</div>
          </div>

          <div class="col-side">
            <div class="side-card">
              <div class="side-card-title">Status summary</div>
              <div class="legend-item"><div class="legend-dot" style="background:var(--status-pending);"></div><span class="legend-label">Pending</span><span class="legend-count">{{ pendingTasks.length }}</span></div>
              <div class="legend-item"><div class="legend-dot" style="background:var(--warning);"></div><span class="legend-label">In progress</span><span class="legend-count">{{ inProgressTasks.length }}</span></div>
              <div class="legend-item"><div class="legend-dot" style="background:var(--danger);"></div><span class="legend-label">Overdue</span><span class="legend-count">{{ overdueTasks.length }}</span></div>
              <div class="legend-item"><div class="legend-dot" style="background:var(--success);"></div><span class="legend-label">Completed</span><span class="legend-count">{{ completedTasks.length }}</span></div>
              <div class="legend-item"><div class="legend-dot" style="background:var(--status-skipped);"></div><span class="legend-label">Skipped</span><span class="legend-count">{{ skippedTasks.length }}</span></div>
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

    <!-- RESCHEDULE (SHIFT) MODAL -->
    <BaseModal
      v-model="shiftModal.open"
      title="Reschedule task"
      :confirm-label="shiftModal.preview ? 'Apply change' : 'Preview change'"
      :loading="shiftLoading || shiftPreviewLoading"
      :confirm-disabled="shiftModal.preview && !canApplyShift"
      @confirm="shiftModal.preview ? confirmShift() : runShiftPreview()"
    >
      <div class="shift-modal-body">
        <div class="shift-mode-tabs">
          <button type="button" class="shift-mode-tab" :class="{ active: shiftModal.mode === 'delay' }" @click="shiftModal.mode = 'delay'; shiftModal.preview = null">Delay by days</button>
          <button type="button" class="shift-mode-tab" :class="{ active: shiftModal.mode === 'date' }" @click="shiftModal.mode = 'date'; shiftModal.preview = null">Pick new end date</button>
        </div>

        <BaseInput
          v-if="shiftModal.mode === 'delay'"
          v-model="shiftModal.days"
          type="number"
          label="Delay (days)"
          placeholder="e.g. 3"
          :max="shiftModal.scope === 'single' ? shiftModal.maxSafeDelayDays : undefined"
          :hint="shiftModal.scope === 'single' && shiftModal.maxSafeDelayDays !== null
            ? `Up to ${shiftModal.maxSafeDelayDays} day${shiftModal.maxSafeDelayDays !== 1 ? 's' : ''} is safe without moving anything else. More requires cascade scope.`
            : 'How many days to push this task back.'"
          @update:model-value="shiftModal.preview = null"
        />
        <BaseDatePicker
          v-else
          v-model="shiftModal.newDate"
          label="New end date"
          @update:model-value="shiftModal.preview = null"
        />

        <BaseSelect v-model="shiftModal.scope" label="Scope" @update:model-value="shiftModal.preview = null">
          <option value="single" :disabled="shiftModal.hasDependents">Only this task</option>
          <option value="cascade">This task and everything downstream of it</option>
        </BaseSelect>
        <p v-if="shiftModal.hasDependents" class="shift-scope-note">
          Other tasks depend on this one, so it can only be rescheduled together with everything
          downstream of it — moving it alone would leave the dependency out of sync with the actual dates.
        </p>

        <label class="check-item">
          <input type="checkbox" v-model="shiftModal.overrideFixed" />
          <span>Move fixed-date tasks too if this task (or anything downstream of it) is fixed</span>
        </label>

        <div v-if="shiftModal.preview" class="shift-preview-box">
          <div class="shift-preview-title">Preview</div>
          <div class="shift-preview-row">
            New dates: {{ formatDate(shiftModal.preview.planned_start_date) }} → {{ formatDate(shiftModal.preview.planned_end_date) }}
          </div>
          <div v-if="shiftModal.preview.upstream_conflict" class="shift-preview-warning">
            {{ shiftModal.preview.upstream_conflict.message }}
          </div>
          <div v-else-if="shiftModal.scope === 'single' && !shiftModal.preview.single_possible" class="shift-preview-warning">
            Can't shift this task alone{{ shiftModal.preview.single_blocking_task ? ` — "${shiftModal.preview.single_blocking_task}" would need to move too.` : '.' }} Switch to cascade scope.
          </div>
          <div v-else-if="shiftModal.scope === 'cascade' && !shiftModal.preview.cascade_possible && !(cascadeOnlyBlockedByFixedDate && shiftModal.overrideFixed)" class="shift-preview-warning">
            {{ cascadeBlockedMessage }}
          </div>
          <div v-else class="shift-preview-row" style="color: var(--success);">
            This change can be applied.
          </div>
        </div>
      </div>
    </BaseModal>

    <!-- NOTE EDITOR MODAL (tasks and activities) -->
    <BaseModal
      v-model="noteModal.open"
      :title="noteModal.kind === 'task' ? 'Task note' : 'Activity note'"
      confirm-label="Save note"
      :loading="noteLoading"
      @confirm="saveNote"
    >
      <label class="field-label">Note</label>
      <textarea v-model="noteModal.text" class="field-textarea" rows="4" placeholder="Add a note..."></textarea>
      <p class="modal-hint">Leaving this empty and saving removes the note.</p>
    </BaseModal>

    <!-- ACTIVITY DATE EDIT MODAL -->
    <BaseModal
      v-model="activityEditModal.open"
      title="Edit activity dates"
      confirm-label="Save dates"
      :loading="activityEditLoading"
      @confirm="saveActivityEdit"
    >
      <p class="modal-hint">Every task still anchored to this activity must fit inside the new range — tasks are never moved to make room, the change is rejected instead.</p>
      <BaseDatePicker v-model="activityEditModal.start" label="Start date" />
      <BaseDatePicker v-model="activityEditModal.end" label="End date" />
    </BaseModal>

    <!-- UNRESOLVED PREREQUISITES MODAL -->
    <BaseModal
      v-model="prereqModal.open"
      title="Resolve prerequisites first"
      confirm-label="Resolve & complete"
      :loading="prereqLoading"
      @confirm="confirmPrereqResolution"
    >
      <p class="modal-hint">This task depends on tasks that aren't finished yet. Resolve each one below before it can be marked completed.</p>
      <div v-for="t in prereqModal.unresolved" :key="t.cycle_task_id" class="prereq-row">
        <span class="prereq-name">{{ t.task_name }}</span>
        <BaseSelect v-model="prereqModal.choices[t.cycle_task_id]">
          <option :value="undefined" disabled>Choose...</option>
          <option value="completed">Completed</option>
          <option value="skipped">Skipped</option>
        </BaseSelect>
      </div>
    </BaseModal>

    <!-- TASK DETAIL MODAL -->
    <BaseModal
      v-model="taskDetailModal.open"
      :title="taskDetailModal.task?.task_name || 'Task details'"
    >
      <div v-if="taskDetailModal.task" class="task-detail">
        <div class="task-detail-row">
          <span class="task-detail-label">Status</span>
          <span class="tc-status" :class="statusClass(taskDetailModal.task.status)">{{ statusLabel(taskDetailModal.task.status) }}</span>
        </div>
        <div class="task-detail-row">
          <span class="task-detail-label">Dates</span>
          <span class="task-detail-value">{{ formatDate(taskDetailModal.task.calculated_start_date) }} → {{ formatDate(taskDetailModal.task.calculated_end_date) }}</span>
        </div>
        <div class="task-detail-row">
          <span class="task-detail-label">Mandatory</span>
          <span class="task-detail-value">{{ taskDetailModal.task.is_mandatory ? 'Yes' : 'No' }}</span>
        </div>
        <div class="task-detail-row">
          <span class="task-detail-label">Fixed date</span>
          <span class="task-detail-value">{{ taskDetailModal.task.is_fixed_date ? 'Yes' : 'No' }}</span>
        </div>
        <div class="task-detail-row">
          <span class="task-detail-label">Reminders</span>
          <span class="task-detail-value">{{ formatTaskReminders(taskDetailModal.task.reminder_lead_days) }}</span>
        </div>
        <div v-if="dependencyForTask(taskDetailModal.task)" class="task-detail-row">
          <span class="task-detail-label">Depends on</span>
          <span class="task-detail-value">{{ dependencyForTask(taskDetailModal.task).task_name }}</span>
        </div>
        <div v-if="activityForTask(taskDetailModal.task)" class="task-detail-row">
          <span class="task-detail-label">Activity</span>
          <span class="task-detail-value">{{ activityForTask(taskDetailModal.task).activity_name }}</span>
        </div>

        <div v-if="tagsForTask(taskDetailModal.task).length > 0" class="task-detail-block">
          <div class="task-detail-block-label">Tags</div>
          <div class="tc-tag-row">
            <span v-for="tag in tagsForTask(taskDetailModal.task)" :key="tag.tag_id" class="tc-tag-chip">{{ tag.tag_name }}</span>
          </div>
        </div>

        <div v-if="taskDetailModal.task.note_text" class="task-detail-block">
          <div class="task-detail-block-label">Note</div>
          <p class="task-detail-block-text">{{ taskDetailModal.task.note_text }}</p>
        </div>

        <div v-if="taskDetailModal.loading" class="task-detail-loading">Loading template details...</div>
        <div v-else-if="taskDetailModal.templateDetail?.description" class="task-detail-block">
          <div class="task-detail-block-label">Description (from template)</div>
          <p class="task-detail-block-text">{{ taskDetailModal.templateDetail.description }}</p>
        </div>
      </div>

      <template #footer>
        <BaseButton variant="secondary" @click="taskDetailModal.open = false">Close</BaseButton>
      </template>
    </BaseModal>

  </AppLayout>
</template>

<style scoped>
.breadcrumb { display: flex; align-items: center; gap: 6px; font-size: var(--font-label); }
.breadcrumb-link { color: var(--text-muted); cursor: pointer; }
.breadcrumb-link:hover { color: var(--violet); }
.breadcrumb-sep { color: var(--text-muted); }
.breadcrumb-current { color: var(--text-primary); font-weight: 500; }

.detail-page { display: flex; flex-direction: column; gap: 20px; }
.loading-msg { font-size: var(--font-body); color: var(--text-muted); padding: 40px 0; }
.error-banner { background: var(--danger-bg); border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 12px 16px; font-size: var(--font-body); color: #B91C1C; }

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

.alert-box { background: var(--danger-bg); border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 12px 16px; display: flex; gap: 10px; align-items: flex-start; }
.alert-box svg { width: 16px; height: 16px; flex-shrink: 0; margin-top: 1px; }
.alert-title { font-size: var(--font-body); font-weight: 600; color: #B91C1C; margin-bottom: 2px; }
.alert-desc { font-size: var(--font-label); color: #991B1B; }


/* ── VIEW TOGGLE ── */
.view-toggle-bar { display: flex; align-items: center; }
.view-toggle { display: flex; align-items: center; gap: 4px; background: var(--bg-page); border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 3px; }
.view-toggle-label { font-size: var(--font-hint); font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; padding: 0 6px 0 4px; }
.view-toggle-btn { display: flex; align-items: center; gap: 6px; padding: 6px 14px; border: none; border-radius: 6px; background: transparent; color: var(--text-secondary); font-size: var(--font-label); font-weight: 500; font-family: var(--font-main); cursor: pointer; transition: background var(--transition-fast), color var(--transition-fast); }
.view-toggle-btn.active { background: var(--white); color: var(--violet); box-shadow: var(--shadow-sm); }
.view-toggle-btn:hover:not(.active) { color: var(--text-primary); }
.view-toggle-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── GANTT CARD (cycle view) ── */
.gantt-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); overflow: hidden; min-height: 420px; }
.gantt-header { padding: 14px 18px; font-size: var(--font-label); font-weight: 600; color: var(--text-primary); border-bottom: 1px solid var(--border-light); }
.gantt-empty { padding: 40px 18px; font-size: var(--font-label); color: var(--text-muted); text-align: center; }

/* ── LAYOUT ── */
.two-col { display: flex; gap: 20px; align-items: flex-start; }
.col-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px; }
.col-side { width: 260px; flex-shrink: 0; display: flex; flex-direction: column; gap: 14px; position: sticky; top: 80px; }

.timeline-label { font-size: var(--font-upper); font-weight: 600; color: var(--text-primary); text-transform: uppercase; letter-spacing: 0.07em; padding: 8px 0 6px; }
.timeline-label.danger { color: var(--danger); }
.timeline-label.violet { color: var(--violet); }

.task-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 12px 16px; margin-bottom: 6px; cursor: pointer; transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
.task-card:hover { border-color: #C4B5FD; box-shadow: var(--shadow-sm); }
.task-card.overdue-card { border-color: #FECACA; background: #FFF8F8; }
.task-card.overdue-card:hover { border-color: #FCA5A5; }
.task-card.completed-card { opacity: 0.65; }
.task-card.skipped-card { opacity: 0.65; }
.tc-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.tc-left { flex: 1; min-width: 0; }
.tc-name { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); margin-bottom: 3px; display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.tc-dates { font-size: var(--font-label); color: var(--text-secondary); }
.tc-note { font-size: var(--font-label); color: var(--text-secondary); margin-top: 4px; }
.tc-dep { font-size: var(--font-upper); color: var(--text-muted); margin-top: 4px; }
.tc-activity-badge { font-size: var(--font-upper); color: var(--violet); margin-top: 3px; font-weight: 500; }
.tc-tag-row { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 5px; }
.tc-tag-chip { font-size: var(--font-hint); font-weight: 500; background: var(--bg-page); color: var(--text-secondary); padding: 2px 8px; border-radius: 20px; border: 1px solid var(--border-light); }
.tc-tag-chip-violet { background: var(--violet-mid); color: var(--violet-dark); border-color: #DDD6FE; }
.tc-right { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; flex-shrink: 0; }
.tc-right-top { display: flex; align-items: center; gap: 8px; }
.tc-mandatory { font-size: var(--font-hint); font-weight: 700; color: var(--danger); }
.tc-fixed { font-size: var(--font-hint); font-weight: 700; color: #92400E; }

.tc-status { font-size: var(--font-hint); font-weight: 600; padding: 4px 11px; border-radius: 12px; }
.status-completed { background: var(--status-completed-badge-bg); color: var(--status-completed-badge-text); }
.status-in-progress { background: var(--status-in-progress-badge-bg); color: var(--status-in-progress-badge-text); }
.status-overdue { background: var(--status-overdue-badge-bg); color: var(--status-overdue-badge-text); }
.status-skipped { background: var(--status-skipped-badge-bg); color: var(--status-skipped-badge-text); }
.status-pending { background: var(--status-pending-badge-bg); color: var(--status-pending-badge-text); }
.status-activity { background: var(--status-activity-badge-bg); color: var(--status-activity-badge-text); }

.tc-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.action-btn {
  font-size: var(--font-label);
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-family: var(--font-main);
  transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
}
.action-btn:hover { transform: translateY(-1px); filter: brightness(0.95); box-shadow: 0 2px 6px rgba(0,0,0,0.15); }
.action-btn:active { transform: translateY(0); box-shadow: none; }
.action-complete { background: var(--success-bg); color: #15803D; border: 1px solid #BBF7D0; }
.action-delay { background: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; }

/* ── STATUS ACTIONS ── */
.status-actions { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; justify-content: flex-end; }

/* ── ROW OVERFLOW MENU ──
   Secondary per-row actions (note, edit dates) collapse behind a
   "⋯" trigger instead of sitting as always-visible buttons — keeps
   the primary status-pill actions from getting crowded out. */
.row-menu { position: relative; }
.row-menu-trigger {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--white);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}
.row-menu-trigger svg { width: 16px; height: 16px; }
.row-menu-trigger:hover { background: var(--bg-page); border-color: var(--border); }
.row-menu-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 10;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  padding: 4px;
  min-width: 140px;
  display: flex;
  flex-direction: column;
}
.row-menu-item {
  text-align: left;
  padding: 8px 10px;
  border: none;
  background: none;
  border-radius: 6px;
  font-size: var(--font-label);
  color: var(--text-primary);
  cursor: pointer;
  font-family: var(--font-main);
  white-space: nowrap;
}
.row-menu-item:hover { background: var(--bg-page); }
.status-pill {
  font-size: var(--font-hint);
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 14px;
  cursor: pointer;
  font-family: var(--font-main);
  border: 1px solid var(--border-light);
  background: var(--bg-page);
  color: var(--text-secondary);
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}
.status-pill:hover { background: var(--white); border-color: var(--border); color: var(--text-primary); }
.status-pill:active { background: var(--bg-page); }

.status-pill.pill-delay:hover { background: #FFE7D8; border-color: #F97316; color: #C2410C; }
.action-undo { background: var(--bg-page); color: var(--text-secondary); border: 1px solid var(--border-light); }

.task-detail { display: flex; flex-direction: column; gap: 10px; }
.task-detail-row { display: flex; align-items: center; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-light); }
.task-detail-row:last-of-type { border-bottom: none; }
.task-detail-label { font-size: var(--font-label); color: var(--text-secondary); }
.task-detail-value { font-size: var(--font-label); font-weight: 500; color: var(--text-primary); }
.task-detail-block { margin-top: 6px; padding-top: 10px; border-top: 1px solid var(--border-light); }
.task-detail-block-label { font-size: var(--font-hint); font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
.task-detail-block-text { font-size: var(--font-label); color: var(--text-secondary); line-height: 1.55; margin: 0; }
.task-detail-loading { font-size: var(--font-label); color: var(--text-muted); padding-top: 8px; }

.activity-card { background: var(--violet-bg); border: 1px solid #DDD6FE; border-radius: var(--radius-md); padding: 12px 16px; margin-bottom: 6px; }
.act-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.act-row-clickable { cursor: pointer; }
.act-name { font-size: var(--font-body); font-weight: 600; color: var(--violet); display: flex; align-items: center; gap: 6px; }
.act-chevron { width: 14px; height: 14px; flex-shrink: 0; transition: transform 0.15s ease; }
.act-chevron-open { transform: rotate(90deg); }
.act-task-count { font-size: var(--font-hint); font-weight: 500; color: var(--violet-dark); opacity: 0.75; margin-left: 4px; }
.act-dates { font-size: var(--font-label); color: var(--violet-dark); }
.act-note { font-size: var(--font-label); color: var(--violet-dark); margin-top: 4px; opacity: 0.8; }
.act-actions { display: flex; gap: 8px; margin-top: 8px; }
.act-task-list { margin-top: 10px; padding-top: 10px; border-top: 1px solid #DDD6FE; display: flex; flex-direction: column; gap: 4px; }
.act-task-row { display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; background: var(--white); border-radius: 6px; cursor: pointer; }
.act-task-row:hover { box-shadow: var(--shadow-sm); }
.act-task-name { font-size: var(--font-label); color: var(--text-primary); font-weight: 500; }
.act-task-empty { margin-top: 10px; padding-top: 10px; border-top: 1px solid #DDD6FE; font-size: var(--font-label); color: var(--violet-dark); opacity: 0.7; }
.empty-section { font-size: var(--font-body); color: var(--text-muted); padding: 24px 0; text-align: center; }


/* ── SHIFT / NOTE / ACTIVITY-EDIT / PREREQ MODALS ── */
.shift-modal-body { display: flex; flex-direction: column; gap: 14px; }
.shift-mode-tabs { display: flex; gap: 6px; }
.shift-mode-tab { flex: 1; padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-light); background: var(--white); color: var(--text-secondary); font-size: var(--font-label); font-weight: 500; font-family: var(--font-main); cursor: pointer; }
.shift-mode-tab.active { background: var(--violet-bg); color: var(--violet); border-color: #DDD6FE; }
.shift-preview-box { background: var(--bg-page); border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 10px 14px; }
.shift-preview-title { font-size: var(--font-hint); font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); margin-bottom: 6px; }
.shift-preview-row { font-size: var(--font-label); color: var(--text-primary); padding: 2px 0; }
.shift-preview-warning { margin-top: 6px; font-size: var(--font-label); color: #92400E; }
.shift-scope-note { font-size: var(--font-label); color: var(--text-muted); margin: -4px 0 0; line-height: 1.5; }

.field-label { display: block; font-size: var(--font-label); font-weight: 500; color: var(--text-primary); margin-bottom: 6px; }
.field-textarea { width: 100%; padding: 9px 12px; border: 1px solid var(--border-light); border-radius: var(--radius-md); font-family: var(--font-main); font-size: var(--font-label); color: var(--text-primary); resize: vertical; box-sizing: border-box; }
.field-textarea:focus { outline: none; border-color: var(--violet); }
.modal-hint { font-size: var(--font-label); color: var(--text-muted); margin: 6px 0 14px; line-height: 1.5; }

.prereq-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--border-light); }
.prereq-row:last-child { border-bottom: none; }
.prereq-name { font-size: var(--font-label); font-weight: 500; color: var(--text-primary); }

.check-item { display: flex; align-items: center; gap: 8px; font-size: var(--font-label); color: var(--text-primary); cursor: pointer; }

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
