import axios from 'axios'

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000/api'
const INACTIVE_SESSION_MESSAGE = 'Your session expired after 30 minutes of inactivity. Please log in again.'
const GENERIC_SESSION_MESSAGE = 'Your session has expired. Please log in again.'

function getErrorMessage(error) {
  const code = error?.response?.data?.code
  const detail = error?.response?.data?.detail

  if (code === 'session_inactive') {
    return detail || INACTIVE_SESSION_MESSAGE
  }

  return detail || GENERIC_SESSION_MESSAGE
}

export function createApiClient({
  baseURL = DEFAULT_BASE_URL,
  withCredentials = true,
  transportAdapter,
  refreshAdapter,
} = {}) {
  const api = axios.create({
    baseURL,
    withCredentials,
    adapter: transportAdapter,
  })

  const refreshClient = axios.create({
    baseURL,
    withCredentials,
    adapter: refreshAdapter || transportAdapter,
  })

  let getAccessToken = () => ''
  let getRefreshToken = () => ''
  let saveSession = () => {}
  let clearSession = () => {}
  let isAccessTokenExpired = () => false

  let refreshPromise = null

  function configureAuth(options) {
    getAccessToken = options.getAccessToken || getAccessToken
    getRefreshToken = options.getRefreshToken || getRefreshToken
    saveSession = options.saveSession || saveSession
    clearSession = options.clearSession || clearSession
    isAccessTokenExpired = options.isAccessTokenExpired || isAccessTokenExpired
  }

  async function performRefresh() {
    const refreshToken = getRefreshToken()
    if (!refreshToken) {
      const error = new Error(GENERIC_SESSION_MESSAGE)
      error.code = 'AUTH_REFRESH_UNAVAILABLE'
      throw error
    }

    try {
      const { data } = await refreshClient.post(
        '/auth/token/refresh/',
        { refresh: refreshToken },
        {
          skipAuthRefresh: true,
          skipActivityTracking: true,
        },
      )

      saveSession({
        access: data.access || '',
        refresh: data.refresh || refreshToken,
        lastActivityAt: data.last_activity_at || null,
        inactivityExpiresAt: data.inactivity_expires_at || null,
      })

      return data
    } catch (error) {
      if (error?.response?.status === 401) {
        clearSession(getErrorMessage(error))
      }

      throw error
    }
  }

  async function refreshAuthSession() {
    if (!refreshPromise) {
      refreshPromise = performRefresh().finally(() => {
        refreshPromise = null
      })
    }

    return refreshPromise
  }

  async function ensureValidAccessToken() {
    const accessToken = getAccessToken()
    if (accessToken && !isAccessTokenExpired()) {
      return accessToken
    }

    const data = await refreshAuthSession()
    return data.access
  }

  api.interceptors.request.use((config) => {
    const accessToken = getAccessToken()
    if (accessToken) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${accessToken}`
    }

    return config
  })

  api.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error?.config

      if (
        !originalRequest
        || !originalRequest.requiresAuth
        || originalRequest.skipAuthRefresh
        || originalRequest._retry
        || error?.response?.status !== 401
      ) {
        return Promise.reject(error)
      }

      if (!getRefreshToken()) {
        clearSession(getErrorMessage(error))
        return Promise.reject(error)
      }

      originalRequest._retry = true

      try {
        await refreshAuthSession()
        originalRequest.headers = originalRequest.headers || {}
        originalRequest.headers.Authorization = `Bearer ${getAccessToken()}`
        return api(originalRequest)
      } catch (refreshError) {
        return Promise.reject(refreshError)
      }
    },
  )

  return {
    api,
    configureAuth,
    ensureValidAccessToken,
    refreshAuthSession,
  }
}

const defaultClient = createApiClient()

export const configureApiAuth = defaultClient.configureAuth
export const ensureValidAccessToken = defaultClient.ensureValidAccessToken
export const refreshAuthSession = defaultClient.refreshAuthSession

export default defaultClient.api
