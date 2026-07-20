import { describe, it, expect, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseModal from '@/components/ui/BaseModal.vue'

// BaseModal uses <Teleport to="body">, so the rendered dialog is not
// inside wrapper.element. Query document.body instead.
let wrapper

afterEach(() => {
  if (wrapper) {
    wrapper.unmount()
    wrapper = null
  }
})

describe('BaseModal', () => {
  it('does not render the dialog when closed', () => {
    wrapper = mount(BaseModal, { props: { modelValue: false, title: 'Test' } })
    expect(document.body.querySelector('.modal-overlay')).toBeNull()
  })

  it('renders the dialog when open', () => {
    wrapper = mount(BaseModal, { props: { modelValue: true, title: 'Delete template?' } })
    const overlay = document.body.querySelector('.modal-overlay')
    expect(overlay).not.toBeNull()
    expect(document.body.querySelector('.modal-title').textContent).toBe('Delete template?')
  })

  it('emits confirm when the confirm button is clicked (destructive action)', async () => {
    wrapper = mount(BaseModal, {
      props: {
        modelValue: true,
        title: 'Delete template?',
        confirmLabel: 'Delete',
        confirmVariant: 'danger',
      },
    })
    const buttons = document.body.querySelectorAll('.modal-footer button')
    const deleteBtn = Array.from(buttons).find((button) => button.textContent.trim() === 'Delete')
    expect(deleteBtn).toBeTruthy()
    deleteBtn.dispatchEvent(new Event('click'))
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('confirm')).toBeTruthy()
    expect(wrapper.emitted('confirm').length).toBe(1)
  })

  it('emits cancel and closes (update:modelValue false) when cancel is clicked', async () => {
    wrapper = mount(BaseModal, {
      props: { modelValue: true, title: 'Delete template?' },
    })
    const buttons = document.body.querySelectorAll('.modal-footer button')
    const cancelBtn = Array.from(buttons).find((button) => button.textContent.trim() === 'Cancel')
    expect(cancelBtn).toBeTruthy()
    cancelBtn.dispatchEvent(new Event('click'))
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('cancel')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([false])
  })

  it('closes without confirming when the close (X) button is clicked', async () => {
    wrapper = mount(BaseModal, {
      props: { modelValue: true, title: 'Delete template?', closable: true },
    })
    const closeBtn = document.body.querySelector('.modal-close-btn')
    expect(closeBtn).toBeTruthy()
    closeBtn.dispatchEvent(new Event('click'))
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([false])
    expect(wrapper.emitted('confirm')).toBeUndefined()
  })

  it('does not close when closable is false and the overlay is clicked', async () => {
    wrapper = mount(BaseModal, {
      props: { modelValue: true, title: 'Cannot dismiss', closable: false },
    })
    expect(document.body.querySelector('.modal-close-btn')).toBeNull()
    const overlay = document.body.querySelector('.modal-overlay')
    overlay.dispatchEvent(new Event('click'))
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})
