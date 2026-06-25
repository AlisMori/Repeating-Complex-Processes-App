<script setup>
import { RouterLink, RouterView } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()
const { authMessage, isAuthenticated, user } = storeToRefs(authStore)
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div>
        <h1>Authentication Test App</h1>
        <p>Temporary Vue frontend for validating the Django REST auth flow in the browser.</p>
      </div>

      <div class="session-summary">
        <div><strong>Authenticated:</strong> {{ isAuthenticated ? 'Yes' : 'No' }}</div>
        <div><strong>User:</strong> {{ user?.username || 'None' }}</div>
      </div>

      <nav>
        <RouterLink to="/">Home</RouterLink>
        <RouterLink v-if="!isAuthenticated" to="/auth/login">Login</RouterLink>
        <RouterLink v-if="!isAuthenticated" to="/auth/register">Register</RouterLink>
        <RouterLink v-if="!isAuthenticated" to="/auth/password-reset">Forgot Password</RouterLink>
        <RouterLink v-if="isAuthenticated" to="/dashboard">Dashboard</RouterLink>
      </nav>
    </header>

    <div v-if="authMessage" class="message info">
      <p>{{ authMessage }}</p>
      <button type="button" @click="authStore.clearAuthMessage()">Dismiss</button>
    </div>

    <RouterView />
  </div>
</template>

<style scoped>
.app-shell {
  max-width: 960px;
  margin: 0 auto;
  padding: 1.5rem;
}

.app-header {
  display: grid;
  gap: 1rem;
  margin-bottom: 2rem;
}

nav {
  width: 100%;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}

nav a.router-link-exact-active {
  color: var(--color-text);
  font-weight: 600;
}

nav a.router-link-exact-active:hover {
  background-color: transparent;
}

nav a {
  display: inline-block;
}

.session-summary {
  display: grid;
  gap: 0.25rem;
}

.message {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.75rem 1rem;
  border: 1px solid #bfd2e8;
  background: #eef5fc;
  margin-bottom: 1.5rem;
}
</style>
