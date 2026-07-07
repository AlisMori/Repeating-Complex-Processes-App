<!-- /frontend/src/views/auth/PasswordResetRequestView.vue -->

<script setup>
import { reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { requestPasswordReset } from '@/api/auth'
import { normalizeApiError } from '@/utils/forms'
import AuthLayout from '@/layouts/AuthLayout.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const form = reactive({ email: '' })
const fieldErrors = ref({})
const generalErrors = ref([])
const loading = ref(false)
const submitted = ref(false)

async function submit() {
  if (loading.value) return
  loading.value = true
  fieldErrors.value = {}
  generalErrors.value = []

  try {
    await requestPasswordReset(form)
    submitted.value = true
  } catch (error) {
    const normalized = normalizeApiError(error, {
      fallbackMessage: 'Something went wrong. Please try again.',
    })
    fieldErrors.value = normalized.fieldErrors
    generalErrors.value = normalized.generalErrors
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthLayout>

    <!-- STEP 1: Request -->
    <template v-if="!submitted">

      <div class="icon-circle">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
      </div>

      <h2 class="form-title">Forgot your password?</h2>
      <p class="form-subtitle">Enter your email and we'll send you a reset link.</p>

      <div v-if="generalErrors.length" class="error-banner" role="alert">
        <p v-for="msg in generalErrors" :key="msg">{{ msg }}</p>
      </div>

      <form @submit.prevent="submit" novalidate>
        <div class="field">
          <BaseInput
            v-model="form.email"
            label="Email address"
            type="email"
            placeholder="you@example.com"
            autocomplete="email"
            :error="fieldErrors.email?.[0]"
            required
          >
            <template #suffix>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>
              </svg>
            </template>
          </BaseInput>
        </div>

        <BaseButton type="submit" variant="primary" :loading="loading" full-width>
          Send reset link
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
          <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>
        </svg>
      </div>

      <h2 class="form-title">Check your email</h2>
      <p class="form-subtitle">
        We sent a reset link to <strong>{{ form.email }}</strong>. The link expires in 30 minutes.
      </p>

      <div class="info-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <p>If you don't see it, check your spam folder. Email comes from <strong>no-reply@recurra.murdoch.edu.au</strong></p>
      </div>

      <p class="resend-row">
        Didn't receive it?
        <button type="button" class="resend-btn" @click="submitted = false">Resend email</button>
      </p>

      <RouterLink to="/auth/login" class="back-link">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
        </svg>
        Back to Sign in
      </RouterLink>

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

.info-box {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  background: var(--violet-bg);
  border: 1px solid #DDD6FE;
  border-radius: var(--radius-md);
  padding: 12px 14px;
  margin-bottom: 18px;
}

.info-box svg { width: 15px; height: 15px; stroke: var(--violet); flex-shrink: 0; margin-top: 2px; }
.info-box p { font-size: 13px; color: var(--violet-dark); line-height: 1.55; margin: 0; }

.resend-row {
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 14px;
}

.resend-btn {
  background: none;
  border: none;
  color: var(--violet);
  font-weight: 500;
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  font-family: var(--font-main);
}

.resend-btn:hover { text-decoration: underline; }

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