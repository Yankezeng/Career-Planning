<template>
  <div class="panel">
    <div class="section-title">差距分析</div>
    <div class="summary">{{ card.summary || "暂无差距分析" }}</div>
    <ul class="list" v-if="gaps.length">
      <li v-for="(item, index) in gaps" :key="`${index}-${item.gap_item || item}`">
        {{ item.gap_item || item.title || item.description || item }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  card: { type: Object, default: () => ({}) },
});

const gaps = computed(() => {
  const data = props.card?.data || {};
  return data.gaps || [];
});
</script>

<style scoped>
.panel { display: grid; gap: 10px; }
.section-title { font-size: 14px; font-weight: 700; color: #0f172a; }
.summary { color: #334155; line-height: 1.7; }
.list { margin: 0; padding-left: 18px; color: #334155; line-height: 1.7; }
</style>