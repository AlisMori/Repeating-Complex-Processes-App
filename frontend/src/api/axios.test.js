import test from 'node:test'
import assert from 'node:assert/strict'

import { createApiClient } from './axios.js'

function resolveResponse(config, status, data) {
  return Promise.resolve({
    config,
    data,
    headers: {},
    status,
    statusText: String(status),
  })
}

function rejectResponse(config, status, data) {
  const error = new Error(data?.detail || `HTTP ${status}`)
  error.config = config
  error.response = {
    config,
    data,
    headers: {},
    status,
    statusText: String(status),
  }
  return Promise.reject(error)
}

test('one expired access token triggers one refresh and retries requests', async () => {
  let refreshCalls = 0
  let protectedCalls = 0

  const session = {
    access: 'expired-access',
    refresh: 'refresh-1',
  }

  const transportAdapter = (config) => {
    if (config.url === '/things/') {
      protectedCalls += 1
      const authHeader = config.headers?.Authorization
      if (authHeader === 'Bearer fresh-access') {
        return resolveResponse(config, 200, { ok: true })
      }

      return rejectResponse(config, 401, { detail: 'Token expired.' })
    }

    return rejectResponse(config, 404, { detail: 'Unexpected request.' })
  }

  const refreshAdapter = (config) => {
    if (config.url === '/auth/token/refresh/') {
      refreshCalls += 1
      return resolveResponse(config, 200, {
        access: 'fresh-access',
        refresh: 'refresh-2',
      })
    }

    return rejectResponse(config, 404, { detail: 'Unexpected refresh request.' })
  }

  const client = createApiClient({ transportAdapter, refreshAdapter })
  client.configureAuth({
    getAccessToken: () => session.access,
    getRefreshToken: () => session.refresh,
    isAccessTokenExpired: () => true,
    saveSession: (payload) => {
      session.access = payload.access
      session.refresh = payload.refresh
    },
    clearSession: () => {
      throw new Error('session should not be cleared')
    },
  })

  const [first, second] = await Promise.all([
    client.api.get('/things/', { requiresAuth: true }),
    client.api.get('/things/', { requiresAuth: true }),
  ])

  assert.equal(first.status, 200)
  assert.equal(second.status, 200)
  assert.equal(refreshCalls, 1)
  assert.equal(protectedCalls, 4)
  assert.equal(session.access, 'fresh-access')
  assert.equal(session.refresh, 'refresh-2')
})

test('inactivity expiration clears auth state once and does not loop refresh attempts', async () => {
  let refreshCalls = 0
  const clearedMessages = []
  const session = {
    access: 'expired-access',
    refresh: 'refresh-1',
  }

  const transportAdapter = (config) => {
    if (config.url === '/things/') {
      return rejectResponse(config, 401, { detail: 'Token expired.' })
    }

    return rejectResponse(config, 404, { detail: 'Unexpected request.' })
  }

  const refreshAdapter = (config) => {
    if (config.url === '/auth/token/refresh/') {
      refreshCalls += 1
      return rejectResponse(config, 401, {
        code: 'session_inactive',
        detail: 'Your session expired after 30 minutes of inactivity. Please log in again.',
      })
    }

    return rejectResponse(config, 404, { detail: 'Unexpected refresh request.' })
  }

  const client = createApiClient({ transportAdapter, refreshAdapter })
  client.configureAuth({
    getAccessToken: () => session.access,
    getRefreshToken: () => session.refresh,
    isAccessTokenExpired: () => true,
    saveSession: () => {
      throw new Error('session should not be refreshed')
    },
    clearSession: (message) => {
      clearedMessages.push(message)
      session.access = ''
      session.refresh = ''
    },
  })

  await assert.rejects(
    client.api.get('/things/', { requiresAuth: true }),
    /30 minutes of inactivity/,
  )

  assert.equal(refreshCalls, 1)
  assert.deepEqual(clearedMessages, [
    'Your session expired after 30 minutes of inactivity. Please log in again.',
  ])
})
