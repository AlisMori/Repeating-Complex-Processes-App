<!-- ============================================
   RECURRA — FULL CYCLE GANTT CHART
   /frontend/src/components/CycleGanttChart.vue

   Used ONLY on a running cycle's Gantt tab (CycleDetailView), once
   real tasks/activities/statuses exist. Not used for template
   previews or the create wizard — those use the simpler, faster
   GanttChart.vue instead. This one is the full interactive version:
   tasks grouped under their activity (or by tag, or ungrouped) with
   a toggle to switch, status-aware coloring, mandatory/fixed badges,
   dependency arrows, and a click-to-inspect detail panel (dates,
   status, dependency, tags).

   DATA CONTRACT
   taskBars: [{
     id,                 // stable unique id — required
     name, start, end,   // day offsets
     status,             // 'pending'|'in_progress'|'completed'|'overdue'|'skipped'
                          // or null/undefined for a template task (no runtime status yet)
     isMandatory, isFixed,
     activityId,          // matches an activityBars[].id this task belongs to, or null
     dependsOnId,         // another taskBars[].id this task depends on, or null
     depName,             // display name of the dependency (for the detail panel)
     tags,                // [{ tag_id, tag_name }] or [string], optional
   }]
   activityBars: [{ id, name, start, end }]
   maxDay: Number (required)
   pxPerDay: Number (default 20)
   defaultGroupBy: 'activity' | 'tag' | 'none' (default 'activity')

   IMPORTANT layout note: the sidebar is a sticky DIRECT child of
   .gantt-scroll-row (not wrapped in anything) — position:sticky
   reliably fails in this app's target browsers otherwise, confirmed
   empirically. Every row (sidebar label + content bar) is now
   absolutely positioned from a single shared `rows` layout instead
   of relying on matched sequential flow heights, so sidebar/content
   can never drift out of alignment regardless of how grouping
   changes the row list.
   ============================================ -->

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  taskBars: { type: Array, default: () => [] },
  activityBars: { type: Array, default: () => [] },
  maxDay: { type: Number, required: true },
  pxPerDay: { type: Number, default: 20 },
  defaultGroupBy: { type: String, default: 'activity' },
})

const TICK_ROW_HEIGHT = 26
const HEADER_ROW_HEIGHT = 24
const BAR_ROW_HEIGHT = 32
const BAR_HEIGHT = 24

const safeMaxDay = computed(() => Math.max(props.maxDay, 1))
const totalWidth = computed(() => safeMaxDay.value * props.pxPerDay)

const hoveredBar = ref(null)
const selectedBar = ref(null)
const groupBy = ref(['activity', 'tag', 'none'].includes(props.defaultGroupBy) ? props.defaultGroupBy : 'activity')

const hasAnyActivity = computed(() => props.activityBars.length > 0)
const hasAnyTag = computed(() => props.taskBars.some(b => (b.tags || []).length > 0))

function tickStyle(bar) {
  const left = bar.start * props.pxPerDay
  const width = Math.max((bar.end - bar.start) * props.pxPerDay, 14)
  return { left: `${left}px`, width: `${width}px` }
}

const tickInterval = computed(() => {
  const targetTickCount = 10
  const raw = safeMaxDay.value / targetTickCount
  const niceSteps = [1, 2, 5, 10, 15, 20, 25, 30, 50, 100, 150, 200]
  return niceSteps.find((step) => step >= raw) || Math.ceil(raw / 50) * 50
})

const ticks = computed(() => {
  const result = []
  for (let day = 0; day <= safeMaxDay.value; day += tickInterval.value) result.push(day)
  if (result[result.length - 1] !== safeMaxDay.value) result.push(safeMaxDay.value)
  return result
})

const chartStyle = computed(() => ({
  '--timeline-width': `${totalWidth.value}px`,
  '--timeline-tick-width': `${tickInterval.value * props.pxPerDay}px`,
  '--timeline-day-width': `${props.pxPerDay}px`,
}))

function tagLabel(tag) {
  return typeof tag === 'string' ? tag : tag.tag_name
}

function statusLabel(status) {
  const map = { pending: 'Pending', in_progress: 'In progress', completed: 'Completed', overdue: 'Overdue', skipped: 'Skipped' }
  return map[status] || null
}

// ── ROW LAYOUT ──────────────────────────────────────────────
// Builds one flat, ordered list of rows (headers + bars) for the
// current grouping mode. Sidebar and content both render from this
// SAME list so they can never fall out of alignment.
const rows = computed(() => {
  const result = []

  if (groupBy.value === 'none') {
    if (props.activityBars.length > 0) {
      result.push({ type: 'header', key: 'h-activities', label: 'Activities' })
      for (const a of props.activityBars) result.push({ type: 'activity', key: 'a-' + a.id, bar: a, indent: false })
    }
    if (props.taskBars.length > 0) {
      result.push({ type: 'header', key: 'h-tasks', label: 'Tasks' })
      for (const t of props.taskBars) result.push({ type: 'task', key: 't-' + t.id, bar: t, indent: false })
    }
    return result
  }

  if (groupBy.value === 'activity') {
    const assignedIds = new Set()
    for (const a of props.activityBars) {
      result.push({ type: 'activity', key: 'a-' + a.id, bar: a, indent: false, isGroupParent: true })
      const children = props.taskBars.filter(t => t.activityId === a.id)
      for (const t of children) {
        assignedIds.add(t.id)
        result.push({ type: 'task', key: 't-' + t.id, bar: t, indent: true })
      }
    }
    const unassigned = props.taskBars.filter(t => !assignedIds.has(t.id))
    if (unassigned.length > 0) {
      result.push({ type: 'header', key: 'h-unassigned', label: props.activityBars.length > 0 ? 'Not part of an activity' : 'Tasks' })
      for (const t of unassigned) result.push({ type: 'task', key: 't-' + t.id, bar: t, indent: false })
    }
    return result
  }

  // groupBy === 'tag'
  const tagNames = new Set()
  for (const t of props.taskBars) {
    for (const tag of (t.tags || [])) tagNames.add(tagLabel(tag))
  }
  const sortedTags = [...tagNames].sort((a, b) => a.localeCompare(b))
  for (const tagName of sortedTags) {
    const members = props.taskBars.filter(t => (t.tags || []).some(tag => tagLabel(tag) === tagName))
    result.push({ type: 'header', key: 'h-tag-' + tagName, label: tagName, count: members.length })
    for (const t of members) result.push({ type: 'task', key: 'tag-' + tagName + '-t-' + t.id, bar: t, indent: false })
  }
  const untagged = props.taskBars.filter(t => (t.tags || []).length === 0)
  if (untagged.length > 0) {
    result.push({ type: 'header', key: 'h-untagged', label: 'Untagged', count: untagged.length })
    for (const t of untagged) result.push({ type: 'task', key: 'untagged-t-' + t.id, bar: t, indent: false })
  }
  return result
})

const rowPositions = computed(() => {
  let top = TICK_ROW_HEIGHT
  return rows.value.map(row => {
    const height = row.type === 'header' ? HEADER_ROW_HEIGHT : BAR_ROW_HEIGHT
    const y = top
    top += height
    return { ...row, y, height }
  })
})

const chartHeight = computed(() => {
  const last = rowPositions.value[rowPositions.value.length - 1]
  return last ? last.y + last.height : TICK_ROW_HEIGHT
})

function barPositionStyle(bar) {
  const left = bar.start * props.pxPerDay
  const width = Math.max((bar.end - bar.start) * props.pxPerDay, 14)
  return { left: `${left}px`, width: `${width}px` }
}

function barClass(row) {
  const bar = row.bar
  if (row.type === 'activity') return 'gantt-bar-activity'
  // Cycle context: color purely by real runtime status.
  if (bar.status) {
    return {
      pending: 'gantt-bar-pending',
      in_progress: 'gantt-bar-in-progress',
      completed: 'gantt-bar-completed',
      overdue: 'gantt-bar-overdue',
      skipped: 'gantt-bar-skipped',
    }[bar.status] || 'gantt-bar-pending'
  }
  // Template context: no runtime status yet, fall back to
  // mandatory/fixed as the bar's own identity.
  if (bar.isMandatory) return 'gantt-bar-mandatory'
  if (bar.isFixed) return 'gantt-bar-fixed'
  return 'gantt-bar-task'
}

function onBarClick(row) {
  selectedBar.value = selectedBar.value === row ? null : row
}

// ── DEPENDENCY ARROWS ───────────────────────────────────────
// Only resolvable when both ends of a dependency are actually
// rendered as bars right now — in "group by tag" mode a task can
// appear more than once, the arrow follows whichever instance was
// laid out last for that task id.
const taskRowById = computed(() => {
  const map = {}
  for (const row of rowPositions.value) {
    if (row.type === 'task') map[row.bar.id] = row
  }
  return map
})

function barRight(bar) {
  return Math.max(bar.end * props.pxPerDay, bar.start * props.pxPerDay + 14)
}
function barLeft(bar) {
  return bar.start * props.pxPerDay
}
function rowCenterY(row) {
  return row.y + row.height / 2
}

const dependencyArrows = computed(() => {
  const arrows = []
  for (const bar of props.taskBars) {
    if (!bar.dependsOnId) continue
    const fromRow = taskRowById.value[bar.dependsOnId]
    const toRow = taskRowById.value[bar.id]
    if (!fromRow || !toRow) continue

    const fromX = barRight(fromRow.bar)
    const fromY = rowCenterY(fromRow)
    const toX = barLeft(toRow.bar)
    const toY = rowCenterY(toRow)
    const elbowX = Math.max(fromX + 10, toX - 10)

    let path
    if (fromY === toY) {
      path = `M ${fromX} ${fromY} L ${Math.max(toX - 6, fromX)} ${toY}`
    } else if (toX > fromX) {
      path = `M ${fromX} ${fromY} L ${elbowX} ${fromY} L ${elbowX} ${toY} L ${toX - 6} ${toY}`
    } else {
      const dipY = Math.max(fromY, toY) + BAR_ROW_HEIGHT / 2 - 4
      path = `M ${fromX} ${fromY} L ${fromX + 10} ${fromY} L ${fromX + 10} ${dipY} L ${toX - 6} ${dipY} L ${toX - 6} ${toY}`
    }
    arrows.push({ id: 'dep-' + bar.id, path })
  }
  return arrows
})

// ── DETAIL PANEL POSITION ────────────────────────────────────
const selectedRowLayout = computed(() => {
  if (!selectedBar.value) return null
  return rowPositions.value.find(r => r.key === selectedBar.value.key) || null
})

const panelStyle = computed(() => {
  if (!selectedRowLayout.value) return {}
  const bar = selectedRowLayout.value.bar
  const left = Math.min(bar.start * props.pxPerDay, Math.max(totalWidth.value - 260, 0))
  return { left: `${left}px`, top: `${selectedRowLayout.value.y + selectedRowLayout.value.height + 4}px` }
})
</script>

<template>
  <div class="gantt-chart">

    <!-- CONTROLS -->
    <div class="gantt-controls">
      <span class="gantt-controls-label">Group by</span>
      <div class="gantt-group-toggle">
        <button type="button" class="gantt-group-btn" :class="{ active: groupBy === 'activity' }" :disabled="!hasAnyActivity" @click="groupBy = 'activity'">Activity</button>
        <button type="button" class="gantt-group-btn" :class="{ active: groupBy === 'tag' }" :disabled="!hasAnyTag" @click="groupBy = 'tag'">Tag</button>
        <button type="button" class="gantt-group-btn" :class="{ active: groupBy === 'none' }" @click="groupBy = 'none'">None</button>
      </div>
    </div>

    <div class="gantt-scroll-row" :style="chartStyle">

      <!-- STICKY SIDEBAR -->
      <div class="gantt-sidebar" :style="{ height: chartHeight + 'px' }">
        <div class="gantt-side-cell gantt-axis-label" :style="{ top: '0px', height: TICK_ROW_HEIGHT + 'px' }">Day</div>
        <div
          v-for="row in rowPositions"
          :key="row.key"
          class="gantt-side-cell"
          :class="row.type === 'header' ? 'gantt-section-label' : (row.indent ? 'gantt-side-label gantt-side-label-indent' : 'gantt-side-label')"
          :style="{ top: row.y + 'px', height: row.height + 'px' }"
          :title="row.type === 'header' ? row.label : row.bar.name"
          @click="row.type !== 'header' && onBarClick(row)"
        >
          {{ row.type === 'header' ? row.label + (row.count !== undefined ? ` (${row.count})` : '') : row.bar.name }}
        </div>
      </div>

      <!-- CONTENT -->
      <div class="gantt-content gantt-grid" :style="{ height: chartHeight + 'px' }">
        <div v-if="hoveredBar" class="gantt-hover-highlight" :style="tickStyle(hoveredBar)"></div>

        <div class="gantt-tick-row" :style="{ height: TICK_ROW_HEIGHT + 'px' }">
          <div v-for="tick in ticks" :key="tick" class="gantt-tick" :style="{ left: (tick * pxPerDay) + 'px' }">
            <span>{{ tick }}</span>
          </div>
        </div>

        <template v-for="row in rowPositions" :key="'content-' + row.key">
          <div
            v-if="row.type !== 'header'"
            class="gantt-bar-row"
            :style="{ top: row.y + 'px', height: row.height + 'px' }"
          >
            <div
              class="gantt-bar"
              :class="barClass(row)"
              :style="{ ...barPositionStyle(row.bar), height: BAR_HEIGHT + 'px', top: (row.height - BAR_HEIGHT) / 2 + 'px' }"
              @mouseenter="hoveredBar = row.bar"
              @mouseleave="hoveredBar = null"
              @click="onBarClick(row)"
            >
              <svg v-if="row.type === 'task' && row.bar.isMandatory" class="gantt-bar-icon gantt-bar-icon-mandatory" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.6 7.1.6-5.4 4.7 1.6 7-6.2-3.8-6.2 3.8 1.6-7-5.4-4.7 7.1-.6z"/></svg>
              <svg v-if="row.type === 'task' && row.bar.isFixed" class="gantt-bar-icon gantt-bar-icon-fixed" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="10" width="16" height="10" rx="1.5"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>
              <span v-if="(row.bar.tags || []).length > 0" class="gantt-bar-tag-dot"></span>
            </div>
            <div v-if="hoveredBar === row.bar && selectedBar !== row" class="gantt-bar-tooltip" :style="{ left: (row.bar.start * pxPerDay + Math.max((row.bar.end - row.bar.start) * pxPerDay, 14) / 2) + 'px' }">
              {{ row.bar.name }} · {{ row.bar.end - row.bar.start }} day{{ (row.bar.end - row.bar.start) !== 1 ? 's' : '' }}
            </div>
          </div>
        </template>

        <svg
          v-if="dependencyArrows.length > 0"
          class="gantt-dep-arrows"
          :width="totalWidth"
          :height="chartHeight"
          :viewBox="`0 0 ${totalWidth} ${chartHeight}`"
        >
          <defs>
            <marker id="gantt-arrowhead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill="var(--violet)" />
            </marker>
          </defs>
          <path v-for="arrow in dependencyArrows" :key="arrow.id" :d="arrow.path" fill="none" stroke="var(--violet)" stroke-width="1.75" marker-end="url(#gantt-arrowhead)" />
        </svg>

        <!-- DETAIL PANEL: click a bar to inspect status, dependency, tags -->
        <div v-if="selectedRowLayout" class="gantt-detail-panel" :style="panelStyle">
          <div class="gdp-header">
            <span class="gdp-name">{{ selectedRowLayout.bar.name }}</span>
            <button type="button" class="gdp-close" @click="selectedBar = null">×</button>
          </div>
          <div class="gdp-row"><span class="gdp-label">Days</span><span>{{ selectedRowLayout.bar.start }}–{{ selectedRowLayout.bar.end }}</span></div>
          <div v-if="statusLabel(selectedRowLayout.bar.status)" class="gdp-row"><span class="gdp-label">Status</span><span class="gdp-status-chip" :class="barClass(selectedRowLayout)">{{ statusLabel(selectedRowLayout.bar.status) }}</span></div>
          <div v-if="selectedRowLayout.type === 'task' && selectedRowLayout.bar.isMandatory" class="gdp-row"><span class="gdp-label">Mandatory</span><span>Yes</span></div>
          <div v-if="selectedRowLayout.type === 'task' && selectedRowLayout.bar.isFixed" class="gdp-row"><span class="gdp-label">Fixed date</span><span>Yes</span></div>
          <div v-if="selectedRowLayout.bar.depName" class="gdp-row"><span class="gdp-label">Depends on</span><span>{{ selectedRowLayout.bar.depName }}</span></div>
          <div v-if="(selectedRowLayout.bar.tags || []).length > 0" class="gdp-tags">
            <span v-for="tag in selectedRowLayout.bar.tags" :key="tagLabel(tag)" class="gdp-tag-chip">{{ tagLabel(tag) }}</span>
          </div>
        </div>
      </div>

    </div>

    <!-- LEGEND -->
    <div class="gantt-legend">
      <span class="legend-item"><span class="legend-dot dot-activity"></span>Activity</span>
      <template v-if="taskBars.some(b => b.status)">
        <span class="legend-item"><span class="legend-dot dot-pending"></span>Pending</span>
        <span class="legend-item"><span class="legend-dot dot-in-progress"></span>In progress</span>
        <span class="legend-item"><span class="legend-dot dot-completed"></span>Completed</span>
        <span class="legend-item"><span class="legend-dot dot-overdue"></span>Overdue</span>
        <span class="legend-item"><span class="legend-dot dot-skipped"></span>Skipped</span>
      </template>
      <template v-else>
        <span class="legend-item"><span class="legend-dot dot-task"></span>Task</span>
        <span class="legend-item"><span class="legend-dot dot-mandatory"></span>Mandatory</span>
        <span class="legend-item"><span class="legend-dot dot-fixed"></span>Fixed date</span>
      </template>
      <span v-if="dependencyArrows.length > 0" class="legend-item">
        <svg width="18" height="10" viewBox="0 0 18 10"><path d="M0 5h12" stroke="var(--violet)" stroke-width="1.75" fill="none"/><path d="M11,1 L17,5 L11,9 z" fill="var(--violet)"/></svg>
        Dependency
      </span>
      <span v-if="hasAnyTag" class="legend-item"><span class="gantt-bar-tag-dot legend-tag-dot"></span>Has tags — click a bar</span>
    </div>

  </div>
</template>

<style scoped>
.gantt-chart { display: flex; flex-direction: column; }

.gantt-controls { display: flex; align-items: center; gap: 10px; padding: 12px 18px 0; }
.gantt-controls-label { font-size: var(--font-hint); font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
.gantt-group-toggle { display: flex; gap: 3px; background: var(--bg-page); border: 1px solid var(--border-light); border-radius: 7px; padding: 2px; }
.gantt-group-btn { font-size: var(--font-hint); font-weight: 600; padding: 4px 11px; border: none; border-radius: 5px; background: transparent; color: var(--text-secondary); cursor: pointer; font-family: var(--font-main); }
.gantt-group-btn.active { background: var(--white); color: var(--violet); box-shadow: var(--shadow-sm); }
.gantt-group-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.gantt-scroll-row { display: flex; align-items: flex-start; padding: 14px 18px; overflow-x: auto; overflow-y: visible; position: relative; }

.gantt-sidebar { position: sticky; left: 0; z-index: 2; flex-shrink: 0; width: 150px; background: var(--white); }

.gantt-side-cell {
  position: absolute; left: 0; right: 0; display: flex; align-items: center; justify-content: flex-end;
  font-size: var(--font-upper); color: var(--text-secondary); text-align: right; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; padding-right: 10px; box-sizing: border-box; cursor: pointer;
}
.gantt-side-label:hover { color: var(--violet); }
.gantt-side-label-indent { padding-right: 20px; }
.gantt-side-label-indent::after { content: ''; }

.gantt-axis-label { position: absolute; font-size: var(--font-hint); font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.07em; cursor: default; }
.gantt-section-label { font-size: var(--font-hint); font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; justify-content: flex-start; padding-left: 2px; cursor: default; }

.gantt-content { flex-shrink: 0; width: var(--timeline-width); position: relative; }

.gantt-grid {
  background-image:
    repeating-linear-gradient(to right, rgba(15, 23, 42, 0.055) 0, rgba(15, 23, 42, 0.055) 1px, transparent 1px, transparent var(--timeline-day-width)),
    repeating-linear-gradient(to right, var(--border-light) 0, var(--border-light) 1.5px, transparent 1.5px, transparent var(--timeline-tick-width));
}

.gantt-bar-row { position: absolute; left: 0; right: 0; border-bottom: 1px solid rgba(15, 23, 42, 0.03); }

.gantt-hover-highlight {
  position: absolute; top: 0; bottom: 0; background: rgba(124, 58, 237, 0.07);
  border-left: 1px dashed rgba(124, 58, 237, 0.45); border-right: 1px dashed rgba(124, 58, 237, 0.45);
  z-index: 1; pointer-events: none;
}

.gantt-bar-tooltip {
  position: absolute; bottom: calc(100% + 4px); transform: translateX(-50%);
  display: flex; align-items: center; justify-content: center;
  font-size: var(--font-hint); font-weight: 600; color: var(--white); background: #1E293B;
  border-radius: 5px; padding: 3px 9px; white-space: nowrap; pointer-events: none; z-index: 6;
  box-shadow: 0 2px 6px rgba(0,0,0,0.2);
}

.gantt-tick-row { position: relative; }
.gantt-tick { position: absolute; top: 2px; display: flex; flex-direction: column; align-items: center; }
.gantt-tick span { font-size: var(--font-hint); color: var(--text-muted); white-space: nowrap; }

.gantt-bar {
  position: absolute; z-index: 2; border-radius: var(--radius-sm); box-shadow: 0 1px 3px rgba(0,0,0,0.15);
  cursor: pointer; transition: opacity 0.15s, box-shadow 0.15s; display: flex; align-items: center; padding: 0 4px; gap: 3px;
}
.gantt-bar:hover { opacity: 0.88; box-shadow: 0 2px 6px rgba(0,0,0,0.22); }

.gantt-bar-activity { background: linear-gradient(90deg, #7C3AED 0%, #A78BFA 100%); }
.gantt-bar-task { background: #475569; }
.gantt-bar-mandatory { background: #EF4444; }
.gantt-bar-fixed { background: #F59E0B; }

.gantt-bar-pending { background: #CBD5E1; }
.gantt-bar-in-progress { background: #F59E0B; }
.gantt-bar-completed { background: #22C55E; }
.gantt-bar-overdue { background: #EF4444; }
.gantt-bar-skipped { background: #94A3B8; }

.gantt-bar-icon { width: 11px; height: 11px; color: rgba(255,255,255,0.95); flex-shrink: 0; }
.gantt-bar-tag-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--white); border: 1.5px solid rgba(0,0,0,0.15); flex-shrink: 0; margin-left: auto; }
.legend-tag-dot { display: inline-block; background: var(--violet); border: none; }

.gantt-dep-arrows { position: absolute; top: 0; left: 0; z-index: 3; pointer-events: none; overflow: visible; }

/* DETAIL PANEL */
.gantt-detail-panel {
  position: absolute; z-index: 8; width: 240px; background: var(--white); border: 1px solid var(--border-light);
  border-radius: var(--radius-md); box-shadow: var(--shadow-lg); padding: 10px 12px;
}
.gdp-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; padding-bottom: 6px; border-bottom: 1px solid var(--border-light); }
.gdp-name { font-size: var(--font-label); font-weight: 600; color: var(--text-primary); }
.gdp-close { border: none; background: none; font-size: 16px; line-height: 1; color: var(--text-muted); cursor: pointer; padding: 0 2px; }
.gdp-close:hover { color: var(--text-primary); }
.gdp-row { display: flex; align-items: center; justify-content: space-between; font-size: var(--font-hint); color: var(--text-secondary); padding: 3px 0; gap: 10px; }
.gdp-label { color: var(--text-muted); }
.gdp-status-chip { font-size: var(--font-hint); font-weight: 600; color: var(--white); padding: 1px 8px; border-radius: 10px; }
.gdp-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--border-light); }
.gdp-tag-chip { font-size: var(--font-hint); font-weight: 500; background: var(--violet-bg); color: var(--violet); padding: 2px 8px; border-radius: 20px; }

.gantt-legend { display: flex; gap: 14px; flex-wrap: wrap; margin: 0 18px 14px 18px; padding-top: 12px; border-top: 1px solid var(--border-light); }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: var(--font-hint); color: var(--text-muted); }
.legend-dot { width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }
.dot-activity { background: #7C3AED; }
.dot-task { background: #475569; }
.dot-mandatory { background: #EF4444; }
.dot-fixed { background: #F59E0B; }
.dot-pending { background: #CBD5E1; }
.dot-in-progress { background: #F59E0B; }
.dot-completed { background: #22C55E; }
.dot-overdue { background: #EF4444; }
.dot-skipped { background: #94A3B8; }
</style>
