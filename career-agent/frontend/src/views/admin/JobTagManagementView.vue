<template>
  <div class="page-shell">
    <PageHeader title="岗位标签管理页" description="通过系统配置维护岗位标签字典，供岗位画像与匹配模块复用。" />
    <SectionCard>
      <el-input v-model="tagText" type="textarea" :rows="5" placeholder="使用逗号分隔岗位标签" />
      <el-button type="primary" style="margin-top: 12px" @click="save">保存标签配置</el-button>
    </SectionCard>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { adminApi } from "@/api";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";

const tagText = ref("");

onMounted(async () => {
  const configs = (await adminApi.configs()).data || [];
  const tags = configs.find((item) => item.key === "job_tags_catalog");
  tagText.value = Array.isArray(tags?.value) ? tags.value.join(", ") : "";
});

const save = async () => {
  const list = tagText.value.split(",").map((item) => item.trim()).filter(Boolean);
  await adminApi.updateConfigs([{ key: "job_tags_catalog", value: list, description: "岗位标签库" }]);
  ElMessage.success("标签配置已保存");
};
</script>
