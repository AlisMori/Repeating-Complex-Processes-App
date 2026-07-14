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

// ── TEMPLATES ────────────────────────────────────────────

/**
 * Get all templates accessible to the current user.
 * @param {string} [search] - optional search query
 */
export function getTemplates(search = '') {
  return api.get('/templates/', { params: search ? { search } : {}, requiresAuth: true })
}

/**
 * Get a single template by ID.
 * @param {number|string} id
 */
export function getTemplate(id) {
  return api.get(`/templates/${id}/`, { requiresAuth: true })
}

/**
 * Create a new template.
 * @param {{ template_name: string, description?: string, is_public?: boolean }} data
 */
export function createTemplate(data) {
  return api.post('/templates/', data, { requiresAuth: true })
}

/**
 * Update an existing template — this creates a new version in the backend.
 * @param {number|string} id
 * @param {{ template_name?: string, description?: string, is_public?: boolean }} data
 */
export function updateTemplate(id, data) {
  return api.put(`/templates/${id}/`, data, { requiresAuth: true })
}

/**
 * Delete a template.
 * @param {number|string} id
 */
export function deleteTemplate(id) {
  return api.delete(`/templates/${id}/`, { requiresAuth: true })
}

/**
 * Get all versions of a template.
 * @param {number|string} id
 */
export function getTemplateVersions(id) {
  return api.get(`/templates/${id}/versions/`, { requiresAuth: true })
}

/**
 * Duplicate a template — creates a full independent copy including tasks and activities.
 * @param {number|string} id
 */
export function duplicateTemplate(id) {
  return api.post(`/templates/${id}/duplicate/`, null, { requiresAuth: true })
}

/**
 * Share a template with another registered user by username.
 * Creates an independent copy in the recipient's account.
 * @param {number|string} id
 * @param {string} username - the recipient's username
 */
export function shareTemplate(id, username) {
  return api.post(`/templates/${id}/share/`, { username }, { requiresAuth: true })
}

/**
 * Export a template with all its tasks and activities included
 * (in-app JSON payload, same shape as GET, not a downloadable file).
 * @param {number|string} id
 */
export function exportTemplate(id) {
  return api.get(`/templates/${id}/export/`, { requiresAuth: true })
}

/**
 * Download a template as a real file (json, csv, or xlsx) for backup,
 * sharing outside the app, or reimporting later.
 * @param {number|string} id
 * @param {'json'|'csv'|'xlsx'} fileFormat
 */
export function downloadTemplate(id, fileFormat = 'json') {
  return api.get(`/templates/${id}/download/`, {
    params: { file_format: fileFormat },
    responseType: 'blob',
    requiresAuth: true,
  })
}

/**
 * Get the dependency-resolved timeline preview for a template —
 * every task/activity's effective start/end day once dependency
 * chains are accounted for. This matches exactly what a cycle
 * created from this template will actually look like.
 * @param {number|string} id
 */
export function getTemplateTimelinePreview(id) {
  return api.get(`/templates/${id}/timeline_preview/`, { requiresAuth: true })
}

/**
 * Replaces this template's entire tasks/activities/dependencies
 * structure in one atomic request — the backend validates everything
 * first and only writes if the whole payload is valid, creating
 * exactly one new template version. Replaces the old pattern of one
 * API call per task/activity/dependency, which forked a version per
 * field and was the root cause of the duplication bugs.
 * @param {number|string} templateId
 * @param {{
 *   activities: Array<{local_id, activity_name, description?, start_offset_days, end_offset_days, note_text?, tag_ids?}>,
 *   tasks: Array<{local_id, task_name, description?, day_offset, duration_days?, is_mandatory?, is_fixed_date?, reminder_lead_days?, note_text?, activity_local_id?, tag_ids?}>,
 *   dependencies: Array<{task_local_id, depends_on_local_id}>,
 * }} payload
 */
export function saveTemplateStructure(templateId, payload) {
  return api.post(`/templates/${templateId}/save_structure/`, payload, { requiresAuth: true })
}

/**
 * Create a cycle instance from a template.
 * The backend automatically generates all runtime tasks and activities.
 * @param {number|string} templateId
 * @param {{ cycle_name: string, start_date: string }} data - start_date format: YYYY-MM-DD
 */
export function createCycleFromTemplate(templateId, data) {
  return api.post(`/templates/${templateId}/create_cycle/`, data, { requiresAuth: true })
}

// ── TEMPLATE TASKS ────────────────────────────────────────

/**
 * Get all tasks for a specific template.
 * @param {number|string} templateId
 */
export function getTemplateTasks(templateId) {
  return api.get('/template-tasks/', { params: { template: templateId }, requiresAuth: true })
}

/**
 * Get a single template task by ID — used to show the original
 * template-authored details (e.g. description) for a running
 * cycle's task, since CycleTask itself doesn't carry that field.
 * @param {number|string} id
 */
export function getTemplateTaskDetail(id) {
  return api.get(`/template-tasks/${id}/`, { requiresAuth: true })
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
  return api.post('/template-tasks/', data, { requiresAuth: true })
}

/**
 * Update a template task.
 * @param {number|string} id
 * @param {object} data
 */
export function updateTemplateTask(id, data) {
  return api.patch(`/template-tasks/${id}/`, data, { requiresAuth: true })
}

/**
 * Delete a template task. This forks a new template version with the
 * task (and any dependency edges touching it) removed — the version
 * currently in use by any existing cycle is untouched.
 * @param {number|string} id
 */
export function deleteTemplateTask(id) {
  return api.delete(`/template-tasks/${id}/`, { requiresAuth: true })
}

export function setTemplateTaskNote(id, noteText) {
  return api.post(`/template-tasks/${id}/note/`, { note_text: noteText }, { requiresAuth: true })
}

export function clearTemplateTaskNote(id) {
  return api.delete(`/template-tasks/${id}/note/`, { requiresAuth: true })
}

// ── TEMPLATE ACTIVITIES ───────────────────────────────────

/**
 * Get all activities for a specific template.
 * @param {number|string} templateId
 */
export function getTemplateActivities(templateId) {
  return api.get('/template-activities/', { params: { template: templateId }, requiresAuth: true })
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
  return api.post('/template-activities/', data, { requiresAuth: true })
}

/**
 * Update a template activity.
 * @param {number|string} id
 * @param {object} data
 */
export function updateTemplateActivity(id, data) {
  return api.patch(`/template-activities/${id}/`, data, { requiresAuth: true })
}

/**
 * Delete a template activity. IMPORTANT: the backend deletes every
 * task still linked to this activity along with it — the caller
 * must confirm that with the user before calling this, the backend
 * does not ask first.
 * @param {number|string} id
 */
export function deleteTemplateActivity(id) {
  return api.delete(`/template-activities/${id}/`, { requiresAuth: true })
}

export function setTemplateActivityNote(id, noteText) {
  return api.post(`/template-activities/${id}/note/`, { note_text: noteText }, { requiresAuth: true })
}

export function clearTemplateActivityNote(id) {
  return api.delete(`/template-activities/${id}/note/`, { requiresAuth: true })
}

// ── TASK DEPENDENCIES ─────────────────────────────────────

/**
 * Get all dependency edges visible to the user. Filter client-side
 * by task id / template — there's no server-side template filter.
 */
export function getTaskDependencies() {
  return api.get('/task-dependencies/', { requiresAuth: true })
}

/**
 * Create a dependency edge. Forks a new template version. Validate
 * first with validateTaskDependency() so the user sees problems
 * before submitting rather than after.
 * @param {{ task: number, depends_on_task: number }} data
 */
export function createTaskDependency(data) {
  return api.post('/task-dependencies/', data, { requiresAuth: true })
}

export function updateTaskDependency(id, data) {
  return api.put(`/task-dependencies/${id}/`, data, { requiresAuth: true })
}

/**
 * Remove a dependency edge. Forks a new template version.
 * @param {number|string} id
 */
export function deleteTaskDependency(id) {
  return api.delete(`/task-dependencies/${id}/`, { requiresAuth: true })
}

/**
 * Dry run — checks a proposed task/depends_on_task pair for circular
 * chains, offset conflicts, and fan-out capacity without writing
 * anything. Returns { valid, issues: [{ error, message, ... }] }.
 */
export function validateTaskDependency(task, dependsOnTask, excludeDependencyId = null) {
  return api.post('/task-dependencies/validate/', {
    task,
    depends_on_task: dependsOnTask,
    exclude_dependency_id: excludeDependencyId,
  }, { requiresAuth: true })
}

/**
 * Every task in the same template that `taskId` could validly depend
 * on (excludes anything that would create a circular chain).
 */
export function getAllowedDependencyTargets(taskId) {
  return api.get('/task-dependencies/allowed_targets/', { params: { task: taskId }, requiresAuth: true })
}

// ── TAGS ──────────────────────────────────────────────────

/**
 * Get all tags belonging to the current user.
 */
export function getTags() {
  return api.get('/tags/', { requiresAuth: true })
}

/**
 * Create a tag.
 * @param {{ tag_name: string }} data
 */
export function createTag(data) {
  return api.post('/tags/', data, { requiresAuth: true })
}

/**
 * Delete a tag. This unassigns it from every task/activity it was
 * attached to (the assignment rows cascade-delete with it). Blocked
 * by the backend (400) if it's still assigned to anything.
 * @param {number|string} id
 */
export function deleteTag(id) {
  return api.delete(`/tags/${id}/`, { requiresAuth: true })
}

/**
 * "Editing" a tag does not rename it in place — the backend creates
 * a brand new tag with the new name and leaves the original (and
 * every task/activity already tagged with it) completely untouched.
 * Returns { message, tag: {...new tag...} }.
 * @param {number|string} id
 * @param {string} newName
 */
export function editTag(id, newName) {
  return api.put(`/tags/${id}/`, { tag_name: newName }, { requiresAuth: true })
}

// ── TEMPLATE CATEGORIES ────────────────────────────────────

/**
 * Get all template categories belonging to the current user.
 * Each includes template_count so the UI can show how many
 * templates use it before offering to delete.
 */
export function getTemplateCategories() {
  return api.get('/template-categories/', { requiresAuth: true })
}

/**
 * Create a category.
 * @param {{ category_name: string }} data
 */
export function createTemplateCategory(data) {
  return api.post('/template-categories/', data, { requiresAuth: true })
}

/**
 * Rename a category in place (unlike Tag, this does NOT create a new
 * row — every template pointing at it just sees the new name).
 * @param {number|string} id
 * @param {string} newName
 */
export function renameTemplateCategory(id, newName) {
  return api.put(`/template-categories/${id}/`, { category_name: newName }, { requiresAuth: true })
}

/**
 * Delete a category. Blocked by the backend (400) if any template —
 * including frozen old versions — still uses it.
 * @param {number|string} id
 */
export function deleteTemplateCategory(id) {
  return api.delete(`/template-categories/${id}/`, { requiresAuth: true })
}

// ── TASK / ACTIVITY TAG ASSIGNMENT ────────────────────────

export function getTaskTags() {
  return api.get('/template-task-tags/', { requiresAuth: true })
}

export function assignTagToTask(templateTaskId, tagId) {
  return api.post('/template-task-tags/', { template_task: templateTaskId, tag: tagId }, { requiresAuth: true })
}

export function unassignTagFromTask(taskTagId) {
  return api.delete(`/template-task-tags/${taskTagId}/`, { requiresAuth: true })
}

export function getActivityTags() {
  return api.get('/template-activity-tags/', { requiresAuth: true })
}

export function assignTagToActivity(templateActivityId, tagId) {
  return api.post('/template-activity-tags/', { template_activity: templateActivityId, tag: tagId }, { requiresAuth: true })
}

export function unassignTagFromActivity(activityTagId) {
  return api.delete(`/template-activity-tags/${activityTagId}/`, { requiresAuth: true })
}
