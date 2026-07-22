import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// ── Mock vue-router: TemplateDetailView reads route.params.id ──
const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '5' } }),
  useRouter: () => ({ push: mockPush }),
}))

// ── Mock the toast store (avoids needing the real component tree) ──
const toastSuccess = vi.fn()
const toastError = vi.fn()
vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({ success: toastSuccess, error: toastError }),
}))

vi.mock('@/stores/onboarding', () => ({
  useOnboardingStore: () => ({ maybeAutoStart: vi.fn(), startTour: vi.fn() }),
}))

// ── Mock the whole templates API module — every function this
// screen calls, controllable per test ──
vi.mock('@/api/templates', () => ({
  getTemplate: vi.fn(),
  getTemplateTasks: vi.fn(),
  getTemplateActivities: vi.fn(),
  getTemplateTimelinePreview: vi.fn(),
  duplicateTemplate: vi.fn(),
  deleteTemplate: vi.fn(),
  downloadTemplate: vi.fn(),
  updateTemplate: vi.fn(),
  deleteTemplateTask: vi.fn(),
  deleteTemplateActivity: vi.fn(),
  setTemplateTaskNote: vi.fn(),
  clearTemplateTaskNote: vi.fn(),
  setTemplateActivityNote: vi.fn(),
  clearTemplateActivityNote: vi.fn(),
  getTaskDependencies: vi.fn(),
  getTags: vi.fn(),
  createTag: vi.fn(),
  getTaskTags: vi.fn(),
  assignTagToTask: vi.fn(),
  unassignTagFromTask: vi.fn(),
  getActivityTags: vi.fn(),
  assignTagToActivity: vi.fn(),
  unassignTagFromActivity: vi.fn(),
  getTemplateCategories: vi.fn(),
  createTemplateCategory: vi.fn(),
  getTemplateVersions: vi.fn(),
  makeCurrentVersion: vi.fn(),
}))

import TemplateDetailView from '@/views/TemplateDetailView.vue'
import * as templatesApi from '@/api/templates'

// Child components stubbed with real slot rendering (not vi.mock),
// so their content is still inspectable — this is standard Vue Test
// Utils practice for large parent components with heavy children
// that aren't the thing under test here.
const globalStubs = {
  AppLayout: { template: '<div><slot name="topbar" /><slot /></div>' },
  BaseButton: { template: '<button><slot /></button>' },
  BaseModal: { template: '<div class="stub-modal"><slot /><slot name="footer" /></div>', props: ['modelValue'] },
  BaseInput: { template: '<input />', props: ['modelValue'] },
  BaseSelect: { template: '<select><slot /></select>', props: ['modelValue'] },
  GanttChart: { template: '<div class="stub-gantt" />' },
}

function emptyTemplateResponses(overrides = {}) {
  return {
    tplData: { template_id: 5, template_name: 'Exam Prep', description: '', template_version: 1, is_current_version: true, ...overrides.template },
    tasksData: overrides.tasks ?? [],
    activitiesData: overrides.activities ?? [],
    depsData: [],
    timelineData: { task_bars: [], activity_bars: [], max_day: 1 },
    tagsData: [], taskTagsData: [], activityTagsData: [],
    categoriesData: [], versionsData: [{ template_id: 5, template_version: 1, is_current_version: true }],
  }
}

function mockAllSucceed(responses) {
  templatesApi.getTemplate.mockResolvedValue({ data: responses.tplData })
  templatesApi.getTemplateTasks.mockResolvedValue({ data: responses.tasksData })
  templatesApi.getTemplateActivities.mockResolvedValue({ data: responses.activitiesData })
  templatesApi.getTaskDependencies.mockResolvedValue({ data: responses.depsData })
  templatesApi.getTemplateTimelinePreview.mockResolvedValue({ data: responses.timelineData })
  templatesApi.getTags.mockResolvedValue({ data: responses.tagsData })
  templatesApi.getTaskTags.mockResolvedValue({ data: responses.taskTagsData })
  templatesApi.getActivityTags.mockResolvedValue({ data: responses.activityTagsData })
  templatesApi.getTemplateCategories.mockResolvedValue({ data: responses.categoriesData })
  templatesApi.getTemplateVersions.mockResolvedValue({ data: responses.versionsData })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('TemplateDetailView — request formation, rendering, loading/error states', () => {
  it('requests the template using the id from the current route', async () => {
    mockAllSucceed(emptyTemplateResponses())
    mount(TemplateDetailView, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(templatesApi.getTemplate).toHaveBeenCalledWith('5')
    expect(templatesApi.getTemplateTasks).toHaveBeenCalledWith('5')
    expect(templatesApi.getTemplateActivities).toHaveBeenCalledWith('5')
  })

  it('shows a loading state before the API calls resolve', () => {
    // Never-resolving promises - simulates a slow API call
    templatesApi.getTemplate.mockReturnValue(new Promise(() => {}))
    templatesApi.getTemplateTasks.mockReturnValue(new Promise(() => {}))
    templatesApi.getTemplateActivities.mockReturnValue(new Promise(() => {}))
    templatesApi.getTaskDependencies.mockReturnValue(new Promise(() => {}))
    templatesApi.getTemplateTimelinePreview.mockReturnValue(new Promise(() => {}))
    templatesApi.getTags.mockReturnValue(new Promise(() => {}))
    templatesApi.getTaskTags.mockReturnValue(new Promise(() => {}))
    templatesApi.getActivityTags.mockReturnValue(new Promise(() => {}))
    templatesApi.getTemplateCategories.mockReturnValue(new Promise(() => {}))
    templatesApi.getTemplateVersions.mockReturnValue(new Promise(() => {}))

    const wrapper = mount(TemplateDetailView, { global: { stubs: globalStubs } })

    expect(wrapper.find('.loading-msg').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Exam Prep')
  })

  it('renders the template name once the API calls succeed', async () => {
    mockAllSucceed(emptyTemplateResponses())
    const wrapper = mount(TemplateDetailView, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(wrapper.find('.loading-msg').exists()).toBe(false)
    expect(wrapper.text()).toContain('Exam Prep')
  })

  it('shows an error message if the template fails to load', async () => {
    templatesApi.getTemplate.mockRejectedValue(new Error('Network error'))
    templatesApi.getTemplateTasks.mockResolvedValue({ data: [] })
    templatesApi.getTemplateActivities.mockResolvedValue({ data: [] })
    templatesApi.getTaskDependencies.mockResolvedValue({ data: [] })
    templatesApi.getTemplateTimelinePreview.mockResolvedValue({ data: { task_bars: [], activity_bars: [], max_day: 1 } })
    templatesApi.getTags.mockResolvedValue({ data: [] })
    templatesApi.getTaskTags.mockResolvedValue({ data: [] })
    templatesApi.getActivityTags.mockResolvedValue({ data: [] })
    templatesApi.getTemplateCategories.mockResolvedValue({ data: [] })
    templatesApi.getTemplateVersions.mockResolvedValue({ data: [] })

    const wrapper = mount(TemplateDetailView, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(wrapper.find('.error-banner').exists()).toBe(true)
    expect(wrapper.find('.loading-msg').exists()).toBe(false)
  })
})

describe('TemplateDetailView — notes (task/activity)', () => {
  it('saving a note sends the trimmed text to the correct endpoint', async () => {
    const task = { template_task_id: 9, task_name: 'Submit form', note_text: '' }
    mockAllSucceed(emptyTemplateResponses({ tasks: [task] }))
    templatesApi.setTemplateTaskNote.mockResolvedValue({ data: {} })

    const wrapper = mount(TemplateDetailView, { global: { stubs: globalStubs } })
    await flushPromises()

    wrapper.vm.openNoteModal('task', task)
    wrapper.vm.noteModal.text = '  Check with client first  '
    await wrapper.vm.saveNote()

    expect(templatesApi.setTemplateTaskNote).toHaveBeenCalledWith(9, 'Check with client first')
  })

  it('saving an empty note clears it instead of setting blank text', async () => {
    const task = { template_task_id: 9, task_name: 'Submit form', note_text: 'old note' }
    mockAllSucceed(emptyTemplateResponses({ tasks: [task] }))
    templatesApi.clearTemplateTaskNote.mockResolvedValue({ data: {} })

    const wrapper = mount(TemplateDetailView, { global: { stubs: globalStubs } })
    await flushPromises()

    wrapper.vm.openNoteModal('task', task)
    wrapper.vm.noteModal.text = '   '
    await wrapper.vm.saveNote()

    expect(templatesApi.clearTemplateTaskNote).toHaveBeenCalledWith(9)
    expect(templatesApi.setTemplateTaskNote).not.toHaveBeenCalled()
  })

  it('shows a toast error if saving a note fails', async () => {
    const task = { template_task_id: 9, task_name: 'Submit form', note_text: '' }
    mockAllSucceed(emptyTemplateResponses({ tasks: [task] }))
    templatesApi.setTemplateTaskNote.mockRejectedValue({ response: { data: { detail: 'Server error' } } })

    const wrapper = mount(TemplateDetailView, { global: { stubs: globalStubs } })
    await flushPromises()

    wrapper.vm.openNoteModal('task', task)
    wrapper.vm.noteModal.text = 'a new note'
    await wrapper.vm.saveNote()

    expect(toastError).toHaveBeenCalledWith('Server error')
  })
})

describe('TemplateDetailView — export/download', () => {
  beforeEach(() => {
    window.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
    window.URL.revokeObjectURL = vi.fn()
    // The component creates a real <a href="blob:..."> and calls
    // .click() on it to trigger the browser's download — jsdom
    // isn't a real browser and tries (and fails) to actually
    // navigate to that href, which is harmless but noisy. Stubbing
    // click() avoids that without changing what's being tested here
    // (the API call and resulting toast/state, not the download
    // mechanism itself).
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })

  it('requests the download in the selected format', async () => {
    mockAllSucceed(emptyTemplateResponses())
    templatesApi.downloadTemplate.mockResolvedValue({ data: new Blob(['x']) })

    const wrapper = mount(TemplateDetailView, { global: { stubs: globalStubs } })
    await flushPromises()

    wrapper.vm.downloadModal.format = 'xlsx'
    await wrapper.vm.confirmDownload()

    expect(templatesApi.downloadTemplate).toHaveBeenCalledWith('5', 'xlsx')
  })

  it('shows a success toast and closes the modal after a successful download', async () => {
    mockAllSucceed(emptyTemplateResponses())
    templatesApi.downloadTemplate.mockResolvedValue({ data: new Blob(['x']) })

    const wrapper = mount(TemplateDetailView, { global: { stubs: globalStubs } })
    await flushPromises()
    wrapper.vm.downloadModal.open = true

    await wrapper.vm.confirmDownload()

    expect(toastSuccess).toHaveBeenCalledWith('Download started.')
    expect(wrapper.vm.downloadModal.open).toBe(false)
  })

  it('shows an error toast and keeps loading state correct if the download fails', async () => {
    mockAllSucceed(emptyTemplateResponses())
    templatesApi.downloadTemplate.mockRejectedValue({ response: { data: { detail: 'Export failed' } } })

    const wrapper = mount(TemplateDetailView, { global: { stubs: globalStubs } })
    await flushPromises()

    await wrapper.vm.confirmDownload()

    expect(toastError).toHaveBeenCalledWith('Export failed')
    expect(wrapper.vm.downloadLoading).toBe(false)
  })
})

// ═══════════════════════════════════════════════════════════
//   CYCLE / TASK SCREEN
// ═══════════════════════════════════════════════════════════

vi.mock('@/api/cycles', () => ({
  getCycle: vi.fn(), getCycleTasks: vi.fn(), getCycleActivities: vi.fn(),
  shutdownCycle: vi.fn(),
  updateCycleTask: vi.fn(), previewTaskShift: vi.fn(), applyTaskShift: vi.fn(),
  setTaskNote: vi.fn(), clearTaskNote: vi.fn(),
  updateCycleActivity: vi.fn(), setActivityNote: vi.fn(), clearActivityNote: vi.fn(),
}))

const { default: CycleDetailView } = await import('@/views/CycleDetailView.vue')
const cyclesApi = await import('@/api/cycles')

function mockCycleLoadSucceeds({ cycle, tasks = [], activities = [] } = {}) {
  cyclesApi.getCycle.mockResolvedValue({ data: cycle || { cycle_id: 5, cycle_name: 'Term 2', status: 'running' } })
  cyclesApi.getCycleTasks.mockResolvedValue({ data: tasks })
  cyclesApi.getCycleActivities.mockResolvedValue({ data: activities })
  templatesApi.getTaskDependencies.mockResolvedValue({ data: [] })
  templatesApi.getTags.mockResolvedValue({ data: [] })
  templatesApi.getTaskTags.mockResolvedValue({ data: [] })
  templatesApi.getActivityTags.mockResolvedValue({ data: [] })
}

describe('CycleDetailView — task status updates and validation error rendering', () => {
  it('a successful status update reloads the cycle and shows a success toast', async () => {
    mockCycleLoadSucceeds()
    cyclesApi.updateCycleTask.mockResolvedValue({ data: { cycle_just_completed: false } })

    const wrapper = mount(CycleDetailView, { global: { stubs: globalStubs } })
    await flushPromises()
    await wrapper.vm.updateTaskStatus(3, 'completed')

    expect(cyclesApi.updateCycleTask).toHaveBeenCalledWith(3, 'completed')
    expect(toastSuccess).toHaveBeenCalledWith('Task status updated.')
  })

  it('completing the last task shows the cycle-shut-down message instead of the generic one', async () => {
    mockCycleLoadSucceeds()
    cyclesApi.updateCycleTask.mockResolvedValue({ data: { cycle_just_completed: true } })

    const wrapper = mount(CycleDetailView, { global: { stubs: globalStubs } })
    await flushPromises()
    await wrapper.vm.updateTaskStatus(3, 'completed')

    expect(toastSuccess).toHaveBeenCalledWith('Last task of the cycle completed/skipped — cycle shut down.')
  })

  it('an unresolved-prerequisites error opens the resolution modal instead of a toast', async () => {
    mockCycleLoadSucceeds()
    cyclesApi.updateCycleTask.mockRejectedValue({
      response: {
        data: {
          code: 'prerequisites_unresolved',
          unresolved: [{ cycle_task_id: 1, task_name: 'Prepare chemicals' }],
        },
      },
    })

    const wrapper = mount(CycleDetailView, { global: { stubs: globalStubs } })
    await flushPromises()
    await wrapper.vm.updateTaskStatus(3, 'completed')

    expect(wrapper.vm.prereqModal.open).toBe(true)
    expect(wrapper.vm.prereqModal.unresolved).toEqual([{ cycle_task_id: 1, task_name: 'Prepare chemicals' }])
    expect(toastError).not.toHaveBeenCalled()
  })

  it('a cycle-frozen error shows the specific frozen-cycle message', async () => {
    mockCycleLoadSucceeds()
    cyclesApi.updateCycleTask.mockRejectedValue({
      response: { data: { code: 'cycle_not_running' } },
    })

    const wrapper = mount(CycleDetailView, { global: { stubs: globalStubs } })
    await flushPromises()
    await wrapper.vm.updateTaskStatus(3, 'completed')

    expect(toastError).toHaveBeenCalledWith('This cycle is completed or shut down, so its tasks can no longer be changed.')
  })

  it('a generic validation error shows the server-provided message', async () => {
    mockCycleLoadSucceeds()
    cyclesApi.updateCycleTask.mockRejectedValue({
      response: { data: { detail: 'Cannot skip a mandatory task without a reason.' } },
    })

    const wrapper = mount(CycleDetailView, { global: { stubs: globalStubs } })
    await flushPromises()
    await wrapper.vm.updateTaskStatus(3, 'skipped')

    expect(toastError).toHaveBeenCalledWith('Cannot skip a mandatory task without a reason.')
  })

  it('shows a loading state while the cycle is slow to load', () => {
    cyclesApi.getCycle.mockReturnValue(new Promise(() => {}))
    cyclesApi.getCycleTasks.mockReturnValue(new Promise(() => {}))
    cyclesApi.getCycleActivities.mockReturnValue(new Promise(() => {}))

    const wrapper = mount(CycleDetailView, { global: { stubs: globalStubs } })

    expect(wrapper.find('.loading-msg').exists()).toBe(true)
  })

  it('shows an error message if the cycle fails to load entirely', async () => {
    cyclesApi.getCycle.mockRejectedValue(new Error('Network error'))
    cyclesApi.getCycleTasks.mockResolvedValue({ data: [] })
    cyclesApi.getCycleActivities.mockResolvedValue({ data: [] })

    const wrapper = mount(CycleDetailView, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(wrapper.find('.error-banner').exists()).toBe(true)
  })
})
