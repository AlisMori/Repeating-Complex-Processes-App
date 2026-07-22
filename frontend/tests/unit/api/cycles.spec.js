import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import api from '@/api/axios'
import {
  getCycles, getCycle, shutdownCycle, exportCycle,
  getCycleTasks, updateCycleTask, setTaskNote, clearTaskNote,
  getCycleActivities,
} from '@/api/cycles'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('cycles API - request shape', () => {
  it('getCycles sends GET /cycles/ with requiresAuth', () => {
    getCycles({ status: 'running' })
    expect(api.get).toHaveBeenCalledWith('/cycles/', {
      params: { status: 'running' }, requiresAuth: true,
    })
  })

  it('getCycle sends GET /cycles/:id/ with requiresAuth', () => {
    getCycle(42)
    expect(api.get).toHaveBeenCalledWith('/cycles/42/', { requiresAuth: true })
  })

  it('shutdownCycle sends POST /cycles/:id/shut_down/ with requiresAuth', () => {
    shutdownCycle(42)
    expect(api.post).toHaveBeenCalledWith('/cycles/42/shut_down/', null, { requiresAuth: true })
  })

  it('exportCycle sends GET /cycles/:id/export/ with requiresAuth', () => {
    exportCycle(42)
    expect(api.get).toHaveBeenCalledWith('/cycles/42/export/', { requiresAuth: true })
  })

  it('getCycleTasks sends GET /cycle-tasks/ filtered by cycle', () => {
    getCycleTasks(42)
    expect(api.get).toHaveBeenCalledWith('/cycle-tasks/', {
      params: { cycle: 42 }, requiresAuth: true,
    })
  })

  it('updateCycleTask sends PATCH with just the status field', () => {
    updateCycleTask(7, 'completed')
    expect(api.patch).toHaveBeenCalledWith('/cycle-tasks/7/', { status: 'completed' }, { requiresAuth: true })
  })

  it('updateCycleTask includes resolve_prerequisites only when provided', () => {
    updateCycleTask(7, 'completed', [1, 2])
    expect(api.patch).toHaveBeenCalledWith(
      '/cycle-tasks/7/',
      { status: 'completed', resolve_prerequisites: [1, 2] },
      { requiresAuth: true },
    )
  })

  it('setTaskNote sends POST with note_text', () => {
    setTaskNote(7, 'Waiting on client')
    expect(api.post).toHaveBeenCalledWith('/cycle-tasks/7/note/', { note_text: 'Waiting on client' }, { requiresAuth: true })
  })

  it('clearTaskNote sends DELETE to the note endpoint', () => {
    clearTaskNote(7)
    expect(api.delete).toHaveBeenCalledWith('/cycle-tasks/7/note/', { requiresAuth: true })
  })

  it('getCycleActivities sends GET /cycle-activities/ filtered by cycle', () => {
    getCycleActivities(42)
    expect(api.get).toHaveBeenCalledWith('/cycle-activities/', {
      params: { cycle: 42 }, requiresAuth: true,
    })
  })

  it('every mutating call includes requiresAuth: true (session-expiry safety)', () => {
    updateCycleTask(1, 'pending')
    setTaskNote(1, 'x')
    shutdownCycle(1)
    for (const call of [...api.patch.mock.calls, ...api.post.mock.calls]) {
      const config = call[call.length - 1]
      expect(config.requiresAuth).toBe(true)
    }
  })
})
