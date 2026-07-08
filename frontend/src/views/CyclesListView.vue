<!-- /frontend/src/views/CyclesListView.vue -->

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import SmartSearch from '@/components/search/SmartSearch.vue'
import { useOnboardingStore } from '@/stores/onboarding'
import { useToastStore } from '@/stores/toast'
import { getCycles } from '@/api/cycles'
import api from '@/api/axios'

const router = useRouter()
const onboardingStore = useOnboardingStore()
const toast = useToastStore()

const cycles = ref([])
const loading = ref(true)
const error = ref('')
const activeFilter = ref('all')
const shutdownModal = ref({ open: false, cycleId: null })
const shutdownLoading = ref(false)

async function loadCycles() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getCycles()
    cycles.value = Array.isArray(data) ? data : (data.results || [])
  } catch {
    error.value = 'Failed to load cycles.'
  } finally {
    loading.value = false
  }
}

const filteredCycles = computed(() => {
  if (activeFilter.value === 'all') return cycles.value
  if (activeFilter.value === 'running') return cycles.value.filter(c => c.status === 'running')
  if (activeFilter.value === 'shutdown') return cycles.value.filter(c => c.status === 'shut_down' || c.status === 'completed')
  return cycles.value
})

function formatDate(dateStr) {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })
}

function statusLabel(status) {
  if (status === 'running') return '● Running'
  if (status === 'overdue') return '⚠ Overdue'
  if (status === 'shut_down') return 'Shut down'
  if (status === 'completed') return 'Completed'
  return status
}

function statusClass(status) {
  if (status === 'running') return 'badge-running'
  if (status === 'overdue') return 'badge-overdue'
  return 'badge-shutdown'
}

function openShutdownModal(cycleId) {
  shutdownModal.value = { open: true, cycleId }
}

async function confirmShutdownCycle() {
  shutdownLoading.value = true
  try {
    await api.post(`/cycles/${shutdownModal.value.cycleId}/shut_down/`)
    shutdownModal.value.open = false
    await loadCycles()
    toast.success('Cycle shut down.')
  } catch {
    toast.error('Failed to shut down cycle.')
  } finally {
    shutdownLoading.value = false
  }
}

function openCycle(id) {
  router.push({ name: 'cycle-detail', params: { id } })
}

onMounted(async () => {
  await loadCycles()
  onboardingStore.maybeAutoStart('cycles')
})
</script>

<template>
  <AppLayout>
    <template #topbar>
      <span class="topbar-title">Cycles</span>
      <div style="margin-left: auto; display: flex; gap: 10px;">
        <button type="button" class="page-help-btn" title="Show tips" @click="onboardingStore.startTour('cycles')">
      <div class="topbar-actions">
        <SmartSearch
          context="cycles"
          :default-scopes="['cycles', 'tasks', 'activities', 'notes']"
          placeholder="Search cycles, tasks, and notes..."
        />
        <button type="button" class="page-help-btn" title="Show tips for this page" @click="onboardingStore.startTour('cycles')">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        </button>
        <BaseButton variant="primary" size="sm" data-tour="cycles-new" @click="router.push({ name: 'cycle-create' })">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          New Cycle
        </BaseButton>
      </div>
    </template>

    <div class="cycles-page">

      <div v-if="loading" class="loading-msg">Loading cycles...</div>
      <div v-else-if="error" class="error-banner">{{ error }}</div>

      <template v-else>

        <!-- FILTER ROW -->
        <div class="filter-row" data-tour="cycles-filter">
          <div class="filter-tabs">
            <div class="filter-tab" :class="{ active: activeFilter === 'all' }" @click="activeFilter = 'all'">All cycles</div>
            <div class="filter-tab" :class="{ active: activeFilter === 'running' }" @click="activeFilter = 'running'">Running</div>
            <div class="filter-tab" :class="{ active: activeFilter === 'shutdown' }" @click="activeFilter = 'shutdown'">Shut down</div>
          </div>
          <span class="filter-count">{{ filteredCycles.length }} cycle{{ filteredCycles.length !== 1 ? 's' : '' }}</span>
        </div>

        <!-- EMPTY STATE -->
        <div v-if="filteredCycles.length === 0" class="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
          </svg>
          <div class="empty-title">No cycles yet</div>
          <div class="empty-desc">Start a cycle from a template to track a repeating process.</div>
          <BaseButton variant="primary" size="sm" @click="router.push({ name: 'cycle-create' })">Start your first cycle</BaseButton>
        </div>

        <!-- CYCLE CARDS -->
        <div v-else class="cycles-grid">
          <div
            v-for="(cycle, idx) in filteredCycles"
            :key="cycle.cycle_id"
            class="cycle-card"
            :class="{ 'cycle-card-dim': cycle.status === 'shut_down' || cycle.status === 'completed' }"
            :data-tour="idx === 0 ? 'cycles-card' : null"
            @click="openCycle(cycle.cycle_id)"
          >
            <div class="cc-top">
              <div class="cc-title-area">
                <div class="cc-name">{{ cycle.cycle_name }}</div>
                <div class="cc-template">Started {{ formatDate(cycle.start_date) }}</div>
              </div>
              <span class="badge" :class="statusClass(cycle.status)">{{ statusLabel(cycle.status) }}</span>
            </div>

            <div class="cc-bottom">
              <div class="cc-dates">Created {{ formatDate(cycle.created_at) }}</div>
              <div style="display:flex; gap:8px; align-items:center;">
                <button
                  v-if="cycle.status === 'running'"
                  class="cc-shutdown-btn"
                  @click.stop="openShutdownModal(cycle.cycle_id)"
                >
                  Shut down
                </button>
                <button class="cc-open-btn" @click.stop="openCycle(cycle.cycle_id)">
                  Open cycle →
                </button>
              </div>
            </div>
          </div>
        </div>

      </template>
    </div>
    <!-- SHUT DOWN CONFIRM MODAL -->
    <BaseModal
      v-model="shutdownModal.open"
      title="Shut down cycle?"
      confirm-label="Shut down"
      confirm-variant="danger"
      :loading="shutdownLoading"
      @confirm="confirmShutdownCycle"
    >
      <p>Are you sure you want to shut down this cycle? This cannot be undone.</p>
    </BaseModal>

  </AppLayout>
</template>

<style scoped>
.topbar-title { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); }
.page-help-btn { width: 34px; height: 34px; border-radius: var(--radius-md); border: 1px solid var(--border-light); background: var(--white); display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-muted); }
.page-help-btn:hover { background: var(--violet-bg); color: var(--violet); }

.cycles-page { display: flex; flex-direction: column; gap: 20px; }
.loading-msg { font-size: var(--font-label); color: var(--text-muted); padding: 40px 0; }
.error-banner { background: var(--danger-bg); border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 12px 16px; font-size: 14px; color: #B91C1C; }

.filter-row { display: flex; align-items: center; justify-content: space-between; }
.filter-tabs { display: flex; gap: 6px; }
.filter-tab { padding: 7px 16px; border-radius: 6px; font-size: var(--font-label); font-weight: 500; cursor: pointer; border: 1px solid var(--border-light); color: var(--text-secondary); background: var(--white); }
.filter-tab.active { background: var(--violet-bg); color: var(--violet); border-color: #DDD6FE; }
.filter-count { font-size: var(--font-label); color: var(--text-muted); }

.empty-state { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 60px 0; }
.empty-state svg { width: 40px; height: 40px; stroke: var(--border-light); }
.empty-title { font-size: var(--font-title); font-weight: 600; color: var(--text-primary); }
.empty-desc { font-size: var(--font-label); color: var(--text-muted); }

.cycles-grid { display: flex; flex-direction: column; gap: 12px; }

.cycle-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 18px 22px; cursor: pointer; transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
.cycle-card:hover { border-color: #C4B5FD; box-shadow: var(--shadow-sm); }
.cycle-card-dim { opacity: 0.65; }

.cc-top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 14px; gap: 16px; }
.cc-title-area { flex: 1; min-width: 0; }
.cc-name { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); margin-bottom: 3px; }
.cc-template { font-size: var(--font-label); color: var(--text-muted); }

.badge { font-size: var(--font-badge); font-weight: 500; padding: 4px 11px; border-radius: 20px; flex-shrink: 0; }
.badge-running { background: var(--success-bg); color: #15803D; }
.badge-overdue { background: var(--danger-bg); color: #B91C1C; }
.badge-shutdown { background: var(--bg-page); color: var(--text-muted); border: 1px solid var(--border-light); }

.cc-bottom { display: flex; align-items: center; justify-content: space-between; }
.cc-dates { font-size: var(--font-hint); color: var(--text-muted); }

.cc-open-btn { font-size: var(--font-label); font-weight: 500; color: var(--violet); background: var(--violet-bg); border: none; border-radius: 6px; padding: 6px 14px; cursor: pointer; font-family: var(--font-main); }
.cc-shutdown-btn { font-size: var(--font-label); font-weight: 500; color: var(--danger); background: var(--danger-bg); border: none; border-radius: 6px; padding: 6px 14px; cursor: pointer; font-family: var(--font-main); }
</style>
