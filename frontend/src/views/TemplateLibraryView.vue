<!-- /frontend/src/views/TemplateLibraryView.vue -->

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { useOnboardingStore } from '@/stores/onboarding'

const router = useRouter()
const onboardingStore = useOnboardingStore()
const activeCategory = ref('all')

const templates = ref([
  {
    id: 1, name: 'Unit Coordination', desc: 'Full workflow for setting up and running a university teaching unit across a semester period.',
    icon: 'academic', tasks: 17, days: 180, activities: 3, version: 'v4', modified: '5 Jun 2026', activeCycles: 2, category: 'Academic',
  },
  {
    id: 2, name: "Cole's Advanced Breeding", desc: 'Seasonal livestock breeding program covering stock selection, mating, husbandry, and post-season review.',
    icon: 'agriculture', tasks: 16, days: 210, activities: 4, version: 'v2', modified: '14 May 2026', activeCycles: 1, category: 'Agriculture',
  },
  {
    id: 3, name: 'Annual Planting Cycle', desc: 'Seed ordering, growing site preparation, seedling care, planting and harvest schedule for annual plants.',
    icon: 'gardening', tasks: 12, days: 120, activities: 2, version: 'v1', modified: '30 May 2026', activeCycles: 1, category: 'Gardening',
  },
])

const sharedTemplates = ref([
  { id: 1, name: 'Student Enrolment Cycle', desc: 'End-to-end enrolment process for each teaching period including unit selection, textbook ordering and orientation.', sharedBy: 'Peter Cole', sharedDate: '9 Jun 2026', tasks: 12, days: 90, category: 'Academic' },
  { id: 2, name: 'Crop Rotation Schedule', desc: 'Seasonal crop planning and rotation workflow covering soil preparation, seeding, and post-harvest recovery.', sharedBy: 'Mark Reynolds', sharedDate: '7 Jun 2026', tasks: 9, days: 150, category: 'Agriculture' },
])

const iconColors = {
  academic: { bg: '#EFF6FF', stroke: '#3B82F6' },
  agriculture: { bg: '#FFF7ED', stroke: '#F59E0B' },
  gardening: { bg: '#F0FDF4', stroke: '#22C55E' },
}

function openTemplate(id) {
  router.push({ name: 'template-detail', params: { id } })
}

function useTemplate(id) {
  router.push({ name: 'cycle-create', query: { template: id } })
}

onMounted(() => {
  onboardingStore.maybeAutoStart('templates')
})
</script>

<template>
  <AppLayout>
    <template #topbar>
      <span class="topbar-title">Template Library</span>
      <div style="margin-left: auto; display: flex; gap: 10px; align-items: center;">
        <div class="search-box">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input type="text" placeholder="Search templates..." />
        </div>
        <button type="button" class="page-help-btn" title="Show tips for this page" @click="onboardingStore.startTour('templates')">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        </button>
        <BaseButton variant="primary" size="sm" data-tour="tpl-new" @click="router.push({ name: 'template-create' })">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New Template
        </BaseButton>
      </div>
    </template>

    <div class="library-page">

      <div class="filter-row">
        <div class="filter-tabs">
          <div class="filter-tab" :class="{ active: activeCategory === 'all' }" @click="activeCategory = 'all'">All templates</div>
          <div class="filter-tab" :class="{ active: activeCategory === 'Academic' }" @click="activeCategory = 'Academic'">Academic</div>
          <div class="filter-tab" :class="{ active: activeCategory === 'Agriculture' }" @click="activeCategory = 'Agriculture'">Agriculture</div>
          <div class="filter-tab" :class="{ active: activeCategory === 'Gardening' }" @click="activeCategory = 'Gardening'">Gardening</div>
        </div>
      </div>

      <div class="section-header">
        <div>
          <div class="section-title">My templates</div>
          <div class="section-sub">{{ templates.length }} templates · click to open, use to create a new cycle</div>
        </div>
      </div>

      <div class="template-grid">
        <div v-for="(tpl, idx) in templates" :key="tpl.id" class="template-card" :data-tour="idx === 0 ? 'tpl-card' : null" @click="openTemplate(tpl.id)">
          <div class="tc-top-row">
            <div class="tc-icon" :style="{ background: iconColors[tpl.icon].bg }">
              <svg viewBox="0 0 24 24" fill="none" :stroke="iconColors[tpl.icon].stroke" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
            </div>
            <div class="tc-menu" @click.stop>
              <div class="tc-menu-btn" title="Duplicate"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></div>
              <div class="tc-menu-btn" title="Share"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg></div>
            </div>
          </div>
          <div class="tc-name">{{ tpl.name }}</div>
          <div class="tc-desc">{{ tpl.desc }}</div>
          <div class="tc-meta-row">
            <div class="tc-meta-chip"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>{{ tpl.tasks }} tasks</div>
            <div class="tc-meta-chip"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>{{ tpl.days }} days</div>
            <div class="tc-meta-chip"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>{{ tpl.activities }} activities</div>
          </div>
          <div class="tc-footer">
            <div>
              <div class="tc-version">{{ tpl.version }} · Modified {{ tpl.modified }}</div>
              <div class="tc-badges">
                <span class="tc-badge badge-active">{{ tpl.activeCycles }} active cycle{{ tpl.activeCycles > 1 ? 's' : '' }}</span>
                <span class="tc-badge badge-category">{{ tpl.category }}</span>
              </div>
            </div>
            <button class="btn-use" @click.stop="useTemplate(tpl.id)">Use template →</button>
          </div>
        </div>
      </div>

      <div class="section-header">
        <div>
          <div class="section-title">Shared with me</div>
          <div class="section-sub">Accepting creates your own independent copy</div>
        </div>
      </div>

      <div class="shared-grid" data-tour="tpl-shared">
        <div v-for="shared in sharedTemplates" :key="shared.id" class="shared-card">
          <div class="shared-from">
            <div class="shared-avatar">{{ shared.sharedBy.split(' ').map(n => n[0]).join('') }}</div>
            <span class="shared-from-text">Shared by {{ shared.sharedBy }} · {{ shared.sharedDate }}</span>
          </div>
          <div class="shared-name">{{ shared.name }}</div>
          <div class="shared-desc">{{ shared.desc }}</div>
          <div class="shared-footer">
            <span class="shared-meta">{{ shared.tasks }} tasks · {{ shared.days }} days · {{ shared.category }}</span>
            <button class="btn-accept">Accept copy</button>
          </div>
        </div>
      </div>

    </div>
  </AppLayout>
</template>

<style scoped>
.topbar-title { font-size: 15px; font-weight: 600; color: var(--text-primary); flex: 1; }

.search-box { display: flex; align-items: center; gap: 8px; border: 1px solid var(--border-light); border-radius: 7px; padding: 7px 12px; background: var(--bg-page); width: 200px; }
.search-box svg { width: 14px; height: 14px; stroke: var(--text-muted); flex-shrink: 0; }
.search-box input { border: none; background: transparent; font-size: 13px; color: var(--text-primary); outline: none; width: 100%; font-family: var(--font-main); }
.search-box input::placeholder { color: var(--text-muted); }

.page-help-btn { width: 34px; height: 34px; border-radius: var(--radius-md); border: 1px solid var(--border-light); background: var(--white); display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-muted); transition: background var(--transition-fast), color var(--transition-fast); flex-shrink: 0; }
.page-help-btn:hover { background: var(--violet-bg); color: var(--violet); }

.library-page { display: flex; flex-direction: column; gap: 20px; }

.filter-row { display: flex; align-items: center; justify-content: space-between; }
.filter-tabs { display: flex; gap: 6px; }
.filter-tab { padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; border: 1px solid var(--border-light); color: var(--text-secondary); background: var(--white); }
.filter-tab.active { background: var(--violet-bg); color: var(--violet); border-color: #DDD6FE; }

.section-header { display: flex; align-items: center; justify-content: space-between; }
.section-title { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.section-sub { font-size: 12.5px; color: var(--text-muted); }

.template-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }

.template-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 18px 20px; cursor: pointer; display: flex; flex-direction: column; transition: border-color var(--transition-fast); }
.template-card:hover { border-color: #C4B5FD; }

.tc-top-row { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 10px; }
.tc-icon { width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.tc-icon svg { width: 18px; height: 18px; }

.tc-menu { display: flex; gap: 4px; }
.tc-menu-btn { width: 28px; height: 28px; border-radius: 6px; border: 1px solid var(--border-light); background: var(--white); display: flex; align-items: center; justify-content: center; cursor: pointer; }
.tc-menu-btn svg { width: 13px; height: 13px; stroke: var(--text-muted); }

.tc-name { font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.tc-desc { font-size: 12.5px; color: var(--text-muted); line-height: 1.5; margin-bottom: 14px; }

.tc-meta-row { display: flex; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }
.tc-meta-chip { display: flex; align-items: center; gap: 4px; font-size: 11.5px; color: var(--text-secondary); }
.tc-meta-chip svg { width: 12px; height: 12px; stroke: var(--text-muted); }

.tc-footer { display: flex; align-items: center; justify-content: space-between; padding-top: 12px; border-top: 1px solid var(--border-light); margin-top: auto; }
.tc-version { font-size: 11.5px; color: var(--text-muted); }
.tc-badges { display: flex; gap: 6px; margin-top: 5px; }
.tc-badge { font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: 4px; }
.badge-active { background: var(--success-bg); color: #15803D; }
.badge-category { background: var(--violet-bg); color: var(--violet); }

.btn-use { font-size: 12px; font-weight: 500; color: var(--violet); background: var(--violet-bg); border: none; border-radius: 6px; padding: 5px 12px; cursor: pointer; font-family: var(--font-main); }

.shared-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.shared-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; }
.shared-from { display: flex; align-items: center; gap: 8px; }
.shared-avatar { width: 24px; height: 24px; border-radius: 50%; background: var(--violet-bg); display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 600; color: var(--violet); }
.shared-from-text { font-size: 11.5px; color: var(--text-muted); }
.shared-name { font-size: 13.5px; font-weight: 600; color: var(--text-primary); }
.shared-desc { font-size: 12px; color: var(--text-muted); }
.shared-footer { display: flex; align-items: center; justify-content: space-between; }
.shared-meta { font-size: 11px; color: var(--text-muted); }
.btn-accept { font-size: 12px; font-weight: 500; color: var(--white); background: var(--violet); border: none; border-radius: 6px; padding: 5px 12px; cursor: pointer; font-family: var(--font-main); }
</style>