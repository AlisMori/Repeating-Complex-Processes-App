import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'

const authApiMocks = vi.hoisted(() => ({
  getShareNotifications: vi.fn(),
  markShareNotificationsRead: vi.fn(),
}))

const pushMock = vi.fn()

vi.mock('@/api/auth', () => ({
  getShareNotifications: authApiMocks.getShareNotifications,
  markShareNotificationsRead: authApiMocks.markShareNotificationsRead,
}))

vi.mock('vue-router', () => ({
  RouterLink: {
    props: ['to'],
    template: '<a><slot /></a>',
  },
  useRouter: () => ({
    push: pushMock,
  }),
}))

async function flushPromises() {
  await Promise.resolve()
  await nextTick()
}

function mountLayout() {
  return mount(AppLayout, {
    slots: {
      default: '<div>Page content</div>',
      topbar: '<div>Topbar</div>',
    },
    global: {
      stubs: {
        LogoIcon: { template: '<div class="logo-stub" />' },
        OnboardingTour: { template: '<div class="tour-stub" />' },
        BaseButton: {
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
        BaseModal: {
          props: ['modelValue', 'title'],
          emits: ['update:modelValue', 'cancel'],
          template: `
            <div v-if="modelValue" class="modal-stub">
              <div class="modal-title">{{ title }}</div>
              <slot />
              <slot name="footer" />
            </div>
          `,
        },
      },
    },
  })
}

describe('AppLayout share notifications', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    const authStore = useAuthStore()
    authStore.setSession({
      access: 'access-token',
      refresh: 'refresh-token',
      user: {
        username: 'alice',
        email: 'alice@example.com',
      },
    })
    authApiMocks.getShareNotifications.mockResolvedValue({
      data: [
        {
          notification_id: 1,
          sender_username: 'bob',
          template_name: 'Hiring Plan',
          created_at: '2026-07-20T09:30:00Z',
        },
        {
          notification_id: 2,
          sender_username: 'carol',
          template_name: 'Launch Checklist',
          created_at: '2026-07-20T10:00:00Z',
        },
      ],
    })
    authApiMocks.markShareNotificationsRead.mockResolvedValue({ data: { updated: 2 } })
  })

  it('opens a popup with unread shared-template notifications and acknowledges them', async () => {
    const wrapper = mountLayout()
    await flushPromises()

    expect(authApiMocks.getShareNotifications).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Templates Shared With You')
    expect(wrapper.text()).toContain('bob shared Hiring Plan')
    expect(wrapper.text()).toContain('carol shared Launch Checklist')

    await wrapper.find('.modal-stub button').trigger('click')
    await flushPromises()

    expect(authApiMocks.markShareNotificationsRead).toHaveBeenCalledWith([1, 2])
    expect(useNotificationStore().shareNotifications).toEqual([])
  })
})
