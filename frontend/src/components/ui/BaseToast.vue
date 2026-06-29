<!-- ============================================
   RECURRA — TOAST/NOTIFICATION COMPONENT (4.8)
   /frontend/src/components/ui/BaseToast.vue
   ============================================ -->

<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  message: { type: String, required: true },
  type: {
    type: String,
    default: 'info',
    validator: (v) => ['success', 'error', 'warning', 'info'].includes(v),
  },
  duration: { type: Number, default: 4000 },
  id: { type: [String, Number], required: true },
})

const emit = defineEmits(['dismiss'])
const visible = ref(true)
const progress = ref(100)

onMounted(() => {
  if (props.duration > 0) {
    const interval = setInterval(() => {
      progress.value -= (100 / (props.duration / 100))
      if (progress.value <= 0) {
        clearInterval(interval)
        dismiss()
      }
    }, 100)
  }
})

function dismiss() {
  visible.value = false
  setTimeout(() => emit('dismiss', props.id), 300)
}

const icons = {
  success: `<polyline points="20 6 9 17 4 12"/>`,
  error: `<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>`,
  warning: `<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>`,
  info: `<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>`,
}
</script>

<template>
  <Transition name="toast">
    <div v-if="visible" class="toast" :class="`toast-${type}`" role="alert">
      <span class="toast-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" v-html="icons[type]"></svg>
      </span>
      <p class="toast-message">{{ message }}</p>
      <button type="button" class="toast-close" @click="dismiss" aria-label="Dismiss">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
      <!-- Progress bar -->
      <div class="toast-progress" :class="`progress-${type}`" :style="{ width: progress + '%' }"></div>
    </div>
  </Transition>
</template>

<style scoped>
.toast {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px 16px;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  width: 340px;
  overflow: hidden;
  border: 1px solid transparent;
}

.toast-success { background: var(--success-bg); border-color: #BBF7D0; }
.toast-error   { background: var(--danger-bg);  border-color: #FECACA; }
.toast-warning { background: var(--warning-bg); border-color: #FDE68A; }
.toast-info    { background: var(--info-bg);    border-color: #BFDBFE; }

.toast-icon { flex-shrink: 0; display: flex; align-items: center; margin-top: 1px; }
.toast-icon svg { width: 16px; height: 16px; }

.toast-success .toast-icon { color: var(--success); }
.toast-error   .toast-icon { color: var(--danger); }
.toast-warning .toast-icon { color: var(--warning); }
.toast-info    .toast-icon { color: var(--info); }

.toast-message {
  flex: 1;
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
  color: var(--text-primary);
}

.toast-close {
  background: none;
  border: none;
  padding: 1px;
  cursor: pointer;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  flex-shrink: 0;
  margin-top: 1px;
}

.toast-close svg { width: 14px; height: 14px; }
.toast-close:hover { color: var(--text-secondary); }

.toast-progress {
  position: absolute;
  bottom: 0;
  left: 0;
  height: 3px;
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
  transition: width 0.1s linear;
}

.progress-success { background: var(--success); }
.progress-error   { background: var(--danger); }
.progress-warning { background: var(--warning); }
.progress-info    { background: var(--info); }

/* Transition */
.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from { opacity: 0; transform: translateX(100%); }
.toast-leave-to   { opacity: 0; transform: translateX(100%); }
</style>
