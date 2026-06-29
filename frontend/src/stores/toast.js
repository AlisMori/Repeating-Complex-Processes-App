// ============================================
//   RECURRA — TOAST STORE
//   /frontend/src/stores/toast.js
// ============================================

import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useToastStore = defineStore('toast', () => {
  const toasts = ref([])

  function show(message, type = 'info', duration = 4000) {
    const id = Date.now() + Math.random()
    toasts.value.push({ id, message, type, duration })
    return id
  }

  function remove(id) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  function success(message, duration) { return show(message, 'success', duration) }
  function error(message, duration)   { return show(message, 'error', duration) }
  function warning(message, duration) { return show(message, 'warning', duration) }
  function info(message, duration)    { return show(message, 'info', duration) }

  return { toasts, show, remove, success, error, warning, info }
})
