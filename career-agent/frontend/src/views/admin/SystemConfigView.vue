<template>
  <div class="page-shell">
    <PageHeader title="系统参数配置页" description="配置模型参数、推荐数量等系统级参数。" />
    <SectionCard>
      <el-table :data="configs">
        <el-table-column prop="key" label="配置项" width="200" />
        <el-table-column label="配置值" min-width="220">
          <template #default="{ row }">
            <el-input v-model="row.valueText" />
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="220" />
      </el-table>
      <el-button type="primary" style="margin-top: 16px" @click="save">保存配置</el-button>
    </SectionCard>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { adminApi } from "@/api";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";

const configs = ref([]);

const load = async () => {
  const res = await adminApi.configs();
  configs.value = (res.data || []).map((item) => ({ ...item, valueText: Array.isArray(item.value) ? item.value.join(", ") : String(item.value ?? "") }));
};

const save = async () => {
  await adminApi.updateConfigs(
    configs.value.map((item) => ({
      key: item.key,
      value: item.key === "job_tags_catalog" ? item.valueText.split(",").map((value) => value.trim()).filter(Boolean) : item.valueText,
      description: item.description,
    }))
  );
  ElMessage.success("系统配置已更新");
};

onMounted(load);
</script>
