<template>
  <div class="panel">
    <div class="section-title">候选人排序</div>
    <div class="summary">{{ card.summary || "暂无候选人排序" }}</div>
    <div class="rows" v-if="rows.length">
      <div v-for="(item, index) in rows" :key="`${index}-${item.student_name || ''}`" class="row">
        <div class="name">{{ item.student_name || item.name || "未命名" }}</div>
        <div class="score">{{ Number(item.match_score || item.score || 0).toFixed(1) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  card: { type: Object, default: () => ({}) },
});

const rows = computed(() => {
  const data = props.card?.data || {};
  return data.ranking || data.portraits || [];
});
</script>

<style scoped>
.panel { display: grid; gap: 10px; }
.section-title { font-size: 14px; font-weight: 700; color: #0f172a; }
.summary { color: #334155; line-height: 1.7; }
.rows { display: grid; gap: 8px; }
.row {
  border: 1px solid #dbe4f1;
  border-radius: 10px;
  padding: 8px 10px;
  display: flex;
  justify-content: space-between;
  color: #334155;
}
.name { font-weight: 600; }
.score { color: #1d4ed8; font-weight: 700; }
</style>