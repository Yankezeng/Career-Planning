<template>
  <div class="hrm-root">
    <section class="hrm-hero">
      <div>
        <div class="hero-eyebrow">Enterprise HRM Console</div>
        <h1 class="hero-title">企业人力资源工作台</h1>
        <p class="hero-desc">把候选人筛选、岗位分布、技能热区和跟进建议集中在一个企业端工作台里，减少来回切页。</p>
        <div class="hero-tags">
          <span class="hero-tag">候选人池 {{ board?.metrics?.delivery_count || 0 }}</span>
          <span class="hero-tag">建议约面 {{ board?.metrics?.interview_ready_count || 0 }}</span>
          <span class="hero-tag">待跟进 {{ board?.metrics?.pending_review_count || 0 }}</span>
          <span class="hero-tag">平均匹配 {{ board?.metrics?.average_match_score || 0 }}%</span>
        </div>
      </div>

      <div class="priority-card">
        <div class="priority-kicker">当前优先动作</div>
        <div class="priority-title">{{ board?.hrm_actions?.[0]?.title || "优先筛选高匹配候选人" }}</div>
        <p class="priority-desc">{{ board?.hrm_actions?.[0]?.description || "建议先处理建议约面和重点跟进候选人。" }}</p>
        <div class="priority-stats">
          <div class="priority-stat">
            <span>已跟进</span>
            <strong>{{ board?.metrics?.reviewed_count || 0 }}</strong>
          </div>
          <div class="priority-stat">
            <span>储备人才</span>
            <strong>{{ board?.metrics?.reserve_count || 0 }}</strong>
          </div>
        </div>
      </div>
    </section>

    <div class="metric-grid">
      <div v-for="card in metricCards" :key="card.label" class="metric-card">
        <div class="metric-label">{{ card.label }}</div>
        <div class="metric-value">{{ card.value }}</div>
        <div class="metric-tip">{{ card.tip }}</div>
      </div>
    </div>

    <div class="toolbar">
      <div class="filter-group">
        <button
          v-for="item in filters"
          :key="item.value"
          type="button"
          :class="['filter-chip', { active: activeFilter === item.value }]"
          @click="activeFilter = item.value"
        >
          {{ item.label }}
        </button>
      </div>

      <div class="toolbar-actions">
        <el-button @click="router.push('/jobs')">查看岗位知识库</el-button>
        <el-button type="primary" @click="loadData">刷新 HRM 数据</el-button>
      </div>
    </div>

    <div class="top-grid">
      <SectionCard title="招聘漏斗">
        <AnalysisChart :option="pipelineChartOption" height="320px" />
      </SectionCard>

      <SectionCard title="岗位需求分布">
        <AnalysisChart :option="jobChartOption" height="320px" />
      </SectionCard>

      <SectionCard title="候选人技能热区">
        <AnalysisChart :option="skillChartOption" height="320px" />
      </SectionCard>
    </div>

    <div class="main-grid">
      <SectionCard title="候选人池" class="candidate-panel">
        <InspectorSearchBar
          v-model="candidateSearch"
          placeholder="搜索候选人 / 专业 / 岗位 / 技能"
          hint="TalentPool"
          :count="filteredDeliveries.length"
        />

        <div class="candidate-list">
          <button
            v-for="item in filteredDeliveries"
            :key="item.id"
            type="button"
            :class="['candidate-item', { active: selectedDelivery?.id === item.id }]"
            @click="selectedDeliveryId = item.id"
          >
            <div class="candidate-item-top">
              <div>
                <div class="candidate-name">{{ item.student?.name || '未命名候选人' }}</div>
                <div class="candidate-meta">{{ item.student?.major || '未标注专业' }} · {{ item.target_job_name || '未标注岗位' }}</div>
              </div>
              <div class="candidate-score">{{ Math.round(item.match_score || 0) }}%</div>
            </div>

            <div class="candidate-summary">
              {{ item.student?.profile_summary || item.delivery_note || '暂未生成画像摘要，建议先查看简历和结构化信息。' }}
            </div>

            <div class="candidate-tags">
              <span>{{ item.pipeline_stage_label || '待筛选' }}</span>
              <span>{{ item.student?.project_count || 0 }} 个项目</span>
              <span>{{ item.student?.internship_count || 0 }} 段实习</span>
            </div>
          </button>

          <el-empty v-if="!filteredDeliveries.length" description="当前筛选条件下暂无候选人" />
        </div>
      </SectionCard>

      <div class="detail-column">
        <SectionCard title="候选人画像详情流" class="detail-stream-card">
          <template v-if="selectedDelivery">
            <div class="portrait-stream">
              <article class="stream-card span-12 stream-summary">
                <div class="candidate-head">
                  <div>
                    <div class="candidate-large-name">{{ selectedDelivery.student?.name || "-" }}</div>
                    <div class="candidate-large-meta">{{ selectedDelivery.student?.major || "-" }} · {{ selectedDelivery.student?.college || "-" }}</div>
                  </div>
                  <div class="score-badge">
                    <div class="score-badge-value">{{ Math.round(selectedDelivery.match_score || 0) }}%</div>
                    <div class="score-badge-label">岗位匹配度</div>
                  </div>
                </div>
                <div class="chip-group">
                  <span class="soft-chip">{{ selectedDelivery.pipeline_stage_label || "待筛选" }}</span>
                  <span class="soft-chip">目标：{{ selectedDelivery.target_job_name || "-" }}</span>
                  <span class="soft-chip">证据：{{ selectedDelivery.student?.evidence_score || 0 }}</span>
                </div>
              </article>

              <article class="stream-card span-4"><span class="stream-k">目标岗位</span><strong class="stream-v">{{ selectedDelivery.target_job_name || "-" }}</strong></article>
              <article class="stream-card span-4"><span class="stream-k">当前阶段</span><strong class="stream-v">{{ selectedDelivery.pipeline_stage_label || "-" }}</strong></article>
              <article class="stream-card span-4"><span class="stream-k">联系方式</span><strong class="stream-v">{{ selectedDelivery.student?.phone || "-" }}</strong></article>
              <article class="stream-card span-4"><span class="stream-k">项目经历</span><strong class="stream-v">{{ selectedDelivery.student?.project_count || 0 }}</strong></article>
              <article class="stream-card span-4"><span class="stream-k">实习经历</span><strong class="stream-v">{{ selectedDelivery.student?.internship_count || 0 }}</strong></article>
              <article class="stream-card span-4"><span class="stream-k">投递时间</span><strong class="stream-v">{{ formatDateTime(selectedDelivery.created_at) }}</strong></article>

              <article class="stream-card span-12">
                <div class="block-title">画像摘要</div>
                <p>{{ selectedDelivery.student?.profile_summary || "暂无画像摘要。" }}</p>
                <span v-for="tag in selectedDelivery.student?.ability_tags || []" :key="tag" class="soft-chip">{{ tag }}</span>
                <span v-if="!(selectedDelivery.student?.ability_tags || []).length" class="soft-chip muted">暂无能力标签</span>
              </article>

              <article class="stream-card span-6">
                <div class="mini-title">优势项</div>
                <div class="mini-list">
                  <span v-for="item in selectedDelivery.student?.strengths || []" :key="item" class="mini-chip">{{ item }}</span>
                  <span v-if="!(selectedDelivery.student?.strengths || []).length" class="mini-chip muted">暂无优势项</span>
                </div>
              </article>

              <article class="stream-card span-6">
                <div class="mini-title">关键技能</div>
                <div class="mini-list">
                  <span v-for="item in selectedDelivery.student?.skill_tags || []" :key="item" class="mini-chip">{{ item }}</span>
                  <span v-if="!(selectedDelivery.student?.skill_tags || []).length" class="mini-chip muted">暂无技能标签</span>
                </div>
              </article>

              <article class="stream-card span-12">
                <div class="mini-title">结构化详情</div>
                <KeyValueInspector :data="selectedDeliveryInspectData" empty-text="请选择左侧候选人后查看结构化详情" />
              </article>

              <article class="stream-card span-12 stream-actions">
                <el-button type="primary" @click="openResume(selectedDelivery)">查看简历</el-button>
                <el-button @click="openSource(selectedDelivery)">岗位来源</el-button>
              </article>
            </div>
          </template>
          <el-empty v-else description="请先从左侧选择一位候选人" />
        </SectionCard>
      </div>
    </div>

    <div class="bottom-grid">
      <SectionCard title="跟进待办清单">
        <div class="review-list">
          <div v-for="item in board?.review_queue || []" :key="item.id" class="review-item">
            <div>
              <div class="review-name">{{ item.student_name }}</div>
              <div class="review-meta">{{ item.major }} · {{ item.target_job_name }}</div>
              <div class="review-summary">{{ item.summary }}</div>
            </div>
            <div class="review-side">
              <strong>{{ Math.round(item.match_score || 0) }}%</strong>
              <span>证据 {{ item.evidence_score || 0 }}</span>
            </div>
          </div>
          <el-empty v-if="!(board?.review_queue || []).length" description="当前没有待处理的跟进任务" />
        </div>
      </SectionCard>

      <SectionCard title="HRM 管理建议">
        <div class="action-list">
          <div v-for="item in board?.hrm_actions || []" :key="item.title" class="action-item">
            <div class="action-title">{{ item.title }}</div>
            <div class="action-desc">{{ item.description }}</div>
          </div>
        </div>
      </SectionCard>
    </div>

    <div class="bottom-grid">
      <SectionCard title="人才分层分析">
        <AnalysisChart :option="matchSegmentChartOption" height="320px" />
      </SectionCard>

      <SectionCard title="近 7 日投递走势">
        <AnalysisChart :option="trendChartOption" height="320px" />
      </SectionCard>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { enterpriseApi } from '@/api';
import AnalysisChart from '@/components/AnalysisChart.vue';
import InspectorSearchBar from '@/components/InspectorSearchBar.vue';
import KeyValueInspector from '@/components/KeyValueInspector.vue';
import SectionCard from '@/components/SectionCard.vue';

const router = useRouter();
const fileBase = 'http://127.0.0.1:8000';

const board = ref(null);
const deliveries = ref([]);
const candidateSearch = ref('');
const selectedDeliveryId = ref(null);
const activeFilter = ref('all');

const filters = [
  { label: '全部候选人', value: 'all' },
  { label: '建议约面', value: 'interview' },
  { label: '重点跟进', value: 'priority' },
  { label: '待跟进', value: 'pending' },
];

const metricCards = computed(() => {
  const metrics = board.value?.metrics || {};
  return [
    { label: '候选人总量', value: metrics.delivery_count || 0, tip: '当前进入企业人才池的全部简历数量。' },
    { label: '高匹配候选人', value: metrics.high_match_count || 0, tip: '匹配度 70 分及以上的候选人数量。' },
    { label: '建议约面', value: metrics.interview_ready_count || 0, tip: '当前适合优先约面的候选人数量。' },
    { label: '待跟进', value: metrics.pending_review_count || 0, tip: '还没有补充企业反馈的候选人数量。' },
    { label: '平均匹配度', value: `${metrics.average_match_score || 0}%`, tip: '当前候选人池的平均岗位匹配度。' },
    { label: '最佳匹配', value: `${metrics.best_match_score || 0}%`, tip: '当前候选人池里的最高匹配结果。' },
  ];
});

const filteredDeliveries = computed(() => {
  let rows = deliveries.value || [];
  if (activeFilter.value === 'interview') rows = rows.filter((item) => item.pipeline_stage === 'interview');
  if (activeFilter.value === 'priority') rows = rows.filter((item) => item.pipeline_stage === 'priority');
  if (activeFilter.value === 'pending') rows = rows.filter((item) => !item.enterprise_feedback);
  const keyword = candidateSearch.value.trim().toLowerCase();
  if (!keyword) return rows;
  return rows.filter((item) =>
    [
      item.student?.name,
      item.student?.major,
      item.target_job_name,
      item.target_job_category,
      ...(item.student?.skill_tags || []),
    ]
      .filter(Boolean)
      .some((field) => String(field).toLowerCase().includes(keyword)),
  );
});

const selectedDelivery = computed(() => {
  return deliveries.value.find((item) => item.id === selectedDeliveryId.value) || filteredDeliveries.value[0] || deliveries.value[0] || null;
});

const selectedDeliveryInspectData = computed(() => {
  const item = selectedDelivery.value;
  if (!item) return null;
  return {
    学生姓名: item.student?.name || '-',
    学号: item.student?.student_no || '-',
    专业: item.student?.major || '-',
    学院: item.student?.college || '-',
    投递岗位: item.target_job_name || '-',
    岗位类别: item.target_job_category || '-',
    招聘阶段: item.pipeline_stage_label || '-',
    匹配度: `${Math.round(item.match_score || 0)}%`,
    证据强度: item.student?.evidence_score || 0,
    技能标签: (item.student?.skill_tags || []).join(' / ') || '暂无',
    证书标签: (item.student?.certificate_tags || []).join(' / ') || '暂无',
    联系电话: item.student?.phone || '-',
    联系邮箱: item.student?.email || '-',
    投递时间: formatDateTime(item.created_at),
  };
});

const pipelineChartOption = computed(() => ({
  color: ['#24544d'],
  tooltip: { trigger: 'item' },
  xAxis: {
    type: 'category',
    data: (board.value?.pipeline_overview || []).map((item) => item.name),
    axisLabel: { color: '#5d7a74', interval: 0 },
    axisLine: { lineStyle: { color: '#c9ddd4' } },
  },
  yAxis: {
    type: 'value',
    axisLabel: { color: '#5d7a74' },
    splitLine: { lineStyle: { color: '#deece6' } },
  },
  grid: { left: 42, right: 16, top: 24, bottom: 40 },
  series: [
    {
      type: 'bar',
      barWidth: 28,
      itemStyle: { borderRadius: [10, 10, 0, 0] },
      data: (board.value?.pipeline_overview || []).map((item) => item.value),
    },
  ],
}));

const jobChartOption = computed(() => ({
  color: ['#5d7a74'],
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: {
    type: 'value',
    axisLabel: { color: '#5d7a74' },
    splitLine: { lineStyle: { color: '#deece6' } },
  },
  yAxis: {
    type: 'category',
    data: (board.value?.job_distribution || []).map((item) => item.name),
    axisLabel: { color: '#5d7a74' },
    axisLine: { show: false },
    axisTick: { show: false },
  },
  grid: { left: 110, right: 18, top: 20, bottom: 18 },
  series: [
    {
      type: 'bar',
      barWidth: 16,
      itemStyle: { borderRadius: 999 },
      data: (board.value?.job_distribution || []).map((item) => item.value),
    },
  ],
}));

const skillChartOption = computed(() => ({
  color: ['#24544d'],
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: {
    type: 'value',
    axisLabel: { color: '#5d7a74' },
    splitLine: { lineStyle: { color: '#deece6' } },
  },
  yAxis: {
    type: 'category',
    data: (board.value?.skill_distribution || []).map((item) => item.name).reverse(),
    axisLabel: { color: '#5d7a74' },
    axisLine: { show: false },
    axisTick: { show: false },
  },
  grid: { left: 92, right: 18, top: 20, bottom: 18 },
  series: [
    {
      type: 'bar',
      barWidth: 14,
      itemStyle: { borderRadius: 999 },
      data: (board.value?.skill_distribution || []).map((item) => item.value).reverse(),
    },
  ],
}));

const matchSegmentChartOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0, textStyle: { color: '#5d7a74' } },
  series: [
    {
      type: 'pie',
      radius: ['42%', '72%'],
      center: ['50%', '44%'],
      label: { color: '#24544d', formatter: '{b}\n{d}%' },
      itemStyle: { borderRadius: 10, borderColor: '#f6fbf8', borderWidth: 4 },
      data: (board.value?.match_segment_distribution || []).map((item, index) => ({
        name: item.name,
        value: item.value,
        itemStyle: {
          color: ['#d8efe3', '#8fb4ab', '#5d7a74', '#24544d'][index % 4],
        },
      })),
    },
  ],
}));

const trendChartOption = computed(() => ({
  color: ['#24544d'],
  tooltip: { trigger: 'axis' },
  grid: { left: 42, right: 16, top: 24, bottom: 28 },
  xAxis: {
    type: 'category',
    data: (board.value?.delivery_trend || []).map((item) => item.label),
    axisLabel: { color: '#5d7a74' },
    axisLine: { lineStyle: { color: '#c9ddd4' } },
  },
  yAxis: {
    type: 'value',
    axisLabel: { color: '#5d7a74' },
    splitLine: { lineStyle: { color: '#deece6' } },
  },
  series: [
    {
      type: 'line',
      smooth: true,
      symbolSize: 8,
      lineStyle: { width: 3 },
      areaStyle: { color: 'rgba(36, 84, 77, 0.12)' },
      data: (board.value?.delivery_trend || []).map((item) => item.value),
    },
  ],
}));

const loadData = async () => {
  const [boardRes, deliveriesRes] = await Promise.all([enterpriseApi.dashboard(), enterpriseApi.deliveries()]);
  board.value = boardRes.data || null;
  deliveries.value = deliveriesRes.data || [];
  if (!selectedDeliveryId.value && deliveries.value.length) {
    selectedDeliveryId.value = deliveries.value[0].id;
  }
};

const openResume = (row) => {
  const path = row?.attachment?.file_path;
  if (!path) {
    ElMessage.warning('当前记录没有可查看的简历文件。');
    return;
  }
  window.open(`${fileBase}${path}`, '_blank');
};

const openSource = (row) => {
  if (!row?.source_url) {
    ElMessage.info('当前记录没有岗位来源链接。');
    return;
  }
  window.open(row.source_url, '_blank');
};

const formatDateTime = (value) => {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false });
};

onMounted(loadData);
</script>

<style scoped>
.hrm-root {
  display: grid;
  gap: 18px;
}

.hrm-hero {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 18px;
  padding: 30px;
  border-radius: 30px;
  background: linear-gradient(135deg, rgba(246, 251, 248, 0.98), rgba(216, 239, 227, 0.74));
  border: 1px solid rgba(36, 84, 77, 0.12);
  box-shadow: 0 18px 38px rgba(22, 48, 43, 0.08);
}

.hero-eyebrow,
.hero-tag,
.filter-chip {
  border-radius: 999px;
}

.hero-eyebrow {
  display: inline-flex;
  padding: 8px 14px;
  background: rgba(216, 239, 227, 0.84);
  color: #24544d;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.hero-title {
  margin: 16px 0 0;
  font-size: 38px;
  line-height: 1.14;
  color: #16302b;
}

.hero-desc {
  margin-top: 12px;
  color: #5d7a74;
  line-height: 1.8;
}

.hero-tags,
.filter-group,
.toolbar-actions,
.candidate-tags,
.chip-group,
.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-tags {
  margin-top: 16px;
}

.hero-tag,
.soft-chip,
.mini-chip {
  padding: 9px 14px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(36, 84, 77, 0.1);
  color: #24544d;
  font-size: 12px;
  font-weight: 700;
}

.priority-card {
  padding: 22px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(248, 252, 249, 0.98), rgba(237, 246, 241, 0.96));
  border: 1px solid rgba(36, 84, 77, 0.12);
  display: grid;
  gap: 12px;
}

.priority-kicker,
.metric-label,
.metric-tip,
.candidate-meta,
.candidate-summary,
.review-meta,
.review-summary,
.action-desc,
.priority-desc,
.stream-k,
.inspector-note,
.candidate-large-meta {
  color: #5d7a74;
}

.priority-title,
.metric-value,
.candidate-score,
.score-badge-value,
.review-side strong,
.action-title,
.candidate-name,
.candidate-large-name,
.block-title,
.mini-title {
  color: #16302b;
}

.priority-title {
  margin: 0;
  font-size: 24px;
  font-weight: 800;
  line-height: 1.35;
}

.priority-desc {
  margin: 0;
  line-height: 1.8;
}

.priority-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.priority-stat {
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(36, 84, 77, 0.1);
}

.priority-stat span {
  display: block;
  font-size: 12px;
}

.priority-stat strong {
  display: block;
  margin-top: 6px;
  font-size: 22px;
}

.metric-grid,
.top-grid,
.bottom-grid {
  display: grid;
  gap: 16px;
}

.metric-grid {
  grid-template-columns: repeat(6, minmax(0, 1fr));
}

.metric-card {
  padding: 20px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(246, 251, 248, 0.98), rgba(232, 243, 237, 0.96));
  border: 1px solid rgba(36, 84, 77, 0.1);
}

.metric-label {
  font-size: 13px;
}

.metric-value {
  margin-top: 10px;
  font-size: 30px;
  font-weight: 800;
}

.metric-tip {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.7;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: center;
}

.filter-chip {
  border: none;
  padding: 10px 14px;
  background: linear-gradient(180deg, rgba(246, 251, 248, 0.98), rgba(232, 243, 237, 0.96));
  border: 1px solid rgba(36, 84, 77, 0.08);
  color: #5d7a74;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}

.filter-chip.active {
  background: linear-gradient(135deg, rgba(36, 84, 77, 0.18), rgba(216, 239, 227, 0.34));
  color: #16302b;
  box-shadow: 0 12px 24px rgba(22, 48, 43, 0.08);
}

.top-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.main-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.1fr);
  gap: 18px;
  align-items: start;
  min-width: 0;
}

.candidate-panel :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.candidate-list {
  display: grid;
  gap: 12px;
  max-height: clamp(360px, calc(100vh - 280px), 760px);
  overflow: auto;
  align-content: start;
  padding-right: 4px;
}

.candidate-item {
  width: 100%;
  border: 1px solid rgba(36, 84, 77, 0.08);
  background: linear-gradient(180deg, rgba(246, 251, 248, 0.98), rgba(232, 243, 237, 0.96));
  border-radius: 22px;
  padding: 16px;
  text-align: left;
  cursor: pointer;
  transition: all 0.18s ease;
}

.candidate-item.active {
  background: linear-gradient(135deg, rgba(36, 84, 77, 0.16), rgba(216, 239, 227, 0.28));
  box-shadow: 0 14px 30px rgba(22, 48, 43, 0.08);
}

.candidate-item-top,
.candidate-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.candidate-score,
.score-badge-value {
  font-size: 28px;
  font-weight: 800;
}

.detail-column,
.review-list,
.action-list,
.mini-list {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.bottom-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.detail-stream-card :deep(.el-card__body) {
  max-height: clamp(380px, calc(100vh - 280px), 760px);
  overflow: auto;
  min-height: 0;
  padding-right: 6px;
}

.portrait-stream {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 14px;
  align-content: start;
}

.stream-card {
  grid-column: span 12;
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(246, 251, 248, 0.98), rgba(232, 243, 237, 0.96));
  border: 1px solid rgba(36, 84, 77, 0.08);
  padding: 16px;
  display: grid;
  gap: 10px;
}

.span-4 {
  grid-column: span 4;
}

.span-6 {
  grid-column: span 6;
}

.span-12 {
  grid-column: span 12;
}

.stream-summary {
  gap: 14px;
}

.score-badge {
  min-width: 120px;
  text-align: center;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgba(36, 84, 77, 0.1);
  background: rgba(255, 255, 255, 0.7);
}

.score-badge-label {
  margin-top: 4px;
  color: #5d7a74;
  font-size: 12px;
}

.stream-k {
  font-size: 12px;
}

.stream-v {
  margin-top: 2px;
}

.stream-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.review-item,
.action-item,
.mini-card {
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(246, 251, 248, 0.98), rgba(232, 243, 237, 0.96));
  border: 1px solid rgba(36, 84, 77, 0.08);
}

.review-item,
.action-item,
.mini-card {
  padding: 16px;
}

.review-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.review-name {
  color: #16302b;
  font-weight: 700;
}

.review-side {
  min-width: 92px;
  text-align: right;
}

.review-side span {
  display: block;
  margin-top: 8px;
  color: #5d7a74;
  font-size: 12px;
}

.action-title,
.block-title,
.mini-title {
  font-weight: 700;
}

.action-desc,
.review-summary {
  margin-top: 8px;
  line-height: 1.75;
}

.mini-list {
  gap: 10px;
  margin-top: 12px;
}

.muted {
  opacity: 0.72;
}

@media (max-width: 1400px) {
  .metric-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1200px) {
  .hrm-hero,
  .top-grid,
  .main-grid,
  .bottom-grid {
    grid-template-columns: 1fr;
  }

  .detail-stream-card :deep(.el-card__body) {
    max-height: none;
  }

  .span-4,
  .span-6,
  .span-12 {
    grid-column: span 12;
  }
}

@media (max-width: 900px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .toolbar,
  .candidate-item-top,
  .candidate-head,
  .review-item {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
