import api from './axios'

export async function searchSmart(params) {
  const response = await api.get('/search/', {
    params,
    requiresAuth: true,
  })

  return response.data
}
