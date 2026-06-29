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

const showPassword = ref(false)
const fieldErrors = ref({})
const generalErrors = ref([])
const loading = ref(false)

async function submit() {
  if (loading.value) return
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
  <div class="auth-screen">

    <!-- LEFT PANEL -->
    <div class="left-panel">
      <div class="left-panel-inner">

        <!-- Logo -->
        <div class="logo-area">
          <div class="logo-icon">
  		<svg width="28" height="28" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M19.4631 18.5292C19.3849 16.1305 21.7053 13.6535 24.1562 15.1743C26.6071 16.6952 26.7637 21.4926 23.6437 23.9957C20.5237 26.4989 14.9006 25.882 12.3714 21.9624C9.84216 18.0428 11.2325 11.594 15.9517 9.03872C20.6708 6.4834 27.9453 8.64723 30.5267 14.166C33.1081 19.6847 30.9704 27.7587 24.6521 30.3662C18.3338 32.9737 10.2336 30.0364 7.60003 22.9186"
      stroke="white" stroke-width="3" stroke-linecap="round"/>
  		</svg>
          </div>
          <span class="logo-text">Recurra</span>
        </div>

        <!-- Brand content -->
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

        <!-- Footer -->
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

        <h2 class="form-title">Welcome back</h2>
        <p class="form-subtitle">Sign in to your Recurra account</p>

        <!-- General errors -->
        <div v-if="generalErrors.length" class="error-box" role="alert">
          <p v-for="message in generalErrors" :key="message">{{ message }}</p>
        </div>

        <form @submit.prevent="submit">

          <!-- Username -->
          <div class="form-group">
            <label class="form-label" for="login-username">Username</label>
            <div class="input-wrapper">
              <input
                id="login-username"
                v-model="form.username"
                class="recurra-input"
                :class="{ error: fieldErrors.username?.length }"
                type="text"
                placeholder="your username"
                autocomplete="username"
                required
              />
              <span class="input-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
                </svg>
              </span>
            </div>
            <p v-if="fieldErrors.username?.length" class="field-error">{{ fieldErrors.username[0] }}</p>
          </div>

          <!-- Password -->
          <div class="form-group">
            <label class="form-label" for="login-password">Password</label>
            <div class="input-wrapper">
              <input
                id="login-password"
                v-model="form.password"
                class="recurra-input"
                :class="{ error: fieldErrors.password?.length }"
                :type="showPassword ? 'text' : 'password'"
                placeholder="••••••••"
                autocomplete="current-password"
                required
              />
              <button type="button" class="input-icon-btn" @click="showPassword = !showPassword">
                <svg v-if="!showPassword" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              </button>
            </div>
            <p v-if="fieldErrors.password?.length" class="field-error">{{ fieldErrors.password[0] }}</p>
          </div>

          <!-- Remember me + forgot -->
          <div class="form-row-between">
            <label class="checkbox-label">
              <input type="checkbox" /> Remember me
            </label>
            <RouterLink to="/auth/password-reset" class="forgot-link">Forgot password?</RouterLink>
          </div>

          <!-- Submit -->
          <button type="submit" class="recurra-btn-primary" :disabled="loading">
            {{ loading ? 'Signing in...' : 'Sign in' }}
          </button>

        </form>

        <div class="divider">
          <div class="divider-line"></div>
          <span class="divider-text">New to Recurra?</span>
          <div class="divider-line"></div>
        </div>

        <p class="register-link">
          Don't have an account?
          <RouterLink to="/auth/register">Create one</RouterLink>
        </p>

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

/* LEFT PANEL */
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

.logo-area {
  display: flex;
  align-items: center;
  gap: 10px;
}

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

.brand-content {
  margin-top: 56px;
}

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

.left-footer {
  margin-top: auto;
}

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

/* RIGHT PANEL */
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

.form-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.3px;
  margin: 0 0 5px;
}

.form-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 28px;
}

.error-box {
  background: var(--danger-bg);
  border: 1px solid #FECACA;
  border-radius: 8px;
  padding: 11px 14px;
  font-size: 13px;
  color: #B91C1C;
  margin-bottom: 20px;
}

.error-box p { margin: 0; }

.form-group {
  margin-bottom: 16px;
}

.form-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.input-wrapper {
  position: relative;
}

.input-icon {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;
}

.input-icon svg {
  width: 16px;
  height: 16px;
  display: block;
}

.input-icon-btn {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  padding: 2px;
  cursor: pointer;
  color: var(--text-muted);
  display: flex;
  align-items: center;
}

.input-icon-btn svg {
  width: 16px;
  height: 16px;
}

.field-error {
  font-size: 12px;
  color: var(--danger);
  margin: 5px 0 0;
}

.form-row-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
}

.checkbox-label input {
  accent-color: var(--violet);
  width: 14px;
  height: 14px;
  cursor: pointer;
}

.forgot-link {
  font-size: 13px;
  color: var(--violet);
  text-decoration: none;
  font-weight: 500;
}

.forgot-link:hover { text-decoration: underline; }

.divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 22px 0;
}

.divider-line {
  flex: 1;
  height: 1px;
  background: var(--border-light);
}

.divider-text {
  font-size: 12px;
  color: var(--text-muted);
}

.register-link {
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

.register-link a {
  color: var(--violet);
  text-decoration: none;
  font-weight: 500;
}

.register-link a:hover { text-decoration: underline; }

/* Responsive */
@media (max-width: 768px) {
  .auth-screen { flex-direction: column; }
  .left-panel { width: 100%; min-height: 280px; }
  .left-panel-inner { padding: 32px; }
  .brand-content { margin-top: 24px; }
  .feature-list { display: none; }
}
</style>
