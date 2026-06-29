<!-- ============================================
   RECURRA — BASE BUTTON COMPONENT (4.2)
   /frontend/src/components/ui/BaseButton.vue
   ============================================ -->

<script setup>
defineProps({
  variant: {
    type: String,
    default: 'primary',
    validator: (v) => ['primary', 'secondary', 'danger', 'ghost'].includes(v),
  },
  size: {
    type: String,
    default: 'md',
    validator: (v) => ['sm', 'md', 'lg'].includes(v),
  },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  fullWidth: { type: Boolean, default: false },
  type: { type: String, default: 'button' },
})
</script>

<template>
  <button
    :type="type"
    class="base-btn"
    :class="[`btn-${variant}`, `btn-${size}`, { 'btn-full': fullWidth, 'btn-loading': loading }]"
    :disabled="disabled || loading"
  >
    <!-- Loading spinner -->
    <svg v-if="loading" class="btn-spinner" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-dasharray="32" stroke-dashoffset="8" stroke-linecap="round"/>
    </svg>
    <slot />
  </button>
</template>

<style scoped>
.base-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-family: var(--font-main);
  font-weight: 500;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast), opacity var(--transition-fast), transform 0.1s;
  white-space: nowrap;
  flex-shrink: 0;
}

.base-btn:active:not(:disabled) { transform: scale(0.98); }
.base-btn:disabled { opacity: 0.55; cursor: not-allowed; }

/* SIZES */
.btn-sm { height: 32px; padding: 0 12px; font-size: 12.5px; }
.btn-md { height: 40px; padding: 0 16px; font-size: 13.5px; }
.btn-lg { height: 46px; padding: 0 20px; font-size: 14.5px; }

/* FULL WIDTH */
.btn-full { width: 100%; }

/* VARIANTS */
.btn-primary {
  background: var(--violet);
  color: #fff;
}
.btn-primary:hover:not(:disabled) { background: var(--violet-dark); }

.btn-secondary {
  background: var(--white);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}
.btn-secondary:hover:not(:disabled) { background: var(--bg-page); border-color: #94A3B8; }

.btn-danger {
  background: var(--white);
  color: var(--danger);
  border: 1px solid #FECACA;
}
.btn-danger:hover:not(:disabled) { background: var(--danger-bg); }

.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
}
.btn-ghost:hover:not(:disabled) { background: var(--bg-page); }

/* SPINNER */
.btn-spinner {
  width: 15px;
  height: 15px;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
