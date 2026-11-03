<template>
  <div class="data-center">
    <div class="page-header">
      <h1>数据中心</h1>
      <p class="subtitle">
        查看抖音 / 快手 / 小红书 / B站 / 视频号作品最近互动数据（每次同步最近 5 条）
        <template v-if="selectedPlatform === 'douyin'">；抖音同步含流量与观众分析，可能较慢</template>
        <template v-else-if="selectedPlatform === 'kuaishou'">；快手同步含流量分析与助推</template>
      </p>
    </div>

    <div class="toolbar">
      <el-select
        v-model="selectedPlatform"
        placeholder="选择平台"
        style="width: 140px"
        @change="onPlatformChange"
      >
        <el-option label="抖音" value="douyin" />
        <el-option label="快手" value="kuaishou" />
        <el-option label="小红书" value="xiaohongshu" />
        <el-option label="B站" value="bilibili" />
        <el-option label="视频号" value="tencent" />
      </el-select>
      <el-select
        v-model="selectedAccountId"
        :placeholder="platformPlaceholder"
        clearable
        filterable
        style="width: 260px"
        @change="onAccountChange"
      >
        <el-option
          v-for="acc in filteredAccounts"
          :key="acc.id"
          :label="acc.name"
          :value="acc.id"
        />
      </el-select>
      <el-button
        type="primary"
        :loading="syncing && !batchSyncing"
        :disabled="!selectedAccountId || syncing || pushing"
        @click="handleSync"
      >
        同步
      </el-button>
      <el-button
        :loading="batchSyncing"
        :disabled="syncing || pushing || !pushableAccounts.length"
        @click="openAccountPicker('sync')"
      >
        批量同步
      </el-button>
      <el-button
        :loading="pushing"
        :disabled="syncing || pushing || !pushableAccounts.length"
        @click="openAccountPicker('push')"
      >
        推送到钉钉
      </el-button>
      <span class="sync-meta">{{ syncMetaText }}</span>
    </div>

    <DouyinStatsTable
      v-if="selectedAccountId && selectedPlatform === 'douyin'"
      :items="items"
      :loading="loading || syncing"
      :empty-text="lastSyncedAt ? '暂无作品' : '尚未同步，请点击同步'"
      :display-cover-url="displayCoverUrl"
      :format-percent="formatPercent"
      :has-traffic-expand="hasTrafficExpand"
    />
    <KuaishouStatsTable
      v-else-if="selectedAccountId && selectedPlatform === 'kuaishou'"
      :items="items"
      :loading="loading || syncing"
      :empty-text="lastSyncedAt ? '暂无作品' : '尚未同步，请点击同步'"
      :display-cover-url="displayCoverUrl"
      :format-percent="formatPercent"
      :has-traffic-expand="hasTrafficExpand"
    />
    <el-table
      v-else-if="selectedAccountId"
      :data="items"
      row-key="itemId"
      v-loading="loading || syncing"
      stripe
      style="width: 100%"
      :empty-text="lastSyncedAt ? '暂无作品' : '尚未同步，请点击同步'"
    >
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="traffic-expand" v-if="hasTrafficExpand(row)">
            <div>2s跳出率：{{ formatPercent(row.bounceRate2s) }}</div>
            <div>5s完播率：{{ formatPercent(row.completionRate5s) }}</div>
            <div v-if="row.avgPlayPercent != null">平均播放占比：{{ formatPercent(row.avgPlayPercent) }}</div>
            <div v-if="row.trafficSources && row.trafficSources.length" class="traffic-sources">
              <div class="traffic-sources-title">流量来源</div>
              <div v-for="s in row.trafficSources" :key="s.name" class="traffic-source-row">
                <span>{{ s.name }}</span>
                <span>{{ formatPercent(s.ratio) }}</span>
              </div>
            </div>
            <div v-else class="traffic-sources-empty">暂无流量来源数据</div>
          </div>
          <div v-else class="traffic-expand muted">暂无流量分析数据</div>
        </template>
      </el-table-column>
      <el-table-column label="封面" width="100">
        <template #default="{ row }">
          <el-image
            v-if="row.coverUrl"
            :src="displayCoverUrl(row.coverUrl)"
            fit="cover"
            style="width: 64px; height: 64px; border-radius: 4px"
            :preview-src-list="[displayCoverUrl(row.coverUrl)]"
            referrer-policy="no-referrer"
            preview-teleported
            hide-on-click-modal
          />
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
      <el-table-column prop="publishedAt" label="发布时间" width="170" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="playCount" label="浏览" width="90" />
      <el-table-column prop="likeCount" label="点赞" width="90" />
      <el-table-column prop="commentCount" label="评论" width="90" />
      <el-table-column prop="shareCount" label="分享" width="90" />
      <el-table-column prop="collectCount" label="收藏" width="90" />
      <el-table-column label="完播率" width="100">
        <template #default="{ row }">
          {{ formatPercent(row.completionRate) }}
        </template>
      </el-table-column>
      <el-table-column label="平均时长" width="100">
        <template #default="{ row }">
          {{ row.avgPlayDurationSec != null ? `${row.avgPlayDurationSec}秒` : '—' }}
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-if="!selectedAccountId"
      :description="`请先选择${platformLabel}账号`"
    />

    <el-dialog
      v-model="accountPickerVisible"
      :title="accountPickerMode === 'sync' ? '选择要批量同步的账号' : '选择要推送到钉钉的账号'"
      width="520px"
      destroy-on-close
      :close-on-click-modal="!syncing && !pushing"
      :close-on-press-escape="!syncing && !pushing"
    >
      <div class="push-dialog-toolbar">
        <p class="push-dialog-tip">
          {{
            accountPickerMode === 'sync'
              ? '可跨平台多选；将逐个同步，单个失败不影响其他账号。'
              : '可跨平台多选；未同步过的账号会被跳过。'
          }}
        </p>
        <div class="push-dialog-actions">
          <el-button link type="primary" :disabled="syncing || pushing" @click="selectAllPushAccounts">全选</el-button>
          <el-button link :disabled="syncing || pushing" @click="clearPushAccounts">清空</el-button>
        </div>
      </div>
      <p v-if="batchProgressText" class="batch-progress">{{ batchProgressText }}</p>
      <el-checkbox-group v-model="pushSelectedKeys" class="push-account-list" :disabled="syncing || pushing">
        <div
          v-for="group in pushAccountsByPlatform"
          :key="group.platform"
          class="push-platform-group"
        >
          <div class="push-platform-header">
            <span>{{ group.label }}</span>
            <el-button
              link
              type="primary"
              :disabled="syncing || pushing"
              @click.stop="selectPlatformPushAccounts(group.platform)"
            >
              全选本组
            </el-button>
          </div>
          <el-checkbox
            v-for="acc in group.accounts"
            :key="acc.key"
            :label="acc.key"
            :value="acc.key"
          >
            {{ acc.name }}
          </el-checkbox>
        </div>
      </el-checkbox-group>
      <template #footer>
        <el-button :disabled="syncing || pushing" @click="accountPickerVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="syncing || pushing"
          :disabled="!pushSelectedKeys.length || syncing || pushing"
          @click="confirmAccountPicker"
        >
          {{
            accountPickerMode === 'sync'
              ? `开始同步（已选 ${pushSelectedKeys.length}）`
              : `推送（已选 ${pushSelectedKeys.length}）`
          }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { accountApi } from '@/api/account'
import { statsApi } from '@/api/stats'
import { useAccountStore } from '@/stores/account'
import DouyinStatsTable from '@/components/stats/DouyinStatsTable.vue'
import KuaishouStatsTable from '@/components/stats/KuaishouStatsTable.vue'

const STATS_TYPE_TO_PLATFORM = {
  1: 'xiaohongshu',
  2: 'tencent',
  3: 'douyin',
  4: 'kuaishou',
  6: 'bilibili'
}

const accountStore = useAccountStore()
const selectedPlatform = ref('douyin')
const selectedAccountId = ref(null)
const items = ref([])
const lastSyncedAt = ref(null)
const loading = ref(false)
const syncing = ref(false)
const pushing = ref(false)
const batchSyncing = ref(false)
const accountPickerVisible = ref(false)
const accountPickerMode = ref('push') // 'sync' | 'push'
const pushSelectedKeys = ref([])
const batchProgressText = ref('')
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'

function displayCoverUrl(url) {
  if (!url) return ''
  // B站 CDN 会校验 Referer，浏览器直链常 403，走后端代理
  if (/hdslb\.com/i.test(url)) {
    return `${apiBaseUrl}/proxyImage?url=${encodeURIComponent(url)}`
  }
  return url
}

function formatPercent(v) {
  if (v === null || v === undefined || v === '') return '—'
  return `${v}%`
}

function hasTrafficExpand(row) {
  return (
    row.bounceRate2s != null ||
    row.completionRate5s != null ||
    row.avgPlayPercent != null ||
    (row.boostPlayCount != null && row.boostPlayCount > 0) ||
    (Array.isArray(row.contentDiagnose) && row.contentDiagnose.length > 0) ||
    (Array.isArray(row.metricTrends) && row.metricTrends.length > 0) ||
    (Array.isArray(row.trafficSources) && row.trafficSources.length > 0) ||
    (Array.isArray(row.audienceGender) && row.audienceGender.length > 0) ||
    (Array.isArray(row.audienceAge) && row.audienceAge.length > 0) ||
    (Array.isArray(row.audienceRegion) && row.audienceRegion.length > 0)
  )
}

function statsPlatformOf(acc) {
  if (STATS_TYPE_TO_PLATFORM[acc.type]) return STATS_TYPE_TO_PLATFORM[acc.type]
  if (acc.platform === '小红书') return 'xiaohongshu'
  if (acc.platform === '快手') return 'kuaishou'
  if (acc.platform === 'B站') return 'bilibili'
  if (acc.platform === '抖音') return 'douyin'
  if (acc.platform === '视频号') return 'tencent'
  return null
}

const platformLabel = computed(() => {
  if (selectedPlatform.value === 'kuaishou') return '快手'
  if (selectedPlatform.value === 'xiaohongshu') return '小红书'
  if (selectedPlatform.value === 'bilibili') return 'B站'
  if (selectedPlatform.value === 'tencent') return '视频号'
  return '抖音'
})
const platformPlaceholder = computed(() => `选择${platformLabel.value}账号`)

const filteredAccounts = computed(() => {
  if (selectedPlatform.value === 'kuaishou') {
    return accountStore.accounts.filter((a) => a.platform === '快手' || a.type === 4)
  }
  if (selectedPlatform.value === 'xiaohongshu') {
    return accountStore.accounts.filter((a) => a.platform === '小红书' || a.type === 1)
  }
  if (selectedPlatform.value === 'bilibili') {
    return accountStore.accounts.filter((a) => a.platform === 'B站' || a.type === 6)
  }
  if (selectedPlatform.value === 'tencent') {
    return accountStore.accounts.filter((a) => a.platform === '视频号' || a.type === 2)
  }
  return accountStore.accounts.filter((a) => a.platform === '抖音' || a.type === 3)
})

const PLATFORM_ORDER = [
  { platform: 'douyin', label: '抖音' },
  { platform: 'kuaishou', label: '快手' },
  { platform: 'xiaohongshu', label: '小红书' },
  { platform: 'bilibili', label: 'B站' },
  { platform: 'tencent', label: '视频号' }
]

const pushableAccounts = computed(() => {
  return accountStore.accounts
    .map((acc) => {
      const platform = statsPlatformOf(acc)
      if (!platform) return null
      return {
        key: `${platform}:${acc.id}`,
        accountId: acc.id,
        platform,
        name: acc.name,
        label: `${acc.platform} · ${acc.name}`
      }
    })
    .filter(Boolean)
})

const pushAccountsByPlatform = computed(() => {
  return PLATFORM_ORDER
    .map((meta) => ({
      platform: meta.platform,
      label: meta.label,
      accounts: pushableAccounts.value.filter((a) => a.platform === meta.platform)
    }))
    .filter((group) => group.accounts.length > 0)
})

const syncMetaText = computed(() => {
  if (batchProgressText.value) return batchProgressText.value
  if (!selectedAccountId.value) return ''
  return lastSyncedAt.value ? `最近同步：${lastSyncedAt.value}` : '尚未同步'
})

async function loadAccounts() {
  const res = await accountApi.getAccounts()
  if (res.code === 200) {
    accountStore.setAccounts(res.data || [])
  }
}

async function loadStats() {
  if (!selectedAccountId.value) {
    items.value = []
    lastSyncedAt.value = null
    return
  }
  loading.value = true
  try {
    const res = await statsApi.getContentStats(selectedAccountId.value, selectedPlatform.value)
    items.value = (res.data && res.data.items) || []
    lastSyncedAt.value = (res.data && res.data.lastSyncedAt) || null
  } catch (e) {
    items.value = []
  } finally {
    loading.value = false
  }
}

function onPlatformChange() {
  selectedAccountId.value = null
  items.value = []
  lastSyncedAt.value = null
}

function onAccountChange() {
  loadStats()
}

async function handleSync() {
  if (!selectedAccountId.value) return
  syncing.value = true
  try {
    const res = await statsApi.syncContentStats(
      selectedAccountId.value,
      selectedPlatform.value,
      5
    )
    items.value = (res.data && res.data.items) || []
    lastSyncedAt.value = (res.data && res.data.lastSyncedAt) || null
    if (!items.value.length) {
      ElMessage.success('同步完成：暂无作品')
    } else {
      ElMessage.success(`同步完成：${items.value.length} 条`)
    }
  } catch (e) {
    // request interceptor already toasts; keep cache untouched
  } finally {
    syncing.value = false
  }
}

function openAccountPicker(mode) {
  accountPickerMode.value = mode
  batchProgressText.value = ''
  const defaults = []
  if (selectedAccountId.value) {
    const key = `${selectedPlatform.value}:${selectedAccountId.value}`
    if (pushableAccounts.value.some((a) => a.key === key)) {
      defaults.push(key)
    }
  }
  pushSelectedKeys.value = defaults
  accountPickerVisible.value = true
}

function selectAllPushAccounts() {
  pushSelectedKeys.value = pushableAccounts.value.map((a) => a.key)
}

function selectPlatformPushAccounts(platform) {
  const keys = pushableAccounts.value
    .filter((a) => a.platform === platform)
    .map((a) => a.key)
  const set = new Set(pushSelectedKeys.value)
  keys.forEach((k) => set.add(k))
  pushSelectedKeys.value = Array.from(set)
}

function clearPushAccounts() {
  pushSelectedKeys.value = []
}

function selectedAccountsFromPicker() {
  const keySet = new Set(pushSelectedKeys.value)
  return pushableAccounts.value.filter((a) => keySet.has(a.key))
}

async function confirmAccountPicker() {
  if (accountPickerMode.value === 'sync') {
    await confirmBatchSync()
  } else {
    await confirmPushDingTalk()
  }
}

async function confirmBatchSync() {
  const accounts = selectedAccountsFromPicker()
  if (!accounts.length) return

  syncing.value = true
  batchSyncing.value = true
  let ok = 0
  let fail = 0
  try {
    for (let i = 0; i < accounts.length; i += 1) {
      const acc = accounts[i]
      batchProgressText.value = `正在同步 ${i + 1}/${accounts.length}：${acc.label}`
      try {
        const res = await statsApi.syncContentStats(acc.accountId, acc.platform, 5)
        ok += 1
        if (
          selectedAccountId.value === acc.accountId &&
          selectedPlatform.value === acc.platform
        ) {
          items.value = (res.data && res.data.items) || []
          lastSyncedAt.value = (res.data && res.data.lastSyncedAt) || null
        }
      } catch (e) {
        fail += 1
      }
    }
    accountPickerVisible.value = false
    if (fail === 0) {
      ElMessage.success(`批量同步完成：成功 ${ok} 个账号`)
    } else {
      ElMessage.warning(`批量同步结束：成功 ${ok}，失败 ${fail}`)
    }
  } finally {
    batchProgressText.value = ''
    batchSyncing.value = false
    syncing.value = false
  }
}

async function confirmPushDingTalk() {
  const accounts = selectedAccountsFromPicker().map((a) => ({
    accountId: a.accountId,
    platform: a.platform
  }))
  if (!accounts.length) return

  pushing.value = true
  try {
    const res = await statsApi.pushContentStatsToDingTalk(accounts)
    const accountCount = (res.data && res.data.accountCount) || accounts.length
    const itemCount = (res.data && res.data.itemCount) || 0
    const skipped = (res.data && res.data.skipped) || []
    let msg = `已推送到钉钉：${accountCount} 个账号，共 ${itemCount} 条`
    if (skipped.length) {
      msg += `（跳过 ${skipped.length} 个）`
    }
    ElMessage.success(msg)
    accountPickerVisible.value = false
  } catch (e) {
    // request interceptor already toasts
  } finally {
    pushing.value = false
  }
}

onMounted(async () => {
  await loadAccounts()
})
</script>

<style lang="scss" scoped>
.data-center {
  .page-header {
    margin-bottom: 16px;
    h1 { margin: 0 0 4px; font-size: 22px; }
    .subtitle { margin: 0; color: #909399; font-size: 13px; }
  }
  .toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;
    .sync-meta { color: #909399; font-size: 13px; }
  }
  .traffic-expand {
    padding: 8px 16px 12px 48px;
    font-size: 13px;
    line-height: 1.7;
    color: #606266;
    &.muted { color: #909399; }
    .traffic-sources { margin-top: 8px; }
    .traffic-sources-title { font-weight: 600; margin-bottom: 4px; }
    .traffic-source-row {
      display: flex;
      gap: 16px;
      max-width: 320px;
      justify-content: space-between;
    }
    .traffic-sources-empty { margin-top: 6px; color: #909399; }
  }
  .push-dialog-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }
  .push-dialog-tip {
    margin: 0;
    color: #909399;
    font-size: 13px;
  }
  .batch-progress {
    margin: 0 0 10px;
    color: #409eff;
    font-size: 13px;
  }
  .push-dialog-actions {
    display: flex;
    gap: 4px;
    flex-shrink: 0;
  }
  .push-account-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-height: 420px;
    overflow-y: auto;
    padding: 4px 0;
    :deep(.el-checkbox) {
      margin-right: 0;
      height: auto;
      white-space: normal;
      display: flex;
      margin-bottom: 6px;
    }
  }
  .push-platform-group {
    padding-bottom: 8px;
    border-bottom: 1px solid #ebeef5;
    &:last-child {
      border-bottom: none;
      padding-bottom: 0;
    }
  }
  .push-platform-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
    font-size: 13px;
    font-weight: 600;
    color: #303133;
  }
}
</style>
