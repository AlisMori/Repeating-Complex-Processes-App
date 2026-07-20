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

export function validatePasswordResetLink(uid, token) {
  return api.get(`/auth/password-reset/confirm/${encodeURIComponent(uid)}/${encodeURIComponent(token)}/`)
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

export function updateMe(payload) {
  return api.patch('/auth/me/', payload, { requiresAuth: true })
}

export function changePassword(payload) {
  return api.post('/auth/change-password/', payload, { requiresAuth: true })
}

export function deleteAccount(payload) {
  return api.post('/auth/delete-account/', payload, { requiresAuth: true })
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

export function searchUsers(query) {
  return api.get('/auth/users/search/', {
    params: { q: query },
    requiresAuth: true,
  })
}

export function getShareNotifications() {
  return api.get('/auth/share-notifications/', { requiresAuth: true })
}

export function markShareNotificationsRead(ids = []) {
  return api.post(
    '/auth/share-notifications/mark-read/',
    { ids },
    { requiresAuth: true },
  )
}
