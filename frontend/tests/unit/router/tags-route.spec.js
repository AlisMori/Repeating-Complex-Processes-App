import { describe, expect, it } from 'vitest'

import router from '@/router'

describe('tags route', () => {
  it('requires authentication', () => {
    const tagsRoute = router.getRoutes().find((route) => route.name === 'tags')

    expect(tagsRoute).toBeTruthy()
    expect(tagsRoute.meta.requiresAuth).toBe(true)
    expect(tagsRoute.path).toBe('/tags')
  })
})
