<template>
  <main class="tasks-page">
    <h1>Template Tasks</h1>
    <p>Create and manage tasks inside templates.</p>

    <section class="task-form">
      <h2>Create Task</h2>

      <form @submit.prevent="createTask">
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
          Task Name
          <input
            v-model="form.task_name"
            type="text"
            required
          />
        </label>

        <label>
          Description
          <textarea
            v-model="form.description"
          ></textarea>
        </label>

        <label>
          Day Offset
          <input
            v-model.number="form.day_offset"
            type="number"
            min="0"
            required
          />
        </label>

        <label>
          Duration Days
          <input
            v-model.number="form.duration_days"
            type="number"
            min="0"
          />
        </label>

        <button type="submit">
          Create Task
        </button>
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

            <button type="submit">
            Create Tag
            </button>
        </form>
    </section>

    <section class="task-list">
      <h2>Task List</h2>

      <p v-if="loading">
        Loading tasks...
      </p>

      <p
        v-if="error"
        class="error"
      >
        {{ error }}
      </p>

      <article
        v-for="task in tasks"
        :key="task.template_task_id"
        class="task-card"
      >
        <h3>{{ task.task_name }}</h3>

        <p>
          {{ task.description || 'No description provided.' }}
        </p>

        <p>
          Day offset:
          {{ task.day_offset }}
        </p>

        <p>
          Duration:
          {{ task.duration_days || 0 }} days
        </p>
        <div class="task-tags">
            <strong>Tags:</strong>

            <span
                v-for="taskTag in getTaskTags(task.template_task_id)"
                :key="taskTag.template_task_tag_id"
                class="tag-chip"
            >
                {{ getTagName(taskTag.tag) }}
            </span>
            </div>

            <div class="assign-tag">
            <select v-model="selectedTags[task.template_task_id]">
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
                @click="assignTagToTask(task.template_task_id)"
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
const tasks = ref([])
const loading = ref(false)
const error = ref('')

const tags = ref([])
const taskTags = ref([])
const newTagName = ref('')
const selectedTags = reactive({})

const form = reactive({
  template: '',
  task_name: '',
  description: '',
  day_offset: 0,
  duration_days: 1,
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

async function fetchTasks() {
  loading.value = true
  error.value = ''

  try {
    const response = await api.get('/template-tasks/', {
      requiresAuth: true,
    })

    tasks.value = response.data
  } catch (err) {
    error.value = 'Could not load tasks.'
  } finally {
    loading.value = false
  }
}

async function createTask() {
  error.value = ''

  try {
    await api.post(
      '/template-tasks/',
      form,
      {
        requiresAuth: true,
      },
    )

    form.task_name = ''
    form.description = ''
    form.day_offset = 0
    form.duration_days = 1

    await fetchTasks()
  } catch (err) {
    error.value = 'Could not create task.'
  }
}

async function fetchTags() {
  try {
    const response = await api.get('/tags/', {
      requiresAuth: true,
    })

    tags.value = response.data
  } catch (err) {
    error.value = 'Could not load tags.'
  }
}

async function fetchTaskTags() {
  try {
    const response = await api.get('/template-task-tags/', {
      requiresAuth: true,
    })

    taskTags.value = response.data
  } catch (err) {
    error.value = 'Could not load task tags.'
  }
}

async function createTag() {
  if (!newTagName.value) {
    return
  }

  try {
    await api.post(
      '/tags/',
      { tag_name: newTagName.value },
      { requiresAuth: true },
    )

    newTagName.value = ''
    await fetchTags()
  } catch (err) {
    error.value = 'Could not create tag.'
  }
}

async function assignTagToTask(taskId) {
  const tagId = selectedTags[taskId]

  if (!tagId) {
    return
  }

  try {
    await api.post(
      '/template-task-tags/',
      {
        template_task: taskId,
        tag: tagId,
      },
      { requiresAuth: true },
    )

    selectedTags[taskId] = ''
    await fetchTaskTags()
  } catch (err) {
    error.value = 'Could not assign tag to task.'
  }
}

function getTaskTags(taskId) {
  return taskTags.value.filter(
    (item) => item.template_task === taskId
  )
}

function getTagName(tagId) {
  const tag = tags.value.find(
    (item) => item.tag_id === tagId
  )

  return tag ? tag.tag_name : 'Tag'
}

onMounted(async () => {
  await fetchTemplates()
  await fetchTasks()
  await fetchTags()
  await fetchTaskTags()
})
</script>

<style scoped>
.tasks-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 2rem;
}

.task-form,
.task-list {
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

.task-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 1rem;
  margin-top: 1rem;
}

.tag-form {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 1.5rem;
  margin-top: 1.5rem;
}

.task-tags {
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

.assign-tag {
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
  align-items: center;
}

.error {
  color: #dc2626;
}
</style>