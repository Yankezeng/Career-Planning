<template>
  <div class="page-shell">
    <PageHeader title="岗位画像页" description="查看岗位技能、能力、证书、经验要求与 AI 画像摘要。" />
    <SectionCard v-if="job" title="岗位画像摘要">
      <p>{{ job.job_profile.summary || job.description }}</p>
      <div class="tag-list" style="margin-bottom: 10px">
        <el-tag v-for="item in job.core_skill_tags" :key="item" type="primary">{{ item }}</el-tag>
      </div>
      <div class="tag-list">
        <el-tag v-for="item in job.common_skill_tags" :key="item" type="success">{{ item }}</el-tag>
      </div>
    </SectionCard>
    <div class="two-col" v-if="job">
      <SectionCard title="技能与证书要求">
        <el-timeline>
          <el-timeline-item v-for="item in job.skills" :key="item.id" :timestamp="`重要度 ${item.importance}`">
            {{ item.name }}
          </el-timeline-item>
        </el-timeline>
      </SectionCard>
      <SectionCard title="推荐证书与课程">
        <div class="tag-list" style="margin-bottom: 16px">
          <el-tag v-for="item in job.certificate_tags" :key="item">{{ item }}</el-tag>
        </div>
        <el-alert type="success" :closable="false">
          <template #title>{{ job.job_profile.recommended_courses?.join(" / ") || "已通过 Mock AI 生成推荐课程" }}</template>
        </el-alert>
      </SectionCard>
    </div>
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
  const res = await jobApi.detail(route.query.id || 1);
  job.value = res.data;
});
</script>
