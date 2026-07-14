<!-- ============================================
   RECURRA — BASE MODAL COMPONENT (4.4)
   /frontend/src/components/ui/BaseModal.vue
   ============================================ -->

<script setup>
import { onMounted, onUnmounted } from 'vue'
import BaseButton from './BaseButton.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  size: {
    type: String,
    default: 'md',
    validator: (v) => ['sm', 'md', 'lg'].includes(v),
  },
  closable: { type: Boolean, default: true },
  confirmLabel: { type: String, default: 'Confirm' },
  confirmDisabled: { type: Boolean, default: false },
  cancelLabel: { type: String, default: 'Cancel' },
  confirmVariant: { type: String, default: 'primary' },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

function close() {
  if (props.closable) emit('update:modelValue', false)
}

function confirm() {
  emit('confirm')
}

function cancel() {
  emit('update:modelValue', false)
  emit('cancel')
}

function onKeydown(e) {
  if (e.key === 'Escape' && props.closable) close()
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="modelValue" class="modal-overlay" @click.self="close">
        <div class="modal-container" :class="`modal-${size}`" role="dialog" aria-modal="true">

          <!-- HEADER -->
          <div class="modal-header">
            <h3 class="modal-title">{{ title }}</h3>
            <button v-if="closable" type="button" class="modal-close-btn" @click="close" aria-label="Close">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>

          <!-- BODY -->
          <div class="modal-body">
            <slot />
          </div>

          <!-- FOOTER -->
          <div v-if="$slots.footer || confirmLabel" class="modal-footer">
            <slot name="footer">
              <BaseButton variant="secondary" @click="cancel">{{ cancelLabel }}</BaseButton>
              <BaseButton :variant="confirmVariant" :loading="loading" :disabled="confirmDisabled" @click="confirm">{{ confirmLabel }}</BaseButton>
            </slot>
          </div>

        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-container {
  background: var(--white);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  width: 100%;
  overflow: hidden;
}

.modal-sm { max-width: 400px; }
.modal-md { max-width: 520px; }
.modal-lg { max-width: 720px; }

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px 16px;
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.modal-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.2px;
}

.modal-close-btn {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
  background: var(--white);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-muted);
  flex-shrink: 0;
  transition: background var(--transition-fast);
}

.modal-close-btn:hover { background: var(--bg-page); }
.modal-close-btn svg { width: 14px; height: 14px; }

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 18px 22px;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 22px;
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

/* Transition */
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.modal-enter-from .modal-container { transform: scale(0.96) translateY(8px); opacity: 0; }
.modal-leave-to .modal-container { transform: scale(0.96) translateY(8px); opacity: 0; }
</style>
