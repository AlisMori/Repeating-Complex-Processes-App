<!-- /frontend/src/views/TemplateCreateView.vue -->
<!-- Handles both CREATE (/templates/new) and EDIT (/templates/:id/edit) -->

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import GanttChart from '@/components/GanttChart.vue'
import { resolveEffectiveOffsets } from '@/utils/scheduling'
import {
  createTemplate, updateTemplate,
  getTemplate, getTemplateTasks, getTemplateActivities, getTaskDependencies,
  getTaskTags, getActivityTags,
  getTemplateCategories, createTemplateCategory,
  saveTemplateStructure,
  getTags, createTag,
} from '@/api/templates'
import { getErrorMessage } from '@/utils/apiErrors'

const route = useRoute()
const router = useRouter()

const isEditMode = computed(() => !!route.params.id)
const templateId = computed(() => route.params.id || null)
const pageTitle = computed(() => isEditMode.value ? 'Edit Template' : 'New Template')

// ── STEP TRACKING ─────────────────────────────────────────
const step = ref(1)
const createdTemplateId = ref(null)
const loadingInitial = ref(false)

// ── STEP 1: TEMPLATE INFO ─────────────────────────────────
const templateForm = reactive({ template_name: '', description: '', category: '' })
const categories = ref([])
const creatingCategory = ref(false)
const newCategoryName = ref('')
const categoryCreating = ref(false)

async function onCreateCategoryInline() {
  const name = newCategoryName.value.trim()
  if (!name) return
  categoryCreating.value = true
  try {
    const { data } = await createTemplateCategory({ category_name: name })
    categories.value = [...categories.value, data]
    templateForm.category = data.category_id
    creatingCategory.value = false
  } catch (e) {
    step1Error.value = getErrorMessage(e, 'Failed to create category.')
  } finally {
    categoryCreating.value = false
  }
}
const step1Loading = ref(false)
const step1Error = ref('')

async function loadExistingTemplate() {
  if (!isEditMode.value) return
  loadingInitial.value = true
  try {
    const [tplRes, tasksRes, activitiesRes, dependenciesRes, taskTagsRes, activityTagsRes] = await Promise.all([
      getTemplate(templateId.value),
      getTemplateTasks(templateId.value),
      getTemplateActivities(templateId.value),
      getTaskDependencies(),
      getTaskTags(),
      getActivityTags(),
    ])
    const tpl = tplRes.data
    templateForm.template_name = tpl.template_name
    templateForm.description = tpl.description || ''
    templateForm.category = tpl.category || ''
    createdTemplateId.value = tpl.template_id

    const taskList = Array.isArray(tasksRes.data) ? tasksRes.data : (tasksRes.data.results || [])
    const actList = Array.isArray(activitiesRes.data) ? activitiesRes.data : (activitiesRes.data.results || [])
    const allDependencies = Array.isArray(dependenciesRes.data) ? dependenciesRes.data : (dependenciesRes.data.results || [])
    const allTaskTags = Array.isArray(taskTagsRes.data) ? taskTagsRes.data : (taskTagsRes.data.results || [])
    const allActivityTags = Array.isArray(activityTagsRes.data) ? activityTagsRes.data : (activityTagsRes.data.results || [])

    // getTaskDependencies() isn't filtered server-side, so narrow it
    // down to edges where both ends belong to THIS template's tasks.
    const thisTemplateTaskIds = new Set(taskList.map(t => t.template_task_id))
    const dependsOnByTaskId = {}
    for (const dep of allDependencies) {
      if (thisTemplateTaskIds.has(dep.task) && thisTemplateTaskIds.has(dep.depends_on_task)) {
        dependsOnByTaskId[dep.task] = dep.depends_on_task
      }
    }
    const taskTagIdsByTaskId = {}
    for (const tt of allTaskTags) {
      if (thisTemplateTaskIds.has(tt.template_task)) {
        (taskTagIdsByTaskId[tt.template_task] ||= []).push(tt.tag)
      }
    }
    const thisTemplateActivityIds = new Set(actList.map(a => a.template_activity_id))
    const activityTagIdsByActivityId = {}
    for (const at of allActivityTags) {
      if (thisTemplateActivityIds.has(at.template_activity)) {
        (activityTagIdsByActivityId[at.template_activity] ||= []).push(at.tag)
      }
    }

    // Tags travel with each task/activity as plain local state now
    // (_tagIds), just like _localId — no more name-matching required
    // to carry them across a save, since the whole structure (tasks,
    // activities, tags, dependencies) is submitted together in one
    // request. Same fix for the dependency this task depends on:
    // resolved straight to a local id below, once every task's
    // _localId exists.
    tasks.value = taskList.map(t => ({
      _localId: nextLocalId(),
      _origTaskId: t.template_task_id,
      task_name: t.task_name,
      description: t.description || '',
      day_offset: t.day_offset || 0,
      duration_days: t.duration_days || 1,
      is_mandatory: t.is_mandatory || false,
      is_fixed_date: t.is_fixed_date || false,
      reminder_7: Array.isArray(t.reminder_lead_days) ? t.reminder_lead_days.includes(7) : t.reminder_lead_days === 7,
      reminder_3: Array.isArray(t.reminder_lead_days) ? t.reminder_lead_days.includes(3) : t.reminder_lead_days === 3,
      reminder_0: Array.isArray(t.reminder_lead_days) ? t.reminder_lead_days.includes(0) : t.reminder_lead_days === 0,
      note_text: t.note_text || '',
      _origActivityId: t.template_activity,
      _tagIds: taskTagIdsByTaskId[t.template_task_id] || [],
    }))

    activities.value = actList.map(a => ({
      _localId: nextLocalId(),
      activity_name: a.activity_name,
      description: a.description || '',
      start_offset_days: a.start_offset_days || 0,
      end_offset_days: a.end_offset_days || 1,
      note_text: a.note_text || '',
      _tagIds: activityTagIdsByActivityId[a.template_activity_id] || [],
      // Reconstruct which of the just-loaded tasks were grouped
      // under this activity, by matching the original backend ids.
      groupedTaskLocalIds: tasks.value
        .filter(t => t._origActivityId === a.template_activity_id)
        .map(t => t._localId),
    }))

    // Now that every task has a _localId, resolve each real
    // dependency edge to a local-id -> local-id pair.
    const localIdByTaskId = Object.fromEntries(tasks.value.map(t => [t._origTaskId, t._localId]))
    const seededDependencies = {}
    for (const t of tasks.value) {
      const dependsOnTaskId = dependsOnByTaskId[t._origTaskId]
      if (dependsOnTaskId && localIdByTaskId[dependsOnTaskId] !== undefined) {
        seededDependencies[t._localId] = localIdByTaskId[dependsOnTaskId]
      }
    }
    dependencies.value = seededDependencies
  } catch (e) {
    step1Error.value = 'Failed to load template data.'
  } finally {
    loadingInitial.value = false
  }
}

async function submitStep1() {
  if (step1Loading.value) return
  if (!templateForm.template_name.trim()) {
    step1Error.value = 'Template name is required.'
    return
  }
  step1Loading.value = true
  step1Error.value = ''
  try {
    const payload = {
      template_name: templateForm.template_name.trim(),
      description: templateForm.description.trim(),
      category: templateForm.category || null,
    }
    if (isEditMode.value) {
      const { data } = await updateTemplate(templateId.value, payload)
      // updateTemplate returns new version in data.template
      createdTemplateId.value = data.template?.template_id || templateId.value
    } else {
      const { data } = await createTemplate(payload)
      createdTemplateId.value = data.template_id
    }
    step.value = 2
  } catch (e) {
    step1Error.value = getErrorMessage(e, 'Failed to save template. Please try again.')
  } finally {
    step1Loading.value = false
  }
}

// ── STEP 2: TASKS & ACTIVITIES ────────────────────────────
const tasks = ref([])
const activities = ref([])
const step2Loading = ref(false)

// One shared tag pool for both tasks and activities, matching the
// backend design — Tag itself has no task/activity split, only the
// assignment (which task or activity it's attached to) does.
const availableTags = ref([])
const newTagName = ref('')
const newTagLoading = ref(false)
const newTagError = ref('')

async function loadTags() {
  try {
    const { data } = await getTags()
    availableTags.value = Array.isArray(data) ? data : (data.results || [])
  } catch {
    // Non-critical — tag checkboxes just won't have options if this fails.
  }
}

async function createNewTag() {
  const name = newTagName.value.trim()
  if (!name) return
  newTagLoading.value = true
  newTagError.value = ''
  try {
    const { data } = await createTag({ tag_name: name })
    availableTags.value.push(data)
    newTagName.value = ''
  } catch (e) {
    newTagError.value = e.response?.data?.tag_name?.[0] || 'Failed to create tag.'
  } finally {
    newTagLoading.value = false
  }
}

const step2Error = ref('')

// Stable per-item ids, independent of array position, so a task can
// be referenced from an activity's groupedTaskLocalIds even after
// other tasks are added/removed/reordered.
let localIdCounter = 0
function nextLocalId() { return ++localIdCounter }

function buildReminderArray(task) {
  const arr = []
  if (task.reminder_7) arr.push(7)
  if (task.reminder_3) arr.push(3)
  if (task.reminder_0) arr.push(0)
  return arr.length > 0 ? arr : null
}

function addTask() {
  tasks.value.push({
    _localId: nextLocalId(),
    task_name: '', description: '',
    day_offset: tasks.value.length === 0 ? 0 : Math.max(...tasks.value.map(t => Number(t.day_offset))) + 1,
    duration_days: 1, is_mandatory: false, is_fixed_date: false,
    reminder_7: false, reminder_3: false, reminder_0: false, note_text: '',
    _tagIds: [],
  })
}

function removeTask(index) {
  const removed = tasks.value[index]
  tasks.value.splice(index, 1)
  // A removed task can't stay grouped under any activity.
  for (const act of activities.value) {
    act.groupedTaskLocalIds = act.groupedTaskLocalIds.filter(id => id !== removed._localId)
  }
}

function addActivity() {
  activities.value.push({
    _localId: nextLocalId(),
    activity_name: '', description: '',
    start_offset_days: 0,
    end_offset_days: activities.value.length === 0 ? 30 : Math.max(...activities.value.map(a => Number(a.end_offset_days))) + 10,
    note_text: '',
    _tagIds: [],
    groupedTaskLocalIds: [],
  })
}

function removeActivity(index) { activities.value.splice(index, 1) }

function toggleTaskInActivity(activity, taskLocalId) {
  const idx = activity.groupedTaskLocalIds.indexOf(taskLocalId)
  if (idx === -1) {
    activity.groupedTaskLocalIds.push(taskLocalId)
  } else {
    activity.groupedTaskLocalIds.splice(idx, 1)
  }
}

// Which activity (if any) a task is currently grouped under — used
// to stop the same task being picked under a second activity too,
// since the backend only allows one activity per task.
function activityForTask(taskLocalId) {
  return activities.value.find(act => act.groupedTaskLocalIds.includes(taskLocalId))
}

// Mirrors validate_activity_bounds on the backend: a task can only
// be grouped under an activity if its own [start, end] falls
// entirely inside the activity's date range — offering a task that
// doesn't fit as a checkable option just guarantees a rejection at
// submit time, so it's filtered out of the list before that.
function taskFitsActivity(task, act) {
  const start = Number(task.day_offset)
  const end = start + Number(task.duration_days || 1)
  return start >= Number(act.start_offset_days) && end <= Number(act.end_offset_days)
}

async function submitStep2() {
  // Synchronous guard against a double-click firing this twice.
  if (step2Loading.value) return

  for (const task of tasks.value) {
    if (!task.task_name.trim()) { step2Error.value = 'All tasks must have a name.'; return }
    if (Number(task.day_offset) < 0) { step2Error.value = 'Day offset cannot be negative.'; return }
  }
  for (const act of activities.value) {
    if (!act.activity_name.trim()) { step2Error.value = 'All activities must have a name.'; return }
    if (Number(act.start_offset_days) < 0) { step2Error.value = `Activity "${act.activity_name}" start day cannot be negative.`; return }
    if (Number(act.end_offset_days) <= Number(act.start_offset_days)) {
      step2Error.value = `Activity "${act.activity_name}" end day must be after start day.`; return
    }
  }
  // A task grouped under an activity must fall entirely inside that
  // activity's date range — the backend enforces this too, checking
  // here first gives an immediate answer instead of waiting for the
  // final save to reject it.
  for (const act of activities.value) {
    for (const localId of act.groupedTaskLocalIds) {
      const task = tasks.value.find(t => t._localId === localId)
      if (!task) continue
      const start = Number(task.day_offset)
      const end = start + Number(task.duration_days || 1)
      if (start < Number(act.start_offset_days) || end > Number(act.end_offset_days)) {
        step2Error.value = `Task "${task.task_name}" (Day ${start}\u2013${end}) doesn't fit inside `
          + `"${act.activity_name}"'s range (Day ${act.start_offset_days}\u2013${act.end_offset_days}). `
          + `Widen the activity or adjust the task's dates.`
        return
      }
    }
  }

  step2Error.value = ''

  // Nothing gets written to the backend here anymore — the whole
  // structure (tasks, activities, tags, dependencies) is saved once,
  // atomically, when step 3 is submitted. This step is now purely
  // local validation, so it's instant and can never leave a partial
  // save behind. A task's own date can change here in ways that
  // break an existing dependency (an offset conflict, or the
  // dependent no longer existing) — instead of silently dropping
  // that dependency, surface it and let the user choose per-item
  // rather than losing the relationship without being told.
  const broken = Object.keys(dependencies.value)
    .filter(localId => !dependencyIsStillValid(localId, dependencies.value[localId]))
    .map(localId => {
      const task = tasks.value.find(t => String(t._localId) === String(localId))
      const dep = tasks.value.find(t => String(t._localId) === String(dependencies.value[localId]))
      return { taskLocalId: localId, task, dep }
    })
    .filter(item => item.task && item.dep)

  if (broken.length > 0) {
    depConflictModal.value = { open: true, items: broken }
    return
  }

  step.value = 3
}

const depConflictModal = ref({ open: false, items: [] })

// Which task rows currently show the "change dependency" dropdown —
// a task with an existing dependency shows it as plain text by
// default (see the step 3 template), only revealing the dropdown of
// allowed alternatives once the user actually asks to change it.
const editingDepFor = reactive(new Set())
function stopEditingDep(localId) {
  editingDepFor.delete(localId)
}

function resolveDependencyConflict(item, action) {
  if (action === 'remove') {
    const next = { ...dependencies.value }
    delete next[item.taskLocalId]
    dependencies.value = next
  } else if (action === 'shift') {
    // Move the dependent task to start right after its prerequisite
    // ends, preserving its own duration — same "shift downstream"
    // idea the cycle Gantt uses, just applied while still editing
    // the template instead of after a cycle exists.
    const task = tasks.value.find(t => t._localId === item.task._localId)
    if (task) {
      task.day_offset = Number(item.dep.day_offset) + Number(item.dep.duration_days || 1)
    }
  }
  depConflictModal.value = {
    open: depConflictModal.value.items.length > 1,
    items: depConflictModal.value.items.filter(i => i.taskLocalId !== item.taskLocalId),
  }
  if (depConflictModal.value.items.length === 0) {
    step.value = 3
  }
}

function skipToStep3() {
  step.value = 3
}

// ── STEP 3: DEPENDENCIES ──────────────────────────────────
// localId -> dependsOnLocalId | undefined. Purely local state until
// the final save — nothing here touches the backend, so every check
// below is a client-side mirror of the same rules bulk_structure.py
// enforces server-side (circular chains, the 2-dependent fan-out
// cap, and the offset conflict rule), kept close enough to those
// that nothing offered here could ever fail the real save.
const dependencies = ref({})
const step3Loading = ref(false)
const step3Error = ref('')

// Mirrors would_create_cycle on the backend: true if making
// `taskLocalId` depend on `candidateLocalId` would close a loop,
// walking forward through everything that (transitively) already
// depends on taskLocalId.
function wouldCreateCycle(taskLocalId, candidateLocalId, visited = new Set()) {
  if (taskLocalId === candidateLocalId) return true
  for (const [localId, dep] of Object.entries(dependencies.value)) {
    if (dep !== taskLocalId) continue
    if (localId === candidateLocalId) return true
    if (!visited.has(localId)) {
      visited.add(localId)
      if (wouldCreateCycle(localId, candidateLocalId, visited)) return true
    }
  }
  return false
}

function dependentCount(localId) {
  return Object.values(dependencies.value).filter(d => d === localId).length
}

function offsetConflict(taskLocalId, candidateLocalId) {
  const task = tasks.value.find(t => String(t._localId) === String(taskLocalId))
  const candidate = tasks.value.find(t => String(t._localId) === String(candidateLocalId))
  if (!task || !candidate) return true
  const upstreamEnd = Number(candidate.day_offset) + Number(candidate.duration_days || 1)
  return Number(task.day_offset) < upstreamEnd
}

function dependencyIsStillValid(taskLocalId, candidateLocalId) {
  if (!candidateLocalId) return false
  const task = tasks.value.find(t => String(t._localId) === String(taskLocalId))
  const candidate = tasks.value.find(t => String(t._localId) === String(candidateLocalId))
  if (!task || !candidate) return false
  if (offsetConflict(taskLocalId, candidateLocalId)) return false
  if (dependentCount(candidateLocalId) > 2 && dependencies.value[taskLocalId] !== candidateLocalId) return false
  return true
}

// Every other task, minus anything that would create a circular
// chain or an offset conflict given current dates — exactly what the
// backend would accept, computed locally so there's no round trip.
function dependencyOptions(taskLocalId) {
  return tasks.value.filter(t =>
    t._localId !== taskLocalId
    && !wouldCreateCycle(taskLocalId, t._localId)
    && !offsetConflict(taskLocalId, t._localId)
  )
}

function onDependencyPicked(taskLocalId, value) {
  if (value) {
    dependencies.value = { ...dependencies.value, [taskLocalId]: value }
  } else {
    const next = { ...dependencies.value }
    delete next[taskLocalId]
    dependencies.value = next
  }
}

async function submitStep3() {
  if (step3Loading.value) return
  step3Loading.value = true
  step3Error.value = ''
  try {
    const payload = {
      activities: activities.value.map(a => ({
        local_id: String(a._localId),
        activity_name: a.activity_name.trim(),
        description: a.description.trim(),
        start_offset_days: Number(a.start_offset_days),
        end_offset_days: Number(a.end_offset_days),
        note_text: a.note_text.trim(),
        tag_ids: a._tagIds || [],
      })),
      tasks: tasks.value.map(t => {
        const parentActivity = activityForTask(t._localId)
        return {
          local_id: String(t._localId),
          task_name: t.task_name.trim(),
          description: t.description.trim(),
          day_offset: Number(t.day_offset),
          duration_days: Number(t.duration_days),
          is_mandatory: t.is_mandatory,
          is_fixed_date: t.is_fixed_date,
          reminder_lead_days: buildReminderArray(t),
          note_text: t.note_text.trim(),
          activity_local_id: parentActivity ? String(parentActivity._localId) : null,
          tag_ids: t._tagIds || [],
        }
      }),
      dependencies: Object.entries(dependencies.value)
        .filter(([, dep]) => dep)
        .map(([taskLocalId, dep]) => ({ task_local_id: String(taskLocalId), depends_on_local_id: String(dep) })),
    }

    const { data } = await saveTemplateStructure(createdTemplateId.value, payload)
    createdTemplateId.value = data.new_template_version.template_id

    if (isEditMode.value) {
      router.push({ name: 'template-detail', params: { id: createdTemplateId.value } })
    } else {
      router.push({ name: 'templates' })
    }
  } catch (e) {
    const errors = e?.response?.data?.errors
    step3Error.value = Array.isArray(errors) && errors.length > 0
      ? errors.map(err => err.message).join(' ')
      : getErrorMessage(e, 'Failed to save template. Please try again.')
  } finally {
    step3Loading.value = false
  }
}

function skipDependencies() {
  dependencies.value = {}
  submitStep3()
}

// ── GANTT PREVIEW ─────────────────────────────────────────
// Uses the same resolveEffectiveOffsets algorithm the backend runs
// (see backend/templates_mgmt/scheduling.py) so this live, unsaved
// preview always agrees with what create_cycle will actually
// produce once things are saved. This is only needed here because
// nothing is saved to the backend until the final submit on step 3 —
// once a template is saved, TemplateDetailView.vue fetches this same
// computation from the backend instead of duplicating it.
function buildGantt(taskList, actList, depByLocalId = {}) {
  if (taskList.length === 0 && actList.length === 0) return null

  const localIdToIdx = Object.fromEntries(taskList.map((t, i) => [t._localId, i]))
  const nodes = {}
  taskList.forEach((t, i) => {
    nodes[i] = {
      offset: Number(t.day_offset),
      duration: Number(t.duration_days || 1),
      fixed: !!t.is_fixed_date,
    }
  })

  const edges = {}
  taskList.forEach((t, i) => {
    const depLocalId = depByLocalId[t._localId]
    if (depLocalId !== undefined && localIdToIdx[depLocalId] !== undefined) {
      edges[i] = [localIdToIdx[depLocalId]]
    }
  })

  const { effective } = resolveEffectiveOffsets(nodes, edges)

  // Topological-ish sort for display — independent tasks first,
  // then tasks that depend on them, so the timeline reads top-down.
  const sorted = [...taskList.map((t, i) => ({ ...t, _origIdx: i }))]
  sorted.sort((a, b) => {
    const aHasDep = edges[a._origIdx] !== undefined
    const bHasDep = edges[b._origIdx] !== undefined
    if (!aHasDep && bHasDep) return -1
    if (aHasDep && !bHasDep) return 1
    return 0
  })

  const taskBars = sorted.map(t => {
    const [effStart, effEnd] = effective[t._origIdx]
    const depOrigIdx = edges[t._origIdx]?.[0]
    const hasDep = depOrigIdx !== undefined
    const dependsOnIndex = hasDep ? sorted.findIndex(s => s._origIdx === depOrigIdx) : null
    const depTask = hasDep ? taskList[depOrigIdx] : null
    return {
      name: t.task_name || '(unnamed)',
      start: effStart,
      end: effEnd,
      isMandatory: t.is_mandatory,
      isFixed: t.is_fixed_date,
      depName: depTask ? depTask.task_name : null,
      dependsOnIndex: dependsOnIndex !== -1 ? dependsOnIndex : null,
    }
  })

  const activityBars = actList.map(a => ({
    name: a.activity_name || '(unnamed)',
    start: Number(a.start_offset_days),
    end: Number(a.end_offset_days),
  }))

  const allEnds = [
    ...taskBars.map(b => b.end),
    ...activityBars.map(b => b.end),
  ]
  const maxDay = Math.max(...allEnds, 1)

  return { taskBars, activityBars, maxDay }
}

const step2Preview = computed(() => buildGantt(tasks.value, activities.value, {}))
const step3Preview = computed(() => buildGantt(tasks.value, activities.value, dependencies.value))

onMounted(async () => {
  try {
    const { data } = await getTemplateCategories()
    categories.value = Array.isArray(data) ? data : (data.results || [])
  } catch {
    categories.value = []
  }
  await loadTags()
  await loadExistingTemplate()
})
</script>

<template>
  <AppLayout>
    <template #topbar>
      <div class="breadcrumb">
        <span class="breadcrumb-link" @click="router.push({ name: 'templates' })">Templates</span>
        <span class="breadcrumb-sep">›</span>
        <span v-if="isEditMode" class="breadcrumb-link" @click="router.push({ name: 'template-detail', params: { id: templateId } })">{{ templateForm.template_name || 'Template' }}</span>
        <span v-if="isEditMode" class="breadcrumb-sep">›</span>
        <span class="breadcrumb-current">{{ isEditMode ? 'Edit' : 'New Template' }}</span>
      </div>
    </template>

    <div class="create-page">

      <div v-if="loadingInitial" class="loading-msg">Loading template data...</div>

      <template v-else>

        <!-- STEP INDICATOR -->
        <div class="steps-bar">
          <div class="step-item" :class="{ active: step === 1, done: step > 1 }">
            <div class="step-circle">
              <svg v-if="step > 1" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              <span v-else>1</span>
            </div>
            <span class="step-label">Template details</span>
          </div>
          <div class="step-connector" :class="{ done: step > 1 }"></div>
          <div class="step-item" :class="{ active: step === 2, done: step > 2 }">
            <div class="step-circle">
              <svg v-if="step > 2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              <span v-else>2</span>
            </div>
            <span class="step-label">Tasks & Activities</span>
          </div>
          <div class="step-connector" :class="{ done: step > 2 }"></div>
          <div class="step-item" :class="{ active: step === 3 }">
            <div class="step-circle"><span>3</span></div>
            <span class="step-label">Dependencies</span>
          </div>
        </div>

        <!-- ── STEP 1 ── -->
        <div v-if="step === 1" class="form-card">
          <div class="form-card-header">
            <div class="form-card-title">Template details</div>
            <div class="form-card-desc">Give your template a clear name so it's easy to find and reuse later.</div>
          </div>
          <div class="form-body">
            <div class="field">
              <BaseInput v-model="templateForm.template_name" label="Template name *" placeholder="e.g. Unit Coordination Template" />
            </div>
            <div class="field">
              <label class="field-label">Description</label>
              <textarea v-model="templateForm.description" class="field-textarea" placeholder="Briefly describe what this template is for..." rows="3"></textarea>
            </div>
            <div class="field">
              <BaseSelect
                v-model="templateForm.category"
                label="Category"
                hint="Optional — helps group and filter templates in the library."
                @update:model-value="(v) => { if (v === '__new__') { creatingCategory = true; templateForm.category = ''; newCategoryName = '' } }"
              >
                <option value="">Uncategorised</option>
                <option v-for="c in categories" :key="c.category_id" :value="c.category_id">{{ c.category_name }}</option>
                <option value="__new__">+ Create new category…</option>
              </BaseSelect>
              <div v-if="creatingCategory" class="inline-category-create">
                <BaseInput v-model="newCategoryName" placeholder="New category name" @keyup.enter="onCreateCategoryInline" />
                <BaseButton variant="secondary" size="sm" :loading="categoryCreating" @click="onCreateCategoryInline">Create</BaseButton>
                <BaseButton variant="secondary" size="sm" :disabled="categoryCreating" @click="creatingCategory = false">Cancel</BaseButton>
              </div>
            </div>
            <div v-if="step1Error" class="error-banner">{{ step1Error }}</div>
          </div>
          <div class="form-footer">
            <BaseButton variant="secondary" size="sm" @click="router.push({ name: 'templates' })">Cancel</BaseButton>
            <BaseButton variant="primary" size="sm" :loading="step1Loading" @click="submitStep1">Continue →</BaseButton>
          </div>
        </div>

        <!-- ── STEP 2 ── -->
        <div v-if="step === 2" class="two-panel">
          <div class="panel-left">
	    <!-- ACTIVITIES (created first, so tasks below can link to one) -->
            <div class="form-card">
              <div class="form-card-header">
                <div>
                  <div class="form-card-title">Activities</div>
                  <div class="form-card-desc">Non-actionable spans that group a period. E.g. "Teaching the unit" spanning the whole semester. Create these first so tasks below can be linked to one.</div>
                </div>
                <BaseButton variant="secondary" size="sm" @click="addActivity">+ Add activity</BaseButton>
              </div>
              <div class="form-body">
                <div v-if="activities.length === 0" class="empty-section">No activities yet — click "Add activity" to start.</div>
                <div v-for="(act, idx) in activities" :key="act._localId" class="item-card">
                  <div class="item-card-header">
                    <span class="item-number">Activity {{ idx + 1 }}</span>
                    <button class="remove-btn" @click="removeActivity(idx)">✕ Remove</button>
                  </div>
                  <div class="item-grid">
                    <div class="field"><BaseInput v-model="act.activity_name" label="Activity name *" placeholder="e.g. Teaching the unit" /></div>
                    <div class="field"><BaseInput v-model="act.description" label="Description" placeholder="Optional" /></div>
                  </div>
                  <div class="item-grid two-col">
                    <div class="field">
                      <BaseInput
                        v-model="act.start_offset_days"
                        label="Start day *"
                        type="number"
                        min="0"
                        placeholder="0"
                        hint="Days from cycle start"
                      />
                    </div>
                    <div class="field">
                      <BaseInput
                        v-model="act.end_offset_days"
                        label="End day *"
                        type="number"
                        min="0"
                        placeholder="1"
                        hint="Must be after start day"
                      />
                    </div>
                  </div>
                  <div class="tag-section">
                    <label class="field-label">Tags</label>
                    <div v-if="availableTags.length === 0" class="tag-empty-hint">No tags yet — create one below.</div>
                    <div v-else class="tag-checks">
                      <label v-for="tag in availableTags" :key="tag.tag_id" class="check-item tag-check-item">
                        <input type="checkbox" :value="tag.tag_id" v-model="act._tagIds" />
                        <span>{{ tag.tag_name }}</span>
                      </label>
                    </div>
                    <div class="tag-create-row">
                      <input
                        v-model="newTagName"
                        type="text"
                        class="tag-create-input"
                        placeholder="New tag name"
                        @keyup.enter="createNewTag"
                      />
                      <button type="button" class="tag-create-btn" :disabled="newTagLoading" @click="createNewTag">+ Add tag</button>
                    </div>
                    <div v-if="newTagError" class="tag-create-error">{{ newTagError }}</div>
                  </div>
                  <div v-if="tasks.length > 0" class="activity-task-group">
                    <div class="field-label">Group tasks under this activity</div>
                    <div class="field-hint">Only tasks that fit inside the date range above are shown. A task can only belong to one activity.</div>
                    <div class="task-group-list">
                      <label
                        v-for="task in tasks.filter(t => taskFitsActivity(t, act) || act.groupedTaskLocalIds.includes(t._localId))"
                        :key="task._localId"
                        class="check-item task-group-item"
                        :class="{ 'task-group-item-disabled': activityForTask(task._localId) && activityForTask(task._localId) !== act }"
                      >
                        <input
                          type="checkbox"
                          :checked="act.groupedTaskLocalIds.includes(task._localId)"
                          :disabled="!!activityForTask(task._localId) && activityForTask(task._localId) !== act"
                          @change="toggleTaskInActivity(act, task._localId)"
                        />
                        <span>
                          {{ task.task_name || '(unnamed task)' }} <span class="task-group-day">Day {{ task.day_offset }}–{{ Number(task.day_offset) + Number(task.duration_days || 1) }}</span>
                          <span v-if="act.groupedTaskLocalIds.includes(task._localId) && !taskFitsActivity(task, act)" class="task-group-warning">no longer fits — resize the activity or uncheck</span>
                        </span>
                      </label>
                      <div v-if="tasks.filter(t => taskFitsActivity(t, act) || act.groupedTaskLocalIds.includes(t._localId)).length === 0" class="task-group-empty">
                        No tasks currently fit inside this activity's date range.
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- TASKS -->
            <div class="form-card">
              <div class="form-card-header">
                <div>
                  <div class="form-card-title">Tasks</div>
                  <div class="form-card-desc">Actionable events. "Days from cycle start" means Day 0 = first day of the cycle.</div>
                </div>
                <BaseButton variant="secondary" size="sm" @click="addTask">+ Add task</BaseButton>
              </div>
              <div class="form-body">
                <div v-if="tasks.length === 0" class="empty-section">No tasks yet — click "Add task" to start.</div>
                <div v-for="(task, idx) in tasks" :key="task._localId" class="item-card">
                  <div class="item-card-header">
                    <span class="item-number">Task {{ idx + 1 }}</span>
                    <button class="remove-btn" @click="removeTask(idx)">✕ Remove</button>
                  </div>
                  <div class="item-grid">
                    <div class="field"><BaseInput v-model="task.task_name" label="Task name *" placeholder="e.g. Submit exam paper" /></div>
                    <div class="field"><BaseInput v-model="task.description" label="Description" placeholder="Optional" /></div>
                  </div>
                  <div class="item-grid three-col">
                    <div class="field">
                      <BaseInput
                        v-model="task.day_offset"
                        label="Days from cycle start *"
                        type="number"
                        min="0"
                        placeholder="0"
                        hint="0 = first day of the cycle"
                      />
                    </div>
                    <div class="field">
                      <BaseInput
                        v-model="task.duration_days"
                        label="Duration (days)"
                        type="number"
                        placeholder="1"
                        :hint="`Spans day ${Number(task.day_offset || 0)} through day ${Number(task.day_offset || 0) + Number(task.duration_days || 1)}`"
                      />
                    </div>
                    <div class="field">
                      <label class="field-label">Email reminders</label>
                      <div class="field-hint">Send reminder before task is due</div>
                      <div class="reminder-checks">
                        <label class="check-item"><input type="checkbox" v-model="task.reminder_7" /><span>7 days before</span></label>
                        <label class="check-item"><input type="checkbox" v-model="task.reminder_3" /><span>3 days before</span></label>
                        <label class="check-item"><input type="checkbox" v-model="task.reminder_0" /><span>On the day</span></label>
                      </div>
                    </div>
                  </div>
                  <div class="item-checks">
                    <label class="check-item"><input type="checkbox" v-model="task.is_mandatory" /><span>Mandatory task</span></label>
                    <label class="check-item"><input type="checkbox" v-model="task.is_fixed_date" /><span>Fixed end date (cannot be shifted by delays)</span></label>
                  </div>
                  <div class="tag-section">
                    <label class="field-label">Tags</label>
                    <div v-if="availableTags.length === 0" class="tag-empty-hint">No tags yet — create one below.</div>
                    <div v-else class="tag-checks">
                      <label v-for="tag in availableTags" :key="tag.tag_id" class="check-item tag-check-item">
                        <input type="checkbox" :value="tag.tag_id" v-model="task._tagIds" />
                        <span>{{ tag.tag_name }}</span>
                      </label>
                    </div>
                    <div class="tag-create-row">
                      <input
                        v-model="newTagName"
                        type="text"
                        class="tag-create-input"
                        placeholder="New tag name"
                        @keyup.enter="createNewTag"
                      />
                      <button type="button" class="tag-create-btn" :disabled="newTagLoading" @click="createNewTag">+ Add tag</button>
                    </div>
                    <div v-if="newTagError" class="tag-create-error">{{ newTagError }}</div>
                  </div>
                </div>
              </div>
            </div>
                
            <!-- ACTIVITIES -->
            <div class="form-card">
              <div class="form-card-header">
                <div>
                  <div class="form-card-title">Activities</div>
                  <div class="form-card-desc">Non-actionable spans that group a period. E.g. "Teaching the unit" spanning the whole semester.</div>
                </div>
                <BaseButton variant="secondary" size="sm" @click="addActivity">+ Add activity</BaseButton>
              </div>
              <div class="form-body">
                <div v-if="activities.length === 0" class="empty-section">No activities yet — click "Add activity" to start.</div>
                <div v-for="(act, idx) in activities" :key="act._localId" class="item-card">
                  <div class="item-card-header">
                    <span class="item-number">Activity {{ idx + 1 }}</span>
                    <button class="remove-btn" @click="removeActivity(idx)">✕ Remove</button>
                  </div>
                  <div class="item-grid">
                    <div class="field"><BaseInput v-model="act.activity_name" label="Activity name *" placeholder="e.g. Teaching the unit" /></div>
                    <div class="field"><BaseInput v-model="act.description" label="Description" placeholder="Optional" /></div>
                  </div>
                  <div class="item-grid two-col">
                    <div class="field">
                      <BaseInput
                        v-model="act.start_offset_days"
                        label="Start day *"
                        type="number"
                        placeholder="0"
                        hint="Days from cycle start"
                      />
                    </div>
                    <div class="tag-create-row">
                      <input
                        v-model="newTaskTagName"
                        type="text"
                        class="tag-create-input"
                        placeholder="New task tag name"
                        @keyup.enter="createNewTaskTag"
                      />
                      <button type="button" class="tag-create-btn" :disabled="newTaskTagLoading" @click="createNewTaskTag">+ Add tag</button>
                    </div>
                    <div v-if="newTaskTagError" class="tag-create-error">{{ newTaskTagError }}</div>
                  </div>

                  <div v-if="tasks.length > 0" class="activity-task-group">
                    <div class="field-label">Group tasks under this activity</div>
                    <div class="field-hint">Only tasks that fit inside the date range above are shown. A task can only belong to one activity.</div>
                    <div class="task-group-list">
                      <label
                        v-for="task in tasks.filter(t => taskFitsActivity(t, act) || act.groupedTaskLocalIds.includes(t._localId))"
                        :key="task._localId"
                        class="check-item task-group-item"
                        :class="{ 'task-group-item-disabled': activityForTask(task._localId) && activityForTask(task._localId) !== act }"
                      >
                        <input
                          type="checkbox"
                          :checked="act.groupedTaskLocalIds.includes(task._localId)"
                          :disabled="!!activityForTask(task._localId) && activityForTask(task._localId) !== act"
                          @change="toggleTaskInActivity(act, task._localId)"
                        />
                        <span>
                          {{ task.task_name || '(unnamed task)' }} <span class="task-group-day">Day {{ task.day_offset }}–{{ Number(task.day_offset) + Number(task.duration_days || 1) }}</span>
                          <span v-if="act.groupedTaskLocalIds.includes(task._localId) && !taskFitsActivity(task, act)" class="task-group-warning">no longer fits — resize the activity or uncheck</span>
                        </span>
                      </label>
                      <div v-if="tasks.filter(t => taskFitsActivity(t, act) || act.groupedTaskLocalIds.includes(t._localId)).length === 0" class="task-group-empty">
                        No tasks currently fit inside this activity's date range.
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="step2Error" class="error-banner">{{ step2Error }}</div>
            <div class="form-footer">
              <BaseButton variant="secondary" size="sm" @click="skipToStep3">Skip — finish without tasks</BaseButton>
              <BaseButton variant="primary" size="sm" :loading="step2Loading" @click="submitStep2">Save & set dependencies →</BaseButton>
            </div>
          </div>

          <!-- GANTT PREVIEW -->
          <div class="panel-right">
            <div class="gantt-header">Timeline preview</div>
            <div v-if="!step2Preview" class="gantt-empty">Add tasks and activities to see the timeline.</div>
            <GanttChart
              v-else
              :task-bars="step2Preview.taskBars"
              :activity-bars="step2Preview.activityBars"
              :max-day="step2Preview.maxDay"
            />
          </div>
        </div>

        <!-- ── STEP 3 ── -->
        <div v-if="step === 3" class="two-panel">
          <div class="panel-left">
            <div class="form-card">
              <div class="form-card-header">
                <div>
                  <div class="form-card-title">Task dependencies</div>
                  <div class="form-card-desc">Set which task each task depends on. When a dependency is delayed, all downstream tasks shift automatically.</div>
                </div>
              </div>
              <div class="form-body">
                <div v-if="tasks.length === 0" class="empty-section">No tasks were added — skip to finish.</div>
                <div v-for="(task, idx) in tasks" :key="task._localId" class="dep-row">
                  <div class="dep-task-name">
                    <div class="dep-badge">{{ idx + 1 }}</div>
                    <span>{{ task.task_name || '(unnamed)' }}</span>
                    <span v-if="task.is_mandatory" class="chip chip-mandatory">MANDATORY</span>
                    <span v-if="task.is_fixed_date" class="chip chip-fixed">FIXED DATE</span>
                  </div>
                  <div class="dep-select-row" v-if="!dependencies[task._localId] || editingDepFor.has(task._localId)">
                    <span class="dep-label">Depends on:</span>
                    <BaseSelect
                      :model-value="dependencies[task._localId] || null"
                      class="dep-select"
                      @update:model-value="(v) => { onDependencyPicked(task._localId, v); stopEditingDep(task._localId) }"
                    >
                      <option :value="null">— No dependency</option>
                      <option
                        v-for="opt in dependencyOptions(task._localId)"
                        :key="opt._localId"
                        :value="opt._localId"
                        :disabled="dependentCount(opt._localId) >= 2 && dependencies[task._localId] !== opt._localId"
                      >
                        {{ opt.task_name || '(unnamed)' }} (Day {{ opt.day_offset }}) · {{ dependentCount(opt._localId) }}/2 tasks depend on it
                      </option>
                    </BaseSelect>
                    <BaseButton v-if="editingDepFor.has(task._localId)" variant="secondary" size="sm" @click="stopEditingDep(task._localId)">Cancel</BaseButton>
                  </div>
                  <div class="dep-select-row" v-else>
                    <span class="dep-label">Depends on:</span>
                    <span class="dep-current-value">{{ tasks.find(t => t._localId === dependencies[task._localId])?.task_name || '(unknown task)' }}</span>
                    <BaseButton variant="secondary" size="sm" @click="editingDepFor.add(task._localId)">Change</BaseButton>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="step3Error" class="error-banner">{{ step3Error }}</div>
            <div class="form-footer form-footer-split">
              <BaseButton variant="secondary" size="sm" @click="step = 2">← Back to Tasks &amp; Activities</BaseButton>
              <div class="form-footer-right">
                <BaseButton variant="secondary" size="sm" :loading="step3Loading" @click="skipDependencies">Skip — no dependencies</BaseButton>
                <BaseButton variant="primary" size="sm" :loading="step3Loading" @click="submitStep3">Save template</BaseButton>
              </div>
            </div>
          </div>

          <!-- GANTT PREVIEW step 3 -->
          <div class="panel-right">
            <div class="gantt-header">Timeline preview</div>
            <div v-if="!step3Preview" class="gantt-empty">No tasks to display.</div>
            <GanttChart
              v-else
              :task-bars="step3Preview.taskBars"
              :activity-bars="step3Preview.activityBars"
              :max-day="step3Preview.maxDay"
            />
          </div>
        </div>

      </template>
    </div>

    <!-- DEPENDENCY CONFLICT MODAL: a task's own date change broke an
         existing dependency (offset conflict) — remove it, or shift
         the dependent task to right after its prerequisite instead
         of silently losing the relationship. -->
    <BaseModal
      v-model="depConflictModal.open"
      title="This date change breaks a dependency"
      :closable="false"
      confirm-label=""
    >
      <div v-for="item in depConflictModal.items" :key="item.taskLocalId" class="dep-conflict-item">
        <p class="dep-conflict-text">
          <strong>{{ item.task.task_name }}</strong> depends on <strong>{{ item.dep.task_name }}</strong>,
          but with its current dates it no longer starts after
          <strong>{{ item.dep.task_name }}</strong> (day {{ item.dep.day_offset }}–{{ Number(item.dep.day_offset) + Number(item.dep.duration_days || 1) }}) finishes.
        </p>
        <div class="dep-conflict-actions">
          <BaseButton variant="secondary" size="sm" @click="resolveDependencyConflict(item, 'remove')">Remove dependency</BaseButton>
          <BaseButton variant="primary" size="sm" @click="resolveDependencyConflict(item, 'shift')">
            Shift "{{ item.task.task_name }}" to day {{ Number(item.dep.day_offset) + Number(item.dep.duration_days || 1) }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>
  </AppLayout>
</template>

<style scoped>
.breadcrumb { display: flex; align-items: center; gap: 6px; font-size: var(--font-label); }
.breadcrumb-link { color: var(--text-muted); cursor: pointer; }
.breadcrumb-link:hover { color: var(--violet); }
.breadcrumb-sep { color: var(--text-muted); }
.breadcrumb-current { color: var(--text-primary); font-weight: 500; }
.loading-msg { font-size: var(--font-label); color: var(--text-muted); padding: 40px 0; }
.create-page { display: flex; flex-direction: column; gap: 20px; }

/* STEPS BAR */
.steps-bar { display: flex; align-items: center; }
.step-item { display: flex; align-items: center; gap: 10px; }
.step-circle { width: 30px; height: 30px; border-radius: 50%; border: 2px solid var(--border-light); background: var(--white); display: flex; align-items: center; justify-content: center; font-size: var(--font-label); font-weight: 600; color: var(--text-muted); flex-shrink: 0; transition: all 0.2s; }
.step-circle svg { width: 14px; height: 14px; }
.step-item.active .step-circle { border-color: var(--violet); background: var(--violet); color: white; }
.step-item.done .step-circle { border-color: var(--success); background: var(--success); color: white; }
.step-label { font-size: var(--font-label); color: var(--text-muted); }
.step-item.active .step-label { color: var(--text-primary); font-weight: 500; }
.step-item.done .step-label { color: var(--success); }
.step-connector { flex: 0 0 40px; height: 1px; background: var(--border-light); margin: 0 12px; transition: background 0.2s; }
.step-connector.done { background: var(--success); }

/* TWO PANEL */
.two-panel { display: flex; gap: 20px; align-items: flex-start; }
.panel-left { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 16px; }
.panel-right { width: 380px; flex-shrink: 0; background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); overflow: hidden; position: sticky; top: 80px; }

/* FORM CARD */
.form-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); overflow: hidden; }
.form-card-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--border-light); gap: 16px; }
.form-card-title { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); margin-bottom: 3px; }
.form-card-desc { font-size: var(--font-label); color: var(--text-muted); line-height: 1.5; max-width: 420px; }
.form-body { padding: 16px 20px; display: flex; flex-direction: column; gap: 14px; }
.form-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 14px 20px; border-top: 1px solid var(--border-light); background: var(--white); }
.form-footer-split { justify-content: space-between; }
.form-footer-right { display: flex; gap: 10px; }

/* FIELDS */
.field { display: flex; flex-direction: column; gap: 5px; }
.field-label { font-size: var(--font-label); font-weight: 500; color: var(--text-primary); }
.inline-category-create { display: flex; align-items: flex-end; gap: 8px; margin-top: 10px; }
.inline-category-create :deep(.base-input-group) { flex: 1; margin-bottom: 0; }
.field-hint { font-size: var(--font-upper); color: var(--text-muted); }
.field-input { height: 40px; padding: 0 12px; border: 1px solid var(--border); border-radius: var(--radius-md); font-size: var(--font-label); font-family: var(--font-main); background: #FAFAFA; color: var(--text-primary); outline: none; width: 100%; }
.field-input:focus { border-color: var(--violet); background: var(--white); }
.field-textarea { padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius-md); font-size: var(--font-label); font-family: var(--font-main); background: #FAFAFA; color: var(--text-primary); outline: none; width: 100%; resize: vertical; line-height: 1.5; }
.field-textarea:focus { border-color: var(--violet); background: var(--white); }

/* REMINDER CHECKBOXES */
.reminder-checks { display: flex; flex-direction: column; gap: 6px; margin-top: 2px; }

/* ITEM CARDS */
.item-card { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 16px; background: var(--bg-page); display: flex; flex-direction: column; gap: 12px; }
.item-card-header { display: flex; align-items: center; justify-content: space-between; }
.item-number { font-size: var(--font-upper); font-weight: 600; color: var(--violet); text-transform: uppercase; letter-spacing: 0.05em; }
.remove-btn { background: none; border: none; font-size: var(--font-label); color: var(--text-muted); cursor: pointer; font-family: var(--font-main); padding: 3px 8px; border-radius: 4px; }
.remove-btn:hover { background: var(--danger-bg); color: var(--danger); }
.item-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.item-grid.three-col { grid-template-columns: 1fr 1fr 1fr; }
.item-grid.two-col { grid-template-columns: 1fr 1fr; }
.item-checks { display: flex; gap: 20px; flex-wrap: wrap; }

/* TAGS */
.tag-section { display: flex; flex-direction: column; gap: 6px; padding-top: 10px; border-top: 1px solid var(--border-light); }
.activity-link-select :deep(.base-select) { height: 40px; padding: 0 30px 0 12px; background: #FAFAFA; }
.tag-empty-hint { font-size: var(--font-hint); color: var(--text-muted); }
.tag-checks { display: flex; flex-wrap: wrap; gap: 10px 16px; }
.tag-check-item { font-size: var(--font-hint); }
.tag-create-row { display: flex; gap: 8px; margin-top: 4px; }
.tag-create-input { flex: 1; height: 34px; padding: 0 10px; border: 1px solid var(--border); border-radius: var(--radius-md); font-size: var(--font-label); font-family: var(--font-main); background: #FAFAFA; color: var(--text-primary); outline: none; }
.tag-create-input:focus { border-color: var(--violet); background: var(--white); }
.tag-create-btn { font-size: var(--font-label); font-weight: 500; color: var(--violet); background: var(--violet-bg); border: none; border-radius: var(--radius-md); padding: 0 14px; cursor: pointer; font-family: var(--font-main); white-space: nowrap; }
.tag-create-btn:disabled { opacity: 0.6; cursor: default; }
.tag-create-error { font-size: var(--font-hint); color: var(--danger); }
.check-item { display: flex; align-items: center; gap: 8px; font-size: var(--font-label); color: var(--text-secondary); cursor: pointer; }
.check-item input { accent-color: var(--violet); width: 15px; height: 15px; cursor: pointer; }

.activity-task-group { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border-light); }
.task-group-list { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; max-height: 180px; overflow-y: auto; }
.task-group-item { padding: 6px 10px; border-radius: 6px; background: var(--bg-page); }
.task-group-item-disabled { opacity: 0.45; cursor: not-allowed; }
.task-group-item-disabled input { cursor: not-allowed; }
.task-group-day { font-size: var(--font-hint); color: var(--text-muted); margin-left: 4px; }
.task-group-warning { font-size: var(--font-hint); color: var(--danger); margin-left: 6px; font-weight: 500; }
.task-group-empty { font-size: var(--font-label); color: var(--text-muted); padding: 8px 0; }
.empty-section { font-size: var(--font-label); color: var(--text-muted); padding: 24px 0; text-align: center; }
.error-banner { background: var(--danger-bg); border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 12px 16px; font-size: var(--font-label); color: #B91C1C; }
.resubmit-warning { background: var(--warning-bg); border: 1px solid #FDE68A; border-radius: var(--radius-md); padding: 12px 16px; font-size: var(--font-label); color: #92400E; line-height: 1.5; }

/* DEPENDENCY ROWS */
.dep-row { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 14px 16px; background: var(--bg-page); display: flex; flex-direction: column; gap: 10px; }
.dep-task-name { display: flex; align-items: center; gap: 8px; font-size: var(--font-label); font-weight: 500; color: var(--text-primary); flex-wrap: wrap; }
.dep-badge { width: 24px; height: 24px; border-radius: 50%; background: var(--violet-bg); color: var(--violet); font-size: var(--font-upper); font-weight: 600; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.chip { font-size: var(--font-hint); font-weight: 600; padding: 2px 8px; border-radius: 4px; }
.chip-mandatory { background: var(--danger-bg); color: #B91C1C; }
.chip-fixed { background: #FEF3C7; color: #92400E; }
.dep-select-row { display: flex; align-items: center; gap: 10px; }
.dep-current-value { font-size: var(--font-label); color: var(--text-primary); font-weight: 500; flex: 1; }
.dep-row-error { font-size: var(--font-hint); color: var(--danger); margin-top: 6px; }
.dep-label { font-size: var(--font-label); color: var(--text-muted); flex-shrink: 0; }
.dep-select { flex: 1; }
.dep-select :deep(.base-select) { height: 38px; padding: 0 30px 0 10px; background: var(--white); }

.dep-conflict-item { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 14px 16px; margin-bottom: 12px; background: var(--bg-page); }
.dep-conflict-item:last-child { margin-bottom: 0; }
.dep-conflict-text { font-size: var(--font-label); color: var(--text-secondary); line-height: 1.5; margin: 0 0 12px; }
.dep-conflict-actions { display: flex; gap: 8px; flex-wrap: wrap; }

/* GANTT */
.gantt-header { padding: 14px 18px; font-size: var(--font-label); font-weight: 600; color: var(--text-primary); border-bottom: 1px solid var(--border-light); }
.gantt-empty { padding: 40px 18px; font-size: var(--font-label); color: var(--text-muted); text-align: center; }
</style>
