// ============================================
//   RECURRA — TEMPLATES API
//   /frontend/src/api/templates.js
//
//   Connects to:
//   GET/POST   /api/templates/
//   GET/PUT/DELETE /api/templates/:id/
//   POST       /api/templates/:id/create_cycle/
//   POST       /api/templates/:id/duplicate/
//   POST       /api/templates/:id/share/
//   GET        /api/templates/:id/versions/
//   GET        /api/templates/:id/export/
//   GET/POST   /api/template-tasks/
//   GET/PUT/DELETE /api/template-tasks/:id/
//   GET/POST   /api/template-activities/
//   GET/PUT/DELETE /api/template-activities/:id/
//   GET/POST   /api/tags/
// ============================================

import api from './axios'

// ── TEMPLATES ────────────────────────────────────────────

/**
 * Get all templates accessible to the current user.
 * @param {string} [search] - optional search query
 */
export function getTemplates(search = '', { allVersions = false } = {}) {
  const params = {}
  if (search) params.search = search
  if (allVersions) params.all_versions = 'true'
  return api.get('/templates/', { params })
}

/**
 * Get a single template by ID.
 * @param {number|string} id
 */
export function getTemplate(id) {
  return api.get(`/templates/${id}/`)
}

/**
 * Create a new template.
 * @param {{ template_name: string, description?: string, is_public?: boolean }} data
 */
export function createTemplate(data) {
  return api.post('/templates/', data)
}

/**
 * Update an existing template — this creates a new version in the backend.
 * @param {number|string} id
 * @param {{ template_name?: string, description?: string, is_public?: boolean }} data
 */
export function updateTemplate(id, data) {
  return api.put(`/templates/${id}/`, data)
}

/**
 * Delete a template.
 * @param {number|string} id
 */
export function deleteTemplate(id) {
  return api.delete(`/templates/${id}/`)
}

/**
 * Get all versions of a template.
 * @param {number|string} id
 */
export function getTemplateVersions(id) {
  return api.get(`/templates/${id}/versions/`)
}

/**
 * Duplicate a template — creates a full independent copy including tasks and activities.
 * @param {number|string} id
 */
export function duplicateTemplate(id) {
  return api.post(`/templates/${id}/duplicate/`)
}

/**
 * Share a template with another registered user by username.
 * Creates an independent copy in the recipient's account.
 * @param {number|string} id
 * @param {string} username - the recipient's username
 */
export function shareTemplate(id, username) {
  return api.post(`/templates/${id}/share/`, { username })
}

/**
 * Export a template with all its tasks and activities included.
 * @param {number|string} id
 */
export function exportTemplate(id) {
  return api.get(`/templates/${id}/export/`)
}

/**
 * Get the dependency-resolved timeline preview for a template —
 * every task/activity's effective start/end day once dependency
 * chains are accounted for. This matches exactly what a cycle
 * created from this template will actually look like.
 * @param {number|string} id
 */
export function getTemplateTimelinePreview(id) {
  return api.get(`/templates/${id}/timeline_preview/`)
}

/**
 * Create a cycle instance from a template.
 * The backend automatically generates all runtime tasks and activities.
 * @param {number|string} templateId
 * @param {{ cycle_name: string, start_date: string }} data - start_date format: YYYY-MM-DD
 */
export function createCycleFromTemplate(templateId, data) {
  return api.post(`/templates/${templateId}/create_cycle/`, data)
}

// ── TEMPLATE TASKS ────────────────────────────────────────

/**
 * Get all tasks for a specific template.
 * @param {number|string} templateId
 */
export function getTemplateTasks(templateId) {
  return api.get('/template-tasks/', { params: { template: templateId } })
}

/**
 * Mark this specific version as the current one for its template
 * family. Other versions still exist afterward — this only changes
 * which one is treated as current.
 * @param {number|string} id
 */
export function makeCurrentVersion(id) {
  return api.post(`/templates/${id}/make_current/`)
}


/**
 * Get a single template task by ID — used to show the original
 * template-authored details (e.g. description) for a running
 * cycle's task, since CycleTask itself doesn't carry that field.
 * @param {number|string} id
 */
export function getTemplateTaskDetail(id) {
  return api.get(`/template-tasks/${id}/`)
}

/**
 * Create a task within a template.
 * @param {{
 *   template: number,
 *   task_name: string,
 *   description?: string,
 *   day_offset: number,
 *   duration_days?: number,
 *   is_mandatory?: boolean,
 *   is_fixed_date?: boolean,
 *   reminder_lead_days?: number,
 *   note_text?: string
 * }} data
 */
export function createTemplateTask(data) {
  return api.post('/template-tasks/', data)
}

/**
 * Update a template task.
 * @param {number|string} id
 * @param {object} data
 */
export function updateTemplateTask(id, data) {
  return api.patch(`/template-tasks/${id}/`, data)
}

/**
 * Delete a template task.
 * @param {number|string} id
 */
export function deleteTemplateTask(id) {
  return api.delete(`/template-tasks/${id}/`)
}

// ── TEMPLATE ACTIVITIES ───────────────────────────────────

/**
 * Get all activities for a specific template.
 * @param {number|string} templateId
 */
export function getTemplateActivities(templateId) {
  return api.get('/template-activities/', { params: { template: templateId } })
}

/**
 * Create an activity within a template.
 * @param {{
 *   template: number,
 *   activity_name: string,
 *   description?: string,
 *   start_offset_days: number,
 *   end_offset_days: number,
 *   note_text?: string
 * }} data
 */
export function createTemplateActivity(data) {
  return api.post('/template-activities/', data)
}

/**
 * Update a template activity.
 * @param {number|string} id
 * @param {object} data
 */
export function updateTemplateActivity(id, data) {
  return api.patch(`/template-activities/${id}/`, data)
}

/**
 * Delete a template activity.
 * @param {number|string} id
 */
export function deleteTemplateActivity(id) {
  return api.delete(`/template-activities/${id}/`)
}

// ── TAGS ──────────────────────────────────────────────────

/**
 * Get all tags belonging to the current user.
 */
export function getTags(tagType = null) {
  return api.get('/tags/', { params: tagType ? { tag_type: tagType } : {} })
}

/**
 * Create a tag.
 * @param {{ tag_name: string }} data
 */
export function createTag(data) {
  return api.post('/tags/', data)
}

/**
 * Delete a tag.
 * @param {number|string} id
 */
export function deleteTag(id) {
  return api.delete(`/tags/${id}/`)
}

/**
 * Attach an existing tag to a template task.
 * @param {{ template_task: number, tag: number }} data
 */
export function createTemplateTaskTag(data) {
  return api.post('/template-task-tags/', data)
}

/**
 * Attach an existing tag to a template activity.
 * @param {{ template_activity: number, tag: number }} data
 */
export function createTemplateActivityTag(data) {
  return api.post('/template-activity-tags/', data)
}

/**
 * Get all task-tag links (used to show which tags are already
 * assigned to which tasks, e.g. when loading a template for editing).
 */
export function getTemplateTaskTags() {
  return api.get('/template-task-tags/')
}

/**
 * Get all activity-tag links.
 */
export function getTemplateActivityTags() {
  return api.get('/template-activity-tags/')
}