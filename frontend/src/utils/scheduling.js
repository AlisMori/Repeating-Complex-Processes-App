// ============================================
//   RECURRA — DEPENDENCY-AWARE SCHEDULE RESOLVER
//   /frontend/src/utils/scheduling.js
//
//   This is a direct port of backend/templates_mgmt/scheduling.py.
//   It exists only for the one case the backend can't help with:
//   previewing a template's timeline while the user is still
//   picking dependencies in the create/edit wizard, before anything
//   is saved. Once tasks and dependencies are actually persisted,
//   use the backend's GET /templates/:id/timeline_preview/ endpoint
//   instead (see TemplateDetailView.vue) — don't let this drift
//   into a second, possibly-diverging implementation.
//
//   nodes: { [taskId]: { offset: number, duration: number, fixed: boolean } }
//   edges: { [taskId]: [dependsOnTaskId, ...] }
// ============================================

export function resolveEffectiveOffsets(nodes, edges) {
  const effective = {}
  const circular = new Set()
  const conflicts = new Set()

  function resolve(taskId, visiting) {
    if (Object.prototype.hasOwnProperty.call(effective, taskId)) {
      return effective[taskId]
    }
    const node = nodes[taskId]
    if (!node) return null

    if (visiting.has(taskId)) {
      circular.add(taskId)
      const start = node.offset
      const end = start + node.duration
      effective[taskId] = [start, end]
      return effective[taskId]
    }

    const nextVisiting = new Set(visiting)
    nextVisiting.add(taskId)

    let maxDepEnd = null
    for (const depId of (edges[taskId] || [])) {
      const depResult = resolve(depId, nextVisiting)
      if (!depResult) continue
      const depEnd = depResult[1]
      if (maxDepEnd === null || depEnd > maxDepEnd) maxDepEnd = depEnd
    }

    let start
    if (node.fixed) {
      start = node.offset
      if (maxDepEnd !== null && maxDepEnd > start) conflicts.add(taskId)
    } else {
      start = maxDepEnd !== null ? Math.max(node.offset, maxDepEnd) : node.offset
    }
    const end = start + node.duration
    effective[taskId] = [start, end]
    return effective[taskId]
  }

  for (const taskId of Object.keys(nodes)) {
    resolve(taskId, new Set())
  }

  return { effective, circular, conflicts }
}