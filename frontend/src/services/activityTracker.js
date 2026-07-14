export const DEFAULT_ACTIVITY_THROTTLE_MS = 2 * 60 * 1000
export const EXPIRING_SOON_THRESHOLD_MS = 60 * 1000

function toTimestamp(value) {
  if (!value) {
    return 0
  }

  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? 0 : parsed
}

function isMeaningfulKeydown(event) {
  return !event.defaultPrevented && !event.metaKey && !event.ctrlKey && !event.altKey
}

export function createActivityTracker({
  reportActivity,
  getIsAuthenticated,
  getInactivityExpiresAt,
  onActivityRecorded = () => {},
  onLocalActivity = () => {},
  throttleMs = DEFAULT_ACTIVITY_THROTTLE_MS,
  expiringSoonThresholdMs = EXPIRING_SOON_THRESHOLD_MS,
  now = () => Date.now(),
  documentRef = typeof document !== 'undefined' ? document : null,
}) {
  let started = false
  let removeNavigationHook = null
  let inFlightReport = null
  let pendingReport = false
  let lastReportedAt = 0
  const removeListeners = []

  function shouldReport(force = false) {
    if (!getIsAuthenticated()) {
      return false
    }

    const currentTime = now()
    const expiresAt = toTimestamp(getInactivityExpiresAt())
    const nearTimeout = expiresAt > 0 && expiresAt - currentTime <= expiringSoonThresholdMs

    if (force || nearTimeout) {
      return true
    }

    return currentTime - lastReportedAt >= throttleMs
  }

  async function flush(force = false) {
    if (!shouldReport(force)) {
      return
    }

    if (inFlightReport) {
      pendingReport = true
      return inFlightReport
    }

    inFlightReport = Promise.resolve()
      .then(() => reportActivity())
      .then((data) => {
        lastReportedAt = now()
        onActivityRecorded(data)
        return data
      })
      .finally(() => {
        inFlightReport = null

        if (pendingReport) {
          pendingReport = false
          void flush(true)
        }
      })

    return inFlightReport
  }

  function recordActivity(source, { force = false } = {}) {
    if (!getIsAuthenticated()) {
      return Promise.resolve()
    }

    onLocalActivity(source)
    return flush(force)
  }

  function bindListener(target, eventName, listener, options) {
    if (!target?.addEventListener) {
      return
    }

    target.addEventListener(eventName, listener, options)
    removeListeners.push(() => target.removeEventListener(eventName, listener, options))
  }

  function start(router) {
    if (started) {
      return
    }

    started = true

    bindListener(documentRef, 'pointerdown', () => recordActivity('pointerdown'))
    bindListener(documentRef, 'submit', () => recordActivity('submit', { force: true }), true)
    bindListener(documentRef, 'keydown', (event) => {
      if (isMeaningfulKeydown(event)) {
        recordActivity('keydown')
      }
    })

    if (router?.afterEach) {
      removeNavigationHook = router.afterEach((to, from) => {
        if (
          getIsAuthenticated()
          && to?.meta?.requiresAuth
          && to.fullPath !== from.fullPath
        ) {
          recordActivity('navigation', { force: true })
        }
      })
    }
  }

  function stop() {
    started = false
    pendingReport = false
    lastReportedAt = 0

    while (removeListeners.length) {
      removeListeners.pop()()
    }

    if (removeNavigationHook) {
      removeNavigationHook()
      removeNavigationHook = null
    }
  }

  return {
    flush,
    recordActivity,
    start,
    stop,
  }
}
