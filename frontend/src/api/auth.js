import api from './axios'

export function register(payload) {
  return api.post('/auth/register/', payload)
}

export function login(payload) {
  return api.post('/auth/login/', payload)
}

export function logout(payload, accessToken) {
  return api.post('/auth/logout/', payload, {
    headers: accessToken
      ? {
          Authorization: `Bearer ${accessToken}`,
        }
      : undefined,
    requiresAuth: true,
    skipActivityTracking: true,
  })
}

export function requestPasswordReset(payload) {
  return api.post('/auth/password-reset/', payload)
}

export function confirmPasswordReset(payload) {
  return api.post('/auth/password-reset/confirm/', payload)
}

export function fetchMe(accessToken) {
  return api.get('/auth/me/', {
    headers: accessToken
      ? {
          Authorization: `Bearer ${accessToken}`,
        }
      : undefined,
    requiresAuth: true,
  })
}

export function reportActivity() {
  return api.post(
    '/auth/activity/',
    {},
    {
      requiresAuth: true,
      skipActivityTracking: true,
    },
  )
}
