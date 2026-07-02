<!-- /frontend/src/views/auth/RegisterView.vue -->

<script setup>
import { reactive, ref, computed } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { register } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { useOnboardingStore } from '@/stores/onboarding'
import { normalizeApiError } from '@/utils/forms'
import AuthLayout from '@/layouts/AuthLayout.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const authStore = useAuthStore()
const onboardingStore = useOnboardingStore()
const router = useRouter()

const form = reactive({
  first_name: '',
  last_name: '',
  email: '',
  username: '',
  password: '',
  password_confirm: '',
})

const fieldErrors = ref({})
const generalErrors = ref([])
const loading = ref(false)
const agreedToTerms = ref(false)

// Password strength
const passwordStrength = computed(() => {
  const pwd = form.password
  if (!pwd) return 0
  let score = 0
  if (pwd.length >= 8) score++
  if (/[A-Z]/.test(pwd)) score++
  if (/[0-9]/.test(pwd)) score++
  if (/[^A-Za-z0-9]/.test(pwd)) score++
  return score
})

const strengthLabel = computed(() => ['', 'Weak', 'Fair', 'Good', 'Strong'][passwordStrength.value])
const strengthColors = ['#E2E8F0', '#EF4444', '#F59E0B', '#7C3AED', '#22C55E']

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
    onboardingStore.maybeAutoStart('sidebar')
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
  <AuthLayout
    headline="Start managing your&#10;processes today"
    tagline="Create your free account and take control of your repeating workflows in minutes."
    :features="['Create unlimited process templates', 'Run multiple overlapping cycles', 'Get email reminders automatically', 'Share templates with your team']"
  >

    <h2 class="form-title">Create your account</h2>
    <p class="form-subtitle">Fill in the details below to get started.</p>

    <div v-if="generalErrors.length" class="error-banner" role="alert">
      <p v-for="msg in generalErrors" :key="msg">{{ msg }}</p>
    </div>

    <form @submit.prevent="submit" novalidate>

      <!-- Name row -->
      <div class="field form-row-2">
        <BaseInput
          v-model="form.first_name"
          label="First name"
          placeholder="Jane"
          :error="fieldErrors.first_name?.[0]"
          required
        />
        <BaseInput
          v-model="form.last_name"
          label="Last name"
          placeholder="Smith"
          :error="fieldErrors.last_name?.[0]"
          required
        />
      </div>

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

      <div class="field">
        <BaseInput
          v-model="form.username"
          label="Username"
          placeholder="your_username"
          autocomplete="username"
          :error="fieldErrors.username?.[0]"
          required
        />
      </div>

      <div class="field">
        <BaseInput
          v-model="form.password"
          label="Password"
          type="password"
          placeholder="••••••••"
          autocomplete="new-password"
          :error="fieldErrors.password?.[0]"
          required
        />
        <!-- Password strength -->
        <div v-if="form.password" class="strength-bars">
          <div
            v-for="i in 4" :key="i"
            class="strength-bar"
            :style="{ background: i <= passwordStrength ? strengthColors[passwordStrength] : '#E2E8F0' }"
          ></div>
        </div>
        <p v-if="form.password" class="strength-label">
          Password strength: <strong>{{ strengthLabel }}</strong>
        </p>
      </div>

      <div class="field">
        <BaseInput
          v-model="form.password_confirm"
          label="Confirm password"
          type="password"
          placeholder="••••••••"
          autocomplete="new-password"
          :error="fieldErrors.password_confirm?.[0]"
          required
        />
      </div>

      <div class="terms-row">
        <input id="terms" v-model="agreedToTerms" type="checkbox" />
        <label for="terms">
          I agree to the <a href="#" class="terms-link">Terms of Service</a> and <a href="#" class="terms-link">Privacy Policy</a>
        </label>
      </div>

      <BaseButton type="submit" variant="primary" :loading="loading" full-width>
        Create account
      </BaseButton>

    </form>

    <p class="bottom-link">
      <span class="bottom-link-text">Already have an account?</span>
      <RouterLink to="/auth/login" class="bottom-link-action"> Sign in</RouterLink>
    </p>


  </AuthLayout>
</template>

<style scoped>
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
  margin: 0 0 22px;
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

.field { margin-bottom: 13px; }

.form-row-2 {
  display: flex;
  gap: 12px;
}

.form-row-2 > * { flex: 1; }

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
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.terms-row input {
  accent-color: var(--violet);
  width: 14px;
  height: 14px;
  margin-top: 2px;
  flex-shrink: 0;
  cursor: pointer;
}

.terms-link {
  color: var(--violet);
  font-weight: 500;
}

.bottom-link {
  text-align: center;
  font-size: 13px;
  margin: 18px 0 0;
}

.bottom-link-text {
  color: var(--text-secondary);
  margin-right: 4px;
}

.bottom-link-action {
  color: var(--violet);
  font-weight: 500;
}

</style>