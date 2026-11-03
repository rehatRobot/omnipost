import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const STORAGE_KEY = 'sau-publish-log'

const loadRecords = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export const usePublishLogStore = defineStore('publishLog', () => {
  const records = ref(loadRecords())

  const count = computed(() => records.value.length)

  const persist = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(records.value))
  }

  const addRecord = (entry) => {
    if (entry.dedupeKey && records.value.some((item) => item.dedupeKey === entry.dedupeKey)) {
      return false
    }
    records.value.unshift({
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      createdAt: Date.now(),
      platform: entry.platform || '未知',
      account: entry.account || '',
      content: entry.content || '',
      status: entry.status || 'note',
      message: entry.message || '',
      source: entry.source || 'manual',
      dedupeKey: entry.dedupeKey || ''
    })
    persist()
    return true
  }

  const addJobResults = (job, platformLabel) => {
    if (!job || job.status === 'running') return 0
    const results = job.results || []
    let added = 0
    const rows = results.length
      ? results
      : [{
          id: 'summary',
          fileName: job.title || '',
          accountName: '',
          status: job.status,
          message: `成功 ${job.successCount || 0} / 失败 ${job.failedCount || 0}`
        }]
    for (const row of rows) {
      if (row.status === 'pending') continue
      const ok = addRecord({
        platform: platformLabel || '未知',
        account: row.accountName || '',
        content: row.fileName || job.title || '',
        status: row.status === 'error' ? 'failed' : (row.status || 'note'),
        message: row.message || '',
        source: 'auto',
        dedupeKey: `job:${job.jobId}:${row.id}`
      })
      if (ok) added += 1
    }
    return added
  }

  const removeRecord = (id) => {
    records.value = records.value.filter((item) => item.id !== id)
    persist()
  }

  const clearRecords = () => {
    records.value = []
    persist()
  }

  return {
    records,
    count,
    addRecord,
    addJobResults,
    removeRecord,
    clearRecords
  }
})
