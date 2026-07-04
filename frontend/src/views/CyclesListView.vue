<!-- /frontend/src/views/CyclesListView.vue -->

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import SmartSearch from '@/components/search/SmartSearch.vue'
import { useOnboardingStore } from '@/stores/onboarding'

const router = useRouter()
const onboardingStore = useOnboardingStore()
const activeFilter = ref('all')

const cycles = ref([
  {
    id: 1, name: 'ICT302 S2 2026', template: 'Unit Coordination Template v3',
    startDate: '2 Jun 2026', endDate: '30 Nov 2026', progress: 62, status: 'overdue',
    tasks: { completed: 8, inProgress: 3, overdue: 1, pending: 5 },
  },
  {
    id: 2, name: 'Breeding Cycle 2026', template: "Cole's Advanced Breeding Template v2",
    startDate: '15 May 2026', endDate: '15 Dec 2026', progress: 45, status: 'overdue',
    tasks: { completed: 5, inProgress: 2, overdue: 1, pending: 8 },
  },
  {
    id: 3, name: 'Garden Planting 2026', template: 'Annual Planting Template v1',
    startDate: '1 Jun 2026', endDate: '30 Sep 2026', progress: 30, status: 'running',
    tasks: { completed: 3, inProgress: 1, overdue: 0, pending: 8 },
  },
  {
    id: 4, name: 'ICT302 TJA 2026', template: 'Unit Coordination Template v3',
    startDate: '5 Jun 2026', endDate: '15 Nov 2026', progress: 18, status: 'running',
    tasks: { completed: 2, inProgress: 1, overdue: 0, pending: 10 },
  },
])

const shutdownCycles = ref([
  {
    id: 5, name: 'ICT302 S1 2026', template: 'Unit Coordination Template v2',
    startDate: '1 Feb 2026', endDate: '31 May 2026', progress: 100, status: 'shutdown',
    tasks: { completed: 17 },
  },
])

function openCycle(id) {
  router.push({ name: 'cycle-detail', params: { id } })
}

onMounted(() => {
  onboardingStore.maybeAutoStart('cycles')
})
</script>

<template>
  <AppLayout>
    <template #topbar>
      <span class="topbar-title">Cycles</span>
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

      <div class="filter-row" data-tour="cycles-filter">
        <div class="filter-tabs">
          <div class="filter-tab" :class="{ active: activeFilter === 'all' }" @click="activeFilter = 'all'">All cycles</div>
          <div class="filter-tab" :class="{ active: activeFilter === 'running' }" @click="activeFilter = 'running'">Running</div>
          <div class="filter-tab" :class="{ active: activeFilter === 'shutdown' }" @click="activeFilter = 'shutdown'">Shut down</div>
        </div>
        <span class="filter-count">{{ cycles.length + shutdownCycles.length }} cycles total</span>
      </div>

      <div>
        <div class="section-label">Running — {{ cycles.length }} cycles</div>
        <div class="cycles-grid">
          <div v-for="(cycle, idx) in cycles" :key="cycle.id" class="cycle-card" :data-tour="idx === 0 ? 'cycles-card' : null" @click="openCycle(cycle.id)">
            <div class="cc-top">
              <div class="cc-title-area">
                <div class="cc-name">{{ cycle.name }}</div>
                <div class="cc-template">{{ cycle.template }} · Started {{ cycle.startDate }}</div>
              </div>
              <div class="cc-badges">
                <span class="badge" :class="cycle.status === 'overdue' ? 'badge-overdue' : 'badge-running'">
                  {{ cycle.status === 'overdue' ? '⚠ Overdue task' : '● Running' }}
                </span>
              </div>
            </div>

            <div class="cc-progress-row">
              <div class="progress-bar-bg"><div class="progress-bar-fill" :style="{ width: cycle.progress + '%' }"></div></div>
              <span class="progress-pct">{{ cycle.progress }}%</span>
            </div>

            <div class="cc-bottom">
              <div class="cc-chips">
                <span class="task-chip"><span class="chip-dot" style="background:var(--success);"></span>{{ cycle.tasks.completed }} completed</span>
                <span class="task-chip"><span class="chip-dot" style="background:var(--warning);"></span>{{ cycle.tasks.inProgress }} in progress</span>
                <span v-if="cycle.tasks.overdue" class="task-chip"><span class="chip-dot" style="background:var(--danger);"></span>{{ cycle.tasks.overdue }} overdue</span>
                <span class="task-chip"><span class="chip-dot" style="background:var(--border);"></span>{{ cycle.tasks.pending }} pending</span>
              </div>
              <div style="display:flex; align-items:center; gap:16px;">
                <div class="cc-dates"><span>{{ cycle.startDate }} → {{ cycle.endDate }}</span></div>
                <button class="cc-open-btn" @click.stop="openCycle(cycle.id)">
                  Open cycle
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div>
        <div class="section-label">Shut down — {{ shutdownCycles.length }} cycle</div>
        <div class="cycles-grid">
          <div v-for="cycle in shutdownCycles" :key="cycle.id" class="cycle-card shutdown" @click="openCycle(cycle.id)">
            <div class="cc-top">
              <div class="cc-title-area">
                <div class="cc-name">{{ cycle.name }}</div>
                <div class="cc-template">{{ cycle.template }} · Started {{ cycle.startDate }}</div>
              </div>
              <div class="cc-badges">
                <span class="badge badge-shutdown">Shut down</span>
              </div>
            </div>
            <div class="cc-progress-row">
              <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:100%; background:var(--success);"></div></div>
              <span class="progress-pct" style="color: var(--success);">{{ cycle.progress }}%</span>
            </div>
            <div class="cc-bottom">
              <div class="cc-chips">
                <span class="task-chip"><span class="chip-dot" style="background:var(--success);"></span>{{ cycle.tasks.completed }} completed</span>
              </div>
              <div style="display:flex; align-items:center; gap:16px;">
                <div class="cc-dates"><span>{{ cycle.startDate }} → {{ cycle.endDate }}</span></div>
                <button class="cc-open-btn" @click.stop="openCycle(cycle.id)">
                  View cycle
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>
  </AppLayout>
</template>

<style scoped>
.topbar-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.topbar-actions { margin-left: auto; display: flex; gap: 10px; align-items: center; min-width: 0; }

.page-help-btn {
  width: 34px; height: 34px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  background: var(--white);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  color: var(--text-muted);
  transition: background var(--transition-fast), color var(--transition-fast);
  flex-shrink: 0;
}

.page-help-btn:hover { background: var(--violet-bg); color: var(--violet); }

.cycles-page { display: flex; flex-direction: column; gap: 20px; }

.filter-row { display: flex; align-items: center; justify-content: space-between; }
.filter-tabs { display: flex; gap: 6px; }

.filter-tab {
  padding: 6px 14px; border-radius: 6px; font-size: 13px;
  font-weight: 500; cursor: pointer; border: 1px solid var(--border-light);
  color: var(--text-secondary); background: var(--white);
}

.filter-tab.active { background: var(--violet-bg); color: var(--violet); border-color: #DDD6FE; }

.filter-count { font-size: 12px; color: var(--text-muted); }

.section-label {
  font-size: 11px; font-weight: 600; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.07em; padding: 4px 0 10px;
}

.cycles-grid { display: flex; flex-direction: column; gap: 12px; }

.cycle-card {
  background: var(--white); border: 1px solid var(--border-light);
  border-radius: var(--radius-lg); padding: 18px 22px; cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.cycle-card:hover { border-color: #C4B5FD; box-shadow: var(--shadow-sm); }
.cycle-card.shutdown { opacity: 0.65; }
.cycle-card.shutdown:hover { border-color: var(--border-light); box-shadow: none; }

.cc-top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 14px; gap: 16px; }
.cc-title-area { flex: 1; min-width: 0; }
.cc-name { font-size: 15px; font-weight: 600; color: var(--text-primary); margin-bottom: 3px; letter-spacing: -0.2px; }
.cc-template { font-size: 12.5px; color: var(--text-muted); }
.cc-badges { display: flex; gap: 7px; align-items: center; flex-shrink: 0; }

.badge { font-size: 12.5px; font-weight: 500; padding: 4px 11px; border-radius: 20px; }
.badge-running { background: var(--success-bg); color: #15803D; }
.badge-overdue { background: var(--danger-bg); color: #B91C1C; }
.badge-shutdown { background: var(--bg-page); color: var(--text-muted); border: 1px solid var(--border-light); }

.cc-progress-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.progress-bar-bg { flex: 1; height: 6px; border-radius: 3px; background: var(--border-light); }
.progress-bar-fill { height: 6px; border-radius: 3px; background: var(--violet); }
.progress-pct { font-size: 13px; font-weight: 500; color: var(--text-secondary); flex-shrink: 0; width: 38px; text-align: right; }

.cc-bottom { display: flex; align-items: center; justify-content: space-between; }
.cc-chips { display: flex; gap: 8px; flex-wrap: wrap; }

.task-chip {
  display: flex; align-items: center; gap: 5px; font-size: 12px;
  padding: 3px 9px; border-radius: 5px; border: 1px solid var(--border-light);
  color: var(--text-secondary); background: var(--bg-page);
}

.chip-dot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }
.cc-dates { font-size: 12px; color: var(--text-muted); }

.cc-open-btn {
  display: flex; align-items: center; gap: 5px; font-size: 12.5px; font-weight: 500;
  color: var(--violet); background: var(--violet-bg); border: none; border-radius: 6px;
  padding: 5px 12px; cursor: pointer; font-family: var(--font-main); flex-shrink: 0;
}

.cc-open-btn svg { width: 13px; height: 13px; }
</style>
