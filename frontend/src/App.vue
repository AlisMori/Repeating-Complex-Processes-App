<script setup>
import { RouterView } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()
const { authMessage } = storeToRefs(authStore)
</script>

<template>
  <div v-if="authMessage" class="auth-message-banner" role="alert">
    <p>{{ authMessage }}</p>
    <button type="button" @click="authStore.clearAuthMessage()">Dismiss</button>
  </div>
  <RouterView />
</template>

<style>
html, body {
  height: 100%;
  margin: 0;
  padding: 0;
}

#app {
  min-height: 100vh;
  width: 100%;
}

.auth-message-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 10px 20px;
  background: #EFF6FF;
  border-bottom: 1px solid #BFDBFE;
  font-size: 13px;
  color: #1E40AF;
}

.auth-message-banner p {
  margin: 0;
}

.auth-message-banner button {
  background: none;
  border: 1px solid #BFDBFE;
  border-radius: 6px;
  padding: 3px 10px;
  font-size: 12px;
  color: #1E40AF;
  cursor: pointer;
  font-family: 'Inter', sans-serif;
  flex-shrink: 0;
}
</style>
