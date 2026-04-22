<template>
  <div class="page-shell career-center">
    <DynamicBackground :particle-count="100" primary-color="#00d4ff" secondary-color="#6fffe9" :speed="0.35" />
    <PageHeader title="职业规划工作台" description="将职业目标、成长路径、学习任务和实习/证书/项目建议合并到同一页，按同一条职业主线连续推进。">
      <el-button @click="load">刷新数据</el-button>
      <el-button v-if="isStudent" type="primary" @click="generatePath">生成 / 刷新成长路径</el-button>
    </PageHeader>

    <StudentScopeSelector v-model="selectedStudentId" @change="handleStudentChange" />

    <template v-if="isStudent || selectedStudentId">
      <div class="metric-grid">
        <SectionCard v-for="item in summaryCards" :key="item.label">
          <div class="metric-label">{{ item.label }}</div>
          <div class="metric-value">{{ item.value }}</div>
          <div class="metric-tip">{{ item.tip }}</div>
        </SectionCard>
      </div>

      <el-tabs v-model="activeTab" class="workbench-tabs" @tab-change="handleTabChange">
        <el-tab-pane v-if="isStudent" label="智能推荐" name="recommendations">
          <CareerGoalRecommendations :fetch-fn="fetchRecommendations" @select="handleSelectRecommendation" />
        </el-tab-pane>

        <el-tab-pane v-if="isStudent" label="职业目标" name="goal">
          <SectionCard title="目标设定与节奏规划">
            <el-form :model="form" label-position="top">
              <el-form-item label="目标岗位">
                <el-select v-model="form.target_job_id" filterable placeholder="选择目标岗位" style="width: 320px">
                  <el-option v-for="item in jobs" :key="item.id" :label="item.name" :value="item.id" />
                </el-select>
              </el-form-item>
              <div class="two-col">
                <el-form-item label="短期目标（1-3 个月）"><el-input v-model="form.short_term_goal" type="textarea" :rows="3" /></el-form-item>
                <el-form-item label="中期目标（3-6 个月）"><el-input v-model="form.medium_term_goal" type="textarea" :rows="3" /></el-form-item>
                <el-form-item label="中长期目标（6-12 个月）"><el-input v-model="form.mid_long_term_goal" type="textarea" :rows="3" /></el-form-item>
                <el-form-item label="长期目标（12 个月以上）"><el-input v-model="form.long_term_goal" type="textarea" :rows="3" /></el-form-item>
              </div>
              <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="3" /></el-form-item>
            </el-form>
            <div class="action-row">
              <el-button type="primary" @click="saveGoal">保存职业目标</el-button>
              <el-button plain @click="switchTab('path')">查看成长路径</el-button>
            </div>
          </SectionCard>
        </el-tab-pane>

        <el-tab-pane label="成长路径" name="path">
          <SectionCard :title="targetJobName ? `目标岗位：${targetJobName}` : '当前成长路径'">
            <el-empty v-if="!path" description="当前还没有生成成长路径。" />
            <template v-else>
              <CareerPathGraph :path-data="path" :loading="pathLoading" />
              <div class="legacy-path-toggle">
                <el-button text @click="showLegacy = !showLegacy">
                  {{ showLegacy ? "隐藏传统时间线视图" : "显示传统时间线视图" }}
                </el-button>
              </div>
              <el-timeline v-if="showLegacy">
                <el-timeline-item v-for="item in pathTasks" :key="item.id || `${item.stage_label}-${item.title}`" :timestamp="item.stage_label" placement="top">
                  <div class="timeline-title">{{ item.title }}</div>
                  <div class="timeline-desc">{{ item.description }}</div>
                  <div v-if="item.weekly_tasks?.length" class="timeline-meta">每周任务：{{ item.weekly_tasks.join(' / ') }}</div>
                </el-timeline-item>
              </el-timeline>
            </template>
          </SectionCard>
        </el-tab-pane>

        <el-tab-pane label="学习任务" name="tasks">
          <SectionCard title="学习 / 项目任务清单">
            <el-empty v-if="!learningTasks.length" description="当前路径里还没有学习或项目类任务。" />
            <el-table v-else :data="learningTasks">
              <el-table-column prop="stage_label" label="阶段" width="140" />
              <el-table-column prop="category" label="类别" width="140" />
              <el-table-column prop="title" label="任务" min-width="220" />
              <el-table-column prop="difficulty_level" label="难度" width="100" />
              <el-table-column label="关联技能" min-width="180">
                <template #default="{ row }">
                  <el-tag v-for="skill in (row.related_skills || [])" :key="skill" size="small" effect="plain" class="skill-tag">{{ skill }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="每周任务" min-width="260">
                <template #default="{ row }">{{ (row.weekly_tasks || []).join(' / ') || '-' }}</template>
              </el-table-column>
            </el-table>
          </SectionCard>
        </el-tab-pane>

        <el-tab-pane label="行动建议" name="suggestions">
          <div class="three-col suggestion-grid">
            <SectionCard title="实习建议">
              <el-empty v-if="!internshipTasks.length" description="当前没有实习建议。" />
              <el-timeline v-else>
                <el-timeline-item v-for="item in internshipTasks" :key="item.id || item.title">{{ item.title }}</el-timeline-item>
              </el-timeline>
            </SectionCard>
            <SectionCard title="证书建议">
              <el-empty v-if="!certificateTasks.length" description="当前没有证书建议。" />
              <el-timeline v-else>
                <el-timeline-item v-for="item in certificateTasks" :key="item.id || item.title">{{ item.title }}</el-timeline-item>
              </el-timeline>
            </SectionCard>
            <SectionCard title="项目建议">
              <el-empty v-if="!projectTasks.length" description="当前没有项目建议。" />
              <el-timeline v-else>
                <el-timeline-item v-for="item in projectTasks" :key="item.id || item.title">{{ item.title }}</el-timeline-item>
              </el-timeline>
            </SectionCard>
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>

    <el-empty v-else description="请先选择学生后查看职业规划数据。" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { enterpriseApi, jobApi, studentApi } from "@/api";
import { useAuthStore } from "@/stores/auth";
import { useRoute, useRouter } from "vue-router";
import DynamicBackground from "@/components/common/DynamicBackground.vue";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";
import StudentScopeSelector from "@/components/StudentScopeSelector.vue";
import CareerPathGraph from "@/components/CareerPathGraph.vue";
import CareerGoalRecommendations from "@/components/CareerGoalRecommendations.vue";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const isStudent = computed(() => auth.role === "student");
const jobs = ref([]);
const path = ref(null);
const pathLoading = ref(false);
const showLegacy = ref(false);
const selectedStudentId = ref(null);
const validStudentTabs = ["recommendations", "goal", "path", "tasks", "suggestions"];
const validScopedTabs = ["path", "tasks", "suggestions"];
const form = reactive({
  target_job_id: null,
  target_company_type: "互联网成长型企业",
  short_term_goal: "",
  medium_term_goal: "",
  mid_long_term_goal: "",
  long_term_goal: "",
  notes: "",
});

const allowedTabs = computed(() => (isStudent.value ? validStudentTabs : validScopedTabs));
const activeTab = ref(allowedTabs.value.includes(route.query.tab) ? route.query.tab : allowedTabs.value[0]);
const pathTasks = computed(() => path.value?.tasks || []);
const targetJobName = computed(() => {
  const goalJob = jobs.value.find((item) => item.id === form.target_job_id)?.name;
  return path.value?.target_job_name || goalJob || "待设定";
});

const matchesCategory = (item, keywords) => {
  const value = String(item.category || "");
  return keywords.some((keyword) => value.includes(keyword));
};

const learningTasks = computed(() => pathTasks.value.filter((item) => matchesCategory(item, ["学习", "项目"])));
const internshipTasks = computed(() => pathTasks.value.filter((item) => matchesCategory(item, ["实习"])));
const certificateTasks = computed(() => pathTasks.value.filter((item) => matchesCategory(item, ["证书"])));
const projectTasks = computed(() => pathTasks.value.filter((item) => matchesCategory(item, ["项目"])));
const weeklyTaskCount = computed(() => pathTasks.value.reduce((sum, item) => sum + (item.weekly_tasks?.length || 0), 0));

const summaryCards = computed(() => [
  { label: "目标岗位", value: targetJobName.value, tip: isStudent.value ? "职业目标和成长路径会围绕同一目标岗位展开。" : "当前正在查看该学生的目标岗位方向。" },
  { label: "阶段任务", value: pathTasks.value.length, tip: "系统已拆解的阶段任务数量。" },
  { label: "每周动作", value: weeklyTaskCount.value, tip: "阶段任务继续拆分后的每周推进动作。" },
  { label: "行动建议", value: internshipTasks.value.length + certificateTasks.value.length + projectTasks.value.length, tip: "实习、证书和项目方向的补强建议总数。" },
]);

const syncRouteState = async () => {
  const nextTab = allowedTabs.value.includes(activeTab.value) ? activeTab.value : allowedTabs.value[0];
  if (route.query.tab === nextTab) return;
  await router.replace({ path: "/career/center", query: { ...route.query, tab: nextTab } });
};

const resetGoalForm = () => {
  Object.assign(form, {
    target_job_id: null,
    target_company_type: "互联网成长型企业",
    short_term_goal: "",
    medium_term_goal: "",
    mid_long_term_goal: "",
    long_term_goal: "",
    notes: "",
  });
};

const load = async () => {
  if (isStudent.value) {
    const [jobsRes, goalRes, pathRes] = await Promise.all([
      jobApi.list(),
      studentApi.getGoal().catch(() => ({ data: null })),
      studentApi.getPath().catch(() => ({ data: null })),
    ]);
    jobs.value = jobsRes.data || [];
    resetGoalForm();
    if (goalRes.data) Object.assign(form, goalRes.data);
    path.value = pathRes.data || null;
  } else {
    if (!selectedStudentId.value) {
      path.value = null;
      return;
    }
    path.value = (await enterpriseApi.studentCareerPath(selectedStudentId.value)).data || null;
  }
};

const saveGoal = async () => {
  await studentApi.saveGoal({ ...form });
  ElMessage.success("职业目标已保存");
  await load();
};

const generatePath = async () => {
  if (!isStudent.value) return;
  pathLoading.value = true;
  try {
    path.value = (await studentApi.generatePath({ target_job_id: form.target_job_id || null })).data || null;
    ElMessage.success("成长路径已生成");
  } finally {
    pathLoading.value = false;
  }
  await switchTab("path");
};

const fetchRecommendations = async () => {
  return await studentApi.getGoalRecommendations();
};

const handleSelectRecommendation = async (rec) => {
  form.target_job_id = rec.job_id;
  await saveGoal();
  ElMessage.success(`已将 ${rec.job_name} 设为目标岗位`);
  await generatePath();
};

const switchTab = async (tab) => {
  activeTab.value = allowedTabs.value.includes(tab) ? tab : allowedTabs.value[0];
  await syncRouteState();
};

const handleTabChange = async (tab) => {
  activeTab.value = tab;
  await syncRouteState();
};

const handleStudentChange = async () => {
  await load();
};

watch(
  () => route.query.tab,
  async (value) => {
    const nextTab = allowedTabs.value.includes(value) ? value : allowedTabs.value[0];
    if (nextTab !== activeTab.value) activeTab.value = nextTab;
  },
);

onMounted(async () => {
  if (isStudent.value) await load();
});
</script>

<style scoped>
.career-center {
  display: grid;
  gap: 18px;
  --metric-label-color: #6b7280;
  --metric-value-color: #1f2937;
  --content-muted-color: #64748b;
  --heading-color: #1f2937;
  --highlight-shadow: none;
}

:global(.role-student) .career-center {
  --metric-label-color: rgba(228, 248, 246, 0.88);
  --metric-value-color: #f8fdff;
  --content-muted-color: rgba(228, 248, 246, 0.88);
  --heading-color: #f8fdff;
  --highlight-shadow: 0 1px 0 rgba(2, 6, 23, 0.38);
}

:global(.role-admin) .career-center {
  --metric-label-color: rgba(203, 226, 255, 0.88);
  --metric-value-color: #f8fbff;
  --content-muted-color: rgba(203, 226, 255, 0.86);
  --heading-color: #f8fbff;
  --highlight-shadow: 0 1px 0 rgba(2, 6, 23, 0.42);
}

:global(.role-enterprise) .career-center {
  --metric-label-color: rgba(241, 252, 248, 0.96);
  --metric-value-color: #ffffff;
  --content-muted-color: rgba(232, 245, 239, 0.9);
  --heading-color: #ffffff;
  --highlight-shadow: 0 1px 0 rgba(4, 12, 24, 0.44);
}

.metric-label {
  color: var(--metric-label-color);
  font-size: 13px;
}

.metric-value {
  margin-top: 8px;
  font-size: 28px;
  font-weight: 800;
  color: var(--metric-value-color);
  text-shadow: var(--highlight-shadow);
}

.metric-tip,
.overview-text,
.timeline-desc,
.timeline-meta {
  margin-top: 8px;
  color: var(--content-muted-color);
  line-height: 1.8;
}

.timeline-title {
  font-weight: 700;
  color: var(--heading-color);
  text-shadow: var(--highlight-shadow);
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.legacy-path-toggle {
  display: flex;
  justify-content: center;
  margin-top: 16px;
  margin-bottom: 12px;
}

.skill-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.suggestion-grid {
  align-items: start;
}

.workbench-tabs :deep(.el-tabs__header) {
  margin-bottom: 18px;
}

.workbench-tabs :deep(.el-tabs__nav-wrap) {
  border-radius: 18px;
  padding: 8px;
}

.workbench-tabs :deep(.el-tabs__item) {
  min-height: 44px;
  padding: 0 18px;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.2px;
}

.workbench-tabs :deep(.el-tabs__item.is-active) {
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.08);
}

@media (max-width: 900px) {
  .workbench-tabs :deep(.el-tabs__item) {
    min-height: 40px;
    padding: 0 14px;
    font-size: 15px;
  }
}
</style>
