function toMessages(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item))
  }

  if (value === null || value === undefined) {
    return []
  }

  return [String(value)]
}

export function normalizeApiError(error, options = {}) {
  const fallbackMessage = options.fallbackMessage || 'Something went wrong. Please try again.'
  const data = error?.response?.data
  const fieldErrors = {}
  const generalErrors = []

  if (error?.code === 'AUTH_SESSION_EXPIRED') {
    return {
      fieldErrors,
      generalErrors: ['Your session has expired. Please log in again.'],
    }
  }

  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return {
      fieldErrors,
      generalErrors: [error?.message || fallbackMessage],
    }
  }

  for (const [key, value] of Object.entries(data)) {
    const messages = toMessages(value)
    if (!messages.length) {
      continue
    }

    if (key === 'detail' || key === 'non_field_errors') {
      generalErrors.push(...messages)
      continue
    }

    fieldErrors[key] = messages
  }

  if (!generalErrors.length && !Object.keys(fieldErrors).length) {
    generalErrors.push(fallbackMessage)
  }

  return { fieldErrors, generalErrors }
}
