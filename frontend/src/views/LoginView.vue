<script setup>
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { login } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { normalizeApiError } from '@/utils/forms'

const authStore = useAuthStore()
const router = useRouter()

const form = reactive({
  username: '',
  password: '',
})

const fieldErrors = ref({})
const generalErrors = ref([])
const loading = ref(false)

async function submit() {
  if (loading.value) {
    return
  }

  loading.value = true
  fieldErrors.value = {}
  generalErrors.value = []

  try {
    const { data } = await login(form)
    authStore.setSession({
      access: data.access || '',
      refresh: data.refresh || '',
      user: data.user || null,
    })
    router.push({ name: 'dashboard' })
  } catch (error) {
    const normalized = normalizeApiError(error, {
      fallbackMessage: 'We could not sign you in. Please try again.',
    })
    fieldErrors.value = normalized.fieldErrors
    generalErrors.value = normalized.generalErrors
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="auth-page">
    <div class="card">
      <h1>Login</h1>
      <p>Sign in with the account you created in the backend test environment.</p>

      <div v-if="generalErrors.length" class="message error" role="alert">
        <p v-for="message in generalErrors" :key="message">{{ message }}</p>
      </div>

      <form class="form" @submit.prevent="submit">
        <label for="login-username">Username</label>
        <input id="login-username" v-model="form.username" autocomplete="username" required type="text" />
        <p v-if="fieldErrors.username?.length" class="field-error">{{ fieldErrors.username[0] }}</p>

        <label for="login-password">Password</label>
        <input
          id="login-password"
          v-model="form.password"
          autocomplete="current-password"
          required
          type="password"
        />
        <p v-if="fieldErrors.password?.length" class="field-error">{{ fieldErrors.password[0] }}</p>

        <button :disabled="loading" type="submit">
          {{ loading ? 'Signing in...' : 'Sign in' }}
        </button>
      </form>

      <p class="form-footer">
        Need an account?
        <RouterLink to="/auth/register">Create one</RouterLink>
      </p>
      <p class="form-footer">
        Forgot your password?
        <RouterLink to="/auth/password-reset">Reset it</RouterLink>
      </p>
    </div>
  </section>
</template>
