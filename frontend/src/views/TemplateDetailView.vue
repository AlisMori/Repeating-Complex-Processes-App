<!-- /frontend/src/views/TemplateDetailView.vue -->

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import GanttChart from '@/components/GanttChart.vue'
import { useToastStore } from '@/stores/toast'
import { useOnboardingStore } from '@/stores/onboarding'
import {
  getTemplate, getTemplateTasks, getTemplateActivities, getTemplateTimelinePreview,
  duplicateTemplate, deleteTemplate, downloadTemplate, updateTemplate,
  deleteTemplateTask, deleteTemplateActivity,
  setTemplateTaskNote, clearTemplateTaskNote,
  setTemplateActivityNote, clearTemplateActivityNote,
  getTaskDependencies,
  getTags, createTag,
  getTaskTags, assignTagToTask, unassignTagFromTask,
  getActivityTags, assignTagToActivity, unassignTagFromActivity,
  getTemplateCategories, createTemplateCategory,
  getTemplateVersions, makeCurrentVersion,
} from '@/api/templates'
import { getErrorMessage, isPermissionError } from '@/utils/apiErrors'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()
const onboardingStore = useOnboardingStore()

const template = ref(null)
const tasks = ref([])
const activities = ref([])
const dependencies = ref([])
const timeline = ref(null)
const loading = ref(true)
const error = ref('')
const deleteModalOpen = ref(false)

// Overflow "⋯" menu shown per row for secondary actions (note,
// delete) — only one open at a time, closes on any click outside it.
const openMenuFor = ref(null)
function toggleMenu(key) {
  openMenuFor.value = openMenuFor.value === key ? null : key
}
function closeMenu() {
  openMenuFor.value = null
}
onMounted(() => document.addEventListener('click', closeMenu))
onUnmounted(() => document.removeEventListener('click', closeMenu))
const taskTagLinks = ref([])
const activityTagLinks = ref([])
const allTags = ref([])
const detailModal = ref({ open: false, type: null, item: null })
const deleteLoading = ref(false)
const versions = ref([])
const viewMode = ref('list') // 'list' | 'gantt'
// Forces the version <select> to remount after each pick — a native
// select always visually locks onto whatever option the browser last
// selected, regardless of what its bound v-model value is reset to
// afterward (confirmed: resetting the bound value alone doesn't
// re-sync the DOM). Remounting via :key is what actually works.
const versionSelectKey = ref(0)
const makeCurrentLoading = ref(false)

// Tags
const tags = ref([])
const taskTags = ref([])
const activityTags = ref([])
const newTagName = ref('')
const tagLoading = ref(false)
const assignTarget = ref({}) // { [taskId or 'act-'+activityId]: tagId }

// Delete task/activity confirmations — deleting an activity cascades
// to every task still linked to it, backend does this without
// asking, so the confirmation has to live here.
const deleteItemModal = ref({ open: false, kind: null, item: null })
const deleteItemLoading = ref(false)

const downloadModal = ref({ open: false, format: 'json' })
const downloadLoading = ref(false)

// Category — the ONE structural field editable directly on this page
// (along with notes below); everything else about a template's
// content requires going through "Edit template".
const categories = ref([])
const categoryEditing = ref(false)
const categorySaving = ref(false)
const categoryDraft = ref('')
const creatingCategory = ref(false)
const newCategoryName = ref('')

// Notes on tasks/activities — also directly editable here, never
// forks a version (see TemplateTaskViewSet.note / TemplateActivityViewSet.note).
const noteModal = ref({ open: false, kind: null, item: null, text: '' })
const noteLoading = ref(false)

const templateId = computed(() => route.params.id)


async function loadTemplate() {
  loading.value = true
  error.value = ''
  try {
    const [tplRes, tasksRes, activitiesRes, depsRes, timelineRes, tagsRes, taskTagsRes, activityTagsRes, categoriesRes, versionsRes] = await Promise.all([
      getTemplate(templateId.value),
      getTemplateTasks(templateId.value),
      getTemplateActivities(templateId.value),
      getTaskDependencies(),
      getTemplateTimelinePreview(templateId.value),
      getTags(),
      getTaskTags(),
      getActivityTags(),
      getTemplateCategories(templateId.value),
      getTemplateVersions(templateId.value),
    ])
    template.value = tplRes.data
    versions.value = Array.isArray(versionsRes.data) ? versionsRes.data : (versionsRes.data.results || [])
    tasks.value = Array.isArray(tasksRes.data) ? tasksRes.data : (tasksRes.data.results || [])
    activities.value = Array.isArray(activitiesRes.data) ? activitiesRes.data : (activitiesRes.data.results || [])
    taskTagLinks.value = Array.isArray(taskTagsRes.data) ? taskTagsRes.data : (taskTagsRes.data.results || [])
    activityTagLinks.value = Array.isArray(activityTagsRes.data) ? activityTagsRes.data : (activityTagsRes.data.results || [])
    allTags.value = Array.isArray(tagsRes.data) ? tagsRes.data : (tagsRes.data.results || [])
    // Filter deps that belong to this template's tasks
    const taskIds = new Set(tasks.value.map(t => t.template_task_id))
    const allDeps = Array.isArray(depsRes.data) ? depsRes.data : (depsRes.data.results || [])
    dependencies.value = allDeps.filter(d => taskIds.has(d.task))
    timeline.value = timelineRes.data
    tags.value = Array.isArray(tagsRes.data) ? tagsRes.data : (tagsRes.data.results || [])
    const allTaskTags = Array.isArray(taskTagsRes.data) ? taskTagsRes.data : (taskTagsRes.data.results || [])
    taskTags.value = allTaskTags.filter(tt => taskIds.has(tt.template_task))
    const activityIds = new Set(activities.value.map(a => a.template_activity_id))
    const allActivityTags = Array.isArray(activityTagsRes.data) ? activityTagsRes.data : (activityTagsRes.data.results || [])
    activityTags.value = allActivityTags.filter(at => activityIds.has(at.template_activity))
    categories.value = Array.isArray(categoriesRes.data) ? categoriesRes.data : (categoriesRes.data.results || [])
  } catch (e) {
    error.value = getErrorMessage(e, 'Failed to load template. Please try again.')
  } finally {
    loading.value = false
  }
}

function getDependencyName(taskId) {
  const task = tasks.value.find(t => t.template_task_id === taskId)
  return task ? task.task_name : '—'
}

function tasksForActivity(activityId) {
  return tasks.value.filter(t => t.template_activity === activityId)
}

function formatReminders(val) {
  if (!val) return '—'
  if (Array.isArray(val)) {
    return val.map(d => d === 0 ? 'On the day' : `${d} days before`).join(', ')
  }
  return val === 0 ? 'On the day' : `${val} days before`
}

function tagNamesForTask(taskId) {
  const tagIds = taskTagLinks.value.filter(l => l.template_task === taskId).map(l => l.tag)
  return allTags.value.filter(t => tagIds.includes(t.tag_id)).map(t => t.tag_name)
}

function tagNamesForActivity(activityId) {
  const tagIds = activityTagLinks.value.filter(l => l.template_activity === activityId).map(l => l.tag)
  return allTags.value.filter(t => tagIds.includes(t.tag_id)).map(t => t.tag_name)
}


function onSwitchVersion(newId) {
  versionSelectKey.value++
  if (String(newId) === String(templateId.value)) return
  router.push({ name: 'template-detail', params: { id: newId } })
}

async function onMakeCurrent() {
  makeCurrentLoading.value = true
  try {
    await makeCurrentVersion(templateId.value)
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
    await duplicateTemplate(templateId.value)
    toast.success('Template duplicated.')
    router.push({ name: 'templates' })
  } catch (e) { toast.error(getErrorMessage(e, 'Failed to duplicate template.')) }
}

async function confirmDelete() {
  deleteLoading.value = true
  try {
    await deleteTemplate(templateId.value)
    toast.success('Template deleted.')
    router.push({ name: 'templates' })
  } catch (e) {
    toast.error(getErrorMessage(e, 'Failed to delete template.'))
  } finally {
    deleteLoading.value = false
  }
}

// ── CATEGORY (direct edit, no "Edit template" needed) ────────
// Changing the category still forks a new template version on the
// backend like any template field edit — everything on this page
// (tasks, activities, dependencies, tags) gets re-copied onto that
// new version too, so templateId is updated in place and the whole
// page is reloaded from the new id, never just patched locally.

function openCategoryEdit() {
  categoryDraft.value = template.value.category || ''
  categoryEditing.value = true
}

async function saveCategory() {
  categorySaving.value = true
  try {
    const { data } = await updateTemplate(templateId.value, { category: categoryDraft.value || null })
    const newId = data.template?.template_id
    categoryEditing.value = false
    if (newId) {
      templateId.value = newId
      router.replace({ name: 'template-detail', params: { id: newId } })
    }
    await loadTemplate()
    toast.success('Category updated.')
  } catch (e) {
    if (isPermissionError(e)) {
      toast.error("You don't have permission to modify this template.")
    } else {
      toast.error(getErrorMessage(e, 'Failed to update category.'))
    }
  } finally {
    categorySaving.value = false
  }
}

async function onCreateCategoryInline() {
  const name = newCategoryName.value.trim()
  if (!name) return
  categorySaving.value = true
  try {
    const { data } = await createTemplateCategory({ category_name: name })
    categories.value = [...categories.value, data]
    categoryDraft.value = data.category_id
    creatingCategory.value = false
    toast.success('Category created.')
  } catch (e) {
    toast.error(getErrorMessage(e, 'Failed to create category.'))
  } finally {
    categorySaving.value = false
  }
}

// ── TASK / ACTIVITY NOTES (direct edit, never forks a version) ──

function openNoteModal(kind, item) {
  noteModal.value = { open: true, kind, item, text: item.note_text || '' }
}

async function saveNote() {
  const { kind, item, text } = noteModal.value
  noteLoading.value = true
  try {
    const id = kind === 'task' ? item.template_task_id : item.template_activity_id
    if (!text.trim()) {
      kind === 'task' ? await clearTemplateTaskNote(id) : await clearTemplateActivityNote(id)
    } else {
      kind === 'task' ? await setTemplateTaskNote(id, text.trim()) : await setTemplateActivityNote(id, text.trim())
    }
    noteModal.value.open = false
    await loadTemplate()
    toast.success('Note saved.')
  } catch (e) {
    if (isPermissionError(e)) {
      toast.error("You don't have permission to modify this template.")
    } else {
      toast.error(getErrorMessage(e, 'Failed to save note.'))
    }
  } finally {
    noteLoading.value = false
  }
}

// ── TASK / ACTIVITY DELETE ──────────────────────────────────

function openDeleteItem(kind, item) {
  deleteItemModal.value = { open: true, kind, item }
}

async function confirmDeleteItem() {
  const { kind, item } = deleteItemModal.value
  deleteItemLoading.value = true
  try {
    if (kind === 'task') {
      await deleteTemplateTask(item.template_task_id)
      toast.success('Task removed. A new template version was created.')
    } else {
      await deleteTemplateActivity(item.template_activity_id)
      toast.success('Activity and its tasks removed. A new template version was created.')
    }
    deleteItemModal.value.open = false
    // Deleting forks a new template version — the id in the URL is
    // now frozen history, so jump to whatever version is current now.
    router.push({ name: 'templates' })
  } catch (e) {
    if (isPermissionError(e)) {
      toast.error("You don't have permission to modify this template.")
    } else {
      toast.error(getErrorMessage(e, `Failed to delete this ${kind}.`))
    }
  } finally {
    deleteItemLoading.value = false
  }
}

// ── TAGS ─────────────────────────────────────────────────────

// A starter set offered only while the user has no tags of their
// own yet — the backend has no "default"/global tag concept (Tag is
// always owned by a user), so these are just suggestions that create
// a real Tag row the moment one is picked, same as typing a custom
// name below.
const DEFAULT_TAG_SUGGESTIONS = ['Important', 'Urgent', 'Optional', 'Review', 'Blocked']
const addingSuggestion = ref('')

const suggestedTags = computed(() => {
  const existingNames = new Set(tags.value.map(t => t.tag_name.toLowerCase()))
  return DEFAULT_TAG_SUGGESTIONS.filter(name => !existingNames.has(name.toLowerCase()))
})

async function createTagByName(name) {
  await createTag({ tag_name: name })
  const { data } = await getTags()
  tags.value = Array.isArray(data) ? data : (data.results || [])
}

async function onCreateTag() {
  const name = newTagName.value.trim()
  if (!name) return
  tagLoading.value = true
  try {
    await createTagByName(name)
    newTagName.value = ''
    toast.success('Tag created.')
  } catch (e) {
    toast.error(getErrorMessage(e, 'Failed to create tag.'))
  } finally {
    tagLoading.value = false
  }
}

async function onAddSuggestedTag(name) {
  addingSuggestion.value = name
  try {
    await createTagByName(name)
    toast.success(`"${name}" tag added.`)
  } catch (e) {
    toast.error(getErrorMessage(e, 'Failed to add this tag.'))
  } finally {
    addingSuggestion.value = ''
  }
}

function tagsForTask(taskId) {
  return taskTags.value
    .filter(tt => tt.template_task === taskId)
    .map(tt => ({ assignmentId: tt.template_task_tag_id, ...tags.value.find(t => t.tag_id === tt.tag) }))
    .filter(t => t.tag_id !== undefined)
}

function tagsForActivity(activityId) {
  return activityTags.value
    .filter(at => at.template_activity === activityId)
    .map(at => ({ assignmentId: at.template_activity_tag_id, ...tags.value.find(t => t.tag_id === at.tag) }))
    .filter(t => t.tag_id !== undefined)
}

async function onAssignTaskTag(taskId) {
  const tagId = assignTarget.value[taskId]
  if (!tagId) return
  try {
    await assignTagToTask(taskId, tagId)
    assignTarget.value[taskId] = ''
    const { data } = await getTaskTags()
    const allTaskTags = Array.isArray(data) ? data : (data.results || [])
    const taskIds = new Set(tasks.value.map(t => t.template_task_id))
    taskTags.value = allTaskTags.filter(tt => taskIds.has(tt.template_task))
  } catch (e) {
    toast.error(getErrorMessage(e, 'Failed to assign tag.'))
  }
}

async function onRemoveTaskTag(assignmentId) {
  try {
    await unassignTagFromTask(assignmentId)
    taskTags.value = taskTags.value.filter(tt => tt.template_task_tag_id !== assignmentId)
  } catch (e) {
    toast.error(getErrorMessage(e, 'Failed to remove tag.'))
  }
}

async function onAssignActivityTag(activityId) {
  const key = 'act-' + activityId
  const tagId = assignTarget.value[key]
  if (!tagId) return
  try {
    await assignTagToActivity(activityId, tagId)
    assignTarget.value[key] = ''
    const { data } = await getActivityTags()
    const allActivityTags = Array.isArray(data) ? data : (data.results || [])
    const activityIds = new Set(activities.value.map(a => a.template_activity_id))
    activityTags.value = allActivityTags.filter(at => activityIds.has(at.template_activity))
  } catch (e) {
    toast.error(getErrorMessage(e, 'Failed to assign tag.'))
  }
}

async function onRemoveActivityTag(assignmentId) {
  try {
    await unassignTagFromActivity(assignmentId)
    activityTags.value = activityTags.value.filter(at => at.template_activity_tag_id !== assignmentId)
  } catch (e) {
    toast.error(getErrorMessage(e, 'Failed to remove tag.'))
  }
}

// ── EXPORT / DOWNLOAD ─────────────────────────────────────────

async function confirmDownload() {
  downloadLoading.value = true
  try {
    const { data } = await downloadTemplate(templateId.value, downloadModal.value.format)
    const blob = new Blob([data])
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    const safeName = (template.value?.template_name || 'template').replace(/[^a-z0-9 _-]/gi, '_')
    a.href = url
    a.download = `${safeName}_v${template.value?.template_version || 1}.${downloadModal.value.format}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
    downloadModal.value.open = false
    toast.success('Download started.')
  } catch (e) {
    toast.error(getErrorMessage(e, 'Failed to export this template.'))
  } finally {
    downloadLoading.value = false
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
  const taskBars = sortedTaskBars.map(b => ({
    name: b.name,
    start: b.start,
    end: b.end,
    isMandatory: b.is_mandatory,
    isFixed: b.is_fixed_date,
    depName: b.dep_name,
    activityId: b.template_activity_id,
  }))
  // Resolve each bar's dependsOnIndex AFTER sorting — the index has
  // to point at the prerequisite's position in THIS final order, not
  // wherever it sat in the backend's original list.
  taskBars.forEach(bar => {
    const idx = bar.depName ? taskBars.findIndex(b => b.name === bar.depName) : -1
    bar.dependsOnIndex = idx !== -1 ? idx : null
  })
  return {
    taskBars,
    activityBars: timeline.value.activity_bars.map(b => ({
      id: b.template_activity_id,
      name: b.name,
      start: b.start,
      end: b.end,
    })),
    maxDay: timeline.value.max_day,
  }
})
watch(() => route.params.id, loadTemplate)

onMounted(async () => {
  await loadTemplate()
  onboardingStore.maybeAutoStart('template-detail')
})
</script>

<template>
  <AppLayout>
    <template #topbar>
      <div class="breadcrumb">
        <span class="breadcrumb-link" @click="router.push({ name: 'templates' })">Templates</span>
        <span class="breadcrumb-sep">›</span>
        <span class="breadcrumb-current">{{ template?.template_name || 'Loading...' }}</span>
      </div>
      <div style="margin-left: auto; display: flex; gap: 10px; align-items: center;">
        <button type="button" class="page-help-btn" title="Show tips for this page" @click="onboardingStore.startTour('template-detail')">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        </button>
        <BaseButton variant="primary" size="sm" data-tour="tpl-detail-edit" @click="router.push({ name: 'template-edit', params: { id: templateId } })">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
          Edit template
        </BaseButton>
        <div class="row-menu" data-tour="tpl-detail-actions" @click.stop>
          <button type="button" class="row-menu-trigger" @click="toggleMenu('template-actions')">
            <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>
          </button>
          <div v-if="openMenuFor === 'template-actions'" class="row-menu-dropdown">
            <button type="button" class="row-menu-item" @click="downloadModal = { open: true, format: 'json' }; openMenuFor = null">Export</button>
            <button type="button" class="row-menu-item" @click="onDuplicate(); openMenuFor = null">Duplicate</button>
            <button type="button" class="row-menu-item row-menu-item-danger" @click="deleteModalOpen = true; openMenuFor = null">Delete</button>
          </div>
        </div>
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
                :key="versionSelectKey"
                class="version-select"
                data-tour="tpl-detail-versions"
                :model-value="''"
                @update:model-value="(v) => { if (v) onSwitchVersion(v) }"
              >
                <option value="" disabled>Other versions</option>
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

          <!-- CATEGORY: the one field editable directly here, no need to open Edit template -->
          <div class="category-row">
            <span class="category-label">Category</span>
            <template v-if="!categoryEditing">
              <span v-if="template.category_name" class="meta-pill pill-category">{{ template.category_name }}</span>
              <span v-else class="category-none">Uncategorised</span>
              <button type="button" class="category-edit-btn" @click="openCategoryEdit">Change</button>
            </template>
            <template v-else-if="creatingCategory">
              <BaseInput v-model="newCategoryName" placeholder="New category name" class="category-select" @keyup.enter="onCreateCategoryInline" />
              <BaseButton variant="primary" size="sm" :loading="categorySaving" @click="onCreateCategoryInline">Create</BaseButton>
              <BaseButton variant="secondary" size="sm" :disabled="categorySaving" @click="creatingCategory = false">Cancel</BaseButton>
            </template>
            <template v-else>
              <BaseSelect v-model="categoryDraft" class="category-select" @update:model-value="(v) => { if (v === '__new__') { creatingCategory = true; newCategoryName = '' } }">
                <option value="">Uncategorised</option>
                <option v-for="c in categories" :key="c.category_id" :value="c.category_id">{{ c.category_name }}</option>
                <option value="__new__">+ Create new category…</option>
              </BaseSelect>
              <BaseButton variant="primary" size="sm" :loading="categorySaving" @click="saveCategory">Save</BaseButton>
              <BaseButton variant="secondary" size="sm" :disabled="categorySaving" @click="categoryEditing = false">Cancel</BaseButton>
            </template>
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

        <!-- VIEW MODE TOGGLE -->
        <div class="view-toggle-bar" data-tour="tpl-detail-view-toggle">
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
        </div>

        <!-- GANTT VIEW -->
        <div v-if="viewMode === 'gantt'" class="gantt-card">
          <div class="gantt-header">Timeline</div>
          <div v-if="!ganttData" class="gantt-empty">No tasks or activities to display.</div>
          <GanttChart
            v-else
            :task-bars="ganttData.taskBars"
            :activity-bars="ganttData.activityBars"
            :max-day="ganttData.maxDay"
            :px-per-day="32"
          />
        </div>

        <!-- LIST VIEW -->
        <div v-else class="two-col">

          <!-- LEFT -->
          <div class="col-main">

	  <!-- ACTIVITIES + their linked tasks, nested; unlinked tasks at the end -->
            <div class="section-card" v-if="tasks.length > 0 || activities.length > 0" data-tour="tpl-detail-list">
              <div class="section-header">
                <div class="section-title">Tasks & Activities</div>
                <span class="section-count">{{ tasks.length + activities.length }}</span>
              </div>
              <div class="task-list">
                <template v-for="act in activities" :key="'act-' + act.template_activity_id">
                  <div class="task-row">
                    <div class="task-row-left">
                      <div class="task-day-badge activity-badge">Day {{ act.start_offset_days }}–{{ act.end_offset_days }}</div>
                      <div style="flex:1; min-width:0;">
                        <div class="task-name">{{ act.activity_name }}</div>
                        <div class="task-meta">Spans {{ act.end_offset_days - act.start_offset_days }} days</div>
                        <div v-if="act.description" class="task-desc">{{ act.description }}</div>
                        <div v-if="act.note_text" class="task-note">{{ act.note_text }}</div>

                        <!-- TAGS -->
                        <div class="tag-row">
                          <span v-for="tag in tagsForActivity(act.template_activity_id)" :key="tag.assignmentId" class="tag-chip">
                            {{ tag.tag_name }}
                            <button type="button" class="tag-remove" @click="onRemoveActivityTag(tag.assignmentId)">×</button>
                          </span>
                          <BaseSelect v-model="assignTarget['act-' + act.template_activity_id]" class="tag-assign-select">
                            <option value="">+ Add tag</option>
                            <option v-for="t in tags" :key="t.tag_id" :value="t.tag_id">{{ t.tag_name }}</option>
                          </BaseSelect>
                          <button type="button" class="tag-assign-btn" @click="onAssignActivityTag(act.template_activity_id)">Add</button>
                        </div>
                      </div>
                      <div class="row-menu" @click.stop>
                        <button type="button" class="row-menu-trigger" @click="toggleMenu('activity-' + act.template_activity_id)">
                          <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>
                        </button>
                        <div v-if="openMenuFor === 'activity-' + act.template_activity_id" class="row-menu-dropdown">
                          <button type="button" class="row-menu-item" @click="openNoteModal('activity', act); openMenuFor = null">{{ act.note_text ? 'Edit note' : 'Add note' }}</button>
                          <button type="button" class="row-menu-item row-menu-item-danger" @click="openDeleteItem('activity', act); openMenuFor = null">Delete activity</button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div v-for="task in tasksForActivity(act.template_activity_id)" :key="task.template_task_id" class="task-row task-row-nested">
                    <div class="task-row-left">
                      <div class="task-day-badge">Day {{ task.day_offset }}</div>
                      <div style="flex:1; min-width:0;">
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
                        <div v-if="task.note_text" class="task-note">{{ task.note_text }}</div>
                        <div v-if="dependencies.find(d => d.task === task.template_task_id)" class="task-dep">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/>
                            <path d="M18 9a9 9 0 0 1-9 9"/>
                          </svg>
                          Depends on: {{ getDependencyName(dependencies.find(d => d.task === task.template_task_id).depends_on_task) }}
                        </div>

                        <!-- TAGS -->
                        <div class="tag-row">
                          <span v-for="tag in tagsForTask(task.template_task_id)" :key="tag.assignmentId" class="tag-chip">
                            {{ tag.tag_name }}
                            <button type="button" class="tag-remove" @click="onRemoveTaskTag(tag.assignmentId)">×</button>
                          </span>
                          <BaseSelect v-model="assignTarget[task.template_task_id]" class="tag-assign-select">
                            <option value="">+ Add tag</option>
                            <option v-for="t in tags" :key="t.tag_id" :value="t.tag_id">{{ t.tag_name }}</option>
                          </BaseSelect>
                          <button type="button" class="tag-assign-btn" @click="onAssignTaskTag(task.template_task_id)">Add</button>
                        </div>
                      </div>
                      <div class="row-menu" @click.stop>
                        <button type="button" class="row-menu-trigger" @click="toggleMenu('task-' + task.template_task_id)">
                          <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>
                        </button>
                        <div v-if="openMenuFor === 'task-' + task.template_task_id" class="row-menu-dropdown">
                          <button type="button" class="row-menu-item" @click="openNoteModal('task', task); openMenuFor = null">{{ task.note_text ? 'Edit note' : 'Add note' }}</button>
                          <button type="button" class="row-menu-item row-menu-item-danger" @click="openDeleteItem('task', task); openMenuFor = null">Delete task</button>
                        </div>
                      </div>
                    </div>
                  </div>
                </template>

                <!-- UNLINKED TASKS (no activity) -->
                <div v-for="task in tasks.filter(t => !t.template_activity)" :key="task.template_task_id" class="task-row">
                  <div class="task-row-left">
                    <div class="task-day-badge">Day {{ task.day_offset }}</div>
                    <div style="flex:1; min-width:0;">
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
                      <div v-if="task.note_text" class="task-note">{{ task.note_text }}</div>
                      <div v-if="dependencies.find(d => d.task === task.template_task_id)" class="task-dep">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/>
                          <path d="M18 9a9 9 0 0 1-9 9"/>
                        </svg>
                        Depends on: {{ getDependencyName(dependencies.find(d => d.task === task.template_task_id).depends_on_task) }}
                      </div>

                      <!-- TAGS -->
                      <div class="tag-row">
                        <span v-for="tag in tagsForTask(task.template_task_id)" :key="tag.assignmentId" class="tag-chip">
                          {{ tag.tag_name }}
                          <button type="button" class="tag-remove" @click="onRemoveTaskTag(tag.assignmentId)">×</button>
                        </span>
                        <BaseSelect v-model="assignTarget[task.template_task_id]" class="tag-assign-select">
                          <option value="">+ Add tag</option>
                          <option v-for="t in tags" :key="t.tag_id" :value="t.tag_id">{{ t.tag_name }}</option>
                        </BaseSelect>
                        <button type="button" class="tag-assign-btn" @click="onAssignTaskTag(task.template_task_id)">Add</button>
                      </div>
                    </div>
                    <div class="row-menu" @click.stop>
                      <button type="button" class="row-menu-trigger" @click="toggleMenu('task-' + task.template_task_id)">
                        <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>
                      </button>
                      <div v-if="openMenuFor === 'task-' + task.template_task_id" class="row-menu-dropdown">
                        <button type="button" class="row-menu-item" @click="openNoteModal('task', task); openMenuFor = null">{{ task.note_text ? 'Edit note' : 'Add note' }}</button>
                        <button type="button" class="row-menu-item row-menu-item-danger" @click="openDeleteItem('task', task); openMenuFor = null">Delete task</button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="tasks.length === 0 && activities.length === 0" class="empty-card">
              No tasks or activities defined. Click Edit template to add some.
            </div>

            <!-- TAG MANAGEMENT -->
            <div class="section-card">
              <div class="section-header">
                <div class="section-title">Tags</div>
                <span class="section-count">{{ tags.length }}</span>
              </div>
              <div class="tag-manage-body">
                <span v-if="tags.length === 0 && suggestedTags.length === 0" class="task-meta">No tags yet — create one below, then attach it to any task or activity above.</span>
                <span v-for="t in tags" :key="t.tag_id" class="tag-chip">{{ t.tag_name }}</span>
                <div class="tag-create-row">
                  <BaseInput v-model="newTagName" placeholder="New tag name" @keyup.enter="onCreateTag" />
                  <BaseButton variant="secondary" size="sm" :loading="tagLoading" @click="onCreateTag">Create tag</BaseButton>
                </div>
              </div>
              <div v-if="suggestedTags.length > 0" class="tag-suggestions-row">
                <span class="tag-suggestions-label">Quick add:</span>
                <button
                  v-for="name in suggestedTags"
                  :key="name"
                  type="button"
                  class="tag-suggestion-chip"
                  :disabled="addingSuggestion === name"
                  @click="onAddSuggestedTag(name)"
                >
                  + {{ name }}
                </button>
              </div>
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
      <p class="delete-warning-note">
        Any cycles already created from this template are kept — they'll stay visible on the
        Cycles page with their history intact. Any that are still <strong>running will be shut
        down</strong> as part of this delete, since they'll no longer have a template to
        validate against.
      </p>
    </BaseModal>

    <!-- DELETE TASK/ACTIVITY CONFIRM MODAL -->
    <BaseModal
      v-model="deleteItemModal.open"
      :title="deleteItemModal.kind === 'activity' ? 'Delete activity?' : 'Delete task?'"
      confirm-label="Delete"
      confirm-variant="danger"
      :loading="deleteItemLoading"
      @confirm="confirmDeleteItem"
    >
      <p v-if="deleteItemModal.kind === 'activity'">
        Deleting <strong>{{ deleteItemModal.item?.activity_name }}</strong> will also delete every task still linked
        to it. This cannot be undone, and creates a new template version.
      </p>
      <p v-else>
        Deleting <strong>{{ deleteItemModal.item?.task_name }}</strong> will also remove any dependency
        connected to it. This cannot be undone, and creates a new template version.
      </p>
    </BaseModal>

    <!-- DOWNLOAD MODAL -->
    <BaseModal
      v-model="downloadModal.open"
      title="Export template"
      confirm-label="Download"
      :loading="downloadLoading"
      @confirm="confirmDownload"
    >
      <BaseSelect v-model="downloadModal.format" label="File format">
        <option value="json">JSON</option>
        <option value="csv">CSV</option>
        <option value="xlsx">Excel (.xlsx)</option>
      </BaseSelect>
    </BaseModal>

    <!-- NOTE EDITOR MODAL (tasks and activities) -->
    <BaseModal
      v-model="noteModal.open"
      :title="noteModal.kind === 'task' ? 'Task note' : 'Activity note'"
      confirm-label="Save note"
      :loading="noteLoading"
      @confirm="saveNote"
    >
      <label class="field-label-modal">Note</label>
      <textarea v-model="noteModal.text" class="note-textarea" rows="4" placeholder="Add a note..."></textarea>
      <p class="modal-hint">Leaving this empty and saving removes the note. Notes never create a new template version.</p>
    </BaseModal>

    <!-- TASK / ACTIVITY DETAIL MODAL -->
    <BaseModal
      v-model="detailModal.open"
      :title="detailModal.type === 'task' ? detailModal.item?.task_name : detailModal.item?.activity_name"
    >
      <div v-if="detailModal.item" class="detail-view">

        <template v-if="detailModal.type === 'task'">
          <div class="detail-row"><span class="detail-label">Day offset</span><span class="detail-value">Day {{ detailModal.item.day_offset }}</span></div>
          <div class="detail-row"><span class="detail-label">Duration</span><span class="detail-value">{{ detailModal.item.duration_days || 1 }} day{{ detailModal.item.duration_days > 1 ? 's' : '' }}</span></div>
          <div class="detail-row"><span class="detail-label">Mandatory</span><span class="detail-value">{{ detailModal.item.is_mandatory ? 'Yes' : 'No' }}</span></div>
          <div class="detail-row"><span class="detail-label">Fixed date</span><span class="detail-value">{{ detailModal.item.is_fixed_date ? 'Yes' : 'No' }}</span></div>
          <div class="detail-row"><span class="detail-label">Reminders</span><span class="detail-value">{{ formatReminders(detailModal.item.reminder_lead_days) }}</span></div>
          <div v-if="activities.find(a => a.template_activity_id === detailModal.item.template_activity)" class="detail-row">
            <span class="detail-label">Linked activity</span>
            <span class="detail-value">{{ activities.find(a => a.template_activity_id === detailModal.item.template_activity).activity_name }}</span>
          </div>
          <div v-if="dependencies.find(d => d.task === detailModal.item.template_task_id)" class="detail-row">
            <span class="detail-label">Depends on</span>
            <span class="detail-value">{{ getDependencyName(dependencies.find(d => d.task === detailModal.item.template_task_id).depends_on_task) }}</span>
          </div>
          <div v-if="detailModal.item.description" class="detail-block">
            <div class="detail-block-label">Description</div>
            <p class="detail-block-text">{{ detailModal.item.description }}</p>
          </div>
          <div v-if="detailModal.item.note_text" class="detail-block">
            <div class="detail-block-label">Note</div>
            <p class="detail-block-text">{{ detailModal.item.note_text }}</p>
          </div>
          <div v-if="tagNamesForTask(detailModal.item.template_task_id).length > 0" class="detail-block">
            <div class="detail-block-label">Tags</div>
            <div class="detail-tags">
              <span v-for="name in tagNamesForTask(detailModal.item.template_task_id)" :key="name" class="detail-tag">{{ name }}</span>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="detail-row"><span class="detail-label">Start day</span><span class="detail-value">Day {{ detailModal.item.start_offset_days }}</span></div>
          <div class="detail-row"><span class="detail-label">End day</span><span class="detail-value">Day {{ detailModal.item.end_offset_days }}</span></div>
          <div class="detail-row"><span class="detail-label">Spans</span><span class="detail-value">{{ detailModal.item.end_offset_days - detailModal.item.start_offset_days }} days</span></div>
          <div class="detail-row"><span class="detail-label">Linked tasks</span><span class="detail-value">{{ tasks.filter(t => t.template_activity === detailModal.item.template_activity_id).length }}</span></div>
          <div v-if="detailModal.item.description" class="detail-block">
            <div class="detail-block-label">Description</div>
            <p class="detail-block-text">{{ detailModal.item.description }}</p>
          </div>
          <div v-if="detailModal.item.note_text" class="detail-block">
            <div class="detail-block-label">Note</div>
            <p class="detail-block-text">{{ detailModal.item.note_text }}</p>
          </div>
          <div v-if="tagNamesForActivity(detailModal.item.template_activity_id).length > 0" class="detail-block">
            <div class="detail-block-label">Tags</div>
            <div class="detail-tags">
              <span v-for="name in tagNamesForActivity(detailModal.item.template_activity_id)" :key="name" class="detail-tag">{{ name }}</span>
            </div>
          </div>
        </template>

      </div>

      <template #footer>
        <BaseButton variant="secondary" @click="detailModal.open = false">Close</BaseButton>
      </template>
    </BaseModal>

  </AppLayout>
</template>

<style scoped>
.delete-warning-note {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
  font-size: var(--font-hint);
  color: var(--text-muted);
  line-height: 1.5;
}
.breadcrumb { display: flex; align-items: center; gap: 6px; font-size: var(--font-label); }
.breadcrumb-link { color: var(--text-muted); cursor: pointer; }
.breadcrumb-link:hover { color: var(--violet); }
.breadcrumb-sep { color: var(--text-muted); }
.breadcrumb-current { color: var(--text-primary); font-weight: 500; }
.page-help-btn { width: 34px; height: 34px; border-radius: var(--radius-md); border: 1px solid var(--border-light); background: var(--white); display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-muted); }
.page-help-btn:hover { background: var(--violet-bg); color: var(--violet); }

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
.category-row { display: flex; align-items: center; gap: 10px; padding-top: 14px; margin-top: 14px; border-top: 1px solid var(--border-light); }
.category-label { font-size: var(--font-hint); font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
.pill-category { background: var(--info-bg); color: #1D4ED8; }
.category-none { font-size: var(--font-label); color: var(--text-muted); font-style: italic; }
.category-edit-btn { font-size: var(--font-label); font-weight: 600; color: var(--violet); background: none; border: none; cursor: pointer; font-family: var(--font-main); padding: 0; }
.category-edit-btn:hover { text-decoration: underline; }
.category-select { width: 220px; }
.category-select :deep(.base-select) { height: 34px; }

.meta-row { display: flex; gap: 32px; padding-top: 16px; border-top: 1px solid var(--border-light); }
.meta-label { font-size: var(--font-hint); text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); margin-bottom: 3px; }
.meta-value { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); }

/* TWO COL */
/* ── VIEW TOGGLE ── */
.view-toggle-bar { display: flex; align-items: center; }
.view-toggle { display: flex; align-items: center; gap: 4px; background: var(--bg-page); border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 3px; }
.view-toggle-btn { display: flex; align-items: center; gap: 6px; padding: 6px 14px; border: none; border-radius: 6px; background: transparent; color: var(--text-secondary); font-size: var(--font-label); font-weight: 500; font-family: var(--font-main); cursor: pointer; transition: background var(--transition-fast), color var(--transition-fast); }
.view-toggle-btn.active { background: var(--white); color: var(--violet); box-shadow: var(--shadow-sm); }
.view-toggle-btn:hover:not(.active) { color: var(--text-primary); }

.two-col { display: flex; gap: 20px; align-items: flex-start; }
.col-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 16px; }
.col-side { width: 380px; flex-shrink: 0; position: sticky; top: 80px; }

/* SECTION CARDS */
.section-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); overflow: hidden; }
.section-header { display: flex; align-items: center; gap: 10px; padding: 14px 20px; border-bottom: 1px solid var(--border-light); }
.section-title { font-size: var(--font-label); font-weight: 600; color: var(--text-primary); flex: 1; }
.section-count { font-size: var(--font-upper); font-weight: 600; background: var(--violet-bg); color: var(--violet); padding: 2px 10px; border-radius: 20px; }

.task-list { display: flex; flex-direction: column; }
.task-row { display: flex; padding: 14px 20px; border-bottom: 1px solid var(--border-light); cursor: pointer; transition: background var(--transition-fast); }
.task-row-nested { padding-left: 48px; background: var(--bg-page); }
.task-row:last-child { border-bottom: none; }
.task-row:hover { background: var(--bg-page); }
.task-row-linked { padding-left: 44px; }
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


/* ── ROW OVERFLOW MENU ──
   Secondary per-row actions (note, delete) collapse behind a "⋯"
   trigger instead of sitting as always-visible buttons. */
.row-menu { position: relative; flex-shrink: 0; }
.row-menu-trigger {
  width: 28px;
  height: 28px;
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
.row-menu-trigger svg { width: 15px; height: 15px; }
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
.row-menu-item-danger { color: var(--danger); }
.row-menu-item-danger:hover { background: var(--danger-bg); }

.task-note { font-size: var(--font-label); color: var(--text-secondary); margin-top: 4px; font-style: italic; }

.field-label-modal { display: block; font-size: var(--font-label); font-weight: 500; color: var(--text-primary); margin-bottom: 6px; }
.note-textarea { width: 100%; padding: 9px 12px; border: 1px solid var(--border-light); border-radius: var(--radius-md); font-family: var(--font-main); font-size: var(--font-label); color: var(--text-primary); resize: vertical; box-sizing: border-box; }
.note-textarea:focus { outline: none; border-color: var(--violet); }
.modal-hint { font-size: var(--font-label); color: var(--text-muted); margin: 6px 0 0; line-height: 1.5; }

/* TAGS */
.tag-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.tag-chip { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-upper); font-weight: 500; background: var(--violet-bg); color: var(--violet); padding: 3px 9px; border-radius: 20px; }
.tag-remove { border: none; background: transparent; color: var(--violet); cursor: pointer; font-size: 13px; line-height: 1; padding: 0; }
.tag-assign-select :deep(.base-select) { height: 28px; font-size: var(--font-hint); padding: 0 22px 0 8px; }
.tag-assign-select { width: 130px; }
.tag-assign-btn { font-size: var(--font-hint); font-weight: 600; color: var(--violet); background: var(--white); border: 1px solid var(--border-light); border-radius: 6px; padding: 4px 10px; cursor: pointer; font-family: var(--font-main); }
.tag-assign-btn:hover { background: var(--violet-bg); }

.tag-manage-body { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 14px 20px; }
.tag-create-row { display: flex; align-items: flex-end; gap: 8px; margin-left: auto; }
.tag-create-row :deep(.base-input-group) { margin-bottom: 0; }

.tag-suggestions-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 0 20px 14px; }
.tag-suggestions-label { font-size: var(--font-hint); color: var(--text-muted); margin-right: 2px; }
.tag-suggestion-chip { font-size: var(--font-upper); font-weight: 500; color: var(--text-secondary); background: var(--bg-page); border: 1px dashed var(--border); border-radius: 20px; padding: 3px 10px; cursor: pointer; font-family: var(--font-main); transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast); }
.tag-suggestion-chip:hover:not(:disabled) { background: var(--violet-bg); color: var(--violet); border-color: #DDD6FE; }
.tag-suggestion-chip:disabled { opacity: 0.5; cursor: default; }

/* GANTT */
.gantt-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); overflow: hidden; }
.gantt-header { padding: 14px 18px; font-size: var(--font-label); font-weight: 600; color: var(--text-primary); border-bottom: 1px solid var(--border-light); }
.gantt-empty { padding: 40px 18px; font-size: var(--font-label); color: var(--text-muted); text-align: center; }

</style>