import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

import api from '@/api/axios'
import {
  getTemplates, createTemplate, updateTemplate,
  downloadTemplate, createCycleFromTemplate,
  createTemplateTask, updateTemplateTask, deleteTemplateTask,
  setTemplateTaskNote, clearTemplateTaskNote,
  makeCurrentVersion,
} from '@/api/templates'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('templates API - request shape', () => {
  it('getTemplates sends GET /templates/ with search and allVersions as query params', () => {
    getTemplates('exam', { allVersions: true })
    expect(api.get).toHaveBeenCalledWith('/templates/', {
      params: { search: 'exam', all_versions: 'true' },
    })
  })

  // FINDING: unlike nearly every other call in this file,
  // getTemplates does not pass requiresAuth: true. Documented here
  // as a real finding rather than silently worked around - worth a
  // one-line fix in the actual module, not this test file.
  it('FINDING: getTemplates does not pass requiresAuth (inconsistent with the rest of this file)', () => {
    getTemplates('exam')
    const [, config] = api.get.mock.calls[0]
    expect(config.requiresAuth).toBeUndefined()
  })

  it('createTemplate sends POST /templates/ with the given data', () => {
    createTemplate({ template_name: 'New Template' })
    expect(api.post).toHaveBeenCalledWith('/templates/', { template_name: 'New Template' }, { requiresAuth: true })
  })

  it('updateTemplate sends PUT (creates a new version), not PATCH', () => {
    updateTemplate(5, { description: 'Updated' })
    expect(api.put).toHaveBeenCalledWith('/templates/5/', { description: 'Updated' }, { requiresAuth: true })
  })

  it('downloadTemplate requests the correct format as a blob', () => {
    downloadTemplate(5, 'xlsx')
    expect(api.get).toHaveBeenCalledWith('/templates/5/download/', {
      params: { file_format: 'xlsx' },
      responseType: 'blob',
      requiresAuth: true,
    })
  })

  it('createCycleFromTemplate sends POST to the correct template-scoped endpoint', () => {
    createCycleFromTemplate(5, { cycle_name: 'Term 2', start_date: '2026-07-01' })
    expect(api.post).toHaveBeenCalledWith(
      '/templates/5/create_cycle/',
      { cycle_name: 'Term 2', start_date: '2026-07-01' },
      { requiresAuth: true },
    )
  })

  it('createTemplateTask sends POST /template-tasks/ with the task data', () => {
    createTemplateTask({ template: 5, task_name: 'Submit form', day_offset: 0 })
    expect(api.post).toHaveBeenCalledWith(
      '/template-tasks/',
      { template: 5, task_name: 'Submit form', day_offset: 0 },
      { requiresAuth: true },
    )
  })

  it('updateTemplateTask sends PATCH with the given fields', () => {
    updateTemplateTask(9, { task_name: 'Renamed' })
    expect(api.patch).toHaveBeenCalledWith('/template-tasks/9/', { task_name: 'Renamed' }, { requiresAuth: true })
  })

  it('deleteTemplateTask sends DELETE to the task endpoint', () => {
    deleteTemplateTask(9)
    expect(api.delete).toHaveBeenCalledWith('/template-tasks/9/', { requiresAuth: true })
  })

  it('setTemplateTaskNote sends POST with note_text', () => {
    setTemplateTaskNote(9, 'Check with client first')
    expect(api.post).toHaveBeenCalledWith('/template-tasks/9/note/', { note_text: 'Check with client first' }, { requiresAuth: true })
  })

  it('clearTemplateTaskNote sends DELETE to the note endpoint', () => {
    clearTemplateTaskNote(9)
    expect(api.delete).toHaveBeenCalledWith('/template-tasks/9/note/', { requiresAuth: true })
  })

  // This test documents a REAL inconsistency found while writing
  // these tests, not a requirement being verified: every other call
  // in this file passes requiresAuth: true, but makeCurrentVersion
  // does not. Left as a genuine finding rather than "fixed" here,
  // since it's a one-line change belonging with the rest of the API
  // module, not something to silently patch inside a test file.
  it('FINDING: makeCurrentVersion is missing requiresAuth (inconsistent with every other call in this file)', () => {
    makeCurrentVersion(5)
    const [, , config] = api.post.mock.calls[0]
    expect(config).toBeUndefined() // documents the current (likely unintended) state
  })
})
