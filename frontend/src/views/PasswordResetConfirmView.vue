<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { confirmPasswordReset, validatePasswordResetLink } from '@/api/auth'
import { normalizeApiError } from '@/utils/forms'
import AuthLayout from '@/layouts/AuthLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'

const route = useRoute()
const router = useRouter()

const form = reactive({
  new_password: '',
  confirmPassword: '',
})

const fieldErrors = ref({})
const generalErrors = ref([])
const loading = ref(false)
const validating = ref(true)
const resetState = ref('validating')
const stateMessage = ref('Checking your reset link...')
let redirectTimer = null

const uid = computed(() => String(route.params.uid || ''))
const token = computed(() => String(route.params.token || ''))
const canSubmit = computed(() => resetState.value === 'valid')

async function validateLink() {
  if (!uid.value || !token.value) {
    resetState.value = 'invalid'
    stateMessage.value = 'This password reset link is invalid.'
    validating.value = false
    return
  }

  validating.value = true
  fieldErrors.value = {}
  generalErrors.value = []

  try {
    await validatePasswordResetLink(uid.value, token.value)
    resetState.value = 'valid'
    stateMessage.value = 'Choose a new password for your account.'
  } catch (error) {
    const code = error?.response?.data?.code
    if (code === 'expired_link') {
      resetState.value = 'expired'
      stateMessage.value = 'This password reset link has expired. Request a new one to continue.'
    } else {
      resetState.value = 'invalid'
      stateMessage.value = 'This password reset link is invalid.'
    }
  } finally {
    validating.value = false
  }
}

async function submit() {
  if (loading.value || !canSubmit.value) return

  fieldErrors.value = {}
  generalErrors.value = []

  if (form.new_password !== form.confirmPassword) {
    fieldErrors.value = { confirmPassword: ['Passwords do not match.'] }
    return
  }

  loading.value = true

  try {
    const { data } = await confirmPasswordReset({
      uid: uid.value,
      token: token.value,
      new_password: form.new_password,
    })
    resetState.value = 'success'
    stateMessage.value = data?.message || 'Password has been reset successfully.'
    form.new_password = ''
    form.confirmPassword = ''
    redirectTimer = window.setTimeout(() => {
      router.push({ name: 'login' })
    }, 1500)
  } catch (error) {
    const code = error?.response?.data?.code
    if (code === 'expired_link') {
      resetState.value = 'expired'
      stateMessage.value = 'This password reset link has expired. Request a new one to continue.'
    } else if (code === 'invalid_link') {
      resetState.value = 'invalid'
      stateMessage.value = 'This password reset link is invalid.'
    } else {
      const normalized = normalizeApiError(error, {
        fallbackMessage: 'We could not reset your password. Please try again.',
      })
      fieldErrors.value = normalized.fieldErrors
      generalErrors.value = normalized.generalErrors

      const tokenError = normalized.fieldErrors.token?.[0]
      if (tokenError === 'This reset link has expired.') {
        resetState.value = 'expired'
        stateMessage.value = 'This password reset link has expired. Request a new one to continue.'
      } else if (tokenError === 'Invalid reset link.' || normalized.fieldErrors.uid?.[0] === 'Invalid reset link.') {
        resetState.value = 'invalid'
        stateMessage.value = 'This password reset link is invalid.'
      }
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  validateLink()
})

onBeforeUnmount(() => {
  if (redirectTimer !== null) {
    window.clearTimeout(redirectTimer)
  }
})
</script>

<template>
  <AuthLayout>
    <template v-if="validating">
      <div class="icon-circle">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 6v6l4 2" />
        </svg>
      </div>

      <h2 class="form-title">Checking reset link</h2>
      <p class="form-subtitle">{{ stateMessage }}</p>
    </template>

    <template v-else-if="resetState === 'valid'">
      <div class="icon-circle">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
      </div>

      <h2 class="form-title">Reset your password</h2>
      <p class="form-subtitle">{{ stateMessage }}</p>

      <div v-if="generalErrors.length" class="error-banner" role="alert">
        <p v-for="message in generalErrors" :key="message">{{ message }}</p>
      </div>

      <form class="form" @submit.prevent="submit" novalidate>
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
    </template>

    <template v-else-if="resetState === 'success'">
      <div class="icon-circle icon-circle-success">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>

      <h2 class="form-title">Password reset</h2>
      <p class="form-subtitle">{{ stateMessage }}</p>

      <BaseButton variant="primary" full-width @click="router.push({ name: 'login' })">
        Continue to Sign in
      </BaseButton>
    </template>

    <template v-else>
      <div class="icon-circle icon-circle-danger">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M15 9l-6 6" />
          <path d="M9 9l6 6" />
        </svg>
      </div>

      <h2 class="form-title">
        {{ resetState === 'expired' ? 'Reset link expired' : 'Invalid reset link' }}
      </h2>
      <p class="form-subtitle">{{ stateMessage }}</p>

      <BaseButton variant="primary" full-width @click="router.push({ name: 'forgot-password' })">
        Request a new link
      </BaseButton>
    </template>

    <RouterLink to="/auth/login" class="back-link">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="19" y1="12" x2="5" y2="12" />
        <polyline points="12 19 5 12 12 5" />
      </svg>
      Back to Sign in
    </RouterLink>
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
.icon-circle-danger { background: var(--danger-bg); }
.icon-circle-danger svg { stroke: #B91C1C; }

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
