<template>
  <div class="publish-log-entry">
    <el-button type="primary" plain @click="visible = true">
      <el-icon><Notebook /></el-icon>
      发布记录
      <el-badge v-if="publishLog.count" :value="publishLog.count" class="log-badge" />
    </el-button>

    <el-drawer
      v-model="visible"
      title="发布记录"
      size="480px"
      append-to-body
    >
      <p class="drawer-tip">
        在「发布中心」发布后会自动记到本机浏览器，可在任意页面查看。
      </p>

      <div class="list-toolbar">
        <el-input v-model="keyword" placeholder="搜索平台、账号或内容" clearable />
        <el-button :disabled="!publishLog.count" @click="handleClear">清空</el-button>
      </div>

      <div v-if="filteredRecords.length" class="log-list">
        <div v-for="item in filteredRecords" :key="item.id" class="log-item">
          <div class="log-item-head">
            <el-tag size="small" :type="statusTagType(item.status)">{{ statusText(item.status) }}</el-tag>
            <span class="log-platform">{{ item.platform }}</span>
            <span class="log-time">{{ formatTime(item.createdAt) }}</span>
          </div>
          <div class="log-content">{{ item.content || '未填写内容' }}</div>
          <div v-if="item.account" class="log-meta">账号：{{ item.account }}</div>
          <div v-if="item.message" class="log-meta">{{ item.message }}</div>
          <el-button link type="danger" @click="publishLog.removeRecord(item.id)">删除</el-button>
        </div>
      </div>
      <el-empty v-else description="暂无发布记录，去发布中心发布后会自动出现" />
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Notebook } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePublishLogStore } from '@/stores/publishLog'

const publishLog = usePublishLogStore()
const visible = ref(false)
const keyword = ref('')

const filteredRecords = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  if (!text) return publishLog.records
  return publishLog.records.filter((item) =>
    [item.platform, item.account, item.content, item.message]
      .some((field) => (field || '').toLowerCase().includes(text))
  )
})

const statusText = (status) => {
  const map = {
    success: '成功',
    failed: '失败',
    skipped: '已跳过',
    cancelled: '已取消',
    submitted: '已提交'
  }
  return map[status] || status
}

const statusTagType = (status) => {
  const map = {
    success: 'success',
    failed: 'danger',
    skipped: 'warning',
    cancelled: 'info',
    submitted: 'info'
  }
  return map[status] || 'info'
}

const formatTime = (value) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const handleClear = async () => {
  try {
    await ElMessageBox.confirm('清空后无法恢复，这些记录只存在本机浏览器里。', '清空发布记录', {
      type: 'warning',
      confirmButtonText: '清空',
      cancelButtonText: '取消'
    })
    publishLog.clearRecords()
    ElMessage.success('已清空')
  } catch {
    // 用户取消
  }
}
</script>

<style lang="scss" scoped>
.publish-log-entry {
  .log-badge {
    margin-left: 8px;
  }
}

.drawer-tip {
  margin: 0 0 16px;
  color: #909399;
  font-size: 13px;
}

.list-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.log-item {
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fafafa;

  .log-item-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }

  .log-platform {
    font-weight: 600;
    color: #303133;
  }

  .log-time {
    margin-left: auto;
    color: #909399;
    font-size: 12px;
  }

  .log-content {
    color: #303133;
    margin-bottom: 4px;
  }

  .log-meta {
    color: #606266;
    font-size: 13px;
    line-height: 1.5;
  }
}
</style>
