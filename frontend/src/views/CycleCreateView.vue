<!-- /frontend/src/views/CycleCreateView.vue -->

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseDatePicker from '@/components/ui/BaseDatePicker.vue'
import { getTemplates, getTemplateTasks, getTemplateActivities, createCycleFromTemplate } from '@/api/templates'
import api from '@/api/axios'

const route = useRoute()
const router = useRouter()

// ── STEP TRACKING ─────────────────────────────────────────
const step = ref(1)

// ── STEP 1: SELECT TEMPLATE ───────────────────────────────
const templates = ref([])
const selectedTemplate = ref(null)
const templateTasks = ref([])
const templateActivities = ref([])
const templateDeps = ref([])
const loadingTemplates = ref(false)
const loadingPreview = ref(false)
const searchQuery = ref('')

const filteredTemplates = computed(() => {
  if (!searchQuery.value.trim()) return templates.value
  const q = searchQuery.value.toLowerCase()
  return templates.value.filter(t =>
    t.template_name?.toLowerCase().includes(q) ||
    t.description?.toLowerCase().includes(q)
  )
})

async function loadTemplates() {
  loadingTemplates.value = true
  try {
    const { data } = await getTemplates()
    templates.value = Array.isArray(data) ? data : (data.results || [])

    const preselect = route.query.template
    if (preselect) {
      const found = templates.value.find(t => String(t.template_id) === String(preselect))
      if (found) {
        await selectTemplate(found)
        proceedToStep2()
      }
    }
  } catch (e) {
    console.error('Failed to load templates', e)
  } finally {
    loadingTemplates.value = false
  }
}

async function selectTemplate(tpl) {
  selectedTemplate.value = tpl
  loadingPreview.value = true
  templateTasks.value = []
  templateActivities.value = []
  templateDeps.value = []
  try {
    const [tasksRes, activitiesRes, depsRes] = await Promise.all([
      getTemplateTasks(tpl.template_id),
      getTemplateActivities(tpl.template_id),
      api.get('/task-dependencies/'),
    ])
    templateTasks.value = Array.isArray(tasksRes.data) ? tasksRes.data : (tasksRes.data.results || [])
    templateActivities.value = Array.isArray(activitiesRes.data) ? activitiesRes.data : (activitiesRes.data.results || [])
    const allDeps = Array.isArray(depsRes.data) ? depsRes.data : (depsRes.data.results || [])
    const taskIds = new Set(templateTasks.value.map(t => t.template_task_id))
    templateDeps.value = allDeps.filter(d => taskIds.has(d.task))
  } catch (e) {
    console.error('Failed to load template preview', e)
  } finally {
    loadingPreview.value = false
  }
}

function proceedToStep2() {
  if (!selectedTemplate.value) return
  step.value = 2
}

// ── STEP 2: NAME + START DATE ─────────────────────────────
const cycleName = ref('')
const startDate = ref('')
const step2Loading = ref(false)
const step2Error = ref('')

// Calculate absolute dates for preview
const calculatedDates = computed(() => {
  if (!startDate.value || templateTasks.value.length === 0) return []
  const start = new Date(startDate.value)
  if (isNaN(start.getTime())) return []

  // Build dep lookup
  const depLookup = {}
  for (const dep of templateDeps.value) depLookup[dep.task] = dep.depends_on_task
  const taskById = {}
  for (const t of templateTasks.value) taskById[t.template_task_id] = t

  function effectiveOffset(task, visited = new Set()) {
    if (visited.has(task.template_task_id)) return task.day_offset || 0
    visited.add(task.template_task_id)
    const depId = depLookup[task.template_task_id]
    if (depId && taskById[depId]) {
      const dep = taskById[depId]
      const depOffset = effectiveOffset(dep, visited)
      return Math.max(task.day_offset || 0, depOffset + (dep.duration_days || 1))
    }
    return task.day_offset || 0
  }

  return templateTasks.value.map(t => {
    const offset = effectiveOffset(t)
    const taskStart = new Date(start)
    taskStart.setDate(taskStart.getDate() + offset)
    const taskEnd = new Date(taskStart)
    taskEnd.setDate(taskEnd.getDate() + (t.duration_days || 1) - 1)
    return {
      name: t.task_name,
      startDate: taskStart.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' }),
      endDate: taskEnd.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' }),
      isMandatory: t.is_mandatory,
      isFixed: t.is_fixed_date,
      offset,
    }
  }).sort((a, b) => a.offset - b.offset)
})

async function submitCycle() {
  if (!cycleName.value.trim()) {
    step2Error.value = 'Cycle name is required.'
    return
  }
  if (!startDate.value) {
    step2Error.value = 'Start date is required.'
    return
  }

  step2Loading.value = true
  step2Error.value = ''
  try {
    const { data } = await createCycleFromTemplate(selectedTemplate.value.template_id, {
      cycle_name: cycleName.value.trim(),
      start_date: startDate.value, // YYYY-MM-DD format from date input
    })
    // Navigate to the new cycle detail view
    const cycleId = data.cycle_id || data.id
    router.push({ name: 'cycle-detail', params: { id: cycleId } })
  } catch (e) {
    step2Error.value = e.response?.data?.start_date?.[0]
      || e.response?.data?.cycle_name?.[0]
      || e.response?.data?.detail
      || 'Failed to create cycle. Please try again.'
  } finally {
    step2Loading.value = false
  }
}

// ── GANTT PREVIEW ─────────────────────────────────────────
const ganttPreview = computed(() => {
  const tasks = templateTasks.value
  const acts = templateActivities.value
  if (tasks.length === 0 && acts.length === 0) return null

  const depLookup = {}
  for (const dep of templateDeps.value) depLookup[dep.task] = dep.depends_on_task
  const taskById = {}
  for (const t of tasks) taskById[t.template_task_id] = t

  function effectiveOffset(task, visited = new Set()) {
    if (visited.has(task.template_task_id)) return task.day_offset || 0
    visited.add(task.template_task_id)
    const depId = depLookup[task.template_task_id]
    if (depId && taskById[depId]) {
      const dep = taskById[depId]
      const depOff = effectiveOffset(dep, visited)
      return Math.max(task.day_offset || 0, depOff + (dep.duration_days || 1))
    }
    return task.day_offset || 0
  }

  const allDays = [
    ...tasks.map(t => effectiveOffset(t) + (t.duration_days || 1)),
    ...acts.map(a => a.end_offset_days || 1),
  ]
  const maxDay = Math.max(...allDays, 1)
  const ticks = Array.from({ length: 6 }, (_, i) => Math.round((maxDay / 5) * i))

  // Sort: independent tasks first
  const sortedTasks = [...tasks].sort((a, b) => {
    const aHasDep = !!depLookup[a.template_task_id]
    const bHasDep = !!depLookup[b.template_task_id]
    if (!aHasDep && bHasDep) return -1
    if (aHasDep && !bHasDep) return 1
    return effectiveOffset(a) - effectiveOffset(b)
  })

  const taskBars = sortedTasks.map(t => {
    const eff = effectiveOffset(t)
    const depId = depLookup[t.template_task_id]
    const depTask = depId ? taskById[depId] : null
    return {
      name: t.task_name,
      left: (eff / maxDay) * 100,
      width: Math.max(((t.duration_days || 1) / maxDay) * 100, 3),
      isMandatory: t.is_mandatory,
      isFixed: t.is_fixed_date,
      depName: depTask ? depTask.task_name : null,
    }
  })

  const activityBars = acts.map(a => ({
    name: a.activity_name,
    left: ((a.start_offset_days || 0) / maxDay) * 100,
    width: Math.max(((a.end_offset_days - a.start_offset_days) / maxDay) * 100, 3),
  }))

  return { taskBars, activityBars, ticks, maxDay }
})

onMounted(loadTemplates)
</script>

<template>
  <AppLayout>
    <template #topbar>
      <div class="breadcrumb">
        <span class="breadcrumb-link" @click="router.push({ name: 'cycles' })">Cycles</span>
        <span class="breadcrumb-sep">›</span>
        <span class="breadcrumb-current">New Cycle</span>
      </div>
    </template>

    <div class="create-page">

      <!-- STEP INDICATOR -->
      <div class="steps-bar">
        <div class="step-item" :class="{ active: step === 1, done: step > 1 }">
          <div class="step-circle">
            <svg v-if="step > 1" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            <span v-else>1</span>
          </div>
          <span class="step-label">Select template</span>
        </div>
        <div class="step-connector" :class="{ done: step > 1 }"></div>
        <div class="step-item" :class="{ active: step === 2 }">
          <div class="step-circle"><span>2</span></div>
          <span class="step-label">Name & start date</span>
        </div>
      </div>

      <!-- ── STEP 1: SELECT TEMPLATE ── -->
      <div v-if="step === 1" class="two-panel">

        <!-- LEFT: TEMPLATE LIST -->
        <div class="panel-left">
          <div class="form-card">
            <div class="form-card-header">
              <div>
                <div class="form-card-title">Choose a template</div>
                <div class="form-card-desc">Select the process template to base this cycle on. Click a template to preview its timeline.</div>
              </div>
            </div>
            <div class="form-body">

              <!-- SEARCH -->
              <div class="search-box">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
                <input v-model="searchQuery" type="text" placeholder="Search templates..." />
              </div>

              <!-- LOADING -->
              <div v-if="loadingTemplates" class="loading-msg">Loading templates...</div>

              <!-- EMPTY -->
              <div v-else-if="filteredTemplates.length === 0" class="empty-section">
                No templates found.
                <BaseButton variant="secondary" size="sm" @click="router.push({ name: 'template-create' })" style="margin-top: 10px;">
                  Create a template first
                </BaseButton>
              </div>

              <!-- TEMPLATE LIST -->
              <div v-else class="template-list">
                <div
                  v-for="tpl in filteredTemplates"
                  :key="tpl.template_id"
                  class="template-row"
                  :class="{ selected: selectedTemplate?.template_id === tpl.template_id }"
                  @click="selectTemplate(tpl)"
                >
                  <div class="template-row-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
                      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
                    </svg>
                  </div>
                  <div class="template-row-info">
                    <div class="template-row-name">{{ tpl.template_name }}</div>
                    <div class="template-row-meta">v{{ tpl.template_version }} · {{ tpl.description || 'No description' }}</div>
                  </div>
                  <div v-if="selectedTemplate?.template_id === tpl.template_id" class="template-row-check">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  </div>
                </div>
              </div>

            </div>
          </div>

          <div class="form-footer">
            <BaseButton variant="secondary" size="sm" @click="router.push({ name: 'cycles' })">Cancel</BaseButton>
            <BaseButton
              variant="primary"
              size="sm"
              :disabled="!selectedTemplate"
              @click="proceedToStep2"
            >
              Continue →
            </BaseButton>
          </div>
        </div>

        <!-- RIGHT: TEMPLATE PREVIEW -->
        <div class="panel-right">
          <div class="preview-header">
            {{ selectedTemplate ? selectedTemplate.template_name : 'Select a template to preview' }}
          </div>

          <div v-if="!selectedTemplate" class="preview-empty">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
              <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
            </svg>
            <p>Click a template on the left to see its timeline here.</p>
          </div>

          <div v-else-if="loadingPreview" class="preview-empty">
            <p>Loading preview...</p>
          </div>

          <div v-else>
            <!-- TEMPLATE META -->
            <div class="preview-meta">
              <div class="preview-meta-item">
                <span class="preview-meta-label">Tasks</span>
                <span class="preview-meta-value">{{ templateTasks.length }}</span>
              </div>
              <div class="preview-meta-item">
                <span class="preview-meta-label">Activities</span>
                <span class="preview-meta-value">{{ templateActivities.length }}</span>
              </div>
              <div class="preview-meta-item">
                <span class="preview-meta-label">Dependencies</span>
                <span class="preview-meta-value">{{ templateDeps.length }}</span>
              </div>
              <div class="preview-meta-item">
                <span class="preview-meta-label">Version</span>
                <span class="preview-meta-value">v{{ selectedTemplate.template_version }}</span>
              </div>
            </div>

            <!-- GANTT -->
            <div v-if="!ganttPreview" class="preview-empty" style="padding: 20px;">
              <p>This template has no tasks or activities yet.</p>
            </div>
            <div v-else class="gantt-chart">
              <div class="gantt-tick-row">
                <div class="gantt-label-col"></div>
                <div class="gantt-bars-col">
                  <div v-for="tick in ganttPreview.ticks" :key="tick" class="gantt-tick" :style="{ left: (tick / ganttPreview.maxDay * 100) + '%' }">
                    <span>Day {{ tick }}</span>
                  </div>
                </div>
              </div>

              <div v-if="ganttPreview.activityBars.length > 0" class="gantt-section-label">Activities</div>
              <div v-for="bar in ganttPreview.activityBars" :key="bar.name" class="gantt-row">
                <div class="gantt-label-col" :title="bar.name">{{ bar.name }}</div>
                <div class="gantt-bars-col">
                  <div class="gantt-bar gantt-bar-activity" :style="{ left: bar.left + '%', width: bar.width + '%' }"></div>
                </div>
              </div>

              <div v-if="ganttPreview.taskBars.length > 0" class="gantt-section-label">Tasks</div>
              <div v-for="bar in ganttPreview.taskBars" :key="bar.name" class="gantt-row">
                <div class="gantt-label-col" :title="bar.name">{{ bar.name }}</div>
                <div class="gantt-bars-col">
                  <div
                    class="gantt-bar"
                    :class="{
                      'gantt-bar-mandatory': bar.isMandatory,
                      'gantt-bar-fixed': bar.isFixed,
                      'gantt-bar-task': !bar.isMandatory && !bar.isFixed
                    }"
                    :style="{ left: bar.left + '%', width: bar.width + '%' }"
                  ></div>
                  <div v-if="bar.depName" class="gantt-dep-row">
                    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M2 6h8M7 3l3 3-3 3"/>
                    </svg>
                    after {{ bar.depName }}
                  </div>
                </div>
              </div>

              <div class="gantt-legend">
                <span class="legend-item"><span class="legend-dot dot-activity"></span>Activity</span>
                <span class="legend-item"><span class="legend-dot dot-task"></span>Task</span>
                <span class="legend-item"><span class="legend-dot dot-mandatory"></span>Mandatory</span>
                <span class="legend-item"><span class="legend-dot dot-fixed"></span>Fixed date</span>
              </div>
            </div>
          </div>
        </div>

      </div>

      <!-- ── STEP 2: NAME & START DATE ── -->
      <div v-if="step === 2" class="two-panel">

        <!-- LEFT: FORM -->
        <div class="panel-left">
          <div class="form-card">
            <div class="form-card-header">
              <div>
                <div class="form-card-title">Cycle details</div>
                <div class="form-card-desc">
                  Based on: <strong>{{ selectedTemplate?.template_name }}</strong> v{{ selectedTemplate?.template_version }}
                </div>
              </div>
            </div>
            <div class="form-body">

              <div class="field">
                <BaseInput
                  v-model="cycleName"
                  label="Cycle name *"
                  placeholder="e.g. ICT302 S2 2026"
                  hint="Give this cycle a unique name to identify it — e.g. include the year or period"
                />
              </div>

              <div class="field">
                <BaseDatePicker
                  v-model="startDate"
                  label="Start date *"
                  hint="All task dates will be calculated automatically from this date"
                />
              </div>

              <div v-if="step2Error" class="error-banner">{{ step2Error }}</div>

              <!-- CALCULATED DATES SUMMARY -->
              <div v-if="calculatedDates.length > 0" class="dates-summary">
                <div class="dates-summary-title">Calculated task dates</div>
                <div class="dates-table">
                  <div class="dates-header">
                    <span>Task</span>
                    <span>Start</span>
                    <span>End</span>
                  </div>
                  <div v-for="d in calculatedDates" :key="d.name" class="dates-row">
                    <span class="dates-task-name">
                      {{ d.name }}
                      <span v-if="d.isMandatory" class="chip chip-mandatory">M</span>
                      <span v-if="d.isFixed" class="chip chip-fixed">F</span>
                    </span>
                    <span class="dates-date">{{ d.startDate }}</span>
                    <span class="dates-date">{{ d.endDate }}</span>
                  </div>
                </div>
              </div>

            </div>
          </div>

          <div class="form-footer">
            <BaseButton variant="secondary" size="sm" @click="step = 1">← Back</BaseButton>
            <BaseButton variant="primary" size="sm" :loading="step2Loading" @click="submitCycle">
              Start cycle
            </BaseButton>
          </div>
        </div>

        <!-- RIGHT: GANTT with real dates if start date entered -->
        <div class="panel-right">
          <div class="preview-header">
            {{ startDate ? 'Timeline with dates' : 'Timeline preview' }}
          </div>
          <div v-if="!ganttPreview" class="preview-empty"><p>No tasks in this template.</p></div>
          <div v-else class="gantt-chart">
            <div class="gantt-tick-row">
              <div class="gantt-label-col"></div>
              <div class="gantt-bars-col">
                <div v-for="tick in ganttPreview.ticks" :key="tick" class="gantt-tick" :style="{ left: (tick / ganttPreview.maxDay * 100) + '%' }">
                  <span>Day {{ tick }}</span>
                </div>
              </div>
            </div>

            <div v-if="ganttPreview.activityBars.length > 0" class="gantt-section-label">Activities</div>
            <div v-for="bar in ganttPreview.activityBars" :key="bar.name" class="gantt-row">
              <div class="gantt-label-col" :title="bar.name">{{ bar.name }}</div>
              <div class="gantt-bars-col">
                <div class="gantt-bar gantt-bar-activity" :style="{ left: bar.left + '%', width: bar.width + '%' }"></div>
              </div>
            </div>

            <div v-if="ganttPreview.taskBars.length > 0" class="gantt-section-label">Tasks</div>
            <div v-for="bar in ganttPreview.taskBars" :key="bar.name" class="gantt-row">
              <div class="gantt-label-col" :title="bar.name">{{ bar.name }}</div>
              <div class="gantt-bars-col">
                <div
                  class="gantt-bar"
                  :class="{
                    'gantt-bar-mandatory': bar.isMandatory,
                    'gantt-bar-fixed': bar.isFixed,
                    'gantt-bar-task': !bar.isMandatory && !bar.isFixed
                  }"
                  :style="{ left: bar.left + '%', width: bar.width + '%' }"
                ></div>
                <div v-if="bar.depName" class="gantt-dep-row">
                  <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M2 6h8M7 3l3 3-3 3"/>
                  </svg>
                  after {{ bar.depName }}
                </div>
              </div>
            </div>

            <div class="gantt-legend">
              <span class="legend-item"><span class="legend-dot dot-activity"></span>Activity</span>
              <span class="legend-item"><span class="legend-dot dot-task"></span>Task</span>
              <span class="legend-item"><span class="legend-dot dot-mandatory"></span>Mandatory</span>
              <span class="legend-item"><span class="legend-dot dot-fixed"></span>Fixed date</span>
            </div>
          </div>
        </div>

      </div>

    </div>
  </AppLayout>
</template>

<style scoped>
.breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 14px; }
.breadcrumb-link { color: var(--text-muted); cursor: pointer; }
.breadcrumb-link:hover { color: var(--violet); }
.breadcrumb-sep { color: var(--text-muted); }
.breadcrumb-current { color: var(--text-primary); font-weight: 500; }

.create-page { display: flex; flex-direction: column; gap: 20px; }
.loading-msg { font-size: 14px; color: var(--text-muted); padding: 20px 0; }

/* STEPS BAR */
.steps-bar { display: flex; align-items: center; }
.step-item { display: flex; align-items: center; gap: 10px; }
.step-circle { width: 30px; height: 30px; border-radius: 50%; border: 2px solid var(--border-light); background: var(--white); display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600; color: var(--text-muted); flex-shrink: 0; transition: all 0.2s; }
.step-circle svg { width: 14px; height: 14px; }
.step-item.active .step-circle { border-color: var(--violet); background: var(--violet); color: white; }
.step-item.done .step-circle { border-color: var(--success); background: var(--success); color: white; }
.step-label { font-size: 14px; color: var(--text-muted); }
.step-item.active .step-label { color: var(--text-primary); font-weight: 500; }
.step-item.done .step-label { color: var(--success); }
.step-connector { flex: 0 0 40px; height: 1px; background: var(--border-light); margin: 0 12px; transition: background 0.2s; }
.step-connector.done { background: var(--success); }

/* TWO PANEL */
.two-panel { display: flex; gap: 20px; align-items: flex-start; }
.panel-left { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 16px; }
.panel-right { width: 400px; flex-shrink: 0; background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); overflow: hidden; position: sticky; top: 80px; max-height: calc(100vh - 120px); overflow-y: auto; }

/* FORM CARD */
.form-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); overflow: hidden; }
.form-card-header { padding: 16px 20px; border-bottom: 1px solid var(--border-light); }
.form-card-title { font-size: 15px; font-weight: 600; color: var(--text-primary); margin-bottom: 3px; }
.form-card-desc { font-size: 13px; color: var(--text-muted); }
.form-body { padding: 16px 20px; display: flex; flex-direction: column; gap: 16px; }
.form-footer { display: flex; justify-content: flex-end; gap: 10px; }

/* SEARCH */
.search-box { display: flex; align-items: center; gap: 8px; border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 8px 12px; background: var(--bg-page); }
.search-box svg { width: 15px; height: 15px; stroke: var(--text-muted); flex-shrink: 0; }
.search-box input { border: none; background: transparent; font-size: 14px; color: var(--text-primary); outline: none; width: 100%; font-family: var(--font-main); }
.search-box input::placeholder { color: var(--text-muted); }

/* TEMPLATE LIST */
.template-list { display: flex; flex-direction: column; gap: 6px; }
.template-row { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: 1px solid var(--border-light); border-radius: var(--radius-md); cursor: pointer; transition: border-color var(--transition-fast), background var(--transition-fast); }
.template-row:hover { border-color: #C4B5FD; background: var(--violet-bg); }
.template-row.selected { border-color: var(--violet); background: var(--violet-bg); }
.template-row-icon { width: 36px; height: 36px; border-radius: 8px; background: var(--violet-bg); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.template-row-icon svg { width: 18px; height: 18px; stroke: var(--violet); }
.template-row.selected .template-row-icon { background: white; }
.template-row-info { flex: 1; min-width: 0; }
.template-row-name { font-size: 14px; font-weight: 500; color: var(--text-primary); margin-bottom: 2px; }
.template-row-meta { font-size: 12px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.template-row-check { width: 22px; height: 22px; border-radius: 50%; background: var(--violet); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.template-row-check svg { width: 12px; height: 12px; stroke: white; }

/* FIELDS */
.field { display: flex; flex-direction: column; gap: 5px; }
.empty-section { font-size: 14px; color: var(--text-muted); text-align: center; padding: 20px 0; display: flex; flex-direction: column; align-items: center; gap: 10px; }
.error-banner { background: var(--danger-bg); border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 12px 16px; font-size: 14px; color: #B91C1C; }

/* CALCULATED DATES */
.dates-summary { border: 1px solid var(--border-light); border-radius: var(--radius-md); overflow: hidden; }
.dates-summary-title { font-size: 12px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; padding: 10px 14px; background: var(--bg-page); border-bottom: 1px solid var(--border-light); }
.dates-table { display: flex; flex-direction: column; }
.dates-header { display: grid; grid-template-columns: 1fr auto auto; gap: 12px; padding: 8px 14px; font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--border-light); }
.dates-row { display: grid; grid-template-columns: 1fr auto auto; gap: 12px; padding: 9px 14px; border-bottom: 1px solid var(--border-light); align-items: center; }
.dates-row:last-child { border-bottom: none; }
.dates-task-name { font-size: 13px; color: var(--text-primary); display: flex; align-items: center; gap: 6px; }
.dates-date { font-size: 12.5px; color: var(--text-secondary); white-space: nowrap; }
.chip { font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px; }
.chip-mandatory { background: var(--danger-bg); color: #B91C1C; }
.chip-fixed { background: #FEF3C7; color: #92400E; }

/* PREVIEW PANEL */
.preview-header { padding: 14px 18px; font-size: 14px; font-weight: 600; color: var(--text-primary); border-bottom: 1px solid var(--border-light); }
.preview-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 50px 20px; gap: 12px; color: var(--text-muted); font-size: 14px; text-align: center; }
.preview-empty svg { width: 36px; height: 36px; stroke: var(--border-light); }
.preview-meta { display: flex; gap: 0; border-bottom: 1px solid var(--border-light); }
.preview-meta-item { flex: 1; padding: 10px 14px; border-right: 1px solid var(--border-light); }
.preview-meta-item:last-child { border-right: none; }
.preview-meta-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; display: block; margin-bottom: 2px; }
.preview-meta-value { font-size: 15px; font-weight: 600; color: var(--text-primary); }

/* GANTT */
.gantt-chart { padding: 14px 18px; display: flex; flex-direction: column; gap: 10px; }
.gantt-section-label { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.07em; margin-top: 4px; }
.gantt-tick-row { display: flex; gap: 8px; margin-bottom: 4px; }
.gantt-row { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 6px; }
.gantt-label-col { width: 100px; flex-shrink: 0; font-size: 12px; color: var(--text-secondary); text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-top: 10px; }
.gantt-bars-col { flex: 1; position: relative; min-height: 34px; }
.gantt-tick { position: absolute; display: flex; flex-direction: column; align-items: center; }
.gantt-tick span { font-size: 10px; color: var(--text-muted); white-space: nowrap; }
.gantt-bar { position: absolute; top: 0; height: 28px; border-radius: 6px; min-width: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
.gantt-bar-activity { background: linear-gradient(90deg, #7C3AED 0%, #A78BFA 100%); opacity: 0.8; }
.gantt-bar-task { background: #475569; }
.gantt-bar-mandatory { background: #EF4444; }
.gantt-bar-fixed { background: #F59E0B; }
.gantt-dep-row { display: flex; align-items: center; gap: 4px; font-size: 11px; color: var(--text-muted); margin-top: 30px; white-space: nowrap; }
.gantt-dep-row svg { width: 11px; height: 11px; }
.gantt-legend { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border-light); }
.legend-item { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--text-muted); }
.legend-dot { width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }
.dot-activity { background: #7C3AED; }
.dot-task { background: #475569; }
.dot-mandatory { background: #EF4444; }
.dot-fixed { background: #F59E0B; }
</style>