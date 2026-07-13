<!-- /frontend/src/views/TemplateCreateView.vue -->
<!-- Handles both CREATE (/templates/new) and EDIT (/templates/:id/edit) -->

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import GanttChart from '@/components/GanttChart.vue'
import { resolveEffectiveOffsets } from '@/utils/scheduling'
import {
  createTemplate, updateTemplate,
  createTemplateTask,
  createTemplateActivity,
  getTemplate, getTemplateTasks, getTemplateActivities,
  getTags, createTag,
  createTemplateTaskTag, createTemplateActivityTag,
  getTemplateTaskTags, getTemplateActivityTags,
} from '@/api/templates'
import api from '@/api/axios'

const route = useRoute()
const router = useRouter()

const isEditMode = computed(() => !!route.params.id)
const templateId = computed(() => route.params.id || null)
const pageTitle = computed(() => isEditMode.value ? 'Edit Template' : 'New Template')

// ── STEP TRACKING ─────────────────────────────────────────
const step = ref(1)
const createdTemplateId = ref(null)
const savedTasks = ref([])
const loadingInitial = ref(false)

// ── STEP 1: TEMPLATE INFO ─────────────────────────────────
const templateForm = reactive({ template_name: '', description: '' })
const step1Loading = ref(false)
const step1Error = ref('')

async function loadExistingTemplate() {
  if (!isEditMode.value) return
  loadingInitial.value = true
  try {
    const [tplRes, tasksRes, activitiesRes, taskTagsRes, activityTagsRes] = await Promise.all([
      getTemplate(templateId.value),
      getTemplateTasks(templateId.value),
      getTemplateActivities(templateId.value),
      getTemplateTaskTags(),
      getTemplateActivityTags(),
    ])
    const tpl = tplRes.data
    templateForm.template_name = tpl.template_name
    templateForm.description = tpl.description || ''
    createdTemplateId.value = tpl.template_id

    const taskList = Array.isArray(tasksRes.data) ? tasksRes.data : (tasksRes.data.results || [])
    const actList = Array.isArray(activitiesRes.data) ? activitiesRes.data : (activitiesRes.data.results || [])
    const allTaskTags = Array.isArray(taskTagsRes.data) ? taskTagsRes.data : (taskTagsRes.data.results || [])
    const allActivityTags = Array.isArray(activityTagsRes.data) ? activityTagsRes.data : (activityTagsRes.data.results || [])

    tasks.value = taskList.map(t => ({
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
      tagIds: allTaskTags.filter(tt => tt.template_task === t.template_task_id).map(tt => tt.tag),
    }))

    activities.value = actList.map(a => ({
      activity_name: a.activity_name,
      description: a.description || '',
      start_offset_days: a.start_offset_days || 0,
      end_offset_days: a.end_offset_days || 1,
      note_text: a.note_text || '',
      tagIds: allActivityTags.filter(at => at.template_activity === a.template_activity_id).map(at => at.tag),
    }))
  } catch (e) {
    step1Error.value = 'Failed to load template data.'
  } finally {
    loadingInitial.value = false
  }
}

async function submitStep1() {
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
    step1Error.value = e.response?.data?.template_name?.[0]
      || e.response?.data?.detail
      || 'Failed to save template. Please try again.'
  } finally {
    step1Loading.value = false
  }
}

// ── STEP 2: TASKS & ACTIVITIES ────────────────────────────
const tasks = ref([])
const activities = ref([])
const step2Loading = ref(false)
const step2Error = ref('')
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
function buildReminderArray(task) {
  const arr = []
  if (task.reminder_7) arr.push(7)
  if (task.reminder_3) arr.push(3)
  if (task.reminder_0) arr.push(0)
  return arr.length > 0 ? arr : null
}

function addTask() {
  tasks.value.push({
    task_name: '', description: '',
    day_offset: tasks.value.length === 0 ? 0 : Math.max(...tasks.value.map(t => Number(t.day_offset))) + 1,
    duration_days: 1, is_mandatory: false, is_fixed_date: false,
    reminder_7: false, reminder_3: false, reminder_0: false, note_text: '',
    tagIds: [],
  })
}

function removeTask(index) { tasks.value.splice(index, 1) }

function addActivity() {
  activities.value.push({
    activity_name: '', description: '',
    start_offset_days: 0,
    end_offset_days: activities.value.length === 0 ? 30 : Math.max(...activities.value.map(a => Number(a.end_offset_days))) + 10,
    note_text: '',
    tagIds: [],
  })
}
function removeActivity(index) { activities.value.splice(index, 1) }

async function submitStep2() {
  for (const task of tasks.value) {
    if (!task.task_name.trim()) { step2Error.value = 'All tasks must have a name.'; return }
    if (Number(task.day_offset) < 0) { step2Error.value = 'Day offset cannot be negative.'; return }
  }
  for (const act of activities.value) {
    if (!act.activity_name.trim()) { step2Error.value = 'All activities must have a name.'; return }
    if (Number(act.end_offset_days) <= Number(act.start_offset_days)) {
      step2Error.value = `Activity "${act.activity_name}" end day must be after start day.`; return
    }
  }

  step2Loading.value = true
  step2Error.value = ''
  try {
    const taskResults = []

    for (const task of tasks.value) {
      const payload = {
        template: createdTemplateId.value,
        task_name: task.task_name.trim(),
        description: task.description.trim(),
        day_offset: Number(task.day_offset),
        duration_days: Number(task.duration_days),
        is_mandatory: task.is_mandatory,
        is_fixed_date: task.is_fixed_date,
        reminder_lead_days: buildReminderArray(task),
        note_text: task.note_text.trim(),
      }
      // Always createTemplateTask — in edit mode updateTemplate() already created
      // a new template version with no tasks, so we always create fresh on new version ID.
      const res = await createTemplateTask(payload)
      taskResults.push({ ...res.data, _localName: task.task_name })

      for (const tagId of task.tagIds || []) {
        await createTemplateTaskTag({ template_task: res.data.template_task_id, tag: tagId })
      }
    }

    for (const act of activities.value) {
      const actRes = await createTemplateActivity({
        template: createdTemplateId.value,
        activity_name: act.activity_name.trim(),
        description: act.description.trim(),
        start_offset_days: Number(act.start_offset_days),
        end_offset_days: Number(act.end_offset_days),
        note_text: act.note_text.trim(),
      })

      for (const tagId of act.tagIds || []) {
        await createTemplateActivityTag({ template_activity: actRes.data.template_activity_id, tag: tagId })
      }
    }

    savedTasks.value = taskResults
    dependencies.value = taskResults.map(() => null)
    step.value = 3
  } catch (e) {
    step2Error.value = e.response?.data?.task_name?.[0]
      || e.response?.data?.detail
      || 'Failed to save. Please check your entries and try again.'
  } finally {
    step2Loading.value = false
  }
}

function skipToStep3() {
  savedTasks.value = []
  dependencies.value = []
  step.value = 3
}

// ── STEP 3: DEPENDENCIES ──────────────────────────────────
const dependencies = ref([])
const step3Loading = ref(false)
const step3Error = ref('')

function dependencyOptions(taskIndex) {
  return savedTasks.value.filter((_, i) => i !== taskIndex)
}

async function submitStep3() {
  step3Loading.value = true
  step3Error.value = ''
  try {
    for (let i = 0; i < savedTasks.value.length; i++) {
      if (dependencies.value[i]) {
        await api.post('/task-dependencies/', {
          task: savedTasks.value[i].template_task_id,
          depends_on_task: dependencies.value[i],
        })
      }
    }
    if (isEditMode.value) {
      router.push({ name: 'template-detail', params: { id: createdTemplateId.value } })
    } else {
      router.push({ name: 'templates' })
    }
  } catch (e) {
    step3Error.value = e.response?.data?.detail
      || e.response?.data?.depends_on_task?.[0]
      || 'Failed to save dependencies. Please try again.'
  } finally {
    step3Loading.value = false
  }
}

function skipDependencies() {
  if (isEditMode.value) {
    router.push({ name: 'template-detail', params: { id: createdTemplateId.value } })
  } else {
    router.push({ name: 'templates' })
  }
}

// ── GANTT PREVIEW ─────────────────────────────────────────
// Uses the same resolveEffectiveOffsets algorithm the backend runs
// (see backend/templates_mgmt/scheduling.py) so this live, unsaved
// preview always agrees with what create_cycle will actually
// produce once things are saved. This is only needed here because
// dependencies don't exist in the backend yet at this point in the
// wizard — once a template is saved, TemplateDetailView.vue fetches
// this same computation from the backend instead of duplicating it.
function buildGantt(taskList, actList, depMap = {}) {
  if (taskList.length === 0 && actList.length === 0) return null

  const nodes = {}
  taskList.forEach((t, i) => {
    nodes[i] = {
      offset: Number(t.day_offset),
      duration: Number(t.duration_days || 1),
      fixed: !!t.is_fixed_date,
    }
  })

  const edges = {}
  Object.entries(depMap).forEach(([i, depIdx]) => {
    if (depIdx !== undefined && depIdx !== null) {
      edges[i] = [depIdx]
    }
  })

  const { effective } = resolveEffectiveOffsets(nodes, edges)

  // Topological-ish sort for display — independent tasks first,
  // then tasks that depend on them, so the timeline reads top-down.
  const sorted = [...taskList.map((t, i) => ({ ...t, _origIdx: i }))]
  sorted.sort((a, b) => {
    const aHasDep = depMap[a._origIdx] !== undefined && depMap[a._origIdx] !== null
    const bHasDep = depMap[b._origIdx] !== undefined && depMap[b._origIdx] !== null
    if (!aHasDep && bHasDep) return -1
    if (aHasDep && !bHasDep) return 1
    return 0
  })

  const taskBars = sorted.map(t => {
    const [effStart, effEnd] = effective[t._origIdx]
    return {
      name: t.task_name || t._localName || '(unnamed)',
      start: effStart,
      end: effEnd,
      isMandatory: t.is_mandatory,
      isFixed: t.is_fixed_date,
      depName: null,
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

const step3Preview = computed(() => {
  // Build depMap: taskIndex -> index of the task it depends on
  const depMap = {}
  for (let i = 0; i < savedTasks.value.length; i++) {
    const depId = dependencies.value[i]
    if (depId) {
      const depIdx = savedTasks.value.findIndex(t => t.template_task_id === depId)
      if (depIdx !== -1) depMap[i] = depIdx
    }
  }

  const gantt = buildGantt(savedTasks.value, activities.value, depMap)
  if (!gantt) return null

  // Add depName to each bar using the original index stored in _origIdx
  gantt.taskBars = gantt.taskBars.map((bar, _) => {
    // Find the original task that matches this bar name
    const origTask = savedTasks.value.find(t => (t.task_name || t._localName) === bar.name)
    if (!origTask) return bar
    const origIdx = savedTasks.value.indexOf(origTask)
    const depIdx = depMap[origIdx]
    const depTask = depIdx !== undefined ? savedTasks.value[depIdx] : null
    return {
      ...bar,
      depName: depTask ? (depTask.task_name || depTask._localName) : null,
    }
  })

  return gantt
})

onMounted(async () => {
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
          </div>
          <div class="form-body">
            <div class="field">
              <BaseInput v-model="templateForm.template_name" label="Template name *" placeholder="e.g. Unit Coordination Template" />
            </div>
            <div class="field">
              <label class="field-label">Description</label>
              <textarea v-model="templateForm.description" class="field-textarea" placeholder="Briefly describe what this template is for..." rows="3"></textarea>
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
                <div v-for="(task, idx) in tasks" :key="idx" class="item-card">
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
                        hint="How many days this task spans"
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
                        <input type="checkbox" :value="tag.tag_id" v-model="task.tagIds" />
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
                <div v-for="(act, idx) in activities" :key="idx" class="item-card">
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
                        <input type="checkbox" :value="tag.tag_id" v-model="act.tagIds" />
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
                <div v-if="savedTasks.length === 0" class="empty-section">No tasks were added — skip to finish.</div>
                <div v-for="(task, idx) in savedTasks" :key="task.template_task_id" class="dep-row">
                  <div class="dep-task-name">
                    <div class="dep-badge">{{ idx + 1 }}</div>
                    <span>{{ task.task_name || task._localName }}</span>
                    <span v-if="task.is_mandatory" class="chip chip-mandatory">MANDATORY</span>
                    <span v-if="task.is_fixed_date" class="chip chip-fixed">FIXED DATE</span>
                  </div>
                  <div class="dep-select-row">
                    <span class="dep-label">Depends on:</span>
                    <BaseSelect v-model="dependencies[idx]" class="dep-select">
                      <option :value="null">— No dependency</option>
                      <option v-for="opt in dependencyOptions(idx)" :key="opt.template_task_id" :value="opt.template_task_id">
                        {{ opt.task_name || opt._localName }} (Day {{ opt.day_offset }})
                      </option>
                    </BaseSelect>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="step3Error" class="error-banner">{{ step3Error }}</div>
            <div class="form-footer">
              <BaseButton variant="secondary" size="sm" @click="skipDependencies">Skip — no dependencies</BaseButton>
              <BaseButton variant="primary" size="sm" :loading="step3Loading" @click="submitStep3">Save template</BaseButton>
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

/* FIELDS */
.field { display: flex; flex-direction: column; gap: 5px; }
.field-label { font-size: var(--font-label); font-weight: 500; color: var(--text-primary); }
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
.empty-section { font-size: var(--font-label); color: var(--text-muted); padding: 24px 0; text-align: center; }
.error-banner { background: var(--danger-bg); border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 12px 16px; font-size: var(--font-label); color: #B91C1C; }

/* DEPENDENCY ROWS */
.dep-row { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 14px 16px; background: var(--bg-page); display: flex; flex-direction: column; gap: 10px; }
.dep-task-name { display: flex; align-items: center; gap: 8px; font-size: var(--font-label); font-weight: 500; color: var(--text-primary); flex-wrap: wrap; }
.dep-badge { width: 24px; height: 24px; border-radius: 50%; background: var(--violet-bg); color: var(--violet); font-size: var(--font-upper); font-weight: 600; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.chip { font-size: var(--font-hint); font-weight: 600; padding: 2px 8px; border-radius: 4px; }
.chip-mandatory { background: var(--danger-bg); color: #B91C1C; }
.chip-fixed { background: #FEF3C7; color: #92400E; }
.dep-select-row { display: flex; align-items: center; gap: 10px; }
.dep-label { font-size: var(--font-label); color: var(--text-muted); flex-shrink: 0; }
.dep-select { flex: 1; }
.dep-select :deep(.base-select) { height: 38px; padding: 0 30px 0 10px; background: var(--white); }

/* GANTT */
.gantt-header { padding: 14px 18px; font-size: var(--font-label); font-weight: 600; color: var(--text-primary); border-bottom: 1px solid var(--border-light); }
.gantt-empty { padding: 40px 18px; font-size: var(--font-label); color: var(--text-muted); text-align: center; }
</style>