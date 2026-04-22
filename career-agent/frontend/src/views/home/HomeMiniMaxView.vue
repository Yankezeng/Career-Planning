﻿﻿﻿﻿﻿﻿﻿<template>
  <div class="mini-page">
    <AgentSidebar
      :menu-groups="auth.isLoggedIn ? visibleMenuGroups : []"
      :history-items="sidebarHistoryItems"
      :active-path="activeSidebarPath"
      :active-history-id="activeSessionId"
      :user-name="auth.user?.real_name || '探索者'"
      :user-role="auth.isLoggedIn ? (auth.user?.role_name || '已登录') : '未登录'"
      :show-workspace="auth.role !== 'admin'"
      :show-history="sidebarHistoryItems.length > 0"
      :can-create-task="canCreateTask"
      @new-task="handleNewTask"
      @select-menu="goFeature"
      @workspace="handleWorkspaceAction"
      @select-history="handleSessionClick"
      @rename-history="handleRenameSession"
      @delete-history="handleDeleteSession"
    />

    <main class="mini-main">
      <header class="top-bar">
        <div class="top-placeholder"></div>
        <div class="top-actions">
          <template v-if="auth.role !== 'admin'">
            <button type="button" class="mini-icon-btn" @click="openWorkspacePanel('search')">搜</button>
            <button type="button" class="mini-icon-btn" @click="openWorkspacePanel('assets')">资</button>
            <button type="button" class="mini-icon-btn" @click="openWorkspacePanel('gallery')">廊</button>
          </template>
          <template v-if="auth.isLoggedIn">
            <span class="top-tag dark">{{ auth.user?.role_name || '用户' }}</span>
            <span class="top-tag light">平台模式</span>
            <span class="top-user">{{ auth.user?.real_name || '-' }}</span>
            <el-button class="login-btn" type="danger" plain @click="logout">退出登录</el-button>
          </template>
          <el-button v-else class="login-btn" plain @click="openLoginModal('login')">登录</el-button>
        </div>
      </header>

      <section class="dialog-shell">
        <section v-if="showWelcome" class="welcome-shell">
          <h1 class="welcome-title">有什么我能帮你的吗？</h1>
          <div class="quick-actions-list center">
            <button v-for="item in promptTemplates" :key="item.label" type="button" class="quick-chip" @click="applyPromptTemplate(item)">
              {{ item.label }}
            </button>
          </div>
        </section>

        <section v-else ref="chatScrollRef" class="chat-area" @scroll="handleChatScroll">
          <div class="chat-inner">
            <div v-for="(msg, idx) in activeMessages" :key="`${msg.role}-${idx}-${msg.time}`" :class="['chat-row', msg.role]">
              <div class="chat-bubble">
                <AssistantMessageRenderer
                  :content="msg.content"
                  :reply-blocks="msg.replyBlocks"
                  :artifacts="Array.isArray(msg.artifacts) ? msg.artifacts : []"
                  :backend-origin="BACKEND_ORIGIN"
                  :prefer-plain-text="shouldRenderPlainText(msg)"
                  :typewriter="shouldTypewriter(msg)"
                />
                <AssistantCardRenderer
                  v-if="Array.isArray(msg.cards) && msg.cards.length"
                  :cards="msg.cards"
                  :backend-origin="BACKEND_ORIGIN"
                  @detail="openDetailCard"
                />
                <ThinkingIndicator
                  v-if="msg.role === 'assistant' && (['waiting', 'streaming', 'error'].includes(msg.streamState || '') || isAssistantBackgroundRunning(msg))"
                  :state="msg.streamState || 'waiting'"
                  :label="msg.thinkingText || ''"
                />
                <div v-if="shouldShowThinkingProcess(msg)" class="thinking-process">
                  <button type="button" class="thinking-process-head" @click="toggleThinkingProcess(msg)">
                    <span>{{ thinkingProcessTitle(msg) }}</span>
                    <span class="thinking-process-toggle">{{ isThinkingProcessOpen(msg) ? "收起" : "展开" }}</span>
                  </button>
                  <div v-show="isThinkingProcessOpen(msg)" class="thinking-process-body">
                    <p v-if="thinkingCurrentText(msg)" class="thinking-process-current">
                      {{ thinkingCurrentText(msg) }}
                    </p>
                    <div v-if="thinkingProcessLines(msg).length" class="thinking-process-lines">
                      <p
                        v-for="(line, lineIndex) in thinkingProcessLines(msg)"
                        :key="`thinking-line-${lineIndex}`"
                        :class="['thinking-process-line', line.statusClass]"
                      >
                        {{ line.text }}
                      </p>
                    </div>
                  </div>
                </div>
                <div v-if="msg.resultCard" class="result-card">
                  <div class="result-tabs">
                    <button
                      v-for="tab in msg.resultCard.tabs"
                      :key="tab.key"
                      type="button"
                      :class="['result-tab', { active: msg.resultCard.activeTab === tab.key }]"
                      @click="selectResultTab(msg, tab.key)"
                    >
                      {{ tab.label }}
                    </button>
                  </div>
                  <div class="result-body">
                    <template v-if="activeResultTab(msg.resultCard)?.items?.length">
                      <div v-for="item in activeResultTab(msg.resultCard).items" :key="item" class="result-item">{{ item }}</div>
                    </template>
                    <p v-else class="result-text">{{ activeResultTab(msg.resultCard)?.content || "-" }}</p>
                  </div>
                </div>
                <div class="bubble-time">{{ msg.time }}</div>
              </div>
            </div>
          </div>
        </section>
        <ScrollToLatestButton
          :visible="!showWelcome && showScrollToBottom"
          :unread-count="unreadNewMessageCount"
          @click="handleScrollToLatest"
        />
      </section>

      <section class="composer-wrap">
        <div ref="composerBoxRef" class="composer-box">
          <el-input
            v-model="draft"
            type="textarea"
            resize="none"
            :rows="2"
            placeholder="发送消息..."
            @keydown.enter.exact.prevent="sendMessage()"
            @keydown.enter.ctrl="handleCtrlEnter"
          />
          <div class="composer-actions">
            <div class="left-actions">
              <el-upload
                accept=".png,.jpg,.jpeg,.webp,.bmp,.pdf,.doc,.docx"
                :auto-upload="false"
                :show-file-list="false"
                :on-change="handleAttachmentChange"
              >
                <button type="button" class="tool-item tool-item-with-icon">
                  <span class="tool-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none">
                      <path
                        d="M16.5 6.5L9 14a3 3 0 104.243 4.243l6.01-6.01a5 5 0 10-7.071-7.072L5.464 11.88a7 7 0 109.9 9.9l6.364-6.364"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                  </span>
                  <span>附件</span>
                </button>
              </el-upload>
              <button type="button" class="tool-item tool-item-with-icon" @click="openSkillPanel">
                <span class="tool-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none">
                    <path
                      d="M12 3l2.2 4.6L19 10l-4.8 2.4L12 17l-2.2-4.6L5 10l4.8-2.4L12 3zM18.5 14.5l1 2 2 1-2 1-1 2-1-2-2-1 2-1 1-2z"
                      stroke="currentColor"
                      stroke-width="1.8"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    />
                  </svg>
                </span>
                <span>技能</span>
              </button>
            </div>
            <div class="right-actions">
              <button ref="sendButtonRef" type="button" class="send-btn circle" :disabled="!canSend || sending" @click="sendMessage()">
                ➤
              </button>
            </div>
          </div>
          <div v-if="uploadFile" class="upload-name">{{ uploadFile.name }}</div>
        </div>
      </section>
    </main>

    <div v-if="workspacePanel" class="workspace-mask" @click.self="closeWorkspacePanel">
      <div class="workspace-panel">
        <div class="workspace-head">
          <div class="workspace-title">{{ panelTitle }}</div>
          <button type="button" class="close-btn" @click="closeWorkspacePanel">×</button>
        </div>

        <div v-if="workspacePanel === 'search'" class="workspace-body">
          <div class="panel-search">
            <el-input v-model="searchKeyword" placeholder="输入关键词检索岗位、学生、报告和投递记录" @keyup.enter="loadSearch" />
            <button type="button" class="tiny-btn" @click="loadSearch">搜索</button>
          </div>
          <div v-if="searchState.loading" class="panel-state">检查中...</div>
          <div v-else-if="searchState.error" class="panel-state panel-error">{{ searchState.error }}</div>
          <div v-else-if="!searchKeyword.trim()" class="panel-state">输入关键词开始搜索</div>
          <div v-else-if="!searchState.items.length" class="panel-state">没有匹配结果</div>
          <div v-else class="panel-list">
            <button v-for="item in searchState.items" :key="`${item.type}-${item.title}-${item.route}`" type="button" class="panel-item" @click="openSearchResult(item)">
              <div class="panel-item-title">{{ item.title }}</div>
              <div class="panel-item-sub">{{ item.subtitle }}</div>
            </button>
          </div>
        </div>

        <div v-else-if="workspacePanel === 'assets'" class="workspace-body">
          <div v-if="assetsState.loading" class="panel-state">加载中...</div>
          <div v-else-if="assetsState.error" class="panel-state panel-error">{{ assetsState.error }}</div>
          <div v-else-if="!assetsState.items.length" class="panel-state">暂无资产</div>
          <div v-else class="panel-list">
            <div v-for="item in assetsState.items" :key="`asset-${item.type}-${item.id}`" class="panel-item panel-item-static">
              <div class="panel-item-title">{{ item.name }}</div>
              <div class="panel-item-sub">{{ item.type }} · {{ item.status }} · {{ item.updated_at }}</div>
              <div class="panel-item-actions">
                <button type="button" class="tiny-btn" @click="openAsset(item)">打开</button>
                <button v-if="item.download_url" type="button" class="tiny-btn panel-link-btn" @click.stop="openDownload(item.download_url)">下载</button>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="workspacePanel === 'gallery'" class="workspace-body">
          <div v-if="galleryState.loading" class="panel-state">加载中...</div>
          <div v-else-if="galleryState.error" class="panel-state panel-error">{{ galleryState.error }}</div>
          <div v-else-if="!galleryState.items.length" class="panel-state">暂无画廊内容</div>
          <div v-else class="gallery-grid">
            <button v-for="item in galleryState.items" :key="`gallery-${item.type}-${item.id}`" type="button" class="gallery-item" @click="openGallery(item)">
              <img v-if="isGalleryImage(item)" :src="item.thumb_url" :alt="item.title" class="gallery-thumb" />
              <div v-else class="gallery-icon-card">
                <span class="gallery-icon-tag">{{ galleryIconMeta(item).tag }}</span>
              </div>
              <div class="gallery-title">{{ item.title }}</div>
              <div class="gallery-time">{{ item.created_at }}</div>
            </button>
          </div>
        </div>

        <div v-else class="workspace-body">
          <div class="panel-state">当前工作区尚未开放该类型面板</div>
        </div>
      </div>
    </div>

    <SkillPickerDialog
      :visible="skillPickerVisible"
      :skills="skillOptions"
      :current-skill-code="activeSkillCode"
      @update:visible="skillPickerVisible = $event"
      @select="pickActiveSkill"
      @add="handleAddSkillEntry"
    />

    <AgentDetailDrawer :visible="detailDrawerVisible" :card="detailCard" @update:visible="detailDrawerVisible = $event" />

    <div v-if="loginVisible" class="login-mask" @click.self="closeLoginModal">
      <div class="login-modal">
        <div class="login-content">
          <div class="login-header">
            <h2>{{ authMode === 'login' ? '登录到 Career Agent' : '创建账号' }}</h2>
            <p>{{ authMode === 'login' ? '使用您的账号登录系统' : '填写信息以创建新账号' }}</p>
          </div>

          <div class="mode-tabs">
            <button type="button" :class="{ active: authMode === 'login' }" @click="switchMode('login')">登录</button>
            <button type="button" :class="{ active: authMode === 'register' }" @click="switchMode('register')">注册</button>
          </div>

          <div class="role-tabs">
            <button
              v-for="item in displayAccountCards"
              :key="item.type"
              type="button"
              :class="{ active: activePreset === item.type }"
              @click="selectRole(item.type)"
            >
              {{ item.label }}
            </button>
          </div>

          <div class="form-section">
            <template v-if="authMode === 'login'">
              <div class="input-field">
                <input v-model="loginForm.username" type="text" placeholder="请输入用户名" />
              </div>
              <div class="input-field">
                <input v-model="loginForm.password" type="password" placeholder="请输入密码" />
              </div>
              <button type="button" class="primary-btn" @click="submitLogin">登录</button>
            </template>
            <template v-else>
              <div class="input-field">
                <input v-model="registerForm.username" type="text" placeholder="请输入用户名" />
              </div>
              <div class="input-field">
                <input v-model="registerForm.real_name" type="text" placeholder="请输入姓名/联系人" />
              </div>
              <div class="input-field">
                <input v-model="registerForm.password" type="password" placeholder="请输入密码" />
              </div>
              <div class="input-field">
                <input v-model="registerForm.confirm_password" type="password" placeholder="请确认密码" />
              </div>
              <div class="input-field">
                <input v-if="registerForm.role_code === 'student'" v-model="registerForm.student_no" type="text" placeholder="请输入学号" />
                <input v-else v-model="registerForm.company_name" type="text" placeholder="请输入企业名称" />
              </div>
              <button type="button" class="primary-btn" @click="submitRegister">注册</button>
            </template>
          </div>

          <div class="divider">
            <span class="divider-line"></span>
            <span class="divider-text">其他方式登录</span>
            <span class="divider-line"></span>
          </div>

          <div class="social-buttons">
            <button type="button" class="social-btn qq-btn" @click="handleThirdPartyLogin('qq')">
              <span class="social-icon qq-icon">Q</span>
              QQ 登录
            </button>
            <button type="button" class="social-btn wx-btn" @click="handleThirdPartyLogin('wechat')">
              <span class="social-icon wx-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm5.34 2.867c-1.797-.052-3.746.512-5.28 1.786-1.72 1.428-2.687 3.72-1.78 6.22.942 2.453 3.666 4.229 6.884 4.229.826 0 1.622-.12 2.361-.336a.722.722 0 0 1 .598.082l1.584.926a.272.272 0 0 0 .14.047c.134 0 .24-.111.24-.247 0-.06-.023-.12-.038-.177l-.327-1.233a.582.582 0 0 1-.023-.156.49.49 0 0 1 .201-.398C23.024 18.48 24 16.82 24 14.98c0-3.21-2.931-5.837-6.656-6.088V8.87c-.135-.004-.272-.012-.407-.012zm-2.53 3.274c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.97-.982zm4.844 0c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.969-.982z"/>
                </svg>
              </span>
              微信登录
            </button>
          </div>

          <p class="login-footer">登录即表示您同意我们的服务条款和隐私政策</p>
        </div>

        <button type="button" class="close-btn" @click="closeLoginModal">×</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onBeforeUnmount, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { gsap } from "gsap";
import { assistantApi, studentApi } from "@/api";
import { useAuthStore } from "@/stores/auth";
import AgentSidebar from "@/components/AgentSidebar.vue";
import SkillPickerDialog from "@/components/SkillPickerDialog.vue";
import AgentDetailDrawer from "@/components/agent/AgentDetailDrawer.vue";
import AssistantCardRenderer from "@/components/agent/AssistantCardRenderer.vue";
import AssistantMessageRenderer from "@/components/agent/AssistantMessageRenderer.vue";
import ThinkingIndicator from "@/components/agent/ThinkingIndicator.vue";
import ScrollToLatestButton from "@/components/agent/ScrollToLatestButton.vue";
import { getRolePromptTemplates, normalizeSkillCode } from "@/constants/assistantSkills";
import { getAssistantClientContext, patchAssistantClientContext } from "@/composables/useAssistantSession";
import { menuGroups } from "@/utils/menusAgent";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

const GUEST_SESSIONS_KEY = "career_agent_guest_sessions";
const MAX_SESSIONS = 8;
const BACKEND_ORIGIN = "http://127.0.0.1:8000";
const BOTTOM_DISTANCE_THRESHOLD = 150;
const TYPEWRITER_CHARS_PER_SECOND = 48;
const TYPEWRITER_MIN_STEP = 1;
const BACKGROUND_POLL_INTERVAL_MS = 2500;

const prefersReducedMotion = ref(false);
let reduceMotionQuery = null;
let typingRafId = 0;
let typingLastAt = 0;
const backgroundPollTimers = new Map();

const sessions = ref([]);
const activeSessionId = ref("");
const draft = ref("");
const sending = ref(false);
const chatScrollRef = ref(null);
const composerBoxRef = ref(null);
const sendButtonRef = ref(null);
const uploadFile = ref(null);
const detailDrawerVisible = ref(false);
const detailCard = ref(null);
const activeContextBinding = ref({});
const showScrollToBottom = ref(false);
const isNearBottom = ref(true);
const unreadNewMessageCount = ref(0);
const userScrolledUp = ref(false);

const summaryLoading = ref(false);
const summaryError = ref("");
const summaryCardsData = ref([]);

const workspacePanel = ref("");
const skillPickerVisible = ref(false);
const activeSkillCode = ref("");
const searchKeyword = ref("");
const searchState = reactive({ loading: false, error: "", items: [] });
const assetsState = reactive({ loading: false, error: "", items: [] });
const galleryState = reactive({ loading: false, error: "", items: [] });
const skillsState = reactive({ loading: false, error: "", items: [] });

const loginVisible = ref(false);
const authMode = ref("login");
const activePreset = ref("student");

const loginForm = reactive({ username: "student01", password: "student123" });
const registerForm = reactive({
  role_code: "student",
  username: "",
  real_name: "",
  password: "",
  confirm_password: "",
  student_no: "",
  company_name: "",
  email: "",
  phone: "",
  grade: "",
  major: "",
  college: "",
  company_type: "",
  company_size: "",
  industry: "",
  address: "",
});

const accountCards = [
  { type: "student", label: "学生端", username: "student01", password: "student123" },
  { type: "enterprise", label: "企业端", username: "enterprise01", password: "enterprise123" },
  { type: "admin", label: "管理端", username: "admin", password: "admin123" },
];

const presets = {
  student: { username: "student01", password: "student123" },
  enterprise: { username: "enterprise01", password: "enterprise123" },
  admin: { username: "admin", password: "admin123" },
};

const promptTemplates = ref(getRolePromptTemplates(auth.role || "student"));


const activeSession = computed(() => sessions.value.find((item) => item.id === activeSessionId.value) || null);
const sidebarHistoryItems = computed(() =>
  sessions.value.map((item) => ({
    id: String(item.id),
    title: item.title || "新任务",
    lastSkill: item.lastSkill || "",
    updatedAt: item.updatedAt || "",
    lastMessage: item.lastMessage || "",
    pinned: !!item.pinned,
  })),
);
const activeMessages = computed(() =>
  (activeSession.value?.messages || []).filter((item) => !String(item.content || "").startsWith("执行")),
);
const showWelcome = computed(() => !activeMessages.value.length);
const canCreateTask = computed(() => activeMessages.value.length > 0);
const canSend = computed(() => {
  if (sending.value) return false;
  if (activeMessages.value.length > 0) return true;
  if (draft.value.trim()) return true;
  if (uploadFile.value) return true;
  return false;
});
const latestAssistantStreamState = computed(() => {
  const messages = activeSession.value?.messages || [];
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === "assistant") return messages[index].streamState || "done";
  }
  return "done";
});
const isThinkingGlobal = computed(() => sending.value && ["waiting", "streaming"].includes(latestAssistantStreamState.value));
const activeSidebarPath = computed(() => (route.path === "/" ? "/assistant" : route.path));
const panelTitle = computed(() => {
  if (workspacePanel.value === "search") return "全局搜索";
  if (workspacePanel.value === "assets") return "资产中心";
  if (workspacePanel.value === "gallery") return "画廊预览";
  return "工作区";
});

const visibleMenuGroups = computed(() =>
  menuGroups
    .map((group) => ({ ...group, items: group.items.filter((item) => item.roles.includes(auth.role)) }))
    .filter((group) => group.items.length),
);

const summaryCards = computed(() => summaryCardsData.value);
const skillOptions = computed(() => skillsState.items);
const activeSkill = computed(() => {
  const code = activeSkillCode.value;
  if (!code) return null;
  return findSkill(code) || null;
});

let composerThinkingTl = null;
let sendThinkingTl = null;

const stopGlobalThinkingFx = () => {
  composerThinkingTl?.kill();
  sendThinkingTl?.kill();
  composerThinkingTl = null;
  sendThinkingTl = null;
  if (composerBoxRef.value) gsap.set(composerBoxRef.value, { clearProps: "boxShadow,x" });
  if (sendButtonRef.value) gsap.set(sendButtonRef.value, { clearProps: "scale,boxShadow,x" });
};

const startGlobalThinkingFx = () => {
  if (!composerBoxRef.value || !sendButtonRef.value) return;
  stopGlobalThinkingFx();
  composerThinkingTl = gsap.timeline({ repeat: -1 });
  composerThinkingTl
    .to(composerBoxRef.value, { boxShadow: "0 22px 44px rgba(15, 23, 42, 0.08), 0 0 0 4px rgba(37, 99, 235, 0.12)", duration: 0.45, ease: "sine.inOut" })
    .to(composerBoxRef.value, { boxShadow: "0 22px 44px rgba(15, 23, 42, 0.08)", duration: 0.45, ease: "sine.inOut" });
  sendThinkingTl = gsap.timeline({ repeat: -1 });
  sendThinkingTl
    .to(sendButtonRef.value, { scale: 1.08, boxShadow: "0 0 0 6px rgba(37, 99, 235, 0.12)", duration: 0.45, ease: "sine.inOut" })
    .to(sendButtonRef.value, { scale: 1, boxShadow: "0 0 0 0 rgba(37, 99, 235, 0)", duration: 0.45, ease: "sine.inOut" });
};

const playGlobalErrorFx = () => {
  stopGlobalThinkingFx();
  if (!composerBoxRef.value || !sendButtonRef.value) return;
  gsap.timeline().to(composerBoxRef.value, { x: 4, duration: 0.06, yoyo: true, repeat: 3, ease: "power1.inOut" }).set(composerBoxRef.value, { x: 0 });
  gsap.timeline().to(sendButtonRef.value, { x: 3, boxShadow: "0 0 0 6px rgba(239, 68, 68, 0.24)", duration: 0.06, yoyo: true, repeat: 3, ease: "power1.inOut" }).set(sendButtonRef.value, { x: 0, boxShadow: "0 0 0 0 rgba(239, 68, 68, 0)" });
};

const displayAccountCards = computed(() =>
  authMode.value === "register" ? accountCards.filter((item) => item.type !== "admin") : accountCards,
);

const normalizeSessionTitle = (value = "") => {
  const text = String(value || "").trim();
  return (text || "新任务").slice(0, 40);
};

const nowText = () => new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
const formatMessageTime = (value) => {
  if (!value) return nowText();
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? nowText()
    : date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
};

const normalizeMessageText = (value) => String(value ?? "");
const isAssistantMessage = (message) => message && message.role === "assistant";
const ASSISTANT_VISIBLE_FALLBACK_TEXT = "当前模型服务连接不稳定，我先给你一版稳妥可执行的建议。你可以继续按“能力差距、表达话术、行动计划”分步追问。";
const ASSISTANT_INTERNAL_ERROR_TOKENS = [
  "traceback",
  "exception",
  "runtimeerror",
  "valueerror",
  "keyerror",
  "llm",
  "ssl",
  "network error",
  "unexpected_eof",
  "unexpected eof",
  "eof occurred",
  "provider",
  "urlerror",
  "connection reset",
  "remote disconnected",
];

const sanitizeAssistantVisibleText = (value, fallback = ASSISTANT_VISIBLE_FALLBACK_TEXT) => {
  const text = normalizeMessageText(value);
  if (!text.trim()) return text;
  const lowered = text.toLowerCase();
  return ASSISTANT_INTERNAL_ERROR_TOKENS.some((token) => lowered.includes(token)) ? fallback : text;
};

const toNullableNumber = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
};

const normalizeBackgroundJob = (value = {}) => {
  if (!value || typeof value !== "object") return {};
  const id = String(value.id || "").trim();
  const status = String(value.status || "").trim();
  if (!id && !status) return {};
  return {
    ...value,
    id,
    type: String(value.type || "resume_optimization"),
    status: status || "running",
    phase: String(value.phase || status || "running"),
    message: String(value.message || ""),
    message_id: toNullableNumber(value.message_id),
    session_id: toNullableNumber(value.session_id),
    started_at: String(value.started_at || ""),
    finished_at: String(value.finished_at || ""),
    error: String(value.error || ""),
  };
};

const BACKGROUND_ACTIVE_STATUSES = new Set(["queued", "running", "extracting", "optimizing", "rendering_word", "registering_artifact"]);

const isBackgroundJobRunning = (job = {}) => BACKGROUND_ACTIVE_STATUSES.has(normalizeBackgroundJob(job).status);
const isBackgroundJobFailed = (job = {}) => normalizeBackgroundJob(job).status === "failed";

const isBackgroundFileTaskRunning = (fileTask = {}) =>
  !!(fileTask && typeof fileTask === "object" && fileTask.background && BACKGROUND_ACTIVE_STATUSES.has(String(fileTask.status || "")));

const isAssistantBackgroundRunning = (message = {}) =>
  isBackgroundJobRunning(message.backgroundJob) || isBackgroundFileTaskRunning(message.fileTask);

const backgroundThinkingText = (job = {}) => {
  const normalized = normalizeBackgroundJob(job);
  if (normalized.message) return normalized.message;
  const phaseText = {
    queued: "简历任务已进入后台队列。",
    extracting: "正在解析简历附件...",
    optimizing: "正在按目标岗位优化简历...",
    rendering_word: "正在生成 Word 文件...",
    registering_artifact: "正在登记 Word 下载文件...",
    running: "后台优化中，完成后会自动更新这条消息。",
  };
  return phaseText[normalized.phase] || "后台优化中，完成后会自动更新这条消息。";
};

const finalStreamStateForData = (data = {}) => {
  if (data?.error) return "error";
  const job = normalizeBackgroundJob(data?.background_job || data?.backgroundJob || {});
  const fileTask = data?.file_task || data?.fileTask || {};
  if (isBackgroundJobRunning(job) || isBackgroundFileTaskRunning(fileTask)) return "waiting";
  if (isBackgroundJobFailed(job) || String(fileTask?.status || "") === "failed") return "error";
  return "done";
};

const closeThinkingProcessForFinalState = (message, state = "") => {
  if (!isAssistantMessage(message)) return;
  if (!["waiting", "streaming"].includes(String(state || message.streamState || ""))) {
    message.thinkingProcessOpen = false;
  }
};

const takeLeadingChars = (text, count) => {
  const chars = Array.from(String(text || ""));
  const take = Math.max(0, Math.min(Number(count) || 0, chars.length));
  return {
    chunk: chars.slice(0, take).join(""),
    rest: chars.slice(take).join(""),
  };
};

const initMessageRenderState = (message, { animate = false } = {}) => {
  if (!isAssistantMessage(message)) return message;
  const fullText = sanitizeAssistantVisibleText(message.content);
  const typingEnabled = !!animate && !prefersReducedMotion.value;
  message.fullContent = fullText;
  message.typingEnabled = typingEnabled;
  message.typingQueue = typingEnabled ? fullText : "";
  message.typingCompleted = !typingEnabled;
  message.pendingFinalState = "";
  message.content = typingEnabled ? "" : fullText;
  if (typingEnabled && message.typingQueue) ensureTypewriterLoop();
  return message;
};

const flushMessageTyping = (message) => {
  if (!isAssistantMessage(message)) return;
  message.content = normalizeMessageText(message.fullContent || message.content);
  message.typingQueue = "";
  message.typingCompleted = true;
  if (message.pendingFinalState) {
    message.streamState = message.pendingFinalState;
    closeThinkingProcessForFinalState(message, message.streamState);
    message.pendingFinalState = "";
  }
};

const enqueueMessageTyping = (message, chunkText) => {
  if (!isAssistantMessage(message)) return;
  const chunk = normalizeMessageText(chunkText);
  if (!chunk) return;
  const currentFull = normalizeMessageText(message.fullContent || message.content);
  const mergedFull = `${currentFull}${chunk}`;
  const nextFull = sanitizeAssistantVisibleText(mergedFull);
  message.fullContent = nextFull;
  if (nextFull !== mergedFull) {
    message.content = nextFull;
    message.typingQueue = "";
    message.typingCompleted = true;
    return;
  }

  if (!message.typingEnabled || prefersReducedMotion.value) {
    message.content = nextFull;
    message.typingQueue = "";
    message.typingCompleted = true;
    return;
  }

  message.typingQueue = `${normalizeMessageText(message.typingQueue)}${chunk}`;
  message.typingCompleted = false;
  ensureTypewriterLoop();
};

const applyFinalMessageContent = (message, finalText, { replace = false } = {}) => {
  if (!isAssistantMessage(message)) return;
  const nextText = sanitizeAssistantVisibleText(finalText);

  if (!message.typingEnabled || prefersReducedMotion.value) {
    message.fullContent = nextText;
    message.content = nextText;
    message.typingQueue = "";
    message.typingCompleted = true;
    return;
  }

  const visibleText = normalizeMessageText(message.content);
  const currentFull = normalizeMessageText(message.fullContent || visibleText);

  if (replace) {
    message.fullContent = nextText;
    if (nextText.startsWith(visibleText)) {
      message.typingQueue = nextText.slice(visibleText.length);
    } else {
      message.content = "";
      message.typingQueue = nextText;
    }
    message.typingCompleted = !message.typingQueue;
    if (message.typingQueue) ensureTypewriterLoop();
    return;
  }

  if (!nextText || nextText === currentFull) return;

  if (nextText.startsWith(currentFull)) {
    message.fullContent = nextText;
    message.typingQueue = `${normalizeMessageText(message.typingQueue)}${nextText.slice(currentFull.length)}`;
    message.typingCompleted = false;
    ensureTypewriterLoop();
    return;
  }

  if (nextText.startsWith(visibleText)) {
    message.fullContent = nextText;
    message.typingQueue = nextText.slice(visibleText.length);
    message.typingCompleted = !message.typingQueue;
    if (message.typingQueue) ensureTypewriterLoop();
    return;
  }

  message.fullContent = nextText;
  message.content = nextText;
  message.typingQueue = "";
  message.typingCompleted = true;
};

const collectTypingMessages = () =>
  sessions.value
    .flatMap((session) => (Array.isArray(session.messages) ? session.messages : []))
    .filter((message) => isAssistantMessage(message) && message.typingEnabled && normalizeMessageText(message.typingQueue));

const stopTypewriterLoop = () => {
  if (typingRafId) window.cancelAnimationFrame(typingRafId);
  typingRafId = 0;
  typingLastAt = 0;
};

const typewriterFrame = (timestamp) => {
  if (!typingLastAt) typingLastAt = timestamp;
  const elapsed = Math.max(16, timestamp - typingLastAt);
  typingLastAt = timestamp;
  const step = Math.max(TYPEWRITER_MIN_STEP, Math.floor((elapsed / 1000) * TYPEWRITER_CHARS_PER_SECOND));
  const pending = collectTypingMessages();
  if (!pending.length) {
    stopTypewriterLoop();
    return;
  }

  for (const message of pending) {
    const queueText = normalizeMessageText(message.typingQueue);
    if (!queueText) continue;
    const { chunk, rest } = takeLeadingChars(queueText, step);
    if (chunk) message.content = `${normalizeMessageText(message.content)}${chunk}`;
    message.typingQueue = rest;
    if (!rest) {
      message.typingCompleted = true;
      if (message.pendingFinalState) {
        message.streamState = message.pendingFinalState;
        closeThinkingProcessForFinalState(message, message.streamState);
        message.pendingFinalState = "";
      }
    } else {
      message.typingCompleted = false;
    }
  }

  if (collectTypingMessages().length) {
    typingRafId = window.requestAnimationFrame(typewriterFrame);
    return;
  }
  stopTypewriterLoop();
};

const ensureTypewriterLoop = () => {
  if (prefersReducedMotion.value) return;
  if (typingRafId) return;
  typingRafId = window.requestAnimationFrame(typewriterFrame);
};

const applyReducedMotionPreference = (matches) => {
  prefersReducedMotion.value = !!matches;
  if (!prefersReducedMotion.value) return;

  stopTypewriterLoop();
  sessions.value.forEach((session) => {
    (session.messages || []).forEach((message) => {
      if (!isAssistantMessage(message)) return;
      message.typingEnabled = false;
      flushMessageTyping(message);
    });
  });
};

const handleReducedMotionChange = (event) => {
  applyReducedMotionPreference(!!event?.matches);
};

const shouldTypewriter = (message) =>
  !!(isAssistantMessage(message) && !prefersReducedMotion.value && normalizeMessageText(message.typingQueue));

const shouldRenderPlainText = (message) =>
  !!(
    isAssistantMessage(message)
    && (
      shouldTypewriter(message)
      || ["waiting", "streaming"].includes(String(message.streamState || ""))
      || isAssistantBackgroundRunning(message)
    )
  );

const saveGuestSessions = () => {
  if (auth.isLoggedIn) return;
  const payload = sessions.value.slice(0, MAX_SESSIONS).map((item) => ({
    id: String(item.id),
    title: normalizeSessionTitle(item.title),
    messages: Array.isArray(item.messages) ? item.messages : [],
    lastMessage: item.lastMessage || "",
    updatedAt: item.updatedAt || "",
    lastSkill: item.lastSkill || "",
    pinned: !!item.pinned,
    state: item.state || {},
  }));
  localStorage.setItem(GUEST_SESSIONS_KEY, JSON.stringify(payload));
};

const createGuestSession = (title = "新任务") => {
  const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const session = {
    id: String(id),
    title: normalizeSessionTitle(title),
    messages: [],
    lastMessage: "",
    updatedAt: new Date().toISOString(),
    lastSkill: "",
    pinned: false,
    state: {},
  };
  sessions.value.unshift(session);
  if (sessions.value.length > MAX_SESSIONS) sessions.value = sessions.value.slice(0, MAX_SESSIONS);
  activeSessionId.value = String(id);
  saveGuestSessions();
  return session;
};

const loadGuestSessions = () => {
  sessions.value = (JSON.parse(localStorage.getItem(GUEST_SESSIONS_KEY) || "[]") || [])
    .slice(0, MAX_SESSIONS)
    .map((item) => ({
      id: String(item.id),
      title: normalizeSessionTitle(item.title),
      messages: Array.isArray(item.messages)
        ? item.messages.map((msg) =>
            initMessageRenderState(
              {
                ...msg,
                serverId: toNullableNumber(msg?.serverId),
                content: normalizeMessageText(msg?.fullContent || msg?.content),
                taskPatch: msg?.taskPatch || {},
                replyMode: msg?.replyMode || "",
                replyBlocks: parseReplyBlocks(msg?.replyBlocks || []),
                streamState: msg?.streamState || "done",
                thinkingText: msg?.thinkingText || "",
                progressEvents: Array.isArray(msg?.progressEvents) ? msg.progressEvents : [],
                agentRoute: msg?.agentRoute || "chat",
                requiresUserInput: !!msg?.requiresUserInput,
                artifacts: Array.isArray(msg?.artifacts) ? msg.artifacts : [],
                fileTask: msg?.fileTask || {},
                backgroundJob: normalizeBackgroundJob(msg?.backgroundJob || {}),
                agentFlow: parseAgentFlow(msg?.agentFlow || []),
                supervisorPlan: msg?.supervisorPlan || {},
                dispatchTrace: normalizeDispatchTrace(msg?.dispatchTrace || {}),
                decisionTrace: Array.isArray(msg?.decisionTrace) ? msg.decisionTrace : [],
                thinkingProcessOpen: typeof msg?.thinkingProcessOpen === "boolean" ? msg.thinkingProcessOpen : undefined,
              },
              { animate: false },
            )
          )
        : [],
      lastMessage: item.lastMessage || "",
      updatedAt: item.updatedAt || "",
      lastSkill: item.lastSkill || "",
      pinned: !!item.pinned,
      state: item.state || {},
    }));
  if (!sessions.value.length) {
    createGuestSession("新任务");
    return;
  }
  const routeSessionId = String(route.query.session || "");
  activeSessionId.value = sessions.value.find((item) => item.id === routeSessionId)?.id || sessions.value[0].id;
  const active = sessions.value.find((item) => item.id === activeSessionId.value);
  activeContextBinding.value = active?.state?.context_binding || {};
  syncSessionRoute(activeSessionId.value);
};

const normalizeServerSession = (item) => ({
  id: String(item.id),
  title: normalizeSessionTitle(item.title),
  lastMessage: item.last_message || "",
  updatedAt: item.updated_at || "",
  lastSkill: skillNameOf(item.last_skill || "") || item.last_skill || "",
  pinned: !!item.pinned,
  state: item.state_json || {},
  messages: [],
});

const createServerSession = async (title = "新任务") => {
  const res = await assistantApi.createSession({ title: normalizeSessionTitle(title) });
  const session = normalizeServerSession(res?.data || {});
  sessions.value.unshift(session);
  activeSessionId.value = session.id;
  return session;
};

const buildMessageFromServerItem = (item = {}, { animate = false } = {}) => {
  const meta = item.meta && typeof item.meta === "object" ? item.meta : {};
  const backgroundJob = normalizeBackgroundJob(item.background_job || meta.background_job || {});
  const fileTask = item.file_task || meta.file_task || {};
  const streamState = isBackgroundJobRunning(backgroundJob) || isBackgroundFileTaskRunning(fileTask)
    ? "waiting"
    : isBackgroundJobFailed(backgroundJob) || String(fileTask?.status || "") === "failed"
      ? "error"
      : "done";
  const message = {
    serverId: toNullableNumber(item.id),
    role: item.role,
    content: item.content,
    knowledgeHits: item.knowledge_hits_json || [],
    skillName: skillNameOf(item.skill || "") || item.skill || "",
    toolSteps: parseToolSteps(item.tool_steps || []),
    cards: Array.isArray(item.result_cards) ? item.result_cards : [],
    actions: Array.isArray(meta.actions) ? meta.actions : [],
    contextBinding: meta.context_binding || {},
    sessionState: meta.session_state || {},
    taskPatch: item.task_patch || meta.task_patch || {},
    replyMode: item.reply_mode || meta.reply_mode || "",
    replyBlocks: parseReplyBlocks(item.reply_blocks || meta.reply_blocks || []),
    agentRoute: item.agent_route || meta.agent_route || "chat",
    requiresUserInput: !!(item.requires_user_input || meta.requires_user_input),
    artifacts: Array.isArray(item.artifacts || meta.artifacts) ? (item.artifacts || meta.artifacts) : [],
    fileTask,
    backgroundJob,
    agentFlow: parseAgentFlow(item.agent_flow || meta.agent_flow || []),
    supervisorPlan: item.supervisor_plan || meta.supervisor_plan || {},
    dispatchTrace: normalizeDispatchTrace(item.dispatch_trace || meta.dispatch_trace || {}),
    decisionTrace: Array.isArray(item.decision_trace || meta.decision_trace) ? (item.decision_trace || meta.decision_trace) : [],
    streamState,
    thinkingText: streamState === "waiting" ? backgroundThinkingText(backgroundJob) : "",
    progressEvents: Array.isArray(meta.progress_events) ? meta.progress_events : [],
    time: formatMessageTime(item.created_at),
  };
  return initMessageRenderState(message, { animate });
};

const loadServerMessages = async (sessionId) => {
  const target = sessions.value.find((item) => item.id === String(sessionId));
  if (!target) return;
  const res = await assistantApi.sessionMessages(Number(sessionId));
  target.messages = (res?.data?.items || []).map((item) => buildMessageFromServerItem(item));
  target.lastSkill = target.lastSkill || target.messages.findLast((item) => item.skillName)?.skillName || "";
  const lastState = [...target.messages].reverse().find((item) => item.role === "assistant" && Object.keys(item.sessionState || {}).length);
  if (lastState?.sessionState) target.state = lastState.sessionState;
  const lastAssistant = [...target.messages].reverse().find((item) => item.role === "assistant");
  const messageBinding = lastAssistant?.contextBinding || {};
  const stateBinding = target.state?.context_binding || {};
  activeContextBinding.value = Object.keys(messageBinding).length ? messageBinding : stateBinding;
  unreadNewMessageCount.value = 0;
  syncBackgroundPollersForSession(target.id);
  await scrollToBottom({ mode: "force", force: true });
};

const backgroundPollKey = (sessionId, job = {}, message = {}) => {
  const normalized = normalizeBackgroundJob(job);
  return `${String(sessionId)}:${normalized.id || normalized.message_id || message.serverId || ""}`;
};

const stopBackgroundPoll = (key) => {
  const timer = backgroundPollTimers.get(key);
  if (timer) window.clearInterval(timer);
  backgroundPollTimers.delete(key);
};

const stopBackgroundPollingForSession = (sessionId) => {
  const prefix = `${String(sessionId)}:`;
  Array.from(backgroundPollTimers.keys()).forEach((key) => {
    if (key.startsWith(prefix)) stopBackgroundPoll(key);
  });
};

const stopAllBackgroundPolling = () => {
  Array.from(backgroundPollTimers.keys()).forEach((key) => stopBackgroundPoll(key));
};

const findBackgroundServerItem = (items = [], job = {}, message = {}) => {
  const normalizedJob = normalizeBackgroundJob(job);
  const messageId = normalizedJob.message_id || message.serverId || null;
  if (messageId) {
    const byMessageId = items.find((item) => toNullableNumber(item.id) === messageId);
    if (byMessageId) return byMessageId;
  }
  if (normalizedJob.id) {
    return items.find((item) => {
      const itemJob = normalizeBackgroundJob(item.background_job || item.meta?.background_job || {});
      return itemJob.id === normalizedJob.id;
    }) || null;
  }
  return null;
};

const replaceLocalMessageFromServer = (sessionId, localMessage, serverItem) => {
  const session = sessions.value.find((item) => item.id === String(sessionId));
  if (!session) return null;
  const messages = Array.isArray(session.messages) ? session.messages : [];
  const serverMessageId = toNullableNumber(serverItem?.id);
  const serverJob = normalizeBackgroundJob(serverItem?.background_job || serverItem?.meta?.background_job || {});
  const localJob = normalizeBackgroundJob(localMessage?.backgroundJob || {});
  const index = messages.findIndex((item) => {
    if (serverMessageId && item.serverId === serverMessageId) return true;
    const itemJob = normalizeBackgroundJob(item.backgroundJob || {});
    if (serverJob.id && itemJob.id === serverJob.id) return true;
    if (localJob.id && itemJob.id === localJob.id) return true;
    return item === localMessage;
  });
  if (index < 0) return null;
  const nextMessage = buildMessageFromServerItem(serverItem);
  messages.splice(index, 1, nextMessage);
  session.lastMessage = normalizeMessageText(nextMessage.fullContent || nextMessage.content || "");
  session.updatedAt = new Date().toISOString();
  if (Object.keys(nextMessage.contextBinding || {}).length) {
    activeContextBinding.value = nextMessage.contextBinding;
    session.state = { ...(session.state || {}), context_binding: nextMessage.contextBinding };
  }
  return nextMessage;
};

const startBackgroundPollingForMessage = (sessionId, message) => {
  if (!auth.isLoggedIn || !message || !isAssistantBackgroundRunning(message)) return;
  const job = normalizeBackgroundJob(message.backgroundJob || {});
  const key = backgroundPollKey(sessionId, job, message);
  if (!key || backgroundPollTimers.has(key)) return;

  let inFlight = false;
  const poll = async () => {
    if (inFlight) return;
    if (!auth.isLoggedIn || activeSessionId.value !== String(sessionId)) {
      stopBackgroundPoll(key);
      return;
    }
    inFlight = true;
    try {
      const res = await assistantApi.sessionMessages(Number(sessionId));
      if (!auth.isLoggedIn || activeSessionId.value !== String(sessionId)) {
        stopBackgroundPoll(key);
        return;
      }
      const serverItem = findBackgroundServerItem(res?.data?.items || [], job, message);
      if (!serverItem) return;
      const serverJob = normalizeBackgroundJob(serverItem.background_job || serverItem.meta?.background_job || {});
      const serverFileTask = serverItem.file_task || serverItem.meta?.file_task || {};
      if (isBackgroundJobRunning(serverJob) || isBackgroundFileTaskRunning(serverFileTask)) {
        message.backgroundJob = serverJob;
        message.fileTask = serverFileTask;
        message.streamState = "waiting";
        message.thinkingText = backgroundThinkingText(serverJob);
        return;
      }

      const updatedMessage = replaceLocalMessageFromServer(sessionId, message, serverItem);
      stopBackgroundPoll(key);
      if (updatedMessage) {
        await nextTick();
        await scrollToBottom({ mode: "conditional" });
      }
    } catch (_) {
      // Keep polling; transient network failures should not strand the background job UI.
    } finally {
      inFlight = false;
    }
  };

  backgroundPollTimers.set(key, window.setInterval(poll, BACKGROUND_POLL_INTERVAL_MS));
  poll();
};

const syncBackgroundPollersForSession = (sessionId) => {
  if (!auth.isLoggedIn) return;
  stopBackgroundPollingForSession(sessionId);
  const session = sessions.value.find((item) => item.id === String(sessionId));
  (session?.messages || []).forEach((message) => startBackgroundPollingForMessage(sessionId, message));
};

const loadServerSessions = async ({ createIfEmpty = false } = {}) => {
  const currentId = activeSessionId.value;
  const routeSessionId = String(route.query.session || "");
  const res = await assistantApi.sessions();
  sessions.value = (res?.data?.items || []).map(normalizeServerSession);
  if (!sessions.value.length && createIfEmpty) {
    const created = await createServerSession("新任务");
    await loadServerMessages(created.id);
    return;
  }
  const target =
    sessions.value.find((item) => item.id === routeSessionId) ||
    sessions.value.find((item) => item.id === String(currentId)) ||
    sessions.value[0] ||
    null;
  activeSessionId.value = target?.id || "";
  if (target) {
    await loadServerMessages(target.id);
    syncSessionRoute(target.id);
  }
};

const refreshServerSessions = async () => {
  const currentId = activeSessionId.value;
  const currentMessages = activeSession.value?.messages || [];
  const currentState = activeSession.value?.state || {};
  const res = await assistantApi.sessions();
  sessions.value = (res?.data?.items || []).map(normalizeServerSession);
  const keep = sessions.value.find((item) => item.id === String(currentId)) || sessions.value[0] || null;
  activeSessionId.value = keep?.id || "";
  if (!keep) return;
  if (keep.id === String(currentId)) {
    keep.messages = currentMessages;
    keep.state = currentState;
  } else {
    await loadServerMessages(keep.id);
  }
  activeContextBinding.value = keep.state?.context_binding || activeContextBinding.value;
  syncSessionRoute(keep.id);
  syncBackgroundPollersForSession(keep.id);
};

const syncSessionRoute = (sessionId = "") => {
  const nextQuery = { ...route.query };
  if (sessionId) nextQuery.session = String(sessionId);
  else delete nextQuery.session;
  router.replace({ path: route.path, query: nextQuery });
};

const ensureActiveSession = async () => {
  if (activeSession.value) return activeSession.value;
  if (auth.isLoggedIn) return createServerSession("新任务");
  return createGuestSession("新任务");
};

const appendGuestMessage = (
  role,
  content,
  knowledgeHits = [],
  skillName = "",
  resultCard = null,
  toolSteps = [],
  cards = [],
  actions = [],
  contextBinding = {},
  taskPatch = {},
  replyMode = "",
  replyBlocks = [],
  streamState = role === "assistant" ? "done" : "",
  agentRoute = "chat",
  requiresUserInput = false,
  artifacts = [],
  fileTask = {},
  agentFlow = [],
  animate = false,
) => {
  const session = activeSession.value || createGuestSession("新任务");
  const time = nowText();
  const message = {
    serverId: null,
    role,
    content,
    knowledgeHits,
    skillName,
    resultCard,
    toolSteps,
    cards,
    actions,
    contextBinding,
    taskPatch,
    replyMode,
    replyBlocks: parseReplyBlocks(replyBlocks),
    streamState,
    thinkingText: "",
    progressEvents: [],
    agentRoute,
    requiresUserInput,
    artifacts: Array.isArray(artifacts) ? artifacts : [],
    fileTask: fileTask || {},
    backgroundJob: {},
    agentFlow: parseAgentFlow(agentFlow || []),
    supervisorPlan: {},
    dispatchTrace: normalizeDispatchTrace({}),
    decisionTrace: [],
    thinkingProcessOpen: undefined,
    time,
  };
  initMessageRenderState(message, { animate: role === "assistant" && !!animate });
  session.messages.push(message);
  handleMessageAppended(role);
  session.lastMessage = normalizeMessageText(message.fullContent || message.content);
  session.updatedAt = new Date().toISOString();
  if (skillName) session.lastSkill = skillName;
  if (Object.keys(contextBinding || {}).length) {
    activeContextBinding.value = contextBinding || {};
    session.state = { ...(session.state || {}), context_binding: contextBinding };
  }
  if (role === "user" && session.title === "新任务") session.title = normalizeSessionTitle(content.slice(0, 16));
  saveGuestSessions();
  return message;
};

const appendActiveMessage = (
  role,
  content,
  knowledgeHits = [],
  skillName = "",
  resultCard = null,
  toolSteps = [],
  cards = [],
  actions = [],
  contextBinding = {},
  taskPatch = {},
  replyMode = "",
  replyBlocks = [],
  streamState = role === "assistant" ? "done" : "",
  agentRoute = "chat",
  requiresUserInput = false,
  artifacts = [],
  fileTask = {},
  agentFlow = [],
  animate = false,
) => {
  const session = activeSession.value;
  if (!session) return;
  const time = nowText();
  const message = {
    serverId: null,
    role,
    content,
    knowledgeHits,
    skillName,
    resultCard,
    toolSteps,
    cards,
    actions,
    contextBinding,
    taskPatch,
    replyMode,
    replyBlocks: parseReplyBlocks(replyBlocks),
    streamState,
    thinkingText: "",
    progressEvents: [],
    agentRoute,
    requiresUserInput,
    artifacts: Array.isArray(artifacts) ? artifacts : [],
    fileTask: fileTask || {},
    backgroundJob: {},
    agentFlow: parseAgentFlow(agentFlow || []),
    supervisorPlan: {},
    dispatchTrace: normalizeDispatchTrace({}),
    decisionTrace: [],
    thinkingProcessOpen: undefined,
    time,
  };
  initMessageRenderState(message, { animate: role === "assistant" && !!animate });
  session.messages.push(message);
  handleMessageAppended(role);
  session.lastMessage = normalizeMessageText(message.fullContent || message.content);
  session.updatedAt = new Date().toISOString();
  if (skillName) session.lastSkill = skillName;
  if (Object.keys(contextBinding || {}).length) {
    activeContextBinding.value = contextBinding || {};
    session.state = { ...(session.state || {}), context_binding: contextBinding };
  }
  if (role === "user" && session.title === "新任务") {
    session.title = normalizeSessionTitle(content.slice(0, 16));
    if (auth.isLoggedIn && session.id) {
      assistantApi.updateSession(Number(session.id), { title: session.title }).catch(() => {});
    }
  }
  if (!auth.isLoggedIn) saveGuestSessions();
  return message;
};

const parseToolSteps = (steps = []) =>
  (Array.isArray(steps) ? steps : [])
    .map((item) => {
      if (typeof item === "string") return { text: item.trim(), status: "done" };
      if (item && typeof item === "object") {
        const text = String(item.text || item.title || item.summary || item.tool || "").trim();
        return text ? { text, status: item.status || "done", tool: item.tool || "" } : null;
      }
      return null;
    })
    .filter(Boolean);

const parseAgentFlow = (flow = []) =>
  (Array.isArray(flow) ? flow : [])
    .map((item, index) => {
      if (!item || typeof item !== "object") return null;
      const stepRaw = Number(item.step);
      const step = Number.isFinite(stepRaw) && stepRaw > 0 ? stepRaw : index + 1;
      const agent = String(item.agent || "").trim();
      const action = String(item.action || item.text || "").trim();
      return {
        ...item,
        step,
        agent,
        action,
      };
    })
    .filter(Boolean);

const normalizeDispatchTrace = (trace = {}) => {
  const value = trace && typeof trace === "object" ? trace : {};
  return {
    ...value,
    events: Array.isArray(value.events) ? value.events : [],
  };
};

const hasOwnContextKey = (value, key) => Object.prototype.hasOwnProperty.call(value || {}, key);

const contextBindingValue = (binding = {}, key, nestedKey, fallback = null) => {
  if (hasOwnContextKey(binding, key)) return binding[key];
  const resume = binding?.resume && typeof binding.resume === "object" ? binding.resume : {};
  if (nestedKey && hasOwnContextKey(resume, nestedKey)) return resume[nestedKey];
  return fallback ?? null;
};

const shouldClearAssistantResumeContext = (data = {}) => {
  const fileTask = data?.file_task && typeof data.file_task === "object" ? data.file_task : {};
  if (!data?.requires_user_input || fileTask.status !== "needs_input") return false;
  const missingFields = Array.isArray(fileTask.missing_fields) ? fileTask.missing_fields.map((item) => String(item)) : [];
  const invalidFields = Array.isArray(fileTask.invalid_fields) ? fileTask.invalid_fields.map((item) => String(item)) : [];
  return [...missingFields, ...invalidFields].some((item) =>
    ["attachment_id", "resume_id", "resume_version_id"].includes(item),
  );
};

const hasThinkingProcessData = (message) => {
  if (!message || message.role !== "assistant") return false;
  if ((message.dispatchTrace?.events || []).length) return true;
  if (message.supervisorPlan?.steps?.length) return true;
  if (message.decisionTrace?.length) return true;
  return (message.progressEvents || []).length > 0 && ["waiting", "streaming", "error"].includes(message.streamState || "");
};

const shouldShowThinkingProcess = (message) => hasThinkingProcessData(message);

const isThinkingProcessOpen = (message) => {
  if (!message) return false;
  if (typeof message.thinkingProcessOpen === "boolean") return message.thinkingProcessOpen;
  return ["waiting", "streaming"].includes(message.streamState || "");
};

const toggleThinkingProcess = (message) => {
  if (!message) return;
  message.thinkingProcessOpen = !isThinkingProcessOpen(message);
};

const thinkingProcessTitle = (message) => {
  const duration = thinkingProcessDurationMs(message);
  if (["waiting", "streaming"].includes(message?.streamState || "")) {
    return duration ? `思考中 ${formatDuration(duration)}` : "思考中";
  }
  return duration ? `已思考 ${formatDuration(duration)}` : "思考过程";
};

const thinkingProcessDurationMs = (message) => {
  const trace = message?.dispatchTrace || {};
  const startedAt = Date.parse(trace.started_at || "");
  const finishedAt = Date.parse(trace.finished_at || "");
  if (Number.isFinite(startedAt) && Number.isFinite(finishedAt) && finishedAt > startedAt) return finishedAt - startedAt;
  const total = (trace.events || []).reduce((sum, item) => sum + Number(item?.duration_ms || 0), 0);
  return Number.isFinite(total) ? total : 0;
};

const thinkingProcessEvents = (message) => {
  const traceEvents = (message?.dispatchTrace?.events || []).map((item) => ({
    event: item.event || "调度事件",
    status: item.status || "running",
    agent_key: item.agent_key || "",
    step_id: item.step_id || "",
    summary: item.summary || item.message || "",
    decision_summary: item.decision_summary || "",
    output_summary: item.output_summary || "",
    failure_reason: item.failure_reason || item.fallback_reason || "",
    event_id: item.event_id || "",
    duration_ms: Number(item.duration_ms || 0),
  }));
  if (traceEvents.length) return traceEvents;
  return (message?.progressEvents || []).map((item) => ({
    event: item.phase || "处理任务",
    status: item.status || "running",
    agent_key: "",
    step_id: "",
    summary: item.message || "",
    decision_summary: "",
    output_summary: "",
    failure_reason: item.error || "",
    event_id: "",
    duration_ms: 0,
  }));
};

const thinkingEventName = (event = "") => {
  const value = String(event || "").trim();
  const names = {
    accepted: "接收问题",
    agent_workflow: "分析问题并组织回复",
    responding: "生成回复",
    done: "完成回复",
    background_polling: "查询后台结果",
  };
  if (names[value]) return names[value];
  return value.replace(/[_-]+/g, " ") || "处理任务";
};

const thinkingEventSentence = (event = {}, index = 0) => {
  const status = String(event.status || "").trim();
  const detail = String(
    event.failure_reason ||
    event.output_summary ||
    event.summary ||
    event.decision_summary ||
    "",
  ).trim();
  if (detail) return detail;

  const name = thinkingEventName(event.event);
  if (status === "failed" || status === "error") return `${name}时遇到问题。`;
  if (status === "done" || status === "success" || status === "completed") return `${name}已完成。`;
  if (status === "fallback") return `${name}已切换到备用方案。`;
  return index === 0 ? `正在${name}。` : `${name}进行中。`;
};

const thinkingLineStatusClass = (status = "") => {
  if (status === "failed" || status === "error") return "is-error";
  if (status === "done" || status === "success" || status === "completed") return "is-done";
  if (status === "fallback") return "is-muted";
  return "is-running";
};

const thinkingCurrentText = (message) => {
  const liveText = String(message?.thinkingText || "").trim();
  if (["waiting", "streaming"].includes(message?.streamState || "") && liveText) return liveText;
  const events = thinkingProcessEvents(message);
  const latest = events[events.length - 1];
  return latest ? thinkingEventSentence(latest, events.length - 1) : "";
};

const thinkingProcessLines = (message) => {
  const lines = [];
  const objective = String(message?.supervisorPlan?.objective || "").trim();
  if (objective) {
    lines.push({ text: `我会围绕「${objective}」来组织回答。`, statusClass: "is-muted" });
  }

  const planSteps = Array.isArray(message?.supervisorPlan?.steps) ? message.supervisorPlan.steps : [];
  planSteps.slice(0, 6).forEach((step, index) => {
    const title = String(step?.title || step?.key || `步骤 ${index + 1}`).trim();
    const description = String(step?.description || "").trim();
    lines.push({
      text: description ? `第 ${index + 1} 步：${title}，${description}` : `第 ${index + 1} 步：${title}`,
      statusClass: "is-muted",
    });
  });

  thinkingProcessEvents(message).forEach((event, index) => {
    const text = thinkingEventSentence(event, index);
    if (!text || lines.some((line) => line.text === text)) return;
    lines.push({
      text,
      statusClass: thinkingLineStatusClass(event.status || ""),
    });
  });

  return lines.slice(-10);
};

const formatDuration = (durationMs = 0) => {
  const ms = Math.max(0, Number(durationMs || 0));
  if (!Number.isFinite(ms) || ms <= 0) return "";
  const seconds = ms / 1000;
  if (seconds < 1) return `${Math.round(ms)} 毫秒`;
  return `${seconds.toFixed(seconds >= 10 ? 0 : 1)} 秒`;
};

const assistantProgressText = (payload = {}) => {
  const message = sanitizeAssistantVisibleText(payload?.message || payload?.title || "", "").trim();
  if (message) return message;
  const phase = String(payload?.phase || "").trim();
  const phaseText = {
    accepted: "请求已接收，正在准备工作流...",
    agent_workflow: "Agent 正在处理任务...",
    responding: "正在生成回复...",
    done: "回复已完成",
  };
  return phaseText[phase] || "正在处理任务...";
};

const appendAssistantProgress = (message, payload = {}) => {
  if (!message) return;
  const row = {
    phase: payload?.phase || "",
    status: payload?.status || "running",
    message: assistantProgressText(payload),
    time: nowText(),
  };
  message.progressEvents = [...(message.progressEvents || []), row].slice(-12);
  message.thinkingText = row.message;
  if (row.status === "failed") {
    message.streamState = "error";
    return;
  }
  if (!String(message.fullContent || message.content || "").trim() && message.streamState !== "streaming") {
    message.streamState = "waiting";
  }
};

const parseReplyBlocks = (blocks = []) =>
  (Array.isArray(blocks) ? blocks : [])
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const type = String(item.type || "").trim();
      if (!type) return null;
      const rawText = String(item.text ?? "");
      const isCode = type === "code";
      return {
        type,
        text: isCode ? rawText : sanitizeAssistantVisibleText(rawText.trim()),
        title: String(item.title || "").trim(),
        items: Array.isArray(item.items) ? item.items.map((entry) => String(entry || "").trim()).filter(Boolean) : [],
        language: String(item.language || item.lang || "").trim(),
        code: String(item.code ?? ""),
      };
    })
    .filter(Boolean);

const taskStepText = (taskPatch = {}) => {
  const steps = Array.isArray(taskPatch?.steps) ? taskPatch.steps : [];
  if (!steps.length) return "-";
  const currentIndex = Number.isFinite(taskPatch?.current) ? Number(taskPatch.current) : 0;
  const current = steps[Math.max(0, Math.min(currentIndex, steps.length - 1))];
  return current?.title || current?.key || "-";
};

const updateScrollFlags = () => {
  const el = chatScrollRef.value;
  if (!el) return;
  const distance = Math.max(el.scrollHeight - el.scrollTop - el.clientHeight, 0);
  const nearBottom = distance <= BOTTOM_DISTANCE_THRESHOLD;
  isNearBottom.value = nearBottom;
  userScrolledUp.value = !nearBottom;
  showScrollToBottom.value = !nearBottom;
  if (nearBottom) unreadNewMessageCount.value = 0;
};

const handleChatScroll = () => {
  updateScrollFlags();
};

const scrollToBottom = async ({ mode = "auto", force = false } = {}) => {
  await nextTick();
  const el = chatScrollRef.value;
  if (!el) return false;
  const shouldScroll =
    force ||
    mode === "force" ||
    (mode === "conditional" ? !userScrolledUp.value : isNearBottom.value || mode === "smooth");
  if (!shouldScroll) return false;
  if (mode === "smooth") {
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  } else {
    el.scrollTop = el.scrollHeight;
  }
  await nextTick();
  updateScrollFlags();
  return true;
};

const handleScrollToLatest = async () => {
  await scrollToBottom({ mode: "smooth", force: true });
  unreadNewMessageCount.value = 0;
  showScrollToBottom.value = false;
};

const handleMessageAppended = async (role = "") => {
  await nextTick();
  if (!chatScrollRef.value) return;
  if (role === "assistant" && userScrolledUp.value && !isNearBottom.value) {
    unreadNewMessageCount.value += 1;
    showScrollToBottom.value = true;
    return;
  }
  unreadNewMessageCount.value = 0;
  await scrollToBottom({ mode: role === "assistant" ? "conditional" : "force", force: role !== "assistant" });
};

const mergeSkills = (remoteItems = []) => {
  const role = auth.role || "student";
  const remote = (remoteItems || [])
    .filter((item) => item?.code)
    .map((item) => ({
      ...item,
      code: normalizeSkillCode(item.code),
      recommended_prompts: Array.isArray(item.recommended_prompts) ? item.recommended_prompts : [],
    }))
    .filter((item) => item.code && item.code !== "general-chat" && (!Array.isArray(item.roles) || item.roles.includes(role)));

  const deduped = new Map();
  for (const item of remote) deduped.set(item.code, item);
  return Array.from(deduped.values()).sort((a, b) => a.code.localeCompare(b.code, "zh-CN"));
};

const normalizeTemplateLabel = (prompt = "", index = 0) => {
  const text = String(prompt || "").trim();
  if (!text) return `快捷任务 ${index + 1}`;
  return text.length <= 12 ? text : `${text.slice(0, 12)}...`;
};

const buildSuggestedTemplates = (suggestions = []) =>
  (suggestions || [])
    .slice(0, 3)
    .map((prompt, index) => ({
      label: normalizeTemplateLabel(prompt, index),
      prompt,
    }));

const loadWelcome = async () => {
  if (!auth.isLoggedIn) {
    promptTemplates.value = getRolePromptTemplates(auth.role || "student");
    return;
  }
  const baseTemplates = getRolePromptTemplates(auth.role || "student");
  try {
    const res = await assistantApi.welcome();
    const suggested = buildSuggestedTemplates(res?.data?.suggestions || []);
    promptTemplates.value = [...baseTemplates, ...suggested];
    skillsState.items = mergeSkills(res?.data?.skills || skillsState.items);
  } catch (_) {
    promptTemplates.value = baseTemplates;
    skillsState.items = mergeSkills(skillsState.items);
  }
};

const loadSummary = async () => {
  if (!auth.isLoggedIn) {
    summaryCardsData.value = [];
    summaryError.value = "";
    return;
  }
  summaryLoading.value = true;
  summaryError.value = "";
  try {
    const res = await assistantApi.summary();
    summaryCardsData.value = res?.data?.cards || [];
  } catch (error) {
    summaryCardsData.value = [];
    summaryError.value = error?.response?.data?.message || "请稍后重试";
  } finally {
    summaryLoading.value = false;
  }
};

const loadSearch = async () => {
  const q = searchKeyword.value.trim();
  if (!q) {
    searchState.items = [];
    searchState.error = "";
    return;
  }
  searchState.loading = true;
  searchState.error = "";
  try {
    const res = await assistantApi.search(q);
    searchState.items = res?.data?.items || [];
  } catch (error) {
    searchState.items = [];
    searchState.error = error?.response?.data?.message || "搜索失败";
  } finally {
    searchState.loading = false;
  }
};

const loadAssets = async () => {
  assetsState.loading = true;
  assetsState.error = "";
  try {
    const res = await assistantApi.assets();
    assetsState.items = res?.data?.items || [];
  } catch (error) {
    assetsState.items = [];
    assetsState.error = error?.response?.data?.message || "资产加载失败";
  } finally {
    assetsState.loading = false;
  }
};

const loadGallery = async () => {
  galleryState.loading = true;
  galleryState.error = "";
  try {
    const res = await assistantApi.gallery();
    galleryState.items = res?.data?.items || [];
  } catch (error) {
    galleryState.items = [];
    galleryState.error = error?.response?.data?.message || "画廊加载失败";
  } finally {
    galleryState.loading = false;
  }
};

const loadSkills = async () => {
  skillsState.loading = true;
  skillsState.error = "";
  try {
    const res = await assistantApi.skills();
    skillsState.items = mergeSkills(res?.data?.items || []);
  } catch (error) {
    skillsState.items = mergeSkills([]);
    skillsState.error = error?.response?.data?.message || "技能加载失败";
  } finally {
    skillsState.loading = false;
  }
};

const syncPanelQuery = (panel = "") => {
  const nextQuery = { ...route.query };
  if (panel) nextQuery.panel = panel;
  else delete nextQuery.panel;
  router.replace({ path: route.path, query: nextQuery });
};

const openWorkspacePanel = async (type) => {
  if (!auth.isLoggedIn) {
    ElMessage.info("登录后可保存任务、生成报告并查看历史记录");
    openLoginModal("login");
    return;
  }
  if (type === "skills") {
    await openSkillPanel();
    syncPanelQuery("");
    return;
  }
  const panel = ["search", "assets", "gallery"].includes(type) ? type : "search";
  workspacePanel.value = panel;
  syncPanelQuery(panel);
  if (panel === "assets") await loadAssets();
  if (panel === "gallery") await loadGallery();
};

const closeWorkspacePanel = () => {
  workspacePanel.value = "";
  syncPanelQuery("");
};

const openSearchResult = (item) => {
  if (!item?.route) return;
  router.push(item.route);
  closeWorkspacePanel();
};

const openAsset = (item) => {
  if (item?.route) router.push(item.route);
  else if (item?.download_url) openDownload(item.download_url);
};

const openGallery = (item) => {
  if (!item?.preview_route) return;
  router.push(item.preview_route);
  closeWorkspacePanel();
};

const isGalleryImage = (item) => {
  if (!item) return false;
  if (item.cover_mode !== "image") return false;
  return Boolean(String(item.thumb_url || "").trim());
};

const galleryIconMeta = (item) => {
  const iconType = item?.icon_type || "";
  if (iconType === "report-composite") return { tag: "报告" };
  if (iconType === "resume") return { tag: "简历" };
  if (iconType === "delivery") return { tag: "投递" };
  if (String(item?.type || "").includes("report")) return { tag: "报告" };
  if (String(item?.type || "").includes("delivery")) return { tag: "投递" };
  return { tag: "素材" };
};

const setActiveSkill = (code = "") => {
  const normalized = normalizeSkillCode(code);
  activeSkillCode.value = normalized || "";
};

const clearActiveSkill = () => {
  activeSkillCode.value = "";
};

const pickActiveSkill = (skill) => {
  if (skill?.code) {
    setActiveSkill(skill.code);
  } else {
    clearActiveSkill();
  }
  skillPickerVisible.value = false;
};

const handleAddSkillEntry = () => {
  draft.value = draft.value.trim() || "????????????????????????????";
  skillPickerVisible.value = false;
};

const findSkill = (code) => {
  if (!code) return null;
  return skillsState.items.find((item) => item.code === code) || null;
};

const skillNameOf = (code) => findSkill(code)?.name || "";

const activeResultTab = (card) => card?.tabs?.find((item) => item.key === card.activeTab) || card?.tabs?.[0] || null;

const selectResultTab = (message, tabKey) => {
  if (!message?.resultCard) return;
  message.resultCard.activeTab = tabKey;
};

const openDetailCard = (card) => {
  detailCard.value = card || null;
  detailDrawerVisible.value = !!card;
};

const handleActionPick = async (action) => {
  const text = String(action || "").trim();
  if (!text) return;
  await sendMessage(text, { skillCode: activeSkillCode.value || "" });
};

const openDownload = (url) => {
  if (!url) return;
  const downloadUrl = url.startsWith("http://") || url.startsWith("https://")
    ? url
    : `${BACKEND_ORIGIN}${url.startsWith("/") ? "" : "/"}${url}`;
  window.open(downloadUrl, "_blank");
};

const handleCtrlEnter = (e) => {
  e.preventDefault();
  draft.value += "\n";
};

const sendMessage = async (preset = "", options = {}) => {
  const content = String(preset || draft.value).trim();
  const shouldResetDraft = !preset;
  const skillCode = normalizeSkillCode(options.skillCode || activeSkillCode.value || "");
  const skillName = skillNameOf(skillCode);
  const shouldClearSkillAfterSend = options.keepSkillSelected !== true;
  if (!content && !skillCode) return;

  if (!auth.isLoggedIn) {
    await ensureActiveSession();
    appendGuestMessage("user", content || "你好，我想随便聊聊", [], skillName);
    await scrollToBottom({ mode: "force", force: true });
    appendGuestMessage("assistant", "登录后可保存任务、生成报告并查看历史记录。", [], skillName);
    ElMessage.info("登录后可保存任务、生成报告并查看历史记录");
    openLoginModal("login");
    await scrollToBottom({ mode: "force", force: true });
    if (shouldClearSkillAfterSend) clearActiveSkill();
    return;
  }

  const session = await ensureActiveSession();
  const history = (session.messages || []).map((item) => ({ role: item.role, content: item.content }));
  const contextBinding = { ...(session.state?.context_binding || activeContextBinding.value || {}) };
  const localClientContext = getAssistantClientContext();
  const clientStatePayload = {
    role: auth.role || "student",
    ...localClientContext,
    selected_skill: skillCode || "",
    target_job: localClientContext.target_job || contextBinding.target_job || "",
    target_city: localClientContext.target_city || contextBinding.target_city || "",
    target_industry: localClientContext.target_industry || contextBinding.target_industry || "",
  };

  appendActiveMessage("user", content || "（使用技能）", [], skillName);
  if (shouldResetDraft) draft.value = "";
  await scrollToBottom({ mode: "force", force: true });

  appendActiveMessage("assistant", "", [], skillName);
  const assistantMessage = activeSession.value?.messages?.[activeSession.value.messages.length - 1] || null;
  if (assistantMessage) {
    initMessageRenderState(assistantMessage, { animate: true });
    assistantMessage.streamState = "waiting";
    assistantMessage.pendingFinalState = "";
  }

  sending.value = true;
  try {
    if (uploadFile.value && auth.role === "student") {
      const formData = new FormData();
      const currentFile = uploadFile.value?.raw || uploadFile.value;
      formData.append("file", currentFile, currentFile?.name || uploadFile.value?.name || "attachment");
      formData.append("description", "assistant upload");
      const uploadRes = await studentApi.uploadAttachment(formData);
      const uploadedAttachment = uploadRes?.data || {};
      const attachmentId = Number(uploadedAttachment.id || 0);
      if (attachmentId) {
        contextBinding.attachment_id = attachmentId;
        contextBinding.attachment = {
          id: attachmentId,
          file_name: uploadedAttachment.file_name || currentFile?.name || "",
          file_type: uploadedAttachment.file_type || "",
        };
        clientStatePayload.attachment_id = attachmentId;
      }
    }

    const payload = {
      message: content || "请开始",
      history,
      skill: skillCode || null,
      session_id: Number(session.id),
      context_binding: contextBinding,
      client_state: clientStatePayload,
    };

    const isResumeFileTask =
      skillCode === "resume-workbench" ||
      !!uploadFile.value ||
      !!clientStatePayload.attachment_id ||
      !!clientStatePayload.resume_id ||
      !!clientStatePayload.resume_version_id;
    const chatTimeoutMs = isResumeFileTask ? 180000 : undefined;

    let finalData = {};
    let streamMeta = {};
    await assistantApi.chat(payload, {
      timeoutMs: chatTimeoutMs,
      timeoutMessage: isResumeFileTask ? "简历处理耗时较长，请稍后查看或重试。" : undefined,
      onMeta: (meta) => {
        streamMeta = meta || {};
        if (assistantMessage) {
          assistantMessage.agentRoute = streamMeta?.agent_route || assistantMessage.agentRoute || "chat";
          assistantMessage.agentFlow = parseAgentFlow(streamMeta?.agent_flow || assistantMessage.agentFlow || []);
          assistantMessage.supervisorPlan = streamMeta?.supervisor_plan || assistantMessage.supervisorPlan || {};
          assistantMessage.dispatchTrace = normalizeDispatchTrace(streamMeta?.dispatch_trace || assistantMessage.dispatchTrace || {});
          assistantMessage.decisionTrace = Array.isArray(streamMeta?.decision_trace) ? streamMeta.decision_trace : assistantMessage.decisionTrace || [];
        }
      },
      onProgress: (progress) => {
        appendAssistantProgress(assistantMessage, progress || {});
      },
      onError: (errorPayload) => {
        appendAssistantProgress(assistantMessage, {
          ...(errorPayload || {}),
          status: "failed",
          message: errorPayload?.message || "深度分析未完整完成，正在切换为稳妥建议...",
        });
      },
      onDelta: (chunk) => {
        if (!assistantMessage) return;
        assistantMessage.streamState = "streaming";
        assistantMessage.thinkingText = assistantMessage.thinkingText || "正在生成回复...";
        enqueueMessageTyping(assistantMessage, String(chunk?.text || ""));
        scrollToBottom({ mode: "conditional" });
      },
      onDone: (data) => {
        finalData = data || {};
        if (!assistantMessage) return;
        const finalReply = normalizeMessageText(finalData?.reply || assistantMessage.fullContent || assistantMessage.content);
        const finalState = finalStreamStateForData(finalData);
        applyFinalMessageContent(assistantMessage, finalReply);
        if (shouldTypewriter(assistantMessage)) {
          assistantMessage.pendingFinalState = finalState;
          assistantMessage.streamState = "streaming";
        } else {
          assistantMessage.pendingFinalState = "";
          assistantMessage.streamState = finalState;
          closeThinkingProcessForFinalState(assistantMessage, finalState);
        }
      },
    });

    const usedSkillCode = finalData?.used_skill || streamMeta?.used_skill || skillCode || "";
    const usedSkillName = skillNameOf(usedSkillCode) || usedSkillCode || skillName;
    const cards = Array.isArray(finalData?.cards) ? finalData.cards : [];
    const actions = Array.isArray(finalData?.actions) ? finalData.actions : [];
    const bindingOut = finalData?.context_binding || {};
    const sessionState = finalData?.session_state || {};
    const replyMode = finalData?.reply_mode || "";
    const replyBlocks = parseReplyBlocks(finalData?.reply_blocks || []);
    const taskPatch = finalData?.task_patch || {};
    const finalReplyText = normalizeMessageText(finalData?.reply || assistantMessage?.fullContent || assistantMessage?.content || "已收到你的任务。");

    if (assistantMessage) {
      applyFinalMessageContent(assistantMessage, finalReplyText);
      const finalState = finalStreamStateForData(finalData);
      if (shouldTypewriter(assistantMessage)) {
        assistantMessage.pendingFinalState = finalState;
        assistantMessage.streamState = "streaming";
      } else {
        assistantMessage.pendingFinalState = "";
        assistantMessage.streamState = finalState;
        closeThinkingProcessForFinalState(assistantMessage, finalState);
      }
      assistantMessage.knowledgeHits = finalData?.knowledge_hits || [];
      assistantMessage.skillName = usedSkillName;
      assistantMessage.toolSteps = parseToolSteps(finalData?.tool_steps || []);
      assistantMessage.cards = cards;
      assistantMessage.actions = actions;
      assistantMessage.contextBinding = bindingOut;
      assistantMessage.sessionState = sessionState;
      assistantMessage.taskPatch = taskPatch;
      assistantMessage.replyMode = replyMode;
      assistantMessage.replyBlocks = replyBlocks;
      assistantMessage.agentRoute = finalData?.agent_route || "chat";
      assistantMessage.requiresUserInput = !!finalData?.requires_user_input;
      assistantMessage.artifacts = Array.isArray(finalData?.artifacts) ? finalData.artifacts : [];
      assistantMessage.fileTask = finalData?.file_task || {};
      assistantMessage.backgroundJob = normalizeBackgroundJob(finalData?.background_job || {});
      assistantMessage.serverId = assistantMessage.backgroundJob.message_id || assistantMessage.serverId || null;
      assistantMessage.agentFlow = parseAgentFlow(finalData?.agent_flow || []);
      assistantMessage.supervisorPlan = finalData?.supervisor_plan || {};
      assistantMessage.dispatchTrace = normalizeDispatchTrace(finalData?.dispatch_trace || {});
      assistantMessage.decisionTrace = Array.isArray(finalData?.decision_trace) ? finalData.decision_trace : [];
      assistantMessage.thinkingText = finalState === "waiting" ? backgroundThinkingText(assistantMessage.backgroundJob) : finalData?.error ? "深度分析未完整完成，已返回稳妥建议" : "";
      assistantMessage.time = nowText();
    }
    if (finalData?.error && shouldResetDraft) draft.value = content;

    session.lastMessage = normalizeMessageText(assistantMessage?.fullContent || assistantMessage?.content || "");
    session.updatedAt = new Date().toISOString();
    if (usedSkillName) session.lastSkill = usedSkillName;

    session.state = { ...(session.state || {}), ...(sessionState || {}) };
    if (Object.keys(bindingOut || {}).length) activeContextBinding.value = bindingOut;
    if (uploadFile.value) uploadFile.value = null;

    const clearAssistantResumeContext = shouldClearAssistantResumeContext(finalData);
    const attachmentBinding = bindingOut?.attachment && typeof bindingOut.attachment === "object" ? bindingOut.attachment : {};
    const nextAttachmentId = clearAssistantResumeContext
      ? null
      : hasOwnContextKey(bindingOut, "attachment_id")
        ? bindingOut.attachment_id
        : hasOwnContextKey(attachmentBinding, "id")
          ? attachmentBinding.id
          : clientStatePayload.attachment_id || null;
    patchAssistantClientContext({
      resume_id: clearAssistantResumeContext
        ? null
        : contextBindingValue(bindingOut, "resume_id", "resume_id", clientStatePayload.resume_id || null),
      resume_version_id: clearAssistantResumeContext
        ? null
        : contextBindingValue(bindingOut, "resume_version_id", "resume_version_id", clientStatePayload.resume_version_id || null),
      attachment_id: nextAttachmentId,
      attachment:
        !clearAssistantResumeContext && nextAttachmentId
          ? {
              id: nextAttachmentId,
              file_name: attachmentBinding.file_name || clientStatePayload.attachment?.file_name || "",
              file_type: attachmentBinding.file_type || clientStatePayload.attachment?.file_type || "",
            }
          : {},
      target_job: bindingOut?.target_job || clientStatePayload.target_job || "",
      target_city: bindingOut?.target_city || clientStatePayload.target_city || "",
      target_industry: bindingOut?.target_industry || clientStatePayload.target_industry || "",
      selected_skill: skillCode || "",
      current_focus: bindingOut?.current_focus || "",
    });

    await handleMessageAppended("assistant");
    await refreshServerSessions();
  } catch (error) {
    if (isResumeFileTask && error?.code === "ASSISTANT_CHAT_TIMEOUT" && assistantMessage) {
      const processingText = "简历任务仍在后台处理中，正在继续查询结果。";
      applyFinalMessageContent(assistantMessage, processingText, { replace: true });
      assistantMessage.pendingFinalState = "";
      assistantMessage.streamState = "waiting";
      assistantMessage.replyMode = "brief";
      assistantMessage.replyBlocks = [{ type: "summary", text: processingText }];
      assistantMessage.thinkingText = processingText;
      appendAssistantProgress(assistantMessage, {
        phase: "background_polling",
        status: "running",
        message: processingText,
      });
      session.lastMessage = processingText;
      session.updatedAt = new Date().toISOString();
      await loadServerMessages(session.id);
      return;
    }
    const errorText = String(
      error?.response?.data?.message ||
      error?.response?.data?.detail ||
      error?.friendlyMessage ||
      error?.backendMessage ||
      error?.message ||
      "当前服务暂不可用，请稍后重试。",
    ).trim();
    const strictErrorText = sanitizeAssistantVisibleText(errorText || "当前服务暂不可用，请稍后重试。", "当前服务暂不可用，请稍后重试。");
    if (shouldResetDraft) draft.value = content;
    if (assistantMessage) {
      applyFinalMessageContent(assistantMessage, strictErrorText, { replace: true });
      if (shouldTypewriter(assistantMessage)) {
        assistantMessage.pendingFinalState = "error";
        assistantMessage.streamState = "streaming";
      } else {
        assistantMessage.pendingFinalState = "";
        assistantMessage.streamState = "error";
        closeThinkingProcessForFinalState(assistantMessage, "error");
      }
      assistantMessage.replyMode = "brief";
      assistantMessage.replyBlocks = [{ type: "summary", text: strictErrorText }];
      assistantMessage.thinkingText = strictErrorText;
      session.lastMessage = normalizeMessageText(assistantMessage.fullContent || assistantMessage.content);
      session.updatedAt = new Date().toISOString();
    } else {
      appendActiveMessage("assistant", strictErrorText, [], skillName);
    }
  } finally {
    sending.value = false;
    if (shouldClearSkillAfterSend) clearActiveSkill();
    await scrollToBottom({ mode: "conditional" });
  }
};

const applyPromptTemplate = (item) => {
  if (!item) return;
  if (item.mode === "free-chat") {
    draft.value = "";
    clearActiveSkill();
  } else if (item.mode) {
    draft.value = item.prompt || "";
    if (item.mode !== "free-chat") {
      setActiveSkill(item.mode);
    }
  } else {
    draft.value = item.prompt || "";
    if (item.skillCode) setActiveSkill(normalizeSkillCode(item.skillCode));
  }
};

const handleNewTask = async () => {
  clearActiveSkill();
  activeContextBinding.value = {};
  stopAllBackgroundPolling();
  if (!auth.isLoggedIn) {
    const created = createGuestSession("新任务");
    syncSessionRoute(created.id);
    return;
  }
  const session = await createServerSession("新任务");
  await loadServerMessages(session.id);
  syncSessionRoute(session.id);
};

const handleWorkspaceAction = (name) => {
  const map = { 搜索: "search", 资产: "assets", 画廊: "gallery" };
  openWorkspacePanel(map[name] || "search");
};

const openSummaryRoute = (item) => {
  if (!item?.route) return;
  router.push(item.route);
};

const goFeature = (path) => router.push(path);

const goJobDetail = (job) => {
  if (!job?.id) return;
  router.push({ path: "/jobs/detail", query: { id: job.id } });
};

const handleAttachmentChange = (file) => {
  uploadFile.value = file.raw || file;
  setActiveSkill("resume-workbench");
  ElMessage.success("附件已选择，可直接发起简历相关任务");
};

const openSkillPanel = async () => {
  workspacePanel.value = "";
  await loadSkills();
  skillPickerVisible.value = true;
};

const handleSessionClick = async (sessionId) => {
  const targetId = String(sessionId);
  stopAllBackgroundPolling();
  activeSessionId.value = targetId;
  if (auth.isLoggedIn) await loadServerMessages(targetId);
  else {
    const target = sessions.value.find((item) => item.id === targetId);
    activeContextBinding.value = target?.state?.context_binding || {};
  }
  syncSessionRoute(targetId);
};

const handleRenameSession = async (sessionId, title) => {
  const targetId = String(sessionId);
  const nextTitle = normalizeSessionTitle(title);
  const session = sessions.value.find((item) => item.id === targetId);
  if (!session) return;

  if (!auth.isLoggedIn) {
    session.title = nextTitle;
    saveGuestSessions();
    return;
  }

  try {
    await assistantApi.updateSession(Number(targetId), { title: nextTitle });
    session.title = nextTitle;
  } catch (_) {
    ElMessage.error("任务重命名失败，请稍后重试");
  }
};

const handleDeleteSession = async (sessionId) => {
  const targetId = String(sessionId);
  const deletingActive = activeSessionId.value === targetId;
  stopBackgroundPollingForSession(targetId);

  if (auth.isLoggedIn) {
    try {
      await assistantApi.deleteSession(Number(targetId));
    } catch (_) {
      ElMessage.error("任务删除失败，请稍后重试");
      return;
    }
  }

  sessions.value = sessions.value.filter((item) => item.id !== targetId);

  if (!sessions.value.length) {
    if (auth.isLoggedIn) {
      const created = await createServerSession("新任务");
      syncSessionRoute(created.id);
      return;
    }
    const created = createGuestSession("新任务");
    syncSessionRoute(created.id);
    saveGuestSessions();
    return;
  }

  if (deletingActive || !sessions.value.find((item) => item.id === activeSessionId.value)) {
    const fallback = sessions.value[0];
    activeSessionId.value = fallback.id;
    if (auth.isLoggedIn) await loadServerMessages(fallback.id);
    else activeContextBinding.value = fallback.state?.context_binding || {};
  }

  if (!auth.isLoggedIn) saveGuestSessions();
  syncSessionRoute(activeSessionId.value || sessions.value[0].id);
};

const openLoginModal = (mode = "login") => {
  authMode.value = mode;
  if (mode === "register" && activePreset.value === "admin") activePreset.value = "student";
  if (mode === "login") Object.assign(loginForm, presets[activePreset.value]);
  registerForm.role_code = activePreset.value === "admin" ? "student" : activePreset.value;
  loginVisible.value = true;
  router.replace({ path: "/", query: { ...route.query, login: "1" } });
};

const closeLoginModal = () => {
  loginVisible.value = false;
  const nextQuery = { ...route.query };
  delete nextQuery.login;
  router.replace({ path: route.path, query: nextQuery });
};

const switchMode = (mode) => {
  authMode.value = mode;
  if (mode === "register" && activePreset.value === "admin") activePreset.value = "student";
  registerForm.role_code = activePreset.value === "admin" ? "student" : activePreset.value;
};

const selectRole = (type) => {
  activePreset.value = type;
  if (authMode.value === "login") Object.assign(loginForm, presets[type]);
  if (authMode.value === "register") registerForm.role_code = type;
};

const submitLogin = async () => {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.error("请输入用户名和密码");
    return;
  }
  await auth.login(loginForm);
  ElMessage.success("登录成功");
  closeLoginModal();
  if (auth.role === "admin") {
    router.push("/dashboard");
    return;
  }
  await loadServerSessions({ createIfEmpty: true });
  await loadSkills();
  await loadWelcome();
  router.push(auth.role === "admin" ? "/dashboard" : "/assistant");
};

const handleThirdPartyLogin = (type) => {
  ElMessage.info(`${type === 'qq' ? 'QQ' : '微信'}登录功能待后端对接`);
};

const submitRegister = async () => {
  if (!registerForm.username || !registerForm.real_name || !registerForm.password || !registerForm.confirm_password) {
    ElMessage.error("请完整填写注册信息");
    return;
  }
  if (registerForm.password !== registerForm.confirm_password) {
    ElMessage.error("两次输入的密码不一致");
    return;
  }
  if (registerForm.role_code === "student" && !registerForm.student_no) {
    ElMessage.error("请输入学号");
    return;
  }
  if (registerForm.role_code === "enterprise" && !registerForm.company_name) {
    ElMessage.error("请输入企业名称");
    return;
  }
  await auth.register({ ...registerForm });
  ElMessage.success("注册成功");
  closeLoginModal();
  if (auth.role === "admin") {
    router.push("/dashboard");
    return;
  }
  await loadServerSessions({ createIfEmpty: true });
  await loadSkills();
  await loadWelcome();
  router.push(auth.role === "admin" ? "/dashboard" : "/assistant");
};

const logout = () => {
  stopAllBackgroundPolling();
  clearActiveSkill();
  summaryCardsData.value = [];
  summaryError.value = "";
  workspacePanel.value = "";
  skillPickerVisible.value = false;
  sessions.value = [];
  activeSessionId.value = "";
  draft.value = "";
  uploadFile.value = null;
  localStorage.removeItem(GUEST_SESSIONS_KEY);
  auth.logout();
  router.push({ path: "/", query: { login: "1" } });
};

onMounted(async () => {
  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    reduceMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    applyReducedMotionPreference(!!reduceMotionQuery.matches);
    if (typeof reduceMotionQuery.addEventListener === "function") {
      reduceMotionQuery.addEventListener("change", handleReducedMotionChange);
    } else if (typeof reduceMotionQuery.addListener === "function") {
      reduceMotionQuery.addListener(handleReducedMotionChange);
    }
  }

  if (auth.isLoggedIn) {
    if (auth.role === "admin") {
      router.replace("/dashboard");
      return;
    }
    await loadServerSessions({ createIfEmpty: true });
    await loadSkills();
    await loadWelcome();
    if (typeof route.query.panel === "string" && route.query.panel) await openWorkspacePanel(route.query.panel);
  } else {
    loadGuestSessions();
  }
  if (route.query.login === "1") loginVisible.value = true;
  await nextTick();
  updateScrollFlags();
});

onBeforeUnmount(() => {
  stopAllBackgroundPolling();
  stopTypewriterLoop();
  if (reduceMotionQuery) {
    if (typeof reduceMotionQuery.removeEventListener === "function") {
      reduceMotionQuery.removeEventListener("change", handleReducedMotionChange);
    } else if (typeof reduceMotionQuery.removeListener === "function") {
      reduceMotionQuery.removeListener(handleReducedMotionChange);
    }
    reduceMotionQuery = null;
  }
  stopGlobalThinkingFx();
});

watch(isThinkingGlobal, (value) => {
  if (value) startGlobalThinkingFx();
  else stopGlobalThinkingFx();
});

watch(
  () => latestAssistantStreamState.value,
  (state) => {
    if (state === "error") playGlobalErrorFx();
  },
);

watch(
  () => activeMessages.value.length,
  async () => {
    if (showWelcome.value) {
      unreadNewMessageCount.value = 0;
      showScrollToBottom.value = false;
      return;
    }
    await nextTick();
    updateScrollFlags();
  },
);

watch(
  () => activeSessionId.value,
  () => {
    unreadNewMessageCount.value = 0;
    showScrollToBottom.value = false;
  },
);

watch(
  () => route.query.login,
  (value) => {
    loginVisible.value = value === "1";
  },
);

watch(
  () => route.query.session,
  async (value) => {
    if (!value) return;
    if (String(value) === activeSessionId.value) return;
    const target = sessions.value.find((item) => item.id === String(value));
    if (!target) return;
    stopAllBackgroundPolling();
    activeSessionId.value = String(value);
    if (auth.isLoggedIn) await loadServerMessages(String(value));
    else activeContextBinding.value = target.state?.context_binding || {};
  },
);

watch(
  () => route.query.panel,
  async (value) => {
    if (!auth.isLoggedIn) return;
    if (!value) {
      workspacePanel.value = "";
      return;
    }
    if (typeof value === "string" && value !== workspacePanel.value) await openWorkspacePanel(value);
  },
);
</script>

<style scoped>
.mini-page {
  display: flex;
  height: 100vh;
  max-height: 100vh;
  overflow: hidden;
  background: #f7f7f8;
  color: #111827;
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
}

.mini-main {
  --home-content-max: 1200px;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100vh;
  min-height: 0;
  padding: 12px 24px 22px;
  gap: 12px;
  overflow: hidden;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 40px;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.mini-icon-btn {
  width: 32px;
  height: 32px;
  border: 1px solid #d7e0ee;
  background: #fff;
  border-radius: 12px;
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.mini-icon-btn:hover {
  border-color: #c5d4ea;
  box-shadow: 0 8px 16px rgba(15, 23, 42, 0.08);
}

.top-tag {
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 700;
}

.top-tag.dark {
  background: #0f172a;
  color: #fff;
}

.top-tag.light {
  background: #e8efff;
  color: #1d4ed8;
}

.top-user {
  font-weight: 700;
  color: #1e293b;
}

.dialog-shell,
.composer-wrap {
  width: min(var(--home-content-max), 100%);
  margin: 0 auto;
}

.dialog-shell {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.welcome-shell {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 26px;
  padding: 50px 0 140px;
}

.welcome-title {
  margin: 0;
  color: #111827;
  font-size: clamp(40px, 4.8vw, 68px);
  line-height: 1.15;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.hero-banner {
  display: none;
}

.chat-area {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
  padding: 16px 0 8px;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.chat-area::-webkit-scrollbar {
  width: 0;
  height: 0;
  display: none;
}

.chat-inner {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chat-row {
  display: flex;
  margin: 10px 0;
  min-width: 0;
}

.chat-row.user {
  justify-content: flex-end;
}

.chat-bubble {
  max-width: min(560px, 65%);
  border-radius: 20px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #e0e6f0;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
  min-width: 0;
}

.chat-row.user .chat-bubble {
  background: #f2f6ff;
  border-color: #d5dff2;
}

.bubble-text {
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.bubble-time {
  margin-top: 8px;
  font-size: 12px;
  color: #9ca3af;
}

.thinking-process {
  margin-top: 10px;
  border: 1px solid #dbe5f2;
  border-radius: 8px;
  background: #f8fbff;
  overflow: hidden;
}

.thinking-process-head {
  width: 100%;
  min-height: 36px;
  border: 0;
  background: transparent;
  color: #334155;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0 10px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
}

.thinking-process-toggle {
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

.thinking-process-body {
  display: grid;
  gap: 10px;
  padding: 0 14px 14px;
}

.thinking-process-current {
  margin: 0;
  font-size: 13px;
  color: #1e293b;
  font-weight: 600;
  line-height: 1.7;
}

.thinking-process-lines {
  display: grid;
  gap: 6px;
}

.thinking-process-line {
  margin: 0;
  position: relative;
  padding-left: 16px;
  color: #475569;
  font-size: 12px;
  line-height: 1.75;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.thinking-process-line::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0.75em;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;
}

.thinking-process-line.is-running::before {
  background: #3b82f6;
}

.thinking-process-line.is-done::before {
  background: #16a34a;
}

.thinking-process-line.is-error::before {
  background: #dc2626;
}

.thinking-process-line.is-muted {
  color: #64748b;
}

.task-progress {
  margin-top: 8px;
  border: 1px solid #dbe5f2;
  border-radius: 12px;
  background: #f8fbff;
  padding: 8px 10px;
  display: flex;
  gap: 4px;
  flex-direction: column;
}

.task-progress-goal {
  font-size: 12px;
  color: #334155;
  font-weight: 700;
}

.task-progress-step {
  font-size: 12px;
  color: #64748b;
}

.tool-step-list {
  margin-top: 10px;
  border: 1px solid #dbe5f2;
  border-radius: 12px;
  background: #f8fbff;
  padding: 8px 10px;
  display: grid;
  gap: 6px;
}

.tool-step-item {
  font-size: 12px;
  color: #334155;
  line-height: 1.5;
}

.knowledge-list {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.knowledge-item {
  border: 1px solid #d6e0ff;
  background: #f5f8ff;
  color: #1d4ed8;
  border-radius: 999px;
  min-height: 32px;
  padding: 0 12px;
  cursor: pointer;
}

.result-card {
  margin-top: 10px;
  border: 1px solid #d8e3f2;
  border-radius: 14px;
  background: #fff;
  overflow: hidden;
}

.result-tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  padding: 8px;
  background: #f5f8ff;
  border-bottom: 1px solid #e1e8f4;
}

.result-tab {
  border: 1px solid #d3deef;
  background: #fff;
  color: #475569;
  border-radius: 10px;
  min-height: 30px;
  padding: 0 10px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}

.result-tab.active {
  background: #e8efff;
  border-color: #bcd0f5;
  color: #1d4ed8;
}

.result-body {
  padding: 10px 12px 12px;
}

.result-text {
  margin: 0;
  color: #475569;
  line-height: 1.8;
}

.result-item + .result-item {
  margin-top: 8px;
}

.result-item {
  color: #334155;
  line-height: 1.7;
}

.composer-wrap {
  flex: 0 0 auto;
  position: relative;
  z-index: 5;
}

.composer-box {
  width: min(var(--home-content-max), 100%);
  margin: 0 auto;
  border: 1px solid #dde3ed;
  background: #fff;
  border-radius: 34px;
  padding: 12px 14px 10px;
  box-shadow: 0 22px 44px rgba(15, 23, 42, 0.08);
}

.composer-box :deep(.el-textarea__inner) {
  min-height: 72px;
  border-radius: 22px;
  border-color: #e0e6f0;
  padding: 14px 15px;
  font-size: 15px;
  line-height: 1.7;
  box-shadow: none;
}

.composer-box :deep(.el-textarea__inner:focus) {
  border-color: #cdd7e6;
  box-shadow: 0 0 0 3px rgba(30, 41, 59, 0.06);
}

.composer-actions {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.left-actions,
.right-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.tool-item {
  border: none;
  background: transparent;
  border-radius: 999px;
  min-height: 30px;
  padding: 0 8px;
  cursor: pointer;
  color: #6b7280;
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.tool-item-with-icon {
  gap: 6px;
}

.tool-icon {
  width: 14px;
  height: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 14px;
}

.tool-icon svg {
  width: 14px;
  height: 14px;
  display: block;
}

.tool-item:hover {
  background: #f2f4f8;
  color: #334155;
}

.tiny-btn {
  border: 1px solid #d6e1f0;
  background: #fff;
  border-radius: 12px;
  min-height: 34px;
  padding: 0 12px;
  cursor: pointer;
  color: #334155;
  font-size: 13px;
  font-weight: 600;
}

.tiny-btn.primary {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.upload-name {
  margin-top: 8px;
  color: #94a3b8;
  font-size: 12px;
}

.send-btn {
  border: 1px solid #d5dbe6;
  background: #f7f8fb;
  color: #475569;
  cursor: pointer;
  font-weight: 700;
}

.send-btn.circle {
  width: 38px;
  height: 38px;
  min-width: 38px;
  min-height: 38px;
  border-radius: 50%;
  display: inline-grid;
  place-items: center;
}

.send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.skill-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 0 10px 0 12px;
  border-radius: 12px;
  border: 1px solid #cfe0ff;
  background: #edf4ff;
}

.skill-pill-name {
  font-size: 12px;
  font-weight: 700;
  color: #1d4ed8;
}

.skill-pill-close {
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 8px;
  background: #fff;
  color: #475569;
  cursor: pointer;
  line-height: 1;
}

.quick-actions-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  max-width: 1060px;
}

.quick-actions-list.center {
  justify-content: center;
}

.quick-chip {
  border: 1px solid #e2e7ef;
  background: #f4f6fa;
  border-radius: 16px;
  min-height: 44px;
  padding: 0 16px;
  cursor: pointer;
  color: #374151;
  font-weight: 500;
  transition: background-color 0.16s ease, box-shadow 0.16s ease;
}

.quick-chip:hover {
  background: #edf1f7;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
}

.workspace-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.28);
  z-index: 1100;
  display: flex;
  justify-content: flex-end;
}

.workspace-panel {
  width: min(760px, 100%);
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  border-left: 1px solid #d9e3f1;
  height: 100%;
  display: flex;
  flex-direction: column;
  border-top-left-radius: 24px;
  border-bottom-left-radius: 24px;
}

.workspace-head {
  height: 68px;
  border-bottom: 1px solid #dbe5f2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
}

.workspace-title {
  font-size: 18px;
  font-weight: 700;
}

.workspace-body {
  flex: 1;
  padding: 16px;
  overflow: auto;
}

.panel-search {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.panel-state {
  border: 1px dashed #ced9ea;
  border-radius: 14px;
  padding: 14px;
  color: #6b7280;
  background: #f8fbff;
}

.panel-state.panel-error {
  border-color: #fecaca;
  color: #b91c1c;
  background: #fff7f7;
}

.panel-list {
  display: grid;
  gap: 10px;
}

.panel-item {
  border: 1px solid #d9e3f1;
  border-radius: 14px;
  background: #fff;
  padding: 14px;
  text-align: left;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
}

.panel-item:hover {
  border-color: #c7d8f2;
  box-shadow: 0 14px 24px rgba(15, 23, 42, 0.08);
}

.panel-item.panel-item-static {
  cursor: default;
}

.panel-item.panel-item-static:hover {
  border-color: #d9e3f1;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
}

.panel-item-title {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
}

.panel-item-sub {
  margin-top: 6px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
}

.panel-item-actions {
  margin-top: 10px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.panel-link-btn {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
  color: #111827;
}

.gallery-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.gallery-item {
  border: 1px solid #d9e3f1;
  border-radius: 14px;
  padding: 8px;
  background: #fff;
  text-align: left;
  cursor: pointer;
}

.gallery-item:hover {
  border-color: #dbe4ff;
  box-shadow: 0 8px 20px rgba(17, 24, 39, 0.08);
}

.gallery-thumb {
  width: 100%;
  aspect-ratio: 16/9;
  border-radius: 10px;
  object-fit: cover;
  background: #f3f4f7;
}

.gallery-icon-card {
  width: 100%;
  aspect-ratio: 16/9;
  border-radius: 10px;
  border: 1px solid #d9e3f1;
  background: linear-gradient(180deg, #f8fbff, #eef3fb);
  display: grid;
  align-content: space-between;
  padding: 10px 12px;
}

.gallery-icon-tag {
  justify-self: start;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: #ffffff;
  border: 1px solid #d7e3f4;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
}

.gallery-icon-main {
  align-self: center;
  justify-self: center;
  font-size: 42px;
  line-height: 1;
}

.gallery-title {
  margin-top: 8px;
  font-size: 13px;
  font-weight: 600;
}

.gallery-time {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}

.login-btn {
  border-radius: 12px;
}

.login-mask {
  position: fixed;
  inset: 0;
  background: transparent;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.login-modal {
  position: relative;
  width: 420px;
  max-width: 100%;
  border-radius: 16px;
  background: #ffffff;
  overflow: hidden;
  box-shadow: 0 20px 50px -12px rgba(15, 23, 42, 0.15);
  border: 1px solid #e8ecf1;
}

.login-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 32px 28px 24px;
}

.login-header {
  text-align: center;
}

.login-header h2 {
  font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 6px;
  letter-spacing: -0.01em;
}

.login-header p {
  font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 14px;
  color: #64748b;
  margin: 0;
  line-height: 1.5;
}

.close-btn {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #94a3b8;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #f1f5f9;
  color: #475569;
}

.mode-tabs {
  display: flex;
  gap: 6px;
  padding: 4px;
  background: #f1f5f9;
  border-radius: 10px;
}

.mode-tabs button {
  flex: 1;
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-tabs button.active {
  background: #ffffff;
  color: #1e293b;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.role-tabs {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.role-tabs button {
  flex: 1;
  padding: 10px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.role-tabs button.active {
  border-color: #94a3b8;
  background: #f8fafc;
  color: #1e293b;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.input-field input {
  width: 100%;
  padding: 13px 15px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  color: #1e293b;
  outline: none;
  transition: all 0.2s;
  background: #ffffff;
  box-sizing: border-box;
}

.input-field input::placeholder {
  color: #94a3b8;
}

.input-field input:focus {
  border-color: #94a3b8;
  box-shadow: 0 0 0 3px rgba(148, 163, 184, 0.15);
}

.primary-btn {
  width: 100%;
  padding: 13px 24px;
  border: none;
  border-radius: 10px;
  background: #475569;
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.primary-btn:hover {
  background: #334155;
}

.divider {
  display: flex;
  align-items: center;
  gap: 12px;
}

.divider-line {
  flex: 1;
  height: 1px;
  background: #e2e8f0;
}

.divider-text {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 500;
}

.social-buttons {
  display: flex;
  gap: 10px;
}

.social-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 11px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  color: #475569;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.social-btn:hover {
  border-color: #94a3b8;
  background: #f8fafc;
}

.qq-btn:hover {
  border-color: #94a3b8;
}

.wx-btn:hover {
  border-color: #94a3b8;
}

.social-icon {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  border-radius: 4px;
  color: #64748b;
}

.qq-icon {
  background: transparent;
}

.wx-icon {
  color: #64748b;
}

.login-footer {
  font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
  margin: 0;
  line-height: 1.5;
}

@media (max-width: 1120px) {
  .gallery-grid {
    grid-template-columns: 1fr;
  }

  .composer-box {
    width: 100%;
  }
}

@media (max-width: 900px) {
  .mini-main {
    padding: 12px 12px 18px;
  }

  .dialog-shell,
  .chat-area,
  .composer-wrap {
    width: 100%;
  }

  .chat-bubble {
    max-width: 100%;
  }

  .composer-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .left-actions,
  .right-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .workspace-panel {
    border-radius: 0;
  }
}

@media (max-width: 640px) {
  .mini-page,
  .mini-main {
    height: 100dvh;
    max-height: 100dvh;
  }

  .panel-search {
    flex-direction: column;
  }

  .switch-group {
    width: 100%;
  }
}
</style>
