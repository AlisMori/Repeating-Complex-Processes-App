<script setup>
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { register } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { normalizeApiError } from '@/utils/forms'

const authStore = useAuthStore()
const router = useRouter()

const form = reactive({
  first_name: '',
  last_name: '',
  email: '',
  username: '',
  password: '',
  password_confirm: '',
})

const showPassword = ref(false)
const showConfirm = ref(false)
const fieldErrors = ref({})
const generalErrors = ref([])
const loading = ref(false)
const agreedToTerms = ref(false)

const passwordStrength = ref(0)

function checkPasswordStrength(pwd) {
  let score = 0
  if (pwd.length >= 8) score++
  if (/[A-Z]/.test(pwd)) score++
  if (/[0-9]/.test(pwd)) score++
  if (/[^A-Za-z0-9]/.test(pwd)) score++
  passwordStrength.value = score
}

function onPasswordInput() {
  checkPasswordStrength(form.password)
}

const strengthLabel = {
  0: '', 1: 'Weak', 2: 'Fair', 3: 'Good', 4: 'Strong'
}

const strengthColor = {
  0: '#E2E8F0', 1: '#EF4444', 2: '#F59E0B', 3: '#7C3AED', 4: '#22C55E'
}

async function submit() {
  if (loading.value) return
  if (!agreedToTerms.value) {
    generalErrors.value = ['Please agree to the Terms of Service and Privacy Policy.']
    return
  }
  loading.value = true
  fieldErrors.value = {}
  generalErrors.value = []

  try {
    const { data } = await register(form)
    authStore.setSession({
      access: data.access || '',
      refresh: data.refresh || '',
      user: data.user || null,
    })
    router.push({ name: 'dashboard' })
  } catch (error) {
    const normalized = normalizeApiError(error, {
      fallbackMessage: 'Registration failed. Please check your details and try again.',
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
          <h1 class="brand-headline">Start managing your<br/>processes today</h1>
          <p class="brand-tagline">Create your free account and take control of your repeating workflows in minutes.</p>
          <ul class="feature-list">
            <li class="feature-item"><span class="feature-dot"></span><span>Create unlimited process templates</span></li>
            <li class="feature-item"><span class="feature-dot"></span><span>Run multiple overlapping cycles</span></li>
            <li class="feature-item"><span class="feature-dot"></span><span>Get email reminders automatically</span></li>
            <li class="feature-item"><span class="feature-dot"></span><span>Share templates with your team</span></li>
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

        <h2 class="form-title">Create your account</h2>
        <p class="form-subtitle">Fill in the details below to get started with Recurra.</p>

        <div v-if="generalErrors.length" class="error-box" role="alert">
          <p v-for="message in generalErrors" :key="message">{{ message }}</p>
        </div>

        <form @submit.prevent="submit">

          <!-- Name row -->
          <div class="form-row-2">
            <div class="form-group">
              <label class="form-label" for="reg-firstname">First name</label>
              <input
                id="reg-firstname"
                v-model="form.first_name"
                class="recurra-input"
                :class="{ error: fieldErrors.first_name?.length }"
                type="text"
                placeholder="Jane"
                required
              />
              <p v-if="fieldErrors.first_name?.length" class="field-error">{{ fieldErrors.first_name[0] }}</p>
            </div>
            <div class="form-group">
              <label class="form-label" for="reg-lastname">Last name</label>
              <input
                id="reg-lastname"
                v-model="form.last_name"
                class="recurra-input"
                :class="{ error: fieldErrors.last_name?.length }"
                type="text"
                placeholder="Smith"
                required
              />
              <p v-if="fieldErrors.last_name?.length" class="field-error">{{ fieldErrors.last_name[0] }}</p>
            </div>
          </div>

          <!-- Email -->
          <div class="form-group">
            <label class="form-label" for="reg-email">Email address</label>
            <div class="input-wrapper">
              <input
                id="reg-email"
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

          <!-- Username -->
          <div class="form-group">
            <label class="form-label" for="reg-username">Username</label>
            <input
              id="reg-username"
              v-model="form.username"
              class="recurra-input"
              :class="{ error: fieldErrors.username?.length }"
              type="text"
              placeholder="your_username"
              autocomplete="username"
              required
            />
            <p v-if="fieldErrors.username?.length" class="field-error">{{ fieldErrors.username[0] }}</p>
          </div>

          <!-- Password -->
          <div class="form-group">
            <label class="form-label" for="reg-password">Password</label>
            <div class="input-wrapper">
              <input
                id="reg-password"
                v-model="form.password"
                class="recurra-input"
                :class="{ error: fieldErrors.password?.length }"
                :type="showPassword ? 'text' : 'password'"
                placeholder="••••••••"
                autocomplete="new-password"
                required
                @input="onPasswordInput"
              />
              <button type="button" class="input-icon-btn" @click="showPassword = !showPassword">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                </svg>
              </button>
            </div>
            <!-- Strength bars -->
            <div v-if="form.password" class="strength-bars">
              <div
                v-for="i in 4" :key="i"
                class="strength-bar"
                :style="{ background: i <= passwordStrength ? strengthColor[passwordStrength] : '#E2E8F0' }"
              ></div>
            </div>
            <p v-if="form.password" class="strength-label">
              Password strength: {{ strengthLabel[passwordStrength] }}
            </p>
            <p v-if="fieldErrors.password?.length" class="field-error">{{ fieldErrors.password[0] }}</p>
          </div>

          <!-- Confirm password -->
          <div class="form-group">
            <label class="form-label" for="reg-confirm">Confirm password</label>
            <div class="input-wrapper">
              <input
                id="reg-confirm"
                v-model="form.password_confirm"
                class="recurra-input"
                :class="{ error: fieldErrors.password_confirm?.length }"
                :type="showConfirm ? 'text' : 'password'"
                placeholder="••••••••"
                autocomplete="new-password"
                required
              />
              <button type="button" class="input-icon-btn" @click="showConfirm = !showConfirm">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                </svg>
              </button>
            </div>
            <p v-if="fieldErrors.password_confirm?.length" class="field-error">{{ fieldErrors.password_confirm[0] }}</p>
          </div>

          <!-- Terms -->
          <div class="terms-row">
            <input id="terms" v-model="agreedToTerms" type="checkbox" />
            <label for="terms" class="terms-text">
              I agree to the <a href="#" class="terms-link">Terms of Service</a> and <a href="#" class="terms-link">Privacy Policy</a>
            </label>
          </div>

          <button type="submit" class="recurra-btn-primary" :disabled="loading">
            {{ loading ? 'Creating account...' : 'Create account' }}
          </button>

        </form>

        <p class="login-link">
          Already have an account?
          <RouterLink to="/auth/login">Sign in</RouterLink>
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
  max-width: 420px;
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

.form-row-2 {
  display: flex;
  gap: 12px;
  margin-bottom: 0;
}

.form-row-2 .form-group { flex: 1; }

.form-group { margin-bottom: 14px; }

.form-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 5px;
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

.input-icon-btn svg { width: 16px; height: 16px; }

.field-error {
  font-size: 12px;
  color: var(--danger);
  margin: 4px 0 0;
}

.strength-bars {
  display: flex;
  gap: 4px;
  margin-top: 7px;
}

.strength-bar {
  flex: 1;
  height: 3px;
  border-radius: 2px;
  transition: background 0.2s;
}

.strength-label {
  font-size: 11.5px;
  color: var(--text-muted);
  margin: 4px 0 0;
}

.terms-row {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin-bottom: 18px;
  margin-top: 4px;
}

.terms-row input {
  width: 14px;
  height: 14px;
  accent-color: var(--violet);
  margin-top: 2px;
  flex-shrink: 0;
  cursor: pointer;
}

.terms-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  cursor: pointer;
}

.terms-link {
  color: var(--violet);
  text-decoration: none;
  font-weight: 500;
}

.terms-link:hover { text-decoration: underline; }

.login-link {
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
  margin: 18px 0 0;
}

.login-link a {
  color: var(--violet);
  text-decoration: none;
  font-weight: 500;
}

.login-link a:hover { text-decoration: underline; }

@media (max-width: 768px) {
  .auth-screen { flex-direction: column; }
  .left-panel { width: 100%; min-height: 260px; }
  .left-panel-inner { padding: 28px; }
  .brand-content { margin-top: 20px; }
  .feature-list { display: none; }
  .form-row-2 { flex-direction: column; gap: 0; }
}
</style>
