// ============================================
//   RECURRA — API ERROR MESSAGE HELPER
//   /frontend/src/utils/apiErrors.js
//
//   Every backend rejection has a specific, human-readable reason
//   (frozen cycle, unresolved prerequisites, dependency conflict,
//   field validation, permission denied). This turns whatever shape
//   DRF/the domain layer sent back into one clear sentence, so every
//   view can show the *real* reason an action was blocked instead of
//   a generic "failed, try again".
// ============================================

// Recognised structured error shapes, checked in order.
function extractStructured(data) {
  if (!data || typeof data !== 'object') return null

  // CycleFrozen (422) — { detail: "..." }
  if (typeof data.detail === 'string' && !data.error) return data.detail

  // PrerequisitesUnresolved (409)
  if (data.error === 'prerequisites_unresolved') return data.message

  // DependencyConflict.as_response_payload() (409, from /shift/)
  if (data.error && data.message) return data.message

  // ValidationError({"depends_on_task": [violations]}) from
  // TaskDependencyViewSet.create/update, and /validate/'s {issues: [...]}
  const violationList = data.depends_on_task || data.issues
  if (Array.isArray(violationList) && violationList.length) {
    const first = violationList[0]
    if (typeof first === 'string') return first
    if (first && first.message) return first.message
  }

  return null
}

// Plain DRF ValidationError: {"field_name": ["message", ...], ...}
function extractFieldErrors(data) {
  if (!data || typeof data !== 'object') return null
  for (const key of Object.keys(data)) {
    const val = data[key]
    if (Array.isArray(val) && val.length && typeof val[0] === 'string') {
      const label = key === 'non_field_errors' ? '' : `${fieldLabel(key)}: `
      return `${label}${val[0]}`
    }
  }
  return null
}

function fieldLabel(key) {
  return key
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

/**
 * Returns the best available human-readable message for an axios/API
 * error. Falls back to `fallback` only if nothing usable came back
 * from the server (e.g. a network failure).
 */
export function getErrorMessage(err, fallback = 'Something went wrong. Please try again.') {
  const data = err?.response?.data
  if (!data) return err?.message || fallback

  return (
    extractStructured(data) ||
    extractFieldErrors(data) ||
    fallback
  )
}

/** True when the backend rejected this because the parent cycle is completed/shut down. */
export function isCycleFrozenError(err) {
  return err?.response?.status === 422 && err?.response?.data?.error === 'cycle_not_running'
}

/** True when a task completion was blocked by unresolved prerequisite tasks. */
export function isPrerequisitesUnresolvedError(err) {
  return err?.response?.status === 409 && err?.response?.data?.error === 'prerequisites_unresolved'
}

/** True when a task shift was blocked by a dependency/fixed-date conflict. */
export function isDependencyConflictError(err) {
  return err?.response?.status === 409 && !!err?.response?.data?.error && !isPrerequisitesUnresolvedError(err)
}

/** True when the backend rejected this purely on permissions (403). */
export function isPermissionError(err) {
  return err?.response?.status === 403
}

export function getUnresolvedPrerequisites(err) {
  return err?.response?.data?.unresolved_prerequisites || []
}
