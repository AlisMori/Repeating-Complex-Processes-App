import './assets/main.css'

import { createApp } from 'vue'

import App from './App.vue'
import { configureApiAuth } from './api/axios'
import router from './router'
import { useAuthStore } from './stores/auth'
import pinia from './stores'

const app = createApp(App)

app.use(pinia)
app.use(router)

const authStore = useAuthStore(pinia)

configureApiAuth({
  getAccessToken: () => authStore.accessToken,
  isAccessTokenExpired: () => authStore.isAccessTokenExpired(),
  onUnauthorized: () => {
    authStore.handleSessionExpired()
    if (router.currentRoute.value.name !== 'login') {
      router.push({ name: 'login' })
    }
  },
})

app.mount('#app')
