// ============================================
//   RECURRA — CYCLES API
//   /frontend/src/api/cycles.js
//
//   Connects to:
//   GET        /api/cycles/                              — list all user cycles
//   GET        /api/cycles/:id/                           — single cycle
//   POST       /api/cycles/:id/shut_down/                 — shut down a cycle
//   POST       /api/cycles/:id/complete/                  — complete a fully resolved cycle
//   GET        /api/cycles/:id/export/                    — full export (cycle + tasks + activities)
//   GET        /api/cycle-tasks/?cycle=:id                — tasks for a cycle
//   PATCH      /api/cycle-tasks/:id/                      — update task status (only field allowed through)
//   GET        /api/cycle-tasks/:id/available_statuses/   — valid next statuses for this task
//   POST       /api/cycle-tasks/:id/shift_preview/        — dry-run a delay/date change, no writes
//   POST       /api/cycle-tasks/:id/shift/                — apply a delay/date change (scope: single|cascade)
//   POST/DELETE /api/cycle-tasks/:id/note/                 — add/update or clear a task note
//   GET        /api/cycle-activities/?cycle=:id           — activities for a cycle
//   PATCH      /api/cycle-activities/:id/                 — resize an activity (start/end date only)
//   POST/DELETE /api/cycle-activities/:id/note/            — add/update or clear an activity note
//
//   NOTE: To CREATE a cycle use createCycleFromTemplate()
//   in templates.js — POST /api/templates/:id/create_cycle/
//   The backend generates all runtime tasks and activities automatically.
//
//   A running cycle only ever allows: task status changes, task/
//   activity notes, and activity date/duration resizing. Everything
//   else (and all of the above once the cycle is completed or shut
//   down) is rejected by the backend with a 422 cycle_not_running —
//   see utils/apiErrors.js for surfacing that message.
//
//   Every call here passes requiresAuth: true so the axios
//   interceptor can catch an expired session BEFORE sending a
//   doomed request — without it, an expired token mid-session
//   silently sends the request with no Authorization header at all,
//   and the backend rejects it with a raw "Authentication
//   credentials were not provided," instead of the app cleanly
//   prompting to log back in.
// ============================================

import api from './axios'

// ── CYCLE INSTANCES ───────────────────────────────────────

export function getCycles(params = {}) {
  return api.get('/cycles/', { params, requiresAuth: true })
}

export function getCycle(id) {
  return api.get(`/cycles/${id}/`, { requiresAuth: true })
}

export function shutdownCycle(id) {
  return api.post(`/cycles/${id}/shut_down/`, null, { requiresAuth: true })
}

export function completeCycle(id) {
  return api.post(`/cycles/${id}/complete/`, null, { requiresAuth: true })
}

export function exportCycle(id) {
  return api.get(`/cycles/${id}/export/`, { requiresAuth: true })
}

// ── CYCLE TASKS ───────────────────────────────────────────

export function getCycleTasks(cycleId) {
  return api.get('/cycle-tasks/', { params: { cycle: cycleId }, requiresAuth: true })
}

export function updateCycleTask(id, status, resolvePrerequisites = null) {
  const payload = { status }
  if (resolvePrerequisites) payload.resolve_prerequisites = resolvePrerequisites
  return api.patch(`/cycle-tasks/${id}/`, payload, { requiresAuth: true })
}

export function getAvailableStatuses(taskId) {
  return api.get(`/cycle-tasks/${taskId}/available_statuses/`, { requiresAuth: true })
}

export function previewTaskShift(taskId, { delayDays, newStartDate, newEndDate } = {}) {
  return api.post(`/cycle-tasks/${taskId}/shift_preview/`, {
    delay_days: delayDays ?? null,
    new_start_date: newStartDate ?? null,
    new_end_date: newEndDate ?? null,
  }, { requiresAuth: true })
}

export function applyTaskShift(taskId, { delayDays, newStartDate, newEndDate, scope = 'single', overrideFixed = false } = {}) {
  return api.post(`/cycle-tasks/${taskId}/shift/`, {
    delay_days: delayDays ?? null,
    new_start_date: newStartDate ?? null,
    new_end_date: newEndDate ?? null,
    scope,
    override_fixed: overrideFixed,
  }, { requiresAuth: true })
}

export function setTaskNote(taskId, noteText) {
  return api.post(`/cycle-tasks/${taskId}/note/`, { note_text: noteText }, { requiresAuth: true })
}

export function clearTaskNote(taskId) {
  return api.delete(`/cycle-tasks/${taskId}/note/`, { requiresAuth: true })
}

export function updateTaskNotificationPreference(taskId, notificationOptIn) {
  return api.post(
    `/cycle-tasks/${taskId}/notification_preference/`,
    { notification_opt_in: notificationOptIn },
    { requiresAuth: true },
  )
}

// ── CYCLE ACTIVITIES ──────────────────────────────────────

export function getCycleActivities(cycleId) {
  return api.get('/cycle-activities/', { params: { cycle: cycleId }, requiresAuth: true })
}

export function updateCycleActivity(id, { calculatedStartDate, calculatedEndDate }) {
  const payload = {}
  if (calculatedStartDate) payload.calculated_start_date = calculatedStartDate
  if (calculatedEndDate) payload.calculated_end_date = calculatedEndDate
  return api.patch(`/cycle-activities/${id}/`, payload, { requiresAuth: true })
}

export function setActivityNote(activityId, noteText) {
  return api.post(`/cycle-activities/${activityId}/note/`, { note_text: noteText }, { requiresAuth: true })
}

export function clearActivityNote(activityId) {
  return api.delete(`/cycle-activities/${activityId}/note/`, { requiresAuth: true })
}
