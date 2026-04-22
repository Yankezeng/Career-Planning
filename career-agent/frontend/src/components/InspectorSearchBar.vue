<template>
  <div class="inspector-search-bar">
    <span class="search-icon">⌕</span>
    <input
      :value="modelValue"
      :placeholder="placeholder"
      class="search-input"
      type="text"
      @input="$emit('update:modelValue', $event.target.value)"
    />
    <span v-if="hint" class="search-hint">{{ hint }}</span>
    <span v-if="count !== null && count !== undefined" class="search-count">{{ count }}</span>
    <button v-if="modelValue" type="button" class="clear-btn" @click="$emit('update:modelValue', '')">清除</button>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: String, default: "" },
  placeholder: { type: String, default: "搜索" },
  hint: { type: String, default: "" },
  count: { type: Number, default: null },
});

defineEmits(["update:modelValue"]);
</script>

<style scoped>
.inspector-search-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.search-icon {
  font-size: 14px;
  opacity: 0.78;
}

.search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: inherit;
  font: inherit;
}

.search-input::placeholder {
  color: rgba(148, 163, 184, 0.78);
}

.search-hint,
.search-count,
.clear-btn {
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1;
}

.search-hint {
  background: rgba(59, 130, 246, 0.14);
  color: #bfdbfe;
}

.search-count {
  background: rgba(16, 185, 129, 0.14);
  color: #86efac;
}

.clear-btn {
  border: none;
  cursor: pointer;
  background: rgba(239, 68, 68, 0.14);
  color: #fecaca;
}

:global(.role-enterprise) .inspector-search-bar {
  background: linear-gradient(180deg, rgba(246, 250, 247, 0.94), rgba(241, 246, 243, 0.96));
  border-color: rgba(15, 118, 110, 0.1);
  color: #173733;
}

:global(.role-enterprise) .search-hint {
  background: rgba(15, 118, 110, 0.1);
  color: #0f5d57;
}

:global(.role-enterprise) .search-count {
  background: rgba(16, 185, 129, 0.12);
  color: #0f766e;
}

:global(.role-enterprise) .clear-btn {
  background: rgba(15, 23, 42, 0.08);
  color: #45625b;
}
</style>
