<template>
  <main class="templates-page">
    <section class="page-header">
      <div>
        <h1>Templates</h1>
        <p>Create and manage reusable process templates.</p>
      </div>
    </section>

    <section class="template-form">
      <h2>Create Template</h2>

      <form @submit.prevent="createTemplate">
        <label>
          Template Name
          <input v-model="form.template_name" type="text" required />
        </label>

        <label>
          Description
          <textarea v-model="form.description"></textarea>
        </label>

        <label class="checkbox-row">
          <input v-model="form.is_public" type="checkbox" />
          Public template
        </label>

        <button type="submit">Create Template</button>
      </form>
    </section>

    <section class="template-list">
      <div class="list-header">
        <h2>Template List</h2>
        <input
          v-model="search"
          type="text"
          placeholder="Search templates..."
          @input="fetchTemplates"
        />
      </div>

      <p v-if="loading">Loading templates...</p>
      <p v-if="error" class="error">{{ error }}</p>

      <div v-if="!loading && templates.length === 0" class="empty">
        No templates found.
      </div>

      <article
        v-for="template in templates"
        :key="template.template_id"
        class="template-card"
      >
        <h3>{{ template.template_name }}</h3>
        <p>{{ template.description || 'No description provided.' }}</p>

        <div class="meta">
          <span>Version: {{ template.template_version }}</span>
          <span>{{ template.is_public ? 'Public' : 'Private' }}</span>
        </div>
        <div class="actions">
          <button type="button" @click="duplicateTemplate(template.template_id)">
            Duplicate
          </button>
          
          <button
            type="button"
            @click="deleteTemplate(template.template_id)"
          >
            Delete
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
const loading = ref(false)
const error = ref('')
const search = ref('')

const form = reactive({
  template_name: '',
  description: '',
  is_public: false,
  template_version: 1,
  created_by_type: 'user',
})

async function deleteTemplate(templateId) {
  const confirmed = window.confirm('Delete this template?')

  if (!confirmed) {
    return
  }

  error.value = ''

  try {
    await api.delete(`/templates/${templateId}/`, {
      requiresAuth: true,
    })

    await fetchTemplates()
  } catch (err) {
    error.value = 'Could not delete template.'
  }
}

async function fetchTemplates() {
  loading.value = true
  error.value = ''

  try {
    const response = await api.get('/templates/', {
      params: search.value ? { search: search.value } : {},
      requiresAuth: true,
    })

    templates.value = response.data
  } catch (err) {
    error.value = 'Could not load templates.'
  } finally {
    loading.value = false
  }
}

async function createTemplate() {
  error.value = ''

  try {
    await api.post('/templates/', form, {
      requiresAuth: true,
    })

    form.template_name = ''
    form.description = ''
    form.is_public = false

    await fetchTemplates()
  } catch (err) {
    error.value = 'Could not create template.'
  }
}

async function duplicateTemplate(templateId) {
  error.value = ''

  try {
    await api.post(`/templates/${templateId}/duplicate/`, {}, {
      requiresAuth: true,
    })

    await fetchTemplates()
  } catch (err) {
    error.value = 'Could not duplicate template.'
  }
}

onMounted(fetchTemplates)
</script>

<style scoped>
.templates-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 2rem;
}

.actions {
  margin-top: 1rem;
}

.actions button {
  padding: 0.5rem 0.9rem;
}

.page-header {
  margin-bottom: 2rem;
}

.page-header h1 {
  margin-bottom: 0.5rem;
}

.template-form,
.template-list {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  border: 1px solid #e5e7eb;
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
textarea {
  padding: 0.7rem;
  border: 1px solid #d1d5db;
  border-radius: 8px;
}

textarea {
  min-height: 90px;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

button {
  width: fit-content;
  padding: 0.7rem 1.2rem;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.list-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
}

.template-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 1rem;
  margin-top: 1rem;
}

.meta {
  display: flex;
  gap: 1rem;
  font-size: 0.9rem;
  opacity: 0.75;
}

.error {
  color: #b91c1c;
}

.empty {
  color: #6b7280;
}
</style>