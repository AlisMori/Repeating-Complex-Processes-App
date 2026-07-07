<!-- ============================================
   RECURRA — BASE DATE PICKER COMPONENT (4.3)
   /frontend/src/components/ui/BaseDatePicker.vue

   Native <input type="date"> wrapped in the same visual
   language as BaseInput (label / error / hint / required /
   disabled), so every date field in the app looks and behaves
   identically instead of being re-styled by hand per view.

   Days are the app's atomic time unit end-to-end (see R&A),
   so this always binds/emits plain "YYYY-MM-DD" strings —
   exactly what a native date input already produces.
   ============================================ -->

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '' },
  error: { type: String, default: '' },
  hint: { type: String, default: '' },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  id: { type: String, default: '' },
  min: { type: String, default: undefined },
  max: { type: String, default: undefined },
})

const emit = defineEmits(['update:modelValue'])

const inputId = computed(() => props.id || `date-${Math.random().toString(36).slice(2, 7)}`)
</script>

<template>
  <div class="base-date-group">
    <!-- Label -->
    <label v-if="label" :for="inputId" class="date-label">
      {{ label }}
      <span v-if="required" class="required-star">*</span>
    </label>

    <!-- Input wrapper -->
    <div class="date-wrapper" :class="{ 'has-error': error, 'is-disabled': disabled }">
      <input
        :id="inputId"
        class="base-date"
        type="date"
        :value="modelValue"
        :required="required"
        :disabled="disabled"
        :min="min"
        :max="max"
        @input="emit('update:modelValue', $event.target.value)"
      />
    </div>

    <!-- Error message -->
    <p v-if="error" class="date-error" role="alert">{{ error }}</p>

    <!-- Hint -->
    <p v-else-if="hint" class="date-hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.base-date-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.date-label {
  font-size: var(--font-label);
  font-weight: 500;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 4px;
}

.required-star {
  color: var(--danger);
  font-size: var(--font-label);
  line-height: 1;
}

.date-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.base-date {
  width: 100%;
  height: 44px;
  padding: 0 13px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: var(--font-body);
  font-family: var(--font-main);
  background: #FAFAFA;
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast), background var(--transition-fast);
}

.base-date::-webkit-calendar-picker-indicator {
  cursor: pointer;
  opacity: 0.6;
}

.base-date:focus {
  border-color: var(--violet);
  background: var(--white);
  box-shadow: 0 0 0 3px rgba(124,58,237,0.1);
}

/* Error state */
.has-error .base-date {
  border-color: var(--danger);
}

.has-error .base-date:focus {
  box-shadow: 0 0 0 3px rgba(239,68,68,0.1);
}

/* Disabled state */
.is-disabled .base-date {
  opacity: 0.6;
  cursor: not-allowed;
  background: var(--border-light);
}

/* Messages */
.date-error {
  font-size: var(--font-hint);
  color: var(--danger);
  margin: 0;
}

.date-hint {
  font-size: var(--font-hint);
  color: var(--text-muted);
  margin: 0;
}
</style>
