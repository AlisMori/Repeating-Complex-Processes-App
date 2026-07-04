<!-- /frontend/src/views/CycleDetailView.vue -->

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const route = useRoute()
const router = useRouter()

const cycle = ref({
  name: 'ICT302 S2 2026',
  template: 'Unit Coordination Template',
  version: 'v3',
  status: 'running',
  startDate: '2 Jun 2026',
  endDate: '30 Nov 2026',
  duration: 181,
  progress: 62,
  totalTasks: 17,
  activeActivities: 3,
  overdue: 1,
})

const tasks = ref({
  overdue: [
    { id: 1, name: 'Submit Exam Paper', desc: 'Upload final exam paper to LMS for review', due: 'Due 9 Jun 2026', mandatory: true, fixedEnd: true },
  ],
  today: [
    { id: 2, name: 'Update LMS Content', desc: 'Upload lecture slides, readings and assessment briefs to LMS', due: 'Due 11 Jun 2026', status: 'in-progress', dependsOn: 'LMS Site Setup' },
  ],
  upcoming: [
    { id: 3, name: 'Write Assignment Brief', desc: 'Draft and finalise Assignment 1 brief document', due: 'Due 14 Jun 2026', mandatory: true, dependsOn: 'Update LMS Content' },
    { id: 4, name: 'Post Assignment to LMS', desc: 'Publish Assignment 1 brief and submission link', due: 'Due 16 Jun 2026', dependsOn: 'Write Assignment Brief' },
  ],
  completed: [
    { id: 5, name: 'Request LMS Site', desc: 'Submit LMS site creation request to IT services', due: '3 Jun 2026' },
    { id: 6, name: 'Update Unit Guide (ULIG)', desc: 'Update and publish the unit learning and information guide', due: '5 Jun 2026' },
  ],
})

const activity = ref({ name: 'Teaching the Unit', desc: 'Non-actionable activity spanning the full teaching semester', start: '2 Jun', end: '30 Nov 2026' })

function openTask(id) {
  router.push({ name: 'cycle-detail', params: { id: route.params.id }, query: { task: id } })
}
</script>

<template>
  <AppLayout>
    <template #topbar>
      <div class="breadcrumb">
        <span class="breadcrumb-link" @click="router.push({ name: 'cycles' })">Cycles</span>
        <span class="breadcrumb-sep">›</span>
        <span class="breadcrumb-current">{{ cycle.name }}</span>
      </div>
      <div style="margin-left: auto; display: flex; gap: 10px;">
        <BaseButton variant="secondary" size="sm">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Export CSV
        </BaseButton>
        <BaseButton variant="danger" size="sm">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="9" x2="15" y2="15"/><line x1="15" y1="9" x2="9" y2="15"/></svg>
          Shut Down Cycle
        </BaseButton>
      </div>
    </template>

    <div class="two-col">

      <div class="col-main">

        <div class="cycle-header">
          <div class="cycle-header-top">
            <div>
              <div class="cycle-title">{{ cycle.name }}</div>
              <div class="cycle-subtitle">{{ cycle.template }} · Started {{ cycle.startDate }}</div>
            </div>
            <div class="cycle-badges">
              <span class="badge badge-running">● Running</span>
              <span class="badge badge-version">Template {{ cycle.version }}</span>
            </div>
          </div>
          <div class="cycle-progress-row">
            <div class="progress-bar-bg"><div class="progress-bar-fill" :style="{ width: cycle.progress + '%' }"></div></div>
            <span class="progress-label">{{ cycle.progress }}% · 8 of {{ cycle.totalTasks }} tasks done</span>
          </div>
          <div class="cycle-meta-row">
            <div class="meta-item"><div class="meta-label">Start</div><div class="meta-value">{{ cycle.startDate }}</div></div>
            <div class="meta-item"><div class="meta-label">End</div><div class="meta-value">{{ cycle.endDate }}</div></div>
            <div class="meta-item"><div class="meta-label">Duration</div><div class="meta-value">{{ cycle.duration }} days</div></div>
            <div class="meta-item"><div class="meta-label">Tasks</div><div class="meta-value">{{ cycle.totalTasks }} total</div></div>
            <div class="meta-item"><div class="meta-label">Activities</div><div class="meta-value">{{ cycle.activeActivities }} active</div></div>
            <div class="meta-item"><div class="meta-label">Overdue</div><div class="meta-value danger">{{ cycle.overdue }} task</div></div>
          </div>
        </div>

        <div class="alert-box">
          <svg viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <div>
            <div class="alert-title">1 overdue task requires attention</div>
            <div class="alert-desc">Submit Exam Paper was due 9 Jun 2026 — click the task below to update its status</div>
          </div>
        </div>

        <div class="timeline">

          <div class="timeline-label danger">⚠ Overdue</div>
          <div v-for="task in tasks.overdue" :key="task.id" class="timeline-item">
            <div class="timeline-dot overdue"><svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg></div>
            <div class="timeline-line"></div>
            <div class="task-card overdue-card" @click="openTask(task.id)">
              <div class="tc-row">
                <div class="tc-left"><div class="tc-name">{{ task.name }}</div><div class="tc-desc">{{ task.desc }}</div></div>
                <div class="tc-right">
                  <span v-if="task.mandatory" class="tc-mandatory">MANDATORY</span>
                  <span class="tc-status status-overdue">Overdue</span>
                  <span class="tc-date">{{ task.due }}</span>
                </div>
              </div>
              <div class="tc-bottom">
                <span v-if="task.fixedEnd" class="fixed-chip"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>Fixed end date</span>
              </div>
            </div>
          </div>

          <div class="timeline-label">Today — 11 Jun 2026</div>

          <div class="timeline-item">
            <div class="timeline-dot activity"></div>
            <div class="timeline-line"></div>
            <div class="task-card activity-card">
              <div class="tc-row">
                <div class="tc-left"><div class="tc-name violet">{{ activity.name }}</div><div class="tc-desc">{{ activity.desc }}</div></div>
                <div class="tc-right"><span class="tc-status status-activity">Activity</span><span class="tc-date">{{ activity.start }} → {{ activity.end }}</span></div>
              </div>
              <div class="activity-span-bar"></div>
            </div>
          </div>

          <div v-for="task in tasks.today" :key="task.id" class="timeline-item">
            <div class="timeline-dot in-progress"></div>
            <div class="timeline-line"></div>
            <div class="task-card" @click="openTask(task.id)">
              <div class="tc-row">
                <div class="tc-left"><div class="tc-name">{{ task.name }}</div><div class="tc-desc">{{ task.desc }}</div></div>
                <div class="tc-right"><span class="tc-status status-in-progress">In Progress</span><span class="tc-date">{{ task.due }}</span></div>
              </div>
              <div class="tc-bottom">
                <span class="dep-chip"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>Depends on: {{ task.dependsOn }}</span>
              </div>
            </div>
          </div>

          <div class="timeline-label">Upcoming</div>

          <div v-for="task in tasks.upcoming" :key="task.id" class="timeline-item">
            <div class="timeline-dot pending"></div>
            <div class="timeline-line"></div>
            <div class="task-card" @click="openTask(task.id)">
              <div class="tc-row">
                <div class="tc-left"><div class="tc-name">{{ task.name }}</div><div class="tc-desc">{{ task.desc }}</div></div>
                <div class="tc-right">
                  <span v-if="task.mandatory" class="tc-mandatory">MANDATORY</span>
                  <span class="tc-status status-pending">Pending</span>
                  <span class="tc-date">{{ task.due }}</span>
                </div>
              </div>
              <div class="tc-bottom">
                <span class="dep-chip"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>Depends on: {{ task.dependsOn }}</span>
              </div>
            </div>
          </div>

          <div class="timeline-label">Completed</div>

          <div v-for="task in tasks.completed" :key="task.id" class="timeline-item">
            <div class="timeline-dot completed"><svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></div>
            <div class="task-card" @click="openTask(task.id)">
              <div class="tc-row">
                <div class="tc-left"><div class="tc-name">{{ task.name }}</div><div class="tc-desc">{{ task.desc }}</div></div>
                <div class="tc-right"><span class="tc-status status-completed">Completed</span><span class="tc-date">{{ task.due }}</span></div>
              </div>
            </div>
          </div>

        </div>
      </div>

      <div class="col-side">
        <div class="side-card">
          <div class="side-card-title">Status summary</div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--success);"></div><span class="legend-label">Completed</span><span class="legend-count">8</span></div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--warning);"></div><span class="legend-label">In progress</span><span class="legend-count">3</span></div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--danger);"></div><span class="legend-label">Overdue</span><span class="legend-count">1</span></div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--border);"></div><span class="legend-label">Pending</span><span class="legend-count">5</span></div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--violet);"></div><span class="legend-label">Activities</span><span class="legend-count">3</span></div>
        </div>

        <div class="side-card">
          <div class="side-card-title">Notes</div>
          <div class="note-box">Students confirmed enrolled. LMS site active and visible.<div class="note-meta">Jane Smith · 3 Jun 2026</div></div>
          <div class="note-box">Exam paper needs approval before submission deadline.<div class="note-meta">Jane Smith · 8 Jun 2026</div></div>
          <button class="add-note-btn">+ Add note</button>
        </div>

        <div class="side-card">
          <div class="side-card-title">Template</div>
          <div class="template-row"><span class="template-row-label">Name</span><span class="template-row-value">{{ cycle.template }}</span></div>
          <div class="template-row"><span class="template-row-label">Version</span><span class="template-row-value">{{ cycle.version }}</span></div>
          <div class="template-row"><span class="template-row-label">Newer version</span><span class="template-row-link">v4 available →</span></div>
        </div>
      </div>

    </div>
  </AppLayout>
</template>

<style scoped>
.breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.breadcrumb-link { color: var(--text-muted); cursor: pointer; }
.breadcrumb-sep { color: var(--text-muted); }
.breadcrumb-current { color: var(--text-primary); font-weight: 500; }

.two-col { display: flex; gap: 20px; align-items: flex-start; }
.col-main { flex: 1; min-width: 0; }
.col-side { width: 268px; flex-shrink: 0; display: flex; flex-direction: column; gap: 14px; }

.cycle-header { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 18px 22px; margin-bottom: 20px; }
.cycle-header-top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 14px; }
.cycle-title { font-size: 18px; font-weight: 600; color: var(--text-primary); letter-spacing: -0.3px; margin-bottom: 3px; }
.cycle-subtitle { font-size: 12.5px; color: var(--text-muted); }
.cycle-badges { display: flex; gap: 7px; align-items: center; flex-shrink: 0; }

.badge { font-size: 12.5px; font-weight: 500; padding: 4px 11px; border-radius: 20px; }
.badge-running { background: var(--success-bg); color: #15803D; }
.badge-version { background: var(--violet-bg); color: var(--violet); }

.cycle-progress-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.progress-bar-bg { flex: 1; height: 6px; border-radius: 3px; background: var(--border-light); }
.progress-bar-fill { height: 6px; border-radius: 3px; background: var(--violet); }
.progress-label { font-size: 12px; font-weight: 500; color: var(--text-secondary); flex-shrink: 0; }

.cycle-meta-row { display: flex; gap: 24px; padding-top: 12px; border-top: 1px solid var(--border-light); }
.meta-label { font-size: 10.5px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 3px; }
.meta-value { font-size: 13px; font-weight: 500; color: var(--text-primary); }
.meta-value.danger { color: var(--danger); }

.alert-box { background: var(--danger-bg); border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 11px 14px; display: flex; gap: 10px; align-items: flex-start; margin-bottom: 20px; }
.alert-box svg { width: 15px; height: 15px; flex-shrink: 0; margin-top: 1px; }
.alert-title { font-size: 13px; font-weight: 600; color: #B91C1C; margin-bottom: 2px; }
.alert-desc { font-size: 12px; color: #991B1B; }

.timeline { display: flex; flex-direction: column; }
.timeline-label { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.07em; padding: 4px 0 8px; }
.timeline-label.danger { color: var(--danger); }

.timeline-item { display: flex; gap: 0; position: relative; padding-left: 26px; }
.timeline-line { position: absolute; left: 7px; top: 22px; bottom: -8px; width: 1.5px; background: var(--border-light); }

.timeline-dot { position: absolute; left: 0; top: 13px; width: 15px; height: 15px; border-radius: 50%; border: 2px solid var(--border-light); background: var(--white); display: flex; align-items: center; justify-content: center; flex-shrink: 0; z-index: 1; }
.timeline-dot svg { width: 7px; height: 7px; }
.timeline-dot.completed { border-color: var(--success); background: var(--success); }
.timeline-dot.in-progress { border-color: var(--warning); background: var(--warning); }
.timeline-dot.overdue { border-color: var(--danger); background: var(--danger); }
.timeline-dot.pending { border-color: var(--border-light); background: var(--white); }
.timeline-dot.activity { border-color: var(--violet); background: var(--violet-bg); }

.task-card { flex: 1; background: var(--white); border: 1px solid var(--border-light); border-radius: 8px; padding: 11px 14px; margin-bottom: 8px; cursor: pointer; transition: border-color var(--transition-fast); }
.task-card:hover { border-color: #C4B5FD; }
.task-card.overdue-card { border-color: #FECACA; background: #FFF8F8; }
.task-card.activity-card { border-color: #DDD6FE; background: #FAFAFE; cursor: default; }

.tc-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.tc-left { flex: 1; min-width: 0; }
.tc-name { font-size: 13.5px; font-weight: 600; color: var(--text-primary); margin-bottom: 2px; }
.tc-name.violet { color: var(--violet); }
.tc-desc { font-size: 12px; color: var(--text-muted); }
.tc-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

.tc-status { font-size: 11.5px; font-weight: 500; padding: 3px 9px; border-radius: 4px; }
.status-completed { background: var(--success-bg); color: #15803D; }
.status-in-progress { background: var(--warning-bg); color: #92400E; }
.status-overdue { background: var(--danger-bg); color: #B91C1C; }
.status-pending { background: var(--bg-page); color: var(--text-muted); border: 1px solid var(--border-light); }
.status-activity { background: var(--violet-bg); color: var(--violet); }

.tc-date { font-size: 11.5px; color: var(--text-muted); }
.tc-mandatory { font-size: 10px; font-weight: 600; color: var(--danger); }

.tc-bottom { display: flex; align-items: center; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.dep-chip { display: flex; align-items: center; gap: 4px; font-size: 11px; color: var(--text-muted); background: var(--bg-page); border: 1px solid var(--border-light); padding: 2px 7px; border-radius: 4px; }
.dep-chip svg { width: 10px; height: 10px; }
.fixed-chip { display: flex; align-items: center; gap: 4px; font-size: 11px; color: #92400E; background: var(--warning-bg); border: 1px solid #FDE68A; padding: 2px 7px; border-radius: 4px; }
.fixed-chip svg { width: 10px; height: 10px; }

.activity-span-bar { height: 4px; border-radius: 2px; background: linear-gradient(to right, var(--violet-mid), var(--violet)); margin-top: 8px; }

.side-card { background: var(--white); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 14px 16px; }
.side-card-title { font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 12px; }

.legend-item { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.legend-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.legend-label { font-size: 12.5px; color: var(--text-secondary); flex: 1; }
.legend-count { font-size: 12px; font-weight: 500; color: var(--text-primary); }

.note-box { background: var(--bg-page); border: 1px solid var(--border-light); border-radius: 7px; padding: 9px 11px; font-size: 12.5px; color: var(--text-secondary); line-height: 1.55; margin-bottom: 8px; }
.note-meta { font-size: 11px; color: var(--text-muted); margin-top: 4px; }
.add-note-btn { width: 100%; padding: 7px; border: 1px dashed var(--border-light); border-radius: 7px; background: transparent; font-size: 12.5px; color: var(--text-muted); cursor: pointer; font-family: var(--font-main); }

.template-row { display: flex; justify-content: space-between; align-items: center; padding: 5px 0; border-bottom: 1px solid var(--border-light); }
.template-row:last-child { border-bottom: none; }
.template-row-label { font-size: 12px; color: var(--text-muted); }
.template-row-value { font-size: 12.5px; font-weight: 500; color: var(--text-primary); }
.template-row-link { font-size: 12px; font-weight: 500; color: var(--violet); cursor: pointer; }
</style>
