import './assets/main.css'

import { createApp } from 'vue'

import App from './App.vue'
import { configureApiAuth } from './api/axios'
import { reportActivity } from './api/auth'
import router from './router'
import { useAuthStore } from './stores/auth'
import pinia from './stores'
import { createActivityTracker } from './services/activityTracker'

const app = createApp(App)

app.use(pinia)
app.use(router)

const authStore = useAuthStore(pinia)

const activityTracker = createActivityTracker({
  reportActivity: async () => {
    const { data } = await reportActivity()
    return data
  },
  getIsAuthenticated: () => authStore.isAuthenticated,
  getInactivityExpiresAt: () => authStore.inactivityExpiresAt,
  onActivityRecorded: (data) => {
    authStore.setActivityWindow({
      lastActivityAt: data.last_activity_at || null,
      inactivityExpiresAt: data.inactivity_expires_at || null,
    })
  },
  onLocalActivity: () => {
    authStore.markLocalActivity()
  },
})

configureApiAuth({
  getAccessToken: () => authStore.accessToken,
  getRefreshToken: () => authStore.refreshToken,
  isAccessTokenExpired: () => authStore.isAccessTokenExpired(),
  saveSession: (session) => {
    authStore.setSession(session)
  },
  clearSession: (message) => {
    activityTracker.stop()
    authStore.handleSessionExpired(message)
    if (router.currentRoute.value.name !== 'login') {
      router.push({ name: 'login' })
    }
  },
})

if (authStore.isAuthenticated) {
  activityTracker.start(router)
}

authStore.$subscribe((_mutation, state) => {
  if (state.refreshToken && state.user) {
    activityTracker.start(router)
  } else {
    activityTracker.stop()
  }
})

app.mount('#app')
