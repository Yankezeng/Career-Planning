<template>
  <div class="panel">
    <div class="section-title">匹配概览</div>
    <div class="summary">{{ card.summary || "暂无匹配结果" }}</div>
    <div class="rows" v-if="rows.length">
      <div v-for="item in rows" :key="`${item.job_name}-${item.match_score}`" class="row">
        <span>{{ item.job_name || "未命名岗位" }}</span>
        <span>{{ Number(item.match_score || item.score || 0).toFixed(1) }}</span>
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
  return data.matches || [];
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
</style>