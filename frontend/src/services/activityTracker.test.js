import test from 'node:test'
import assert from 'node:assert/strict'

import { createActivityTracker } from './activityTracker.js'

class FakeEventTarget {
  constructor() {
    this.listeners = new Map()
  }

  addEventListener(eventName, listener) {
    if (!this.listeners.has(eventName)) {
      this.listeners.set(eventName, new Set())
    }

    this.listeners.get(eventName).add(listener)
  }

  removeEventListener(eventName, listener) {
    this.listeners.get(eventName)?.delete(listener)
  }

  dispatchEvent(eventName, event = {}) {
    for (const listener of this.listeners.get(eventName) || []) {
      listener(event)
    }
  }
}

test('meaningful user activity is detected and reported', async () => {
  const fakeDocument = new FakeEventTarget()
  const reports = []
  const localEvents = []

  const tracker = createActivityTracker({
    reportActivity: async () => {
      reports.push('reported')
      return { inactivity_expires_at: '2026-01-01T00:10:00Z' }
    },
    getIsAuthenticated: () => true,
    getInactivityExpiresAt: () => null,
    onLocalActivity: (source) => {
      localEvents.push(source)
    },
    throttleMs: 0,
    documentRef: fakeDocument,
    now: () => 1_000,
  })

  await tracker.recordActivity('pointerdown')

  assert.deepEqual(localEvents, ['pointerdown'])
  assert.equal(reports.length, 1)
})

test('activity requests are throttled', async () => {
  const reports = []
  let currentTime = 1_000_000

  const tracker = createActivityTracker({
    reportActivity: async () => {
      reports.push(currentTime)
      return {}
    },
    getIsAuthenticated: () => true,
    getInactivityExpiresAt: () => null,
    throttleMs: 120_000,
    now: () => currentTime,
  })

  await tracker.recordActivity('pointerdown')

  currentTime += 60_000
  await tracker.recordActivity('pointerdown')

  assert.equal(reports.length, 1)
})

test('automatic polling alone does not report activity', () => {
  const tracker = createActivityTracker({
    reportActivity: async () => {
      throw new Error('should not be called')
    },
    getIsAuthenticated: () => true,
    getInactivityExpiresAt: () => null,
    documentRef: new FakeEventTarget(),
  })

  tracker.start()
  assert.ok(tracker)
})

test('logout removes activity listeners', async () => {
  const fakeDocument = new FakeEventTarget()
  let reportCount = 0

  const tracker = createActivityTracker({
    reportActivity: async () => {
      reportCount += 1
      return {}
    },
    getIsAuthenticated: () => true,
    getInactivityExpiresAt: () => null,
    throttleMs: 0,
    documentRef: fakeDocument,
    now: () => 1_000,
  })

  tracker.start()
  tracker.stop()
  fakeDocument.dispatchEvent('pointerdown')
  await Promise.resolve()

  assert.equal(reportCount, 0)
})
