<template>
  <div class="shell">
    <AgentSidebar
      :brand-subtitle="sidebarSubtitle"
      :menu-groups="visibleMenus"
      :history-items="historyItems"
      :active-path="activePath"
      :active-history-id="activeHistoryId"
      :user-name="auth.user?.real_name || '探索者'"
      :user-role="auth.user?.role_name || '已登录'"
      :show-workspace="auth.role !== 'admin'"
      :show-history="auth.role !== 'admin'"
      @new-task="goAssistant"
      @select-menu="goPath"
      @workspace="handleUtility"
      @select-history="goHistory"
      @rename-history="handleRenameHistory"
      @delete-history="handleDeleteHistory"
    />

    <section class="main">
      <header class="topbar">
        <div class="top-placeholder"></div>
        <div class="top-actions">
          <template v-if="auth.role !== 'admin'">
            <button type="button" class="mini-icon-btn" @click="handleUtility('搜索')">搜</button>
            <button type="button" class="mini-icon-btn" @click="handleUtility('资产')">资</button>
            <button type="button" class="mini-icon-btn" @click="handleUtility('画廊')">廊</button>
          </template>
          <span class="top-tag dark">{{ auth.user?.role_name || '用户' }}</span>
          <span class="top-tag light">{{ modeLabel }}</span>
          <span class="top-user">{{ auth.user?.real_name || '-' }}</span>
          <el-button class="login-btn" type="danger" plain @click="logout">退出登录</el-button>
        </div>
      </header>

      <main class="content">
        <router-view />
      </main>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AgentSidebar from "@/components/AgentSidebar.vue";
import { useAuthStore } from "@/stores/auth";
import { assistantApi } from "@/api";
import { ElMessage } from "element-plus";
import { menuGroups } from "@/utils/menusAgent";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const historyItems = ref([]);

const visibleMenus = computed(() =>
  menuGroups
    .map((group) => ({ ...group, items: group.items.filter((item) => item.roles.includes(auth.role)) }))
    .filter((group) => group.items.length),
);

const activePath = computed(() => (route.path === "/" ? "/assistant" : route.path));
const activeHistoryId = computed(() => (route.path === "/assistant" ? String(route.query.session || "") : ""));

const modeLabel = computed(() => {
  if (auth.role === "student") return "平台模式";
  if (auth.role === "enterprise") return "企业模式";
  if (auth.role === "admin") return "管理模式";
  return "访客模式";
});

const sidebarSubtitle = computed(() => (auth.role === "admin" ? "统一职业规划后台管理台" : "统一职业规划智能工作台"));

const normalizeSessionTitle = (value = "") => {
  const text = String(value || "").trim();
  return (text || "新任务").slice(0, 40);
};

const loadHistory = async () => {
  if (auth.role === "admin") {
    historyItems.value = [];
    return;
  }
  const res = await assistantApi.sessions();
  historyItems.value = (res?.data?.items || []).map((item) => ({
    id: String(item.id),
    title: normalizeSessionTitle(item.title),
    lastSkill: item.last_skill || "",
    updatedAt: item.updated_at || "",
    lastMessage: item.last_message || "",
    pinned: !!item.pinned,
  }));
};

const goPath = (path) => router.push(path);

const goAssistant = async () => {
  if (auth.role === "admin") {
    router.push("/dashboard");
    return;
  }
  const res = await assistantApi.createSession({ title: "新任务" });
  const sessionId = String(res?.data?.id || "");
  await loadHistory();
  router.push({ path: "/assistant", query: { ...route.query, session: sessionId } });
};

const goHistory = (sessionId) => {
  if (auth.role === "admin") {
    router.push("/dashboard");
    return;
  }
  router.push({ path: "/assistant", query: { ...route.query, session: String(sessionId) } });
};

const handleRenameHistory = async (sessionId, title) => {
  const targetId = String(sessionId);
  const nextTitle = normalizeSessionTitle(title);
  try {
    await assistantApi.updateSession(Number(targetId), { title: nextTitle });
    const target = historyItems.value.find((item) => item.id === targetId);
    if (target) target.title = nextTitle;
  } catch (_) {
    ElMessage.error("任务重命名失败，请稍后重试");
  }
};

const handleDeleteHistory = async (sessionId) => {
  const targetId = String(sessionId);
  const deletingCurrent = String(route.query.session || "") === targetId;
  const inAssistant = route.path === "/assistant";
  try {
    await assistantApi.deleteSession(Number(targetId));
  } catch (_) {
    ElMessage.error("任务删除失败，请稍后重试");
    return;
  }
  await loadHistory();
  if (!historyItems.value.length) {
    const created = await assistantApi.createSession({ title: "新任务" });
    const createdId = String(created?.data?.id || "");
    await loadHistory();
    if (inAssistant || deletingCurrent) {
      router.push({ path: "/assistant", query: { ...route.query, session: createdId } });
    }
    return;
  }
  const currentStillExists = historyItems.value.some((item) => item.id === String(route.query.session || ""));
  if ((inAssistant && !currentStillExists) || deletingCurrent) {
    router.push({ path: "/assistant", query: { ...route.query, session: historyItems.value[0].id } });
  }
};

const handleUtility = (name) => {
  const map = { 搜索: "search", 资产: "assets", 画廊: "gallery" };
  router.push({ path: "/assistant", query: { panel: map[name] || "search" } });
};

const logout = () => {
  auth.logout();
  router.push({ path: "/", query: { login: "1" } });
};

onMounted(async () => {
  await loadHistory();
});

watch(
  () => route.path,
  async () => {
    if (route.path !== "/assistant") await loadHistory();
  },
);
</script>

<style scoped>
.shell {
  display: flex;
  min-height: 100vh;
  background: transparent;
  color: #111827;
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 14px 20px 24px;
  gap: 14px;
}

.topbar {
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
  border-color: #c4d3ea;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
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

.login-btn {
  border-radius: 12px;
}

.content {
  min-height: 0;
  flex: 1;
}

@media (max-width: 900px) {
  .main {
    padding: 12px 12px 18px;
  }
}
</style>
