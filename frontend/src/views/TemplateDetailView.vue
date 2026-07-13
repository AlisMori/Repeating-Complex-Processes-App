<!-- /frontend/src/views/TemplateDetailView.vue -->

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import GanttChart from '@/components/GanttChart.vue'
import { useToastStore } from '@/stores/toast'
import { getTemplate, getTemplateTasks, getTemplateActivities, getTemplateTimelinePreview, duplicateTemplate, deleteTemplate, getTemplateVersions, makeCurrentVersion } from '@/api/templates'
import api from '@/api/axios'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()

const template = ref(null)
const tasks = ref([])
const activities = ref([])
const dependencies = ref([])
const timeline = ref(null)
const loading = ref(true)
const error = ref('')
const deleteModalOpen = ref(false)
const deleteLoading = ref(false)

const templateId = route.params.id

const versions = ref([])
const makeCurrentLoading = ref(false)

async function loadTemplate() {
  loading.value = true
  error.value = ''
  try {
    const [tplRes, tasksRes, activitiesRes, depsRes, timelineRes] = await Promise.all([
      getTemplate(templateId),
      getTemplateTasks(templateId),
      getTemplateActivities(templateId),
      api.get('/task-dependencies/'),
      getTemplateTimelinePreview(templateId),
    ])
    template.value = tplRes.data
    tasks.value = Array.isArray(tasksRes.data) ? tasksRes.data : (tasksRes.data.results || [])
    activities.value = Array.isArray(activitiesRes.data) ? activitiesRes.data : (activitiesRes.data.results || [])
    // Filter deps that belong to this template's tasks
    const taskIds = new Set(tasks.value.map(t => t.template_task_id))
    const allDeps = Array.isArray(depsRes.data) ? depsRes.data : (depsRes.data.results || [])
    dependencies.value = allDeps.filter(d => taskIds.has(d.task))
    timeline.value = timelineRes.data
  } catch {
    error.value = 'Failed to load template. Please try again.'
  } finally {
    loading.value = false
  }
}

function getDependencyName(taskId) {
  const task = tasks.value.find(t => t.template_task_id === taskId)
  return task ? task.task_name : '—'
}

function formatReminders(val) {
  if (!val) return '—'
  if (Array.isArray(val)) {
    return val.map(d => d === 0 ? 'On the day' : `${d} days before`).join(', ')
  }
  return val === 0 ? 'On the day' : `${val} days before`
}

function onSwitchVersion(newId) {
  if (String(newId) === String(templateId)) return
  router.push({ name: 'template-detail', params: { id: newId } })
}

async function onMakeCurrent() {
  makeCurrentLoading.value = true
  try {
    await makeCurrentVersion(templateId)
    toast.success('This version is now current.')
    await loadTemplate()
  } catch {
    toast.error('Failed to update the current version.')
  } finally {
    makeCurrentLoading.value = false
  }
}

async function onDuplicate() {
  try {
    await duplicateTemplate(templateId)
    toast.success('Template duplicated.')
    router.push({ name: 'templates' })
  } catch { toast.error('Failed to duplicate template.') }
}

async function confirmDelete() {
  deleteLoading.value = true
  try {
    await deleteTemplate(templateId)
    toast.success('Template deleted.')
    router.push({ name: 'templates' })
  } catch {
    toast.error('Failed to delete template.')
  } finally {
    deleteLoading.value = false
  }
}

// The backend already returns tasks sorted by their own natural
// order; independent tasks first reads better in a Gantt, so we
// only reorder for display — the effective start/end values
// themselves come straight from the backend, unmodified.
const ganttData = computed(() => {
  if (!timeline.value) return null
  const sortedTaskBars = [...timeline.value.task_bars].sort((a, b) => {
    const aHasDep = !!a.dep_name
    const bHasDep = !!b.dep_name
    if (!aHasDep && bHasDep) return -1
    if (aHasDep && !bHasDep) return 1
    return 0
  })
  return {
    taskBars: sortedTaskBars.map(b => ({
      name: b.name,
      start: b.start,
      end: b.end,
      isMandatory: b.is_mandatory,
      isFixed: b.is_fixed_date,
      depName: b.dep_name,
    })),
    activityBars: timeline.value.activity_bars.map(b => ({
      name: b.name,
      start: b.start,
      end: b.end,
    })),
    maxDay: timeline.value.max_day,
  }
})

onMounted(loadTemplate)
</script>

<template>
  <AppLayout>
    <template #topbar>
      <div class="breadcrumb">
        <span class="breadcrumb-link" @click="router.push({ name: 'templates' })">Templates</span>
        <span class="breadcrumb-sep">›</span>
        <span class="breadcrumb-current">{{ template?.template_name || 'Loading...' }}</span>
      </div>
      <div style="margin-left: auto; display: flex; gap: 10px;">
        <BaseButton variant="secondary" size="sm" @click="onDuplicate">Duplicate</BaseButton>
        <BaseButton variant="danger" size="sm" @click="deleteModalOpen = true">Delete</BaseButton>
        <BaseButton variant="primary" size="sm" @click="router.push({ name: 'template-edit', params: { id: templateId } })">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
          Edit template
        </BaseButton>
      </div>
    </template>

    <div class="detail-page">

      <div v-if="loading" class="loading-msg">Loading template...</div>
      <div v-else-if="error" class="error-banner">{{ error }}</div>

      <template v-else-if="template">

        <!-- HEADER CARD -->
        <div class="info-card">
          <div class="info-card-top">
            <div>
              <div class="template-title">{{ template.template_name }}</div>
              <div class="template-desc">{{ template.description || 'No description.' }}</div>
            </div>
            <div class="meta-pills">
              <span class="meta-pill pill-version">v{{ template.template_version }}</span>
              <span v-if="template.is_current_version" class="meta-pill pill-current">Current version</span>
              <BaseSelect
                v-if="versions.length > 1"
                class="version-select"
                :model-value="templateId"
                @update:model-value="onSwitchVersion"
              >
                <option v-for="v in versions" :key="v.template_id" :value="v.template_id">
                  v{{ v.template_version }}{{ v.is_current_version ? ' (current)' : '' }}
                </option>
              </BaseSelect>
              <BaseButton
                v-if="!template.is_current_version"
                variant="secondary"
                size="sm"
                :loading="makeCurrentLoading"
                @click="onMakeCurrent"
              >Make current</BaseButton>
            </div>
          </div>
          <div class="meta-row">
            <div class="meta-item">
              <div class="meta-label">Tasks</div>
              <div class="meta-value">{{ tasks.length }}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">Activities</div>
              <div class="meta-value">{{ activities.length }}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">Dependencies</div>
              <div class="meta-value">{{ dependencies.length }}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">Created</div>
              <div class="meta-value">{{ template.created_at ? new Date(template.created_at).toLocaleDateString('en-AU') : '—' }}</div>
            </div>
          </div>
        </div>

        <div class="two-col">

          <!-- LEFT -->
          <div class="col-main">

            <!-- TASKS -->
            <div class="section-card" v-if="tasks.length > 0">
              <div class="section-header">
                <div class="section-title">Tasks</div>
                <span class="section-count">{{ tasks.length }}</span>
              </div>
              <div class="task-list">
                <div v-for="task in tasks" :key="task.template_task_id" class="task-row">
                  <div class="task-row-left">
                    <div class="task-day-badge">Day {{ task.day_offset }}</div>
                    <div>
                      <div class="task-name">
                        {{ task.task_name }}
                        <span v-if="task.is_mandatory" class="chip chip-mandatory">MANDATORY</span>
                        <span v-if="task.is_fixed_date" class="chip chip-fixed">FIXED DATE</span>
                      </div>
                      <div class="task-meta">
                        Duration: {{ task.duration_days || 1 }} day{{ task.duration_days > 1 ? 's' : '' }}
                        <span v-if="task.reminder_lead_days"> · Reminder: {{ formatReminders(task.reminder_lead_days) }}</span>
                      </div>
                      <div v-if="task.description" class="task-desc">{{ task.description }}</div>
                      <div v-if="dependencies.find(d => d.task === task.template_task_id)" class="task-dep">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/>
                          <path d="M18 9a9 9 0 0 1-9 9"/>
                        </svg>
                        Depends on: {{ getDependencyName(dependencies.find(d => d.task === task.template_task_id).depends_on_task) }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="tasks.length === 0" class="empty-card">
              No tasks defined. Click Edit template to add tasks.
            </div>

            <!-- ACTIVITIES -->
            <div class="section-card" v-if="activities.length > 0">
              <div class="section-header">
                <div class="section-title">Activities</div>
                <span class="section-count">{{ activities.length }}</span>
              </div>
              <div class="task-list">
                <div v-for="act in activities" :key="act.template_activity_id" class="task-row">
                  <div class="task-row-left">
                    <div class="task-day-badge activity-badge">Day {{ act.start_offset_days }}–{{ act.end_offset_days }}</div>
                    <div>
                      <div class="task-name">{{ act.activity_name }}</div>
                      <div class="task-meta">Spans {{ act.end_offset_days - act.start_offset_days }} days</div>
                      <div v-if="act.description" class="task-desc">{{ act.description }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="activities.length === 0 && tasks.length > 0" class="empty-card">
              No activities defined.
            </div>

          </div>

          <!-- RIGHT: GANTT -->
          <div class="col-side">
            <div class="gantt-card">
              <div class="gantt-header">Timeline</div>
              <div v-if="!ganttData" class="gantt-empty">No tasks or activities to display.</div>
              <GanttChart
                v-else
                :task-bars="ganttData.taskBars"
                :activity-bars="ganttData.activityBars"
                :max-day="ganttData.maxDay"
              />
            </div>
          </div>

        </div>
      </template>

    </div>
    <!-- DELETE CONFIRM MODAL -->
    <BaseModal
      v-model="deleteModalOpen"
      title="Delete template?"
      confirm-label="Delete"
      confirm-variant="danger"
      :loading="deleteLoading"
      @confirm="confirmDelete"
    >
      <p>Are you sure you want to delete this template? This cannot be undone.</p>
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
.loading-msg { font-size: var(--font-label); color: var(--text-muted); padding: 40px 0; }
.error-banner { background: var(--danger-bg); border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 12px 16px; font-size: var(--font-label); color: #B91C1C; }

/* HEADER CARD */
.info-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 20px 24px; }
.info-card-top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 18px; gap: 16px; }
.template-title { font-size: var(--font-heading); font-weight: 600; color: var(--text-primary); letter-spacing: -0.3px; margin-bottom: 4px; }
.template-desc { font-size: var(--font-label); color: var(--text-secondary); line-height: 1.6; }
.meta-pills { display: flex; gap: 8px; align-items: center; flex-shrink: 0; }
.version-select { width: 150px; }
.version-select :deep(.base-select) { height: 30px; padding: 0 26px 0 10px; font-size: var(--font-hint); }
.meta-pill { font-size: var(--font-upper); font-weight: 500; padding: 4px 12px; border-radius: 20px; }
.pill-version { background: var(--violet-bg); color: var(--violet); }
.pill-current { background: var(--success-bg); color: #15803D; }
.meta-row { display: flex; gap: 32px; padding-top: 16px; border-top: 1px solid var(--border-light); }
.meta-label { font-size: var(--font-hint); text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); margin-bottom: 3px; }
.meta-value { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); }

/* TWO COL */
.two-col { display: flex; gap: 20px; align-items: flex-start; }
.col-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 16px; }
.col-side { width: 380px; flex-shrink: 0; position: sticky; top: 80px; }

/* SECTION CARDS */
.section-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); overflow: hidden; }
.section-header { display: flex; align-items: center; gap: 10px; padding: 14px 20px; border-bottom: 1px solid var(--border-light); }
.section-title { font-size: var(--font-label); font-weight: 600; color: var(--text-primary); flex: 1; }
.section-count { font-size: var(--font-upper); font-weight: 600; background: var(--violet-bg); color: var(--violet); padding: 2px 10px; border-radius: 20px; }

.task-list { display: flex; flex-direction: column; }
.task-row { display: flex; padding: 14px 20px; border-bottom: 1px solid var(--border-light); }
.task-row:last-child { border-bottom: none; }
.task-row-left { display: flex; gap: 14px; align-items: flex-start; width: 100%; }

.task-day-badge { font-size: var(--font-upper); font-weight: 600; color: var(--violet); background: var(--violet-bg); padding: 4px 10px; border-radius: 6px; flex-shrink: 0; white-space: nowrap; }
.activity-badge { color: #1D4ED8; background: var(--info-bg); }

.task-name { font-size: var(--font-label); font-weight: 600; color: var(--text-primary); margin-bottom: 3px; display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.task-meta { font-size: var(--font-badge); color: var(--text-muted); margin-bottom: 3px; }
.task-desc { font-size: var(--font-label); color: var(--text-secondary); line-height: 1.5; }
.task-dep { display: flex; align-items: center; gap: 5px; font-size: var(--font-upper); color: var(--text-muted); margin-top: 5px; }
.task-dep svg { width: 12px; height: 12px; flex-shrink: 0; }

.chip { font-size: var(--font-hint); font-weight: 600; padding: 2px 7px; border-radius: 4px; }
.chip-mandatory { background: var(--danger-bg); color: #B91C1C; }
.chip-fixed { background: #FEF3C7; color: #92400E; }

.empty-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 28px 20px; font-size: var(--font-label); color: var(--text-muted); text-align: center; }

/* GANTT */
.gantt-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); overflow: hidden; }
.gantt-header { padding: 14px 18px; font-size: var(--font-label); font-weight: 600; color: var(--text-primary); border-bottom: 1px solid var(--border-light); }
.gantt-empty { padding: 40px 18px; font-size: var(--font-label); color: var(--text-muted); text-align: center; }

</style>