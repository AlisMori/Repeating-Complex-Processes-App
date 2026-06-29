// /frontend/src/router/index.js

import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import pinia from '../stores'
import TemplatesView from '../views/TemplatesView.vue'
import TemplateTasksView from '../views/TemplateTasksView.vue'
import TemplateActivitiesView from '../views/TemplateActivitiesView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [

    // ── AUTH ROUTES (guest only) ──────────────────────────────
    {
      path: '/auth/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/auth/register',
      name: 'register',
      component: () => import('../views/RegisterView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/auth/password-reset',
      name: 'forgot-password',
      component: () => import('../views/PasswordResetRequestView.vue'),
    },
    {
      path: '/auth/password-reset/confirm',
      name: 'password-reset-confirm',
      component: () => import('../views/PasswordResetConfirmView.vue'),
    },

    // ── REDIRECT ROOT ─────────────────────────────────────────
    {
      path: '/',
      redirect: { name: 'dashboard' },
    },

    // ── MAIN APP ROUTES (auth required) ──────────────────────
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('../views/DashboardView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/cycles',
      name: 'cycles',
      component: () => import('../views/CyclesListView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/cycles/new',
      name: 'cycle-create',
      component: () => import('../views/CycleCreateView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/cycles/:id',
      name: 'cycle-detail',
      component: () => import('../views/CycleDetailView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/templates',
      name: 'templates',
      component: () => import('../views/TemplateLibraryView.vue'),
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
      path: '/auth/test',
      redirect: { name: 'dashboard' },

      path: '/templates/new',
      name: 'template-create',
      component: () => import('../views/TemplateCreateView.vue'),
      meta: { requiresAuth: true },

    },
    {
      path: '/templates/:id',
      name: 'template-detail',
      component: () => import('../views/TemplateCreateView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/settings',
      name: 'account-settings',
      component: () => import('../views/AccountSettingsView.vue'),
      meta: { requiresAuth: true },
    },

    // ── FALLBACK ──────────────────────────────────────────────
    {
      path: '/:pathMatch(.*)*',
      redirect: { name: 'dashboard' },
    },
  ],
})

router.beforeEach((to) => {
  const authStore = useAuthStore(pinia)

  if (to.meta.requiresAuth) {
    if (!authStore.accessToken) {
      authStore.handleSessionExpired('Please log in to continue.')
      return { name: 'login' }
    }
    if (authStore.isAccessTokenExpired()) {
      authStore.handleSessionExpired()
      return { name: 'login' }
    }
  }

  if (to.meta.guestOnly && authStore.accessToken && !authStore.isAccessTokenExpired()) {
    return { name: 'dashboard' }
  }

  return true
})

export default router
