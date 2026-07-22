<!-- ============================================
   RECURRA — APP LAYOUT (4.1, 4.6)
   /frontend/src/layouts/AppLayout.vue
   Shared shell for all authenticated screens
   ============================================ -->

<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import { useOnboardingStore } from '@/stores/onboarding'
import LogoIcon from '@/components/ui/LogoIcon.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import OnboardingTour from '@/components/ui/OnboardingTour.vue'

const authStore = useAuthStore()
const { user } = storeToRefs(authStore)
const notificationStore = useNotificationStore()
const { shareNotifications, shareNotificationsOpen } = storeToRefs(notificationStore)
const router = useRouter()
const onboardingStore = useOnboardingStore()

const userMenuOpen = ref(false)

function toggleUserMenu() {
  userMenuOpen.value = !userMenuOpen.value
}

function closeUserMenu() {
  userMenuOpen.value = false
}

async function logout() {
  await authStore.logoutCurrentSession()
  notificationStore.reset()
  router.push({ name: 'login' })
}

function openHelp() {
  closeUserMenu()
  onboardingStore.startTour('sidebar')
}

async function acknowledgeShareNotifications() {
  await notificationStore.acknowledgeShareNotifications()
}

const notificationSummary = computed(() => {
  if (shareNotifications.value.length === 1) {
    return '1 new shared template'
  }
  return `${shareNotifications.value.length} new shared templates`
})

onMounted(() => {
  notificationStore.loadShareNotifications()
})

const navItems = [
  {
    label: 'Dashboard',
    name: 'dashboard',
    tourKey: 'dashboard',
    icon: `<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>`,
  },
  {
    label: 'Cycles',
    name: 'cycles',
    tourKey: 'cycles',
    icon: `<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>`,
  },
  {
    label: 'Templates',
    name: 'templates',
    tourKey: 'templates',
    icon: `<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>`,
  },
  {
    label: 'Tags',
    name: 'tags',
    tourKey: 'tags',
    icon: `<path d="M20.59 13.41 13.42 20.58a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><circle cx="7" cy="7" r="1.5" fill="currentColor" stroke="none"/>`,
  },
]
</script>

<template>
  <div class="app-layout" @click="closeUserMenu">

    <!-- SIDEBAR -->
    <aside class="sidebar">

      <!-- Logo -->
      <div class="sidebar-logo" data-tour="logo">
        <LogoIcon :size="32" />
      </div>

      <!-- Nav -->
      <nav class="sidebar-nav">

        <RouterLink
          v-for="item in navItems"
          :key="item.name"
          :to="{ name: item.name }"
          class="nav-item"
          active-class="nav-item-active"
          :data-tour="item.tourKey"
        >
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" v-html="item.icon"></svg>
          <span class="nav-label">{{ item.label }}</span>
        </RouterLink>

        <RouterLink :to="{ name: 'account-settings' }" class="nav-item" active-class="nav-item-active">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
          </svg>
          <span class="nav-label">Account Settings</span>
        </RouterLink>

        <button type="button" class="nav-item nav-item-button" @click="openHelp">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <span class="nav-label">Help</span>
        </button>
      </nav>

      <!-- User row with dropdown -->
      <div class="sidebar-footer">

        <!-- Dropdown -->
        <Transition name="dropdown">
          <div v-if="userMenuOpen" class="user-dropdown" @click.stop>
            <div class="dropdown-header">
              <div class="dropdown-name">{{ user?.first_name || user?.username }}</div>
              <div class="dropdown-email">{{ user?.email }}</div>
            </div>
            <RouterLink :to="{ name: 'account-settings' }" class="dropdown-item" @click="closeUserMenu">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
              </svg>
              Account Settings
            </RouterLink>
            <button type="button" class="dropdown-item" @click="openHelp">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
              Replay tour
            </button>
            <button type="button" class="dropdown-item dropdown-logout" @click="logout">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
              Log out
            </button>
          </div>
        </Transition>

        <!-- User row -->
        <button type="button" class="user-row" data-tour="user-menu" @click.stop="toggleUserMenu">
          <div class="user-avatar">
            {{ (user?.first_name?.[0] || user?.username?.[0] || '?').toUpperCase() }}{{ (user?.last_name?.[0] || '').toUpperCase() }}
          </div>
          <div class="user-info">
            <div class="user-name">{{ user?.first_name ? `${user.first_name} ${user.last_name}` : user?.username }}</div>
            <div class="user-email">{{ user?.email }}</div>
          </div>
          <svg class="user-chevron" :class="{ 'chevron-up': userMenuOpen }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>

      </div>
    </aside>

    <!-- MAIN AREA -->
    <div class="main-area">

      <!-- TOPBAR -->
      <header class="topbar">
        <slot name="topbar" />
      </header>

      <!-- CONTENT -->
      <main class="content-area">
        <slot />
      </main>

    </div>

    <!-- ONBOARDING TOUR -->
    <OnboardingTour />

    <BaseModal
      v-model="shareNotificationsOpen"
      title="Templates Shared With You"
      size="lg"
      confirm-label=""
      @cancel="notificationStore.closeShareNotifications"
    >
      <div class="share-notification-modal">
        <div class="share-notification-summary">{{ notificationSummary }}</div>
        <div class="share-notification-list">
          <div
            v-for="notification in shareNotifications"
            :key="notification.notification_id"
            class="share-notification-item"
          >
            <div class="share-notification-badge">Shared</div>
            <div class="share-notification-copy">
              <div class="share-notification-title">
                {{ notification.sender_username }} shared <strong>{{ notification.template_name }}</strong>
              </div>
              <div class="share-notification-meta">
                {{ new Date(notification.created_at).toLocaleString('en-AU', { dateStyle: 'medium', timeStyle: 'short' }) }}
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <BaseButton variant="primary" @click="acknowledgeShareNotifications">
          Open my templates
        </BaseButton>
      </template>
    </BaseModal>

  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  width: 100%;
  min-height: 100vh;
}

/* SIDEBAR */
.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  background: var(--white);
  border-right: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: sticky;
  top: 0;
}

.sidebar-logo {
  padding: 18px 18px 14px;
  border-bottom: 1px solid var(--border-light);
}

.sidebar-nav {
  flex: 1;
  padding: 10px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}

.nav-section-label {
  font-size: var(--font-upper);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.07em;
  padding: 10px 10px 5px;
  display: block;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: var(--radius-md);
  font-size: var(--font-body);
  color: var(--text-secondary);
  text-decoration: none;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.nav-item:hover {
  background: var(--bg-page);
  color: var(--text-primary);
  text-decoration: none;
}

.nav-item-active {
  background: var(--violet-bg) !important;
  color: var(--violet) !important;
  font-weight: 500;
}

.nav-item-button {
  background: none;
  border: none;
  width: 100%;
  text-align: left;
  cursor: pointer;
  font-family: var(--font-main);
}

.nav-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.nav-label { flex: 1; }

.share-notification-modal {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.share-notification-summary {
  font-size: var(--font-label);
  font-weight: 600;
  color: var(--text-primary);
}

.share-notification-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.share-notification-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 16px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, #F5F3FF 0%, #FFFFFF 100%);
  border: 1px solid #DDD6FE;
}

.share-notification-badge {
  flex-shrink: 0;
  padding: 5px 9px;
  border-radius: 999px;
  background: var(--violet);
  color: var(--white);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.share-notification-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.share-notification-title {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.5;
}

.share-notification-meta {
  font-size: 12px;
  color: var(--text-muted);
}

/* SIDEBAR FOOTER */
.sidebar-footer {
  padding: 10px 8px;
  border-top: 1px solid var(--border-light);
  position: relative;
}

.user-row {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  cursor: pointer;
  width: 100%;
  background: var(--bg-page);
  border: 1px solid var(--border-light);
  font-family: var(--font-main);
  transition: background var(--transition-fast);
}

.user-row:hover { background: var(--border-light); }

.user-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--violet-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-hint);
  font-weight: 600;
  color: var(--violet);
  flex-shrink: 0;
}

.user-info { flex: 1; min-width: 0; text-align: left; }

.user-name {
  font-size: var(--font-label);
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-email {
  font-size: var(--font-hint);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-chevron {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  color: var(--text-muted);
  transition: transform var(--transition-fast);
}

.chevron-up { transform: rotate(180deg); }

/* USER DROPDOWN */
.user-dropdown {
  position: absolute;
  bottom: 68px;
  left: 8px;
  right: 8px;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  z-index: 100;
}

.dropdown-header {
  padding: 11px 14px;
  border-bottom: 1px solid var(--border-light);
  background: var(--bg-page);
}

.dropdown-name {
  font-size: var(--font-label);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 1px;
}

.dropdown-email {
  font-size: 11.5px;
  color: var(--text-muted);
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  font-size: var(--font-label);
  color: var(--text-secondary);
  text-decoration: none;
  border-bottom: 1px solid var(--border-light);
  background: none;
  border-left: none;
  border-right: none;
  border-top: none;
  width: 100%;
  cursor: pointer;
  font-family: var(--font-main);
  transition: background var(--transition-fast);
}

.dropdown-item:last-child { border-bottom: none; }
.dropdown-item:hover { background: var(--bg-page); text-decoration: none; }
.dropdown-item svg { width: 15px; height: 15px; flex-shrink: 0; }

.dropdown-logout { color: var(--danger); }
.dropdown-logout svg { stroke: var(--danger); }

/* Dropdown transition */
.dropdown-enter-active, .dropdown-leave-active { transition: all 0.15s ease; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; transform: translateY(6px); }

/* MAIN AREA */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 100vh;
}

.topbar {
  height: 57px;
  border-bottom: 1px solid var(--border-light);
  background: var(--white);
  display: flex;
  align-items: center;
  padding: 0 28px;
  gap: 12px;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: 10;
}

.content-area {
  flex: 1;
  padding: 24px 28px;
  overflow-y: auto;
}
</style>
