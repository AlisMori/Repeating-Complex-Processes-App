import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import AuthHomeView from '../views/AuthHomeView.vue'
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
import AccountSettingsView from '../views/AccountSettingsView.vue'
import { useAuthStore } from '../stores/auth'
import pinia from '../stores'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/about',
      name: 'about',
      // route level code-splitting
      // this generates a separate chunk (About.[hash].js) for this route
      // which is lazy-loaded when the route is visited.
      component: () => import('../views/AboutView.vue'),
    },
    {
      path: '/auth',
      name: 'auth-home',
      component: AuthHomeView,
      meta: { guestOnly: true },
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
      path: '/auth/password-reset/confirm',
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
      path: '/templates/new',
      name: 'template-create',
      component: TemplateCreateView,
      meta: { requiresAuth: true },
    },
    {
      path: '/templates/:id',
      name: 'template-detail',
      component: TemplateCreateView,
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