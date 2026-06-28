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

    <section class="activity-list">
      <h2>Activity List</h2>

      <p v-if="loading">Loading activities...</p>
      <p v-if="error" class="error">{{ error }}</p>

      <article
        v-for="activity in activities"
        :key="activity.template_activity_id"
        class="activity-card"
      >
        <h3>{{ activity.activity_name }}</h3>
        <p>{{ activity.description || 'No description provided.' }}</p>
        <p>Start offset: {{ activity.start_offset_days }}</p>
        <p>End offset: {{ activity.end_offset_days }}</p>
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
  } catch (err) {
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
  } catch (err) {
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
  } catch (err) {
    error.value = 'Could not create activity.'
  }
}

onMounted(async () => {
  await fetchTemplates()
  await fetchActivities()
})
</script>

<style scoped>
.activities-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 2rem;
}

.activity-form,
.activity-list {
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

.error {
  color: #dc2626;
}
</style>