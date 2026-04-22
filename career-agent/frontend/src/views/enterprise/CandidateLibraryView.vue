<template>
  <div class="page-shell resume-center-page">
    <PageHeader title="企业简历中心" description="统一查看候选人列表、简历预览、结构化解析与企业评估，专注招聘筛选工作流。">
      <div class="header-actions">
        <el-button @click="loadData">刷新</el-button>
      </div>
    </PageHeader>

    <div class="metric-grid">
      <div v-for="card in metricCards" :key="card.label" class="metric-card">
        <div class="metric-label">{{ card.label }}</div>
        <div class="metric-value">{{ card.value }}</div>
        <div class="metric-tip">{{ card.tip }}</div>
      </div>
    </div>

    <SectionCard title="筛选器">
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
        <el-input
          v-model="searchKeyword"
          class="search-input"
          placeholder="搜索候选人 / 专业 / 岗位 / 技能"
          clearable
        />
      </div>
    </SectionCard>

    <div class="workspace-grid">
      <SectionCard title="候选人列表" class="list-panel">
        <div class="candidate-list-wrap">
          <div class="candidate-list-toolbar">共 {{ filteredDeliveries.length }} 位候选人</div>
          <div class="candidate-list">
            <button
              v-for="item in filteredDeliveries"
              :key="item.id"
              type="button"
              :class="['candidate-card', { active: selectedDelivery?.id === item.id }]"
              @click="selectCandidate(item)"
            >
              <div class="candidate-top">
                <div>
                  <div class="candidate-name">{{ item.student?.name || '未命名候选人' }}</div>
                  <div class="candidate-meta">{{ item.student?.major || '专业未标注' }} · {{ item.target_job_name || '岗位未标注' }}</div>
                </div>
                <div class="candidate-score">{{ Math.round(item.match_score || 0) }}%</div>
              </div>

              <div class="candidate-summary">
                {{ item.student?.profile_summary || item.delivery_note || '暂无画像摘要，可在右侧解析页查看结构化简历。' }}
              </div>

              <div class="candidate-tags">
                <span>{{ item.pipeline_stage_label || '待初筛' }}</span>
                <span>{{ item.student?.project_count || 0 }} 项目</span>
                <span>{{ item.student?.internship_count || 0 }} 实习</span>
              </div>
            </button>

            <el-empty v-if="!filteredDeliveries.length" description="当前筛选条件下没有候选人" />
          </div>
        </div>
      </SectionCard>

      <SectionCard title="右侧工作台" class="detail-panel">
        <template v-if="selectedDelivery">
          <div class="detail-shell">
            <div class="detail-head">
              <div>
                <div class="detail-name">{{ selectedDelivery.student?.name || '-' }}</div>
                <div class="detail-meta">
                  {{ selectedDelivery.student?.major || '-' }} · {{ selectedDelivery.student?.college || '-' }} · {{ selectedDelivery.target_job_name || '-' }}
                </div>
              </div>
              <div class="score-pill">匹配 {{ Math.round(selectedDelivery.match_score || 0) }}%</div>
            </div>

            <el-tabs v-model="activeTab" class="detail-tabs" stretch>
              <el-tab-pane label="概览" name="overview" />
              <el-tab-pane label="简历" name="resume" />
              <el-tab-pane label="解析" name="analysis" />
              <el-tab-pane label="评估" name="evaluation" />
            </el-tabs>

            <div class="detail-body">
              <template v-if="activeTab === 'overview'">
                <div class="overview-grid">
                  <div><span>姓名</span><strong>{{ selectedDelivery.student?.name || '-' }}</strong></div>
                  <div><span>专业</span><strong>{{ selectedDelivery.student?.major || '-' }}</strong></div>
                  <div><span>学校/学院</span><strong>{{ selectedDelivery.student?.college || '-' }}</strong></div>
                  <div><span>目标岗位</span><strong>{{ selectedDelivery.target_job_name || '-' }}</strong></div>
                  <div><span>匹配度</span><strong>{{ Math.round(selectedDelivery.match_score || 0) }}%</strong></div>
                  <div><span>当前阶段</span><strong>{{ selectedDelivery.pipeline_stage_label || '待初筛' }}</strong></div>
                </div>

                <div class="block-card">
                  <div class="block-title">标签</div>
                  <div class="chip-group">
                    <span v-for="tag in selectedDelivery.student?.ability_tags || []" :key="`ability-${tag}`" class="soft-chip">{{ tag }}</span>
                    <span v-for="tag in selectedDelivery.student?.skill_tags || []" :key="`skill-${tag}`" class="soft-chip">{{ tag }}</span>
                    <span v-if="!(selectedDelivery.student?.ability_tags || []).length && !(selectedDelivery.student?.skill_tags || []).length" class="soft-chip muted">暂无标签</span>
                  </div>
                </div>

                <div class="block-card">
                  <div class="block-title">画像摘要</div>
                  <p>{{ selectedDelivery.student?.profile_summary || '暂无画像摘要' }}</p>
                </div>
              </template>

              <template v-else-if="activeTab === 'resume'">
                <iframe v-if="resumePreviewUrl" :src="resumePreviewUrl" class="resume-frame" />
                <div v-else class="resume-empty">
                  <p>当前附件格式暂不支持直接预览，请查看解析结果或下载原文件。</p>
                </div>
                <div class="action-row">
                  <el-button type="primary" @click="openResumeFile(selectedDelivery)">查看原文件</el-button>
                  <el-button v-if="selectedDelivery.source_url" @click="openSource(selectedDelivery)">岗位来源</el-button>
                </div>
              </template>

              <template v-else-if="activeTab === 'analysis'">
                <div class="analysis-actions">
                  <el-button :loading="analysisLoading" @click="ensureResumeAnalysis(true)">刷新解析</el-button>
                  <span class="analysis-tip" v-if="analysisError">{{ analysisError }}</span>
                </div>

                <template v-if="currentAnalysis">
                  <div class="overview-grid">
                    <div><span>姓名</span><strong>{{ currentAnalysis.basic?.name || '-' }}</strong></div>
                    <div><span>电话</span><strong>{{ currentAnalysis.basic?.phone || '-' }}</strong></div>
                    <div><span>邮箱</span><strong>{{ currentAnalysis.basic?.email || '-' }}</strong></div>
                    <div><span>专业</span><strong>{{ currentAnalysis.basic?.major || '-' }}</strong></div>
                    <div><span>学院</span><strong>{{ currentAnalysis.basic?.college || '-' }}</strong></div>
                    <div><span>目标岗位</span><strong>{{ currentAnalysis.basic?.target_role || selectedDelivery.target_job_name || '-' }}</strong></div>
                  </div>

                  <div class="block-card">
                    <div class="block-title">技能</div>
                    <div class="chip-group">
                      <span v-for="skill in currentAnalysis.skills || []" :key="skill" class="soft-chip">{{ skill }}</span>
                      <span v-if="!(currentAnalysis.skills || []).length" class="soft-chip muted">暂无技能数据</span>
                    </div>
                  </div>

                  <div class="analysis-grid">
                    <div class="block-card">
                      <div class="block-title">项目经历</div>
                      <div v-if="(currentAnalysis.projects || []).length" class="text-list">
                        <div v-for="(item, idx) in currentAnalysis.projects" :key="`project-${idx}`" class="text-item">
                          <strong>{{ item.name || '项目' }}</strong>
                          <p>{{ item.description || item.outcome || '-' }}</p>
                        </div>
                      </div>
                      <p v-else>暂无项目经历</p>
                    </div>

                    <div class="block-card">
                      <div class="block-title">实习经历</div>
                      <div v-if="(currentAnalysis.internships || []).length" class="text-list">
                        <div v-for="(item, idx) in currentAnalysis.internships" :key="`intern-${idx}`" class="text-item">
                          <strong>{{ item.company || '-' }} · {{ item.position || '-' }}</strong>
                          <p>{{ item.description || '-' }}</p>
                        </div>
                      </div>
                      <p v-else>暂无实习经历</p>
                    </div>
                  </div>

                  <div class="block-card">
                    <div class="block-title">教育经历</div>
                    <p>{{ currentAnalysis.education || '-' }}</p>
                  </div>

                  <div class="block-card">
                    <div class="block-title">简历摘要</div>
                    <p>{{ currentAnalysis.summary || '-' }}</p>
                  </div>
                </template>
                <el-empty v-else description="暂无解析结果，点击“刷新解析”生成" />
              </template>

              <template v-else>
                <div class="overview-grid">
                  <div><span>匹配度</span><strong>{{ Math.round(selectedDelivery.match_score || 0) }}%</strong></div>
                  <div><span>画像摘要</span><strong>{{ selectedDelivery.student?.profile_summary || currentAnalysis?.profile_summary || '-' }}</strong></div>
                  <div><span>项目数</span><strong>{{ selectedDelivery.student?.project_count || 0 }}</strong></div>
                  <div><span>实习数</span><strong>{{ selectedDelivery.student?.internship_count || 0 }}</strong></div>
                </div>

                <div class="analysis-grid">
                  <div class="block-card">
                    <div class="block-title">优势项</div>
                    <ul class="bullet-list">
                      <li v-for="(item, idx) in evaluationHighlights" :key="`plus-${idx}`">{{ item }}</li>
                    </ul>
                  </div>

                  <div class="block-card">
                    <div class="block-title">风险项</div>
                    <ul class="bullet-list">
                      <li v-for="(item, idx) in evaluationRisks" :key="`risk-${idx}`">{{ item }}</li>
                    </ul>
                  </div>
                </div>

                <div class="block-card">
                  <div class="block-title">推荐动作</div>
                  <p>{{ evaluationAction }}</p>
                </div>

                <div class="block-card">
                  <div class="block-title">推荐追问</div>
                  <ul class="bullet-list">
                    <li v-for="(item, idx) in followupQuestions" :key="`q-${idx}`">{{ item }}</li>
                  </ul>
                </div>
              </template>
            </div>
          </div>
        </template>
        <el-empty v-else description="请先从左侧选择一位候选人" />
      </SectionCard>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { enterpriseApi } from "@/api";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";

const fileBase = "http://127.0.0.1:8000";

const deliveries = ref([]);
const activeFilter = ref("all");
const searchKeyword = ref("");
const selectedDeliveryId = ref(null);
const activeTab = ref("overview");

const analysisCache = ref({});
const analysisLoading = ref(false);
const analysisError = ref("");

const filters = [
  { label: "全部候选人", value: "all" },
  { label: "高匹配优先", value: "high" },
  { label: "建议约面", value: "interview" },
  { label: "待复评", value: "pending" },
];

const filteredDeliveries = computed(() => {
  let rows = deliveries.value || [];
  if (activeFilter.value === "high") rows = rows.filter((item) => Number(item.match_score || 0) >= 70);
  if (activeFilter.value === "interview") rows = rows.filter((item) => item.pipeline_stage === "interview");
  if (activeFilter.value === "pending") rows = rows.filter((item) => !item.enterprise_feedback);

  const keyword = searchKeyword.value.trim().toLowerCase();
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

const selectedDelivery = computed(
  () =>
    deliveries.value.find((item) => item.id === selectedDeliveryId.value)
    || filteredDeliveries.value[0]
    || deliveries.value[0]
    || null,
);

const currentAnalysis = computed(() => {
  const id = selectedDelivery.value?.id;
  if (!id) return null;
  return analysisCache.value[id] || null;
});

const resumePreviewUrl = computed(() => {
  const attachment = selectedDelivery.value?.attachment;
  if (!attachment?.file_path) return "";
  const type = String(attachment.file_type || "").toLowerCase();
  if (!["pdf", "png", "jpg", "jpeg", "webp", "bmp"].includes(type)) return "";
  return `${fileBase}${attachment.file_path}`;
});

const bestScore = computed(() => {
  if (!deliveries.value.length) return "0%";
  return `${Math.round(Math.max(...deliveries.value.map((item) => Number(item.match_score || 0))))}%`;
});

const highMatchCount = computed(() => deliveries.value.filter((item) => Number(item.match_score || 0) >= 70).length);
const interviewReadyCount = computed(() => deliveries.value.filter((item) => item.pipeline_stage === "interview").length);
const pendingReviewCount = computed(() => deliveries.value.filter((item) => !item.enterprise_feedback).length);

const metricCards = computed(() => [
  { label: "全部候选人", value: deliveries.value.length, tip: "当前企业端可处理的简历总数" },
  { label: "高匹配候选人", value: highMatchCount.value, tip: "匹配度 70% 以上，建议优先处理" },
  { label: "建议约面", value: interviewReadyCount.value, tip: "已达到建议约面的候选人" },
  { label: "待复评", value: pendingReviewCount.value, tip: "尚未填写企业复评意见" },
  { label: "最高匹配度", value: bestScore.value, tip: "当前候选人池最高匹配结果" },
  { label: "当前筛选结果", value: filteredDeliveries.value.length, tip: "经过筛选器与关键词过滤后的候选人数量" },
]);

const evaluationHighlights = computed(() => {
  const row = selectedDelivery.value;
  if (!row) return [];
  const tags = (row.student?.ability_tags || []).slice(0, 3);
  const skills = (row.student?.skill_tags || []).slice(0, 3);
  const result = [];
  if (Number(row.match_score || 0) >= 70) result.push("岗位匹配度较高，具备推进价值");
  if (skills.length) result.push(`关键技能：${skills.join("、")}`);
  if (tags.length) result.push(`画像标签：${tags.join("、")}`);
  if (!result.length) result.push("当前优势证据较少，建议先补充项目与技能证明");
  return result;
});

const evaluationRisks = computed(() => {
  const row = selectedDelivery.value;
  if (!row) return [];
  const risks = [];
  if (Number(row.match_score || 0) < 70) risks.push("岗位匹配度偏低，建议先电话沟通确认岗位意向");
  if (Number(row.student?.project_count || 0) === 0) risks.push("项目经历不足，缺少可验证的成果证据");
  if (Number(row.student?.internship_count || 0) === 0) risks.push("实习经历不足，实战场景信息偏少");
  if (!row.student?.phone && !row.student?.email) risks.push("联系方式缺失，后续推进存在阻碍");
  if (!risks.length) risks.push("未发现明显风险项，可进入下一轮沟通");
  return risks;
});

const evaluationAction = computed(() => {
  const score = Number(selectedDelivery.value?.match_score || 0);
  if (score >= 85) return "建议约面：优先安排一轮结构化面试，并确认入岗时间。";
  if (score >= 70) return "建议继续观察：先电话沟通确认岗位匹配细节，再决定是否约面。";
  return "证据不足待补充：建议先索取补充材料，再决定是否推进。";
});

const followupQuestions = computed(() => {
  const target = selectedDelivery.value?.target_job_name || "目标岗位";
  return [
    `请你结合一个最相关项目，说明你如何胜任“${target}”的核心职责？`,
    "你在项目或实习中最有代表性的结果是什么？如何量化？",
    "如果入职后两周内需要独立承担任务，你会如何推进？",
  ];
});

const loadData = async () => {
  const res = await enterpriseApi.deliveries();
  deliveries.value = res.data || [];
  if (!selectedDeliveryId.value && deliveries.value.length) selectedDeliveryId.value = deliveries.value[0].id;
};

const selectCandidate = (row) => {
  selectedDeliveryId.value = row?.id || null;
};

const ensureResumeAnalysis = async (force = false) => {
  const deliveryId = selectedDelivery.value?.id;
  if (!deliveryId) return;
  if (!force && analysisCache.value[deliveryId]) return;

  analysisLoading.value = true;
  analysisError.value = "";
  try {
    const res = await enterpriseApi.resumeAnalysis(deliveryId);
    analysisCache.value = {
      ...analysisCache.value,
      [deliveryId]: res.data || null,
    };
  } catch (error) {
    analysisError.value = error?.friendlyMessage || error?.response?.data?.message || "简历解析失败";
  } finally {
    analysisLoading.value = false;
  }
};

const openResumeFile = (row) => {
  const path = row?.attachment?.file_path;
  if (!path) {
    ElMessage.warning("当前记录没有可查看的简历文件");
    return;
  }
  window.open(`${fileBase}${path}`, "_blank");
};

const openSource = (row) => {
  if (!row?.source_url) {
    ElMessage.info("当前记录没有岗位来源链接");
    return;
  }
  window.open(row.source_url, "_blank");
};

watch(
  () => selectedDelivery.value?.id,
  (id) => {
    if (!id) return;
    if (activeTab.value === "analysis") ensureResumeAnalysis();
  },
);

watch(
  () => activeTab.value,
  (tab) => {
    if (tab === "analysis") ensureResumeAnalysis();
  },
);

onMounted(loadData);
</script>

<style scoped>
.resume-center-page {
  display: grid;
  gap: 18px;
}

.header-actions,
.toolbar,
.filter-group,
.candidate-tags,
.action-row,
.chip-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 16px;
}

.metric-card {
  padding: 18px;
  border-radius: 18px;
  border: 1px solid rgba(36, 84, 77, 0.1);
  background: linear-gradient(180deg, #ffffff, #f7fbf9);
}

.metric-label {
  color: #5d7a74;
  font-size: 13px;
}

.metric-value {
  margin-top: 10px;
  color: #16302b;
  font-size: 28px;
  font-weight: 800;
}

.metric-tip {
  margin-top: 8px;
  color: #6f8780;
  font-size: 12px;
  line-height: 1.7;
}

.toolbar {
  justify-content: space-between;
  align-items: center;
}

.search-input {
  max-width: 360px;
}

.filter-chip {
  border: 1px solid rgba(36, 84, 77, 0.1);
  padding: 9px 14px;
  border-radius: 999px;
  background: #f4faf7;
  color: #41655f;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}

.filter-chip.active {
  background: #ddf0e8;
  color: #173733;
}

.workspace-grid {
  display: grid;
  grid-template-columns: 0.92fr 1.08fr;
  gap: 18px;
  align-items: stretch;
}

.list-panel :deep(.el-card__body),
.detail-panel :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.candidate-list-wrap,
.detail-shell {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.candidate-list-toolbar {
  color: #6f8780;
  font-size: 12px;
}

.candidate-list {
  display: grid;
  gap: 12px;
  min-height: 0;
  overflow: auto;
  max-height: calc(100vh - 340px);
  align-content: start;
  padding-right: 4px;
}

.candidate-card {
  width: 100%;
  border: 1px solid rgba(36, 84, 77, 0.08);
  background: linear-gradient(180deg, #ffffff, #f7fbf9);
  border-radius: 16px;
  padding: 14px;
  text-align: left;
  cursor: pointer;
}

.candidate-card.active {
  border-color: rgba(36, 84, 77, 0.22);
  background: #ecf7f2;
}

.candidate-top,
.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

.candidate-name,
.detail-name,
.block-title {
  font-weight: 700;
  color: #173733;
}

.candidate-meta,
.candidate-summary,
.detail-meta,
.block-card p,
.analysis-tip {
  margin-top: 6px;
  color: #5d7a74;
  line-height: 1.75;
}

.candidate-score {
  color: #173733;
  font-size: 24px;
  font-weight: 800;
}

.candidate-tags span,
.soft-chip,
.score-pill {
  padding: 7px 12px;
  border-radius: 999px;
  background: #e6f4ed;
  color: #24544d;
  font-size: 12px;
  font-weight: 700;
}

.soft-chip.muted {
  opacity: 0.75;
}

.detail-name {
  font-size: 24px;
}

.detail-tabs {
  margin-top: 2px;
}

.detail-body {
  min-height: 0;
  overflow: auto;
  max-height: calc(100vh - 390px);
  display: grid;
  gap: 12px;
  align-content: start;
  padding-right: 4px;
}

.overview-grid,
.analysis-grid {
  display: grid;
  gap: 10px 12px;
}

.overview-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.analysis-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.overview-grid div {
  padding: 12px;
  border-radius: 12px;
  border: 1px solid #e1ece8;
  background: #fbfdfc;
}

.overview-grid span {
  display: block;
  color: #5d7a74;
  font-size: 12px;
}

.overview-grid strong {
  display: block;
  margin-top: 8px;
  color: #173733;
}

.block-card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid #e1ece8;
  background: #ffffff;
}

.block-title {
  margin-bottom: 8px;
}

.resume-frame {
  width: 100%;
  min-height: 600px;
  border: none;
  border-radius: 12px;
  background: #f6fbf8;
}

.resume-empty {
  min-height: 180px;
  border: 1px dashed #c9ddd5;
  border-radius: 12px;
  display: grid;
  place-items: center;
  text-align: center;
  padding: 18px;
}

.analysis-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.text-list {
  display: grid;
  gap: 10px;
}

.text-item p {
  margin: 6px 0 0;
}

.bullet-list {
  margin: 0;
  padding-left: 18px;
  color: #35534e;
  display: grid;
  gap: 6px;
}

@media (max-width: 1400px) {
  .metric-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1200px) {
  .workspace-grid,
  .overview-grid,
  .analysis-grid {
    grid-template-columns: 1fr;
  }

  .candidate-list,
  .detail-body {
    max-height: none;
  }
}

@media (max-width: 900px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .toolbar,
  .detail-head {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
