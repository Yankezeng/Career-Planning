<template>
  <el-dialog
    :model-value="visible"
    :show-close="false"
    :append-to-body="true"
    width="920px"
    top="8vh"
    class="skill-picker-dialog"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="skill-head">
      <div class="skill-title">我的 Skills</div>
      <div class="skill-head-actions">
        <button type="button" class="head-btn add-btn" @click="emit('add')">+ 添加更多技能</button>
        <button type="button" class="head-btn close-btn" @click="emit('update:visible', false)">✕</button>
      </div>
    </div>

    <div v-if="skills.length" class="skill-grid">
      <button
        v-for="item in skills"
        :key="item.code"
        type="button"
        :class="['skill-card', { active: currentSkillCode === item.code }]"
        @click="emit('select', item)"
      >
        <div class="skill-card-name">{{ item.name || item.code }}</div>
        <div class="skill-card-desc">{{ item.description || "点击后将作为当前技能上下文" }}</div>
      </button>
    </div>

    <div v-else class="empty-wrap">
      <div class="empty-title">这里空空的。</div>
      <button type="button" class="empty-btn" @click="emit('add')">去添加</button>
    </div>
  </el-dialog>
</template>

<script setup>
const props = defineProps({
  visible: { type: Boolean, default: false },
  skills: { type: Array, default: () => [] },
  currentSkillCode: { type: String, default: "" },
});

const emit = defineEmits(["update:visible", "select", "add"]);
</script>

<style scoped>
.skill-picker-dialog :deep(.el-dialog) {
  border-radius: 28px;
  border: 1px solid #dbe4f1;
  box-shadow: 0 22px 54px rgba(15, 23, 42, 0.2);
  overflow: hidden;
}

.skill-picker-dialog :deep(.el-dialog__body) {
  padding: 22px;
  display: grid;
  gap: 18px;
}

.skill-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.skill-title {
  font-size: 24px;
  font-weight: 800;
  color: #0f172a;
}

.skill-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.head-btn {
  border: 1px solid #d7e0ee;
  background: #fff;
  color: #334155;
  border-radius: 12px;
  min-height: 36px;
  padding: 0 12px;
  cursor: pointer;
  font-weight: 600;
}

.add-btn {
  border-radius: 999px;
  padding: 0 14px;
}

.close-btn {
  width: 36px;
  min-width: 36px;
  padding: 0;
}

.skill-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  max-height: 62vh;
  overflow: auto;
  padding-right: 4px;
}

.skill-card {
  border: 1px solid #dbe4f1;
  border-radius: 16px;
  background: linear-gradient(180deg, #fff, #f8fbff);
  text-align: left;
  padding: 14px;
  display: grid;
  gap: 8px;
  cursor: pointer;
  color: inherit;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.skill-card:hover {
  border-color: #c4d4ef;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.skill-card.active {
  border-color: #a9c4f5;
  background: linear-gradient(180deg, #f5f9ff, #eef4ff);
}

.skill-card-name {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.skill-card-desc {
  font-size: 13px;
  color: #64748b;
  line-height: 1.65;
}

.empty-wrap {
  min-height: 360px;
  display: grid;
  place-items: center;
  gap: 14px;
  text-align: center;
}

.empty-title {
  font-size: 22px;
  font-weight: 700;
  color: #475569;
}

.empty-btn {
  border: 1px solid #c6d8f6;
  background: #edf4ff;
  color: #1d4ed8;
  border-radius: 999px;
  min-height: 38px;
  padding: 0 18px;
  cursor: pointer;
  font-weight: 700;
}

@media (max-width: 1100px) {
  .skill-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .skill-grid {
    grid-template-columns: 1fr;
  }
}
</style>
