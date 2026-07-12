<!-- ============================================
   RECURRA — SHARED GANTT / TIMELINE CHART
   /frontend/src/components/GanttChart.vue

   Renders task & activity bars on a day-based horizontal axis,
   at a fixed pixel-per-day scale so long templates produce a wide
   chart you scroll through, at a constant, always-readable scale.

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
  // [{ name, start, end, isMandatory, isFixed, depName }]
  taskBars: { type: Array, default: () => [] },
  // [{ name, start, end }]
  activityBars: { type: Array, default: () => [] },
  maxDay: { type: Number, required: true },
  // Pixels of horizontal space per day. 20px keeps short (5-10
  // day) templates compact while still making long ones (100+
  // days) wide enough to need — and reward — scrolling.
  pxPerDay: { type: Number, default: 20 },
})

const ROW_HEIGHT = 24  // tick row, section row
const ACTIVITY_ROW_HEIGHT = 36
const TASK_ROW_HEIGHT = 46 // extra room for an optional dependency line

const safeMaxDay = computed(() => Math.max(props.maxDay, 1))
const totalWidth = computed(() => safeMaxDay.value * props.pxPerDay)

const hoveredBar = ref(null)

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
</script>

<template>
  <div class="gantt-chart">

    <div class="gantt-scroll-row" :style="chartStyle">

      <!-- STICKY SIDEBAR: every row's label, top to bottom -->
      <div class="gantt-sidebar">
        <div class="gantt-side-cell gantt-axis-label" :style="{ height: ROW_HEIGHT + 'px' }">Day</div>

        <div v-if="activityBars.length > 0" class="gantt-side-cell gantt-section-label" :style="{ height: ROW_HEIGHT + 'px' }">Activities</div>
        <div
          v-for="bar in activityBars"
          :key="'a-side-' + bar.name"
          class="gantt-side-cell gantt-side-label"
          :style="{ height: ACTIVITY_ROW_HEIGHT + 'px' }"
          :title="bar.name"
        >{{ bar.name }}</div>

        <div v-if="taskBars.length > 0" class="gantt-side-cell gantt-section-label" :style="{ height: ROW_HEIGHT + 'px' }">Tasks</div>
        <div
          v-for="bar in taskBars"
          :key="'t-side-' + bar.name"
          class="gantt-side-cell gantt-side-label"
          :style="{ height: TASK_ROW_HEIGHT + 'px' }"
          :title="bar.name"
        >{{ bar.name }}</div>
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

        <div v-if="activityBars.length > 0" class="gantt-content-cell" :style="{ height: ROW_HEIGHT + 'px' }"></div>
        <div
          v-for="bar in activityBars"
          :key="'a-content-' + bar.name"
          class="gantt-content-cell"
          :style="{ height: ACTIVITY_ROW_HEIGHT + 'px' }"
        >
        <div
            class="gantt-bar gantt-bar-activity"
            :style="positionBar(bar)"
            @mouseenter="hoveredBar = bar"
            @mouseleave="hoveredBar = null"
          ></div>
          <div v-if="hoveredBar === bar" class="gantt-bar-tooltip" :style="tooltipStyle(bar)">
            {{ bar.end - bar.start }} day{{ (bar.end - bar.start) !== 1 ? 's' : '' }}
          </div>
        </div>

        <div v-if="taskBars.length > 0" class="gantt-content-cell" :style="{ height: ROW_HEIGHT + 'px' }"></div>
        <div
          v-for="bar in taskBars"
          :key="'t-content-' + bar.name"
          class="gantt-content-cell"
          :style="{ height: TASK_ROW_HEIGHT + 'px' }"
        >
          <div
            class="gantt-bar"
            :class="{
              'gantt-bar-mandatory': bar.isMandatory,
              'gantt-bar-fixed': bar.isFixed,
              'gantt-bar-task': !bar.isMandatory && !bar.isFixed
            }"
            :style="positionBar(bar)"
            @mouseenter="hoveredBar = bar"
            @mouseleave="hoveredBar = null"
          ></div>
          <div v-if="bar.depName" class="gantt-dep-row" :style="{ left: (bar.start * pxPerDay) + 'px' }">
            <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M2 6h8M7 3l3 3-3 3"/>
            </svg>
            after {{ bar.depName }}
          </div>
        </div>
      </div>

    </div>

    <!-- LEGEND: outside the scroll row entirely, always fully visible -->
    <div class="gantt-legend">
      <span class="legend-item"><span class="legend-dot dot-activity"></span>Activity</span>
      <span class="legend-item"><span class="legend-dot dot-task"></span>Task</span>
      <span class="legend-item"><span class="legend-dot dot-mandatory"></span>Mandatory</span>
      <span class="legend-item"><span class="legend-dot dot-fixed"></span>Fixed date</span>
    </div>

  </div>
</template>

<style scoped>
.gantt-chart {
  display: flex;
  flex-direction: column;
}

/* This is the actual scrolling element. Sidebar and content MUST
   stay direct children of THIS, never nested in an extra wrapper —
   see the note in the script block above. */
.gantt-scroll-row {
  display: flex;
  align-items: flex-start;
  padding: 14px 18px;
  overflow-x: auto;
}

/* Sticky sidebar MUST stay a direct child of .gantt-scroll-row. */
.gantt-sidebar {
  position: sticky;
  left: 0;
  z-index: 2;
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

.gantt-section-label {
  font-size: var(--font-hint);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.07em;
  justify-content: flex-start;
  padding-left: 2px;
}

.gantt-content {
  flex-shrink: 0;
  width: var(--timeline-width);
  position: relative;
}

/* Two layered gridlines: a faint one every single day (so you can
   always see exactly where "day N" is, even between labeled
   ticks), and a slightly stronger one at the labeled interval. */
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

.gantt-bar-tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-hint);
  font-weight: 600;
  color: var(--white);
  background: #1E293B;
  border-radius: 5px;
  padding: 3px 9px;
  white-space: nowrap;
  pointer-events: none;
  z-index: 5;
  box-shadow: 0 2px 6px rgba(0,0,0,0.2);
}

.gantt-bar-tooltip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-top-color: #1E293B;
}

.gantt-tick-row { position: relative; }
.gantt-tick { position: absolute; top: 2px; display: flex; flex-direction: column; align-items: center; }
.gantt-tick span { font-size: var(--font-hint); color: var(--text-muted); white-space: nowrap; }

.gantt-bar {
  position: absolute;
  top: 3px;
  height: 30px;
  z-index: 2;
  border-radius: var(--radius-sm);
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
}

.gantt-bar-activity { background: linear-gradient(90deg, #7C3AED 0%, #A78BFA 100%); }
.gantt-bar-task { background: #475569; }
.gantt-bar-mandatory { background: #EF4444; }
.gantt-bar-fixed { background: #F59E0B; }

.gantt-dep-row {
  position: absolute;
  top: 37px;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--font-hint);
  color: var(--text-muted);
  white-space: nowrap;
}
.gantt-dep-row svg { width: 10px; height: 10px; }

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