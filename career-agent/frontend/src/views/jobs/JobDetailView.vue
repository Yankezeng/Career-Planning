<template>
  <div class="page-shell">
    <PageHeader title="岗位详情页" description="展示岗位基础信息、工作内容与发展方向。" />
    <SectionCard v-if="job">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="岗位名称">{{ job.name }}</el-descriptions-item>
        <el-descriptions-item label="岗位类别">{{ job.category }}</el-descriptions-item>
        <el-descriptions-item label="所属行业">{{ job.industry }}</el-descriptions-item>
        <el-descriptions-item label="薪资区间">{{ job.salary_range }}</el-descriptions-item>
        <el-descriptions-item label="学历要求">{{ job.degree_requirement }}</el-descriptions-item>
        <el-descriptions-item label="专业要求">{{ job.major_requirement }}</el-descriptions-item>
        <el-descriptions-item label="实习要求">{{ job.internship_requirement }}</el-descriptions-item>
        <el-descriptions-item label="AI生成">{{ job.generated_by_ai ? '是' : '否' }}</el-descriptions-item>
      </el-descriptions>
      <p style="margin-top: 16px"><strong>岗位描述：</strong>{{ job.description }}</p>
      <p><strong>工作内容：</strong>{{ job.work_content }}</p>
      <p><strong>发展方向：</strong>{{ job.development_direction }}</p>
    </SectionCard>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { jobApi } from "@/api";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";

const route = useRoute();
const job = ref(null);

onMounted(async () => {
  const id = route.query.id || 1;
  const res = await jobApi.detail(id);
  job.value = res.data;
});
</script>
