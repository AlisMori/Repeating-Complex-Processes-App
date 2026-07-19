import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'

describe('BaseInput', () => {
  it('does not show an error state when no error prop is passed', () => {
    const wrapper = mount(BaseInput, { props: { label: 'Name' } })
    expect(wrapper.find('.input-wrapper').classes()).not.toContain('has-error')
    expect(wrapper.find('.input-error').exists()).toBe(false)
  })

  it('shows the correct error state and message when error prop is set', () => {
    const wrapper = mount(BaseInput, {
      props: { label: 'Name', required: true, error: 'Name is required' },
    })
    expect(wrapper.find('.input-wrapper').classes()).toContain('has-error')
    const errorEl = wrapper.find('.input-error')
    expect(errorEl.exists()).toBe(true)
    expect(errorEl.attributes('role')).toBe('alert')
    expect(errorEl.text()).toBe('Name is required')
  })

  it('marks the field as required and shows the required indicator', () => {
    const wrapper = mount(BaseInput, { props: { label: 'Email', required: true } })
    expect(wrapper.find('input').attributes('required')).toBeDefined()
    expect(wrapper.find('.required-star').exists()).toBe(true)
  })

  it('emits update:modelValue with the typed value', async () => {
    const wrapper = mount(BaseInput, { props: { modelValue: '' } })
    await wrapper.find('input').setValue('hello')
    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['hello'])
  })
})

describe('BaseSelect', () => {
  it('does not show an error state when no error prop is passed', () => {
    const wrapper = mount(BaseSelect, { props: { label: 'Status' } })
    expect(wrapper.find('.select-wrapper').classes()).not.toContain('has-error')
    expect(wrapper.find('.select-error').exists()).toBe(false)
  })

  it('shows the correct error state and message when error prop is set', () => {
    const wrapper = mount(BaseSelect, {
      props: { label: 'Status', required: true, error: 'Please choose a status' },
    })
    expect(wrapper.find('.select-wrapper').classes()).toContain('has-error')
    const errorEl = wrapper.find('.select-error')
    expect(errorEl.exists()).toBe(true)
    expect(errorEl.attributes('role')).toBe('alert')
    expect(errorEl.text()).toBe('Please choose a status')
  })

  it('marks the field as required and shows the required indicator', () => {
    const wrapper = mount(BaseSelect, { props: { label: 'Status', required: true } })
    expect(wrapper.find('select').attributes('required')).toBeDefined()
    expect(wrapper.find('.required-star').exists()).toBe(true)
  })
})
