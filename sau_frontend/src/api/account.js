import { http } from '@/utils/request'

// 账号管理相关API
export const accountApi = {
  // 获取有效账号列表（带验证）；type 可选，指定时只校验该平台账号
  getValidAccounts(type) {
    const params = type != null ? { type } : undefined
    return http.get('/getValidAccounts', params)
  },

  // 获取账号列表（不带验证，快速加载）
  getAccounts() {
    return http.get('/getAccounts')
  },

  // 添加账号
  addAccount(data) {
    return http.post('/account', data)
  },

  // 更新账号
  updateAccount(data) {
    return http.post('/updateUserinfo', data)
  },

  // 删除账号
  deleteAccount(id) {
    return http.get(`/deleteAccount?id=${id}`)
  },

  // 打开创作者中心（有头浏览器 + 已保存 cookie）
  openCreatorCenter(id) {
    return http.post('/openCreatorCenter', { id })
  }
}