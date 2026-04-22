<template>
  <aside class="agent-sidebar">
    <div class="sidebar-head">
      <div class="logo-dot">CA</div>
      <div class="brand-text">
        <div class="logo-name">{{ brandTitle }}</div>
        <div class="logo-sub">{{ brandSubtitle }}</div>
      </div>
    </div>

    <button type="button" class="new-task-btn" :disabled="!canCreateTask" @click="$emit('new-task')">
      <span>+</span>
      <span>新建任务</span>
    </button>

    <div class="sidebar-scroll">
      <section v-for="group in menuGroups" :key="group.title" class="menu-group">
        <div class="menu-title">{{ group.title }}</div>
        <button
          v-for="item in group.items"
          :key="item.path"
          type="button"
          :class="['menu-item', { active: activePath === item.path }]"
          @click="$emit('select-menu', item.path)"
        >
          <span>{{ item.label }}</span>
        </button>
      </section>

      <section v-if="showWorkspace" class="menu-group">
        <div class="menu-title">工作区</div>
        <button type="button" class="menu-item" @click="$emit('workspace', '搜索')">搜索</button>
        <button type="button" class="menu-item" @click="$emit('workspace', '资产')">资产</button>
        <button type="button" class="menu-item" @click="$emit('workspace', '画廊')">画廊</button>
      </section>
    </div>

    <div v-if="showHistory" class="history-wrap">
      <div class="menu-title">历史任务</div>
      <div class="session-list">
        <div
          v-for="item in historyItems"
          :key="item.id"
          :class="['session-item', { active: String(item.id) === String(activeHistoryId) }]"
        >
          <button type="button" class="session-main" @click="$emit('select-history', item.id)">
            <div class="session-line">
              <input
                v-if="editingId === String(item.id)"
                :ref="(el) => bindInputRef(String(item.id), el)"
                v-model="editingTitle"
                class="session-input"
                maxlength="40"
                @click.stop
                @keydown.esc.prevent="cancelRename"
                @keydown.enter.prevent="confirmRename(item.id)"
                @blur="confirmRename(item.id)"
              />
              <span v-else class="session-title">{{ item.title || "新任务" }}</span>
            </div>
            <div class="session-sub">{{ sessionSubText(item) }}</div>
          </button>

          <div class="session-action" @click.stop>
            <el-dropdown trigger="click" @command="(command) => onSessionCommand(command, item)">
              <button type="button" class="more-btn" @click.stop>...</button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item :command="'rename'">重命名任务</el-dropdown-item>
                  <el-dropdown-item :command="'delete'">删除任务</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </div>
    </div>

    <div class="sidebar-user">
      <div class="avatar">AI</div>
      <div>
        <div class="user-name">{{ userName }}</div>
        <div class="user-role">{{ userRole }}</div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { nextTick, ref } from "vue";
import { ElMessageBox } from "element-plus";

defineProps({
  brandTitle: { type: String, default: "Career Agent" },
  brandSubtitle: { type: String, default: "统一职业规划智能工作台" },
  menuGroups: { type: Array, default: () => [] },
  historyItems: { type: Array, default: () => [] },
  activePath: { type: String, default: "" },
  activeHistoryId: { type: [String, Number], default: "" },
  userName: { type: String, default: "探索者" },
  userRole: { type: String, default: "未登录" },
  showWorkspace: { type: Boolean, default: true },
  showHistory: { type: Boolean, default: true },
  canCreateTask: { type: Boolean, default: true },
});

const emit = defineEmits(["new-task", "select-menu", "workspace", "select-history", "rename-history", "delete-history"]);

const editingId = ref("");
const editingTitle = ref("");
const inputRefs = ref({});

const bindInputRef = (id, el) => {
  if (!id) return;
  if (el) inputRefs.value[id] = el;
  else delete inputRefs.value[id];
};

const normalizeTitle = (value = "") => {
  const text = String(value || "").trim();
  return (text || "新任务").slice(0, 40);
};

const trimMessage = (value = "") => {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.length > 26 ? `${text.slice(0, 26)}...` : text;
};

const sessionSubText = (item) => {
  if (item?.lastSkill) return `执行技能：${item.lastSkill}`;
  if (item?.updatedAt) return `最近更新：${item.updatedAt}`;
  const message = trimMessage(item?.lastMessage || item?.last_message || "");
  return message || "最近更新：-";
};

const startRename = async (item) => {
  editingId.value = String(item?.id || "");
  editingTitle.value = normalizeTitle(item?.title || "");
  await nextTick();
  const input = inputRefs.value[editingId.value];
  if (!input) return;
  input.focus();
  input.select();
};

const cancelRename = () => {
  editingId.value = "";
  editingTitle.value = "";
};

const confirmRename = (sessionId) => {
  if (!editingId.value || String(sessionId) !== editingId.value) return;
  emit("rename-history", String(sessionId), normalizeTitle(editingTitle.value));
  cancelRename();
};

const confirmDelete = async (item) => {
  try {
    await ElMessageBox.confirm("确认删除该任务吗？删除后不可恢复。", "删除确认", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    });
    emit("delete-history", String(item.id));
  } catch (_) {
    // 用户取消删除
  }
};

const onSessionCommand = async (command, item) => {
  if (command === "rename") {
    await startRename(item);
    return;
  }
  if (command === "delete") {
    await confirmDelete(item);
  }
};
</script>

<style scoped>
.agent-sidebar {
  width: 272px;
  border-right: 1px solid #dce3ef;
  background: linear-gradient(180deg, #f9fbff 0%, #f3f7ff 100%);
  display: flex;
  flex-direction: column;
  padding: 16px 14px;
  gap: 12px;
}

.sidebar-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px;
}

.logo-dot {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  color: #fff;
  display: grid;
  place-items: center;
  font-size: 14px;
  font-weight: 700;
}

.brand-text {
  min-width: 0;
}

.logo-name {
  font-size: 18px;
  line-height: 1.15;
  font-weight: 800;
  color: #0f172a;
}

.logo-sub {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.4;
}

.new-task-btn {
  border: 1px solid #d7e0ee;
  background: #fff;
  border-radius: 14px;
  min-height: 42px;
  font-size: 14px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  color: #1e293b;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.new-task-btn:hover {
  border-color: #c1d2ec;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.new-task-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.sidebar-scroll {
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 52vh;
  padding-right: 2px;
}

.menu-group {
  border: 1px solid #d7e0ee;
  border-radius: 14px;
  background: #fff;
  padding: 8px;
}

.menu-title {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 6px;
  font-weight: 700;
}

.menu-item {
  width: 100%;
  border: none;
  border-radius: 10px;
  text-align: left;
  background: transparent;
  min-height: 36px;
  padding: 0 10px;
  cursor: pointer;
  color: #1f2937;
  transition: background-color 0.16s ease, color 0.16s ease;
}

.menu-item:hover {
  background: #f2f6ff;
}

.menu-item.active {
  background: #e8efff;
  color: #1d4ed8;
  font-weight: 700;
}

.history-wrap {
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.session-list {
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  max-height: 26vh;
}

.session-item {
  border: 1px solid #dbe4f1;
  border-radius: 12px;
  background: #fff;
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: stretch;
  min-height: 56px;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background-color 0.18s ease;
}

.session-item:hover {
  border-color: #c6d8f6;
  box-shadow: 0 8px 16px rgba(30, 64, 175, 0.08);
}

.session-item.active {
  border-color: #b7cbf4;
  background: #edf4ff;
}

.session-main {
  border: none;
  background: transparent;
  padding: 8px 10px;
  text-align: left;
  cursor: pointer;
  min-width: 0;
}

.session-line {
  min-height: 22px;
  display: flex;
  align-items: center;
}

.session-title {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-sub {
  margin-top: 4px;
  font-size: 11px;
  color: #64748b;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-input {
  width: 100%;
  border: 1px solid #bfd2f7;
  border-radius: 8px;
  min-height: 24px;
  padding: 0 8px;
  font-size: 13px;
  color: #0f172a;
  outline: none;
  background: #fff;
}

.session-action {
  display: flex;
  align-items: flex-start;
  padding: 8px 8px 0 0;
}

.more-btn {
  width: 24px;
  height: 24px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  line-height: 1;
  opacity: 0;
  transition: opacity 0.16s ease, border-color 0.16s ease, background-color 0.16s ease;
}

.session-item:hover .more-btn,
.session-item.active .more-btn,
.more-btn:focus-visible {
  opacity: 1;
}

.more-btn:hover,
.more-btn:focus-visible {
  border-color: #cedcf4;
  background: #f1f5fe;
}

.sidebar-user {
  margin-top: auto;
  border-top: 1px solid #dbe4f1;
  padding-top: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 700;
}

.user-name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.user-role {
  font-size: 12px;
  color: #6b7280;
}

@media (max-width: 900px) {
  .session-list {
    max-height: 22vh;
  }

  .more-btn {
    opacity: 1;
  }
}
</style>

