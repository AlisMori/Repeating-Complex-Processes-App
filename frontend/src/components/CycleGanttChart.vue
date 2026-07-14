<!-- ============================================
   RECURRA — FULL CYCLE GANTT CHART
   /frontend/src/components/CycleGanttChart.vue

   Used ONLY on a running cycle's Gantt tab (CycleDetailView), once
   real tasks/activities/statuses exist. Not used for template
   previews or the create wizard — those use the simpler, faster
   GanttChart.vue instead.

   MS-Project style: the sidebar is a real multi-column table (Name,
   Status, Start, End, Depends on, Tags) so every row's information
   is visible at a glance with no clicking required, next to the
   usual bar timeline. Tasks nest under their activity (or group by
   tag, or stay flat) via the toggle at the top.

   DATA CONTRACT
   taskBars: [{
     id,                 // stable unique id — required
     name, start, end,   // day offsets (for bar positioning)
     startDate, endDate,  // real calendar date strings (for the table columns)
     status,             // 'pending'|'in_progress'|'completed'|'overdue'|'skipped'
     isMandatory, isFixed,
     activityId,          // matches an activityBars[].id this task belongs to, or null
     dependsOnId,         // another taskBars[].id this task depends on, or null
     depName,             // display name of the dependency (for the Depends on column)
     tags,                // [{ tag_id, tag_name }] or [string], optional
   }]
   activityBars: [{ id, name, start, end, startDate, endDate, tags }]
   maxDay: Number (required)
   pxPerDay: Number (default 20)
   defaultGroupBy: 'activity' | 'tag' | 'none' (default 'activity')

   IMPORTANT layout note: the sidebar is a sticky DIRECT child of
   .gantt-scroll-row (not wrapped in anything) — position:sticky
   reliably fails in this app's target browsers otherwise, confirmed
   empirically. Every row (sidebar + content bar) is absolutely
   positioned from a single shared `rows` layout so sidebar/content
   can never drift out of alignment regardless of grouping.
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

const TICK_ROW_HEIGHT = 34
const HEADER_ROW_HEIGHT = 26
const BAR_ROW_HEIGHT = 36
const BAR_HEIGHT = 24

// Sidebar column widths — a real table, not just a label column.
const COL = { name: 190, status: 78, start: 68, end: 68, depends: 110, tags: 130 }
const SIDEBAR_WIDTH = COL.name + COL.status + COL.start + COL.end + COL.depends + COL.tags

const safeMaxDay = computed(() => Math.max(props.maxDay, 1))
const totalWidth = computed(() => safeMaxDay.value * props.pxPerDay)

const hoveredBar = ref(null)
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

function formatShortDate(dateStr) {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })
}

const STATUS_LABELS = { pending: 'Pending', in_progress: 'In progress', completed: 'Completed', overdue: 'Overdue', skipped: 'Skipped' }
const STATUS_CLASS = { pending: 'st-pending', in_progress: 'st-in-progress', completed: 'st-completed', overdue: 'st-overdue', skipped: 'st-skipped' }

// ── ROW LAYOUT ──────────────────────────────────────────────
const rows = computed(() => {
  const result = []

  if (groupBy.value === 'none') {
    if (props.activityBars.length > 0) {
      result.push({ type: 'header', key: 'h-activities', label: 'Activities' })
      for (const a of props.activityBars) result.push({ type: 'activity', key: 'a-' + a.id, bar: a })
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
      result.push({ type: 'activity', key: 'a-' + a.id, bar: a })
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
  for (const t of props.taskBars) for (const tag of (t.tags || [])) tagNames.add(tagLabel(tag))
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
  return STATUS_CLASS[bar.status] || 'st-pending'
}

// ── DEPENDENCY ARROWS ───────────────────────────────────────
const taskRowById = computed(() => {
  const map = {}
  for (const row of rowPositions.value) if (row.type === 'task') map[row.bar.id] = row
  return map
})

function barRight(bar) { return Math.max(bar.end * props.pxPerDay, bar.start * props.pxPerDay + 14) }
function barLeft(bar) { return bar.start * props.pxPerDay }
function rowCenterY(row) { return row.y + row.height / 2 }

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

    let path
    if (fromY === toY) {
      path = `M ${fromX} ${fromY} L ${Math.max(toX - 6, fromX)} ${toY}`
    } else if (toX > fromX) {
      // Clamp the elbow so it always sits strictly between fromX and
      // toX, even when the gap is very small (dependent tasks are
      // often scheduled right up against each other). Without this,
      // a fixed 10px offset on each side can overshoot past the
      // final horizontal segment's endpoint and make the path double
      // back on itself — the "arrow bent backward" bug.
      const gap = toX - fromX
      const elbowX = fromX + Math.min(10, gap / 2)
      // The arrowhead marker's rotation (orient="auto-start-reverse")
      // is derived from the direction of THIS final segment. It must
      // always be a real, positive-length horizontal stretch —
      // clamping only with Math.max(toX - 6, elbowX) let it collapse
      // to zero (or invert) whenever the gap was small, leaving the
      // marker's orientation undefined and rendering it bent/twisted
      // instead of pointing cleanly rightward into the bar.
      const endX = Math.max(toX - 6, elbowX + 4)
      path = `M ${fromX} ${fromY} L ${elbowX} ${fromY} L ${elbowX} ${toY} L ${endX} ${toY}`
    } else {
      // Loops under intervening rows to approach the target from the
      // left. The final approach into the bar must also be a real
      // horizontal segment for the same reason as above — ending on
      // a vertical segment (straight from the dip row up/down into
      // the target row) left the arrowhead oriented vertically.
      const dipY = Math.max(fromY, toY) + BAR_ROW_HEIGHT / 2 - 4
      const approachX = toX - 6
      const preApproachX = approachX - 10
      path = `M ${fromX} ${fromY} L ${fromX + 10} ${fromY} L ${fromX + 10} ${dipY} L ${preApproachX} ${dipY} L ${preApproachX} ${toY} L ${approachX} ${toY}`
    }
    arrows.push({ id: 'dep-' + bar.id, path })
  }
  return arrows
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

      <!-- STICKY SIDEBAR: a real table — Name / Status / Start / End / Depends on / Tags -->
      <div class="gantt-sidebar" :style="{ height: chartHeight + 'px', width: SIDEBAR_WIDTH + 'px' }">

        <div class="gantt-table-header" :style="{ height: TICK_ROW_HEIGHT + 'px' }">
          <span class="gth-cell" :style="{ width: COL.name + 'px' }">Task</span>
          <span class="gth-cell gth-center" :style="{ width: COL.status + 'px' }">Status</span>
          <span class="gth-cell gth-center" :style="{ width: COL.start + 'px' }">Start</span>
          <span class="gth-cell gth-center" :style="{ width: COL.end + 'px' }">End</span>
          <span class="gth-cell" :style="{ width: COL.depends + 'px' }">Depends on</span>
          <span class="gth-cell" :style="{ width: COL.tags + 'px' }">Tags</span>
        </div>

        <template v-for="row in rowPositions" :key="row.key">
          <!-- GROUP HEADER ROW: spans full width, no columns -->
          <div
            v-if="row.type === 'header'"
            class="gantt-side-cell gantt-section-label"
            :style="{ top: row.y + 'px', height: row.height + 'px', width: SIDEBAR_WIDTH + 'px' }"
          >{{ row.label }}{{ row.count !== undefined ? ` (${row.count})` : '' }}</div>

          <!-- DATA ROW: full table row -->
          <div
            v-else
            class="gantt-table-row"
            :class="{ 'gantt-table-row-activity': row.type === 'activity' }"
            :style="{ top: row.y + 'px', height: row.height + 'px', width: SIDEBAR_WIDTH + 'px' }"
            @mouseenter="hoveredBar = row.bar"
            @mouseleave="hoveredBar = null"
          >
            <span class="gtr-cell gtr-name" :class="{ 'gtr-name-indent': row.indent }" :style="{ width: COL.name + 'px' }" :title="row.bar.name">
              <svg v-if="row.type === 'activity'" class="gtr-name-icon" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
              <span class="gtr-name-text">{{ row.bar.name }}</span>
              <svg v-if="row.type === 'task' && row.bar.isMandatory" class="gtr-flag gtr-flag-mandatory" viewBox="0 0 24 24" fill="currentColor" title="Mandatory"><path d="M12 2l2.9 6.6 7.1.6-5.4 4.7 1.6 7-6.2-3.8-6.2 3.8 1.6-7-5.4-4.7 7.1-.6z"/></svg>
              <svg v-if="row.type === 'task' && row.bar.isFixed" class="gtr-flag gtr-flag-fixed" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" title="Fixed date"><rect x="4" y="10" width="16" height="10" rx="1.5"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>
            </span>
            <span class="gtr-cell gtr-center" :style="{ width: COL.status + 'px' }">
              <span v-if="row.type === 'task'" class="gtr-status-chip" :class="barClass(row)">{{ STATUS_LABELS[row.bar.status] || row.bar.status }}</span>
            </span>
            <span class="gtr-cell gtr-center gtr-date" :style="{ width: COL.start + 'px' }">{{ formatShortDate(row.bar.startDate) }}</span>
            <span class="gtr-cell gtr-center gtr-date" :style="{ width: COL.end + 'px' }">{{ formatShortDate(row.bar.endDate) }}</span>
            <span class="gtr-cell gtr-dep" :style="{ width: COL.depends + 'px' }" :title="row.bar.depName || ''">{{ row.type === 'task' ? (row.bar.depName || '—') : '' }}</span>
            <span class="gtr-cell gtr-tags" :style="{ width: COL.tags + 'px' }">
              <template v-if="(row.bar.tags || []).length > 0">
                <span v-for="tag in row.bar.tags.slice(0, 2)" :key="tagLabel(tag)" class="gtr-tag-chip">{{ tagLabel(tag) }}</span>
                <span v-if="row.bar.tags.length > 2" class="gtr-tag-more">+{{ row.bar.tags.length - 2 }}</span>
              </template>
            </span>
          </div>
        </template>
      </div>

      <!-- CONTENT: ticks + bars -->
      <div class="gantt-content gantt-grid" :style="{ height: chartHeight + 'px' }">
        <div v-if="hoveredBar" class="gantt-hover-highlight" :style="tickStyle(hoveredBar)"></div>

        <div class="gantt-tick-row" :style="{ height: TICK_ROW_HEIGHT + 'px' }">
          <div v-for="tick in ticks" :key="tick" class="gantt-tick" :style="{ left: (tick * pxPerDay) + 'px' }">
            <span>{{ tick }}</span>
          </div>
        </div>

        <template v-for="row in rowPositions" :key="'content-' + row.key">
          <div v-if="row.type !== 'header'" class="gantt-bar-row" :style="{ top: row.y + 'px', height: row.height + 'px' }">
            <div
              class="gantt-bar"
              :class="barClass(row)"
              :style="{ ...barPositionStyle(row.bar), height: BAR_HEIGHT + 'px', top: (row.height - BAR_HEIGHT) / 2 + 'px' }"
              @mouseenter="hoveredBar = row.bar"
              @mouseleave="hoveredBar = null"
            ></div>
            <div v-if="hoveredBar === row.bar" class="gantt-bar-tooltip" :style="{ left: (row.bar.start * pxPerDay + Math.max((row.bar.end - row.bar.start) * pxPerDay, 14) / 2) + 'px' }">
              {{ row.bar.name }} · {{ row.bar.end - row.bar.start }} day{{ (row.bar.end - row.bar.start) !== 1 ? 's' : '' }}
            </div>
          </div>
        </template>

        <svg v-if="dependencyArrows.length > 0" class="gantt-dep-arrows" :width="totalWidth" :height="chartHeight" :viewBox="`0 0 ${totalWidth} ${chartHeight}`">
          <defs>
            <marker id="cgantt-arrowhead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill="var(--violet)" />
            </marker>
          </defs>
          <path v-for="arrow in dependencyArrows" :key="arrow.id" :d="arrow.path" fill="none" stroke="var(--violet)" stroke-width="1.75" marker-end="url(#cgantt-arrowhead)" />
        </svg>
      </div>

    </div>

    <!-- LEGEND -->
    <div class="gantt-legend">
      <span class="legend-item"><span class="legend-dot dot-activity"></span>Activity</span>
      <span class="legend-item"><span class="legend-dot dot-pending"></span>Pending</span>
      <span class="legend-item"><span class="legend-dot dot-in-progress"></span>In progress</span>
      <span class="legend-item"><span class="legend-dot dot-completed"></span>Completed</span>
      <span class="legend-item"><span class="legend-dot dot-overdue"></span>Overdue</span>
      <span class="legend-item"><span class="legend-dot dot-skipped"></span>Skipped</span>
      <span class="legend-item"><svg width="11" height="11" viewBox="0 0 24 24" fill="var(--danger)"><path d="M12 2l2.9 6.6 7.1.6-5.4 4.7 1.6 7-6.2-3.8-6.2 3.8 1.6-7-5.4-4.7 7.1-.6z"/></svg>Mandatory</span>
      <span class="legend-item"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#92400E" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="10" width="16" height="10" rx="1.5"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>Fixed date</span>
      <span v-if="dependencyArrows.length > 0" class="legend-item">
        <svg width="18" height="10" viewBox="0 0 18 10"><path d="M0 5h12" stroke="var(--violet)" stroke-width="1.75" fill="none"/><path d="M11,1 L17,5 L11,9 z" fill="var(--violet)"/></svg>
        Dependency
      </span>
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

.gantt-sidebar { position: sticky; left: 0; z-index: 2; flex-shrink: 0; background: var(--white); border-right: 1px solid var(--border-light); }

/* TABLE HEADER ROW */
.gantt-table-header { display: flex; align-items: center; border-bottom: 1.5px solid var(--border-light); background: var(--bg-page); }
.gth-cell { font-size: var(--font-hint); font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; padding: 0 8px; box-sizing: border-box; flex-shrink: 0; }
.gth-center { text-align: center; }

/* GROUP HEADER ROW (spans full width) */
.gantt-side-cell {
  position: absolute; left: 0; display: flex; align-items: center;
  font-size: var(--font-hint); color: var(--text-muted); white-space: nowrap; box-sizing: border-box;
}
.gantt-section-label { font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; padding-left: 10px; background: var(--bg-page); border-bottom: 1px solid var(--border-light); border-top: 1px solid var(--border-light); }

/* DATA TABLE ROW */
.gantt-table-row { position: absolute; left: 0; display: flex; align-items: center; box-sizing: border-box; border-bottom: 1px solid rgba(15, 23, 42, 0.05); }
.gantt-table-row:hover { background: var(--bg-page); }
.gantt-table-row-activity { background: var(--violet-bg); }
.gantt-table-row-activity:hover { background: var(--violet-mid); }

.gtr-cell { padding: 0 8px; box-sizing: border-box; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--font-hint); color: var(--text-secondary); }
.gtr-center { text-align: center; }
.gtr-date { color: var(--text-muted); font-size: var(--font-hint); }

.gtr-name { display: flex; align-items: center; gap: 5px; font-size: var(--font-label); font-weight: 500; color: var(--text-primary); }
.gtr-name-indent { padding-left: 22px; }
.gtr-name-icon { width: 13px; height: 13px; flex-shrink: 0; }
.gtr-name-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gtr-flag { width: 11px; height: 11px; flex-shrink: 0; }
.gtr-flag-mandatory { color: var(--danger); }
.gtr-flag-fixed { color: #92400E; }

.gtr-dep { color: var(--text-muted); }

.gtr-tags { display: flex; align-items: center; gap: 3px; }
.gtr-tag-chip { font-size: 10px; font-weight: 600; background: var(--violet-bg); color: var(--violet); padding: 1px 6px; border-radius: 20px; white-space: nowrap; }
.gtr-tag-more { font-size: 10px; font-weight: 600; color: var(--text-muted); }

.gtr-status-chip { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 20px; color: var(--white); white-space: nowrap; }
.st-pending { background: #94A3B8; }
.st-in-progress { background: #F59E0B; }
.st-completed { background: #22C55E; }
.st-overdue { background: #EF4444; }
.st-skipped { background: #64748B; }

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

.gantt-tick-row { position: relative; border-bottom: 1.5px solid var(--border-light); background: var(--bg-page); }
.gantt-tick { position: absolute; top: 8px; display: flex; flex-direction: column; align-items: center; }
.gantt-tick span { font-size: var(--font-hint); font-weight: 600; color: var(--text-muted); white-space: nowrap; }

.gantt-bar {
  position: absolute; z-index: 2; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.18);
  cursor: default; transition: opacity 0.15s, box-shadow 0.15s;
}
.gantt-bar:hover { opacity: 0.88; box-shadow: 0 2px 6px rgba(0,0,0,0.24); }

.gantt-bar-activity { background: linear-gradient(90deg, #7C3AED 0%, #A78BFA 100%); }

.gantt-dep-arrows { position: absolute; top: 0; left: 0; z-index: 3; pointer-events: none; overflow: visible; }

.gantt-legend { display: flex; gap: 14px; flex-wrap: wrap; margin: 0 18px 14px 18px; padding-top: 12px; border-top: 1px solid var(--border-light); }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: var(--font-hint); color: var(--text-muted); }
.legend-dot { width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }
.dot-activity { background: #7C3AED; }
.dot-pending { background: #94A3B8; }
.dot-in-progress { background: #F59E0B; }
.dot-completed { background: #22C55E; }
.dot-overdue { background: #EF4444; }
.dot-skipped { background: #64748B; }
</style>
