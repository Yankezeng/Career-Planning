<template>
  <div class="score-bars">
    <div v-for="item in items" :key="item.label" class="row">
      <div class="label">{{ item.label }}</div>
      <el-progress :percentage="Math.round(item.value || 0)" :stroke-width="14" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  items: { type: Array, default: () => [] },
});
</script>

<style scoped>
.score-bars {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.label {
  margin-bottom: 6px;
  font-weight: 600;
}
</style>
