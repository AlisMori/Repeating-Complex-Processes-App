import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import AccountSettingsView from '@/views/AccountSettingsView.vue'
import { useAuthStore } from '@/stores/auth'

const authApiMocks = vi.hoisted(() => ({
  fetchMe: vi.fn(),
  updateMe: vi.fn(),
  changePassword: vi.fn(),
  deleteAccount: vi.fn(),
}))

vi.mock('@/api/auth', () => ({
  fetchMe: authApiMocks.fetchMe,
  updateMe: authApiMocks.updateMe,
  changePassword: authApiMocks.changePassword,
  deleteAccount: authApiMocks.deleteAccount,
}))

const pushMock = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}))

function deferred() {
  let resolve
  const promise = new Promise((res) => {
    resolve = res
  })
  return { promise, resolve }
}

async function flushPromises() {
  await Promise.resolve()
  await nextTick()
}

function mountView() {
  return mount(AccountSettingsView, {
    global: {
      stubs: {
        AppLayout: {
          template: '<div><slot name="topbar" /><slot /></div>',
        },
        BaseButton: {
          props: ['disabled', 'loading'],
          template: '<button :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>',
        },
        BaseInput: {
          props: ['modelValue', 'type', 'placeholder', 'autocomplete'],
          emits: ['update:modelValue'],
          template: '<input :value="modelValue" :type="type" :placeholder="placeholder" :autocomplete="autocomplete" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseModal: {
          props: ['modelValue', 'title', 'confirmLabel', 'confirmDisabled', 'loading'],
          emits: ['update:modelValue', 'confirm', 'cancel'],
          template: `
            <div v-if="modelValue" class="base-modal-stub">
              <div class="modal-title">{{ title }}</div>
              <slot />
              <button class="modal-cancel" @click="$emit('cancel')">Cancel</button>
              <button class="modal-confirm" :disabled="confirmDisabled || loading" @click="$emit('confirm')">{{ confirmLabel }}</button>
            </div>
          `,
        },
      },
    },
  })
}

describe('AccountSettingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    pushMock.mockReset()
    const authStore = useAuthStore()
    authStore.setSession({
      access: 'access-token',
      refresh: 'refresh-token',
      user: {
        username: 'alice',
        email: 'alice@example.com',
        first_name: '',
        last_name: '',
        notification_opt_in: true,
      },
    })
    authApiMocks.fetchMe.mockResolvedValue({
      data: {
        username: 'alice',
        email: 'loaded@example.com',
        first_name: 'Loaded',
        last_name: 'User',
        notification_opt_in: false,
      },
    })
    authApiMocks.updateMe.mockResolvedValue({
      data: {
        username: 'alice',
        email: 'loaded@example.com',
        first_name: 'Loaded',
        last_name: 'User',
        notification_opt_in: false,
      },
    })
    authApiMocks.changePassword.mockResolvedValue({ data: { message: 'Password updated successfully.' } })
    authApiMocks.deleteAccount.mockResolvedValue({ data: { message: 'Account deleted successfully.' } })
  })

  it('loads authenticated settings on mount', async () => {
    const wrapper = mountView()
    await flushPromises()
    const notificationsTab = wrapper.findAll('.settings-nav-item').find((item) => item.text() === 'Notifications')
    await notificationsTab.trigger('click')

    expect(authApiMocks.fetchMe).toHaveBeenCalledTimes(1)
    expect(useAuthStore().user.email).toBe('loaded@example.com')
    expect(wrapper.find('input[type="checkbox"]').element.checked).toBe(false)
  })

  it('saves profile changes through the backend', async () => {
    const wrapper = mountView()
    await flushPromises()

    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('Alice')
    await inputs[1].setValue('Ng')
    await inputs[2].setValue('alice.ng@example.com')

    const saveButtons = wrapper.findAll('button').filter((button) => button.text() === 'Save changes')
    await saveButtons[0].trigger('click')

    expect(authApiMocks.updateMe).toHaveBeenCalledWith({
      first_name: 'Alice',
      last_name: 'Ng',
      email: 'alice.ng@example.com',
    })
  })

  it('does not duplicate profile submissions while a save is in flight', async () => {
    const pending = deferred()
    authApiMocks.updateMe.mockReturnValueOnce(pending.promise)
    const wrapper = mountView()
    await flushPromises()

    const saveButton = wrapper.findAll('button').find((button) => button.text() === 'Save changes')
    await saveButton.trigger('click')
    await saveButton.trigger('click')

    expect(authApiMocks.updateMe).toHaveBeenCalledTimes(1)

    pending.resolve({
      data: {
        username: 'alice',
        email: 'loaded@example.com',
        first_name: 'Loaded',
        last_name: 'User',
        notification_opt_in: false,
      },
    })
    await flushPromises()
  })

  it('shows delete-account controls and keeps unsupported session-timeout hidden', async () => {
    const wrapper = mountView()
    await flushPromises()

    const securityTab = wrapper.findAll('.settings-nav-item').find((item) => item.text() === 'Security')
    await securityTab.trigger('click')

    expect(wrapper.text()).toContain('Delete account')
    expect(wrapper.text()).not.toContain('Session timeout')
  })

  it('requires one acknowledgement plus DELETE before deleting the account', async () => {
    const wrapper = mountView()
    await flushPromises()

    const securityTab = wrapper.findAll('.settings-nav-item').find((item) => item.text() === 'Security')
    await securityTab.trigger('click')
    const deleteButton = wrapper.findAll('button').find((button) => button.text() === 'Delete account')
    await deleteButton.trigger('click')

    const confirmButton = wrapper.find('.modal-confirm')
    expect(confirmButton.attributes('disabled')).toBeDefined()

    const modalInputs = wrapper.findAll('.base-modal-stub input')
    await modalInputs[0].setChecked()
    await modalInputs[1].setValue('DELETE')

    expect(wrapper.find('.modal-confirm').attributes('disabled')).toBeUndefined()
    await wrapper.find('.modal-confirm').trigger('click')

    expect(authApiMocks.deleteAccount).toHaveBeenCalledWith({
      confirmation_text: 'DELETE',
    })
    expect(pushMock).toHaveBeenCalledWith({ name: 'login' })
  })
})
