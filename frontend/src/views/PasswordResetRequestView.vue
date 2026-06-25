<script setup>
import { reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { requestPasswordReset } from '@/api/auth'
import { normalizeApiError } from '@/utils/forms'

const form = reactive({
  email: '',
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

  try {
    const { data } = await requestPasswordReset(form)
    successMessage.value =
      data?.message || 'If an account exists for this email, a password reset link has been sent.'
  } catch (error) {
    const normalized = normalizeApiError(error, {
      fallbackMessage: 'We could not submit the password reset request.',
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
      <h1>Forgot Password</h1>
      <p>Enter your email address to request a password reset.</p>

      <div v-if="generalErrors.length" class="message error" role="alert">
        <p v-for="message in generalErrors" :key="message">{{ message }}</p>
      </div>

      <div v-if="successMessage" class="message success" role="status">
        <p>{{ successMessage }}</p>
      </div>

      <form class="form" @submit.prevent="submit">
        <label for="password-reset-email">Email</label>
        <input
          id="password-reset-email"
          v-model="form.email"
          autocomplete="email"
          required
          type="email"
        />
        <p v-if="fieldErrors.email?.length" class="field-error">{{ fieldErrors.email[0] }}</p>

        <button :disabled="loading" type="submit">
          {{ loading ? 'Sending reset link...' : 'Send reset link' }}
        </button>
      </form>

      <p class="form-footer">
        Back to
        <RouterLink to="/auth/login">login</RouterLink>
      </p>
    </div>
  </section>
</template>
