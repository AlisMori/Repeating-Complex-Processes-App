// ============================================
//   RECURRA — CYCLES API
//   /frontend/src/api/cycles.js
//
//   Connects to:
//   GET        /api/cycles/                          — list all user cycles
//   GET        /api/cycles/:id/                      — single cycle
//   POST       /api/cycles/:id/shut_down/            — shut down a cycle
//   GET        /api/cycle-tasks/?cycle=:id           — tasks for a cycle
//   PATCH      /api/cycle-tasks/:id/                 — update task status
//   POST       /api/cycle-tasks/:id/record_delay/    — record a delay
//   POST       /api/cycle-tasks/:id/recalculate_dependencies/
//   GET        /api/cycle-activities/?cycle=:id      — activities for a cycle
//
//   NOTE: To CREATE a cycle use createCycleFromTemplate()
//   in templates.js — POST /api/templates/:id/create_cycle/
//   The backend generates all runtime tasks and activities automatically.
// ============================================

import api from './axios'

// ── CYCLE INSTANCES ───────────────────────────────────────

export function getCycles(params = {}) {
  return api.get('/cycles/', { params })
}

export function getCycle(id) {
  return api.get(`/cycles/${id}/`)
}

export function shutdownCycle(id) {
  return api.post(`/cycles/${id}/shut_down/`)
}

// ── CYCLE TASKS ───────────────────────────────────────────

export function getCycleTasks(cycleId) {
  return api.get('/cycle-tasks/', { params: { cycle: cycleId } })
}

export function updateCycleTask(id, data) {
  return api.patch(`/cycle-tasks/${id}/`, data)
}

export function recordDelay(taskId, delayDays) {
  return api.post(`/cycle-tasks/${taskId}/record_delay/`, { delay_days: delayDays })
}

export function recalculateDependencies(taskId) {
  return api.post(`/cycle-tasks/${taskId}/recalculate_dependencies/`)
}

// ── CYCLE ACTIVITIES ──────────────────────────────────────

export function getCycleActivities(cycleId) {
  return api.get('/cycle-activities/', { params: { cycle: cycleId } })
}