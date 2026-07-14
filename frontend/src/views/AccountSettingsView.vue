<!-- /frontend/src/views/AccountSettingsView.vue -->

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import AppLayout from '@/layouts/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const { user } = storeToRefs(authStore)

const activeSection = ref('profile')

// Profile form
const profileForm = reactive({
  first_name: user.value?.first_name || '',
  last_name: user.value?.last_name || '',
  email: user.value?.email || '',
})

// Password form
const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

// Notification preferences
const notifications = reactive({
  email_enabled: true,
  reminder_7_days: true,
  reminder_3_days: true,
  reminder_on_day: false,
  overdue_alerts: true,
})

// Session settings
const sessionTimeout = ref('30')

const profileSaved = ref(false)
const passwordSaved = ref(false)
const notifSaved = ref(false)
const passwordError = ref('')

function saveProfile() {
  // TODO: connect to API
  profileSaved.value = true
  setTimeout(() => profileSaved.value = false, 3000)
}

function savePassword() {
  passwordError.value = ''
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    passwordError.value = 'New passwords do not match.'
    return
  }
  if (passwordForm.new_password.length < 8) {
    passwordError.value = 'Password must be at least 8 characters.'
    return
  }
  // TODO: connect to API
  passwordSaved.value = true
  passwordForm.current_password = ''
  passwordForm.new_password = ''
  passwordForm.confirm_password = ''
  setTimeout(() => passwordSaved.value = false, 3000)
}

function saveNotifications() {
  // TODO: connect to API
  notifSaved.value = true
  setTimeout(() => notifSaved.value = false, 3000)
}

async function logout() {
  await authStore.logoutCurrentSession()
  router.push({ name: 'login' })
}

const sections = [
  { key: 'profile', label: 'Profile', icon: `<circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>` },
  { key: 'password', label: 'Password', icon: `<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>` },
  { key: 'notifications', label: 'Notifications', icon: `<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>` },
  { key: 'security', label: 'Session & Security', icon: `<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>` },
]
</script>

<template>
  <AppLayout>
    <template #topbar>
      <span class="topbar-title">Account Settings</span>
    </template>

    <div class="settings-page">

      <!-- SETTINGS NAV -->
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

      <!-- SETTINGS CONTENT -->
      <div class="settings-content">

        <!-- PROFILE -->
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
              <span v-if="profileSaved" class="saved-msg">✓ Changes saved</span>
              <BaseButton variant="primary" size="sm" @click="saveProfile">Save changes</BaseButton>
            </div>
          </div>

        </div>

        <!-- PASSWORD -->
        <div v-if="activeSection === 'password'">

          <div class="section-card">
            <div class="section-card-header">
              <div class="section-card-title">Change password</div>
              <div class="section-card-desc">Choose a strong password at least 8 characters long</div>
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
              <BaseButton variant="primary" size="sm" @click="savePassword">Update password</BaseButton>
            </div>
          </div>

        </div>

        <!-- NOTIFICATIONS -->
        <div v-if="activeSection === 'notifications'">

          <div class="section-card">
            <div class="section-card-header">
              <div class="section-card-title">Notification preferences</div>
              <div class="section-card-desc">Control how and when Recurra sends you email reminders</div>
            </div>

            <div class="setting-row">
              <div class="setting-info">
                <div class="setting-label">Email notifications</div>
                <div class="setting-desc">Master switch — turning this off disables all email reminders globally</div>
              </div>
              <div class="setting-control">
                <label class="toggle-switch">
                  <input type="checkbox" v-model="notifications.email_enabled" />
                  <span class="toggle-slider"></span>
                </label>
              </div>
            </div>

            <div class="setting-row" :class="{ disabled: !notifications.email_enabled }">
              <div class="setting-info">
                <div class="setting-label">Default reminder lead times</div>
                <div class="setting-desc">Applied to all tasks unless overridden at template or task level</div>
              </div>
              <div class="setting-control">
                <div class="reminder-check-group">
                  <label class="reminder-check-item">
                    <input type="checkbox" v-model="notifications.reminder_7_days" :disabled="!notifications.email_enabled" />
                    7 days before
                  </label>
                  <label class="reminder-check-item">
                    <input type="checkbox" v-model="notifications.reminder_3_days" :disabled="!notifications.email_enabled" />
                    3 days before
                  </label>
                  <label class="reminder-check-item">
                    <input type="checkbox" v-model="notifications.reminder_on_day" :disabled="!notifications.email_enabled" />
                    On the day
                  </label>
                </div>
              </div>
            </div>

            <div class="setting-row" :class="{ disabled: !notifications.email_enabled }">
              <div class="setting-info">
                <div class="setting-label">Overdue task alerts</div>
                <div class="setting-desc">Send one email when a task passes its due date without completion</div>
              </div>
              <div class="setting-control">
                <label class="toggle-switch">
                  <input type="checkbox" v-model="notifications.overdue_alerts" :disabled="!notifications.email_enabled" />
                  <span class="toggle-slider"></span>
                </label>
              </div>
            </div>

            <div class="btn-save-row">
              <span v-if="notifSaved" class="saved-msg">✓ Preferences saved</span>
              <BaseButton variant="primary" size="sm" @click="saveNotifications">Save preferences</BaseButton>
            </div>
          </div>

        </div>

        <!-- SESSION & SECURITY -->
        <div v-if="activeSection === 'security'">

          <div class="section-card">
            <div class="section-card-header">
              <div class="section-card-title">Session & security</div>
              <div class="section-card-desc">Manage your login session and account security</div>
            </div>

            <div class="setting-row">
              <div class="setting-info">
                <div class="setting-label">Session timeout</div>
                <div class="setting-desc">Automatically log out after a period of inactivity</div>
              </div>
              <div class="setting-control">
                <BaseSelect v-model="sessionTimeout" class="setting-select">
                  <option value="15">15 minutes</option>
                  <option value="30">30 minutes</option>
                  <option value="60">1 hour</option>
                  <option value="120">2 hours</option>
                </BaseSelect>
              </div>
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

          <!-- DANGER ZONE -->
          <div class="section-card danger-zone">
            <div class="section-card-header">
              <div class="section-card-title">Danger zone</div>
              <div class="section-card-desc">These actions are permanent and cannot be undone</div>
            </div>
            <div class="setting-row">
              <div class="setting-info">
                <div class="setting-label">Delete account</div>
                <div class="setting-desc">Permanently delete your account and all associated templates, cycles and data</div>
              </div>
              <div class="setting-control">
                <BaseButton variant="danger" size="sm">Delete account</BaseButton>
              </div>
            </div>
          </div>

        </div>

      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.topbar-title { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); }

.settings-page {
  display: flex;
  gap: 28px;
  align-items: flex-start;
}

/* NAV */
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

/* CONTENT */
.settings-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 16px; }

/* SECTION CARDS */
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

/* AVATAR */
.avatar-row { display: flex; align-items: center; gap: 14px; padding: 14px 20px; border-bottom: 1px solid var(--border-light); }
.avatar-lg { width: 48px; height: 48px; border-radius: 50%; background: var(--violet-bg); display: flex; align-items: center; justify-content: center; font-size: var(--font-title); font-weight: 600; color: var(--violet); flex-shrink: 0; }
.avatar-name { font-size: var(--font-body); font-weight: 600; color: var(--text-primary); margin-bottom: 2px; }
.avatar-email { font-size: var(--font-label); color: var(--text-muted); }

/* ROWS */
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-light);
  gap: 24px;
}

.setting-row:last-child { border-bottom: none; }
.setting-row.disabled { opacity: 0.5; pointer-events: none; }

.setting-info { flex: 1; }
.setting-label { font-size: var(--font-label); font-weight: 500; color: var(--text-primary); margin-bottom: 2px; }
.setting-desc { font-size: var(--font-label); color: var(--text-muted); line-height: 1.5; }
.setting-control { flex-shrink: 0; width: 280px; }

/* SELECT — compact width for the settings row layout */
.setting-select { width: 160px; }
.setting-select :deep(.base-select) { height: 36px; padding: 0 26px 0 11px; }

/* TOGGLE */
.toggle-switch { position: relative; width: 38px; height: 21px; display: inline-block; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background: #CBD5E1; border-radius: 21px; transition: 0.2s; }
.toggle-slider::before { position: absolute; content: ''; height: 15px; width: 15px; left: 3px; bottom: 3px; background: white; border-radius: 50%; transition: 0.2s; }
input:checked + .toggle-slider { background: var(--violet); }
input:checked + .toggle-slider::before { transform: translateX(17px); }

/* REMINDER CHECKBOXES */
.reminder-check-group { display: flex; gap: 20px; flex-wrap: wrap; }
.reminder-check-item { display: flex; align-items: center; gap: 8px; font-size: var(--font-body); color: var(--text-primary); cursor: pointer; }
.reminder-check-item input { accent-color: var(--violet); width: 17px; height: 17px; cursor: pointer; }

/* SAVE ROW */
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

/* DANGER ZONE */
.danger-zone { border-color: #FECACA; }
.danger-zone .section-card-header { background: var(--danger-bg); border-bottom-color: #FECACA; }
.danger-zone .section-card-title { color: #B91C1C; }
.danger-zone .section-card-desc { color: #991B1B; }
</style>
