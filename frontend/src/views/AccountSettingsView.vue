<!-- /frontend/src/views/AccountSettingsView.vue -->

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import { changePassword, deleteAccount, fetchMe, updateMe } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/apiErrors'

const router = useRouter()
const authStore = useAuthStore()
const { user } = storeToRefs(authStore)

const activeSection = ref('profile')
const loadingSettings = ref(true)
const loadError = ref('')

const profileForm = reactive({
  first_name: '',
  last_name: '',
  email: '',
})

const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

const notifications = reactive({
  email_enabled: true,
})

const profileSaved = ref(false)
const passwordSaved = ref(false)
const notifSaved = ref(false)
const profileError = ref('')
const passwordError = ref('')
const notifError = ref('')
const profileLoading = ref(false)
const passwordLoading = ref(false)
const notifLoading = ref(false)
const deleteAccountLoading = ref(false)
const deleteAccountError = ref('')
const deleteModal = reactive({
  open: false,
  confirmPhrase: '',
  acknowledgeDeletion: false,
})

function applyUserData(account) {
  profileForm.first_name = account?.first_name || ''
  profileForm.last_name = account?.last_name || ''
  profileForm.email = account?.email || ''
  notifications.email_enabled = account?.notification_opt_in ?? true
}

function flashSaved(stateRef) {
  stateRef.value = true
  setTimeout(() => {
    stateRef.value = false
  }, 3000)
}

async function loadSettings() {
  loadingSettings.value = true
  loadError.value = ''
  try {
    const { data } = await fetchMe()
    authStore.setSession({ user: data })
    applyUserData(data)
  } catch (error) {
    loadError.value = getErrorMessage(error, 'Failed to load account settings.')
  } finally {
    loadingSettings.value = false
  }
}

async function saveProfile() {
  if (profileLoading.value) return
  profileError.value = ''
  profileLoading.value = true
  try {
    const { data } = await updateMe({
      first_name: profileForm.first_name,
      last_name: profileForm.last_name,
      email: profileForm.email,
    })
    authStore.setSession({ user: data })
    applyUserData(data)
    flashSaved(profileSaved)
  } catch (error) {
    profileError.value = getErrorMessage(error, 'Failed to save profile.')
  } finally {
    profileLoading.value = false
  }
}

async function savePassword() {
  if (passwordLoading.value) return
  passwordError.value = ''
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    passwordError.value = 'New passwords do not match.'
    return
  }
  if (passwordForm.new_password.length < 8) {
    passwordError.value = 'Password must be at least 8 characters.'
    return
  }

  passwordLoading.value = true
  try {
    await changePassword({
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    })
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
    flashSaved(passwordSaved)
  } catch (error) {
    passwordError.value = getErrorMessage(error, 'Failed to update password.')
  } finally {
    passwordLoading.value = false
  }
}

async function saveNotifications() {
  if (notifLoading.value) return
  notifError.value = ''
  notifLoading.value = true
  try {
    const { data } = await updateMe({
      notification_opt_in: notifications.email_enabled,
    })
    authStore.setSession({ user: data })
    applyUserData(data)
    flashSaved(notifSaved)
  } catch (error) {
    notifError.value = getErrorMessage(error, 'Failed to save notification preferences.')
  } finally {
    notifLoading.value = false
  }
}

async function logout() {
  await authStore.logoutCurrentSession()
  router.push({ name: 'login' })
}

function openDeleteAccountModal() {
  deleteAccountError.value = ''
  deleteModal.open = true
}

function closeDeleteAccountModal() {
  deleteModal.open = false
  deleteModal.confirmPhrase = ''
  deleteModal.acknowledgeDeletion = false
  deleteAccountError.value = ''
}

const canDeleteAccount = () => (
  deleteModal.confirmPhrase === 'DELETE'
  && deleteModal.acknowledgeDeletion
)

async function confirmDeleteAccount() {
  if (deleteAccountLoading.value || !canDeleteAccount()) return
  deleteAccountError.value = ''
  deleteAccountLoading.value = true
  try {
    await deleteAccount({
      confirmation_text: deleteModal.confirmPhrase,
    })
    deleteAccountLoading.value = false
    closeDeleteAccountModal()
    authStore.clearSession()
    authStore.setAuthMessage('Your account has been deleted.')
    router.push({ name: 'login' })
  } catch (error) {
    deleteAccountError.value = getErrorMessage(error, 'Failed to delete account.')
  } finally {
    deleteAccountLoading.value = false
  }
}

const sections = [
  { key: 'profile', label: 'Profile', icon: `<circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>` },
  { key: 'password', label: 'Password', icon: `<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>` },
  { key: 'notifications', label: 'Notifications', icon: `<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>` },
  { key: 'security', label: 'Security', icon: `<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>` },
]

onMounted(loadSettings)
</script>

<template>
  <AppLayout>
    <template #topbar>
      <span class="topbar-title">Account Settings</span>
    </template>

    <div class="settings-page">
      <div v-if="loadingSettings" class="status-banner">Loading account settings...</div>
      <div v-else-if="loadError" class="error-banner">{{ loadError }}</div>

      <template v-else>
        <div class="settings-nav">
          <div
            v-for="section in sections"
            :key="section.key"
            class="settings-nav-item"
            :class="{ active: activeSection === section.key }"
            @click="activeSection = section.key"
          >
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" v-html="section.icon"></svg>
            {{ section.label }}
          </div>
        </div>

        <div class="settings-content">
          <div v-if="activeSection === 'profile'">
            <div class="section-card">
              <div class="section-card-header">
                <div class="section-card-title">Profile</div>
                <div class="section-card-desc">Your personal account information</div>
              </div>

              <div class="avatar-row">
                <div class="avatar-lg">
                  {{ (profileForm.first_name?.[0] || user?.username?.[0] || '?').toUpperCase() }}{{ (profileForm.last_name?.[0] || '').toUpperCase() }}
                </div>
                <div>
                  <div class="avatar-name">{{ profileForm.first_name }} {{ profileForm.last_name }}</div>
                  <div class="avatar-email">{{ profileForm.email }}</div>
                </div>
              </div>

              <div class="setting-row">
                <div class="setting-info">
                  <div class="setting-label">First name</div>
                </div>
                <div class="setting-control">
                  <BaseInput v-model="profileForm.first_name" placeholder="First name" />
                </div>
              </div>

              <div class="setting-row">
                <div class="setting-info">
                  <div class="setting-label">Last name</div>
                </div>
                <div class="setting-control">
                  <BaseInput v-model="profileForm.last_name" placeholder="Last name" />
                </div>
              </div>

              <div class="setting-row">
                <div class="setting-info">
                  <div class="setting-label">Email address</div>
                  <div class="setting-desc">Used for login and all email notifications</div>
                </div>
                <div class="setting-control">
                  <BaseInput v-model="profileForm.email" type="email" placeholder="you@example.com" />
                </div>
              </div>

              <div class="btn-save-row">
                <span v-if="profileError" class="error-msg">{{ profileError }}</span>
                <span v-if="profileSaved" class="saved-msg">✓ Changes saved</span>
                <BaseButton variant="primary" size="sm" :loading="profileLoading" :disabled="profileLoading" @click="saveProfile">Save changes</BaseButton>
              </div>
            </div>
          </div>

          <div v-if="activeSection === 'password'">
            <div class="section-card">
              <div class="section-card-header">
                <div class="section-card-title">Change password</div>
                <div class="section-card-desc">Choose a strong password and confirm it before saving</div>
              </div>

              <div class="setting-row">
                <div class="setting-info">
                  <div class="setting-label">Current password</div>
                </div>
                <div class="setting-control">
                  <BaseInput v-model="passwordForm.current_password" type="password" placeholder="••••••••" autocomplete="current-password" />
                </div>
              </div>

              <div class="setting-row">
                <div class="setting-info">
                  <div class="setting-label">New password</div>
                </div>
                <div class="setting-control">
                  <BaseInput v-model="passwordForm.new_password" type="password" placeholder="••••••••" autocomplete="new-password" />
                </div>
              </div>

              <div class="setting-row">
                <div class="setting-info">
                  <div class="setting-label">Confirm new password</div>
                </div>
                <div class="setting-control">
                  <BaseInput v-model="passwordForm.confirm_password" type="password" placeholder="••••••••" autocomplete="new-password" />
                </div>
              </div>

              <div class="btn-save-row">
                <span v-if="passwordError" class="error-msg">{{ passwordError }}</span>
                <span v-if="passwordSaved" class="saved-msg">✓ Password updated</span>
                <BaseButton variant="primary" size="sm" :loading="passwordLoading" :disabled="passwordLoading" @click="savePassword">Update password</BaseButton>
              </div>
            </div>
          </div>

          <div v-if="activeSection === 'notifications'">
            <div class="section-card">
              <div class="section-card-header">
                <div class="section-card-title">Notification preferences</div>
                <div class="section-card-desc">Control global email reminders and manage per-task opt-outs from cycle task details</div>
              </div>

              <div class="setting-row">
                <div class="setting-info">
                  <div class="setting-label">Email notifications</div>
                  <div class="setting-desc">Turning this off disables reminder and overdue emails for your account.</div>
                </div>
                <div class="setting-control">
                  <label class="toggle-switch">
                    <input type="checkbox" v-model="notifications.email_enabled" />
                    <span class="toggle-slider"></span>
                  </label>
                </div>
              </div>

              <div class="setting-row">
                <div class="setting-info">
                  <div class="setting-label">Per-task opt-out</div>
                  <div class="setting-desc">Each runtime task can also opt out individually from its detail modal inside a cycle.</div>
                </div>
              </div>

              <div class="btn-save-row">
                <span v-if="notifError" class="error-msg">{{ notifError }}</span>
                <span v-if="notifSaved" class="saved-msg">✓ Preferences saved</span>
                <BaseButton variant="primary" size="sm" :loading="notifLoading" :disabled="notifLoading" @click="saveNotifications">Save preferences</BaseButton>
              </div>
            </div>
          </div>

          <div v-if="activeSection === 'security'">
            <div class="section-card">
              <div class="section-card-header">
                <div class="section-card-title">Security</div>
                <div class="section-card-desc">Manage your active authenticated session</div>
              </div>

              <div class="setting-row">
                <div class="setting-info">
                  <div class="setting-label">Log out</div>
                  <div class="setting-desc">End your current session and return to the login screen</div>
                </div>
                <div class="setting-control">
                  <BaseButton variant="secondary" size="sm" @click="logout">Log out</BaseButton>
                </div>
              </div>
            </div>

            <div class="section-card danger-zone">
              <div class="section-card-header">
                <div class="section-card-title">Danger zone</div>
                <div class="section-card-desc">These actions are permanent and cannot be undone</div>
              </div>

              <div class="setting-row">
                <div class="setting-info">
                  <div class="setting-label">Delete account</div>
                  <div class="setting-desc">Permanently delete your account, running cycles, saved data, and owned templates.</div>
                </div>
                <div class="setting-control">
                  <BaseButton variant="danger" size="sm" @click="openDeleteAccountModal">Delete account</BaseButton>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <BaseModal
      v-model="deleteModal.open"
      title="Delete account"
      confirm-label="Delete account"
      confirm-variant="danger"
      :confirm-disabled="!canDeleteAccount()"
      :loading="deleteAccountLoading"
      @confirm="confirmDeleteAccount"
      @cancel="closeDeleteAccountModal"
    >
      <div class="delete-modal-body">
        <p class="delete-modal-lead">
          This permanently removes your account and clears access to Recurra. This action cannot be undone.
        </p>

        <div class="delete-warning-box">
          <div class="delete-warning-title">Before you continue</div>
          <label class="check-item">
            <input v-model="deleteModal.acknowledgeDeletion" type="checkbox">
            I understand this will permanently delete my account and all associated Recurra data.
          </label>
        </div>

        <div>
          <div class="field-label">Type DELETE to confirm</div>
          <BaseInput
            v-model="deleteModal.confirmPhrase"
            placeholder="DELETE"
          />
        </div>

        <p v-if="deleteAccountError" class="delete-error">{{ deleteAccountError }}</p>
      </div>
    </BaseModal>
  </AppLayout>
</template>

<style scoped>
.topbar-title { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); }

.settings-page {
  display: flex;
  gap: 28px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.status-banner,
.error-banner {
  width: 100%;
  border-radius: var(--radius-md);
  padding: 12px 16px;
  font-size: var(--font-body);
}

.status-banner {
  background: var(--bg-page);
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
}

.error-banner {
  background: var(--danger-bg);
  border: 1px solid #FECACA;
  color: #B91C1C;
}

.settings-nav {
  width: 190px;
  flex-shrink: 0;
}

.settings-nav-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  font-size: var(--font-body);
  color: var(--text-secondary);
  cursor: pointer;
  margin-bottom: 2px;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.settings-nav-item:hover { background: var(--bg-page); color: var(--text-primary); }
.settings-nav-item.active { background: var(--violet-bg); color: var(--violet); font-weight: 500; }

.nav-icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
}

.settings-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 16px; }

.section-card {
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin-bottom: 16px;
}

.section-card-header { padding: 15px 20px; border-bottom: 1px solid var(--border-light); }
.section-card-title { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); margin-bottom: 2px; }
.section-card-desc { font-size: var(--font-label); color: var(--text-muted); }

.avatar-row { display: flex; align-items: center; gap: 14px; padding: 14px 20px; border-bottom: 1px solid var(--border-light); }
.avatar-lg { width: 48px; height: 48px; border-radius: 50%; background: var(--violet-bg); display: flex; align-items: center; justify-content: center; font-size: var(--font-title); font-weight: 600; color: var(--violet); flex-shrink: 0; }
.avatar-name { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); margin-bottom: 2px; }
.avatar-email { font-size: var(--font-label); color: var(--text-muted); }

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-light);
  gap: 24px;
}

.setting-row:last-child { border-bottom: none; }

.setting-info { flex: 1; }
.setting-label { font-size: var(--font-label); font-weight: 500; color: var(--text-primary); margin-bottom: 2px; }
.setting-desc { font-size: var(--font-label); color: var(--text-muted); line-height: 1.5; }
.setting-control { flex-shrink: 0; width: 280px; }

.toggle-switch { position: relative; width: 38px; height: 21px; display: inline-block; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background: #CBD5E1; border-radius: 21px; transition: 0.2s; }
.toggle-slider::before { position: absolute; content: ''; height: 15px; width: 15px; left: 3px; bottom: 3px; background: white; border-radius: 50%; transition: 0.2s; }
input:checked + .toggle-slider { background: var(--violet); }
input:checked + .toggle-slider::before { transform: translateX(17px); }

.btn-save-row {
  padding: 12px 20px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  border-top: 1px solid var(--border-light);
}

.saved-msg { font-size: var(--font-body); color: var(--success); font-weight: 500; }
.error-msg { font-size: var(--font-body); color: var(--danger); }

.danger-zone { border-color: #FECACA; }
.danger-zone .section-card-header { background: var(--danger-bg); border-bottom-color: #FECACA; }
.danger-zone .section-card-title { color: #B91C1C; }
.danger-zone .section-card-desc { color: #991B1B; }

.delete-modal-body { display: flex; flex-direction: column; gap: 16px; }
.delete-modal-lead { margin: 0; font-size: var(--font-body); color: var(--text-secondary); line-height: 1.6; }
.delete-warning-box {
  background: #FFF7ED;
  border: 1px solid #FED7AA;
  border-radius: var(--radius-md);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.delete-warning-title {
  font-size: var(--font-label);
  font-weight: 600;
  color: #9A3412;
}
.field-label {
  margin-bottom: 6px;
  font-size: var(--font-label);
  font-weight: 500;
  color: var(--text-primary);
}
.check-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: var(--font-label);
  line-height: 1.5;
  color: var(--text-primary);
}
.check-item input {
  margin-top: 2px;
  accent-color: var(--violet);
}
.delete-error {
  margin: 0;
  color: var(--danger);
  font-size: var(--font-label);
}
</style>
