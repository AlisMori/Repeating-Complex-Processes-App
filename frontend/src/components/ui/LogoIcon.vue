<!-- ============================================
   RECURRA — LOGO ICON COMPONENT
   /frontend/src/components/ui/LogoIcon.vue
   ============================================ -->

<script setup>
defineProps({
  size: { type: Number, default: 32 },
  showText: { type: Boolean, default: true },
})
</script>

<template>
  <div class="logo-area">
    <div class="logo-icon" :style="{ width: size + 'px', height: size + 'px' }">
      <svg
        :width="size * 0.82"
        :height="size * 0.82"
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M19.4631 18.5292C19.3849 16.1305 21.7053 13.6535 24.1562 15.1743C26.6071 16.6952 26.7637 21.4926 23.6437 23.9957C20.5237 26.4989 14.9006 25.882 12.3714 21.9624C9.84216 18.0428 11.2325 11.594 15.9517 9.03872C20.6708 6.4834 27.9453 8.64723 30.5267 14.166C33.1081 19.6847 30.9704 27.7587 24.6521 30.3662C18.3338 32.9737 10.2336 30.0364 7.60003 22.9186"
          stroke="white"
          stroke-width="3"
          stroke-linecap="round"
        />
      </svg>
    </div>
    <span v-if="showText" class="logo-text">Recurra</span>
  </div>
</template>

<style scoped>
.logo-area {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-icon {
  background: var(--violet);
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.logo-text {
  font-size: 17px;
  font-weight: 600;
  color: #4C1D95;
  letter-spacing: -0.3px;
}
</style>