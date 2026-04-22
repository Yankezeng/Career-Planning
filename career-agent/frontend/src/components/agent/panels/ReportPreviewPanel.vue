<template>
  <div class="panel">
    <div class="section-title">报告预览</div>
    <div class="summary">{{ card.summary || "暂无报告摘要" }}</div>
    <div class="meta" v-if="reportTitle">报告标题：{{ reportTitle }}</div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  card: { type: Object, default: () => ({}) },
});

const reportTitle = computed(() => props.card?.data?.title || props.card?.data?.report?.title || "");
</script>

<style scoped>
.panel { display: grid; gap: 10px; }
.section-title { font-size: 14px; font-weight: 700; color: #0f172a; }
.summary { color: #334155; line-height: 1.7; }
.meta { color: #475569; font-size: 13px; }
</style>