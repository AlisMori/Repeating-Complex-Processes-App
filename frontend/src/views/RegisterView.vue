<script setup>
import { reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { register } from '@/api/auth'
import { normalizeApiError } from '@/utils/forms'

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})

const fieldErrors = ref({})
const generalErrors = ref([])
const successMessage = ref('')
const loading = ref(false)

async function submit() {
  if (loading.value) {
    return
  }

  loading.value = true
  fieldErrors.value = {}
  generalErrors.value = []
  successMessage.value = ''

  if (form.password !== form.confirmPassword) {
    fieldErrors.value = {
      confirmPassword: ['Passwords do not match.'],
    }
    loading.value = false
    return
  }

  try {
    await register({
      username: form.username,
      email: form.email,
      password: form.password,
    })
    successMessage.value = 'Account created successfully. You can now sign in.'
    form.username = ''
    form.email = ''
    form.password = ''
    form.confirmPassword = ''
  } catch (error) {
    const normalized = normalizeApiError(error, {
      fallbackMessage: 'We could not create your account. Please review the form and try again.',
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
      <h1>Create Account</h1>
      <p>Register a test user so the JWT login and protected dashboard flow can be verified.</p>

      <div v-if="generalErrors.length" class="message error" role="alert">
        <p v-for="message in generalErrors" :key="message">{{ message }}</p>
      </div>

      <div v-if="successMessage" class="message success" role="status">
        <p>{{ successMessage }}</p>
      </div>

      <form class="form" @submit.prevent="submit">
        <label for="register-username">Username</label>
        <input
          id="register-username"
          v-model="form.username"
          autocomplete="username"
          required
          type="text"
        />
        <p v-if="fieldErrors.username?.length" class="field-error">{{ fieldErrors.username[0] }}</p>

        <label for="register-email">Email</label>
        <input id="register-email" v-model="form.email" autocomplete="email" required type="email" />
        <p v-if="fieldErrors.email?.length" class="field-error">{{ fieldErrors.email[0] }}</p>

        <label for="register-password">Password</label>
        <input
          id="register-password"
          v-model="form.password"
          autocomplete="new-password"
          required
          type="password"
        />
        <p v-if="fieldErrors.password?.length" class="field-error">{{ fieldErrors.password[0] }}</p>

        <label for="register-confirm-password">Confirm Password</label>
        <input
          id="register-confirm-password"
          v-model="form.confirmPassword"
          autocomplete="new-password"
          required
          type="password"
        />
        <p v-if="fieldErrors.confirmPassword?.length" class="field-error">
          {{ fieldErrors.confirmPassword[0] }}
        </p>

        <button :disabled="loading" type="submit">
          {{ loading ? 'Creating account...' : 'Create account' }}
        </button>
      </form>

      <p class="form-footer">
        Already registered?
        <RouterLink to="/auth/login">Back to login</RouterLink>
      </p>
    </div>
  </section>
</template>
