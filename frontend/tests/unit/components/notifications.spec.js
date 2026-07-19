import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import BaseToast from '@/components/ui/BaseToast.vue'
import ToastContainer from '@/components/ui/ToastContainer.vue'
import { useToastStore } from '@/stores/toast'

describe('toast store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('success() adds a toast with type "success"', () => {
    const store = useToastStore()
    store.success('Saved successfully')
    expect(store.toasts.length).toBe(1)
    expect(store.toasts[0].type).toBe('success')
    expect(store.toasts[0].message).toBe('Saved successfully')
  })

  it('error() adds a toast with type "error"', () => {
    const store = useToastStore()
    store.error('Something went wrong')
    expect(store.toasts[0].type).toBe('error')
  })

  it('warning() adds a toast with type "warning" (validation feedback)', () => {
    const store = useToastStore()
    store.warning('Please check the highlighted fields')
    expect(store.toasts[0].type).toBe('warning')
  })

  it('remove() removes the toast with the matching id', () => {
    const store = useToastStore()
    const id = store.success('Saved')
    expect(store.toasts.length).toBe(1)
    store.remove(id)
    expect(store.toasts.length).toBe(0)
  })
})

describe('BaseToast', () => {
  it('renders the success variant with the correct class and message', () => {
    const wrapper = mount(BaseToast, { props: { id: 1, message: 'Saved successfully', type: 'success' } })
    expect(wrapper.find('.toast').classes()).toContain('toast-success')
    expect(wrapper.find('.toast-message').text()).toBe('Saved successfully')
  })

  it('renders the error variant with the correct class and message', () => {
    const wrapper = mount(BaseToast, { props: { id: 2, message: 'Something went wrong', type: 'error' } })
    expect(wrapper.find('.toast').classes()).toContain('toast-error')
    expect(wrapper.find('.toast-message').text()).toBe('Something went wrong')
  })

  it('renders the warning variant with the correct class and message (validation feedback)', () => {
    const wrapper = mount(BaseToast, { props: { id: 3, message: 'Check the form', type: 'warning' } })
    expect(wrapper.find('.toast').classes()).toContain('toast-warning')
    expect(wrapper.find('.toast-message').text()).toBe('Check the form')
  })

  it('defaults to the info variant when no type is given', () => {
    const wrapper = mount(BaseToast, { props: { id: 4, message: 'FYI' } })
    expect(wrapper.find('.toast').classes()).toContain('toast-info')
  })

  it('emits dismiss with its id when the close button is clicked', async () => {
    const wrapper = mount(BaseToast, { props: { id: 42, message: 'Bye', type: 'info', duration: 0 } })
    await wrapper.find('.toast-close').trigger('click')
    await new Promise((r) => setTimeout(r, 310)) // dismiss() waits 300ms before emitting
    expect(wrapper.emitted('dismiss')).toBeTruthy()
    expect(wrapper.emitted('dismiss')[0]).toEqual([42])
  })
})

describe('ToastContainer', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders one BaseToast per toast in the store, with correct variants', () => {
    const store = useToastStore()
    store.success('Saved')
    store.error('Failed')
    const wrapper = mount(ToastContainer)
    const toasts = wrapper.findAll('.toast')
    expect(toasts.length).toBe(2)
    expect(toasts[0].classes()).toContain('toast-success')
    expect(toasts[1].classes()).toContain('toast-error')
  })

  it('renders nothing when there are no toasts', () => {
    const wrapper = mount(ToastContainer)
    expect(wrapper.findAll('.toast').length).toBe(0)
  })
})
