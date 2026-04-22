<template>
  <div :class="['page-shell', 'dashboard-root', `dashboard-${role}`]">
    <DynamicBackground :particle-count="120" primary-color="#00d4ff" secondary-color="#6fffe9" :speed="0.4" />
    <template v-if="role === 'admin'">
      <section class="hero admin-hero">
        <div>
          <div class="hero-eyebrow">System CRM Panel</div>
          <h1 class="hero-title">系统管理中控台</h1>
          <p class="hero-desc">聚合系统总览、服务状态、数据库状态和知识库状态，面向后台管理与运维巡检。</p>
          <div class="hero-tags">
            <span class="hero-tag">注册账号：{{ crmMetrics.registered_account_count ?? adminCenter?.counts?.user_count ?? 0 }}</span>
            <span class="hero-tag">企业库：{{ crmMetrics.enterprise_total_count ?? adminCenter?.counts?.enterprise_count ?? 0 }}</span>
            <span class="hero-tag">知识库：{{ adminCenter?.vector_db?.document_count || 0 }} 条</span>
          </div>
        </div>
        <div class="hero-side-card admin-side-card">
          <div class="hero-side-label">系统总览</div>
          <div class="hero-side-value">{{ crmMetrics.enterprise_with_delivery_count ?? 0 }} 家活跃企业</div>
          <div class="hero-side-meta">{{ adminCenter?.counts?.delivery_count || 0 }} 份投递已进入企业端，{{ crmMetrics.active_account_count ?? 0 }} 个账号目前处于启用状态。</div>
        </div>
      </section>

      <div class="metric-grid cockpit-metrics">
        <div v-for="card in adminMetricCards" :key="card.label" class="metric-card metric-card-admin">
          <div class="metric-card-label">{{ card.label }}</div>
          <div class="metric-card-value">{{ card.value }}</div>
          <div class="metric-card-tip">{{ card.tip }}</div>
        </div>
      </div>

      <div class="three-col admin-status-grid">
        <SectionCard title="服务健康面板">
          <div class="status-list">
            <div v-for="item in adminServiceStatus" :key="item.label" class="status-item">
              <div>
                <div class="status-label">{{ item.label }}</div>
                <div class="status-meta">{{ item.meta }}</div>
              </div>
              <span :class="['status-pill', item.status]">{{ item.statusLabel }}</span>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="业务数据库状态">
          <div class="info-list">
            <div class="info-row"><span>数据库</span><strong>{{ adminCenter?.business_db?.database || "-" }}</strong></div>
            <div class="info-row"><span>连接串</span><strong>{{ adminCenter?.business_db?.url || "-" }}</strong></div>
            <div class="info-row"><span>表数量</span><strong>{{ adminCenter?.business_db?.table_count || 0 }}</strong></div>
            <div class="info-row"><span>连通延迟</span><strong>{{ adminCenter?.business_db?.latency_ms ?? "-" }} ms</strong></div>
            <div class="info-row"><span>版本</span><strong>{{ adminCenter?.business_db?.server_version || "-" }}</strong></div>
            <div class="info-row"><span>大小</span><strong>{{ adminSizeLabel }}</strong></div>
          </div>
        </SectionCard>

        <SectionCard title="Milvus 岗位知识库">
          <div class="vector-status-head">
            <span class="status-label">运行状态</span>
            <span :class="['status-pill', adminCenter?.vector_db?.status || 'unknown']">{{ vectorStatusLabel }}</span>
          </div>
          <div class="info-list">
            <div class="info-row"><span>后端</span><strong>{{ adminCenter?.vector_db?.backend || "-" }}</strong></div>
            <div class="info-row"><span>模式</span><strong>{{ adminCenter?.vector_db?.mode || "-" }}</strong></div>
            <div class="info-row"><span>集合</span><strong>{{ adminCenter?.vector_db?.collection_name || "-" }}</strong></div>
            <div class="info-row"><span>文档总数</span><strong>{{ adminCenter?.vector_db?.document_count || 0 }}</strong></div>
            <div class="info-row"><span>企业来源</span><strong>{{ adminCenter?.vector_db?.company_count || 0 }}</strong></div>
            <div class="info-row"><span>岗位分类</span><strong>{{ adminCenter?.vector_db?.category_count || 0 }}</strong></div>
            <div class="info-row"><span>存储位置</span><strong>{{ adminCenter?.vector_db?.uri || "-" }}</strong></div>
            <div class="info-row"><span>状态说明</span><strong>{{ adminCenter?.vector_db?.message || "-" }}</strong></div>
          </div>
        </SectionCard>
      </div>

      <div class="two-col admin-main-grid">
        <SectionCard title="CRM 关键线索">
          <div class="highlight-grid">
            <div v-for="item in adminHighlightCards" :key="item.title" class="highlight-card">
              <div class="highlight-title">{{ item.title }}</div>
              <div class="highlight-value">{{ item.value }}</div>
              <div class="highlight-desc">{{ item.description }}</div>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="角色分布与治理重点">
          <div class="role-bars">
            <div v-for="item in adminRoleBars" :key="item.role_code" class="role-bar-item">
              <div class="role-bar-top">
                <span>{{ item.role_name }}</span>
                <strong>{{ item.count }}</strong>
              </div>
              <div class="role-bar-track"><span :style="{ width: item.width }"></span></div>
            </div>
          </div>
          <div class="admin-actions">
            <div v-for="item in adminActionList" :key="item.title" class="action-card">
              <div class="action-title">{{ item.title }}</div>
              <div class="action-desc">{{ item.desc }}</div>
            </div>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="模型质检面板">
        <div class="metric-grid cockpit-metrics quality-metrics">
          <div v-for="item in qualityCards" :key="item.label" class="metric-card metric-card-admin">
            <div class="metric-card-label">{{ item.label }}</div>
            <div class="metric-card-value">{{ item.value }}</div>
            <div class="metric-card-tip">{{ item.tip }}</div>
          </div>
        </div>
        <el-table :data="qualityRows" class="student-table">
          <el-table-column prop="label" label="评估类型" min-width="140" />
          <el-table-column prop="sampleSize" label="样本数" width="110" />
          <el-table-column label="准确率" width="130">
            <template #default="{ row }">{{ Number(row.accuracy || 0).toFixed(1) }}%</template>
          </el-table-column>
          <el-table-column label="命中率" width="130">
            <template #default="{ row }">{{ Number(row.hitRate || 0).toFixed(1) }}%</template>
          </el-table-column>
          <el-table-column label="解释率" width="130">
            <template #default="{ row }">{{ Number(row.explainRate || 0).toFixed(1) }}%</template>
          </el-table-column>
        </el-table>
      </SectionCard>

      <div class="two-col admin-chart-grid">
        <SectionCard title="注册账号角色分布">
          <AnalysisChart :option="adminRoleChartOption" height="320px" />
        </SectionCard>
        <SectionCard title="注册账号增长趋势">
          <AnalysisChart :option="adminAccountGrowthOption" height="320px" />
        </SectionCard>
      </div>

      <div class="two-col admin-chart-grid">
        <SectionCard title="企业接入增长趋势">
          <AnalysisChart :option="adminEnterpriseGrowthOption" height="320px" />
        </SectionCard>
        <SectionCard title="企业行业分布">
          <AnalysisChart :option="adminIndustryPieOption" height="320px" />
        </SectionCard>
      </div>

      <SectionCard title="企业投递活跃排行">
        <AnalysisChart :option="adminEnterpriseRankOption" height="340px" />
      </SectionCard>

      <div class="two-col admin-crm-grid">
        <SectionCard title="注册账号 CRM 检视台">
          <div class="inspector-shell">
            <div class="inspector-sidebar">
              <InspectorSearchBar v-model="adminAccountSearch" placeholder="搜索账号 / 姓名 / 角色" hint="SearchInput" :count="filteredAdminAccounts.length" />
              <div class="inspector-list">
                <button
                  v-for="item in filteredAdminAccounts"
                  :key="item.id"
                  type="button"
                  :class="['inspector-item', { active: selectedAdminAccount?.id === item.id }]"
                  @click="selectedAdminAccountId = item.id"
                >
                  <div class="inspector-item-top">
                    <strong>{{ item.real_name || item.username }}</strong>
                    <span class="inspector-badge">{{ item.role_name }}</span>
                  </div>
                  <div class="inspector-item-meta">{{ item.username }} · {{ boolText(item.is_active) }}</div>
                  <div class="inspector-item-desc">{{ item.department || "未分配院系/部门" }} {{ item.classroom ? `· ${item.classroom}` : "" }}</div>
                </button>
                <el-empty v-if="!filteredAdminAccounts.length" description="没有匹配到账号" />
              </div>
            </div>

            <div class="inspector-detail-panel">
              <div class="inspector-detail-head">
                <div>
                  <div class="detail-heading">{{ selectedAdminAccount?.real_name || "未选择账号" }}</div>
                  <div class="detail-subheading">{{ selectedAdminAccount?.username || "请从左侧选择一条账号记录" }}</div>
                </div>
                <el-tag v-if="selectedAdminAccount" effect="dark">{{ selectedAdminAccount.role_name }}</el-tag>
              </div>
              <div class="inspector-detail-body">
                <KeyValueInspector :data="selectedAdminAccountInspectData" empty-text="请选择左侧账号后查看详情" />
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="企业 CRM 检视台">
          <div class="inspector-shell">
            <div class="inspector-sidebar">
              <InspectorSearchBar v-model="adminEnterpriseSearch" placeholder="搜索企业 / 行业 / 类型" hint="KeyValue" :count="filteredAdminEnterprises.length" />
              <div class="inspector-list">
                <button
                  v-for="item in filteredAdminEnterprises"
                  :key="item.id"
                  type="button"
                  :class="['inspector-item', { active: selectedAdminEnterprise?.id === item.id }]"
                  @click="selectedAdminEnterpriseId = item.id"
                >
                  <div class="inspector-item-top">
                    <strong>{{ item.company_name }}</strong>
                    <span class="inspector-badge">{{ item.industry }}</span>
                  </div>
                  <div class="inspector-item-meta">{{ item.company_type || "未分类" }} · {{ item.company_size || "规模未标注" }}</div>
                  <div class="inspector-item-desc">投递 {{ item.delivery_count }} 份 · 平均匹配 {{ Number(item.avg_match_score || 0).toFixed(1) }}</div>
                </button>
                <el-empty v-if="!filteredAdminEnterprises.length" description="没有匹配到企业" />
              </div>
            </div>

            <div class="inspector-detail-panel">
              <div class="inspector-detail-head">
                <div>
                  <div class="detail-heading">{{ selectedAdminEnterprise?.company_name || "未选择企业" }}</div>
                  <div class="detail-subheading">{{ selectedAdminEnterprise?.industry || "请从左侧选择一条企业记录" }}</div>
                </div>
                <el-tag v-if="selectedAdminEnterprise" effect="dark">投递 {{ selectedAdminEnterprise.delivery_count }}</el-tag>
              </div>
              <div class="inspector-detail-body">
                <KeyValueInspector :data="selectedAdminEnterpriseInspectData" empty-text="请选择左侧企业后查看详情" />
              </div>
            </div>
          </div>
        </SectionCard>
      </div>
    </template>

    <template v-else-if="role === 'enterprise'">
      <EnterpriseHRMBoard />
    </template>

    <template v-else>
      <section class="hero student-hero">
        <div>
          <div class="hero-eyebrow">Student Workspace</div>
          <h1 class="hero-title">学生中控台</h1>
          <p class="hero-desc">把画像、匹配、路径、岗位图谱、简历和投递动作收拢到一个学生侧控制面板里，先看状态，再决定下一步推进什么。</p>
          <div class="hero-tags">
            <span class="hero-tag">画像：{{ studentProfile ? "已生成" : "待生成" }}</span>
            <span class="hero-tag">匹配：{{ studentMatches.length }} 条</span>
            <span class="hero-tag">图谱：独立页面</span>
          </div>
        </div>
        <div class="hero-side-card student-side-card">
          <div class="hero-side-label">当前核心目标</div>
          <div class="hero-side-value">{{ studentTopMatches[0]?.job?.name || "先生成匹配结果" }}</div>
          <div class="hero-side-meta">优先围绕一个岗位补齐差距，再同步查看图谱、项目、简历和投递动作。</div>
        </div>
      </section>

      <div class="metric-grid student-metrics">
        <div v-for="card in studentMetricCards" :key="card.label" class="metric-card metric-card-student">
          <div class="metric-card-label">{{ card.label }}</div>
          <div class="metric-card-value">{{ card.value }}</div>
          <div class="metric-card-tip">{{ card.tip }}</div>
        </div>
      </div>

      <SectionCard title="中控台快捷入口">
        <div class="student-shortcuts">
          <button v-for="item in studentQuickActions" :key="item.title" type="button" class="shortcut-card" @click="router.push(item.path)">
            <div class="shortcut-title">{{ item.title }}</div>
            <div class="shortcut-desc">{{ item.desc }}</div>
          </button>
        </div>
      </SectionCard>

      <div class="two-col student-main-grid">
        <SectionCard title="中控台主线">
          <div class="student-story">
            <div class="student-story-title">{{ studentTopMatches[0]?.job?.name || "建议先生成匹配" }}</div>
            <p>{{ studentStory }}</p>
            <div class="story-steps">
              <div v-for="item in studentActionList" :key="item.title" class="story-step">
                <div class="story-step-title">{{ item.title }}</div>
                <div class="story-step-desc">{{ item.desc }}</div>
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="画像与成熟度快照">
          <template v-if="studentProfile">
            <div class="snapshot-grid">
              <div v-for="item in studentProfileSnapshot" :key="item.label" class="snapshot-card">
                <div class="snapshot-label">{{ item.label }}</div>
                <div class="snapshot-value">{{ item.value }}</div>
              </div>
            </div>
            <div class="detail-block dark-block">
              <div class="detail-block-title">画像摘要</div>
              <p>{{ studentProfile.summary || "暂无摘要" }}</p>
            </div>
          </template>
          <el-empty v-else description="还没有学生画像，建议先生成画像" />
        </SectionCard>
      </div>

      <SectionCard title="岗位优先级面板">
        <el-table :data="studentTopMatches" class="student-table">
          <el-table-column label="岗位名称" min-width="180">
            <template #default="{ row }">{{ row.job?.name || "-" }}</template>
          </el-table-column>
          <el-table-column label="岗位类别" width="120">
            <template #default="{ row }">{{ row.job?.category || "-" }}</template>
          </el-table-column>
          <el-table-column label="匹配度" width="120">
            <template #default="{ row }">{{ Number(row.total_score || 0).toFixed(1) }} 分</template>
          </el-table-column>
          <el-table-column label="建议动作" min-width="220">
            <template #default="{ row }">{{ matchActionText(row) }}</template>
          </el-table-column>
        </el-table>
      </SectionCard>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { adminApi, enterpriseApi, studentApi } from "@/api";
import { useAuthStore } from "@/stores/auth";
import AnalysisChart from "@/components/AnalysisChart.vue";
import DynamicBackground from "@/components/common/DynamicBackground.vue";
import EnterpriseHRMBoard from "@/components/enterprise/EnterpriseHRMBoard.vue";
import InspectorSearchBar from "@/components/InspectorSearchBar.vue";
import KeyValueInspector from "@/components/KeyValueInspector.vue";
import SectionCard from "@/components/SectionCard.vue";

const fileBase = "http://127.0.0.1:8000";
const auth = useAuthStore();
const router = useRouter();
const role = computed(() => auth.role || "student");
const adminCenter = ref(null);
const enterpriseBoard = ref(null);
const enterpriseDeliveries = ref([]);
const selectedDeliveryId = ref(null);
const enterpriseFilter = ref("all");
const candidateSearch = ref("");
const studentMatches = ref([]);
const studentProfile = ref(null);
const studentPath = ref(null);
const adminAccountSearch = ref("");
const selectedAdminAccountId = ref(null);
const adminEnterpriseSearch = ref("");
const selectedAdminEnterpriseId = ref(null);

const enterpriseFilters = [
  { label: "全部候选人", value: "all" },
  { label: "高匹配优先", value: "high" },
  { label: "待复评", value: "pending" },
];

const crmDashboard = computed(() => adminCenter.value?.crm_dashboard || {});
const crmMetrics = computed(() => crmDashboard.value.metrics || {});
const crmCharts = computed(() => crmDashboard.value.charts || {});
const adminAccounts = computed(() => crmDashboard.value.accounts || []);
const adminEnterprises = computed(() => crmDashboard.value.enterprises || []);
const adminInsights = computed(() => crmDashboard.value.insights || []);
const adminHighlightCards = computed(() => [...(adminCenter.value?.highlights || []), ...adminInsights.value]);
const qualityPanel = computed(() => adminCenter.value?.quality_panel || {});
const qualityCards = computed(() => [
  { label: "总体准确率", value: `${qualityPanel.value?.overall?.accuracy ?? 0}%`, tip: "岗位画像/学生画像/人岗匹配综合抽样准确率" },
  { label: "总体命中率", value: `${qualityPanel.value?.overall?.hit_rate ?? 0}%`, tip: "关键要点命中率，反映匹配与画像有效性" },
  { label: "总体解释率", value: `${qualityPanel.value?.overall?.explain_rate ?? 0}%`, tip: "结果解释可读率，反映报告和匹配可解释性" },
]);
const qualityRows = computed(() => [
  {
    label: "岗位画像",
    sampleSize: qualityPanel.value?.job_portrait?.sample_size ?? 0,
    accuracy: qualityPanel.value?.job_portrait?.accuracy ?? 0,
    hitRate: qualityPanel.value?.job_portrait?.hit_rate ?? 0,
    explainRate: qualityPanel.value?.job_portrait?.explain_rate ?? 0,
  },
  {
    label: "学生画像",
    sampleSize: qualityPanel.value?.student_portrait?.sample_size ?? 0,
    accuracy: qualityPanel.value?.student_portrait?.accuracy ?? 0,
    hitRate: qualityPanel.value?.student_portrait?.hit_rate ?? 0,
    explainRate: qualityPanel.value?.student_portrait?.explain_rate ?? 0,
  },
  {
    label: "人岗匹配",
    sampleSize: qualityPanel.value?.job_match?.sample_size ?? 0,
    accuracy: qualityPanel.value?.job_match?.accuracy ?? 0,
    hitRate: qualityPanel.value?.job_match?.hit_rate ?? 0,
    explainRate: qualityPanel.value?.job_match?.explain_rate ?? 0,
  },
]);
const filteredAdminAccounts = computed(() => {
  const keyword = adminAccountSearch.value.trim().toLowerCase();
  const rows = adminAccounts.value;
  if (!keyword) return rows;
  return rows.filter((item) =>
    [item.username, item.real_name, item.role_name, item.department, item.classroom]
      .filter(Boolean)
      .some((field) => String(field).toLowerCase().includes(keyword))
  );
});
const selectedAdminAccount = computed(
  () => filteredAdminAccounts.value.find((item) => item.id === selectedAdminAccountId.value) || filteredAdminAccounts.value[0] || null
);
const selectedAdminAccountInspectData = computed(() => {
  const item = selectedAdminAccount.value;
  if (!item) return null;
  return {
    账号: item.username,
    姓名: item.real_name,
    角色: item.role_name,
    启用状态: boolText(item.is_active),
    邮箱: item.email || "未填写",
    电话: item.phone || "未填写",
    院系部门: item.department || "未分配",
    班级: item.classroom || "未分配",
    注册时间: formatDateTime(item.created_at),
  };
});
const filteredAdminEnterprises = computed(() => {
  const keyword = adminEnterpriseSearch.value.trim().toLowerCase();
  const rows = adminEnterprises.value;
  if (!keyword) return rows;
  return rows.filter((item) =>
    [item.company_name, item.industry, item.company_type, item.company_size, item.account_username]
      .filter(Boolean)
      .some((field) => String(field).toLowerCase().includes(keyword))
  );
});
const selectedAdminEnterprise = computed(
  () =>
    filteredAdminEnterprises.value.find((item) => item.id === selectedAdminEnterpriseId.value) ||
    filteredAdminEnterprises.value[0] ||
    null
);
const selectedAdminEnterpriseInspectData = computed(() => {
  const item = selectedAdminEnterprise.value;
  if (!item) return null;
  return {
    企业名称: item.company_name,
    行业: item.industry,
    企业类型: item.company_type || "未标注",
    企业规模: item.company_size || "未标注",
    地址: item.address || "未标注",
    绑定账号: item.account_username || "未绑定",
    账号状态: boolText(item.account_active),
    来源文档数: item.source_doc_count,
    收到投递: item.delivery_count,
    待复评: item.pending_review_count,
    平均匹配度: `${Number(item.avg_match_score || 0).toFixed(1)} 分`,
    最近投递: formatDateTime(item.last_delivery_at),
    建档时间: formatDateTime(item.created_at),
  };
});

const adminMetricCards = computed(() => {
  const counts = adminCenter.value?.counts || {};
  const metrics = crmMetrics.value;
  return [
    { label: "注册账号总数", value: metrics.registered_account_count ?? counts.user_count ?? 0, tip: "系统内全部已注册账号数量" },
    { label: "活跃账号数", value: metrics.active_account_count ?? 0, tip: "当前处于启用状态的账号数量" },
    { label: "企业库总量", value: metrics.enterprise_total_count ?? counts.enterprise_count ?? 0, tip: "数据库中已建立企业档案的企业数量" },
    { label: "活跃企业数", value: metrics.enterprise_with_delivery_count ?? 0, tip: "至少收到过一份投递简历的企业数量" },
  ];
});

const adminServiceStatus = computed(() => {
  const db = adminCenter.value?.business_db || {};
  const vector = adminCenter.value?.vector_db || {};
  const vectorStatus = vector.status || "unknown";
  const vectorLabel = vectorStatus === "online" ? "正常" : vectorStatus === "degraded" ? "降级" : vectorStatus === "error" ? "异常" : "未知";
  return [
    { label: "API 服务", meta: `${adminCenter.value?.runtime?.api_prefix || "/api"} 已挂载`, status: "online", statusLabel: "在线" },
    {
      label: "业务数据库",
      meta: db.message || "等待检测",
      status: db.status || "unknown",
      statusLabel: db.status === "online" ? "正常" : db.status === "offline" ? "异常" : "未知",
    },
    {
      label: "Milvus 知识库",
      meta: vector.message || `${vector.backend || "-"} / ${vector.document_count || 0} 条岗位文档`,
      status: vectorStatus,
      statusLabel: vectorLabel,
    },
    { label: "文件存储", meta: adminCenter.value?.runtime?.upload_dir || "-", status: "online", statusLabel: "可用" },
  ];
});

const vectorStatusLabel = computed(() => {
  const status = adminCenter.value?.vector_db?.status || "unknown";
  if (status === "online") return "正常";
  if (status === "degraded") return "降级运行";
  if (status === "error") return "异常";
  return "未知";
});

const adminRoleBars = computed(() => {
  const rows = crmCharts.value.role_distribution || adminCenter.value?.role_distribution || [];
  const max = Math.max(...rows.map((item) => Number(item.count || 0)), 1);
  return rows.map((item) => ({ ...item, width: `${Math.max((Number(item.count || 0) / max) * 100, 8)}%` }));
});

const adminActionList = computed(() => {
  const items = [
    { title: "巡检业务库与知识库", desc: "确认业务数据库和 Milvus 知识库都在线，避免答辩时链路中断。" },
    { title: "优先演示企业闭环", desc: "从学生投递到企业筛选再到复评，更能体现系统完整性。" },
    { title: "关注账号与企业增长", desc: "查看注册账号趋势与企业接入趋势，突出平台真实运营视角。" },
  ];
  return [...items, ...adminInsights.value.map((item) => ({ title: item.title, desc: item.description }))].slice(0, 4);
});

const adminSizeLabel = computed(() => {
  const value = adminCenter.value?.business_db?.size_mb;
  return value === null || value === undefined ? "-" : `${value} MB`;
});

const adminRoleChartOption = computed(() => ({
  tooltip: {
    trigger: "item",
    backgroundColor: "rgba(255, 255, 255, 0.98)",
    borderColor: "#dbe7f5",
    textStyle: { color: "#1f2d3d" },
  },
  legend: {
    bottom: 0,
    textStyle: { color: "#64748b" },
  },
  series: [
    {
      type: "pie",
      radius: ["42%", "70%"],
      center: ["50%", "44%"],
      itemStyle: {
        borderRadius: 10,
        borderColor: "#ffffff",
        borderWidth: 4,
      },
      label: { color: "#334155", formatter: "{b}\n{d}%" },
      data: adminRoleBars.value.map((item, index) => ({
        name: item.role_name,
        value: item.count,
        itemStyle: {
          color: ["#3b82f6", "#06b6d4", "#10b981", "#f59e0b", "#8b5cf6"][index % 5],
        },
      })),
    },
  ],
}));

const adminAccountGrowthOption = computed(() => ({
  grid: { left: 42, right: 16, top: 28, bottom: 28 },
  tooltip: {
    trigger: "axis",
    backgroundColor: "rgba(255, 255, 255, 0.98)",
    borderColor: "#dbe7f5",
    textStyle: { color: "#1f2d3d" },
  },
  xAxis: {
    type: "category",
    axisLine: { lineStyle: { color: "#d7e1ee" } },
    axisLabel: { color: "#64748b" },
    data: (crmCharts.value.account_growth || []).map((item) => item.label),
  },
  yAxis: {
    type: "value",
    splitLine: { lineStyle: { color: "#eef3f8" } },
    axisLabel: { color: "#64748b" },
  },
  series: [
    {
      type: "line",
      smooth: true,
      symbolSize: 8,
      lineStyle: { width: 3, color: "#3b82f6" },
      areaStyle: { color: "rgba(59, 130, 246, 0.16)" },
      data: (crmCharts.value.account_growth || []).map((item) => item.value),
    },
  ],
}));

const adminEnterpriseGrowthOption = computed(() => ({
  grid: { left: 42, right: 16, top: 28, bottom: 28 },
  tooltip: {
    trigger: "axis",
    backgroundColor: "rgba(255, 255, 255, 0.98)",
    borderColor: "#dbe7f5",
    textStyle: { color: "#1f2d3d" },
  },
  xAxis: {
    type: "category",
    axisLine: { lineStyle: { color: "#d7e1ee" } },
    axisLabel: { color: "#64748b" },
    data: (crmCharts.value.enterprise_growth || []).map((item) => item.label),
  },
  yAxis: {
    type: "value",
    splitLine: { lineStyle: { color: "#eef3f8" } },
    axisLabel: { color: "#64748b" },
  },
  series: [
    {
      type: "bar",
      barWidth: 26,
      itemStyle: { borderRadius: [10, 10, 0, 0], color: "#06b6d4" },
      data: (crmCharts.value.enterprise_growth || []).map((item) => item.value),
    },
  ],
}));

const adminIndustryPieOption = computed(() => ({
  tooltip: {
    trigger: "item",
    backgroundColor: "rgba(255, 255, 255, 0.98)",
    borderColor: "#dbe7f5",
    textStyle: { color: "#1f2d3d" },
  },
  legend: {
    bottom: 0,
    textStyle: { color: "#64748b" },
  },
  series: [
    {
      type: "pie",
      radius: ["38%", "68%"],
      center: ["50%", "44%"],
      itemStyle: {
        borderRadius: 8,
        borderColor: "#ffffff",
        borderWidth: 4,
      },
      label: { color: "#334155", formatter: "{b}\n{d}%" },
      data: (crmCharts.value.enterprise_industry_distribution || []).map((item, index) => ({
        name: item.name,
        value: item.value,
        itemStyle: {
          color: ["#10b981", "#3b82f6", "#f59e0b", "#8b5cf6", "#ef4444", "#14b8a6"][index % 6],
        },
      })),
    },
  ],
}));

const adminEnterpriseRankOption = computed(() => ({
  grid: { left: 92, right: 20, top: 24, bottom: 20 },
  tooltip: {
    trigger: "axis",
    axisPointer: { type: "shadow" },
    backgroundColor: "rgba(255, 255, 255, 0.98)",
    borderColor: "#dbe7f5",
    textStyle: { color: "#1f2d3d" },
  },
  xAxis: {
    type: "value",
    splitLine: { lineStyle: { color: "#eef3f8" } },
    axisLabel: { color: "#64748b" },
  },
  yAxis: {
    type: "category",
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: "#64748b" },
    data: (crmCharts.value.enterprise_delivery_rank || []).map((item) => item.name),
  },
  series: [
    {
      type: "bar",
      barWidth: 16,
      itemStyle: { borderRadius: 999, color: "#10b981" },
      data: (crmCharts.value.enterprise_delivery_rank || []).map((item) => item.value),
    },
  ],
}));

const enterpriseMetricCards = computed(() => {
  const metrics = enterpriseBoard.value?.metrics || {};
  return [
    { label: "全部投递", value: metrics.delivery_count || 0, tip: "进入企业人才池的全部简历" },
    { label: "高匹配候选人", value: metrics.high_match_count || 0, tip: "匹配度 70 分及以上的候选人" },
    { label: "待复评", value: metrics.pending_review_count || 0, tip: "还未填写企业复评的候选人" },
    { label: "最佳匹配", value: `${metrics.best_match_score || 0}%`, tip: "当前企业端最高匹配度" },
  ];
});

const filteredEnterpriseDeliveries = computed(() => {
  const keyword = candidateSearch.value.trim().toLowerCase();
  let rows = enterpriseDeliveries.value || [];
  if (enterpriseFilter.value === "high") rows = rows.filter((item) => Number(item.match_score || 0) >= 70);
  if (enterpriseFilter.value === "pending") rows = rows.filter((item) => !item.enterprise_feedback);
  if (!keyword) return rows;
  return rows.filter((item) =>
    [
      item.student?.name,
      item.student?.major,
      item.target_job_name,
      item.target_job_category,
      item.company_name,
    ]
      .filter(Boolean)
      .some((field) => String(field).toLowerCase().includes(keyword))
  );
});

const selectedEnterpriseDelivery = computed(() => {
  return enterpriseDeliveries.value.find((item) => item.id === selectedDeliveryId.value) || enterpriseDeliveries.value[0] || null;
});

const previewableResumeUrl = computed(() => {
  const attachment = selectedEnterpriseDelivery.value?.attachment;
  if (!attachment?.file_path) return "";
  const type = (attachment.file_type || "").toLowerCase();
  return ["pdf", "png", "jpg", "jpeg", "webp", "bmp"].includes(type) ? `${fileBase}${attachment.file_path}` : "";
});
const selectedEnterpriseDeliveryInspectData = computed(() => {
  const item = selectedEnterpriseDelivery.value;
  if (!item) return null;
  return {
    学生姓名: item.student?.name || "-",
    专业: item.student?.major || "-",
    学院: item.student?.college || "-",
    电话: item.student?.phone || "-",
    邮箱: item.student?.email || "-",
    投递岗位: item.target_job_name || "-",
    岗位类别: item.target_job_category || "-",
    匹配度: `${Math.round(item.match_score || 0)}%`,
    企业: item.company_name || "-",
    投递时间: formatDateTime(item.created_at),
    复评状态: item.enterprise_feedback ? "已复评" : "待复评",
    简历文件: item.attachment?.file_name || "-",
  };
});

const enterpriseMajorMax = computed(() => {
  const rows = enterpriseBoard.value?.major_distribution || [];
  return Math.max(...rows.map((item) => Number(item.value || 0)), 1);
});

const studentTopMatches = computed(() => (studentMatches.value || []).slice(0, 6));
const studentMetricCards = computed(() => [
  { label: "匹配线索", value: studentMatches.value.length, tip: "当前已生成的人岗匹配结果数量" },
  { label: "路径状态", value: studentPath.value ? "已生成" : "待生成", tip: "生成后会形成阶段任务与推进节奏" },
  { label: "图谱入口", value: "已开放", tip: "岗位图谱中心支持筛选、缩放和关系查看" },
  { label: "成熟度", value: studentProfile.value?.maturity_level || "待评估", tip: "来自六维画像、成长记录和执行情况综合判断" },
]);

const studentQuickActions = computed(() => [
  { title: "更新学生档案", desc: "完善基础信息、技能和简历资料。", path: "/student/base" },
  { title: "查看画像分析", desc: "进入综合图谱分析页查看能力结构。", path: "/profile/radar" },
  { title: "推进成长路径", desc: "查看当前成长路径和阶段任务。", path: "/career/path" },
  { title: "岗位图谱中心", desc: "查看岗位之间的技能关联与发展路径。", path: "/student/job-graph" },
]);

const studentProfileSnapshot = computed(() => {
  const profile = studentProfile.value;
  if (!profile) return [];
  return [
    { label: "专业能力", value: Math.round(profile.professional_score || 0) },
    { label: "实践能力", value: Math.round(profile.practice_score || 0) },
    { label: "沟通协作", value: Math.round(profile.communication_score || 0) },
    { label: "学习成长", value: Math.round(profile.learning_score || 0) },
    { label: "创新能力", value: Math.round(profile.innovation_score || 0) },
    { label: "职业素养", value: Math.round(profile.professionalism_score || 0) },
  ];
});

const studentStory = computed(() => {
  const top = studentTopMatches.value[0];
  return top
    ? `当前建议把“${top.job?.name || "目标岗位"}”作为唯一主攻方向，围绕差距项拆成学习任务、项目证据、简历表达和投递准备四条线同步推进。`
    : "先完成学生画像与匹配生成，系统会自动收敛出最适合优先冲刺的岗位方向，再继续推进路径、图谱、简历和投递。";
});

const studentActionList = computed(() => [
  { title: "先锁定一个主攻岗位", desc: "避免同时推进多个方向，优先围绕当前最高匹配岗位展开准备。" },
  { title: "把差距项拆成周任务", desc: "围绕技能、项目、实习和证书补齐可展示的岗位证据。" },
  { title: "同步更新简历与投递材料", desc: "阶段成果回写后，及时刷新简历、项目证据和投递材料。" },
]);

const loadAdminDashboard = async () => {
  const res = await adminApi.controlCenter();
  adminCenter.value = res.data || null;
};

const loadEnterpriseDashboard = async () => {
  const [boardRes, deliveriesRes] = await Promise.all([enterpriseApi.dashboard(), enterpriseApi.deliveries()]);
  enterpriseBoard.value = boardRes.data || null;
  enterpriseDeliveries.value = deliveriesRes.data || [];
  if (!selectedDeliveryId.value && enterpriseDeliveries.value.length) selectedDeliveryId.value = enterpriseDeliveries.value[0].id;
};

const loadStudentDashboard = async () => {
  const results = await Promise.allSettled([studentApi.getMatches(), studentApi.getProfile(), studentApi.getPath()]);
  studentMatches.value = results[0].status === "fulfilled" ? results[0].value.data || [] : [];
  studentProfile.value = results[1].status === "fulfilled" ? results[1].value.data || null : null;
  studentPath.value = results[2].status === "fulfilled" ? results[2].value.data || null : null;
};

const selectEnterpriseDelivery = (item) => { selectedDeliveryId.value = item.id; };
const openResume = (row) => {
  const path = row?.attachment?.file_path;
  if (!path) return ElMessage.warning("当前记录缺少可打开的简历文件");
  window.open(`${fileBase}${path}`, "_blank");
};
const openSource = (row) => {
  if (!row?.source_url) return ElMessage.info("当前记录没有岗位来源链接");
  window.open(row.source_url, "_blank");
};
const formatDate = (value) => {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("zh-CN");
};
const formatDateTime = (value) => {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
};
const boolText = (value) => (value ? "启用" : "停用");
const calcWidth = (value, max) => `${Math.max((Number(value || 0) / Math.max(max || 1, 1)) * 100, 8)}%`;
const matchActionText = (row) => {
  const score = Number(row.total_score || 0);
  if (score >= 80) return "优先完善简历并开始集中投递";
  if (score >= 60) return "继续补齐关键技能和项目证据";
  return "先生成成长任务，再围绕差距项补能力";
};

onMounted(async () => {
  if (role.value === "admin") return loadAdminDashboard();
  if (role.value === "enterprise") return;
  return loadStudentDashboard();
});
</script>

<style scoped>
.dashboard-root { gap: 18px; }
.hero { display: grid; grid-template-columns: 1.25fr 0.75fr; gap: 18px; padding: 28px 30px; border-radius: 30px; }
.hero-eyebrow { display: inline-flex; padding: 8px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; letter-spacing: 0.08em; }
.hero-title { margin: 14px 0 0; font-size: 38px; line-height: 1.16; }
.hero-desc { margin: 12px 0 0; max-width: 760px; line-height: 1.85; }
.hero-tags, .filter-group, .toolbar-actions, .candidate-tags, .detail-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.hero-tags { margin-top: 18px; }
.hero-tag, .filter-chip { padding: 10px 14px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.hero-side-card { padding: 22px; border-radius: 24px; display: flex; flex-direction: column; justify-content: center; }
.hero-side-label { font-size: 12px; letter-spacing: 0.08em; }
.hero-side-value { margin-top: 12px; font-size: 30px; font-weight: 800; }
.hero-side-meta { margin-top: 10px; line-height: 1.8; }
.metric-card { padding: 20px; border-radius: 22px; border: 1px solid transparent; }
.metric-card-label { font-size: 13px; }
.metric-card-value { margin-top: 10px; font-size: 30px; font-weight: 800; }
.metric-card-tip { margin-top: 8px; font-size: 12px; line-height: 1.7; }
.status-list, .info-list, .role-bars, .distribution-list, .focus-list { display: grid; gap: 14px; }
.status-item, .focus-item, .action-card { display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 14px 16px; border-radius: 18px; }
.status-label, .action-title, .focus-name, .detail-block-title, .candidate-name, .candidate-large-name, .student-story-title { font-weight: 700; }
.status-meta, .action-desc, .focus-meta, .candidate-meta, .candidate-summary, .candidate-large-meta, .detail-block p, .student-story p { margin-top: 6px; line-height: 1.75; }
.status-pill { padding: 8px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.status-pill.online { background: rgba(16, 185, 129, 0.14); color: #22c55e; }
.status-pill.degraded { background: rgba(245, 158, 11, 0.16); color: #b45309; }
.status-pill.error { background: rgba(239, 68, 68, 0.14); color: #dc2626; }
.status-pill.offline { background: rgba(239, 68, 68, 0.14); color: #ef4444; }
.status-pill.unknown { background: rgba(148, 163, 184, 0.14); color: #94a3b8; }
.vector-status-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.info-row, .detail-grid.compact div, .role-bar-top, .distribution-top { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.info-row span, .detail-grid.compact span, .role-bar-top span, .distribution-top span, .snapshot-label { font-size: 12px; }
.info-row strong, .detail-grid.compact strong, .distribution-top strong, .role-bar-top strong { text-align: right; }
.highlight-grid, .snapshot-grid, .story-steps, .student-shortcuts { display: grid; gap: 14px; }
.highlight-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.highlight-card, .snapshot-card, .story-step, .shortcut-card { padding: 16px; border-radius: 20px; }
.highlight-title, .snapshot-value, .story-step-title { font-weight: 700; }
.highlight-value { margin-top: 10px; font-size: 26px; font-weight: 800; }
.highlight-desc, .snapshot-label, .story-step-desc { margin-top: 8px; line-height: 1.75; }
.role-bar-track, .distribution-track { margin-top: 8px; height: 8px; border-radius: 999px; overflow: hidden; }
.role-bar-track span, .distribution-track span { display: block; height: 100%; border-radius: inherit; }
.enterprise-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.filter-chip { border: none; cursor: pointer; color: #365550; }
.filter-chip.active { font-weight: 700; }
.enterprise-board-grid { display: grid; grid-template-columns: 0.92fr 1.08fr; gap: 18px; align-items: start; }
.candidate-list-card { align-self: start; }
.candidate-list-card :deep(.el-card__body) { display: grid; gap: 12px; }
.candidate-list { display: grid; gap: 12px; max-height: clamp(320px, 52vh, 540px); overflow: auto; align-content: start; padding-right: 4px; }
.candidate-item { width: 100%; border: none; text-align: left; padding: 14px; border-radius: 20px; cursor: pointer; }
.candidate-top, .candidate-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.candidate-score { font-size: 24px; font-weight: 800; }
.candidate-detail-column, .candidate-overview, .student-story { display: grid; gap: 16px; }
.score-ring { min-width: 126px; min-height: 126px; border-radius: 999px; display: grid; place-items: center; text-align: center; }
.score-ring-value { font-size: 28px; font-weight: 800; }
.score-ring-label { margin-top: 4px; font-size: 12px; }
.detail-grid.compact { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 16px; }
.detail-block { padding: 16px; border-radius: 18px; }
.resume-preview-frame { width: 100%; min-height: 620px; border: none; border-radius: 18px; background: #f3f7f4; }
.resume-preview-empty { min-height: 240px; display: grid; place-items: center; text-align: center; gap: 14px; }
.snapshot-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.snapshot-value { margin-top: 10px; font-size: 24px; }
.dark-block { margin-top: 12px; }
.inspector-shell {
  display: grid;
  grid-template-columns: 0.92fr 1.08fr;
  gap: 16px;
  min-height: 0;
  height: auto;
  max-height: clamp(420px, calc(100vh - 260px), 640px);
}
.inspector-sidebar, .inspector-detail-panel { display: flex; flex-direction: column; gap: 14px; min-height: 0; }
.inspector-list { flex: 1; min-height: 0; display: grid; gap: 10px; overflow: auto; align-content: start; padding-right: 4px; }
.inspector-detail-body { flex: 1; min-height: 0; overflow: auto; padding-right: 4px; }
.inspector-item { width: 100%; border: 1px solid #d8e2f0; text-align: left; padding: 14px; border-radius: 18px; cursor: pointer; background: linear-gradient(180deg, #ffffff, #f8fbff); color: inherit; }
.inspector-item.active { box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08); border-color: #bfd4f5; background: linear-gradient(180deg, #f7fbff, #edf4ff); }
.inspector-item-top { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.inspector-badge { padding: 6px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; background: #e8efff; color: #1d4ed8; }
.inspector-item-meta, .inspector-item-desc, .detail-subheading { margin-top: 8px; font-size: 12px; line-height: 1.7; color: #64748b; }
.inspector-detail-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.detail-heading { font-size: 22px; font-weight: 800; color: #0f172a; }

.admin-hero { background: linear-gradient(135deg, #ffffff, #f5f9ff); border: 1px solid #d9e3f1; box-shadow: 0 14px 30px rgba(15, 23, 42, 0.08); }
.admin-hero .hero-eyebrow, .admin-side-card, .metric-card-admin, .highlight-card, .action-card { background: linear-gradient(180deg, #ffffff, #f8fbff); border: 1px solid #d9e3f1; }
.admin-hero .hero-eyebrow, .admin-hero .hero-tag, .metric-card-admin .metric-card-label, .metric-card-admin .metric-card-tip, .highlight-desc, .info-row span, .status-meta, .role-bar-top span, .action-desc { color: #64748b; }
.admin-hero .hero-title, .admin-hero .hero-side-value, .metric-card-admin .metric-card-value, .highlight-value, .info-row strong, .role-bar-top strong, .action-title { color: #0f172a; }
.admin-hero .hero-desc, .admin-hero .hero-side-meta, .highlight-title { color: #475569; }
.admin-hero .hero-tag, .admin-hero .hero-side-label { background: #e8efff; color: #1d4ed8; }
.admin-status-grid :deep(.section-card), .admin-main-grid :deep(.section-card) { min-height: 100%; }
.admin-chart-grid :deep(.section-card) { min-height: 100%; }
.admin-crm-grid :deep(.section-card) { min-height: 0; }
.admin-crm-grid :deep(.el-card__body) { display: flex; flex-direction: column; min-height: 0; }
.role-bar-track { background: #e8eef8; }
.role-bar-track span { background: linear-gradient(90deg, #2563eb, #1d4ed8); }

.enterprise-hero { background: linear-gradient(135deg, rgba(251, 253, 251, 0.96), rgba(241, 246, 243, 0.94)); border: 1px solid rgba(15, 118, 110, 0.1); box-shadow: 0 16px 34px rgba(15, 23, 42, 0.045); }
.enterprise-hero .hero-eyebrow, .enterprise-side-card, .metric-card-enterprise, .candidate-item, .focus-item, .detail-block, .filter-chip, .distribution-item { background: linear-gradient(180deg, rgba(246, 250, 247, 0.94), rgba(241, 246, 243, 0.96)); border: 1px solid rgba(15, 118, 110, 0.1); }
.enterprise-hero .hero-eyebrow, .enterprise-hero .hero-tag, .metric-card-enterprise .metric-card-label, .metric-card-enterprise .metric-card-tip, .candidate-meta, .candidate-summary, .candidate-tags span, .detail-block p, .resume-preview-empty p, .distribution-top span { color: #607773; }
.enterprise-hero .hero-title, .enterprise-hero .hero-side-value, .metric-card-enterprise .metric-card-value, .candidate-name, .candidate-large-name, .candidate-score, .score-ring-value, .detail-grid.compact strong, .focus-name, .distribution-top strong { color: #173733; }
.enterprise-hero .hero-desc, .enterprise-hero .hero-side-meta, .candidate-large-meta, .score-ring-label { color: #4f6661; }
.enterprise-hero .hero-tag, .enterprise-hero .hero-side-label { background: #eef6f1; }
.filter-chip.active, .candidate-item.active { background: linear-gradient(135deg, rgba(15, 118, 110, 0.12), rgba(16, 185, 129, 0.06)); color: #163230; box-shadow: 0 12px 24px rgba(15, 23, 42, 0.05); }
.score-ring { background: radial-gradient(circle at 30% 30%, rgba(16, 185, 129, 0.12), rgba(15, 118, 110, 0.05)); border: 1px solid rgba(15, 118, 110, 0.1); }
.distribution-track { background: #e4eee9; }
.distribution-track span { background: linear-gradient(90deg, #0f766e, #10b981); }
.dashboard-enterprise .inspector-item { background: linear-gradient(180deg, rgba(246, 250, 247, 0.94), rgba(241, 246, 243, 0.96)); border-color: rgba(15, 118, 110, 0.1); }
.dashboard-enterprise .inspector-item.active { background: linear-gradient(135deg, rgba(15, 118, 110, 0.12), rgba(16, 185, 129, 0.06)); }
.dashboard-enterprise .inspector-badge { background: rgba(15, 118, 110, 0.1); color: #0f5d57; }
.dashboard-enterprise .inspector-item-meta, .dashboard-enterprise .inspector-item-desc, .dashboard-enterprise .detail-subheading { color: #5b726d; }
.dashboard-enterprise .detail-heading { color: #173733; }

.student-hero { background: linear-gradient(135deg, #ffffff, #f5f9ff); border: 1px solid #d9e3f1; box-shadow: 0 14px 30px rgba(15, 23, 42, 0.08); }
.student-hero .hero-eyebrow, .student-side-card, .metric-card-student, .snapshot-card, .story-step, .dark-block, .shortcut-card { background: linear-gradient(180deg, #ffffff, #f8fbff); border: 1px solid #d9e3f1; }
.student-hero .hero-eyebrow, .student-hero .hero-tag, .metric-card-student .metric-card-label, .metric-card-student .metric-card-tip, .snapshot-label, .story-step-desc, .student-story p, .dark-block p, .shortcut-desc { color: #64748b; }
.student-hero .hero-title, .student-hero .hero-side-value, .metric-card-student .metric-card-value, .student-story-title, .snapshot-value, .story-step-title, .shortcut-title { color: #0f172a; }
.student-hero .hero-desc, .student-hero .hero-side-meta { color: #475569; }
.student-hero .hero-tag, .student-hero .hero-side-label { background: #e8efff; color: #1d4ed8; }
.student-main-grid :deep(.section-card), .student-table { background: #fff; }
.student-shortcuts { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.shortcut-card { border: none; text-align: left; cursor: pointer; transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease; }
.shortcut-card:hover { transform: translateY(-2px); border-color: #bfd4f5; box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08); }
.shortcut-title { font-size: 16px; }
.shortcut-desc { margin-top: 8px; line-height: 1.75; }

@media (max-width: 1200px) {
  .enterprise-board-grid, .hero, .two-col, .three-col, .highlight-grid, .snapshot-grid, .inspector-shell, .student-shortcuts { grid-template-columns: 1fr; }
  .inspector-shell { max-height: none; }
}

@media (max-width: 840px) {
  .enterprise-toolbar, .candidate-header { flex-direction: column; align-items: stretch; }
  .detail-grid.compact { grid-template-columns: 1fr; }
}
</style>
