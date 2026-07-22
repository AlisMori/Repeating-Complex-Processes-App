import { beforeEach, describe, expect, it, vi } from 'vitest'

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('@/api/axios', () => ({
  default: apiMock,
}))

import {
  assignTagToActivity,
  assignTagToTask,
  createTag,
  deleteTag,
  editTag,
  getActivityTags,
  getTags,
  getTaskTags,
  unassignTagFromActivity,
  unassignTagFromTask,
} from '@/api/templates'

describe('template tag API helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('requires auth for tag CRUD endpoints', () => {
    getTags()
    createTag({ tag_name: 'Important' })
    editTag(7, 'Urgent')
    deleteTag(7)

    expect(apiMock.get).toHaveBeenCalledWith('/tags/', { requiresAuth: true })
    expect(apiMock.post).toHaveBeenCalledWith(
      '/tags/',
      { tag_name: 'Important' },
      { requiresAuth: true },
    )
    expect(apiMock.put).toHaveBeenCalledWith(
      '/tags/7/',
      { tag_name: 'Urgent' },
      { requiresAuth: true },
    )
    expect(apiMock.delete).toHaveBeenCalledWith('/tags/7/', { requiresAuth: true })
  })

  it('requires auth for task and activity tag assignment endpoints', () => {
    getTaskTags()
    assignTagToTask(11, 12)
    unassignTagFromTask(13)
    getActivityTags()
    assignTagToActivity(21, 22)
    unassignTagFromActivity(23)

    expect(apiMock.get).toHaveBeenNthCalledWith(1, '/template-task-tags/', { requiresAuth: true })
    expect(apiMock.post).toHaveBeenNthCalledWith(
      1,
      '/template-task-tags/',
      { template_task: 11, tag: 12 },
      { requiresAuth: true },
    )
    expect(apiMock.delete).toHaveBeenNthCalledWith(1, '/template-task-tags/13/', { requiresAuth: true })
    expect(apiMock.get).toHaveBeenNthCalledWith(2, '/template-activity-tags/', { requiresAuth: true })
    expect(apiMock.post).toHaveBeenNthCalledWith(
      2,
      '/template-activity-tags/',
      { template_activity: 21, tag: 22 },
      { requiresAuth: true },
    )
    expect(apiMock.delete).toHaveBeenNthCalledWith(2, '/template-activity-tags/23/', { requiresAuth: true })
  })
})
