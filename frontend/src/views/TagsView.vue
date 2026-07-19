<!-- /frontend/src/views/TagsView.vue -->

<script setup>
import { ref, onMounted } from 'vue'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import { useToastStore } from '@/stores/toast'
import { useOnboardingStore } from '@/stores/onboarding'
import { getTags, createTag, editTag, deleteTag } from '@/api/templates'
import { getErrorMessage } from '@/utils/apiErrors'

const toast = useToastStore()
const onboardingStore = useOnboardingStore()

const tags = ref([])
const loading = ref(true)
const error = ref('')

const newTagName = ref('')
const createLoading = ref(false)

const editModal = ref({ open: false, tag: null, name: '' })
const editLoading = ref(false)
const editError = ref('')

const deleteModal = ref({ open: false, tag: null })
const deleteLoading = ref(false)

async function loadTags() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getTags()
    tags.value = Array.isArray(data) ? data : (data.results || [])
  } catch (e) {
    error.value = getErrorMessage(e, 'Failed to load tags. Please try again.')
  } finally {
    loading.value = false
  }
}

async function onCreateTag() {
  const name = newTagName.value.trim()
  if (!name) return
  createLoading.value = true
  try {
    await createTag({ tag_name: name })
    newTagName.value = ''
    await loadTags()
    toast.success('Tag created.')
  } catch (e) {
    toast.error(getErrorMessage(e, 'Failed to create tag.'))
  } finally {
    createLoading.value = false
  }
}

function openEditModal(tag) {
  editModal.value = { open: true, tag, name: tag.tag_name }
  editError.value = ''
}

async function confirmEdit() {
  const name = editModal.value.name.trim()
  if (!name) {
    editError.value = 'Tag name cannot be empty.'
    return
  }
  editLoading.value = true
  editError.value = ''
  try {
    await editTag(editModal.value.tag.tag_id, name)
    editModal.value.open = false
    await loadTags()
    toast.success('New tag created. The previous tag and everything already tagged with it are unchanged.')
  } catch (e) {
    editError.value = getErrorMessage(e, 'Failed to create the renamed tag.')
  } finally {
    editLoading.value = false
  }
}

function openDeleteModal(tag) {
  deleteModal.value = { open: true, tag }
}

async function confirmDelete() {
  deleteLoading.value = true
  try {
    await deleteTag(deleteModal.value.tag.tag_id)
    deleteModal.value.open = false
    await loadTags()
    toast.success('Tag deleted.')
  } catch (e) {
    // Most common case here: the backend blocks deletion because the
    // tag is still assigned to at least one task or activity.
    toast.error(getErrorMessage(e, 'Failed to delete tag.'))
  } finally {
    deleteLoading.value = false
  }
}

onMounted(async () => {
  await loadTags()
  onboardingStore.maybeAutoStart('tags')
})
</script>

<template>
  <AppLayout>
    <template #topbar>
      <span class="topbar-title">Tags</span>
      <button type="button" class="page-help-btn" title="Show tips for this page" style="margin-left: auto;" @click="onboardingStore.startTour('tags')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
      </button>
    </template>

    <div class="tags-page">
      <p class="page-desc">
        Tags help you find and filter tasks and activities across templates. Renaming a tag
        creates a new one — the original and everything already tagged with it stay exactly
        as they were. A tag can only be deleted once nothing is tagged with it anymore.
      </p>

      <!-- CREATE -->
      <div class="create-card" data-tour="tags-create">
        <BaseInput
          v-model="newTagName"
          placeholder="New tag name, e.g. Important"
          @keyup.enter="onCreateTag"
        />
        <BaseButton variant="primary" size="sm" :loading="createLoading" @click="onCreateTag">
          Create tag
        </BaseButton>
      </div>

      <div v-if="loading" class="loading-msg">Loading tags...</div>
      <div v-else-if="error" class="error-banner">{{ error }}</div>

      <div v-else-if="tags.length === 0" class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20.59 13.41 13.42 20.58a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><circle cx="7" cy="7" r="1.5"/>
        </svg>
        <p>No tags yet. Create your first one above.</p>
      </div>

      <!-- LIST -->
      <div v-else class="tag-list" data-tour="tags-list">
        <div v-for="tag in tags" :key="tag.tag_id" class="tag-row">
          <div class="tag-row-left">
            <span class="tag-chip-lg">{{ tag.tag_name }}</span>
            <span class="tag-usage">
              {{ tag.usage_count }} task{{ tag.usage_count !== 1 ? 's' : '' }}/activity assignment{{ tag.usage_count !== 1 ? 's' : '' }}
            </span>
          </div>
          <div class="tag-row-actions">
            <button type="button" class="tag-action-btn" @click="openEditModal(tag)">Rename</button>
            <button
              type="button"
              class="tag-action-btn tag-action-danger"
              :disabled="tag.usage_count > 0"
              :title="tag.usage_count > 0 ? 'Remove this tag from every task/activity first' : ''"
              @click="openDeleteModal(tag)"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- EDIT (RENAME -> NEW TAG) MODAL -->
    <BaseModal
      v-model="editModal.open"
      title="Rename tag"
      confirm-label="Create renamed tag"
      :loading="editLoading"
      @confirm="confirmEdit"
    >
      <p class="modal-hint">
        This creates a brand new tag with the new name. "{{ editModal.tag?.tag_name }}" and
        everything already tagged with it will stay unchanged.
      </p>
      <BaseInput v-model="editModal.name" label="New name" :error="editError" @keyup.enter="confirmEdit" />
    </BaseModal>

    <!-- DELETE CONFIRM MODAL -->
    <BaseModal
      v-model="deleteModal.open"
      title="Delete tag?"
      confirm-label="Delete"
      confirm-variant="danger"
      :loading="deleteLoading"
      @confirm="confirmDelete"
    >
      <p>Are you sure you want to delete "{{ deleteModal.tag?.tag_name }}"? This cannot be undone.</p>
    </BaseModal>

  </AppLayout>
</template>

<style scoped>
.topbar-title { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); }
.page-help-btn { width: 34px; height: 34px; border-radius: var(--radius-md); border: 1px solid var(--border-light); background: var(--white); display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-muted); }
.page-help-btn:hover { background: var(--violet-bg); color: var(--violet); }

.tags-page { display: flex; flex-direction: column; gap: 18px; }
.page-desc { font-size: var(--font-label); color: var(--text-secondary); line-height: 1.6; margin: 0; max-width: 780px; }

.create-card { display: flex; align-items: flex-end; gap: 10px; background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 16px 18px; }
.create-card :deep(.base-input-group) { flex: 1; margin-bottom: 0; }

.loading-msg { font-size: var(--font-label); color: var(--text-muted); padding: 20px 0; }
.error-banner { background: var(--danger-bg); border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 12px 16px; font-size: var(--font-label); color: #B91C1C; }

.empty-state { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 50px 0; color: var(--text-muted); }
.empty-state svg { width: 34px; height: 34px; }
.empty-state p { font-size: var(--font-label); margin: 0; }

.tag-list { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); overflow: hidden; }
.tag-row { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border-light); gap: 12px; }
.tag-row:last-child { border-bottom: none; }
.tag-row-left { display: flex; align-items: center; gap: 12px; min-width: 0; flex-wrap: wrap; }
.tag-chip-lg { font-size: var(--font-label); font-weight: 500; background: var(--violet-bg); color: var(--violet); padding: 4px 12px; border-radius: 20px; }
.tag-usage { font-size: var(--font-hint); color: var(--text-muted); }

.tag-row-actions { display: flex; gap: 8px; flex-shrink: 0; }
.tag-action-btn { font-size: var(--font-label); font-weight: 600; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-family: var(--font-main); background: var(--white); color: var(--text-secondary); border: 1px solid var(--border-light); }
.tag-action-btn:hover:not(:disabled) { background: var(--bg-page); }
.tag-action-danger { color: var(--danger); }
.tag-action-danger:hover:not(:disabled) { background: var(--danger-bg); border-color: #FECACA; }
.tag-action-btn:disabled { opacity: 0.45; cursor: not-allowed; }

.modal-hint { font-size: var(--font-label); color: var(--text-muted); margin: 0 0 14px; line-height: 1.5; }
</style>