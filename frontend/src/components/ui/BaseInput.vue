<!-- ============================================
   RECURRA — BASE INPUT COMPONENT (4.3)
   /frontend/src/components/ui/BaseInput.vue
   ============================================ -->

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  type: { type: String, default: 'text' },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  error: { type: String, default: '' },
  hint: { type: String, default: '' },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  autocomplete: { type: String, default: 'off' },
  id: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const showPassword = ref(false)

const inputType = computed(() => {
  if (props.type === 'password') {
    return showPassword.value ? 'text' : 'password'
  }
  return props.type
})

const inputId = computed(() => props.id || `input-${Math.random().toString(36).slice(2, 7)}`)
</script>

<template>
  <div class="base-input-group">
    <!-- Label -->
    <label v-if="label" :for="inputId" class="input-label">
      {{ label }}
      <span v-if="required" class="required-star">*</span>
    </label>

    <!-- Input wrapper -->
    <div class="input-wrapper" :class="{ 'has-error': error, 'is-disabled': disabled }">

      <!-- Left slot (icon) -->
      <span v-if="$slots.icon" class="input-icon-left">
        <slot name="icon" />
      </span>

      <input
        :id="inputId"
        class="base-input"
        :class="{ 'has-left-icon': $slots.icon, 'has-right-icon': type === 'password' || $slots.suffix }"
        :type="inputType"
        :value="modelValue"
        :placeholder="placeholder"
        :required="required"
        :disabled="disabled"
        :autocomplete="autocomplete"
        @input="emit('update:modelValue', $event.target.value)"
      />

      <!-- Password toggle -->
      <button
        v-if="type === 'password'"
        type="button"
        class="input-icon-right input-icon-btn"
        @click="showPassword = !showPassword"
        :aria-label="showPassword ? 'Hide password' : 'Show password'"
      >
        <svg v-if="!showPassword" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>
        </svg>
      </button>

      <!-- Right slot (suffix icon) -->
      <span v-else-if="$slots.suffix" class="input-icon-right">
        <slot name="suffix" />
      </span>

    </div>

    <!-- Error message -->
    <p v-if="error" class="input-error" role="alert">{{ error }}</p>

    <!-- Hint -->
    <p v-else-if="hint" class="input-hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.base-input-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.input-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 4px;
}

.required-star {
  color: var(--danger);
  font-size: 14px;
  line-height: 1;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.base-input {
  width: 100%;
  height: 42px;
  padding: 0 13px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-family: var(--font-main);
  background: #FAFAFA;
  color: var(--text-primary);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast), background var(--transition-fast);
}

.base-input::placeholder { color: var(--text-muted); }

.base-input:focus {
  border-color: var(--violet);
  background: var(--white);
  box-shadow: 0 0 0 3px rgba(124,58,237,0.1);
}

.base-input.has-left-icon { padding-left: 38px; }
.base-input.has-right-icon { padding-right: 38px; }

/* Error state */
.has-error .base-input {
  border-color: var(--danger);
}

.has-error .base-input:focus {
  box-shadow: 0 0 0 3px rgba(239,68,68,0.1);
}

/* Disabled state */
.is-disabled .base-input {
  opacity: 0.6;
  cursor: not-allowed;
  background: var(--border-light);
}

/* Icons */
.input-icon-left {
  position: absolute;
  left: 11px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  pointer-events: none;
}

.input-icon-left :deep(svg) { width: 16px; height: 16px; }

.input-icon-right {
  position: absolute;
  right: 11px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
}

.input-icon-right :deep(svg) { width: 16px; height: 16px; }

.input-icon-btn {
  background: none;
  border: none;
  padding: 2px;
  cursor: pointer;
  color: var(--text-muted);
  font-family: var(--font-main);
}

.input-icon-btn:hover { color: var(--text-secondary); }

/* Messages */
.input-error {
  font-size: 12px;
  color: var(--danger);
  margin: 0;
}

.input-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0;
}
</style>
