<!-- ============================================
   RECURRA — SHARED GANTT / TIMELINE CHART (PREVIEW)
   /frontend/src/components/GanttChart.vue

   Used for lightweight timeline PREVIEWS: template detail page and
   the template create/edit wizard's live preview. For the full
   interactive Gantt shown on a cycle after it's created, see
   CycleGanttChart.vue instead — that one has grouping, status
   colors, and click-to-inspect; this one stays a simple, fast
   read-only preview on purpose.

   Renders task & activity bars on a day-based horizontal axis,
   at a fixed pixel-per-day scale so long templates produce a wide
   chart you scroll through, at a constant, always-readable scale.

   Dependency arrows: each task bar can carry a dependsOnIndex
   pointing at another entry in the SAME taskBars array (its index
   after whatever ordering the caller already applied). An elbow
   connector with an arrowhead is drawn from the right edge of the
   prerequisite bar to the left edge of the dependent bar, the
   standard "normal Gantt chart" dependency line. depName is kept
   purely for the small text label under the bar — the arrow itself
   is driven entirely by dependsOnIndex + row geometry.

   IMPORTANT layout note: this uses two separate direct children of
   the scrolling container — a sticky "sidebar" column (row labels)
   and a normally-flowing "content" column (ticks + bars) — instead
   of one sticky label per flex row. That's not a style preference:
   position:sticky reliably fails in this app's target browsers
   whenever the sticky element is wrapped in ANY intermediate
   element (even non-block, even inline-block) before reaching the
   scrolling ancestor — confirmed empirically. The sidebar must
   stay a direct child of .gantt-scroll-row. Do not reintroduce a
   per-row wrapper around the label — it will silently break
   sticky again with no console error.

   The two columns stay visually aligned purely because every row
   type (tick row / section row / activity row / task row) uses the
   same fixed height on both the sidebar and content side.
   ============================================ -->

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  // [{ name, start, end, isMandatory, isFixed, depName, dependsOnIndex }]
  // dependsOnIndex: index of the prerequisite bar within THIS SAME
  // taskBars array (after sorting), or null/undefined for none.
  taskBars: { type: Array, default: () => [] },
  // [{ id, name, start, end }]
  activityBars: { type: Array, default: () => [] },
  maxDay: { type: Number, required: true },
  // Pixels of horizontal space per day. 20px keeps short (5-10
  // day) templates compact while still making long ones (100+
  // days) wide enough to need — and reward — scrolling.
  pxPerDay: { type: Number, default: 20 },
})

const ROW_HEIGHT = 24  // tick row
const ACTIVITY_ROW_HEIGHT = 36
const TASK_ROW_HEIGHT = 36
const BAR_CENTER_Y = 18 // vertical center of a bar within its row (top:3px, height:30px)

// One flat, ordered list of rows: each activity immediately
// followed by the tasks linked to it (grouped by dependency, not by
// type), then any tasks with no linked activity at the end. No
// separate "Activities"/"Tasks" section headers — the grouping
// itself, plus a slight indent on linked tasks, is what conveys the
// structure.
const rows = computed(() => {
  const result = []
  const linkedTaskIndices = new Set()

  props.activityBars.forEach((act, actIdx) => {
    result.push({ type: 'activity', bar: act, key: 'a-' + actIdx })
    props.taskBars.forEach((task, taskIdx) => {
      if (act.id !== undefined && task.activityId === act.id) {
        result.push({ type: 'task', bar: task, key: 't-' + taskIdx, linked: true })
        linkedTaskIndices.add(taskIdx)
      }
    })
  })

  props.taskBars.forEach((task, taskIdx) => {
    if (!linkedTaskIndices.has(taskIdx)) {
      result.push({ type: 'task', bar: task, key: 't-' + taskIdx, linked: false })
    }
  })

  return result
})

const safeMaxDay = computed(() => Math.max(props.maxDay, 1))
const totalWidth = computed(() => safeMaxDay.value * props.pxPerDay)

// Which bar (if any) is currently hovered, so we can spotlight its
// day range across the full chart height — makes it obvious exactly
// which days a bar spans relative to the tick marks above, even for
// bars far down the task list.
// Tracked by row key (a stable string), not object reference —
// comparing hoveredBar to row.bar by === was unreliable (verified:
// the correct bar was being set on hover, but the equality check
// still failed on the very next render), most likely a Vue
// reactivity/proxy-identity subtlety with props-derived objects.
// Key comparison sidesteps that class of bug entirely.
const hoveredRowKey = ref(null)
const hoveredBar = computed(() => {
  const row = rows.value.find((r) => r.key === hoveredRowKey.value)
  return row ? row.bar : null
})

function highlightStyle(bar) {
  const left = bar.start * props.pxPerDay
  const width = Math.max((bar.end - bar.start) * props.pxPerDay, 14)
  return { left: `${left}px`, width: `${width}px` }
}

// Pick a "nice" day interval for the labeled major ticks so a
// 5-day template shows every day, and a 100-day template shows
// every 10th day, rather than always showing a fixed 6 ticks.
const tickInterval = computed(() => {
  const targetTickCount = 10
  const raw = safeMaxDay.value / targetTickCount
  const niceSteps = [1, 2, 5, 10, 15, 20, 25, 30, 50, 100, 150, 200]
  return niceSteps.find((step) => step >= raw) || Math.ceil(raw / 50) * 50
})

const ticks = computed(() => {
  const result = []
  for (let day = 0; day <= safeMaxDay.value; day += tickInterval.value) {
    result.push(day)
  }
  if (result[result.length - 1] !== safeMaxDay.value) {
    result.push(safeMaxDay.value)
  }
  return result
})

function positionBar(bar) {
  const left = bar.start * props.pxPerDay
  const width = Math.max((bar.end - bar.start) * props.pxPerDay, 14)
  return { left: `${left}px`, width: `${width}px` }
}

// The tooltip's own width depends on its text ("5 days" vs "12
// days"), which rarely matches the bar's width exactly — especially
// for short bars. Center it on the bar's midpoint instead of trying
// to match the bar's box, so it's never visibly off-center.
function tooltipStyle(bar) {
  const left = bar.start * props.pxPerDay
  const width = Math.max((bar.end - bar.start) * props.pxPerDay, 14)
  return { left: `${left + width / 2}px` }
}

const chartStyle = computed(() => ({
  '--timeline-width': `${totalWidth.value}px`,
  '--timeline-tick-width': `${tickInterval.value * props.pxPerDay}px`,
  '--timeline-day-width': `${props.pxPerDay}px`,
}))

// ── DEPENDENCY ARROW GEOMETRY ──────────────────────────────
// Rows are no longer two separate blocks (activities, then tasks) —
// the grouping redesign interleaves each activity with its linked
// tasks. So a bar's vertical position is wherever it actually landed
// in `rows`, not some fixed offset assuming a rigid two-block layout.
// (This only works cleanly because ACTIVITY_ROW_HEIGHT and
// TASK_ROW_HEIGHT are equal — every row is the same height.)
const chartHeight = computed(() => ROW_HEIGHT + rows.value.length * TASK_ROW_HEIGHT)

function barCenterY(bar) {
  const rowIndex = rows.value.findIndex((r) => r.bar === bar)
  return ROW_HEIGHT + rowIndex * TASK_ROW_HEIGHT + BAR_CENTER_Y
}

function barRight(bar) {
  return Math.max(bar.end * props.pxPerDay, bar.start * props.pxPerDay + 14)
}
function barLeft(bar) {
  return bar.start * props.pxPerDay
}

// One elbow connector per dependent bar: right out of the
// prerequisite's end, across/down (or up) to the dependent's row,
// then right into its start. Falls back to a routed-below connector
// if a task starts before its prerequisite ends (shouldn't normally
// happen — the backend rejects that — but never draw something
// broken if it does).
const dependencyArrows = computed(() => {
  const arrows = []
  props.taskBars.forEach((bar, i) => {
    const depIndex = bar.dependsOnIndex
    if (depIndex === null || depIndex === undefined) return
    const depBar = props.taskBars[depIndex]
    if (!depBar) return

    const fromX = barRight(depBar)
    const fromY = barCenterY(depBar)
    const toX = barLeft(bar)
    const toY = barCenterY(bar)

    let path
    if (fromY === toY) {
      path = `M ${fromX} ${fromY} L ${Math.max(toX - 6, fromX)} ${toY}`
    } else if (toX >= fromX) {
      // Clamp the elbow so it always sits strictly between fromX and
      // toX, even when the gap is very small (dependent tasks are
      // often scheduled right up against each other).
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
      const dipY = Math.max(fromY, toY) + TASK_ROW_HEIGHT / 2 - 4
      const approachX = toX - 6
      const preApproachX = approachX - 10
      path = `M ${fromX} ${fromY} L ${fromX + 10} ${fromY} L ${fromX + 10} ${dipY} L ${preApproachX} ${dipY} L ${preApproachX} ${toY} L ${approachX} ${toY}`
    }

    arrows.push({ id: `dep-arrow-${i}`, path })
  })
  return arrows
})
</script>

<template>
  <div class="gantt-chart">

    <div class="gantt-scroll-row" :style="chartStyle">

      <!-- STICKY SIDEBAR: every row's label, top to bottom -->
      <div class="gantt-sidebar">
        <div class="gantt-side-cell gantt-axis-label" :style="{ height: ROW_HEIGHT + 'px' }">Day</div>

        <div
          v-for="row in rows"
          :key="'side-' + row.key"
          class="gantt-side-cell gantt-side-label"
          :class="{ 'gantt-side-label-linked': row.type === 'task' && row.linked }"
          :style="{ height: (row.type === 'activity' ? ACTIVITY_ROW_HEIGHT : TASK_ROW_HEIGHT) + 'px' }"
          :title="row.bar.name"
        >{{ row.bar.name }}</div>
      </div>

      <!-- CONTENT: ticks + bars, top to bottom, same row heights as the sidebar -->
      <div class="gantt-content gantt-grid">

        <!-- HOVER SPOTLIGHT: full-height band across the hovered bar's day range -->
        <div
          v-if="hoveredBar"
          class="gantt-hover-highlight"
          :style="highlightStyle(hoveredBar)"
        ></div>

        <div class="gantt-tick-row" :style="{ height: ROW_HEIGHT + 'px' }">
          <div v-for="tick in ticks" :key="tick" class="gantt-tick" :style="{ left: (tick * pxPerDay) + 'px' }">
            <span>{{ tick }}</span>
          </div>
        </div>

        <div
          v-for="row in rows"
          :key="'content-' + row.key"
          class="gantt-content-cell"
          :style="{ height: (row.type === 'activity' ? ACTIVITY_ROW_HEIGHT : TASK_ROW_HEIGHT) + 'px' }"
        >
          <template v-if="row.type === 'activity'">
            <div
              class="gantt-bar gantt-bar-activity"
              :style="positionBar(row.bar)"
              @mouseenter="hoveredRowKey = row.key"
              @mouseleave="hoveredRowKey = null"
            ></div>
            <div v-if="hoveredRowKey === row.key" class="gantt-bar-tooltip" :style="tooltipStyle(row.bar)">
              {{ row.bar.end - row.bar.start }} day{{ (row.bar.end - row.bar.start) !== 1 ? 's' : '' }}
            </div>
          </template>
          <template v-else>
            <div
              class="gantt-bar"
              :class="{
                'gantt-bar-mandatory': row.bar.isMandatory,
                'gantt-bar-fixed': row.bar.isFixed,
                'gantt-bar-task': !row.bar.isMandatory && !row.bar.isFixed
              }"
              :style="positionBar(row.bar)"
              @mouseenter="hoveredRowKey = row.key"
              @mouseleave="hoveredRowKey = null"
            ></div>
            <div v-if="hoveredRowKey === row.key" class="gantt-bar-tooltip" :style="tooltipStyle(row.bar)">
              {{ row.bar.end - row.bar.start }} day{{ (row.bar.end - row.bar.start) !== 1 ? 's' : '' }}
            </div>
          </template>
        </div>

        <!-- DEPENDENCY ARROWS: one continuous SVG overlay across the
             whole chart height, drawn above the bars, standard
             elbow-connector-with-arrowhead Gantt notation. -->
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
          <path
            v-for="arrow in dependencyArrows"
            :key="arrow.id"
            :d="arrow.path"
            fill="none"
            stroke="var(--violet)"
            stroke-width="1.75"
            marker-end="url(#gantt-arrowhead)"
          />
        </svg>
      </div>

    </div>

    <!-- LEGEND: outside the scroll row entirely, always fully visible -->
    <div class="gantt-legend">
      <span class="legend-item"><span class="legend-dot dot-activity"></span>Activity</span>
      <span class="legend-item"><span class="legend-dot dot-task"></span>Task</span>
      <span class="legend-item"><span class="legend-dot dot-mandatory"></span>Mandatory</span>
      <span class="legend-item"><span class="legend-dot dot-fixed"></span>Fixed date</span>
      <span v-if="taskBars.some(b => b.dependsOnIndex !== null && b.dependsOnIndex !== undefined)" class="legend-item">
        <svg width="18" height="10" viewBox="0 0 18 10"><path d="M0 5h12" stroke="var(--violet)" stroke-width="1.75" fill="none"/><path d="M11,1 L17,5 L11,9 z" fill="var(--violet)"/></svg>
        Dependency
      </span>
    </div>

  </div>
</template>

<style scoped>
.gantt-chart {
  display: flex;
  flex-direction: column;
}

.gantt-scroll-row {
  display: flex;
  align-items: flex-start;
  padding: 14px 18px 28px 18px;
  overflow-x: auto;
}

.gantt-sidebar {
  position: sticky;
  left: 0;
  z-index: 10;
  flex-shrink: 0;
  width: 130px;
  background: var(--white);
}

.gantt-side-cell {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  font-size: var(--font-upper);
  color: var(--text-secondary);
  text-align: right;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 10px;
  box-sizing: border-box;
}

.gantt-axis-label {
  font-size: var(--font-hint);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.07em;
}

/* Tasks nested under an activity get a slight indent — this, plus
   ordering, is what conveys the grouping now that there are no
   separate "Activities"/"Tasks" section headers. */
.gantt-side-label-linked {
  padding-right: 22px;
}

.gantt-content {
  flex-shrink: 0;
  width: var(--timeline-width);
  position: relative;
}

.gantt-grid {
  background-image:
    repeating-linear-gradient(to right, rgba(15, 23, 42, 0.055) 0, rgba(15, 23, 42, 0.055) 1px, transparent 1px, transparent var(--timeline-day-width)),
    repeating-linear-gradient(to right, var(--border-light) 0, var(--border-light) 1.5px, transparent 1.5px, transparent var(--timeline-tick-width));
}

.gantt-content-cell {
  position: relative;
  box-sizing: border-box;
  border-bottom: 1px solid rgba(15, 23, 42, 0.03);
}

/* Full-height spotlight band shown while hovering a bar, so it's
   obvious exactly which days it spans relative to the tick marks
   above — sits behind the bars themselves (z-index), never blocks
   interaction with them. */
.gantt-hover-highlight {
  position: absolute;
  top: 0;
  bottom: 0;
  background: rgba(124, 58, 237, 0.07);
  border-left: 1px dashed rgba(124, 58, 237, 0.45);
  border-right: 1px dashed rgba(124, 58, 237, 0.45);
  z-index: 1;
  pointer-events: none;
}

/* Floating duration tooltip, anchored directly above the hovered
   bar (same left/width as the bar itself, via positionBar) — a
   styled replacement for the native browser title tooltip, showing
   only the duration, never the task/activity name. */
.gantt-bar-tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-hint);
  font-weight: 600;
  color: #1E293B;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 5px;
  padding: 3px 9px;
  white-space: nowrap;
  pointer-events: none;
  z-index: 5;
  box-shadow: 0 4px 12px rgba(0,0,0,0.18);
}

.gantt-bar-tooltip::before {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: var(--border-light);
}

.gantt-bar-tooltip::after {
  content: '';
  position: absolute;
  top: calc(100% - 1px);
  left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-top-color: var(--white);
}

.gantt-tick-row { position: relative; }
.gantt-tick { position: absolute; top: 2px; display: flex; flex-direction: column; align-items: center; }
.gantt-tick span { font-size: var(--font-hint); color: var(--text-muted); white-space: nowrap; }

.gantt-bar {
  position: absolute;
  top: 3px;
  height: 30px;
  border-radius: var(--radius-sm);
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
  z-index: 2;
}

.gantt-bar-activity { background: linear-gradient(90deg, #7C3AED 0%, #A78BFA 100%); }
.gantt-bar-task { background: #475569; }
.gantt-bar-mandatory { background: #EF4444; }
.gantt-bar-fixed { background: #F59E0B; }

.gantt-dep-arrows {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 3;
  pointer-events: none;
  overflow: visible;
}

.gantt-legend {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  margin: 0 18px 14px 18px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}
.legend-item { display: flex; align-items: center; gap: 6px; font-size: var(--font-hint); color: var(--text-muted); }
.legend-dot { width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }
.dot-activity { background: #7C3AED; }
.dot-task { background: #475569; }
.dot-mandatory { background: #EF4444; }
.dot-fixed { background: #F59E0B; }
</style>