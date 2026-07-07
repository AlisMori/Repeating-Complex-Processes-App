<!-- /frontend/src/views/auth/LoginView.vue -->

<script setup>
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { login } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { normalizeApiError } from '@/utils/forms'
import AuthLayout from '@/layouts/AuthLayout.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const authStore = useAuthStore()
const router = useRouter()

const form = reactive({ username: '', password: '' })
const fieldErrors = ref({})
const generalErrors = ref([])
const loading = ref(false)
const rememberMe = ref(false)

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
  <AuthLayout>

    <h2 class="form-title">Welcome back</h2>
    <p class="form-subtitle">Sign in to your Recurra account</p>

    <!-- General error -->
    <div v-if="generalErrors.length" class="error-banner" role="alert">
      <p v-for="msg in generalErrors" :key="msg">{{ msg }}</p>
    </div>

    <form @submit.prevent="submit" novalidate>

      <div class="field">
        <BaseInput
          v-model="form.username"
          label="Username"
          placeholder="your username"
          autocomplete="username"
          :error="fieldErrors.username?.[0]"
          required
        >
          <template #suffix>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
            </svg>
          </template>
        </BaseInput>
      </div>

      <div class="field">
        <BaseInput
          v-model="form.password"
          label="Password"
          type="password"
          placeholder="••••••••"
          autocomplete="current-password"
          :error="fieldErrors.password?.[0]"
          required
        />
      </div>

      <div class="form-row-between">
        <label class="checkbox-label">
          <input v-model="rememberMe" type="checkbox" /> Remember me
        </label>
        <RouterLink to="/auth/password-reset" class="forgot-link">Forgot password?</RouterLink>
      </div>

      <BaseButton type="submit" variant="primary" :loading="loading" full-width>
        Sign in
      </BaseButton>

    </form>

    <div class="divider">
      <div class="divider-line"></div>
      <span class="divider-text">New to Recurra?</span>
      <div class="divider-line"></div>
    </div>

    <p class="bottom-link">
      <span class="bottom-link-text">Don't have an account?</span>
      <RouterLink to="/auth/register" class="bottom-link-action">Create one</RouterLink>
    </p>

  </AuthLayout>
</template>

<style scoped>
form { width: 100%; }

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
  margin: 0 0 26px;
}

.error-banner {
  background: var(--danger-bg);
  border: 1px solid #FECACA;
  border-radius: var(--radius-md);
  padding: 11px 14px;
  font-size: 13px;
  color: #B91C1C;
  margin-bottom: 18px;
}
.error-banner p { margin: 0; }

.field { margin-bottom: 14px; }

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
  font-size: 14px;
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
  font-size: 14px;
  color: var(--violet);
  font-weight: 500;
}

.divider {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 22px 0;
}

.divider-line { flex: 1; height: 1px; background: var(--border-light); }
.divider-text { font-size: 14px; color: var(--text-muted); }

.bottom-link {
  text-align: center;
  font-size: 14px;
  margin: 0;
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