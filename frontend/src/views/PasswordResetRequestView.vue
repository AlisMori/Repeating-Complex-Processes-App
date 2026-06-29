<script setup>
import { reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { requestPasswordReset } from '@/api/auth'
import { normalizeApiError } from '@/utils/forms'

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
  <div class="auth-screen">

    <!-- LEFT PANEL -->
    <div class="left-panel">
      <div class="left-panel-inner">
        <div class="logo-area">
          <div class="logo-icon">
		<svg width="28" height="28" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M19.4631 18.5292C19.3849 16.1305 21.7053 13.6535 24.1562 15.1743C26.6071 16.6952 26.7637 21.4926 23.6437 23.9957C20.5237 26.4989 14.9006 25.882 12.3714 21.9624C9.84216 18.0428 11.2325 11.594 15.9517 9.03872C20.6708 6.4834 27.9453 8.64723 30.5267 14.166C33.1081 19.6847 30.9704 27.7587 24.6521 30.3662C18.3338 32.9737 10.2336 30.0364 7.60003 22.9186"
      stroke="white" stroke-width="3" stroke-linecap="round"/>
  		</svg>
          </div>
          <span class="logo-text">Recurra</span>
        </div>

        <div class="brand-content">
          <h1 class="brand-headline">Manage repeating<br/>processes with ease</h1>
          <p class="brand-tagline">Define once, repeat forever. Recurra tracks your complex workflows so you never miss a step.</p>
          <ul class="feature-list">
            <li class="feature-item"><span class="feature-dot"></span><span>Reusable process templates</span></li>
            <li class="feature-item"><span class="feature-dot"></span><span>Automatic timeline scheduling</span></li>
            <li class="feature-item"><span class="feature-dot"></span><span>Smart task dependency chains</span></li>
            <li class="feature-item"><span class="feature-dot"></span><span>Email reminders and notifications</span></li>
          </ul>
        </div>

        <div class="left-footer">
          <div class="status-badge">
            <span class="status-dot"></span>
            All systems operational
          </div>
          <p class="footer-note">Hosted on Murdoch University infrastructure</p>
        </div>
      </div>
    </div>

    <!-- RIGHT PANEL -->
    <div class="right-panel">
      <div class="form-card">

        <!-- STEP 1: Request form -->
        <template v-if="!submitted">
          <div class="icon-circle">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
          </div>

          <h2 class="form-title">Forgot your password?</h2>
          <p class="form-subtitle">Enter the email address associated with your account and we'll send you a reset link.</p>

          <div v-if="generalErrors.length" class="error-box" role="alert">
            <p v-for="message in generalErrors" :key="message">{{ message }}</p>
          </div>

          <form @submit.prevent="submit">
            <div class="form-group">
              <label class="form-label" for="reset-email">Email address</label>
              <div class="input-wrapper">
                <input
                  id="reset-email"
                  v-model="form.email"
                  class="recurra-input"
                  :class="{ error: fieldErrors.email?.length }"
                  type="email"
                  placeholder="you@example.com"
                  autocomplete="email"
                  required
                />
                <span class="input-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>
                  </svg>
                </span>
              </div>
              <p v-if="fieldErrors.email?.length" class="field-error">{{ fieldErrors.email[0] }}</p>
            </div>

            <button type="submit" class="recurra-btn-primary" :disabled="loading">
              {{ loading ? 'Sending...' : 'Send reset link' }}
            </button>
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
          <div class="icon-circle success">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>
            </svg>
          </div>

          <h2 class="form-title">Check your email</h2>
          <p class="form-subtitle">
            We sent a password reset link to
            <strong>{{ form.email }}</strong>.
            The link will expire in 30 minutes.
          </p>

          <div class="info-box">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <p>If you don't see the email, check your spam folder. The email comes from <strong>no-reply@recurra.murdoch.edu.au</strong></p>
          </div>

          <p class="resend-row">
            Didn't receive it?
            <button class="resend-btn" type="button" @click="submitted = false">Resend email</button>
          </p>

          <RouterLink to="/auth/login" class="back-link">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
            </svg>
            Back to Sign in
          </RouterLink>
        </template>

      </div>
    </div>

  </div>
</template>

<style scoped>
.auth-screen {
  display: flex;
  width: 100%;
  min-height: 100vh;
}

.left-panel {
  width: 420px;
  flex-shrink: 0;
  background: #F5F3FF;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.left-panel::before {
  content: '';
  position: absolute;
  width: 400px;
  height: 400px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(124,58,237,0.12) 0%, transparent 70%);
  bottom: -80px;
  left: -80px;
  pointer-events: none;
}

.left-panel::after {
  content: '';
  position: absolute;
  width: 250px;
  height: 250px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(124,58,237,0.08) 0%, transparent 70%);
  top: 60px;
  right: -60px;
  pointer-events: none;
}

.left-panel-inner {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
  padding: 48px 48px 40px;
}

.logo-area { display: flex; align-items: center; gap: 10px; }

.logo-icon {
  width: 38px;
  height: 38px;
  background: var(--violet);
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.logo-text {
  font-size: 19px;
  font-weight: 600;
  color: #4C1D95;
  letter-spacing: -0.3px;
}

.brand-content { margin-top: 56px; }

.brand-headline {
  font-size: 26px;
  font-weight: 600;
  color: #3B0764;
  line-height: 1.3;
  margin: 0 0 12px;
  letter-spacing: -0.4px;
}

.brand-tagline {
  font-size: 13.5px;
  color: #5B21B6;
  line-height: 1.7;
  opacity: 0.8;
  margin: 0;
}

.feature-list {
  list-style: none;
  margin: 32px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #5B21B6;
}

.feature-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--violet);
  flex-shrink: 0;
}

.left-footer { margin-top: auto; }

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: rgba(34,197,94,0.12);
  color: #15803D;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 11px;
  border-radius: 20px;
  margin-bottom: 8px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22C55E;
}

.footer-note {
  font-size: 11.5px;
  color: #5B21B6;
  opacity: 0.5;
  margin: 0;
}

.right-panel {
  flex: 1;
  background: #FFFFFF;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 40px;
}

.form-card {
  width: 100%;
  max-width: 380px;
}

.icon-circle {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--violet-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 22px;
}

.icon-circle svg {
  width: 26px;
  height: 26px;
  stroke: var(--violet);
}

.icon-circle.success {
  background: var(--success-bg);
}

.icon-circle.success svg {
  stroke: var(--success);
}

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

.error-box {
  background: var(--danger-bg);
  border: 1px solid #FECACA;
  border-radius: 8px;
  padding: 11px 14px;
  font-size: 13px;
  color: #B91C1C;
  margin-bottom: 16px;
}

.error-box p { margin: 0; }

.form-group { margin-bottom: 20px; }

.form-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.input-wrapper { position: relative; }

.input-icon {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;
}

.input-icon svg { width: 16px; height: 16px; display: block; }

.field-error {
  font-size: 12px;
  color: var(--danger);
  margin: 5px 0 0;
}

.info-box {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  background: var(--violet-bg);
  border: 1px solid #DDD6FE;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 20px;
}

.info-box svg {
  width: 16px;
  height: 16px;
  stroke: var(--violet);
  flex-shrink: 0;
  margin-top: 2px;
}

.info-box p {
  font-size: 13px;
  color: var(--violet-dark);
  line-height: 1.55;
  margin: 0;
}

.resend-row {
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 16px;
}

.resend-btn {
  background: none;
  border: none;
  color: var(--violet);
  font-weight: 500;
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  font-family: 'Inter', sans-serif;
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
}

.back-link svg {
  width: 14px;
  height: 14px;
  stroke: var(--text-secondary);
}

.back-link:hover { color: var(--violet); }
.back-link:hover svg { stroke: var(--violet); }

@media (max-width: 768px) {
  .auth-screen { flex-direction: column; }
  .left-panel { width: 100%; min-height: 260px; }
  .left-panel-inner { padding: 28px; }
  .brand-content { margin-top: 20px; }
  .feature-list { display: none; }
}
</style>
