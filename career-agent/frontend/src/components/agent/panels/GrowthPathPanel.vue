<template>
  <div class="panel">
    <div class="section-title">成长路径</div>
    <div class="summary">{{ card.summary || "暂无成长路径" }}</div>
    <ul class="list" v-if="tasks.length">
      <li v-for="(item, index) in tasks" :key="`${index}-${item.title || item}`">
        {{ item.title || item.description || item }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  card: { type: Object, default: () => ({}) },
});

const tasks = computed(() => {
  const data = props.card?.data || {};
  return data.tasks || data.path?.tasks || [];
});
</script>

<style scoped>
.panel { display: grid; gap: 10px; }
.section-title { font-size: 14px; font-weight: 700; color: #0f172a; }
.summary { color: #334155; line-height: 1.7; }
.list { margin: 0; padding-left: 18px; color: #334155; line-height: 1.7; }
</style>