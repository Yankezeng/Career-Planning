<template>
  <div v-if="actions.length" class="action-bar">
    <button
      v-for="(item, index) in actions"
      :key="`${index}-${item}`"
      type="button"
      class="action-btn"
      @click="$emit('pick', item)"
    >
      {{ item }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  actions: { type: Array, default: () => [] },
});

defineEmits(["pick"]);
</script>

<style scoped>
.action-bar {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.action-btn {
  border: 1px solid #d7e1ef;
  border-radius: 999px;
  min-height: 30px;
  padding: 0 12px;
  background: #fff;
  color: #334155;
  font-size: 12px;
  cursor: pointer;
}

.action-btn:hover {
  border-color: #b8cbed;
  color: #1d4ed8;
}
</style>