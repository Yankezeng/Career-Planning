<template>
  <div class="page-shell student-job-graph-page">
    <PageHeader title="岗位图谱中心" description="独立查看岗位之间的技能关联、依赖关系和发展路径，支持缩放、拖拽、筛选与聚焦查看。" />
    <section class="graph-panel">
      <JobRelationGraph />
    </section>
  </div>
</template>

<script setup>
import PageHeader from "@/components/PageHeader.vue";
import JobRelationGraph from "@/components/JobRelationGraph.vue";
</script>

<style scoped>
.student-job-graph-page {
  width: min(1680px, 100%);
}

.graph-panel {
  min-height: 680px;
  padding: 18px;
  border: 1px solid rgba(111, 255, 233, 0.18);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 16px 42px rgba(15, 23, 42, 0.08);
}

:global(.role-student) .graph-panel {
  background: rgba(248, 252, 255, 0.96);
  box-shadow: 0 18px 46px rgba(0, 20, 48, 0.22);
}

@media (max-width: 768px) {
  .graph-panel {
    min-height: 560px;
    padding: 12px;
    border-radius: 12px;
  }
}
</style>
