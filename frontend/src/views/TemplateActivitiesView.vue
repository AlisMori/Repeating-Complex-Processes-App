<template>
  <main class="activities-page">
    <h1>Template Activities</h1>
    <p>Create and manage activities inside templates.</p>

    <section class="activity-form">
      <h2>Create Activity</h2>

      <form @submit.prevent="createActivity">
        <label>
          Template
          <select v-model="form.template" required>
            <option disabled value="">Select template</option>
            <option
              v-for="template in templates"
              :key="template.template_id"
              :value="template.template_id"
            >
              {{ template.template_name }}
            </option>
          </select>
        </label>

        <label>
          Activity Name
          <input v-model="form.activity_name" type="text" required />
        </label>

        <label>
          Description
          <textarea v-model="form.description"></textarea>
        </label>

        <label>
          Start Offset Days
          <input v-model.number="form.start_offset_days" type="number" min="0" required />
        </label>

        <label>
          End Offset Days
          <input v-model.number="form.end_offset_days" type="number" min="0" required />
        </label>

        <button type="submit">Create Activity</button>
      </form>
    </section>

    <section class="tag-form">
      <h2>Create Tag</h2>

      <form @submit.prevent="createTag">
        <label>
          Tag Name
          <input
            v-model="newTagName"
            type="text"
            placeholder="Example: Important"
          />
        </label>

        <button type="submit">Create Tag</button>
      </form>
    </section>

    <section class="activity-list">
      <h2>Activity List</h2>

      <div class="filter-box">
        <label>
          Filter by Tag
          <select v-model="selectedFilterTag">
            <option value="">All Tags</option>
            <option
              v-for="tag in tags"
              :key="tag.tag_id"
              :value="tag.tag_id"
            >
              {{ tag.tag_name }}
            </option>
          </select>
        </label>
      </div>

      <p v-if="loading">Loading activities...</p>
      <p v-if="error" class="error">{{ error }}</p>

      <article
        v-for="activity in filteredActivities()"
        :key="activity.template_activity_id"
        class="activity-card"
      >
        <h3>{{ activity.activity_name }}</h3>
        <p>{{ activity.description || 'No description provided.' }}</p>
        <p>Start offset: {{ activity.start_offset_days }}</p>
        <p>End offset: {{ activity.end_offset_days }}</p>

        <div class="activity-tags">
          <strong>Tags:</strong>

          <span
            v-for="activityTag in getActivityTags(activity.template_activity_id)"
            :key="activityTag.template_activity_tag_id"
            class="tag-chip"
          >
            {{ getTagName(activityTag.tag) }}
            <button
              type="button"
              class="remove-tag"
              @click="removeTagFromActivity(activityTag.template_activity_tag_id)"
            >
              ×
            </button>
          </span>
        </div>

        <div class="assign-tag">
          <select v-model="selectedTags[activity.template_activity_id]">
            <option disabled value="">Select tag</option>
            <option
              v-for="tag in tags"
              :key="tag.tag_id"
              :value="tag.tag_id"
            >
              {{ tag.tag_name }}
            </option>
          </select>

          <button
            type="button"
            @click="assignTagToActivity(activity.template_activity_id)"
          >
            Add Tag
          </button>
        </div>
      </article>
    </section>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api/axios'

const templates = ref([])
const activities = ref([])
const loading = ref(false)
const error = ref('')

const tags = ref([])
const activityTags = ref([])
const newTagName = ref('')
const selectedTags = reactive({})
const selectedFilterTag = ref('')

const form = reactive({
  template: '',
  activity_name: '',
  description: '',
  start_offset_days: 0,
  end_offset_days: 1,
})

async function fetchTemplates() {
  try {
    const response = await api.get('/templates/', {
      requiresAuth: true,
    })

    templates.value = response.data
  } catch {
    error.value = 'Could not load templates.'
  }
}

async function fetchActivities() {
  loading.value = true
  error.value = ''

  try {
    const response = await api.get('/template-activities/', {
      requiresAuth: true,
    })

    activities.value = response.data
  } catch {
    error.value = 'Could not load activities.'
  } finally {
    loading.value = false
  }
}

async function createActivity() {
  error.value = ''

  try {
    await api.post('/template-activities/', form, {
      requiresAuth: true,
    })

    form.activity_name = ''
    form.description = ''
    form.start_offset_days = 0
    form.end_offset_days = 1

    await fetchActivities()
  } catch {
    error.value = 'Could not create activity.'
  }
}

async function fetchTags() {
  try {
    const response = await api.get('/tags/', {
      requiresAuth: true,
    })

    tags.value = response.data
  } catch {
    error.value = 'Could not load tags.'
  }
}

async function fetchActivityTags() {
  try {
    const response = await api.get('/template-activity-tags/', {
      requiresAuth: true,
    })

    activityTags.value = response.data
  } catch {
    error.value = 'Could not load activity tags.'
  }
}

async function createTag() {
  if (!newTagName.value) {
    return
  }

  error.value = ''

  try {
    await api.post(
      '/tags/',
      { tag_name: newTagName.value },
      { requiresAuth: true },
    )

    newTagName.value = ''
    await fetchTags()
  } catch {
    error.value = 'Could not create tag.'
  }
}

async function assignTagToActivity(activityId) {
  const tagId = selectedTags[activityId]

  if (!tagId) {
    return
  }

  const alreadyAssigned = activityTags.value.some(
    (item) => item.template_activity === activityId && item.tag === tagId,
  )

  if (alreadyAssigned) {
    error.value = 'This tag is already assigned to this activity.'
    return
  }

  error.value = ''

  try {
    await api.post(
      '/template-activity-tags/',
      {
        template_activity: activityId,
        tag: tagId,
      },
      { requiresAuth: true },
    )

    selectedTags[activityId] = ''
    await fetchActivityTags()
  } catch {
    error.value = 'Could not assign tag to activity.'
  }
}

async function removeTagFromActivity(activityTagId) {
  error.value = ''

  try {
    await api.delete(`/template-activity-tags/${activityTagId}/`, {
      requiresAuth: true,
    })

    await fetchActivityTags()
  } catch {
    error.value = 'Could not remove tag from activity.'
  }
}

function getActivityTags(activityId) {
  return activityTags.value.filter(
    (item) => item.template_activity === activityId,
  )
}

function getTagName(tagId) {
  const tag = tags.value.find(
    (item) => item.tag_id === tagId,
  )

  return tag ? tag.tag_name : 'Tag'
}

function filteredActivities() {
  if (!selectedFilterTag.value) {
    return activities.value
  }

  const activityIds = activityTags.value
    .filter((item) => item.tag === selectedFilterTag.value)
    .map((item) => item.template_activity)

  return activities.value.filter((activity) =>
    activityIds.includes(activity.template_activity_id),
  )
}

onMounted(async () => {
  await fetchTemplates()
  await fetchActivities()
  await fetchTags()
  await fetchActivityTags()
})
</script>

<style scoped>
.activities-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 2rem;
}

.activity-form,
.activity-list,
.tag-form {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 1.5rem;
  margin-top: 1.5rem;
}

form {
  display: grid;
  gap: 1rem;
}

label {
  display: grid;
  gap: 0.4rem;
  font-weight: 600;
}

input,
textarea,
select {
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 8px;
}

button {
  width: fit-content;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.activity-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 1rem;
  margin-top: 1rem;
}

.activity-tags {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.8rem;
}

.tag-chip {
  background: #eef2ff;
  border-radius: 999px;
  padding: 0.3rem 0.7rem;
  font-size: 0.85rem;
}

.remove-tag {
  margin-left: 0.4rem;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0;
}

.assign-tag {
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
  align-items: center;
}

.filter-box {
  margin-bottom: 1rem;
}

.error {
  color: #dc2626;
}
</style>
