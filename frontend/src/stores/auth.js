import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

const STORAGE_KEY = 'auth-test-session'
const SESSION_EXPIRED_MESSAGE = 'Your session has expired. Please log in again.'

function readStoredSession() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
    return {
      access: parsed?.access || '',
      refresh: parsed?.refresh || '',
      user: parsed?.user || null,
    }
  } catch {
    return {
      access: '',
      refresh: '',
      user: null,
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

  const isAuthenticated = computed(() => Boolean(accessToken.value) && !isAccessTokenExpired())

  function persist() {
    if (!accessToken.value && !refreshToken.value && !user.value) {
      localStorage.removeItem(STORAGE_KEY)
      return
    }

    // Temporary localStorage-based token persistence for auth flow testing only.
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        access: accessToken.value,
        refresh: refreshToken.value,
        user: user.value,
      }),
    )
  }

  function setSession(session) {
    accessToken.value = session.access || ''
    refreshToken.value = session.refresh || ''
    user.value = session.user || null
    authMessage.value = ''
    persist()
  }

  function clearSession() {
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
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

  function handleSessionExpired(message = SESSION_EXPIRED_MESSAGE) {
    clearSession()
    setAuthMessage(message)
  }

  return {
    accessToken,
    refreshToken,
    user,
    authMessage,
    isAuthenticated,
    setSession,
    clearSession,
    setAuthMessage,
    clearAuthMessage,
    isAccessTokenExpired,
    handleSessionExpired,
  }
})
