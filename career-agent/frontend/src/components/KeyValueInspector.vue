<template>
  <div class="kv-panel">
    <template v-if="entries.length">
      <div v-for="entry in entries" :key="entry.key" class="kv-row">
        <div class="kv-key">{{ entry.label }}</div>
        <div class="kv-value">
          <template v-if="entry.type === 'list'">
            <div class="kv-tags">
              <el-tag v-for="item in entry.value" :key="`${entry.key}-${item}`" size="small" round>{{ item }}</el-tag>
            </div>
          </template>
          <template v-else-if="entry.type === 'object'">
            <div class="kv-nested">
              <div v-for="child in entry.children" :key="`${entry.key}-${child.key}`" class="kv-nested-row">
                <span>{{ child.label }}</span>
                <strong>{{ child.display }}</strong>
              </div>
            </div>
          </template>
          <template v-else>
            <span>{{ entry.display }}</span>
          </template>
        </div>
      </div>
    </template>
    <div v-else class="kv-empty">{{ emptyText }}</div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  data: { type: Object, default: null },
  emptyText: { type: String, default: "暂无详情数据" },
});

const formatLabel = (value) =>
  String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());

const normalizePrimitive = (value) => {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value);
};

const entries = computed(() => {
  const data = props.data;
  if (!data || typeof data !== "object") return [];
  return Object.entries(data)
    .filter(([, value]) => value !== undefined)
    .map(([key, value]) => {
      if (Array.isArray(value)) {
        const list = value.map((item) => normalizePrimitive(item)).filter((item) => item !== "-");
        return { key, label: formatLabel(key), type: "list", value: list };
      }
      if (value && typeof value === "object") {
        const children = Object.entries(value).map(([childKey, childValue]) => ({
          key: childKey,
          label: formatLabel(childKey),
          display: normalizePrimitive(childValue),
        }));
        return { key, label: formatLabel(key), type: "object", children };
      }
      return { key, label: formatLabel(key), type: "text", display: normalizePrimitive(value) };
    })
    .filter((entry) => {
      if (entry.type === "list") return entry.value.length > 0;
      if (entry.type === "object") return entry.children.length > 0;
      return true;
    });
});
</script>

<style scoped>
.kv-panel {
  display: grid;
  gap: 10px;
}

.kv-row {
  display: grid;
  grid-template-columns: 128px 1fr;
  gap: 14px;
  align-items: start;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.kv-key {
  font-size: 12px;
  font-weight: 700;
  color: rgba(191, 219, 254, 0.82);
  letter-spacing: 0.04em;
}

.kv-value {
  min-width: 0;
  color: #eff6ff;
  line-height: 1.7;
  word-break: break-word;
}

.kv-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.kv-nested {
  display: grid;
  gap: 8px;
}

.kv-nested-row {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
}

.kv-empty {
  padding: 18px;
  border-radius: 18px;
  color: rgba(191, 219, 254, 0.78);
  background: rgba(255, 255, 255, 0.04);
  border: 1px dashed rgba(148, 163, 184, 0.18);
}

:global(.role-enterprise) .kv-row {
  background: rgba(255, 255, 255, 0.56);
  border-color: rgba(15, 118, 110, 0.08);
}

:global(.role-enterprise) .kv-key {
  color: #4f6661;
}

:global(.role-enterprise) .kv-value {
  color: #173733;
}

:global(.role-enterprise) .kv-nested-row {
  background: rgba(255, 255, 255, 0.6);
}

:global(.role-enterprise) .kv-empty {
  color: #5b726d;
  background: rgba(255, 255, 255, 0.5);
  border-color: rgba(15, 118, 110, 0.1);
}

@media (max-width: 760px) {
  .kv-row {
    grid-template-columns: 1fr;
  }
}
</style>
