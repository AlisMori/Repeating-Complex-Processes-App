import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { logout as logoutRequest } from '@/api/auth'

const STORAGE_KEY = 'auth-test-session'
const SESSION_EXPIRED_MESSAGE = 'Your session has expired. Please log in again.'
const SESSION_INACTIVE_MESSAGE = 'Your session expired after 30 minutes of inactivity. Please log in again.'

function readStoredSession() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
    return {
      access: parsed?.access || '',
      refresh: parsed?.refresh || '',
      user: parsed?.user || null,
      lastActivityAt: parsed?.lastActivityAt || null,
      inactivityExpiresAt: parsed?.inactivityExpiresAt || null,
    }
  } catch {
    return {
      access: '',
      refresh: '',
      user: null,
      lastActivityAt: null,
      inactivityExpiresAt: null,
    }
  }
}

function decodeJwtPayload(token) {
  try {
    const payload = token.split('.')[1]
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
    return JSON.parse(atob(padded))
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const initialSession = readStoredSession()
  const accessToken = ref(initialSession.access)
  const refreshToken = ref(initialSession.refresh)
  const user = ref(initialSession.user)
  const authMessage = ref('')
  const lastActivityAt = ref(initialSession.lastActivityAt)
  const inactivityExpiresAt = ref(initialSession.inactivityExpiresAt)

  const isAuthenticated = computed(() => Boolean(user.value) && Boolean(refreshToken.value || accessToken.value))

  function persist() {
    if (!accessToken.value && !refreshToken.value && !user.value) {
      localStorage.removeItem(STORAGE_KEY)
      return
    }

    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        access: accessToken.value,
        refresh: refreshToken.value,
        user: user.value,
        lastActivityAt: lastActivityAt.value,
        inactivityExpiresAt: inactivityExpiresAt.value,
      }),
    )
  }

  function setSession(session) {
    accessToken.value = session.access || accessToken.value || ''
    refreshToken.value = session.refresh || refreshToken.value || ''
    user.value = session.user ?? user.value
    lastActivityAt.value = session.lastActivityAt ?? lastActivityAt.value
    inactivityExpiresAt.value = session.inactivityExpiresAt ?? inactivityExpiresAt.value
    authMessage.value = ''
    persist()
  }

  function clearSession() {
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    lastActivityAt.value = null
    inactivityExpiresAt.value = null
    persist()
  }

  function setAuthMessage(message) {
    authMessage.value = message
  }

  function clearAuthMessage() {
    authMessage.value = ''
  }

  function isAccessTokenExpired() {
    if (!accessToken.value) {
      return true
    }

    const payload = decodeJwtPayload(accessToken.value)
    if (!payload?.exp) {
      return true
    }

    return Date.now() >= payload.exp * 1000
  }

  function markLocalActivity() {
    lastActivityAt.value = new Date().toISOString()
    persist()
  }

  function setActivityWindow(payload = {}) {
    if (payload.lastActivityAt !== undefined) {
      lastActivityAt.value = payload.lastActivityAt
    }

    if (payload.inactivityExpiresAt !== undefined) {
      inactivityExpiresAt.value = payload.inactivityExpiresAt
    }

    persist()
  }

  function handleSessionExpired(message = SESSION_EXPIRED_MESSAGE) {
    clearSession()
    setAuthMessage(message)
  }

  async function logoutCurrentSession() {
    const currentRefreshToken = refreshToken.value
    const currentAccessToken = accessToken.value

    try {
      if (currentRefreshToken) {
        await logoutRequest({ refresh: currentRefreshToken }, currentAccessToken)
      }
    } catch {
      // Best-effort server logout; local cleanup still has to happen.
    } finally {
      clearSession()
    }
  }

  return {
    accessToken,
    refreshToken,
    user,
    authMessage,
    inactivityExpiresAt,
    isAuthenticated,
    clearAuthMessage,
    clearSession,
    handleSessionExpired,
    isAccessTokenExpired,
    lastActivityAt,
    logoutCurrentSession,
    markLocalActivity,
    setActivityWindow,
    setAuthMessage,
    setSession,
    SESSION_INACTIVE_MESSAGE,
  }
})
