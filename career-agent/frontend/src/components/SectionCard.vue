<template>
  <el-card shadow="never" class="section-card card-3d">
    <template #header v-if="title || $slots.header">
      <div class="card-header">
        <span class="title">{{ title }}</span>
        <slot name="header" />
      </div>
    </template>
    <slot />
  </el-card>
</template>

<script setup>
defineProps({
  title: { type: String, default: "" },
});
</script>

<style scoped>
.section-card {
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.95) 0%, rgba(249, 251, 255, 0.9) 100%);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
  transition: box-shadow 0.3s ease;
}

.section-card.card-3d:hover {
  box-shadow:
    0 20px 40px rgba(15, 23, 42, 0.12),
    0 8px 16px rgba(15, 23, 42, 0.08);
}

.section-card :deep(.el-card__header) {
  border-bottom-color: rgba(231, 237, 248, 0.5);
  padding: 16px 18px;
}

.section-card :deep(.el-card__body) {
  color: #111827;
  padding: 18px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.title {
  min-width: 0;
  color: #0f172a;
  font-size: 16px;
  font-weight: 700;
}
</style>
