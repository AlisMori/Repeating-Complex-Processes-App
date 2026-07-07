<!-- ============================================
   RECURRA — BASE SELECT COMPONENT (4.3)
   /frontend/src/components/ui/BaseSelect.vue

   Same visual language and prop contract as BaseInput
   (label / error / hint / required / disabled) so dropdowns
   never have to be re-styled by hand in a view again.

   Usage — pass native <option> elements into the default slot,
   exactly like a plain <select>:

     <BaseSelect v-model="status" label="Status">
       <option value="pending">Pending</option>
       <option value="completed">Completed</option>
     </BaseSelect>

   v-model is forwarded straight onto the underlying <select>,
   so non-string bound values (null, numbers, etc. via
   :value="..." on <option>) work exactly as they would on a
   plain native <select v-model="...">.
   ============================================ -->

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: null, default: '' },
  label: { type: String, default: '' },
  error: { type: String, default: '' },
  hint: { type: String, default: '' },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  id: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const inner = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const selectId = computed(() => props.id || `select-${Math.random().toString(36).slice(2, 7)}`)
</script>

<template>
  <div class="base-select-group">
    <!-- Label -->
    <label v-if="label" :for="selectId" class="select-label">
      {{ label }}
      <span v-if="required" class="required-star">*</span>
    </label>

    <!-- Select wrapper -->
    <div class="select-wrapper" :class="{ 'has-error': error, 'is-disabled': disabled }">
      <select
        :id="selectId"
        v-model="inner"
        class="base-select"
        :disabled="disabled"
        :required="required"
      >
        <slot />
      </select>

      <svg class="select-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </div>

    <!-- Error message -->
    <p v-if="error" class="select-error" role="alert">{{ error }}</p>

    <!-- Hint -->
    <p v-else-if="hint" class="select-hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.base-select-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.select-label {
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

.select-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.base-select {
  width: 100%;
  height: 44px;
  padding: 0 34px 0 13px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: var(--font-body);
  font-family: var(--font-main);
  background: #FAFAFA;
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast), background var(--transition-fast);
}

.base-select:focus {
  border-color: var(--violet);
  background: var(--white);
  box-shadow: 0 0 0 3px rgba(124,58,237,0.1);
}

/* Error state */
.has-error .base-select {
  border-color: var(--danger);
}

.has-error .base-select:focus {
  box-shadow: 0 0 0 3px rgba(239,68,68,0.1);
}

/* Disabled state */
.is-disabled .base-select {
  opacity: 0.6;
  cursor: not-allowed;
  background: var(--border-light);
}

/* Chevron */
.select-chevron {
  position: absolute;
  right: 11px;
  width: 15px;
  height: 15px;
  color: var(--text-muted);
  pointer-events: none;
}

/* Messages */
.select-error {
  font-size: var(--font-hint);
  color: var(--danger);
  margin: 0;
}

.select-hint {
  font-size: var(--font-hint);
  color: var(--text-muted);
  margin: 0;
}
</style>
