<template>
  <div class="publish-center">
    <!-- Tab管理区域 -->
    <div class="tab-management">
      <div class="tab-header">
        <div class="tab-list">
          <div 
            v-for="tab in tabs" 
            :key="tab.name"
            :class="['tab-item', { active: activeTab === tab.name }]"
            @click="activeTab = tab.name"
          >
            <span>{{ tab.label }}</span>
            <el-icon 
              v-if="tabs.length > 1"
              class="close-icon" 
              @click.stop="removeTab(tab.name)"
            >
              <Close />
            </el-icon>
          </div>
        </div>
        <div class="tab-actions">
          <el-button 
            type="primary" 
            size="small" 
            @click="addTab"
            class="add-tab-btn"
          >
            <el-icon><Plus /></el-icon>
            添加Tab
          </el-button>
          <el-button 
            type="success" 
            size="small" 
            @click="batchPublish"
            :loading="batchPublishing"
            class="batch-publish-btn"
          >
            批量发布
          </el-button>
        </div>
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="publish-content">
      <div class="tab-content-wrapper">
        <div 
          v-for="tab in tabs" 
          :key="tab.name"
          v-show="activeTab === tab.name"
          class="tab-content"
        >
          <!-- 发布状态提示 -->
          <div v-if="tab.publishStatus" class="publish-status">
            <el-alert
              :title="tab.publishStatus.message"
              :type="tab.publishStatus.type"
              :closable="false"
              show-icon
            />
          </div>

          <!-- 发布结果明细（按 视频×账号） -->
          <div v-if="tab.publishJob" class="publish-job-panel">
            <div class="publish-job-header">
              <h3>发布结果</h3>
              <el-tag :type="publishJobTagType(tab.publishJob.status)" size="small">
                {{ publishJobStatusText(tab.publishJob) }}
              </el-tag>
            </div>
            <el-table
              :data="tab.publishJob.results || []"
              size="small"
              border
              stripe
              max-height="280"
              empty-text="暂无明细"
            >
              <el-table-column prop="fileName" label="视频/内容" min-width="160" show-overflow-tooltip />
              <el-table-column prop="accountName" label="账号" min-width="100" show-overflow-tooltip />
              <el-table-column label="状态" width="90">
                <template #default="{ row }">
                  <el-tag :type="resultStatusTagType(row.status)" size="small">
                    {{ resultStatusText(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="message" label="说明" min-width="180" show-overflow-tooltip />
            </el-table>
          </div>

          <!-- 视频上传区域：文章模式隐藏 -->
          <div v-if="!isArticleTab(tab)" class="upload-section">
            <h3>视频</h3>
            <div class="upload-options">
              <el-button type="primary" @click="showUploadOptions(tab)" class="upload-btn">
                <el-icon><Upload /></el-icon>
                上传视频
              </el-button>
            </div>

            <!-- 已上传文件列表 -->
            <div v-if="tab.fileList.length > 0" class="uploaded-files">
              <h4>已上传文件：</h4>
              <div class="file-list">
                <div v-for="(file, index) in tab.fileList" :key="index" class="file-item">
                  <el-link :href="file.url" target="_blank" type="primary">{{ file.name }}</el-link>
                  <span class="file-size">{{ (file.size / 1024 / 1024).toFixed(2) }}MB</span>
                  <el-button type="danger" size="small" @click="removeFile(tab, index)">删除</el-button>
                </div>
              </div>
            </div>
          </div>

          <!-- 上传选项弹窗 -->
          <el-dialog
            v-model="uploadOptionsVisible"
            title="选择上传方式"
            width="400px"
            class="upload-options-dialog"
          >
            <div class="upload-options-content">
              <el-button type="primary" @click="selectLocalUpload" class="option-btn">
                <el-icon><Upload /></el-icon>
                本地上传
              </el-button>
              <el-button type="success" @click="selectMaterialLibrary" class="option-btn">
                <el-icon><Folder /></el-icon>
                素材库
              </el-button>
            </div>
          </el-dialog>

          <!-- 本地上传弹窗 -->
          <el-dialog
            v-model="localUploadVisible"
            title="本地上传"
            width="600px"
            class="local-upload-dialog"
          >
            <el-upload
              class="video-upload"
              drag
              :auto-upload="true"
              :action="`${apiBaseUrl}/upload`"
              :on-success="(response, file) => handleUploadSuccess(response, file, currentUploadTab)"
              :on-error="handleUploadError"
              multiple
              accept="video/*"
              :headers="authHeaders"
            >
              <el-icon class="el-icon--upload"><Upload /></el-icon>
              <div class="el-upload__text">
                将视频文件拖到此处，或<em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持MP4、AVI等视频格式，可上传多个文件
                </div>
              </template>
            </el-upload>
          </el-dialog>

          <!-- 批量发布进度对话框 -->
          <el-dialog
            v-model="batchPublishDialogVisible"
            title="批量发布进度"
            width="500px"
            :close-on-click-modal="false"
            :close-on-press-escape="false"
            :show-close="false"
          >
            <div class="publish-progress">
              <el-progress 
                :percentage="publishProgress"
                :status="publishProgress === 100 ? 'success' : ''"
              />
              <div v-if="currentPublishingTab" class="current-publishing">
                正在发布：{{ currentPublishingTab.label }}
              </div>
              
              <!-- 发布结果列表 -->
              <div class="publish-results" v-if="publishResults.length > 0">
                <div 
                  v-for="(result, index) in publishResults" 
                  :key="index"
                  :class="['result-item', result.status]"
                >
                  <el-icon v-if="result.status === 'success'"><Check /></el-icon>
                  <el-icon v-else-if="result.status === 'error'"><Close /></el-icon>
                  <el-icon v-else><InfoFilled /></el-icon>
                  <span class="label">{{ result.label }}</span>
                  <span class="message">{{ result.message }}</span>
                </div>
              </div>
            </div>
            
            <template #footer>
              <div class="dialog-footer">
                <el-button 
                  @click="cancelBatchPublish" 
                  :disabled="publishProgress === 100"
                >
                  取消发布
                </el-button>
                <el-button 
                  type="primary" 
                  @click="batchPublishDialogVisible = false"
                  v-if="publishProgress === 100"
                >
                  关闭
                </el-button>
              </div>
            </template>
          </el-dialog>

          <!-- 素材库选择弹窗 -->
          <el-dialog
            v-model="materialLibraryVisible"
            title="选择素材"
            width="800px"
            class="material-library-dialog"
          >
            <div class="material-library-content">
              <el-checkbox-group v-model="selectedMaterials">
                <div class="material-list">
                  <div
                    v-for="material in materials"
                    :key="material.id"
                    class="material-item"
                  >
                    <el-checkbox :label="material.id" class="material-checkbox">
                      <div class="material-info">
                        <div class="material-name">{{ material.filename }}</div>
                        <div class="material-details">
                          <span class="file-size">{{ material.filesize }}MB</span>
                          <span class="upload-time">{{ material.upload_time }}</span>
                        </div>
                      </div>
                    </el-checkbox>
                  </div>
                </div>
              </el-checkbox-group>
            </div>
            <template #footer>
              <div class="dialog-footer">
                <el-button @click="materialLibraryVisible = false">取消</el-button>
                <el-button type="primary" @click="confirmMaterialSelection">确定</el-button>
              </div>
            </template>
          </el-dialog>

          <!-- 账号选择 -->
          <div class="account-section">
            <h3>账号</h3>
            <div class="account-display">
              <div class="selected-accounts">
                <el-tag
                  v-for="(account, index) in tab.selectedAccounts"
                  :key="index"
                  closable
                  @close="removeAccount(tab, index)"
                  class="account-tag"
                >
                  {{ getAccountDisplayName(account) }}
                </el-tag>
              </div>
              <el-button 
                type="primary" 
                plain 
                @click="openAccountDialog(tab)"
                class="select-account-btn"
              >
                选择账号
              </el-button>
            </div>
          </div>

          <!-- 账号选择弹窗 -->
          <el-dialog
            v-model="accountDialogVisible"
            title="选择账号"
            width="600px"
            class="account-dialog"
          >
            <div class="account-dialog-content">
              <el-checkbox-group v-model="tempSelectedAccounts">
                <div class="account-list">
                  <el-checkbox
                    v-for="account in availableAccounts"
                    :key="account.id"
                    :label="account.id"
                    class="account-item"
                  >
                    <div class="account-info">
                      <span class="account-name">{{ account.name }}</span>                      
                    </div>
                  </el-checkbox>
                </div>
              </el-checkbox-group>
            </div>

            <template #footer>
              <div class="dialog-footer">
                <el-button @click="accountDialogVisible = false">取消</el-button>
                <el-button type="primary" @click="confirmAccountSelection">确定</el-button>
              </div>
            </template>
          </el-dialog>

          <!-- 平台选择 -->
          <div class="platform-section">
            <h3>平台</h3>
            <el-radio-group v-model="tab.selectedPlatform" class="platform-radios" @change="() => onPlatformChange(tab)">
              <el-radio
                v-for="platform in platforms"
                :key="platform.key"
                :label="platform.key"
                class="platform-radio"
              >
                {{ platform.name }}
              </el-radio>
            </el-radio-group>
          </div>

          <!-- 百家号 / 今日头条 / 搜狐 / 知乎：内容类型 -->
          <div v-if="articleCapablePlatforms.includes(tab.selectedPlatform)" class="content-type-section">
            <h3>内容类型</h3>
            <el-radio-group v-model="tab.contentType" class="content-type-radios" @change="() => onContentTypeChange(tab)">
              <el-radio v-if="!articleOnlyPlatforms.includes(tab.selectedPlatform)" label="video">视频</el-radio>
              <el-radio label="article">图文文章</el-radio>
            </el-radio-group>
            <div v-if="tab.selectedPlatform === 8" class="optional-hint">搜狐号第一期仅支持图文文章（mp.sohu.com）</div>
            <div v-else-if="tab.selectedPlatform === 9" class="optional-hint">知乎第一期仅支持文章（zhuanlan.zhihu.com/write）</div>
            <div v-else-if="tab.selectedPlatform === 7" class="optional-hint">文章走创作者后台「发文章」，不做微头条</div>
            <div v-else class="optional-hint">文章走百家号后台「图文」，标题需 2-64 字</div>
          </div>

          <!-- 标题输入（小红书/视频号/抖音/快手非必填） -->
          <div class="title-section">
            <h3>标题<span v-if="tab.selectedPlatform === 1 || tab.selectedPlatform === 2 || tab.selectedPlatform === 3 || tab.selectedPlatform === 4" class="optional-hint">（选填）</span><span v-else-if="tab.selectedPlatform === 8" class="optional-hint">（必填，5-72字）</span><span v-else-if="tab.selectedPlatform === 9" class="optional-hint">（必填，最多100字）</span><span v-else-if="tab.selectedPlatform === 5 && tab.contentType === 'article'" class="optional-hint">（必填，2-64字）</span><span v-else-if="tab.selectedPlatform === 7 && tab.contentType === 'article'" class="optional-hint">（必填，最多30字）</span></h3>
            <el-input
              v-model="tab.title"
              type="textarea"
              :rows="3"
              :placeholder="(tab.selectedPlatform === 1 || tab.selectedPlatform === 2 || tab.selectedPlatform === 3 || tab.selectedPlatform === 4) ? '请输入标题（可不填）' : (tab.selectedPlatform === 8 ? '请输入标题（5-72字）' : (tab.selectedPlatform === 9 ? '请输入标题（最多100字）' : '请输入标题'))"
              :maxlength="tab.selectedPlatform === 7 && tab.contentType === 'article' ? 30 : (tab.selectedPlatform === 8 ? 72 : (tab.selectedPlatform === 9 ? 100 : 100))"
              show-word-limit
              class="title-input"
            />
          </div>

          <!-- 图文文章正文：紧挨标题下方 -->
          <div v-if="isArticleTab(tab)" class="article-body-section">
            <h3>正文<span class="optional-hint">（必填，纯文本，换行保留）</span></h3>
            <el-input
              v-model="tab.articleBody"
              type="textarea"
              :rows="12"
              placeholder="请输入文章正文"
              maxlength="20000"
              show-word-limit
              class="article-body-input"
            />
          </div>

          <!-- 图文文章封面：正文下方 -->
          <div v-if="isArticleTab(tab)" class="article-cover-section">
            <h3>
              展示封面
              <span v-if="tab.selectedPlatform === 5" class="optional-hint">（必填，单图；JPEG/PNG，最大 5MB）</span>
              <span v-else-if="tab.selectedPlatform === 8" class="optional-hint">（选填；尺寸大于 450×300，jpg/jpeg/png，最大 10MB）</span>
              <span v-else-if="tab.selectedPlatform === 9" class="optional-hint">（选填，单图；JPEG/PNG，最大 10MB）</span>
              <span v-else class="optional-hint">（选填，单图；JPEG/PNG，最大 20MB）</span>
            </h3>
            <el-radio-group v-model="tab.coverMode" class="cover-mode-radios">
              <el-radio label="single">{{ tab.selectedPlatform === 8 ? '上传封面' : '单图' }}</el-radio>
              <el-radio v-if="tab.selectedPlatform !== 5" label="none">无封面</el-radio>
            </el-radio-group>

            <!-- 搜狐：封面（后台弹窗最多 1 张） -->
            <div v-if="tab.coverMode === 'single' && tab.selectedPlatform === 8" class="article-cover-upload-wrap sohu-multi-cover">
              <div class="sohu-cover-list">
                <div
                  v-for="(img, idx) in tab.coverImages"
                  :key="img.path || idx"
                  class="cover-preview-box sohu-cover-item"
                >
                  <img :src="img.previewUrl" alt="封面预览" class="cover-preview-img" />
                  <div class="cover-preview-mask">
                    <span @click.stop="removeSohuCover(tab, idx)">删除</span>
                  </div>
                </div>
                <el-upload
                  v-if="!(tab.coverImages && tab.coverImages.length)"
                  class="article-cover-upload"
                  :show-file-list="false"
                  :auto-upload="true"
                  accept="image/jpeg,image/jpg,image/png,.jpg,.jpeg,.png"
                  :action="`${apiBaseUrl}/upload`"
                  :headers="authHeaders"
                  :before-upload="(file) => beforeCoverUpload(file, tab)"
                  :on-success="(response, file) => handleSohuCoverUploadSuccess(response, file, tab)"
                  :on-error="handleCoverUploadError"
                >
                  <div class="cover-plus-box">
                    <el-icon :size="28"><Plus /></el-icon>
                  </div>
                </el-upload>
              </div>
              <div class="cover-tip">封面图片尺寸应大于 450×300，最大 10M，格式限制：jpg、jpeg、png</div>
            </div>

            <!-- 其它平台：单图封面 -->
            <div v-else-if="tab.coverMode === 'single'" class="article-cover-upload-wrap">
              <el-upload
                class="article-cover-upload"
                :show-file-list="false"
                :auto-upload="true"
                accept="image/jpeg,image/jpg,image/png,.jpg,.jpeg,.png"
                :action="`${apiBaseUrl}/upload`"
                :headers="authHeaders"
                :before-upload="(file) => beforeCoverUpload(file, tab)"
                :on-success="(response, file) => handleCoverUploadSuccess(response, file, tab)"
                :on-error="handleCoverUploadError"
              >
                <div v-if="tab.coverPreviewUrl" class="cover-preview-box">
                  <img :src="tab.coverPreviewUrl" alt="封面预览" class="cover-preview-img" />
                  <div class="cover-preview-mask">
                    <span>更换封面</span>
                  </div>
                </div>
                <div v-else class="cover-plus-box">
                  <el-icon :size="28"><Plus /></el-icon>
                </div>
              </el-upload>
              <div class="cover-side-actions">
                <el-button
                  v-if="tab.coverPreviewUrl"
                  type="primary"
                  link
                  @click="previewArticleCover(tab)"
                >
                  预览
                </el-button>
                <el-button
                  v-if="tab.coverImage"
                  type="danger"
                  link
                  @click="clearArticleCover(tab)"
                >
                  删除
                </el-button>
              </div>
              <div class="cover-tip">{{ tab.selectedPlatform === 5 ? '优质的封面有利于推荐，格式支持 JPEG、PNG，单张最大 5MB' : (tab.selectedPlatform === 9 ? '优质的封面有利于推荐，格式支持 JPEG、PNG，单张最大 10MB' : '优质的封面有利于推荐，格式支持 JPEG、PNG，单张最大 20MB') }}</div>
              <div v-if="tab.coverFileName" class="cover-file-name">{{ tab.coverFileName }}</div>
            </div>
          </div>

          <!-- 今日头条图文作品声明：封面下方（创作者后台为单选） -->
          <div v-if="tab.selectedPlatform === 7 && tab.contentType === 'article'" class="work-statement-section">
            <h3>
              作品声明
              <span class="optional-hint">（选填，单选）</span>
            </h3>
            <el-radio-group v-model="tab.workStatement" class="work-statement-group">
              <el-radio label="">不声明</el-radio>
              <el-radio
                v-for="opt in toutiaoWorkStatementOptions"
                :key="opt"
                :label="opt"
              >
                {{ opt }}
              </el-radio>
            </el-radio-group>
          </div>

          <!-- 搜狐号图文信息来源：封面下方（创作者后台为单选） -->
          <div v-if="tab.selectedPlatform === 8" class="work-statement-section">
            <h3>
              信息来源
              <span class="optional-hint">（单选，默认无特别声明）</span>
            </h3>
            <el-radio-group v-model="tab.workStatement" class="work-statement-group">
              <el-radio
                v-for="opt in sohuInfoSourceOptions"
                :key="opt"
                :label="opt"
              >
                {{ opt }}
              </el-radio>
            </el-radio-group>
          </div>

          <!-- 知乎图文创作声明：封面下方（写文章页下拉） -->
          <div v-if="tab.selectedPlatform === 9" class="work-statement-section">
            <h3>
              创作声明
              <span class="optional-hint">（下拉单选，默认无声明）</span>
            </h3>
            <el-select
              v-model="tab.workStatement"
              placeholder="选择创作声明"
              class="bilibili-creation-select"
            >
              <el-option
                v-for="opt in zhihuCreationStatementOptions"
                :key="opt"
                :label="opt"
                :value="opt"
              />
            </el-select>
          </div>

          <!-- 原创声明 (仅在视频号可见，其它平台无对应实现) -->
          <div v-if="tab.selectedPlatform === 2" class="original-section">
            <el-checkbox
              v-model="tab.isOriginal"
              label="声明原创"
              class="original-checkbox"
            />
          </div>

          <!-- 草稿选项 (仅在视频号可见) -->
          <div v-if="tab.selectedPlatform === 2" class="draft-section">
            <el-checkbox
              v-model="tab.isDraft"
              label="视频号仅保存草稿(用手机发布)"
              class="draft-checkbox"
            />
          </div>

          <!-- 自主声明/作者声明/内容类型声明/视频标注：AI生成 -->
          <div v-if="tab.selectedPlatform === 1 || tab.selectedPlatform === 2 || tab.selectedPlatform === 3 || tab.selectedPlatform === 4" class="ai-declaration-section">
            <el-checkbox
              v-model="tab.aiGenerated"
              :label="tab.selectedPlatform === 2 ? '视频标注：含AI生成内容' : tab.selectedPlatform === 4 ? '作者声明：内容为AI生成' : tab.selectedPlatform === 1 ? '内容类型声明：笔记含AI合成内容' : '自主声明：内容由AI生成'"
              class="ai-declaration-checkbox"
            />
          </div>

          <!-- B站创作声明（通过 biliup --extra-fields 提交） -->
          <div v-if="tab.selectedPlatform === 6" class="bilibili-creation-section">
            <h3>创作声明</h3>
            <el-select
              v-model="tab.bilibiliCreationStatement"
              placeholder="选择创作声明"
              clearable
              class="bilibili-creation-select"
            >
              <el-option
                v-for="opt in bilibiliCreationOptions"
                :key="String(opt.value)"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
            <div class="optional-hint">对应 B 站投稿页「创作声明」；通过 biliup 的 --extra-fields 提交</div>
          </div>

          <!-- 仅预览不发布：B站无浏览器可预览，不展示该开关 -->
          <div v-if="tab.selectedPlatform !== 6" class="dry-run-section">
            <el-checkbox
              v-model="tab.dryRun"
              label="仅预览不发布（填完表后停住，方便核对）"
              class="dry-run-checkbox"
            />
          </div>

          <!-- 标签 (仅在抖音可见) -->
          <div v-if="tab.selectedPlatform === 3" class="product-section">
            <h3>商品链接</h3>
            <el-input
              v-model="tab.productTitle"
              type="text"
              :rows="1"
              placeholder="请输入商品名称"
              maxlength="200"
              class="product-name-input"
            />
            <el-input
              v-model="tab.productLink"
              type="text"
              :rows="1"
              placeholder="请输入商品链接"
              maxlength="200"
              class="product-link-input"
            />
          </div>

          <!-- 话题输入 -->
          <div class="topic-section">
            <h3>
              话题
              <span class="optional-hint">{{ getTopicCountHint(tab.selectedPlatform) }}</span>
            </h3>
            <div class="topic-display">
              <div class="selected-topics">
                <el-tag
                  v-for="(topic, index) in tab.selectedTopics"
                  :key="index"
                  closable
                  @close="removeTopic(tab, index)"
                  class="topic-tag"
                >
                  #{{ topic }}
                </el-tag>
              </div>
              <div class="topic-actions">
                <el-button
                  type="success"
                  plain
                  @click="randomPickTopics(tab)"
                  class="select-topic-btn"
                >
                  随机抽取
                </el-button>
                <el-button
                  type="primary"
                  plain
                  @click="openTopicDialog(tab)"
                  class="select-topic-btn"
                >
                  添加话题
                </el-button>
              </div>
            </div>
          </div>

          <!-- 添加话题弹窗 -->
          <el-dialog
            v-model="topicDialogVisible"
            title="添加话题"
            width="600px"
            class="topic-dialog"
          >
            <div class="topic-dialog-content">
              <!-- 自定义话题输入 -->
              <div class="custom-topic-input">
                <el-input
                  v-model="customTopic"
                  placeholder="输入自定义话题"
                  class="custom-input"
                >
                  <template #prepend>#</template>
                </el-input>
                <el-button type="primary" @click="addCustomTopic">添加</el-button>
              </div>

              <!-- 推荐话题 -->
              <div class="recommended-topics">
                <h4>推荐话题</h4>
                <div class="topic-grid">
                  <el-button
                    v-for="topic in recommendedTopics"
                    :key="topic"
                    :type="currentTab?.selectedTopics?.includes(topic) ? 'primary' : 'default'"
                    @click="toggleRecommendedTopic(topic)"
                    class="topic-btn"
                  >
                    {{ topic }}
                  </el-button>
                </div>
              </div>
            </div>

            <template #footer>
              <div class="dialog-footer">
                <el-button @click="topicDialogVisible = false">取消</el-button>
                <el-button type="primary" @click="confirmTopicSelection">确定</el-button>
              </div>
            </template>
          </el-dialog>

          <!-- 定时发布 -->
          <div class="schedule-section">
            <h3>定时发布</h3>
            <div class="schedule-controls">
              <el-switch
                v-model="tab.scheduleEnabled"
                active-text="定时发布"
                inactive-text="立即发布"
              />
              <div v-if="tab.scheduleEnabled" class="schedule-settings">
                <div class="schedule-item">
                  <span class="label">每天发布视频数：</span>
                  <el-select v-model="tab.videosPerDay" placeholder="选择发布数量">
                    <el-option
                      v-for="num in 55"
                      :key="num"
                      :label="num"
                      :value="num"
                    />
                  </el-select>
                </div>
                <div class="schedule-item">
                  <span class="label">每天发布时间：</span>
                  <el-time-select
                    v-for="(time, index) in tab.dailyTimes"
                    :key="index"
                    v-model="tab.dailyTimes[index]"
                    start="00:00"
                    step="00:30"
                    end="23:30"
                    placeholder="选择时间"
                  />
                  <el-button
                    v-if="tab.dailyTimes.length < tab.videosPerDay"
                    type="primary"
                    size="small"
                    @click="tab.dailyTimes.push('10:00')"
                  >
                    添加时间
                  </el-button>
                </div>
                <div class="schedule-item">
                  <span class="label">起始日期：</span>
                  <el-date-picker
                    v-model="tab.startDate"
                    type="date"
                    placeholder="选择起始日期"
                    format="YYYY年MM月DD日"
                    value-format="YYYY-MM-DD"
                    :disabled-date="disabledScheduleStartDate"
                    :clearable="false"
                  />
                  <span class="schedule-hint">从该日起按每日时刻依次排期</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="action-buttons">
            <el-button size="small" @click="cancelPublish(tab)">取消</el-button>
            <el-button
              size="small"
              type="primary"
              @click="confirmPublish(tab)"
              :loading="tab.publishing || false"
            >
              {{ tab.publishing ? '发布中...' : '发布' }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { Upload, Plus, Close, Folder } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAccountStore, PLATFORM_TYPES } from '@/stores/account'
import { usePublishLogStore } from '@/stores/publishLog'
import { useAppStore } from '@/stores/app'
import { materialApi } from '@/api/material'
import { accountApi } from '@/api/account'
import { http } from '@/utils/request'

// API base URL
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'

// Authorization headers
const authHeaders = computed(() => ({
  'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
}))

// 当前激活的tab
const activeTab = ref('tab1')

// tab计数器
let tabCounter = 1

// 获取应用状态管理
const appStore = useAppStore()
const accountStore = useAccountStore()
const publishLog = usePublishLogStore()

// 上传相关状态
const uploadOptionsVisible = ref(false)
const localUploadVisible = ref(false)
const materialLibraryVisible = ref(false)
const currentUploadTab = ref(null)
const selectedMaterials = ref([])
const materials = computed(() => appStore.materials)

// 批量发布相关状态
const batchPublishing = ref(false)
const batchPublishMessage = ref('')
const batchPublishType = ref('info')

// 平台列表 - 对应后端type字段
const platforms = [
  { key: 3, name: '抖音' },
  { key: 4, name: '快手' },
  { key: 1, name: '小红书' },
  { key: 6, name: 'B站' },
  { key: 2, name: '视频号' },
  { key: 5, name: '百家号' },
  { key: 7, name: '今日头条' },
  { key: 8, name: '搜狐' },
  { key: 9, name: '知乎' }
]

const defaultTabInit = {
  name: 'tab1',
  label: '发布1',
  fileList: [], // 后端返回的文件名列表
  displayFileList: [], // 用于显示的文件列表
  selectedAccounts: [], // 选中的账号ID列表
  selectedPlatform: 3, // 默认选中抖音（单选）
  title: '',
  productLink: '', // 商品链接
  productTitle: '', // 商品名称
  selectedTopics: [], // 话题列表（不带#号）
  scheduleEnabled: false, // 定时发布开关
  videosPerDay: 1, // 每天发布视频数量
  dailyTimes: ['10:00'], // 每天发布时间点列表
  startDate: '', // 定时发布起始日期 YYYY-MM-DD，提交时换算为 startDays
  publishStatus: null, // 发布状态，包含message和type
  publishJob: null, // 后台任务结果 { jobId, status, results, ... }
  publishing: false, // 发布状态，用于控制按钮loading效果
  isDraft: false, // 是否保存为草稿，仅视频号平台可见
  isOriginal: true, // 是否标记为原创（视频号，默认勾选）
  aiGenerated: true, // 抖音/快手/小红书/视频号 AI 内容声明（默认勾选）
  // B站创作声明：null=不传；-1无需标注；1=AI；2=虚构演绎；3=营销；4=个人观点
  bilibiliCreationStatement: 1,
  dryRun: false, // 仅预览不发布：默认关闭；B站走 CLI，勾选后会直接跳过上传
  contentType: 'video', // 今日头条：video | article
  articleBody: '', // 今日头条文章正文
  // 今日头条图文封面：single=单图，none=无封面
  coverMode: 'single',
  coverImage: '', // 后端 videoFile 下文件名（单图平台）
  coverImages: [], // 搜狐多图封面：[{ path, name, previewUrl }]
  coverPreviewUrl: '',
  coverFileName: '',
  // 今日头条图文作品声明（单选；空字符串=不声明）
  // 搜狐号复用该字段表示「信息来源」，默认「无特别声明」
  // 知乎复用该字段表示「创作声明」，默认「无声明」
  workStatement: ''
}

// B站创作声明选项（creation_statement.id）
const bilibiliCreationOptions = [
  { label: '含 AI 生成内容', value: 1 },
  { label: '含虚构演绎内容', value: 2 },
  { label: '内容含营销信息', value: 3 },
  { label: '个人观点，仅供参考', value: 4 },
  { label: '内容无需标注', value: -1 }
]

// 支持「视频 / 图文文章」两种内容类型的平台：5=百家号，7=今日头条；8=搜狐 / 9=知乎（仅图文）
const articleCapablePlatforms = [5, 7, 8, 9]
const articleOnlyPlatforms = [8, 9]

const onContentTypeChange = (tab) => {
  if (articleOnlyPlatforms.includes(tab.selectedPlatform)) {
    tab.contentType = 'article'
  }
}

const onPlatformChange = (tab) => {
  if (articleOnlyPlatforms.includes(tab.selectedPlatform)) {
    tab.contentType = 'article'
    // 搜狐默认信息来源 / 知乎默认创作声明
    if (tab.selectedPlatform === 8) {
      if (!sohuInfoSourceOptions.includes(tab.workStatement)) {
        tab.workStatement = '无特别声明'
      }
    } else if (tab.selectedPlatform === 9) {
      if (!zhihuCreationStatementOptions.includes(tab.workStatement)) {
        tab.workStatement = '无声明'
      }
    } else if (
      sohuInfoSourceOptions.includes(tab.workStatement) ||
      zhihuCreationStatementOptions.includes(tab.workStatement)
    ) {
      tab.workStatement = ''
    }
  } else if (tab.selectedPlatform === 7) {
    // 切回头条时，若之前是搜狐/知乎选项则清空
    if (
      sohuInfoSourceOptions.includes(tab.workStatement) ||
      zhihuCreationStatementOptions.includes(tab.workStatement)
    ) {
      tab.workStatement = ''
    }
  } else if (
    sohuInfoSourceOptions.includes(tab.workStatement) ||
    zhihuCreationStatementOptions.includes(tab.workStatement)
  ) {
    tab.workStatement = ''
  }
}

// 当前 tab 是否处于图文文章模式
const isArticleTab = (tab) =>
  articleCapablePlatforms.includes(tab.selectedPlatform) && tab.contentType === 'article'

// 今日头条图文「作品声明」选项
const toutiaoWorkStatementOptions = [
  '取材网络',
  '引用站内',
  '个人观点，仅供参考',
  '引用AI',
  '虚构演绎，故事经历',
  '投资观点，仅供参考',
  '健康医疗分享，仅供参考'
]

// 搜狐号图文「信息来源」选项
const sohuInfoSourceOptions = [
  '无特别声明',
  '引用声明',
  '包含AI创作内容',
  '包含虚构创作'
]

// 知乎图文「创作声明」选项（写文章页下拉）
const zhihuCreationStatementOptions = [
  '包含剧透',
  '包含医疗建议',
  '虚构创作',
  '包含理财内容',
  '包含 AI 辅助创作 作者对内容负责',
  '无声明'
]

const SCHEDULE_MAX_AHEAD_DAYS = 14

const formatLocalDate = (date) => {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const getDefaultStartDate = () => {
  const date = new Date()
  date.setHours(0, 0, 0, 0)
  date.setDate(date.getDate() + 1)
  return formatLocalDate(date)
}

const parseLocalDate = (dateStr) => {
  const [y, m, d] = String(dateStr).split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** 后端 startDays：0=明天，1=后天；由起始日期换算 */
const startDateToStartDays = (dateStr) => {
  if (!dateStr) return 0
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const selected = parseLocalDate(dateStr)
  const diffDays = Math.round((selected - today) / 86400000)
  return Math.max(0, diffDays - 1)
}

const disabledScheduleStartDate = (date) => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const min = new Date(today)
  min.setDate(min.getDate() + 1)
  const max = new Date(today)
  max.setDate(max.getDate() + SCHEDULE_MAX_AHEAD_DAYS)
  const t = date.getTime()
  return t < min.getTime() || t > max.getTime()
}

// helper to create a fresh deep-copied tab from defaultTabInit
const makeNewTab = () => {
  // prefer structuredClone when available (newer browsers/node), fallback to JSON
  let tab
  try {
    tab = typeof structuredClone === 'function' ? structuredClone(defaultTabInit) : JSON.parse(JSON.stringify(defaultTabInit))
  } catch (e) {
    tab = JSON.parse(JSON.stringify(defaultTabInit))
  }
  tab.startDate = getDefaultStartDate()
  return tab
}

const PLATFORM_TYPE_NAME = {
  1: '小红书',
  2: '视频号',
  3: '抖音',
  4: '快手',
  5: '百家号',
  6: 'B站',
  7: '今日头条',
  8: '搜狐',
  9: '知乎'
}

const syncDisplayFileList = (tab) => {
  tab.displayFileList = [...(tab.fileList || []).map((item) => ({
    name: item.name,
    url: item.url
  }))]
}

const getAccountIdsForPlatform = (platformType) => {
  return accountStore.accounts
    .filter((acc) => Number(acc.type) === Number(platformType))
    .map((acc) => acc.id)
}

/** 为发布页分配账号：优先用户已选，不足时用同平台其余账号补齐，再按序取一个 */
const pickAccountIdForIndex = (platformType, preferredIds, index) => {
  const allIds = getAccountIdsForPlatform(platformType)
  if (!allIds.length) return null
  const preferred = (preferredIds || []).filter((id) => allIds.includes(id))
  const rest = allIds.filter((id) => !preferred.includes(id))
  const pool = preferred.length ? [...preferred, ...rest] : allIds
  return pool[index % pool.length]
}

const copyTabPublishSettings = (fromTab, toTab) => {
  toTab.selectedPlatform = fromTab.selectedPlatform
  toTab.title = fromTab.title
  // 话题不直接复制：多视频拆页时每个发布页各自随机，避免全部相同
  toTab.selectedTopics = []
  toTab.scheduleEnabled = fromTab.scheduleEnabled
  toTab.videosPerDay = fromTab.videosPerDay
  toTab.dailyTimes = [...(fromTab.dailyTimes || ['10:00'])]
  toTab.startDate = fromTab.startDate
  toTab.aiGenerated = fromTab.aiGenerated
  toTab.isDraft = fromTab.isDraft
  toTab.isOriginal = fromTab.isOriginal
  toTab.dryRun = fromTab.dryRun
  toTab.productLink = fromTab.productLink
  toTab.productTitle = fromTab.productTitle
  toTab.bilibiliCreationStatement = fromTab.bilibiliCreationStatement
  toTab.contentType = fromTab.contentType || 'video'
  toTab.workStatement = fromTab.workStatement
}

/**
 * 同一发布页选了多个视频时：按视频数拆成多个发布页，
 * 平台与配置沿用当前页，每个页 1 个视频 + 1 个同平台账号。
 */
const expandVideosToTabs = (sourceTab) => {
  if (!sourceTab || isArticleTab(sourceTab)) return 0
  const files = [...(sourceTab.fileList || [])]
  if (files.length === 0) return 0

  const preferredAccountIds = [...(sourceTab.selectedAccounts || [])]
  const platformAccountIds = getAccountIdsForPlatform(sourceTab.selectedPlatform)

  if (files.length === 1) {
    if (!sourceTab.selectedAccounts?.length) {
      const id = pickAccountIdForIndex(sourceTab.selectedPlatform, preferredAccountIds, 0)
      sourceTab.selectedAccounts = id != null ? [id] : []
    }
    syncDisplayFileList(sourceTab)
    return 0
  }

  sourceTab.fileList = [files[0]]
  syncDisplayFileList(sourceTab)
  {
    const id = pickAccountIdForIndex(sourceTab.selectedPlatform, preferredAccountIds, 0)
    sourceTab.selectedAccounts = id != null ? [id] : []
  }

  const sourceIndex = tabs.findIndex((t) => t.name === sourceTab.name)
  const insertBase = sourceIndex >= 0 ? sourceIndex : tabs.length - 1
  const sourceHadTopics = (sourceTab.selectedTopics || []).length > 0
  const topicCount = getTopicCountForPlatform(sourceTab.selectedPlatform)

  for (let i = 1; i < files.length; i++) {
    tabCounter++
    const newTab = makeNewTab()
    newTab.name = `tab${tabCounter}`
    newTab.label = `发布${tabCounter}`
    copyTabPublishSettings(sourceTab, newTab)
    newTab.fileList = [files[i]]
    syncDisplayFileList(newTab)
    const id = pickAccountIdForIndex(sourceTab.selectedPlatform, preferredAccountIds, i)
    newTab.selectedAccounts = id != null ? [id] : []
    // 源页已有话题时，新页各自重新随机，避免和发布1完全一样
    if (sourceHadTopics) {
      newTab.selectedTopics = sampleTopics(recommendedTopics, topicCount)
    }
    tabs.splice(insertBase + i, 0, newTab)
  }

  const platformName = PLATFORM_TYPE_NAME[sourceTab.selectedPlatform] || '当前平台'
  if (!platformAccountIds.length) {
    ElMessage.warning(`已按 ${files.length} 个视频拆成 ${files.length} 个发布页，但${platformName}暂无账号，请手动选择`)
  } else if (platformAccountIds.length < files.length) {
    ElMessage.warning(
      `已按 ${files.length} 个视频拆成 ${files.length} 个${platformName}发布页；账号仅 ${platformAccountIds.length} 个，已循环分配`
    )
  } else {
    ElMessage.success(`已按 ${files.length} 个视频拆成 ${files.length} 个${platformName}发布页，并自动分配账号`)
  }
  return files.length - 1
}

const expandVideosTimers = new Map()
const scheduleExpandVideosToTabs = (tab) => {
  if (!tab?.name) return
  const prev = expandVideosTimers.get(tab.name)
  if (prev) clearTimeout(prev)
  const timer = setTimeout(() => {
    expandVideosTimers.delete(tab.name)
    expandVideosToTabs(tab)
  }, 450)
  expandVideosTimers.set(tab.name, timer)
}

// tab页数据 - 默认只有一个tab (use deep copy to avoid shared refs)
const tabs = reactive([
  makeNewTab()
])

// 账号相关状态
const accountDialogVisible = ref(false)
const tempSelectedAccounts = ref([])
const currentTab = ref(null)

// 页面加载时获取账号列表
onMounted(async () => {
  if (accountStore.accounts.length === 0) {
    try {
      const res = await accountApi.getAccounts()
      if (res.code === 200 && res.data) {
        accountStore.setAccounts(res.data)
      }
    } catch (error) {
      console.error('获取账号数据失败:', error)
    }
  }
})

// 根据选择的平台获取可用账号列表
const availableAccounts = computed(() => {
  const platformMap = PLATFORM_TYPE_NAME
  const currentPlatform = currentTab.value ? platformMap[currentTab.value.selectedPlatform] : null
  return currentPlatform ? accountStore.accounts.filter(acc => acc.platform === currentPlatform) : []
})

// 话题相关状态
const topicDialogVisible = ref(false)
const customTopic = ref('')

// 推荐话题池（面具 / 道具 / 工艺相关）
const recommendedTopics = [
  '树脂面具', '艺术面具', '创意面具', '仿真面具', '人脸面具', '立体面具', '装饰面具', '收藏面具',
  '树脂工艺', '树脂制品', '树脂艺术', '树脂创作', '树脂手工', '树脂模型', '树脂雕塑',
  '手工制作', '手工艺术', '手工工艺', '匠心制作', '工艺美术', '工艺品制作', '艺术创作',
  '原创设计', '创意设计', '造型设计', '产品设计',
  '道具设计', '道具制作', '手工道具', '创意道具', '仿真道具', '艺术道具', '展示道具',
  '拍摄道具', '摄影道具', '影视道具', '电影道具', '电视剧道具', '短剧道具', '广告道具',
  '舞台道具', '演出道具', '戏剧道具', '剧场道具', '表演道具', '角色道具', '人物道具',
  '场景道具', '陈列道具', '展览道具', '橱窗道具',
  '影视制作', '电影制作', '短剧制作', '视频制作', '广告拍摄', '创意拍摄',
  '影视美术', '电影美术', '剧组道具', '片场道具', '道具师', '美术道具', '影视置景', '场景搭建',
  '舞台美术', '舞台造型', '人物造型', '角色造型', '造型艺术',
  '特效化妆', '影视特效', '化妆特效', '人物特效',
  '仿真艺术', '写实艺术', '雕塑艺术', '雕刻艺术',
  '模型制作', '人物模型', '角色模型', '艺术模型', '静物模型', '创意模型',
  '手办制作', '艺术手办', '收藏模型', '艺术摆件', '创意摆件', '家居摆件', '桌面摆件',
  '空间装饰', '艺术装饰', '陈列设计', '展示设计',
  '视觉设计', '视觉艺术', '视觉创意', '美学设计', '艺术美学', '静物美学', '细节美学', '质感美学',
  '小众美学', '高级感', '氛围感', '设计感', '艺术感', '创意感',
  '产品展示', '产品拍摄', '产品细节', '细节展示', '质感展示', '工艺展示',
  '制作过程', '手工过程', '创作过程', '幕后制作', '制作日常', '工作室日常', '手作日常', '匠人日常',
  '创意短片', '创意视频', '艺术短片', '产品短片', '短视频创作', '定格动画', '视觉实验',
  '光影艺术', '色彩艺术', '创意灵感', '设计灵感', '艺术灵感', '手工灵感',
  '审美分享', '好物分享', '小众好物', '创意好物', '艺术好物', '设计好物',
  '特色工艺品', '个性化设计', '创意定制', '道具定制', '面具定制', '模型定制', '艺术定制',
  '原创作品', '手工作品', '艺术作品', '设计作品',
  '匠心工艺', '精细工艺', '细节工艺', '传统工艺', '现代工艺', '创意工艺',
  '道具艺术', '面具艺术', '面具文化', '面具造型', '面具收藏', '面具设计', '面具制作',
  '角色扮演道具', '舞台表演', '剧场艺术', '戏剧艺术', '表演艺术',
  '艺术生活', '生活美学', '让艺术走进生活', '发现创意', '创意无限', '灵感记录',
  '作品分享', '每日创作', '艺术分享', '设计分享', '手作分享',
  '中国制造', '中国手工', '创意制造', '工艺制造'
]

// 各平台随机抽取话题数量：固定值 或 [min, max]
const platformTopicCount = {
  3: 5,           // 抖音：5 个
  6: [6, 7],      // B站：6~7 个
  4: 4,           // 快手：4 个
  1: [7, 8],      // 小红书：7~8 个
  2: 5,           // 视频号：默认 5 个
  5: 5,           // 百家号：默认 5 个
  7: 5,           // 今日头条：默认 5 个
  8: 5            // 搜狐：默认 5 个
}

const getTopicCountForPlatform = (platform) => {
  const conf = platformTopicCount[platform]
  if (Array.isArray(conf)) {
    const [min, max] = conf
    return min + Math.floor(Math.random() * (max - min + 1))
  }
  return conf || 5
}

const getTopicCountHint = (platform) => {
  const conf = platformTopicCount[platform]
  if (Array.isArray(conf)) return `（随机 ${conf[0]}~${conf[1]} 个）`
  if (conf) return `（随机 ${conf} 个）`
  return '（随机 5 个）'
}

// Fisher-Yates 洗牌后取前 n 个
const sampleTopics = (pool, n) => {
  const arr = [...pool]
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[arr[i], arr[j]] = [arr[j], arr[i]]
  }
  return arr.slice(0, Math.min(n, arr.length))
}

// 添加新tab
const addTab = () => {
  tabCounter++
  const newTab = makeNewTab()
  newTab.name = `tab${tabCounter}`
  newTab.label = `发布${tabCounter}`
  tabs.push(newTab)
  activeTab.value = newTab.name
}

// 删除tab
const removeTab = (tabName) => {
  const timer = expandVideosTimers.get(tabName)
  if (timer) {
    clearTimeout(timer)
    expandVideosTimers.delete(tabName)
  }
  const index = tabs.findIndex(tab => tab.name === tabName)
  if (index > -1) {
    tabs.splice(index, 1)
    // 如果删除的是当前激活的tab，切换到第一个tab
    if (activeTab.value === tabName && tabs.length > 0) {
      activeTab.value = tabs[0].name
    }
  }
}

// 处理文件上传成功
const handleUploadSuccess = (response, file, tab) => {
  if (response.code === 200) {
    // 获取文件路径
    const filePath = response.data.path || response.data
    // 从路径中提取文件名
    const filename = filePath.split('/').pop()

    // 保存文件信息到fileList，包含文件路径和其他信息
    const fileInfo = {
      name: file.name,
      url: materialApi.getMaterialPreviewUrl(filename), // 使用getMaterialPreviewUrl生成预览URL
      path: filePath,
      size: file.size,
      type: file.type
    }

    // 添加到文件列表
    tab.fileList.push(fileInfo)
    syncDisplayFileList(tab)
    // 多文件上传时稍等齐再拆页，避免每传一个就弹一次提示
    scheduleExpandVideosToTabs(tab)
    ElMessage.success('文件上传成功')
  } else {
    ElMessage.error(response.msg || '上传失败')
  }
}

// 图文封面：上传前校验
// 百家号 5MB JPEG/PNG；搜狐/知乎 10MB jpg/jpeg/png；其它 20MB JPEG/PNG
const getCoverMaxSize = (tab) => {
  if (tab?.selectedPlatform === 5) return 5 * 1024 * 1024
  if (tab?.selectedPlatform === 8 || tab?.selectedPlatform === 9) return 10 * 1024 * 1024
  return 20 * 1024 * 1024
}

const readImageSize = (file) => new Promise((resolve, reject) => {
  const url = URL.createObjectURL(file)
  const img = new Image()
  img.onload = () => {
    const size = { width: img.width, height: img.height }
    URL.revokeObjectURL(url)
    resolve(size)
  }
  img.onerror = () => {
    URL.revokeObjectURL(url)
    reject(new Error('无法读取图片尺寸'))
  }
  img.src = url
})

const beforeCoverUpload = async (file, tab) => {
  const isSohu = tab?.selectedPlatform === 8
  const isImage = isSohu
    ? (file.type === 'image/jpeg' || file.type === 'image/png' || file.type === 'image/jpg'
      || /\.(jpe?g|png)$/i.test(file.name || ''))
    : (file.type === 'image/jpeg' || file.type === 'image/png' || file.type === 'image/jpg'
      || /\.(jpe?g|png)$/i.test(file.name || ''))
  if (!isImage) {
    ElMessage.error(isSohu ? '封面仅支持 jpg、jpeg、png 格式' : '封面仅支持 JPEG、PNG 格式')
    return false
  }
  const maxMb = tab?.selectedPlatform === 5 ? 5 : ((tab?.selectedPlatform === 8 || tab?.selectedPlatform === 9) ? 10 : 20)
  const maxSize = getCoverMaxSize(tab)
  if (file.size > maxSize) {
    ElMessage.error(`单张封面最大支持 ${maxMb}MB`)
    return false
  }
  if (isSohu) {
    if (Array.isArray(tab.coverImages) && tab.coverImages.length >= 1) {
      ElMessage.error('搜狐号封面最多 1 张')
      return false
    }
    try {
      const { width, height } = await readImageSize(file)
      if (width <= 450 || height <= 300) {
        ElMessage.error(`搜狐封面尺寸需大于 450×300，当前 ${width}×${height}`)
        return false
      }
    } catch (e) {
      ElMessage.error('无法校验封面尺寸，请更换图片后重试')
      return false
    }
  }
  return true
}

const handleCoverUploadSuccess = (response, file, tab) => {
  if (response?.code === 200) {
    const filePath = response.data?.path || response.data
    const filename = String(filePath || '').split('/').pop()
    tab.coverImage = filePath
    tab.coverFileName = file?.name || filename
    tab.coverPreviewUrl = materialApi.getMaterialPreviewUrl(filename)
    tab.coverMode = 'single'
    ElMessage.success('封面上传成功')
  } else {
    ElMessage.error(response?.msg || '封面上传失败')
  }
}

const handleSohuCoverUploadSuccess = (response, file, tab) => {
  if (response?.code === 200) {
    const filePath = response.data?.path || response.data
    const filename = String(filePath || '').split('/').pop()
    if (!Array.isArray(tab.coverImages)) tab.coverImages = []
    tab.coverImages.push({
      path: filePath,
      name: file?.name || filename,
      previewUrl: materialApi.getMaterialPreviewUrl(filename)
    })
    // 兼容旧字段：首图写入 coverImage
    tab.coverImage = tab.coverImages[0]?.path || ''
    tab.coverFileName = tab.coverImages.map(i => i.name).join(', ')
    tab.coverPreviewUrl = tab.coverImages[0]?.previewUrl || ''
    tab.coverMode = 'single'
    ElMessage.success('封面上传成功')
  } else {
    ElMessage.error(response?.msg || '封面上传失败')
  }
}

const removeSohuCover = (tab, index) => {
  if (!Array.isArray(tab.coverImages)) return
  tab.coverImages.splice(index, 1)
  tab.coverImage = tab.coverImages[0]?.path || ''
  tab.coverFileName = tab.coverImages.map(i => i.name).join(', ')
  tab.coverPreviewUrl = tab.coverImages[0]?.previewUrl || ''
  ElMessage.success('已删除该封面')
}

const handleCoverUploadError = () => {
  ElMessage.error('封面上传失败')
}

const clearArticleCover = (tab) => {
  tab.coverImage = ''
  tab.coverImages = []
  tab.coverPreviewUrl = ''
  tab.coverFileName = ''
  ElMessage.success('已清除封面')
}

const previewArticleCover = (tab) => {
  if (tab.coverPreviewUrl) {
    window.open(tab.coverPreviewUrl, '_blank')
  }
}

// 处理文件上传失败
const handleUploadError = (error) => {
  ElMessage.error('文件上传失败')
}

// 删除已上传文件
const removeFile = (tab, index) => {
  // 从文件列表中删除
  tab.fileList.splice(index, 1)
  
  // 更新显示列表
  tab.displayFileList = [...tab.fileList.map(item => ({
    name: item.name,
    url: item.url
  }))]
  
  ElMessage.success('文件删除成功')
}

// 话题相关方法
/** 把当前页话题原样同步到同平台的其他发布页（手动选话题时用） */
const syncTopicsToSamePlatformTabs = (sourceTab) => {
  if (!sourceTab) return 0
  const topics = [...(sourceTab.selectedTopics || [])]
  let synced = 0
  for (const t of tabs) {
    if (t.name === sourceTab.name) continue
    if (Number(t.selectedPlatform) !== Number(sourceTab.selectedPlatform)) continue
    t.selectedTopics = [...topics]
    synced++
  }
  return synced
}

/** 同平台每个发布页各自随机抽取话题（互不相同） */
const randomPickTopicsForSamePlatformTabs = (sourceTab) => {
  if (!sourceTab) return 0
  let count = 0
  for (const t of tabs) {
    if (Number(t.selectedPlatform) !== Number(sourceTab.selectedPlatform)) continue
    const n = getTopicCountForPlatform(t.selectedPlatform)
    t.selectedTopics = sampleTopics(recommendedTopics, n)
    count++
  }
  return count
}

// 按当前平台数量随机抽取；同平台其他 Tab 也各自重新随机，避免多发时话题全一样
const randomPickTopics = (tab) => {
  const affected = randomPickTopicsForSamePlatformTabs(tab)
  if (affected > 1) {
    ElMessage.success(`已为 ${affected} 个发布页分别随机抽取话题（各不相同）`)
  } else {
    ElMessage.success(`已随机抽取 ${tab.selectedTopics.length} 个话题`)
  }
}

// 打开添加话题弹窗
const openTopicDialog = (tab) => {
  currentTab.value = tab
  topicDialogVisible.value = true
}

// 添加自定义话题
const addCustomTopic = () => {
  if (!customTopic.value.trim()) {
    ElMessage.warning('请输入话题内容')
    return
  }
  if (currentTab.value && !currentTab.value.selectedTopics.includes(customTopic.value.trim())) {
    currentTab.value.selectedTopics.push(customTopic.value.trim())
    customTopic.value = ''
    ElMessage.success('话题添加成功')
  } else {
    ElMessage.warning('话题已存在')
  }
}

// 切换推荐话题
const toggleRecommendedTopic = (topic) => {
  if (!currentTab.value) return
  
  const index = currentTab.value.selectedTopics.indexOf(topic)
  if (index > -1) {
    currentTab.value.selectedTopics.splice(index, 1)
  } else {
    currentTab.value.selectedTopics.push(topic)
  }
}

// 删除话题
const removeTopic = (tab, index) => {
  tab.selectedTopics.splice(index, 1)
}

// 确认添加话题（手动挑选的话题也同步到同平台其他发布页）
const confirmTopicSelection = () => {
  const source = currentTab.value
  topicDialogVisible.value = false
  customTopic.value = ''
  currentTab.value = null
  if (source) {
    const synced = syncTopicsToSamePlatformTabs(source)
    if (synced > 0) {
      ElMessage.success(`添加话题完成，已同步到另外 ${synced} 个发布页`)
      return
    }
  }
  ElMessage.success('添加话题完成')
}

// 账号选择相关方法
// 打开账号选择弹窗
const openAccountDialog = (tab) => {
  currentTab.value = tab
  tempSelectedAccounts.value = [...tab.selectedAccounts]
  accountDialogVisible.value = true
}

// 确认账号选择
const confirmAccountSelection = () => {
  if (currentTab.value) {
    currentTab.value.selectedAccounts = [...tempSelectedAccounts.value]
  }
  accountDialogVisible.value = false
  currentTab.value = null
  ElMessage.success('账号选择完成')
}

// 删除选中的账号
const removeAccount = (tab, index) => {
  tab.selectedAccounts.splice(index, 1)
}

// 获取账号显示名称
const getAccountDisplayName = (accountId) => {
  const account = accountStore.accounts.find(acc => acc.id === accountId)
  return account ? account.name : accountId
}

// 取消发布
const cancelPublish = (tab) => {
  ElMessage.info('已取消发布')
}

// 确认发布
const confirmPublish = async (tab) => {
  // 防止重复点击
  if (tab.publishing) {
    throw new Error('正在发布中，请稍候...')
  }

  tab.publishing = true // 设置发布状态为进行中

  // 数据验证
  const isArticle = isArticleTab(tab)
  const isToutiaoArticle = tab.selectedPlatform === 7 && isArticle
  const isBaijiahaoArticle = tab.selectedPlatform === 5 && isArticle
  const isSohuArticle = tab.selectedPlatform === 8 && isArticle
  const isZhihuArticle = tab.selectedPlatform === 9 && isArticle
  if (!isArticle && tab.fileList.length === 0) {
    ElMessage.error('请先上传视频文件')
    tab.publishing = false
    throw new Error('请先上传视频文件')
  }
  if (isArticle && !(tab.articleBody || '').trim()) {
    ElMessage.error('请输入文章正文')
    tab.publishing = false
    throw new Error('请输入文章正文')
  }
  // 百家号图文标题下限 2 字：前置拦截，避免后端补字导致标题与预期不一致
  if (isBaijiahaoArticle && tab.title.trim().length < 2) {
    ElMessage.error('百家号图文标题至少 2 个字')
    tab.publishing = false
    throw new Error('百家号图文标题至少 2 个字')
  }
  if (isSohuArticle) {
    const sohuTitleLen = tab.title.trim().length
    if (sohuTitleLen < 5 || sohuTitleLen > 72) {
      ElMessage.error('搜狐号文章标题需 5-72 个字')
      tab.publishing = false
      throw new Error('搜狐号文章标题需 5-72 个字')
    }
  }
  if (isZhihuArticle) {
    const zhihuTitleLen = tab.title.trim().length
    if (!zhihuTitleLen) {
      ElMessage.error('请输入知乎文章标题')
      tab.publishing = false
      throw new Error('请输入知乎文章标题')
    }
    if (zhihuTitleLen > 100) {
      ElMessage.error('知乎文章标题最多 100 个字')
      tab.publishing = false
      throw new Error('知乎文章标题最多 100 个字')
    }
  }
  if (isBaijiahaoArticle && (!tab.coverImage || tab.coverMode !== 'single')) {
    ElMessage.error('百家号图文必须上传展示封面')
    tab.publishing = false
    throw new Error('百家号图文必须上传展示封面')
  }
  // 小红书（1）、视频号（2）、抖音（3）、快手（4）标题非必填，其它平台仍必填
  if (tab.selectedPlatform !== 1 && tab.selectedPlatform !== 2 && tab.selectedPlatform !== 3 && tab.selectedPlatform !== 4 && !tab.title.trim()) {
    ElMessage.error('请输入标题')
    tab.publishing = false
    throw new Error('请输入标题')
  }
  if (!tab.selectedPlatform) {
    ElMessage.error('请选择发布平台')
    tab.publishing = false
    throw new Error('请选择发布平台')
  }
  if (tab.selectedAccounts.length === 0) {
    ElMessage.error('请选择发布账号')
    tab.publishing = false
    throw new Error('请选择发布账号')
  }
  if (tab.scheduleEnabled && !tab.startDate) {
    ElMessage.error('请选择定时发布起始日期')
    tab.publishing = false
    throw new Error('请选择定时发布起始日期')
  }

  // 构造发布数据，符合后端API格式
  const publishData = {
    type: tab.selectedPlatform,
    title: tab.title,
    tags: tab.selectedTopics, // 不带#号的话题列表
    fileList: isArticle ? [] : tab.fileList.map(file => file.path), // 只发送文件路径
    accountList: tab.selectedAccounts.map(accountId => {
      const account = accountStore.accounts.find(acc => acc.id === accountId)
      return account ? account.filePath : accountId
    }), // 发送账号的文件路径
    enableTimer: tab.scheduleEnabled ? 1 : 0,
    videosPerDay: tab.scheduleEnabled ? tab.videosPerDay || 1 : 1,
    dailyTimes: tab.scheduleEnabled ? tab.dailyTimes || ['10:00'] : ['10:00'],
    startDays: tab.scheduleEnabled ? startDateToStartDays(tab.startDate) : 0,
    category: tab.isOriginal ? 1 : 0, // 1表示原创，0表示非原创
    productLink: tab.productLink.trim() || '',
    productTitle: tab.productTitle.trim() || '',
    isDraft: tab.isDraft,
    aiGenerated: (tab.selectedPlatform === 1 || tab.selectedPlatform === 2 || tab.selectedPlatform === 3 || tab.selectedPlatform === 4) ? !!tab.aiGenerated : false,
    // B站创作声明 id；null/undefined 表示不传 extra-fields
    bilibiliCreationStatement: tab.selectedPlatform === 6 && tab.bilibiliCreationStatement !== null && tab.bilibiliCreationStatement !== undefined && tab.bilibiliCreationStatement !== ''
      ? Number(tab.bilibiliCreationStatement)
      : null,
    // B站不支持浏览器预览，强制关闭 dryRun
    dryRun: tab.selectedPlatform === 6 ? false : !!tab.dryRun,
    // 百家号 / 今日头条 / 搜狐 / 知乎：视频/图文文章（搜狐/知乎强制 article）
    contentType: articleOnlyPlatforms.includes(tab.selectedPlatform)
      ? 'article'
      : (articleCapablePlatforms.includes(tab.selectedPlatform) ? (tab.contentType || 'video') : 'video'),
    articleBody: isArticle ? (tab.articleBody || '') : '',
    // 图文封面；搜狐支持多图 coverImages；知乎走单图 thumbnail
    coverImage: isArticle && tab.coverMode === 'single'
      ? (tab.selectedPlatform === 8
          ? (tab.coverImages?.[0]?.path || tab.coverImage || '')
          : (tab.coverImage || ''))
      : (tab.selectedPlatform === 5 && tab.coverImage ? tab.coverImage : ''),
    coverImages: isArticle && tab.selectedPlatform === 8 && tab.coverMode === 'single'
      ? (tab.coverImages || []).map(i => i.path).filter(Boolean)
      : [],
    thumbnail: isArticle && tab.coverMode === 'single'
      ? (tab.selectedPlatform === 8
          ? (tab.coverImages?.[0]?.path || tab.coverImage || '')
          : (tab.coverImage || ''))
      : (tab.selectedPlatform === 5 && tab.coverImage ? tab.coverImage : ''),
    // 今日头条作品声明 / 搜狐信息来源 / 知乎创作声明（复用 workStatement）
    workStatement: (isToutiaoArticle || isSohuArticle || isZhihuArticle) ? (tab.workStatement || '') : '',
    // 兼容旧字段：后端仍接受列表，单选时最多传一项
    workStatements: (isToutiaoArticle || isSohuArticle || isZhihuArticle) && tab.workStatement ? [tab.workStatement] : []
  }

  // 调用后端发布API（使用统一的http封装）
  // 注意：后端会立刻返回“任务已提交”和 jobId；真正上传在后台执行，前端轮询结果。
  try {
    stopPublishJobPolling(tab)
    tab.publishJob = null
    const data = await http.post('/postVideo', publishData)
    const isBilibili = tab.selectedPlatform === 6
    const isBaijiahao = tab.selectedPlatform === 5
    let message = data?.msg || '发布任务已提交，正在后台执行'
    let statusType = 'success'

    if (!isBilibili && tab.dryRun) {
      if (isToutiaoArticle) {
        message = '任务已提交：今日头条文章仅预览不发布'
      } else if (isSohuArticle) {
        message = '任务已提交：搜狐号文章仅预览不发布'
      } else if (isZhihuArticle) {
        message = '任务已提交：知乎文章仅预览不发布'
      } else if (isBaijiahaoArticle) {
        message = '任务已提交：百家号图文仅预览不发布（脚本不会点发布；后台可能出现自动保存的草稿，不等于已发布）'
      } else {
        message = '任务已提交：仅预览不发布（浏览器会打开填表，不会点发布）'
      }
      statusType = 'warning'
    } else if (isBilibili) {
      message = 'B站上传任务已提交：后台通过 biliup 上传中（不会打开浏览器，请到后端终端查看进度）'
      statusType = 'info'
    } else if (isBaijiahao) {
      message = isBaijiahaoArticle
        ? '百家号图文发布任务已提交：浏览器将自动打开填表，请稍候'
        : '百家号发布任务已提交：浏览器将自动打开上传，请稍候'
      statusType = 'info'
    } else if (isToutiaoArticle) {
      message = data?.msg || '今日头条文章发布任务已提交，正在后台执行'
    } else if (isSohuArticle) {
      message = data?.msg || '搜狐号文章发布任务已提交，正在后台执行'
    } else if (isZhihuArticle) {
      message = data?.msg || '知乎文章发布任务已提交，正在后台执行'
    }

    const jobId = data?.data?.jobId
    const platformLabel = PLATFORM_TYPES[tab.selectedPlatform] || '未知'
    const accountNames = (tab.selectedAccounts || []).map((id) => getAccountDisplayName(id)).join('、')
    const contentLabel = tab.title
      || (isArticle ? '图文文章' : '')
      || (tab.fileList || []).map((file) => file.name).filter(Boolean).join('、')
      || '未命名内容'

    if (jobId) {
      message = `${message}（可在下方查看每个视频的成败）`
      tab.publishJob = {
        jobId,
        status: 'running',
        totalCount: 0,
        successCount: 0,
        failedCount: 0,
        results: []
      }
      startPublishJobPolling(tab, jobId)
    } else {
      // 无 jobId 时直接记一条本地发布记录
      publishLog.addRecord({
        platform: platformLabel,
        account: accountNames,
        content: contentLabel,
        status: statusType === 'warning' ? 'submitted' : 'success',
        message,
        source: 'auto',
        dedupeKey: `submit:${tab.selectedPlatform}:${contentLabel}:${accountNames}:${Date.now()}`
      })
    }

    tab.publishStatus = {
      message,
      type: statusType
    }
    if (statusType === 'warning') {
      ElMessage.warning({ message, duration: 6000, showClose: true })
    } else if (statusType === 'info') {
      ElMessage.info({ message, duration: 8000, showClose: true })
    } else {
      ElMessage.success({ message, duration: 5000, showClose: true })
    }

    // 清空当前tab的数据（保留 publishStatus / publishJob）
    tab.fileList = []
    tab.displayFileList = []
    tab.title = ''
    tab.articleBody = ''
    tab.coverMode = 'single'
    tab.coverImage = ''
    tab.coverImages = []
    tab.coverPreviewUrl = ''
    tab.coverFileName = ''
    tab.workStatement = tab.selectedPlatform === 8
      ? '无特别声明'
      : (tab.selectedPlatform === 9 ? '无声明' : '')
    tab.selectedTopics = []
    tab.selectedAccounts = []
    tab.scheduleEnabled = false
  } catch (error) {
    console.error('发布错误:', error)
    const backendMsg = error?.response?.data?.msg
    const message = `发布失败：${backendMsg || error.message || '请检查网络连接'}`
    tab.publishStatus = {
      message,
      type: 'error'
    }
    ElMessage.error(message)
    publishLog.addRecord({
      platform: PLATFORM_TYPES[tab.selectedPlatform] || '未知',
      account: (tab.selectedAccounts || []).map((id) => getAccountDisplayName(id)).join('、'),
      content: tab.title || (tab.fileList || []).map((file) => file.name).filter(Boolean).join('、'),
      status: 'failed',
      message,
      source: 'auto'
    })
    throw error
  } finally {
    tab.publishing = false
  }
}

const publishJobPollers = new Map()

const stopPublishJobPolling = (tab) => {
  const key = tab?.name
  if (!key) return
  const timer = publishJobPollers.get(key)
  if (timer) {
    clearInterval(timer)
    publishJobPollers.delete(key)
  }
}

const resultStatusText = (status) => {
  const map = {
    pending: '等待中',
    success: '成功',
    failed: '失败',
    skipped: '已跳过'
  }
  return map[status] || status || '-'
}

const resultStatusTagType = (status) => {
  const map = {
    pending: 'info',
    success: 'success',
    failed: 'danger',
    skipped: 'warning'
  }
  return map[status] || 'info'
}

const publishJobStatusText = (job) => {
  if (!job) return ''
  const results = job.results || []
  const total = job.totalCount || results.length
  const done = results.filter((r) => r.status && r.status !== 'pending').length
  const successCount = results.filter((r) => r.status === 'success' || r.status === 'skipped').length
  const failedCount = results.filter((r) => r.status === 'failed').length
  if (job.status === 'running') {
    return `进行中 ${done}/${total || '?'}`
  }
  if (job.status === 'success') return `全部成功 ${successCount || job.successCount || 0}/${total}`
  if (job.status === 'failed') return `全部失败 ${failedCount || job.failedCount || 0}/${total}`
  if (job.status === 'partial') {
    return `部分成功 成功${successCount || job.successCount || 0} / 失败${failedCount || job.failedCount || 0}`
  }
  return job.status
}

const publishJobTagType = (status) => {
  const map = {
    running: 'warning',
    success: 'success',
    failed: 'danger',
    partial: 'warning'
  }
  return map[status] || 'info'
}

const applyPublishJobToTab = (tab, job) => {
  tab.publishJob = job
  if (!job || job.status === 'running') return
  const platformLabel = PLATFORM_TYPES[job.platform] || PLATFORM_TYPES[tab.selectedPlatform] || '未知'
  const added = publishLog.addJobResults(job, platformLabel)
  const total = job.totalCount || (job.results || []).length
  if (job.status === 'success') {
    tab.publishStatus = {
      message: `发布完成：全部成功（${job.successCount || 0}/${total}）`,
      type: 'success'
    }
  } else if (job.status === 'failed') {
    tab.publishStatus = {
      message: `发布完成：全部失败（${job.failedCount || 0}/${total}），请查看下方明细`,
      type: 'error'
    }
  } else if (job.status === 'partial') {
    tab.publishStatus = {
      message: `发布完成：部分成功（成功 ${job.successCount || 0}，失败 ${job.failedCount || 0}），请查看下方明细`,
      type: 'warning'
    }
  }
  if (added > 0) {
    ElMessage.info(`已写入 ${added} 条本地发布记录`)
  }
}

const startPublishJobPolling = (tab, jobId) => {
  stopPublishJobPolling(tab)
  const pollOnce = async () => {
    try {
      const resp = await http.get(`/publishJob/${jobId}`)
      const job = resp?.data
      if (!job) return
      applyPublishJobToTab(tab, job)
      if (job.status && job.status !== 'running') {
        stopPublishJobPolling(tab)
      }
    } catch (err) {
      console.error('轮询发布结果失败:', err)
    }
  }
  pollOnce()
  const timer = setInterval(pollOnce, 2000)
  publishJobPollers.set(tab.name, timer)
}

onUnmounted(() => {
  for (const timer of publishJobPollers.values()) {
    clearInterval(timer)
  }
  publishJobPollers.clear()
  for (const timer of expandVideosTimers.values()) {
    clearTimeout(timer)
  }
  expandVideosTimers.clear()
})

// 显示上传选项
const showUploadOptions = (tab) => {
  currentUploadTab.value = tab
  uploadOptionsVisible.value = true
}

// 选择本地上传
const selectLocalUpload = () => {
  uploadOptionsVisible.value = false
  localUploadVisible.value = true
}

// 选择素材库
const selectMaterialLibrary = async () => {
  uploadOptionsVisible.value = false
  
  // 如果素材库为空，先获取素材数据
  if (materials.value.length === 0) {
    try {
      const response = await materialApi.getAllMaterials()
      if (response.code === 200) {
        appStore.setMaterials(response.data)
      } else {
        ElMessage.error('获取素材列表失败')
        return
      }
    } catch (error) {
      console.error('获取素材列表出错:', error)
      ElMessage.error('获取素材列表失败')
      return
    }
  }
  
  selectedMaterials.value = []
  materialLibraryVisible.value = true
}

// 确认素材选择
const confirmMaterialSelection = () => {
  if (selectedMaterials.value.length === 0) {
    ElMessage.warning('请选择至少一个素材')
    return
  }
  
  if (currentUploadTab.value) {
    // 将选中的素材添加到当前tab的文件列表
    selectedMaterials.value.forEach(materialId => {
      const material = materials.value.find(m => m.id === materialId)
      if (material) {
        const fileInfo = {
          name: material.filename,
          url: materialApi.getMaterialPreviewUrl(material.file_path.split('/').pop()),
          path: material.file_path,
          size: material.filesize * 1024 * 1024, // 转换为字节
          type: 'video/mp4'
        }
        
        // 检查是否已存在相同文件
        const exists = currentUploadTab.value.fileList.some(file => file.path === fileInfo.path)
        if (!exists) {
          currentUploadTab.value.fileList.push(fileInfo)
        }
      }
    })
    
    syncDisplayFileList(currentUploadTab.value)
    const splitCount = expandVideosToTabs(currentUploadTab.value)
    const addedCount = selectedMaterials.value.length
    materialLibraryVisible.value = false
    selectedMaterials.value = []
    currentUploadTab.value = null
    if (splitCount === 0) {
      ElMessage.success(`已添加 ${addedCount} 个素材`)
    }
    return
  }
  
  const addedCount = selectedMaterials.value.length
  materialLibraryVisible.value = false
  selectedMaterials.value = []
  currentUploadTab.value = null
  ElMessage.success(`已添加 ${addedCount} 个素材`)
}

// 批量发布对话框状态
const batchPublishDialogVisible = ref(false)
const currentPublishingTab = ref(null)
const publishProgress = ref(0)
const publishResults = ref([])
const isCancelled = ref(false)

// 取消批量发布
const cancelBatchPublish = () => {
  isCancelled.value = true
  ElMessage.info('正在取消发布...')
}

// 批量发布方法
const batchPublish = async () => {
  if (batchPublishing.value) return
  
  batchPublishing.value = true
  currentPublishingTab.value = null
  publishProgress.value = 0
  publishResults.value = []
  isCancelled.value = false
  batchPublishDialogVisible.value = true
  
  try {
    for (let i = 0; i < tabs.length; i++) {
      if (isCancelled.value) {
        publishResults.value.push({
          label: tabs[i].label,
          status: 'cancelled',
          message: '已取消'
        })
        continue
      }

      const tab = tabs[i]
      currentPublishingTab.value = tab
      publishProgress.value = Math.floor((i / tabs.length) * 100)
      
      try {
        await confirmPublish(tab)
        publishResults.value.push({
          label: tab.label,
          status: 'success',
          message: '发布成功'
        })
      } catch (error) {
        publishResults.value.push({
          label: tab.label,
          status: 'error',
          message: error.message
        })
        // 不立即返回，继续显示发布结果
      }
    }
    
    publishProgress.value = 100
    
    // 统计发布结果
    const successCount = publishResults.value.filter(r => r.status === 'success').length
    const failCount = publishResults.value.filter(r => r.status === 'error').length
    const cancelCount = publishResults.value.filter(r => r.status === 'cancelled').length
    
    if (isCancelled.value) {
      ElMessage.warning(`发布已取消：${successCount}个成功，${failCount}个失败，${cancelCount}个未执行`)
    } else if (failCount > 0) {
      ElMessage.error(`发布完成：${successCount}个成功，${failCount}个失败`)
    } else {
      ElMessage.success('所有Tab发布成功')
      setTimeout(() => {
        batchPublishDialogVisible.value = false
      }, 1000)
    }
    
  } catch (error) {
    console.error('批量发布出错:', error)
    ElMessage.error('批量发布出错，请重试')
  } finally {
    batchPublishing.value = false
    isCancelled.value = false
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.publish-center {
  display: flex;
  flex-direction: column;
  height: 100%;

  .publish-status {
    margin-bottom: 16px;
  }

  .publish-job-panel {
    margin-bottom: 20px;
    padding: 12px 16px;
    background: #fafafa;
    border: 1px solid #ebeef5;
    border-radius: 4px;

    .publish-job-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;

      h3 {
        margin: 0;
        font-size: 15px;
        font-weight: 600;
      }
    }
  }
  
  // Tab管理区域
  .tab-management {
    background-color: #fff;
    border-radius: 4px;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
    margin-bottom: 20px;
    padding: 15px 20px;
    
    .tab-header {
      display: flex;
      align-items: flex-start;
      gap: 15px;
      
      .tab-list {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        flex: 1;
        min-width: 0;
        
        .tab-item {
           display: flex;
           align-items: center;
           gap: 6px;
           padding: 6px 12px;
           background-color: #f5f7fa;
           border: 1px solid #dcdfe6;
           border-radius: 4px;
           cursor: pointer;
           transition: all 0.3s;
           font-size: 14px;
           height: 32px;
           
           &:hover {
             background-color: #ecf5ff;
             border-color: #b3d8ff;
           }
           
           &.active {
             background-color: #409eff;
             border-color: #409eff;
             color: #fff;
             
             .close-icon {
               color: #fff;
               
               &:hover {
                 background-color: rgba(255, 255, 255, 0.2);
               }
             }
           }
           
           .close-icon {
             padding: 2px;
             border-radius: 2px;
             cursor: pointer;
             transition: background-color 0.3s;
             font-size: 12px;
             
             &:hover {
               background-color: rgba(0, 0, 0, 0.1);
             }
           }
         }
       }
       
      .tab-actions {
        display: flex;
        gap: 10px;
        flex-shrink: 0;
        
        .add-tab-btn,
        .batch-publish-btn {
          display: flex;
          align-items: center;
          gap: 4px;
          height: 32px;
          padding: 6px 12px;
          font-size: 14px;
          white-space: nowrap;
        }
      }
    }
  }
  
  // 批量发布进度对话框样式
  .publish-progress {
    padding: 20px;
    
    .current-publishing {
      margin: 15px 0;
      text-align: center;
      color: #606266;
    }

    .publish-results {
      margin-top: 20px;
      border-top: 1px solid #EBEEF5;
      padding-top: 15px;
      max-height: 300px;
      overflow-y: auto;

      .result-item {
        display: flex;
        align-items: center;
        padding: 8px 0;
        color: #606266;

        .el-icon {
          margin-right: 8px;
        }

        .label {
          margin-right: 10px;
          font-weight: 500;
        }

        .message {
          color: #909399;
        }

        &.success {
          color: #67C23A;
        }

        &.error {
          color: #F56C6C;
        }

        &.cancelled {
          color: #909399;
        }
      }
    }
  }

  .dialog-footer {
    text-align: right;
  }
  
  // 内容区域
  .publish-content {
    flex: 1;
    background-color: #fff;
    border-radius: 4px;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
    padding: 20px;
    
    .tab-content-wrapper {
      display: flex;
      justify-content: center;
      
      .tab-content {
        width: 100%;
        max-width: 800px;
        
        h3 {
          font-size: 16px;
          font-weight: 500;
          color: $text-primary;
          margin: 0 0 10px 0;
        }
        
        .upload-section,
        .account-section,
        .platform-section,
        .content-type-section,
        .article-body-section,
        .article-cover-section,
        .work-statement-section,
        .title-section,
        .product-section,
        .topic-section,
        .schedule-section {
          margin-bottom: 30px;
        }

        .content-type-section {
          .content-type-radios {
            display: flex;
            gap: 16px;
          }
        }

        .article-body-section {
          .article-body-input {
            width: 100%;
          }
        }

        .article-cover-section {
          .cover-mode-radios {
            display: flex;
            gap: 16px;
            margin-bottom: 12px;
          }

          .article-cover-upload-wrap {
            display: flex;
            flex-wrap: wrap;
            align-items: flex-start;
            gap: 12px;

            &.sohu-multi-cover {
              flex-direction: column;
              width: 100%;
            }

            .sohu-cover-list {
              display: flex;
              flex-wrap: wrap;
              align-items: flex-start;
              gap: 12px;
            }

            .sohu-cover-item {
              border: 1px dashed #d9d9d9;
              border-radius: 6px;
              overflow: hidden;

              .cover-preview-mask span {
                cursor: pointer;
              }
            }
          }

          .article-cover-upload {
            :deep(.el-upload) {
              border: 1px dashed #d9d9d9;
              border-radius: 6px;
              cursor: pointer;
              overflow: hidden;
              transition: border-color 0.2s;
            }

            :deep(.el-upload:hover) {
              border-color: #409eff;
            }
          }

          .cover-plus-box,
          .cover-preview-box {
            width: 148px;
            height: 148px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #fafafa;
            color: #8c939d;
            position: relative;
          }

          .cover-preview-box {
            .cover-preview-img {
              width: 100%;
              height: 100%;
              object-fit: cover;
              display: block;
            }

            .cover-preview-mask {
              position: absolute;
              inset: 0;
              display: none;
              align-items: center;
              justify-content: center;
              background: rgba(0, 0, 0, 0.45);
              color: #fff;
              font-size: 13px;
            }

            &:hover .cover-preview-mask {
              display: flex;
            }
          }

          .cover-side-actions {
            display: flex;
            flex-direction: column;
            gap: 4px;
            padding-top: 4px;
          }

          .cover-tip {
            width: 100%;
            font-size: 12px;
            color: #909399;
            line-height: 1.5;
          }

          .cover-file-name {
            width: 100%;
            font-size: 12px;
            color: #606266;
          }
        }

        .work-statement-section {
          .work-statement-group {
            display: flex;
            flex-wrap: wrap;
            gap: 8px 18px;

            :deep(.el-radio) {
              margin-right: 0;
              height: auto;
              white-space: normal;
            }
          }
        }

        .product-section {
          .product-name-input,
          .product-link-input {
            margin-bottom: 5px;
          }
        }
        
        .video-upload {
          width: 100%;
          
          :deep(.el-upload-dragger) {
            width: 100%;
            height: 180px;
          }
        }
        
        .account-input {
          max-width: 400px;
        }
        
        .platform-buttons {
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
          
          .platform-btn {
            min-width: 80px;
          }
        }
        
        .title-input {
          max-width: 600px;
        }

        .optional-hint {
          margin-left: 4px;
          font-size: 12px;
          font-weight: normal;
          color: #909399;
        }
        
        .topic-display {
          display: flex;
          flex-direction: column;
          gap: 12px;

          .topic-actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
          }

          .selected-topics {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            min-height: 32px;

            .topic-tag {
              font-size: 14px;
            }
          }

          .select-topic-btn {
            align-self: flex-start;
          }
        }
        
        .schedule-controls {
          display: flex;
          flex-direction: column;
          gap: 15px;

          .schedule-settings {
            margin-top: 15px;
            padding: 15px;
            background-color: #f5f7fa;
            border-radius: 4px;

            .schedule-item {
              display: flex;
              align-items: center;
              flex-wrap: wrap;
              margin-bottom: 15px;

              &:last-child {
                margin-bottom: 0;
              }

              .label {
                min-width: 120px;
                margin-right: 10px;
              }

              .schedule-hint {
                margin-left: 10px;
                color: #909399;
                font-size: 12px;
              }

              .el-time-select {
                margin-right: 10px;
              }

              .el-button {
                margin-left: 10px;
              }
            }
          }
        }
        
        .action-buttons {
          display: flex;
          justify-content: flex-end;
          gap: 10px;
          margin-top: 30px;
          padding-top: 20px;
          border-top: 1px solid #ebeef5;
        }

        .draft-section {
          margin: 20px 0;

          .draft-checkbox {
            display: block;
            margin: 10px 0;
          }
        }

        .original-section {
          margin: 10px 0 20px;

          .original-checkbox {
            display: block;
            margin: 10px 0;
          }
        }

        .ai-declaration-section {
          margin: 10px 0 20px;

          .ai-declaration-checkbox {
            display: block;
            margin: 10px 0;
          }
        }

        .bilibili-creation-section {
          margin: 10px 0 20px;

          h3 {
            margin-bottom: 10px;
          }

          .bilibili-creation-select {
            width: 100%;
            max-width: 360px;
          }

          .optional-hint {
            margin-top: 8px;
            font-size: 12px;
            color: #909399;
          }
        }

        .dry-run-section {
          margin: 10px 0 20px;

          .dry-run-checkbox {
            display: block;
            margin: 10px 0;
          }
        }
      }
    }
  }

  // 已上传文件列表样式
  .uploaded-files {
    margin-top: 20px;
    
    h4 {
      font-size: 16px;
      font-weight: 500;
      margin-bottom: 12px;
      color: #303133;
    }
    
    .file-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
      
      .file-item {
        display: flex;
        align-items: center;
        padding: 10px 15px;
        background-color: #f5f7fa;
        border-radius: 4px;
        
        .el-link {
          margin-right: 10px;
          max-width: 300px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        
        .file-size {
          color: #909399;
          font-size: 13px;
          margin-right: auto;
        }
      }
    }
  }
  
  // 添加话题弹窗样式
  .topic-dialog {
    .topic-dialog-content {
      .custom-topic-input {
        display: flex;
        gap: 12px;
        margin-bottom: 24px;
        
        .custom-input {
          flex: 1;
        }
      }
      
      .recommended-topics {
        h4 {
          margin: 0 0 16px 0;
          font-size: 16px;
          font-weight: 500;
          color: #303133;
        }
        
        .topic-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
          gap: 12px;
          
          .topic-btn {
            height: 36px;
            font-size: 14px;
            border-radius: 6px;
            min-width: 100px;
            padding: 0 12px;
            white-space: nowrap;
            text-align: center;
            display: flex;
            align-items: center;
            justify-content: center;
            
            &.el-button--primary {
              background-color: #409eff;
              border-color: #409eff;
              color: white;
            }
          }
        }
      }
    }
    
    .dialog-footer {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
    }
  }
}
</style>
