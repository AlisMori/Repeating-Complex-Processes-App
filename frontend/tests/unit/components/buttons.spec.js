import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseButton from '@/components/ui/BaseButton.vue'

describe('BaseButton', () => {
  it('renders each variant with the correct class', () => {
    for (const variant of ['primary', 'secondary', 'danger', 'ghost']) {
      const wrapper = mount(BaseButton, { props: { variant } })
      expect(wrapper.classes()).toContain(`btn-${variant}`)
    }
  })

  it('defaults to the primary variant', () => {
    const wrapper = mount(BaseButton, {})
    expect(wrapper.classes()).toContain('btn-primary')
  })

  it('is disabled when the disabled prop is true', () => {
    const wrapper = mount(BaseButton, { props: { disabled: true } })
    expect(wrapper.attributes('disabled')).toBeDefined()
  })

  it('is disabled while loading, even if disabled prop is false', () => {
    const wrapper = mount(BaseButton, { props: { loading: true } })
    expect(wrapper.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.btn-spinner').exists()).toBe(true)
  })

  it('does not emit a click when disabled', async () => {
    const wrapper = mount(BaseButton, { props: { disabled: true } })
    await wrapper.trigger('click')
    // A disabled native <button> never fires click at all
    expect(wrapper.emitted('click')).toBeUndefined()
  })

  it('applies full-width class when fullWidth is true', () => {
    const wrapper = mount(BaseButton, { props: { fullWidth: true } })
    expect(wrapper.classes()).toContain('btn-full')
  })
})
