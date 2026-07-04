<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { searchSmart } from '@/api/search'

const props = defineProps({
  context: {
    type: String,
    required: true,
  },
  defaultScopes: {
    type: Array,
    default: () => [],
  },
  placeholder: {
    type: String,
    default: 'Search',
  },
})

const router = useRouter()
const rootRef = ref(null)
const query = ref('')
const isOpen = ref(false)
const isLoading = ref(false)
const error = ref('')
const selectedScopes = ref([])
const results = ref(null)
const debounceHandle = ref(null)

const scopeOptions = [
  { value: 'all', label: 'All' },
  { value: 'templates', label: 'Templates' },
  { value: 'cycles', label: 'Cycles' },
  { value: 'tasks', label: 'Tasks' },
  { value: 'activities', label: 'Activities' },
  { value: 'notes', label: 'Notes' },
]

const minQueryLength = 2

const effectiveScopes = computed(() => {
  if (selectedScopes.value.includes('all')) {
    return ['all']
  }
  return selectedScopes.value
})

const defaultScopeLabels = computed(() =>
  scopeOptions
    .filter((option) => props.defaultScopes.includes(option.value))
    .map((option) => option.label)
    .join(', ')
)

const groups = computed(() => results.value?.groups || [])
const hasQuery = computed(() => query.value.trim().length >= minQueryLength)
const hasResults = computed(() => groups.value.length > 0)

function handleDocumentClick(event) {
  if (!rootRef.value?.contains(event.target)) {
    isOpen.value = false
  }
}

function openPanel() {
  isOpen.value = true
}

function clearResults() {
  results.value = null
  error.value = ''
  isLoading.value = false
}

function isScopeVisuallyActive(scope) {
  if (scope === 'all') {
    return selectedScopes.value.includes('all')
  }

  if (selectedScopes.value.length === 0) {
    return props.defaultScopes.includes(scope)
  }

  return selectedScopes.value.includes(scope)
}

function toggleScope(scope) {
  if (scope === 'all') {
    selectedScopes.value = selectedScopes.value.includes('all') ? [] : ['all']
    return
  }

  const next = selectedScopes.value.filter((value) => value !== 'all')
  const index = next.indexOf(scope)

  if (selectedScopes.value.length === 0) {
    const defaultSet = new Set(props.defaultScopes)
    if (defaultSet.has(scope)) {
      defaultSet.delete(scope)
    } else {
      defaultSet.add(scope)
    }
    selectedScopes.value = Array.from(defaultSet)
    return
  }

  if (index >= 0) {
    next.splice(index, 1)
  } else {
    next.push(scope)
  }

  selectedScopes.value = next
}

async function runSearch() {
  const trimmedQuery = query.value.trim()

  if (trimmedQuery.length < minQueryLength) {
    clearResults()
    return
  }

  isLoading.value = true
  error.value = ''

  try {
    results.value = await searchSmart({
      q: trimmedQuery,
      context: props.context,
      scopes: effectiveScopes.value.length ? effectiveScopes.value.join(',') : undefined,
    })
  } catch (err) {
    results.value = null
    error.value = 'Search failed. Please try again.'
  } finally {
    isLoading.value = false
  }
}

function scheduleSearch() {
  if (debounceHandle.value) {
    window.clearTimeout(debounceHandle.value)
  }

  debounceHandle.value = window.setTimeout(() => {
    runSearch()
  }, 300)
}

function goToResult(result) {
  isOpen.value = false
  router.push(result.url)
}

watch([query, selectedScopes], () => {
  if (!isOpen.value) {
    return
  }
  scheduleSearch()
})

watch(isOpen, (open) => {
  if (open) {
    scheduleSearch()
  }
})

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
  if (debounceHandle.value) {
    window.clearTimeout(debounceHandle.value)
  }
})
</script>

<template>
  <div ref="rootRef" class="smart-search" :class="{ open: isOpen }">
    <div class="search-shell">
      <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        v-model="query"
        type="text"
        class="search-input"
        :placeholder="placeholder"
        @focus="openPanel"
      />
      <span v-if="isLoading" class="search-status">Searching...</span>
    </div>

    <div v-if="isOpen" class="search-panel">
      <div class="scope-row">
        <button
          v-for="scope in scopeOptions"
          :key="scope.value"
          type="button"
          class="scope-chip"
          :class="{ active: isScopeVisuallyActive(scope.value), all: scope.value === 'all' }"
          @click="toggleScope(scope.value)"
        >
          {{ scope.label }}
        </button>
      </div>

      <p v-if="!hasQuery" class="search-helper">
        Type at least 2 characters. Default scope: {{ defaultScopeLabels }}.
      </p>
      <p v-else-if="error" class="search-message error">{{ error }}</p>
      <p v-else-if="!isLoading && !hasResults" class="search-message empty">No matching results found.</p>

      <div v-if="hasResults" class="results-wrap">
        <section v-for="group in groups" :key="group.type" class="result-group">
          <div class="group-header">
            <span class="group-title">{{ group.label }}</span>
            <span class="group-count">{{ group.count }}</span>
          </div>

          <button
            v-for="result in group.results"
            :key="`${group.type}-${result.id}-${result.url}`"
            type="button"
            class="result-row"
            @click="goToResult(result)"
          >
            <div class="result-type">{{ result.type }}</div>
            <div class="result-copy">
              <div class="result-title">{{ result.title }}</div>
              <div v-if="result.snippet" class="result-snippet">{{ result.snippet }}</div>
              <div v-if="result.parent" class="result-parent">
                in {{ result.parent.type === 'cycle' ? 'Cycle' : 'Template' }}: {{ result.parent.title }}
              </div>
            </div>
          </button>

          <div v-if="group.has_more" class="more-note">More results available</div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.smart-search {
  position: relative;
  width: min(430px, 100%);
}

.search-shell {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 220px;
  padding: 7px 12px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--bg-page);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast), background var(--transition-fast);
}

.open .search-shell {
  background: var(--white);
  border-color: #c4b5fd;
  box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.08);
}

.search-icon {
  width: 14px;
  height: 14px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  width: 100%;
  border: none;
  background: transparent;
  outline: none;
  font-size: 13px;
  color: var(--text-primary);
  font-family: var(--font-main);
}

.search-input::placeholder {
  color: var(--text-muted);
}

.search-status {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}

.search-panel {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  width: 100%;
  max-height: min(70vh, 620px);
  overflow-y: auto;
  padding: 12px;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  background: var(--white);
  box-shadow: var(--shadow-lg);
  z-index: 40;
}

.scope-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.scope-chip {
  padding: 5px 10px;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background: var(--white);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  font-family: var(--font-main);
}

.scope-chip.active {
  border-color: #c4b5fd;
  background: var(--violet-bg);
  color: var(--violet);
}

.scope-chip.all.active {
  border-color: var(--violet);
}

.search-helper,
.search-message,
.more-note {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.search-message.error {
  color: #b91c1c;
}

.results-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}

.result-group {
  border-top: 1px solid var(--border-light);
  padding-top: 12px;
}

.result-group:first-child {
  border-top: none;
  padding-top: 0;
}

.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.group-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.group-count {
  font-size: 11px;
  color: var(--text-muted);
}

.result-row {
  display: flex;
  gap: 10px;
  width: 100%;
  padding: 10px;
  margin-bottom: 6px;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--white);
  cursor: pointer;
  text-align: left;
  font-family: var(--font-main);
}

.result-row:hover {
  border-color: #c4b5fd;
  background: #fcfbff;
}

.result-type {
  min-width: 64px;
  padding-top: 1px;
  font-size: 11px;
  font-weight: 600;
  color: var(--violet);
  text-transform: uppercase;
}

.result-copy {
  min-width: 0;
}

.result-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.result-snippet,
.result-parent {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.45;
}

@media (max-width: 900px) {
  .smart-search {
    width: 100%;
  }

  .search-panel {
    left: 0;
    right: auto;
  }
}
</style>
