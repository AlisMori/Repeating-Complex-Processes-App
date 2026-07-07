<!-- /frontend/src/views/PasswordResetConfirmView.vue -->

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRoute, RouterLink, useRouter } from 'vue-router'
import { confirmPasswordReset } from '@/api/auth'
import { normalizeApiError } from '@/utils/forms'
import AuthLayout from '@/layouts/AuthLayout.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const route = useRoute()
const router = useRouter()

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

// If the reset link ever carries uid/token as query params
// (?uid=...&token=...), pre-fill them instead of asking the
// user to paste them in by hand.
onMounted(() => {
  if (route.query.uid) form.uid = String(route.query.uid)
  if (route.query.token) form.token = String(route.query.token)
})

async function submit() {
  if (loading.value) return

  loading.value = true
  fieldErrors.value = {}
  generalErrors.value = []
  successMessage.value = ''

  if (form.new_password !== form.confirmPassword) {
    fieldErrors.value = { confirmPassword: ['Passwords do not match.'] }
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
  <AuthLayout
    headline="Choose a new\npassword"
    tagline="Paste the reset details from your email, then set a new password for your account."
  >

    <!-- STEP 1: Reset form -->
    <template v-if="!successMessage">

      <div class="icon-circle">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
      </div>

      <h2 class="form-title">Reset your password</h2>
      <p class="form-subtitle">Paste the reset UID and token from the backend email or log output, then choose a new password.</p>

      <div v-if="generalErrors.length" class="error-banner" role="alert">
        <p v-for="message in generalErrors" :key="message">{{ message }}</p>
      </div>

      <form class="form" @submit.prevent="submit" novalidate>
        <div class="field">
          <BaseInput
            v-model="form.uid"
            label="UID"
            placeholder="From the reset email or log output"
            :error="fieldErrors.uid?.[0]"
            required
          />
        </div>

        <div class="field">
          <BaseInput
            v-model="form.token"
            label="Token"
            placeholder="From the reset email or log output"
            :error="fieldErrors.token?.[0]"
            required
          />
        </div>

        <div class="field">
          <BaseInput
            v-model="form.new_password"
            type="password"
            label="New password"
            autocomplete="new-password"
            :error="fieldErrors.new_password?.[0]"
            required
          />
        </div>

        <div class="field">
          <BaseInput
            v-model="form.confirmPassword"
            type="password"
            label="Confirm new password"
            autocomplete="new-password"
            :error="fieldErrors.confirmPassword?.[0]"
            required
          />
        </div>

        <BaseButton type="submit" variant="primary" :loading="loading" full-width>
          Reset password
        </BaseButton>
      </form>

      <RouterLink to="/auth/login" class="back-link">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
        </svg>
        Back to Sign in
      </RouterLink>

    </template>

    <!-- STEP 2: Confirmation -->
    <template v-else>

      <div class="icon-circle icon-circle-success">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
      </div>

      <h2 class="form-title">Password reset</h2>
      <p class="form-subtitle">{{ successMessage }}</p>

      <BaseButton variant="primary" full-width @click="router.push({ name: 'login' })">
        Continue to Sign in
      </BaseButton>

    </template>

  </AuthLayout>
</template>

<style scoped>
form { width: 100%; }
.icon-circle {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background: var(--violet-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.icon-circle svg { width: 24px; height: 24px; stroke: var(--violet); }
.icon-circle-success { background: var(--success-bg); }
.icon-circle-success svg { stroke: var(--success); }

.form-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.3px;
  margin: 0 0 6px;
}

.form-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 24px;
}

.error-banner {
  background: var(--danger-bg);
  border: 1px solid #FECACA;
  border-radius: var(--radius-md);
  padding: 11px 14px;
  font-size: 13px;
  color: #B91C1C;
  margin-bottom: 16px;
}
.error-banner p { margin: 0; }

.field { margin-bottom: 20px; }

.back-link {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  text-decoration: none;
  margin-top: 16px;
  width: fit-content;
  transition: color var(--transition-fast);
}

.back-link svg { width: 14px; height: 14px; }
.back-link:hover { color: var(--violet); text-decoration: none; }
</style>
