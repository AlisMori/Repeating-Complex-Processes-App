import api from './axios'

export function register(payload) {
  return api.post('/auth/register/', payload)
}

export function login(payload) {
  return api.post('/auth/login/', payload)
}

export function logout(payload, accessToken) {
  return api.post('/auth/logout/', payload, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
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
