import { defineStore } from 'pinia'
import { ref } from 'vue'

import { getShareNotifications, markShareNotificationsRead } from '@/api/auth'

export const useNotificationStore = defineStore('notifications', () => {
  const shareNotifications = ref([])
  const shareNotificationsOpen = ref(false)
  const initialized = ref(false)
  const loading = ref(false)

  function normalizeItems(data) {
    return Array.isArray(data) ? data : (data?.results || [])
  }

  async function loadShareNotifications({ force = false } = {}) {
    if (loading.value || (initialized.value && !force)) {
      return shareNotifications.value
    }

    loading.value = true
    try {
      const { data } = await getShareNotifications()
      shareNotifications.value = normalizeItems(data)
      shareNotificationsOpen.value = shareNotifications.value.length > 0
      initialized.value = true
      return shareNotifications.value
    } finally {
      loading.value = false
    }
  }

  async function acknowledgeShareNotifications(ids = null) {
    const targetIds = ids || shareNotifications.value.map((item) => item.notification_id)
    if (targetIds.length > 0) {
      await markShareNotificationsRead(targetIds)
    }
    shareNotifications.value = shareNotifications.value.filter(
      (item) => !targetIds.includes(item.notification_id),
    )
    shareNotificationsOpen.value = false
    initialized.value = true
  }

  function closeShareNotifications() {
    shareNotificationsOpen.value = false
  }

  function reset() {
    shareNotifications.value = []
    shareNotificationsOpen.value = false
    initialized.value = false
    loading.value = false
  }

  return {
    shareNotifications,
    shareNotificationsOpen,
    initialized,
    loading,
    loadShareNotifications,
    acknowledgeShareNotifications,
    closeShareNotifications,
    reset,
  }
})
