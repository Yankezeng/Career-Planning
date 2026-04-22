<template>
  <div class="page-shell match-center">
    <PageHeader title="人岗匹配工作台" description="将匹配列表、排序推荐、维度详情和差距分析收拢到同一页，保留全部匹配能力但减少重复页面切换。">
      <el-button @click="load">刷新数据</el-button>
      <el-button v-if="isStudent" type="primary" :loading="generating" @click="generate">重新生成人岗匹配</el-button>
    </PageHeader>

    <StudentScopeSelector v-model="selectedStudentId" @change="handleStudentChange" />

    <el-empty v-if="!orderedMatches.length" description="当前还没有匹配结果，先生成画像或重新计算匹配。" />

    <template v-else>
      <div class="metric-grid">
        <SectionCard v-for="item in summaryCards" :key="item.label">
          <div class="metric-label">{{ item.label }}</div>
          <div class="metric-value">{{ item.value }}</div>
          <div class="metric-tip">{{ item.tip }}</div>
        </SectionCard>
      </div>

      <div class="two-col focus-grid">
        <SectionCard title="当前聚焦岗位">
          <div class="focus-card">
            <div>
              <div class="focus-name">{{ selectedMatch?.job?.name || "未选择岗位" }}</div>
              <div class="focus-meta">{{ selectedMatch?.job?.category || "-" }} · {{ selectedMatch?.job?.industry || "-" }}</div>
            </div>
            <div class="focus-score">{{ Number(selectedMatch?.total_score || 0).toFixed(1) }} 分</div>
          </div>
          <p class="focus-summary">{{ selectedMatch?.summary || "当前岗位暂无匹配摘要。" }}</p>
          <div class="focus-actions">
            <el-button type="primary" @click="switchTab('detail')">查看维度详情</el-button>
            <el-button plain @click="switchTab('gaps')">查看差距分析</el-button>
          </div>
        </SectionCard>

        <SectionCard title="岗位切换">
          <el-select v-model="selectedJobId" filterable placeholder="选择岗位" style="width: 100%" @change="handleJobChange">
            <el-option v-for="item in orderedMatches" :key="item.job?.id" :label="`${item.job?.name || '-'} · ${Number(item.total_score || 0).toFixed(1)} 分`" :value="item.job?.id" />
          </el-select>
          <div class="tag-wrap selector-tags">
            <el-tag round type="success">已纳入展示岗位 {{ orderedMatches.length }} 个</el-tag>
            <el-tag round>当前差距项 {{ selectedMatch?.gaps?.length || 0 }} 个</el-tag>
          </div>
        </SectionCard>
      </div>

      <el-tabs v-model="activeTab" class="workbench-tabs" @tab-change="handleTabChange">
        <el-tab-pane label="总览排序" name="overview">
          <SectionCard title="岗位排序总览">
            <el-table :data="orderedMatches">
              <el-table-column type="index" label="排名" width="76" />
              <el-table-column label="岗位名称" min-width="180">
                <template #default="{ row }">{{ row.job?.name || "-" }}</template>
              </el-table-column>
              <el-table-column label="岗位类别" min-width="120">
                <template #default="{ row }">{{ row.job?.category || "-" }}</template>
              </el-table-column>
              <el-table-column label="匹配分" width="110">
                <template #default="{ row }">{{ Number(row.total_score || 0).toFixed(1) }}</template>
              </el-table-column>
              <el-table-column prop="summary" label="匹配说明" min-width="260" />
              <el-table-column label="操作" width="180" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="pickMatch(row, 'detail')">详情</el-button>
                  <el-button link type="primary" @click="pickMatch(row, 'gaps')">差距</el-button>
                </template>
              </el-table-column>
            </el-table>
          </SectionCard>
        </el-tab-pane>

        <el-tab-pane label="匹配详情" name="detail">
          <div class="two-col">
            <SectionCard :title="`${selectedMatch?.job?.name || '当前岗位'} · 维度得分`">
              <ScoreBars :items="scoreItems" />
            </SectionCard>

            <SectionCard title="匹配理由与建议">
              <div class="stack">
                <p class="focus-summary">{{ selectedMatch?.summary || "当前岗位暂无匹配摘要。" }}</p>
                <el-timeline>
                  <el-timeline-item v-for="item in selectedMatch?.reasons || []" :key="item">{{ item }}</el-timeline-item>
                </el-timeline>
              </div>
            </SectionCard>
          </div>
        </el-tab-pane>

        <el-tab-pane label="差距分析" name="gaps">
          <SectionCard :title="`${selectedMatch?.job?.name || '当前岗位'} · 差距项`">
            <el-empty v-if="!(selectedMatch?.gaps || []).length" description="当前岗位暂无明显差距项。" />
            <el-table v-else :data="selectedMatch?.gaps || []">
              <el-table-column prop="gap_type" label="差距类型" width="140" />
              <el-table-column prop="gap_item" label="差距项" min-width="180" />
              <el-table-column prop="description" label="说明" min-width="260" />
              <el-table-column prop="priority" label="优先级" width="100" />
            </el-table>
          </SectionCard>
        </el-tab-pane>
      </el-tabs>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { enterpriseApi, studentApi } from "@/api";
import { useAuthStore } from "@/stores/auth";
import PageHeader from "@/components/PageHeader.vue";
import ScoreBars from "@/components/ScoreBars.vue";
import SectionCard from "@/components/SectionCard.vue";
import StudentScopeSelector from "@/components/StudentScopeSelector.vue";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const isStudent = computed(() => auth.role === "student");
const matches = ref([]);
const selectedStudentId = ref(null);
const selectedJobId = ref(null);
const generating = ref(false);
let routeSyncEnabled = true;
const validTabs = ["overview", "detail", "gaps"];
const activeTab = ref(validTabs.includes(route.query.tab) ? route.query.tab : "overview");

const orderedMatches = computed(() =>
  [...matches.value].sort((left, right) => Number(right.total_score || 0) - Number(left.total_score || 0)),
);

const selectedMatch = computed(() => {
  const currentId = Number(selectedJobId.value || 0);
  return orderedMatches.value.find((item) => Number(item.job?.id || 0) === currentId) || orderedMatches.value[0] || null;
});

const scoreItems = computed(() => {
  if (!selectedMatch.value) return [];
  return [
    { label: "专业匹配", value: selectedMatch.value.major_match },
    { label: "技能匹配", value: selectedMatch.value.skill_match },
    { label: "证书匹配", value: selectedMatch.value.certificate_match },
    { label: "项目经历匹配", value: selectedMatch.value.project_match },
    { label: "实习经历匹配", value: selectedMatch.value.internship_match },
    { label: "通用能力匹配", value: selectedMatch.value.soft_skill_match },
    { label: "兴趣方向匹配", value: selectedMatch.value.interest_match },
  ];
});

const averageScore = computed(() => {
  if (!orderedMatches.value.length) return 0;
  const total = orderedMatches.value.reduce((sum, item) => sum + Number(item.total_score || 0), 0);
  return Number((total / orderedMatches.value.length).toFixed(1));
});

const summaryCards = computed(() => [
  { label: "全部岗位", value: orderedMatches.value.length, tip: "Milvus 内同步到业务库后的全部岗位匹配结果。" },
  { label: "最高匹配分", value: `${Number(orderedMatches.value[0]?.total_score || 0).toFixed(1)} 分`, tip: orderedMatches.value[0]?.job?.name || "暂无推荐岗位" },
  { label: "平均匹配分", value: `${averageScore.value} 分`, tip: "当前展示岗位的平均匹配水平。" },
  { label: "当前差距项", value: selectedMatch.value?.gaps?.length || 0, tip: "围绕当前聚焦岗位需要优先补齐的能力项。" },
]);

const canSyncRouteState = () => routeSyncEnabled && route.path === "/matches/center";

const syncRouteState = async () => {
  if (!canSyncRouteState()) return;
  const nextQuery = { ...route.query, tab: activeTab.value };
  if (selectedJobId.value) nextQuery.id = String(selectedJobId.value);
  else delete nextQuery.id;
  if (nextQuery.tab === route.query.tab && nextQuery.id === route.query.id) return;
  await router.replace({ path: "/matches/center", query: nextQuery });
};

const normalizeSelection = async () => {
  const currentIds = orderedMatches.value.map((item) => Number(item.job?.id || 0)).filter(Boolean);
  if (!currentIds.length) {
    selectedJobId.value = null;
    return;
  }
  const routeJobId = Number(route.query.id || 0);
  if (currentIds.includes(routeJobId)) selectedJobId.value = routeJobId;
  if (!currentIds.includes(Number(selectedJobId.value || 0))) selectedJobId.value = currentIds[0];
  if (!validTabs.includes(activeTab.value)) activeTab.value = "overview";
  await syncRouteState();
};

const load = async () => {
  if (!isStudent.value && !selectedStudentId.value) {
    matches.value = [];
    selectedJobId.value = null;
    return;
  }
  if (isStudent.value) {
    const res = await studentApi.getMatches();
    const existing = res.data || [];
    if (existing.length) {
      matches.value = existing;
      await normalizeSelection();
      return;
    }
    await generate();
    return;
  }
  const res = await enterpriseApi.studentMatches(selectedStudentId.value);
  matches.value = res.data || [];
  await normalizeSelection();
};

const generate = async () => {
  generating.value = true;
  try {
    const res = await studentApi.generateMatches();
    matches.value = res.data || [];
    await normalizeSelection();
  } finally {
    generating.value = false;
  }
};

const switchTab = async (tab) => {
  activeTab.value = validTabs.includes(tab) ? tab : "overview";
  await syncRouteState();
};

const handleTabChange = async (tab) => {
  activeTab.value = tab;
  await syncRouteState();
};

const handleJobChange = async () => {
  await normalizeSelection();
};

const handleStudentChange = async () => {
  await load();
};

const pickMatch = async (row, tab = "detail") => {
  selectedJobId.value = row.job?.id || null;
  activeTab.value = tab;
  await syncRouteState();
};

watch(
  () => route.query.tab,
  async (value) => {
    const nextTab = validTabs.includes(value) ? value : "overview";
    if (nextTab !== activeTab.value) activeTab.value = nextTab;
  },
);

watch(
  () => route.query.id,
  async (value) => {
    const nextId = Number(value || 0);
    if (nextId && nextId !== Number(selectedJobId.value || 0)) {
      selectedJobId.value = nextId;
      await normalizeSelection();
    }
  },
);

onMounted(async () => {
  if (isStudent.value) await load();
});

onBeforeUnmount(() => {
  routeSyncEnabled = false;
});
</script>

<style scoped>
.match-center {
  display: grid;
  gap: 18px;
  --metric-label-color: #6b7280;
  --metric-value-color: #1f2937;
  --content-muted-color: #64748b;
  --heading-color: #111827;
  --score-color: #2563eb;
  --highlight-shadow: none;
  --disabled-button-bg: rgba(148, 163, 184, 0.08);
  --disabled-button-border: rgba(148, 163, 184, 0.14);
  --disabled-button-color: #94a3b8;
}

.metric-label {
  color: var(--metric-label-color);
  font-size: 13px;
}

.metric-value {
  margin-top: 8px;
  font-size: 30px;
  font-weight: 800;
  color: var(--metric-value-color);
  text-shadow: var(--highlight-shadow);
}

.metric-tip,
.focus-meta,
.focus-summary {
  margin-top: 8px;
  color: var(--content-muted-color);
  line-height: 1.8;
}

.focus-grid {
  align-items: stretch;
}

.focus-card,
.focus-actions,
.selector-tags,
.stack {
  display: flex;
  gap: 12px;
}

.focus-card,
.focus-actions {
  align-items: center;
  justify-content: space-between;
}

.focus-actions,
.selector-tags,
.stack {
  flex-wrap: wrap;
}

.focus-name {
  font-size: 24px;
  font-weight: 700;
  color: var(--heading-color);
  text-shadow: var(--highlight-shadow);
}

.focus-score {
  font-size: 30px;
  font-weight: 800;
  color: var(--score-color);
  text-shadow: var(--highlight-shadow);
}

.selector-tags {
  margin-top: 14px;
}

.workbench-tabs :deep(.el-tabs__header) {
  margin-bottom: 18px;
}

:global(.role-student) .match-center {
  --metric-label-color: rgba(241, 252, 255, 0.96);
  --metric-value-color: #ffffff;
  --content-muted-color: rgba(234, 247, 252, 0.92);
  --heading-color: #f8fdff;
  --score-color: #60a5fa;
  --highlight-shadow: 0 1px 0 rgba(2, 6, 23, 0.48);
  --disabled-button-bg: rgba(191, 219, 229, 0.24);
  --disabled-button-border: rgba(111, 255, 233, 0.18);
  --disabled-button-color: rgba(248, 252, 255, 0.92);
}

:global(.role-admin) .match-center {
  --metric-label-color: rgba(226, 239, 255, 0.96);
  --metric-value-color: #ffffff;
  --content-muted-color: rgba(220, 236, 255, 0.92);
  --heading-color: #f8fbff;
  --score-color: #60a5fa;
  --highlight-shadow: 0 1px 0 rgba(2, 6, 23, 0.52);
  --disabled-button-bg: rgba(148, 163, 184, 0.24);
  --disabled-button-border: rgba(96, 165, 250, 0.18);
  --disabled-button-color: rgba(239, 246, 255, 0.9);
}

:global(.role-enterprise) .match-center {
  --metric-label-color: rgba(241, 252, 248, 0.96);
  --metric-value-color: #ffffff;
  --content-muted-color: rgba(232, 245, 239, 0.9);
  --heading-color: #ffffff;
  --score-color: #60a5fa;
  --highlight-shadow: 0 1px 0 rgba(4, 12, 24, 0.46);
  --disabled-button-bg: rgba(191, 219, 229, 0.26);
  --disabled-button-border: rgba(111, 255, 233, 0.18);
  --disabled-button-color: rgba(248, 252, 255, 0.92);
}

.match-center :deep(.el-button.is-disabled),
.match-center :deep(.el-button.is-disabled:hover),
.match-center :deep(.el-button.is-disabled:focus-visible) {
  background: var(--disabled-button-bg);
  border-color: var(--disabled-button-border);
  color: var(--disabled-button-color);
}

@media (max-width: 900px) {
  .focus-card,
  .focus-actions {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
