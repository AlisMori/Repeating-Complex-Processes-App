import { createRouter, createWebHistory } from 'vue-router'
import { ensureValidAccessToken } from '../api/axios'
import DashboardView from '../views/DashboardView.vue'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import PasswordResetRequestView from '../views/PasswordResetRequestView.vue'
import PasswordResetConfirmView from '../views/PasswordResetConfirmView.vue'
import CyclesListView from '../views/CyclesListView.vue'
import CycleCreateView from '../views/CycleCreateView.vue'
import CycleDetailView from '../views/CycleDetailView.vue'
import TemplateLibraryView from '../views/TemplateLibraryView.vue'
import TemplateCreateView from '../views/TemplateCreateView.vue'
import TemplateDetailView from '../views/TemplateDetailView.vue'
import AccountSettingsView from '../views/AccountSettingsView.vue'
import { useAuthStore } from '../stores/auth'
import pinia from '../stores'
import TemplateTasksView from '../views/TemplateTasksView.vue'
import TemplateActivitiesView from '../views/TemplateActivitiesView.vue'
import TagsView from '../views/TagsView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      // No public landing page — send straight into the app.
      // The router guard below bounces unauthenticated users on
      // to /auth/login automatically.
      path: '/',
      redirect: { name: 'login' },
    },
    {
      path: '/auth',
      redirect: { name: 'login' },
    },
    {
      path: '/auth/register',
      name: 'register',
      component: RegisterView,
      meta: { guestOnly: true },
    },
    {
      path: '/auth/login',
      name: 'login',
      component: LoginView,
      meta: { guestOnly: true },
    },
    {
      path: '/auth/password-reset',
      name: 'forgot-password',
      component: PasswordResetRequestView,
    },
    {
      path: '/auth/password-reset/confirm/:uid/:token',
      name: 'password-reset-confirm',
      component: PasswordResetConfirmView,
    },
    {
      path: '/auth/test',
      redirect: { name: 'dashboard' },
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardView,
      meta: { requiresAuth: true },
    },
    {
      path: '/cycles',
      name: 'cycles',
      component: CyclesListView,
      meta: { requiresAuth: true },
    },
    {
      path: '/cycles/new',
      name: 'cycle-create',
      component: CycleCreateView,
      meta: { requiresAuth: true },
    },
    {
      path: '/cycles/:id',
      name: 'cycle-detail',
      component: CycleDetailView,
      meta: { requiresAuth: true },
    },
    {
      path: '/templates',
      name: 'templates',
      component: TemplateLibraryView,
      meta: { requiresAuth: true },
    },
    {
      path: '/template-tasks',
      name: 'template-tasks',
      component: TemplateTasksView,
      meta: { requiresAuth: true },
    },
    {
      path: '/template-activities',
      name: 'template-activities',
      component: TemplateActivitiesView,
      meta: { requiresAuth: true },
    },
    {
      path: '/templates/new',
      name: 'template-create',
      component: TemplateCreateView,
      meta: { requiresAuth: true },
    },
    {
      path: '/templates/:id',
      name: 'template-detail',
      component: TemplateDetailView,
      meta: { requiresAuth: true },
    },
    {
      path: '/templates/:id/edit',
      name: 'template-edit',
      component: TemplateCreateView,
      meta: { requiresAuth: true },
    },
    {
      path: '/tags',
      name: 'tags',
      component: TagsView,
      meta: { requiresAuth: true },
    },
    {
      path: '/settings',
      name: 'account-settings',
      component: AccountSettingsView,
      meta: { requiresAuth: true },
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: { name: 'dashboard' },
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore(pinia)

  if (to.meta.requiresAuth) {
    if (!authStore.refreshToken && !authStore.accessToken) {
      authStore.handleSessionExpired('Please log in to continue.')
      return { name: 'login' }
    }

    if (authStore.isAccessTokenExpired()) {
      try {
        await ensureValidAccessToken()
      } catch {
        return { name: 'login' }
      }
    }
  }

  if (to.meta.guestOnly && authStore.refreshToken) {
    return { name: 'dashboard' }
  }

  return true
})

export default router
