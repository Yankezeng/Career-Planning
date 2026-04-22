<template>
  <div class="page-shell growth-center">
    <DynamicBackground :particle-count="100" primary-color="#00d4ff" secondary-color="#6fffe9" :speed="0.35" />
    <PageHeader title="成长跟踪工作台" description="将成长计划执行、阶段成果提交、企业复评、优化方案和趋势分析合并到同一页，围绕同一条成长闭环连续推进。">
      <el-button @click="load">刷新数据</el-button>
      <el-button v-if="isStudent && activeTab === 'optimization'" type="primary" :loading="optimizing" @click="runOptimization">重新生成优化方案</el-button>
      <el-button v-if="isStudent && activeTab === 'submission'" type="primary" @click="submitGrowth">提交阶段成果</el-button>
      <el-button v-if="!isStudent && activeTab === 'review'" type="primary" :disabled="!selectedStudentId" @click="submitReview">提交企业复评</el-button>
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
        <el-tab-pane v-if="isStudent" label="计划执行" name="execution">
          <div class="two-col">
            <SectionCard title="当前任务清单">
              <el-empty v-if="!pathTasks.length" description="当前还没有成长路径任务。" />
              <el-table v-else :data="pathTasks">
                <el-table-column prop="stage_label" label="阶段" width="140" />
                <el-table-column prop="title" label="任务" min-width="180" />
                <el-table-column prop="category" label="类别" width="140" />
              </el-table>
            </SectionCard>

            <SectionCard title="最近一次成长记录">
              <el-empty v-if="!latestRecord" description="还没有阶段成长记录。" />
              <el-descriptions v-else :column="1" border>
                <el-descriptions-item label="阶段">{{ latestRecord.stage_label }}</el-descriptions-item>
                <el-descriptions-item label="完成率">{{ latestRecord.completion_rate }}%</el-descriptions-item>
                <el-descriptions-item label="周总结">{{ latestRecord.weekly_summary || '-' }}</el-descriptions-item>
              </el-descriptions>
            </SectionCard>
          </div>
        </el-tab-pane>

        <el-tab-pane v-if="isStudent" label="成果提交" name="submission">
          <SectionCard title="提交阶段成果">
            <el-form :model="submissionForm" label-position="top">
              <div class="three-col compact-grid">
                <el-form-item label="阶段名称"><el-input v-model="submissionForm.stage_label" /></el-form-item>
                <el-form-item label="已完成课程（逗号分隔）"><el-input v-model="coursesText" /></el-form-item>
                <el-form-item label="新增技能（逗号分隔）"><el-input v-model="skillsText" /></el-form-item>
                <el-form-item label="新增证书（逗号分隔）"><el-input v-model="certText" /></el-form-item>
                <el-form-item label="新增项目（逗号分隔）"><el-input v-model="projectText" /></el-form-item>
                <el-form-item label="新增实习（逗号分隔）"><el-input v-model="internText" /></el-form-item>
              </div>
              <el-form-item label="每周总结"><el-input v-model="submissionForm.weekly_summary" type="textarea" :rows="4" /></el-form-item>
              <el-form-item label="完成率"><el-slider v-model="submissionForm.completion_rate" :max="100" show-input /></el-form-item>
            </el-form>
          </SectionCard>
        </el-tab-pane>

        <el-tab-pane label="阶段复评" name="review">
          <template v-if="isStudent">
            <div class="two-col">
              <SectionCard title="我的复评记录">
                <el-empty v-if="!reviews.length" description="还没有企业复评记录。" />
                <div v-else class="card-list">
                  <div v-for="item in reviews" :key="item.id" class="review-card">
                    <div class="review-head">
                      <div class="review-score">{{ item.score || 0 }} 分</div>
                      <div class="review-time">{{ formatTime(item.created_at) }}</div>
                    </div>
                    <div class="review-text">{{ item.comment || '暂无文字评语' }}</div>
                    <div class="tag-wrap">
                      <el-tag v-for="suggestion in item.suggestions || []" :key="suggestion" effect="plain" round>
                        {{ suggestion }}
                      </el-tag>
                    </div>
                  </div>
                </div>
              </SectionCard>

              <SectionCard title="复评后的下一步">
                <el-empty v-if="!optimization" description="生成优化方案后，这里会联动显示新的执行重点。" />
                <div v-else class="summary-card">
                  <div class="summary-title">{{ optimization.top_matches?.[0]?.job_name || '新的推荐方向' }}</div>
                  <div class="summary-text">{{ optimization.summary }}</div>
                  <div class="bullet-list">
                    <div v-for="item in optimization.focus_actions || []" :key="item" class="bullet-item">{{ item }}</div>
                  </div>
                </div>
              </SectionCard>
            </div>
          </template>

          <SectionCard v-else title="选择阶段并提交复评">
            <el-empty v-if="!records.length" description="当前学生还没有可复评的成长记录。" />
            <template v-else>
              <div class="record-picker">
                <div
                  v-for="item in sortedRecords"
                  :key="item.id"
                  :class="['record-option', { active: reviewForm.growth_record_id === item.id }]"
                  @click="reviewForm.growth_record_id = item.id"
                >
                  <div class="review-head">
                    <div class="review-score">{{ item.stage_label }}</div>
                    <el-tag effect="plain">{{ item.completion_rate }}%</el-tag>
                  </div>
                  <div class="review-text">{{ item.weekly_summary || '暂无阶段总结' }}</div>
                </div>
              </div>

              <el-form :model="reviewForm" label-position="top" class="review-form">
                <el-form-item label="复评意见">
                  <el-input v-model="reviewForm.comment" type="textarea" :rows="4" placeholder="建议从完成情况、岗位适配变化和下一步建议三个角度填写。" />
                </el-form-item>
                <div class="two-col compact-grid">
                  <el-form-item label="复评分数"><el-slider v-model="reviewForm.score" :max="100" show-input /></el-form-item>
                  <el-form-item label="建议（逗号分隔）"><el-input v-model="reviewSuggestText" placeholder="例如：补齐 SQL 项目, 强化简历量化成果" /></el-form-item>
                </div>
              </el-form>
            </template>
          </SectionCard>
        </el-tab-pane>

        <el-tab-pane label="优化方案" name="optimization">
          <SectionCard title="最新优化方案">
            <el-empty v-if="!optimization" description="当前还没有生成优化方案。" />
            <template v-else>
              <div class="summary-card">
                <div class="summary-title">{{ optimization.top_matches?.[0]?.job_name || '当前主攻岗位' }}</div>
                <div class="summary-text">{{ optimization.summary }}</div>
                <div class="tag-wrap">
                  <el-tag v-for="item in optimization.top_matches || []" :key="item.job_id || item.job_name" round effect="plain">
                    {{ item.job_name }} · {{ Number(item.total_score || 0).toFixed(1) }} 分
                  </el-tag>
                </div>
              </div>

              <div class="two-col optimization-grid">
                <SectionCard title="优先动作">
                  <div class="bullet-list">
                    <div v-for="item in optimization.focus_actions || []" :key="item" class="bullet-item">{{ item }}</div>
                  </div>
                </SectionCard>

                <SectionCard title="联动任务">
                  <el-empty v-if="!(optimization.career_tasks || []).length" description="当前没有联动出的成长任务。" />
                  <el-timeline v-else>
                    <el-timeline-item v-for="item in optimization.career_tasks || []" :key="item.id || item.title" :timestamp="item.stage_label">
                      {{ item.title }}
                    </el-timeline-item>
                  </el-timeline>
                </SectionCard>
              </div>
            </template>
          </SectionCard>
        </el-tab-pane>

        <el-tab-pane label="成长趋势" name="trend">
          <div class="two-col">
            <SectionCard title="完成率与投入强度">
              <AnalysisChart :option="progressTrendOption" height="340px" />
            </SectionCard>
            <SectionCard title="成果增量变化">
              <AnalysisChart :option="achievementTrendOption" height="340px" />
            </SectionCard>
          </div>

          <SectionCard title="阶段成长记录">
            <el-empty v-if="!sortedRecords.length" description="还没有阶段成长记录。" />
            <el-table v-else :data="sortedRecords">
              <el-table-column prop="stage_label" label="阶段" min-width="140" />
              <el-table-column label="完成率" width="120">
                <template #default="{ row }">{{ Number(row.completion_rate || 0).toFixed(0) }}%</template>
              </el-table-column>
              <el-table-column label="新增成果" min-width="240">
                <template #default="{ row }">
                  技能 {{ (row.new_skills || []).length }} / 证书 {{ (row.new_certificates || []).length }} / 项目 {{ (row.new_projects || []).length }} / 实习 {{ (row.new_internships || []).length }}
                </template>
              </el-table-column>
              <el-table-column prop="weekly_summary" label="阶段总结" min-width="280" />
            </el-table>
          </SectionCard>
        </el-tab-pane>
      </el-tabs>
    </template>

    <el-empty v-else description="请先选择学生后查看成长跟踪数据。" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { enterpriseApi, studentApi } from "@/api";
import { useAuthStore } from "@/stores/auth";
import { useRoute, useRouter } from "vue-router";
import AnalysisChart from "@/components/AnalysisChart.vue";
import DynamicBackground from "@/components/common/DynamicBackground.vue";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";
import StudentScopeSelector from "@/components/StudentScopeSelector.vue";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const isStudent = computed(() => auth.role === "student");
const selectedStudentId = ref(null);
const path = ref(null);
const records = ref([]);
const reviews = ref([]);
const optimization = ref(null);
const optimizing = ref(false);
const trend = ref(createEmptyTrend());
const studentTabs = ["execution", "submission", "review", "optimization", "trend"];
const scopedTabs = ["review", "optimization", "trend"];
const allowedTabs = computed(() => (isStudent.value ? studentTabs : scopedTabs));
const activeTab = ref(allowedTabs.value.includes(route.query.tab) ? route.query.tab : allowedTabs.value[0]);

const submissionForm = reactive({
  stage_label: "第二阶段",
  completed_courses: [],
  new_skills: [],
  new_certificates: [],
  new_projects: [],
  new_internships: [],
  weekly_summary: "",
  completion_rate: 80,
});

const reviewForm = reactive({
  growth_record_id: null,
  comment: "",
  score: 85,
  suggestions: [],
});

function createEmptyTrend() {
  return {
    labels: [],
    completion_rates: [],
    skill_counts: [],
    certificate_counts: [],
    project_counts: [],
    internship_counts: [],
    effort_index: [],
  };
}

const bindList = (key) =>
  computed({
    get: () => submissionForm[key].join(", "),
    set: (value) => {
      submissionForm[key] = value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
    },
  });

const coursesText = bindList("completed_courses");
const skillsText = bindList("new_skills");
const certText = bindList("new_certificates");
const projectText = bindList("new_projects");
const internText = bindList("new_internships");
const reviewSuggestText = computed({
  get: () => reviewForm.suggestions.join(", "),
  set: (value) => {
    reviewForm.suggestions = value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  },
});

const sortedRecords = computed(() => [...records.value].sort((left, right) => Number(right.id || 0) - Number(left.id || 0)));
const latestRecord = computed(() => sortedRecords.value[0] || null);
const pathTasks = computed(() => path.value?.tasks || []);
const currentTarget = computed(() => optimization.value?.top_matches?.[0]?.job_name || path.value?.target_job_name || "待确定");

const summaryCards = computed(() => [
  { label: "当前主攻岗位", value: currentTarget.value, tip: "成长执行、复评和优化会围绕同一岗位方向收敛。" },
  { label: "已记录阶段", value: sortedRecords.value.length, tip: "当前已经提交并记录的阶段成长次数。" },
  { label: "最近完成率", value: `${Number(latestRecord.value?.completion_rate || 0).toFixed(0)}%`, tip: latestRecord.value?.stage_label || "暂无阶段记录" },
  { label: isStudent.value ? "复评记录" : "可复评阶段", value: isStudent.value ? reviews.value.length : sortedRecords.value.length, tip: isStudent.value ? "企业端返回的阶段复评数量。" : "企业端当前可选择复评的阶段数量。" },
]);

const progressTrendOption = computed(() => ({
  tooltip: { trigger: "axis" },
  legend: { data: ["完成率", "投入指数"], bottom: 0 },
  grid: { left: 42, right: 18, top: 24, bottom: 42 },
  xAxis: { type: "category", boundaryGap: false, data: trend.value.labels || [] },
  yAxis: { type: "value", min: 0, max: 100 },
  series: [
    {
      name: "完成率",
      type: "line",
      smooth: true,
      symbolSize: 8,
      lineStyle: { width: 3, color: "#0f62fe" },
      areaStyle: { color: "rgba(15, 98, 254, 0.14)" },
      data: trend.value.completion_rates || [],
    },
    {
      name: "投入指数",
      type: "line",
      smooth: true,
      symbolSize: 8,
      lineStyle: { width: 3, color: "#00a6a6" },
      areaStyle: { color: "rgba(0, 166, 166, 0.12)" },
      data: trend.value.effort_index || [],
    },
  ],
}));

const achievementTrendOption = computed(() => ({
  tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
  legend: { bottom: 0, data: ["技能", "证书", "项目", "实习"] },
  grid: { left: 42, right: 18, top: 24, bottom: 42 },
  xAxis: { type: "category", data: trend.value.labels || [] },
  yAxis: { type: "value", minInterval: 1 },
  series: [
    { name: "技能", type: "bar", stack: "total", data: trend.value.skill_counts || [] },
    { name: "证书", type: "bar", stack: "total", data: trend.value.certificate_counts || [] },
    { name: "项目", type: "bar", stack: "total", data: trend.value.project_counts || [] },
    { name: "实习", type: "bar", stack: "total", data: trend.value.internship_counts || [] },
  ],
}));

const applyGrowthPayload = (payload) => {
  records.value = payload?.records || [];
  trend.value = { ...createEmptyTrend(), ...(payload?.trend || {}) };
  const recordIds = sortedRecords.value.map((item) => item.id);
  if (!recordIds.length) {
    reviewForm.growth_record_id = null;
    return;
  }
  if (!recordIds.includes(reviewForm.growth_record_id)) reviewForm.growth_record_id = recordIds[0];
};

const syncRouteState = async () => {
  const nextTab = allowedTabs.value.includes(activeTab.value) ? activeTab.value : allowedTabs.value[0];
  if (route.query.tab === nextTab) return;
  await router.replace({ path: "/growth/center", query: { ...route.query, tab: nextTab } });
};

const load = async () => {
  if (isStudent.value) {
    const [pathRes, growthRes, reviewRes, optimizationRes] = await Promise.allSettled([
      studentApi.getPath(),
      studentApi.growthRecords(),
      studentApi.reviews(),
      studentApi.latestOptimization(),
    ]);
    path.value = pathRes.status === "fulfilled" ? pathRes.value.data || null : null;
    applyGrowthPayload(growthRes.status === "fulfilled" ? growthRes.value.data : null);
    reviews.value = reviewRes.status === "fulfilled" ? reviewRes.value.data || [] : [];
    optimization.value = optimizationRes.status === "fulfilled" ? optimizationRes.value.data || null : null;
  } else {
    if (!selectedStudentId.value) {
      path.value = null;
      records.value = [];
      reviews.value = [];
      optimization.value = null;
      trend.value = createEmptyTrend();
      return;
    }
    const [pathRes, growthRes, optimizationRes] = await Promise.allSettled([
      enterpriseApi.studentCareerPath(selectedStudentId.value),
      enterpriseApi.studentGrowthRecords(selectedStudentId.value),
      enterpriseApi.studentLatestOptimization(selectedStudentId.value),
    ]);
    path.value = pathRes.status === "fulfilled" ? pathRes.value.data || null : null;
    applyGrowthPayload(growthRes.status === "fulfilled" ? growthRes.value.data : null);
    reviews.value = [];
    optimization.value = optimizationRes.status === "fulfilled" ? optimizationRes.value.data || null : null;
  }
};

const submitGrowth = async () => {
  if (!isStudent.value) return;
  await studentApi.createGrowthRecord({ ...submissionForm });
  ElMessage.success("阶段成果已提交");
  await load();
  await switchTab("trend");
};

const submitReview = async () => {
  if (isStudent.value || !selectedStudentId.value || !reviewForm.growth_record_id) return;
  await enterpriseApi.review(selectedStudentId.value, { ...reviewForm });
  ElMessage.success("企业复评已提交");
  reviewForm.comment = "";
  reviewForm.score = 85;
  reviewForm.suggestions = [];
  await load();
};

const runOptimization = async () => {
  if (!isStudent.value) return;
  optimizing.value = true;
  try {
    optimization.value = (await studentApi.reOptimize()).data || null;
    ElMessage.success("优化方案已刷新");
  } finally {
    optimizing.value = false;
  }
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

const formatTime = (value) => (value ? String(value).replace("T", " ").slice(0, 16) : "-");

watch(
  () => route.query.tab,
  (value) => {
    const nextTab = allowedTabs.value.includes(value) ? value : allowedTabs.value[0];
    if (nextTab !== activeTab.value) activeTab.value = nextTab;
  },
);

onMounted(async () => {
  if (isStudent.value) await load();
});
</script>

<style scoped>
.growth-center {
  display: grid;
  gap: 18px;
  --metric-label-color: #6b7280;
  --metric-value-color: #1f2937;
  --content-muted-color: #64748b;
  --heading-color: #1f2937;
  --bullet-color: #475569;
  --highlight-shadow: none;
  --surface-bg: #fbfdff;
  --surface-border: #e6edf7;
  --description-label-bg: #f8fbff;
  --description-content-bg: #ffffff;
  --description-label-color: #334155;
  --description-content-color: #1f2937;
}

:global(.role-student) .growth-center {
  --metric-label-color: rgba(228, 248, 246, 0.88);
  --metric-value-color: #f8fdff;
  --content-muted-color: rgba(228, 248, 246, 0.88);
  --heading-color: #f8fdff;
  --bullet-color: rgba(236, 250, 248, 0.92);
  --highlight-shadow: 0 1px 0 rgba(2, 6, 23, 0.38);
  --surface-bg: linear-gradient(180deg, rgba(28, 37, 65, 0.92), rgba(11, 19, 43, 0.86));
  --surface-border: rgba(91, 192, 190, 0.14);
  --description-label-bg: rgba(28, 37, 65, 0.96);
  --description-content-bg: rgba(17, 27, 50, 0.9);
  --description-label-color: #e8fffc;
  --description-content-color: #f8fdff;
}

:global(.role-admin) .growth-center {
  --metric-label-color: rgba(203, 226, 255, 0.88);
  --metric-value-color: #f8fbff;
  --content-muted-color: rgba(203, 226, 255, 0.86);
  --heading-color: #f8fbff;
  --bullet-color: rgba(219, 234, 254, 0.92);
  --highlight-shadow: 0 1px 0 rgba(2, 6, 23, 0.42);
  --surface-bg: linear-gradient(180deg, rgba(30, 41, 59, 0.92), rgba(15, 23, 42, 0.88));
  --surface-border: rgba(56, 189, 248, 0.14);
  --description-label-bg: rgba(30, 41, 59, 0.96);
  --description-content-bg: rgba(18, 28, 48, 0.92);
  --description-label-color: #e5f0ff;
  --description-content-color: #f8fbff;
}

:global(.role-enterprise) .growth-center {
  --metric-label-color: rgba(241, 252, 248, 0.96);
  --metric-value-color: #ffffff;
  --content-muted-color: rgba(232, 245, 239, 0.9);
  --heading-color: #ffffff;
  --bullet-color: rgba(244, 252, 248, 0.94);
  --highlight-shadow: 0 1px 0 rgba(4, 12, 24, 0.44);
  --surface-bg: linear-gradient(180deg, rgba(12, 25, 50, 0.92), rgba(15, 31, 60, 0.88));
  --surface-border: rgba(111, 255, 233, 0.16);
  --description-label-bg: rgba(16, 31, 58, 0.96);
  --description-content-bg: rgba(10, 24, 46, 0.92);
  --description-label-color: #f0fffb;
  --description-content-color: #ffffff;
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
.review-text,
.summary-text,
.review-time {
  margin-top: 8px;
  color: var(--content-muted-color);
  line-height: 1.8;
}

.card-list,
.record-picker,
.bullet-list,
.tag-wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.tag-wrap {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 10px;
}

.review-card,
.summary-card,
.record-option {
  padding: 18px;
  border-radius: 20px;
  border: 1px solid var(--surface-border);
  background: var(--surface-bg);
}

.record-option {
  cursor: pointer;
  transition: all 0.18s ease;
}

.record-option.active,
.record-option:hover {
  border-color: #88b4ff;
  box-shadow: 0 14px 28px rgba(15, 98, 254, 0.08);
}

.review-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.review-score,
.summary-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--heading-color);
  text-shadow: var(--highlight-shadow);
}

.bullet-item {
  position: relative;
  padding-left: 14px;
  color: var(--bullet-color);
  line-height: 1.7;
}

.bullet-item::before {
  content: "";
  position: absolute;
  left: 0;
  top: 11px;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #0f62fe;
}

.review-form {
  margin-top: 18px;
}

.workbench-tabs :deep(.el-tabs__header) {
  margin-bottom: 18px;
}

.growth-center :deep(.el-descriptions__table),
.growth-center :deep(.el-descriptions__body),
.growth-center :deep(.el-descriptions__cell) {
  --el-descriptions-table-border: var(--surface-border);
  --el-fill-color-blank: var(--description-content-bg);
  --el-fill-color-light: var(--description-label-bg);
  --el-bg-color: var(--description-content-bg);
  --el-descriptions-item-bordered-label-background: var(--description-label-bg);
  --el-descriptions-item-bordered-content-background: var(--description-content-bg);
}

.growth-center :deep(.el-descriptions__label) {
  color: var(--description-label-color);
  font-weight: 700;
}

.growth-center :deep(.el-descriptions__content) {
  color: var(--description-content-color);
}

.growth-center :deep(.el-descriptions__label.el-descriptions__cell.is-bordered-label) {
  background: var(--description-label-bg) !important;
  color: var(--description-label-color) !important;
}

.growth-center :deep(.el-descriptions__content.el-descriptions__cell.is-bordered-content) {
  background: var(--description-content-bg) !important;
  color: var(--description-content-color) !important;
}
</style>
