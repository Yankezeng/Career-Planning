<template>
  <div v-if="rows.length" class="timeline">
    <div v-for="(item, index) in rows" :key="`${index}-${item.text}`" class="timeline-row">
      <span :class="['dot', item.status || 'done']"></span>
      <span class="text">{{ item.text }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  steps: { type: Array, default: () => [] },
});

const rows = computed(() =>
  (props.steps || [])
    .map((item) => {
      if (typeof item === "string") return { text: item, status: "done" };
      return {
        text: item?.text || item?.title || "已执行",
        status: item?.status || "done",
      };
    })
    .filter((item) => item.text),
);
</script>

<style scoped>
.timeline {
  margin-top: 10px;
  display: grid;
  gap: 6px;
}

.timeline-row {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #475569;
  font-size: 12px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #60a5fa;
}

.dot.failed {
  background: #ef4444;
}

.text {
  line-height: 1.5;
}
</style>