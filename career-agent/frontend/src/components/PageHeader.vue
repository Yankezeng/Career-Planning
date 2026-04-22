<template>
  <header class="page-header">
    <div class="copy">
      <h2>{{ title }}</h2>
      <p v-if="description">{{ description }}</p>
    </div>
    <div v-if="$slots.default" class="actions">
      <slot />
    </div>
  </header>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: "" },
});
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18px;
  padding: 18px 20px;
  border: 1px solid #dbe4f1;
  border-radius: 20px;
  background: linear-gradient(140deg, rgba(255, 255, 255, 0.98), rgba(247, 250, 255, 0.96));
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.copy {
  min-width: 0;
  flex: 1;
}

h2 {
  margin: 0;
  font-size: 30px;
  color: #0f172a;
  letter-spacing: 0;
  line-height: 1.2;
}

p {
  margin: 10px 0 0;
  color: #64748b;
  line-height: 1.8;
  font-size: 14px;
}

.actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

@media (max-width: 760px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .actions {
    justify-content: flex-start;
  }
}
</style>
