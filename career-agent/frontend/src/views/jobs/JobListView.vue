<template>
  <div class="page-shell">
    <PageHeader title="岗位列表页" description="支持查看岗位画像库、进入详情和编辑页面。">
      <el-button v-if="auth.role === 'admin'" type="primary" @click="router.push('/jobs/create')">新增岗位</el-button>
    </PageHeader>

    <SectionCard>
      <el-table :data="jobs" stripe class="job-table">
        <el-table-column prop="name" label="岗位名称" min-width="160" />
        <el-table-column prop="category" label="岗位类别" width="120" />
        <el-table-column prop="industry" label="所属行业" width="120" />
        <el-table-column label="核心技能" min-width="220">
          <template #default="{ row }">
            <div class="tag-list">
              <el-tag v-for="item in row.core_skill_tags" :key="item">{{ item }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="router.push(`/jobs/detail?id=${row.id}`)">详情</el-button>
            <el-button link type="primary" @click="router.push(`/jobs/profile?id=${row.id}`)">画像</el-button>
            <el-button link type="primary" @click="router.push(jobGraphPath(row))">图谱</el-button>
            <el-button v-if="auth.role === 'admin'" link @click="router.push(`/jobs/create?id=${row.id}`)">编辑</el-button>
            <el-button v-if="auth.role === 'admin'" link type="danger" @click="remove(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </SectionCard>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRouter } from "vue-router";
import { jobApi } from "@/api";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();
const jobs = ref([]);

const load = async () => {
  const res = await jobApi.list();
  jobs.value = res.data || [];
};

const jobGraphPath = (row) => (auth.role === "student" ? `/student/job-graph?id=${row.id}` : `/graph/relations?id=${row.id}`);

const remove = async (id) => {
  await ElMessageBox.confirm("确认删除该岗位吗？", "提示");
  await jobApi.remove(id);
  ElMessage.success("删除成功");
  await load();
};

onMounted(load);
</script>

<style scoped>
.job-table :deep(.el-tag) {
  border-radius: 999px;
  padding-inline: 10px;
}

:global(.role-student) .job-table {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: rgba(11, 19, 43, 0.76);
  --el-table-row-hover-bg-color: rgba(91, 192, 190, 0.12);
  --el-fill-color-lighter: rgba(28, 37, 65, 0.96);
  --el-fill-color-light: rgba(28, 37, 65, 0.92);
  --el-table-fixed-left-column: rgba(15, 25, 49, 0.98);
  --el-table-fixed-right-column: rgba(15, 25, 49, 0.98);
}

:global(.role-student) .job-table :deep(th.el-table__cell) {
  background: rgba(15, 25, 49, 0.98);
  color: #eff8ff;
}

:global(.role-student) .job-table :deep(td.el-table__cell) {
  background: rgba(11, 19, 43, 0.78);
  color: #edf9ff;
}

:global(.role-student) .job-table :deep(.el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: rgba(28, 37, 65, 0.96);
}

:global(.role-student) .job-table :deep(.el-table__body tr:hover > td.el-table__cell) {
  background: rgba(91, 192, 190, 0.12) !important;
}

:global(.role-student) .job-table :deep(.el-table-fixed-column--right),
:global(.role-student) .job-table :deep(.el-table-fixed-column--left) {
  background: rgba(15, 25, 49, 0.98);
}

:global(.role-student) .job-table :deep(.el-tag) {
  background: rgba(91, 192, 190, 0.12);
  border-color: rgba(111, 255, 233, 0.16);
  color: #dcfff8;
}

:global(.role-admin) .job-table {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: rgba(15, 23, 42, 0.76);
  --el-table-row-hover-bg-color: rgba(34, 211, 238, 0.1);
  --el-fill-color-lighter: rgba(30, 41, 59, 0.96);
  --el-fill-color-light: rgba(30, 41, 59, 0.92);
  --el-table-fixed-left-column: rgba(15, 23, 42, 0.98);
  --el-table-fixed-right-column: rgba(15, 23, 42, 0.98);
}

:global(.role-admin) .job-table :deep(th.el-table__cell) {
  background: rgba(15, 23, 42, 0.98);
  color: #eff8ff;
}

:global(.role-admin) .job-table :deep(td.el-table__cell) {
  background: rgba(15, 23, 42, 0.8);
  color: #eef9ff;
}

:global(.role-admin) .job-table :deep(.el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: rgba(30, 41, 59, 0.96);
}

:global(.role-admin) .job-table :deep(.el-table__body tr:hover > td.el-table__cell) {
  background: rgba(34, 211, 238, 0.1) !important;
}

:global(.role-admin) .job-table :deep(.el-table-fixed-column--right),
:global(.role-admin) .job-table :deep(.el-table-fixed-column--left) {
  background: rgba(15, 23, 42, 0.98);
}

:global(.role-admin) .job-table :deep(.el-tag) {
  background: rgba(34, 211, 238, 0.1);
  border-color: rgba(103, 232, 249, 0.16);
  color: #d8f6ff;
}
</style>
