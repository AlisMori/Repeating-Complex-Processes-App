<script setup>
import { reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { confirmPasswordReset } from '@/api/auth'
import { normalizeApiError } from '@/utils/forms'

const form = reactive({
  uid: '',
  token: '',
  new_password: '',
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

  if (form.new_password !== form.confirmPassword) {
    fieldErrors.value = {
      confirmPassword: ['Passwords do not match.'],
    }
    loading.value = false
    return
  }

  try {
    const { data } = await confirmPasswordReset({
      uid: form.uid,
      token: form.token,
      new_password: form.new_password,
    })
    successMessage.value = data?.message || 'Password has been reset successfully.'
    form.uid = ''
    form.token = ''
    form.new_password = ''
    form.confirmPassword = ''
  } catch (error) {
    const normalized = normalizeApiError(error, {
      fallbackMessage: 'We could not reset your password. Please check the link details.',
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
      <h1>Reset Password</h1>
      <p>Paste the reset UID and token from the backend email or log output, then choose a new password.</p>

      <div v-if="generalErrors.length" class="message error" role="alert">
        <p v-for="message in generalErrors" :key="message">{{ message }}</p>
      </div>

      <div v-if="successMessage" class="message success" role="status">
        <p>{{ successMessage }} <RouterLink to="/auth/login">Return to login</RouterLink></p>
      </div>

      <form class="form" @submit.prevent="submit">
        <label for="reset-uid">UID</label>
        <input id="reset-uid" v-model="form.uid" required type="text" />
        <p v-if="fieldErrors.uid?.length" class="field-error">{{ fieldErrors.uid[0] }}</p>

        <label for="reset-token">Token</label>
        <input id="reset-token" v-model="form.token" required type="text" />
        <p v-if="fieldErrors.token?.length" class="field-error">{{ fieldErrors.token[0] }}</p>

        <label for="reset-new-password">New Password</label>
        <input
          id="reset-new-password"
          v-model="form.new_password"
          autocomplete="new-password"
          required
          type="password"
        />
        <p v-if="fieldErrors.new_password?.length" class="field-error">
          {{ fieldErrors.new_password[0] }}
        </p>

        <label for="reset-confirm-password">Confirm New Password</label>
        <input
          id="reset-confirm-password"
          v-model="form.confirmPassword"
          autocomplete="new-password"
          required
          type="password"
        />
        <p v-if="fieldErrors.confirmPassword?.length" class="field-error">
          {{ fieldErrors.confirmPassword[0] }}
        </p>

        <button :disabled="loading" type="submit">
          {{ loading ? 'Resetting password...' : 'Reset password' }}
        </button>
      </form>
    </div>
  </section>
</template>
