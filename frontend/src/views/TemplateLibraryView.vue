<!-- /frontend/src/views/TemplateLibraryView.vue -->

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import { useOnboardingStore } from '@/stores/onboarding'
import { useToastStore } from '@/stores/toast'
import {
  getTemplates,
  duplicateTemplate,
  shareTemplate,
  deleteTemplate,
} from '@/api/templates'

const router = useRouter()
const onboardingStore = useOnboardingStore()
const toast = useToastStore()

const templates = ref([])
const loading = ref(false)
const error = ref('')
const activeCategory = ref('all')
const searchQuery = ref('')
const shareModal = ref({ open: false, templateId: null, username: '' })
const shareError = ref('')
const shareLoading = ref(false)
const deleteModal = ref({ open: false, templateId: null })
const deleteLoading = ref(false)

// Derived — filter by category client-side since backend uses search
const filteredTemplates = computed(() => {
  return templates.value.filter(t => {
    if (activeCategory.value !== 'all' && t.category !== activeCategory.value) return false
    return true
  })
})

async function loadTemplates() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getTemplates(searchQuery.value)
    // Backend returns an array or paginated { results: [] }
    templates.value = Array.isArray(data) ? data : (data.results || [])
  } catch {
    error.value = 'Failed to load templates. Please try again.'
  } finally {
    loading.value = false
  }
}

async function onDuplicate(id) {
  try {
    await duplicateTemplate(id)
    await loadTemplates()
    toast.success('Template duplicated.')
  } catch {
    toast.error('Failed to duplicate template.')
  }
}

function openShareModal(id) {
  shareModal.value = { open: true, templateId: id, username: '' }
  shareError.value = ''
}

async function onShare() {
  if (!shareModal.value.username.trim()) {
    shareError.value = 'Please enter a username.'
    return
  }
  shareLoading.value = true
  shareError.value = ''
  try {
    await shareTemplate(shareModal.value.templateId, shareModal.value.username.trim())
    shareModal.value.open = false
    toast.success('Template shared successfully.')
  } catch (e) {
    const msg = e.response?.data?.detail || e.response?.data?.username?.[0] || 'User not found.'
    shareError.value = msg
  } finally {
    shareLoading.value = false
  }
}

function openDeleteModal(id) {
  deleteModal.value = { open: true, templateId: id }
}

async function onDelete() {
  deleteLoading.value = true
  try {
    await deleteTemplate(deleteModal.value.templateId)
    deleteModal.value.open = false
    await loadTemplates()
    toast.success('Template deleted.')
  } catch {
    toast.error('Failed to delete template.')
  } finally {
    deleteLoading.value = false
  }
}

function openTemplate(id) {
  router.push({ name: 'template-detail', params: { id } })
}

function useTemplate(id) {
  router.push({ name: 'cycle-create', query: { template: id } })
}

// Format date helper
function formatDate(dateStr) {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })
}

onMounted(async () => {
  await loadTemplates()
  onboardingStore.maybeAutoStart('templates')
})
</script>

<template>
  <AppLayout>
    <template #topbar>
      <span class="topbar-title">Template Library</span>
      <div style="margin-left: auto; display: flex; gap: 10px; align-items: center;">
        <div class="search-box">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search templates..."
            @input="loadTemplates"
          />
        </div>
        <button type="button" class="page-help-btn" title="Show tips" @click="onboardingStore.startTour('templates')">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        </button>
        <BaseButton variant="primary" size="sm" data-tour="tpl-new" @click="router.push({ name: 'template-create' })">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          New Template
        </BaseButton>
      </div>
    </template>

    <div class="library-page">

      <!-- ERROR -->
      <div v-if="error" class="error-box">{{ error }}</div>

      <!-- LOADING -->
      <div v-if="loading" class="loading-msg">Loading templates...</div>

      <!-- FILTER TABS -->
      <div class="filter-row">
        <div class="filter-tabs">
          <div class="filter-tab" :class="{ active: activeCategory === 'all' }" @click="activeCategory = 'all'">All</div>
          <div class="filter-tab" :class="{ active: activeCategory === 'Academic' }" @click="activeCategory = 'Academic'">Academic</div>
          <div class="filter-tab" :class="{ active: activeCategory === 'Agriculture' }" @click="activeCategory = 'Agriculture'">Agriculture</div>
          <div class="filter-tab" :class="{ active: activeCategory === 'Gardening' }" @click="activeCategory = 'Gardening'">Gardening</div>
        </div>
        <span class="filter-count">{{ filteredTemplates.length }} template{{ filteredTemplates.length !== 1 ? 's' : '' }}</span>
      </div>

      <!-- EMPTY STATE -->
      <div v-if="!loading && filteredTemplates.length === 0" class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
        </svg>
        <p>No templates yet.</p>
        <BaseButton variant="primary" size="sm" @click="router.push({ name: 'template-create' })">
          Create your first template
        </BaseButton>
      </div>

      <!-- TEMPLATE GRID -->
      <div v-else class="template-grid">
        <div
          v-for="(tpl, idx) in filteredTemplates"
          :key="tpl.template_id || tpl.id"
          class="template-card"
          :data-tour="idx === 0 ? 'tpl-card' : null"
          @click="openTemplate(tpl.template_id || tpl.id)"
        >
          <div class="tc-top-row">
            <div class="tc-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="#7C3AED" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
              </svg>
            </div>
            <div class="tc-menu" @click.stop>
              <div class="tc-menu-btn" title="Duplicate" @click="onDuplicate(tpl.template_id || tpl.id)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
              </div>
              <div class="tc-menu-btn" title="Share" @click="openShareModal(tpl.template_id || tpl.id)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
                  <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
                </svg>
              </div>
              <div class="tc-menu-btn tc-menu-btn-danger" title="Delete" @click="openDeleteModal(tpl.template_id || tpl.id)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                  <path d="M10 11v6"/><path d="M14 11v6"/>
                </svg>
              </div>
            </div>
          </div>

          <div class="tc-name">{{ tpl.template_name }}</div>
          <div class="tc-desc">{{ tpl.description || 'No description.' }}</div>

          <div class="tc-footer">
            <div>
              <div class="tc-version">v{{ tpl.template_version }} · Modified {{ formatDate(tpl.updated_at || tpl.created_at) }}</div>
              <div class="tc-badges">
                <span v-if="tpl.is_current_version" class="tc-badge badge-current">Current version</span>
                <span v-if="tpl.is_public" class="tc-badge badge-public">Public</span>
              </div>
            </div>
            <button class="btn-use" @click.stop="useTemplate(tpl.template_id || tpl.id)">Use →</button>
          </div>
        </div>
      </div>

    </div>

    <!-- SHARE MODAL -->
    <BaseModal
      v-model="shareModal.open"
      title="Share template"
      confirm-label="Share"
      :loading="shareLoading"
      @confirm="onShare"
    >
      <p class="modal-desc">Enter the username of a registered Recurra user. They will receive an independent copy of this template.</p>
      <BaseInput
        v-model="shareModal.username"
        label="Username"
        placeholder="e.g. petercole"
        :error="shareError"
        @keyup.enter="onShare"
      />
    </BaseModal>

    <!-- DELETE CONFIRM MODAL -->
    <BaseModal
      v-model="deleteModal.open"
      title="Delete template?"
      confirm-label="Delete"
      confirm-variant="danger"
      :loading="deleteLoading"
      @confirm="onDelete"
    >
      <p class="modal-desc">This will permanently delete the template. This cannot be undone.</p>
    </BaseModal>

  </AppLayout>
</template>

<style scoped>
.topbar-title { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); flex: 1; }

.search-box { display: flex; align-items: center; gap: 8px; border: 1px solid var(--border-light); border-radius: 7px; padding: 7px 12px; background: var(--bg-page); width: 200px; }
.search-box svg { width: 14px; height: 14px; flex-shrink: 0; stroke: var(--text-muted); }
.search-box input { border: none; background: transparent; font-size: var(--font-label); color: var(--text-primary); outline: none; width: 100%; font-family: var(--font-main); }
.search-box input::placeholder { color: var(--text-muted); }

.page-help-btn { width: 34px; height: 34px; border-radius: var(--radius-md); border: 1px solid var(--border-light); background: var(--white); display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-muted); }
.page-help-btn:hover { background: var(--violet-bg); color: var(--violet); }

.library-page { display: flex; flex-direction: column; gap: 16px; }

.error-box { background: var(--danger-bg); border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 12px 16px; font-size: var(--font-label); color: #B91C1C; }
.loading-msg { font-size: var(--font-label); color: var(--text-muted); padding: 20px 0; }

.filter-row { display: flex; align-items: center; justify-content: space-between; }
.filter-tabs { display: flex; gap: 6px; }
.filter-tab { padding: 6px 14px; border-radius: 6px; font-size: var(--font-label); font-weight: 500; cursor: pointer; border: 1px solid var(--border-light); color: var(--text-secondary); background: var(--white); }
.filter-tab.active { background: var(--violet-bg); color: var(--violet); border-color: #DDD6FE; }
.filter-count { font-size: var(--font-upper); color: var(--text-muted); }

.empty-state { display: flex; flex-direction: column; align-items: center; gap: 14px; padding: 60px 0; color: var(--text-muted); }
.empty-state svg { width: 40px; height: 40px; }
.empty-state p { font-size: var(--font-label); margin: 0; }

.template-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }

.template-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 18px 20px; cursor: pointer; display: flex; flex-direction: column; transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
.template-card:hover { border-color: #C4B5FD; box-shadow: var(--shadow-sm); }

.tc-top-row { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 10px; }
.tc-icon { width: 36px; height: 36px; border-radius: 8px; background: var(--violet-bg); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.tc-icon svg { width: 18px; height: 18px; }

.tc-menu { display: flex; gap: 4px; }
.tc-menu-btn { width: 28px; height: 28px; border-radius: 6px; border: 1px solid var(--border-light); background: var(--white); display: flex; align-items: center; justify-content: center; cursor: pointer; }
.tc-menu-btn svg { width: 13px; height: 13px; stroke: var(--text-muted); }
.tc-menu-btn:hover { background: var(--bg-page); }
.tc-menu-btn-danger:hover { border-color: #FECACA; background: var(--danger-bg); }
.tc-menu-btn-danger:hover svg { stroke: var(--danger); }

.tc-name { font-size: var(--font-label); font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.tc-desc { font-size: var(--font-label); color: var(--text-muted); line-height: 1.5; margin-bottom: 14px; flex: 1; }

.tc-footer { display: flex; align-items: center; justify-content: space-between; padding-top: 12px; border-top: 1px solid var(--border-light); margin-top: auto; }
.tc-version { font-size: var(--font-label); color: var(--text-muted); margin-bottom: 5px; }
.tc-badges { display: flex; gap: 6px; }
.tc-badge { font-size: var(--font-upper); font-weight: 500; padding: 2px 8px; border-radius: 4px; }
.badge-current { background: var(--success-bg); color: #15803D; }
.badge-public { background: var(--info-bg); color: #1D4ED8; }
.btn-use { font-size: var(--font-upper); font-weight: 500; color: var(--violet); background: var(--violet-bg); border: none; border-radius: 6px; padding: 5px 12px; cursor: pointer; font-family: var(--font-main); }

/* SHARE MODAL */
.modal-desc { font-size: var(--font-label); color: var(--text-secondary); margin: 0 0 14px; line-height: 1.55; }

@media (max-width: 1024px) {
  .template-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>