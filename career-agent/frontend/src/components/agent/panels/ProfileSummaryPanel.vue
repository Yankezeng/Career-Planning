<template>
  <div class="panel">
    <div class="section-title">画像摘要</div>
    <div class="summary">{{ card.summary || "暂无画像摘要" }}</div>
    <ul class="list" v-if="strengths.length">
      <li v-for="item in strengths" :key="item">{{ item }}</li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  card: { type: Object, default: () => ({}) },
});

const strengths = computed(() => {
  const data = props.card?.data || {};
  return data.strengths || data.highlights || [];
});
</script>

<style scoped>
.panel { display: grid; gap: 10px; }
.section-title { font-size: 14px; font-weight: 700; color: #0f172a; }
.summary { color: #334155; line-height: 1.7; }
.list { margin: 0; padding-left: 18px; color: #334155; line-height: 1.7; }
</style>