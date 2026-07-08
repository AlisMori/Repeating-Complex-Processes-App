<!-- ============================================
   RECURRA — AUTH LAYOUT (4.1)
   /frontend/src/layouts/AuthLayout.vue
   Shared shell for Login, Register, Password Reset
   ============================================ -->

<script setup>
import LogoIcon from '@/components/ui/LogoIcon.vue'

defineProps({
  headline: { type: String, default: 'Manage repeating\nprocesses with ease' },
  tagline: { type: String, default: 'Define once, repeat forever. Recurra tracks your complex workflows so you never miss a step.' },
  features: {
    type: Array,
    default: () => [
      'Reusable process templates',
      'Automatic timeline scheduling',
      'Smart task dependency chains',
      'Email reminders and notifications',
    ],
  },
})
</script>

<template>
  <div class="auth-layout">

    <!-- LEFT PANEL — branding -->
    <div class="auth-left">
      <div class="auth-left-inner">

        <!-- Logo -->
        <LogoIcon :size="38" />

        <!-- Brand content -->
        <div class="brand-content">
          <h1 class="brand-headline" v-html="headline.replace('\n', '<br/>')"></h1>
          <p class="brand-tagline">{{ tagline }}</p>
          <ul class="feature-list">
            <li v-for="feature in features" :key="feature" class="feature-item">
              <span class="feature-dot"></span>
              <span>{{ feature }}</span>
            </li>
          </ul>
        </div>

        <!-- Footer -->
        <div class="auth-left-footer">
          <div class="status-badge">
            <span class="status-dot"></span>
            All systems operational
          </div>
          <p class="footer-note">Hosted on Murdoch University infrastructure</p>
        </div>

      </div>
    </div>

    <!-- RIGHT PANEL — form slot -->
    <div class="auth-right">
      <div class="form-card">
        <slot />
      </div>
    </div>

  </div>
</template>

<style scoped>
.auth-layout {
  display: flex;
  width: 100%;
  min-height: 100vh;
}

/* LEFT PANEL */
.auth-left {
  width: 420px;
  flex-shrink: 0;
  background: #F5F3FF;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.auth-left::before {
  content: '';
  position: absolute;
  width: 400px;
  height: 400px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(124,58,237,0.12) 0%, transparent 70%);
  bottom: -80px;
  left: -80px;
  pointer-events: none;
}

.auth-left::after {
  content: '';
  position: absolute;
  width: 250px;
  height: 250px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(124,58,237,0.08) 0%, transparent 70%);
  top: 60px;
  right: -60px;
  pointer-events: none;
}

.auth-left-inner {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
  padding: 48px 48px 40px;
}

.brand-content { margin-top: 52px; }

.brand-headline {
  font-size: 28px;
  font-weight: 600;
  color: #3B0764;
  line-height: 1.3;
  margin: 0 0 12px;
  letter-spacing: -0.4px;
}

.brand-tagline {
  font-size: 16px;
  color: #5B21B6;
  line-height: 1.7;
  opacity: 0.8;
  margin: 0;
}

.feature-list {
  list-style: none;
  margin: 28px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  color: #5B21B6;
}

.feature-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--violet);
  flex-shrink: 0;
}

.auth-left-footer { margin-top: auto; }

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: rgba(34,197,94,0.12);
  color: #15803D;
  font-size: 13px;
  font-weight: 500;
  padding: 4px 11px;
  border-radius: 20px;
  margin-bottom: 8px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22C55E;
}

.footer-note {
  font-size: 12px;
  color: #5B21B6;
  opacity: 0.5;
  margin: 0;
}

/* RIGHT PANEL */
.auth-right {
  flex: 1;
  background: var(--white);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 40px;
}

.form-card {
  width: 100%;
  max-width: 400px;
}
</style>
