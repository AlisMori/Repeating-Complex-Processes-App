<!-- ============================================
   RECURRA — TOAST CONTAINER (4.8)
   /frontend/src/components/ui/ToastContainer.vue
   Usage: Place once in App.vue
   Then use: useToast().show('message', 'success')
   ============================================ -->

<script setup>
import { useToastStore } from '@/stores/toast'
import BaseToast from './BaseToast.vue'

const toastStore = useToastStore()
</script>

<template>
  <div class="toast-container">
    <BaseToast
      v-for="toast in toastStore.toasts"
      :key="toast.id"
      :id="toast.id"
      :message="toast.message"
      :type="toast.type"
      :duration="toast.duration"
      @dismiss="toastStore.remove"
    />
  </div>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
}

.toast-container > * {
  pointer-events: all;
}
</style>
