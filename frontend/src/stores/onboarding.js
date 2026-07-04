// ============================================
//   RECURRA — ONBOARDING STORE (v2)
//   /frontend/src/stores/onboarding.js
//
//   Supports multiple independent tours, one per
//   screen, each tracked separately so a user who
//   has completed the Dashboard tour still sees the
//   Cycles tour the first time they visit that page.
// ============================================

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const STORAGE_PREFIX = 'recurra_tour_completed_'

const TOUR_DEFINITIONS = {
  sidebar: [
    { key: 'logo', title: 'Welcome to Recurra', body: "Let's take a quick look around. This will only take a minute." },
    { key: 'dashboard', title: 'Dashboard', body: 'Your home screen. See every running cycle, what\'s due today, and overdue tasks at a glance.' },
    { key: 'cycles', title: 'Cycles', body: 'A cycle is a running instance of a process — like this semester\'s teaching schedule. Open one to see its full timeline.' },
    { key: 'templates', title: 'Templates', body: 'Templates are reusable blueprints. Build one once, then start a new cycle from it any time you need to repeat the process.' },
    { key: 'user-menu', title: "You're all set", body: 'Find your account settings here, and you can replay any tour anytime from the Help button.' },
  ],
  dashboard: [
    { key: 'dash-stats', title: 'Your stats at a glance', body: 'These cards show running cycles, what\'s due today, overdue tasks, and what you\'ve completed this week.' },
    { key: 'dash-alert', title: 'Overdue alerts', body: 'If anything is overdue, it shows up here first so you never miss it.' },
    { key: 'dash-cycles', title: 'Running cycles', body: 'Each card is a live process. Click one to open its full timeline and update tasks.' },
    { key: 'dash-upcoming', title: 'Upcoming tasks', body: 'A quick list of what\'s coming up next across all your cycles.' },
  ],
  cycles: [
    { key: 'cycles-filter', title: 'Filter your cycles', body: 'Switch between all cycles, running ones, or ones you\'ve shut down.' },
    { key: 'cycles-new', title: 'Start a new cycle', body: 'Pick a template, give it a name and a start date — Recurra calculates the whole timeline for you.' },
    { key: 'cycles-card', title: 'Cycle cards', body: 'Each card shows progress, task counts, and dates. Click anywhere on a card to open it.' },
  ],
  templates: [
    { key: 'tpl-new', title: 'Create a template', body: 'A template is a reusable blueprint — build it once, then use it to start as many cycles as you need.' },
    { key: 'tpl-card', title: 'Template cards', body: 'Each card shows the task count, duration, and category. Duplicate, share, or use it to start a cycle.' },
    { key: 'tpl-shared', title: 'Shared with you', body: 'Templates other people have shared with you appear here — accept to get your own independent copy.' },
  ],
}

export const useOnboardingStore = defineStore('onboarding', () => {
  const tourActive = ref(false)
  const activeTourName = ref(null)

  const activeSteps = computed(() => TOUR_DEFINITIONS[activeTourName.value] || [])

  function hasCompleted(tourName) {
    return localStorage.getItem(STORAGE_PREFIX + tourName) === 'true'
  }

  function startTour(tourName) {
    if (!TOUR_DEFINITIONS[tourName]) return
    activeTourName.value = tourName
    tourActive.value = true
  }

  function completeActiveTour() {
    if (activeTourName.value) {
      localStorage.setItem(STORAGE_PREFIX + activeTourName.value, 'true')
    }
    tourActive.value = false
    activeTourName.value = null
  }

  // Called on mount of a screen — auto-starts that screen's tour
  // only the first time the user visits it.
  function maybeAutoStart(tourName) {
    if (!hasCompleted(tourName)) {
      startTour(tourName)
    }
  }

  return {
    tourActive,
    activeTourName,
    activeSteps,
    hasCompleted,
    startTour,
    completeActiveTour,
    maybeAutoStart,
  }
})