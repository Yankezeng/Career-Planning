<template>
  <div class="page-shell">
    <PageHeader title="岗位关系图谱中心" description="基于图数据库展示岗位之间的技能关联与依赖关系，支持缩放、拖拽和分类筛选。" />
    <SectionCard>
      <JobRelationGraph />
    </SectionCard>
  </div>
</template>

<script setup>
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";
import JobRelationGraph from "@/components/JobRelationGraph.vue";
</script>
