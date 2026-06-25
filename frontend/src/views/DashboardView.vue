<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchMe, logout } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { normalizeApiError } from '@/utils/forms'

const authStore = useAuthStore()
const router = useRouter()

const statusMessage = ref('Checking your account access...')
const errorMessage = ref('')
const loading = ref(true)
const logoutLoading = ref(false)

async function loadProfile() {
  loading.value = true
  errorMessage.value = ''

  try {
    const { data } = await fetchMe(authStore.accessToken)
    authStore.setSession({
      access: authStore.accessToken,
      refresh: authStore.refreshToken,
      user: data,
    })
    statusMessage.value = 'You are signed in and the protected account check succeeded.'
  } catch (error) {
    const normalized = normalizeApiError(error, {
      fallbackMessage: 'We could not verify your account right now.',
    })
    errorMessage.value = normalized.generalErrors[0] || 'We could not verify your account right now.'
  } finally {
    loading.value = false
  }
}

async function handleLogout() {
  if (logoutLoading.value) {
    return
  }

  logoutLoading.value = true
  const accessToken = authStore.accessToken
  const refreshToken = authStore.refreshToken

  try {
    if (accessToken && refreshToken) {
      await logout({ refresh: refreshToken }, accessToken)
    }
  } finally {
    authStore.clearSession()
    authStore.setAuthMessage('You have been logged out.')
    logoutLoading.value = false
    router.push({ name: 'login' })
  }
}

onMounted(() => {
  loadProfile()
})
</script>

<template>
  <section class="auth-page">
    <div class="card">
      <div class="card-header">
        <div>
          <h1>Dashboard</h1>
          <p>Minimal protected page for validating the backend authentication flow.</p>
        </div>
        <button :disabled="logoutLoading" type="button" @click="handleLogout">
          {{ logoutLoading ? 'Signing out...' : 'Logout' }}
        </button>
      </div>

      <div class="status-panel" :class="{ error: errorMessage }">
        <p v-if="loading">Checking your account access...</p>
        <p v-else-if="errorMessage">{{ errorMessage }}</p>
        <p v-else>{{ statusMessage }}</p>
      </div>

      <dl class="details-list">
        <div>
          <dt>Username</dt>
          <dd>{{ authStore.user?.username || 'Not available' }}</dd>
        </div>
        <div>
          <dt>Email</dt>
          <dd>{{ authStore.user?.email || 'Not available' }}</dd>
        </div>
      </dl>
    </div>
  </section>
</template>
