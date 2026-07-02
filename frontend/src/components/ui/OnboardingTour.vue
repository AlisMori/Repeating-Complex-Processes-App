<!-- ============================================
   RECURRA — ONBOARDING TOUR COMPONENT (v2)
   /frontend/src/components/ui/OnboardingTour.vue

   Generic tour engine — steps are supplied by the
   onboarding store depending on which tour is active
   (sidebar / dashboard / cycles / templates).
   Target elements must carry matching data-tour="KEY"
   attributes within the currently mounted view.
   ============================================ -->

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useOnboardingStore } from '@/stores/onboarding'

const store = useOnboardingStore()

const steps = computed(() => store.activeSteps)
const currentIndex = ref(0)
const currentStep = computed(() => steps.value[currentIndex.value] || null)
const isLastStep = computed(() => currentIndex.value === steps.value.length - 1)
const targetRect = ref(null)
const tooltipPos = ref({ top: 0, left: 0 })
const cardEl = ref(null)

const TOOLTIP_WIDTH = 280
const MARGIN = 16

function locateTarget() {
  if (!currentStep.value) return

  const el = document.querySelector(`[data-tour="${currentStep.value.key}"]`)
  if (!el) {
    targetRect.value = null
    return
  }

  el.scrollIntoView({ block: 'center', behavior: 'smooth' })

  // Wait a tick for scroll to settle before measuring
  requestAnimationFrame(() => {
    const rect = el.getBoundingClientRect()
    targetRect.value = rect
    positionTooltip(rect)
  })
}

function positionTooltip(rect) {
  const vw = window.innerWidth
  const vh = window.innerHeight
  const cardHeight = cardEl.value?.offsetHeight || 180

  let top, left

  const spaceRight = vw - rect.right
  const spaceLeft = rect.left
  const spaceBelow = vh - rect.bottom

  if (spaceRight > TOOLTIP_WIDTH + MARGIN * 2) {
    // place to the right
    left = rect.right + MARGIN
    top = rect.top
  } else if (spaceLeft > TOOLTIP_WIDTH + MARGIN * 2) {
    // place to the left
    left = rect.left - TOOLTIP_WIDTH - MARGIN
    top = rect.top
  } else if (spaceBelow > cardHeight + MARGIN * 2) {
    // place below
    left = rect.left
    top = rect.bottom + MARGIN
  } else {
    // place above
    left = rect.left
    top = rect.top - cardHeight - MARGIN
  }

  // Clamp horizontally within viewport
  left = Math.min(Math.max(left, MARGIN), vw - TOOLTIP_WIDTH - MARGIN)
  // Clamp vertically within viewport
  top = Math.min(Math.max(top, MARGIN), vh - cardHeight - MARGIN)

  tooltipPos.value = { top, left }
}

function next() {
  if (isLastStep.value) {
    finish()
    return
  }
  currentIndex.value++
}

function prev() {
  if (currentIndex.value > 0) currentIndex.value--
}

function skip() {
  finish()
}

function finish() {
  currentIndex.value = 0
  store.completeActiveTour()
}

function onResize() {
  if (targetRect.value) positionTooltip(targetRect.value)
}

watch(currentIndex, () => nextTick(locateTarget))
watch(() => store.tourActive, (active) => {
  if (active) {
    currentIndex.value = 0
    nextTick(locateTarget)
  }
})

onMounted(() => {
  if (store.tourActive) nextTick(locateTarget)
  window.addEventListener('resize', onResize)
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  document.removeEventListener('keydown', onKeydown)
})

function onKeydown(e) {
  if (!store.tourActive) return
  if (e.key === 'Escape') skip()
  if (e.key === 'ArrowRight') next()
  if (e.key === 'ArrowLeft') prev()
}
</script>

<template>
  <Teleport to="body">
    <div v-if="store.tourActive && currentStep" class="tour-overlay">

      <!-- Spotlight cutout -->
      <div
        v-if="targetRect"
        class="tour-spotlight"
        :style="{
          top: (targetRect.top - 6) + 'px',
          left: (targetRect.left - 6) + 'px',
          width: (targetRect.width + 12) + 'px',
          height: (targetRect.height + 12) + 'px',
        }"
      ></div>

      <!-- Tooltip card -->
      <Transition name="tour-fade" mode="out-in">
        <div
          ref="cardEl"
          :key="currentStep.key"
          class="tour-card"
          :style="{ top: tooltipPos.top + 'px', left: tooltipPos.left + 'px' }"
        >
          <div class="tour-progress">
            <div
              v-for="(s, i) in steps" :key="s.key"
              class="tour-dot"
              :class="{ 'tour-dot-active': i === currentIndex, 'tour-dot-done': i < currentIndex }"
            ></div>
          </div>

          <h3 class="tour-title">{{ currentStep.title }}</h3>
          <p class="tour-body">{{ currentStep.body }}</p>

          <div class="tour-footer">
            <span class="tour-step-count">{{ currentIndex + 1 }} of {{ steps.length }}</span>
            <div class="tour-actions">
              <button type="button" class="tour-btn-ghost" @click="skip">Skip</button>
              <button v-if="currentIndex > 0" type="button" class="tour-btn-ghost" @click="prev">Back</button>
              <button type="button" class="tour-btn-primary" @click="next">
                {{ isLastStep ? 'Finish' : 'Next' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>

    </div>
  </Teleport>
</template>

<style scoped>
.tour-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(15, 23, 42, 0.55);
  pointer-events: auto;
}

.tour-spotlight {
  position: fixed;
  border: 2px solid var(--violet, #7C3AED);
  border-radius: 10px;
  box-shadow: 0 0 0 4px rgba(124, 58, 237, 0.2), 0 0 0 9999px rgba(15, 23, 42, 0.55);
  background: transparent;
  pointer-events: none;
  transition: top 0.25s ease, left 0.25s ease, width 0.25s ease, height 0.25s ease;
}

.tour-card {
  position: fixed;
  width: 280px;
  max-width: calc(100vw - 32px);
  background: var(--white, #fff);
  border-radius: 12px;
  padding: 16px 18px;
  box-shadow: 0 12px 32px rgba(0,0,0,0.2), 0 4px 12px rgba(0,0,0,0.1);
  box-sizing: border-box;
}

.tour-progress {
  display: flex;
  gap: 5px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.tour-dot {
  width: 20px;
  height: 3px;
  border-radius: 2px;
  background: var(--border-light, #E2E8F0);
  transition: background 0.2s;
  flex-shrink: 0;
}

.tour-dot-active { background: var(--violet, #7C3AED); }
.tour-dot-done { background: #C4B5FD; }

.tour-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #1E293B);
  margin: 0 0 6px;
}

.tour-body {
  font-size: 12.5px;
  color: var(--text-secondary, #64748B);
  line-height: 1.55;
  margin: 0 0 14px;
}

.tour-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.tour-step-count {
  font-size: 11px;
  color: var(--text-muted, #94A3B8);
  flex-shrink: 0;
}

.tour-actions {
  display: flex;
  gap: 6px;
}

.tour-btn-ghost {
  background: none;
  border: none;
  font-size: 11.5px;
  color: var(--text-muted, #94A3B8);
  cursor: pointer;
  padding: 5px 8px;
  font-family: inherit;
}

.tour-btn-ghost:hover { color: var(--text-secondary, #64748B); }

.tour-btn-primary {
  background: var(--violet, #7C3AED);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 500;
  padding: 6px 14px;
  cursor: pointer;
  font-family: inherit;
}

.tour-btn-primary:hover { background: var(--violet-dark, #5B21B6); }

.tour-fade-enter-active, .tour-fade-leave-active { transition: opacity 0.15s ease; }
.tour-fade-enter-from, .tour-fade-leave-to { opacity: 0; }
</style>