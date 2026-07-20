import { beforeEach, describe, expect, it, vi } from 'vitest'

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

vi.mock('@/api/axios', () => ({
  default: apiMock,
}))

import {
  getShareNotifications,
  markShareNotificationsRead,
  searchUsers,
} from '@/api/auth'

describe('auth notification helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('searches users with auth and query params', () => {
    searchUsers('ali')

    expect(apiMock.get).toHaveBeenCalledWith('/auth/users/search/', {
      params: { q: 'ali' },
      requiresAuth: true,
    })
  })

  it('loads and marks share notifications with auth', () => {
    getShareNotifications()
    markShareNotificationsRead([1, 2])

    expect(apiMock.get).toHaveBeenCalledWith('/auth/share-notifications/', {
      requiresAuth: true,
    })
    expect(apiMock.post).toHaveBeenCalledWith(
      '/auth/share-notifications/mark-read/',
      { ids: [1, 2] },
      { requiresAuth: true },
    )
  })
})
