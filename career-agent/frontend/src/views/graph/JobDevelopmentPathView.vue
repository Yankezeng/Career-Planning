<template>
  <div class="page-shell">
    <PageHeader title="岗位发展路径页" description="查看从岗位 A 到岗位 B 的迁移建议。" />
    <SectionCard>
      <div class="three-col">
        <el-select v-model="sourceId" placeholder="起点岗位">
          <el-option v-for="item in jobs" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-select v-model="targetId" placeholder="目标岗位">
          <el-option v-for="item in jobs" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-button type="primary" @click="load">生成迁移建议</el-button>
      </div>
    </SectionCard>
    <SectionCard v-if="result" title="迁移建议">
      <el-steps :active="result.path_names?.length" finish-status="success">
        <el-step v-for="item in result.path_names" :key="item" :title="item" />
      </el-steps>
      <p style="margin-top: 16px">{{ result.advice }}</p>
    </SectionCard>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { jobApi } from "@/api";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";

const jobs = ref([]);
const sourceId = ref();
const targetId = ref();
const result = ref(null);

const load = async () => {
  if (!sourceId.value || !targetId.value) return;
  const res = await jobApi.transfer(sourceId.value, targetId.value);
  result.value = res.data;
};

onMounted(async () => {
  const res = await jobApi.list();
  jobs.value = res.data;
  sourceId.value = jobs.value[0]?.id;
  targetId.value = jobs.value[3]?.id;
  load();
});
</script>
