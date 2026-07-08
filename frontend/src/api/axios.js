import axios from 'axios'

let getAccessToken = () => ''
let isAccessTokenExpired = () => false
let onUnauthorized = () => {}

export function configureApiAuth(options) {
  getAccessToken = options.getAccessToken || getAccessToken
  isAccessTokenExpired = options.isAccessTokenExpired || isAccessTokenExpired
  onUnauthorized = options.onUnauthorized || onUnauthorized
}

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
  withCredentials: true,
})

api.interceptors.request.use((config) => {
  const accessToken = getAccessToken()

  if (accessToken && !isAccessTokenExpired()) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${accessToken}`
  } else if (config.requiresAuth) {
    // Only block the request if it explicitly requires auth
    onUnauthorized()
    const error = new Error('Your session has expired. Please log in again.')
    error.code = 'AUTH_SESSION_EXPIRED'
    return Promise.reject(error)
  }

  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401 && error?.config?.requiresAuth) {
      onUnauthorized()
    }

    return Promise.reject(error)
  },
)

export default api
