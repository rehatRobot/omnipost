<template>
  <div class="creator-center">
    <div class="page-header">
      <h1>创作者中心</h1>
      <p class="page-desc">选择已添加的账号，一键打开对应平台创作者后台</p>
    </div>

    <div class="toolbar">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索账号名称或平台"
        prefix-icon="Search"
        clearable
        style="width: 280px"
      />
      <el-button type="info" @click="fetchAccounts" :loading="loading">
        <el-icon :class="{ 'is-loading': loading }"><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <div v-if="platformGroups.length > 0" class="platform-sections">
      <section
        v-for="group in platformGroups"
        :key="group.platform"
        class="platform-section"
      >
        <div class="section-title">
          <el-tag :type="getPlatformTagType(group.platform)" effect="dark">
            {{ group.platform }}
          </el-tag>
          <span class="section-count">{{ group.accounts.length }} 个账号</span>
        </div>
        <div class="account-row">
          <div
            v-for="account in group.accounts"
            :key="account.id"
            class="account-card"
          >
            <div class="card-top">
              <el-avatar :src="getDefaultAvatar(account.name)" :size="48" />
              <div class="card-meta">
                <div class="account-name" :title="account.name">{{ account.name }}</div>
                <el-tag
                  :type="getStatusTagType(account.status)"
                  size="small"
                  effect="plain"
                >
                  {{ account.status }}
                </el-tag>
              </div>
            </div>
            <el-button
              type="primary"
              size="small"
              :loading="openingId === account.id"
              :disabled="openingId !== null && openingId !== account.id"
              @click="handleOpen(account)"
            >
              <el-icon v-if="openingId !== account.id"><Monitor /></el-icon>
              打开后台
            </el-button>
          </div>
        </div>
      </section>
    </div>

    <div v-else-if="!loading" class="empty-data">
      <el-empty description="暂无账号，请先在「账号管理」中添加">
        <el-button type="primary" @click="$router.push('/account-management')">
          去添加账号
        </el-button>
      </el-empty>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Refresh, Monitor } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { accountApi } from '@/api/account'
import { useAccountStore } from '@/stores/account'

const accountStore = useAccountStore()
const searchKeyword = ref('')
const loading = ref(false)
const openingId = ref(null)

const PLATFORM_ORDER = [
  '抖音',
  '快手',
  '小红书',
  '视频号',
  '百家号',
  'B站',
  '今日头条',
  '搜狐',
  '知乎'
]

const filteredAccounts = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  const list = accountStore.accounts
  if (!keyword) return list
  return list.filter(
    (a) =>
      (a.name || '').toLowerCase().includes(keyword) ||
      (a.platform || '').toLowerCase().includes(keyword)
  )
})

const platformGroups = computed(() => {
  const grouped = new Map()
  for (const account of filteredAccounts.value) {
    const platform = account.platform || '未知'
    if (!grouped.has(platform)) grouped.set(platform, [])
    grouped.get(platform).push(account)
  }
  const ordered = PLATFORM_ORDER
    .filter((name) => grouped.has(name))
    .map((name) => ({ platform: name, accounts: grouped.get(name) }))
  for (const [platform, accounts] of grouped) {
    if (!PLATFORM_ORDER.includes(platform)) {
      ordered.push({ platform, accounts })
    }
  }
  return ordered
})

const getDefaultAvatar = (name) => {
  const initial = (name || '?').charAt(0).toUpperCase()
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80">
    <rect width="80" height="80" fill="#409EFF"/>
    <text x="50%" y="54%" dominant-baseline="middle" text-anchor="middle"
      fill="#fff" font-size="36" font-family="sans-serif">${initial}</text>
  </svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

const getPlatformTagType = (platform) => {
  const map = {
    小红书: 'danger',
    视频号: 'success',
    抖音: '',
    快手: 'warning',
    百家号: 'info',
    B站: 'primary',
    今日头条: 'danger',
    搜狐: 'info',
    知乎: 'primary'
  }
  return map[platform] || 'info'
}

const getStatusTagType = (status) => {
  if (status === '正常') return 'success'
  if (status === '异常') return 'danger'
  return 'warning'
}

const fetchAccounts = async () => {
  loading.value = true
  try {
    const res = await accountApi.getAccounts()
    if (res.code === 200 && res.data) {
      accountStore.setAccounts(res.data)
    }
  } catch (error) {
    console.error('获取账号失败:', error)
  } finally {
    loading.value = false
  }
}

const handleOpen = async (account) => {
  openingId.value = account.id
  try {
    const res = await accountApi.openCreatorCenter(account.id)
    ElMessage.success(res.msg || `正在打开 ${account.platform} 创作者中心`)
  } catch (error) {
    console.error('打开创作者中心失败:', error)
  } finally {
    // 浏览器在后台启动，稍等再解除 loading，避免连点
    setTimeout(() => {
      openingId.value = null
    }, 1500)
  }
}

onMounted(() => {
  fetchAccounts()
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.creator-center {
  .page-header {
    margin-bottom: 20px;

    h1 {
      font-size: 24px;
      color: $text-primary;
      margin: 0 0 8px;
    }

    .page-desc {
      margin: 0;
      color: $text-secondary;
      font-size: 14px;
    }
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding: 16px 20px;
    background: #fff;
    border-radius: 4px;
    box-shadow: $box-shadow-light;

    .el-icon.is-loading {
      animation: rotate 1s linear infinite;
    }
  }

  .platform-sections {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .platform-section {
    background: #fff;
    border-radius: 8px;
    padding: 16px 20px 20px;
    box-shadow: $box-shadow-light;

    .section-title {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 14px;

      .section-count {
        color: $text-secondary;
        font-size: 13px;
      }
    }
  }

  .account-row {
    display: flex;
    flex-wrap: nowrap;
    gap: 12px;
    overflow-x: auto;
  }

  .account-card {
    flex: 0 0 240px;
    background: #f7f8fa;
    border-radius: 8px;
    padding: 16px;
    transition: box-shadow 0.2s, transform 0.2s;

    &:hover {
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
      transform: translateY(-2px);
    }

    .el-button {
      width: 100%;
    }

    .card-top {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;

      .card-meta {
        flex: 1;
        min-width: 0;

        .account-name {
          font-size: 16px;
          font-weight: 600;
          color: $text-primary;
          margin-bottom: 6px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }

  }

  .empty-data {
    padding: 60px 0;
    background: #fff;
    border-radius: 4px;
    box-shadow: $box-shadow-light;
  }
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
