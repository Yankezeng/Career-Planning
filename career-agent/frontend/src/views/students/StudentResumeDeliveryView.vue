<template>
  <div class="page-shell resume-delivery-page">
    <PageHeader
      title="投递简历"
      description="从企业岗位知识库中选择目标岗位，查看标准岗位画像、要求与发展路径，并投递当前简历。"
    >
      <el-button @click="loadAll">刷新</el-button>
      <el-button type="primary" @click="router.push('/student/resume')">管理简历</el-button>
    </PageHeader>

    <SectionCard>
      <div class="delivery-console">
        <div class="console-main">
          <div class="console-title">当前投递简历</div>
          <div class="console-controls">
            <el-select v-model="activeResumeId" placeholder="选择简历" filterable>
              <el-option
                v-for="item in resumes"
                :key="item.id"
                :label="`${item.title || '简历'}${item.is_default ? '（默认）' : ''}`"
                :value="item.id"
              />
            </el-select>
            <el-select v-model="activeResumeVersionId" placeholder="选择版本" clearable>
              <el-option
                v-for="item in activeResumeVersions"
                :key="item.id"
                :label="`V${item.version_no} ${item.change_summary || ''}`"
                :value="item.id"
              />
            </el-select>
            <el-input v-model="deliveryNote" clearable placeholder="投递备注（可选）" />
          </div>
          <div class="console-hint">
            {{
              activeResume
                ? `已选择：${activeResume.title || '简历'}，目标 ${activeResume.target_job || '未标注'}`
                : '请先选择一份简历，再投递目标岗位。'
            }}
          </div>
        </div>
        <div class="console-stats">
          <div>
            <span>岗位数</span>
            <strong>{{ jobTotal }}</strong>
          </div>
          <div>
            <span>已投递</span>
            <strong>{{ deliveries.length }}</strong>
          </div>
        </div>
      </div>
    </SectionCard>

    <div class="job-toolbar">
      <el-input v-model="keyword" clearable placeholder="搜索岗位、企业、行业、技能" />
      <el-select v-model="categoryFilter" clearable placeholder="岗位类别">
        <el-option v-for="item in categoryOptions" :key="item" :label="item" :value="item" />
      </el-select>
    </div>

    <el-empty v-if="!filteredJobs.length && !loadingJobs" description="暂无可投递岗位" />
    <div v-else v-loading="loadingJobs" class="job-card-grid">
      <article v-for="job in filteredJobs" :key="job.id" class="job-card">
        <header class="job-card-head">
          <div>
            <div class="job-title">{{ jobDisplayName(job) }}</div>
            <div class="job-meta">
              {{ job.category || '开发' }} · {{ job.industry || '互联网' }} · {{ job.salary_range || '薪资面议' }}
            </div>
            <div class="job-company">{{ job.company_name || '企业岗位库' }}</div>
          </div>
          <span :class="['delivery-pill', { delivered: deliveryForJob(job) }]">
            {{ deliveryForJob(job) ? '已投递' : '可投递' }}
          </span>
        </header>

        <p class="job-summary">{{ profileSummary(job) }}</p>

        <div class="requirement-grid">
          <div>
            <span>学历</span>
            <strong>{{ job.degree_requirement || '本科及以上' }}</strong>
          </div>
          <div>
            <span>专业</span>
            <strong>{{ job.major_requirement || '相关专业优先' }}</strong>
          </div>
          <div>
            <span>实习</span>
            <strong>{{ job.internship_requirement || '项目或实习经历优先' }}</strong>
          </div>
        </div>

        <section v-if="postingFacts(job).length" class="card-section posting-info-section">
          <div class="section-label">岗位信息</div>
          <div class="posting-facts">
            <div v-for="item in postingFacts(job)" :key="`${job.id}-fact-${item.key}`" class="posting-fact">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </section>

        <section class="card-section">
          <div class="section-label">专业技能</div>
          <div class="tag-wrap skill-tags">
            <span v-for="item in skillTags(job)" :key="`${job.id}-skill-${item}`" class="soft-tag skill-tag">{{ item }}</span>
          </div>
        </section>

        <section class="card-section">
          <div class="section-label">证书要求</div>
          <div class="tag-wrap cert-tags">
            <span v-for="item in certificateTags(job)" :key="`${job.id}-cert-${item}`" class="soft-tag cert-tag">{{ item }}</span>
            <span v-if="!certificateTags(job).length" class="soft-tag cert-tag">暂无硬性证书</span>
          </div>
        </section>

        <section class="card-section">
          <div class="section-label">岗位画像</div>
          <div class="dimension-list">
            <div v-for="item in orderedPortraitDimensions(job)" :key="`${job.id}-${item.key}`" class="dimension-item">
              <span class="dimension-name">{{ item.label }}</span>
              <div class="dimension-meter">
                <span class="dimension-track">
                  <span
                    :class="['dimension-fill', { strong: item.score >= 85 }]"
                    :style="{ width: `${item.score}%` }"
                  ></span>
                </span>
                <span v-if="item.score >= 85" class="dimension-check">✓</span>
                <span v-else class="dimension-score">{{ item.score }}%</span>
              </div>
            </div>
          </div>
        </section>

        <section class="card-section">
          <div class="section-label">垂直岗位图谱</div>
          <div class="path-line">
            <span v-for="item in verticalPathPreview(job)" :key="`${job.id}-path-${item.level}-${item.job_name}`">
              {{ item.level }}：{{ item.job_name }}
            </span>
          </div>
        </section>

        <section class="card-section">
          <div class="section-label">换岗路径</div>
          <div class="transfer-list">
            <div v-for="item in transferPathPreview(job)" :key="`${job.id}-transfer-${item.target_job_name}`" class="transfer-item">
              <strong>{{ item.target_job_name }}</strong>
              <span>{{ item.path_note }}</span>
            </div>
          </div>
        </section>

        <footer class="job-actions">
          <el-button type="primary" :disabled="!activeResume" :loading="deliveringJobId === job.id" @click="deliverJob(job)">
            投递该岗位
          </el-button>
          <el-button :disabled="!profileJobId(job)" @click="goJobDetail(job)">详情</el-button>
          <el-button :disabled="!profileJobId(job)" @click="goJobGraph(job)">图谱</el-button>
        </footer>
      </article>
    </div>

    <div v-if="jobTotal > jobPageSize" class="job-pagination">
      <el-pagination
        v-model:current-page="jobPage"
        v-model:page-size="jobPageSize"
        background
        layout="total, sizes, prev, pager, next, jumper"
        :page-sizes="[20, 40, 80, 120]"
        :total="jobTotal"
        @current-change="loadJobs"
        @size-change="handlePageSizeChange"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { jobApi, studentApi } from "@/api";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";

const router = useRouter();

const jobs = ref([]);
const loadingJobs = ref(false);
const jobPage = ref(1);
const jobPageSize = ref(40);
const jobTotal = ref(0);
const jobStats = ref({});
const resumes = ref([]);
const resumeVersionsById = ref({});
const deliveries = ref([]);
const activeResumeId = ref(null);
const activeResumeVersionId = ref(null);
const deliveryNote = ref("");
const keyword = ref("");
const categoryFilter = ref("");
const deliveringJobId = ref(null);

const portraitDimensionOrder = [
  { key: "professional_skill", label: "专业技能", fallback: 82 },
  { key: "certificate", label: "证书要求", fallback: 76 },
  { key: "innovation", label: "创新能力", fallback: 72 },
  { key: "learning", label: "学习能力", fallback: 84 },
  { key: "stress_resistance", label: "抗压能力", fallback: 80 },
  { key: "communication", label: "沟通能力", fallback: 75 },
  { key: "internship", label: "实习能力", fallback: 82 },
];

const activeResume = computed(() => resumes.value.find((item) => item.id === activeResumeId.value) || null);
const activeResumeVersions = computed(() => resumeVersionsById.value[activeResumeId.value] || []);

const categoryOptions = computed(() => {
  const values = new Set([...(jobStats.value.categories || []), ...jobs.value.map((item) => item.category)].filter(Boolean));
  return Array.from(values).sort();
});

const filteredJobs = computed(() => {
  const query = keyword.value.trim().toLowerCase();
  return jobs.value.filter((job) => {
    if (categoryFilter.value && job.category !== categoryFilter.value) return false;
    if (!query) return true;
    const haystack = [
      job.name,
      job.display_name,
      job.company_name,
      job.category,
      job.industry,
      profileSummary(job),
      ...skillTags(job),
      ...certificateTags(job),
    ].join(" ").toLowerCase();
    return haystack.includes(query);
  });
});

const loadJobs = async () => {
  loadingJobs.value = true;
  try {
    const res = await jobApi.knowledgePostings({
      page: jobPage.value,
      page_size: jobPageSize.value,
      keyword: keyword.value.trim() || undefined,
      category: categoryFilter.value || undefined,
    });
    const payload = res.data || {};
    if (Array.isArray(payload)) {
      jobs.value = payload;
      jobTotal.value = payload.length;
      jobStats.value = {};
      return;
    }
    jobs.value = payload.items || [];
    jobTotal.value = Number(payload.total ?? jobs.value.length);
    jobStats.value = payload.stats || {};
  } finally {
    loadingJobs.value = false;
  }
};

const handlePageSizeChange = async () => {
  jobPage.value = 1;
  await loadJobs();
};

const loadResumes = async () => {
  const res = await studentApi.listResumes();
  resumes.value = res.data || [];
  if (!activeResumeId.value) {
    activeResumeId.value = resumes.value.find((item) => item.is_default)?.id || resumes.value[0]?.id || null;
  }
};

const loadResumeVersions = async (resumeId) => {
  if (!resumeId) return;
  const res = await studentApi.listResumeVersions(resumeId);
  resumeVersionsById.value = { ...resumeVersionsById.value, [resumeId]: res.data || [] };
  const versions = resumeVersionsById.value[resumeId] || [];
  const currentId = activeResume.value?.current_version_id;
  activeResumeVersionId.value = versions.find((item) => item.id === currentId)?.id || versions[0]?.id || null;
};

const loadDeliveries = async () => {
  const res = await studentApi.listResumeDeliveries();
  deliveries.value = res.data || [];
};

const loadAll = async () => {
  await Promise.all([loadJobs(), loadResumes(), loadDeliveries()]);
  if (activeResumeId.value) await loadResumeVersions(activeResumeId.value);
};

const deliverJob = async (job) => {
  if (!activeResume.value) {
    ElMessage.warning("请先选择一份简历");
    return;
  }
  deliveringJobId.value = job.id;
  const targetJobId = profileJobId(job);
  try {
    await studentApi.deliverResumeByResume(activeResume.value.id, {
      target_job_id: targetJobId,
      knowledge_doc_id: job.knowledge_doc_id || null,
      company_name: job.company_name || null,
      target_job_name: job.name || null,
      target_job_category: job.category || null,
      resume_version_id: activeResumeVersionId.value || activeResume.value.current_version_id || null,
      delivery_note: deliveryNote.value || null,
    });
    ElMessage.success("投递成功");
    await loadDeliveries();
  } finally {
    deliveringJobId.value = null;
  }
};

const deliveryForJob = (job) => {
  const docId = String(job.knowledge_doc_id || "").trim();
  if (docId) {
    return deliveries.value.find((item) => String(item.knowledge_doc_id || "").trim() === docId);
  }
  const targetJobId = profileJobId(job);
  return deliveries.value.find((item) => targetJobId && Number(item.target_job_id || item.snapshot?.job?.id) === Number(targetJobId));
};

const profileJobId = (job) => job?.target_job_id || job?.profile_job?.id || null;

const jobDisplayName = (job) => job?.display_name || job?.name || "目标岗位";

const goJobDetail = (job) => {
  const id = profileJobId(job);
  if (id) router.push(`/jobs/detail?id=${id}`);
};

const goJobGraph = (job) => {
  const id = profileJobId(job);
  if (id) router.push(`/student/job-graph?id=${id}`);
};

const profileOf = (job) => (job?.job_profile && typeof job.job_profile === "object" ? job.job_profile : {});

const profileSummary = (job) =>
  safeSummary(profileOf(job).summary) ||
  safeSummary(job.profile_job?.profile_summary) ||
  buildStructuredSummary(job) ||
  "该岗位画像已内置，建议结合技能、证书和项目经历持续补齐岗位证据。";

const safeSummary = (value) => {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  const rawLabels = ["岗位名称", "岗位类别", "工作地点", "薪资范围", "公司名称", "所属行业", "岗位编码", "岗位描述", "工作内容", "福利待遇"];
  const labelHits = rawLabels.filter((label) => text.includes(`${label}：`) || text.includes(`${label}:`)).length;
  if (labelHits >= 2 || text.length > 120) return "";
  return text;
};

const skillTags = (job) => {
  const values = [
    ...(job.core_skill_tags || []),
    ...(profileOf(job).core_skills || []),
    ...(job.common_skill_tags || []),
  ];
  return unique(values).slice(0, 8);
};

const buildStructuredSummary = (job) => {
  const skills = skillTags(job).slice(0, 3).join("、");
  const category = job.category || job.industry || "";
  const role = job.name || "目标岗位";
  if (skills) return `${role}关注${skills}等能力，适合围绕项目经验、沟通协作与学习成长补齐岗位证据。`;
  if (category) return `${role}属于${category}方向，建议结合岗位画像查看技能、证书、实习与发展路径。`;
  return "";
};

const certificateTags = (job) => unique([...(job.certificate_tags || []), ...(profileOf(job).certificates || [])]).slice(0, 5);

const postingInfo = (job) => (job?.posting_info && typeof job.posting_info === "object" ? job.posting_info : {});

const postingFacts = (job) => {
  const facts = postingInfo(job).facts;
  if (Array.isArray(facts) && facts.length) return facts.filter((item) => item?.value).slice(0, 6);
  return [
    { key: "location", label: "工作地点", value: job.work_location },
    { key: "salary_range", label: "薪资范围", value: job.salary_range },
    { key: "company_size", label: "公司规模", value: job.company_size },
    { key: "company_type", label: "公司类型", value: job.company_type },
    { key: "job_code", label: "岗位编码", value: job.job_code },
  ].filter((item) => item.value);
};

const orderedPortraitDimensions = (job) => {
  const dimensions = profileOf(job).portrait_dimensions || [];
  const byKey = new Map(dimensions.map((item) => [item.key, item]));
  return portraitDimensionOrder.map((dimension) => {
    const item = byKey.get(dimension.key) || {};
    return {
      key: dimension.key,
      label: item.label || dimension.label,
      score: boundedScore(item.score ?? dimension.fallback),
    };
  });
};

const verticalPath = (job) => profileOf(job).vertical_path || [];

const transferPaths = (job) => profileOf(job).transfer_paths || [];

const verticalPathPreview = (job) => {
  const path = verticalPath(job).slice(0, 3);
  if (path.length) return path;
  return [
    { level: "初级", job_name: job.name || "目标岗位" },
    { level: "中级", job_name: `高级${job.name || "岗位"}` },
    { level: "高级", job_name: "技术负责人/专家" },
  ];
};

const transferPathPreview = (job) => {
  const paths = transferPaths(job).slice(0, 3);
  if (paths.length) return paths;
  return [
    { target_job_name: "测试工程师", path_note: "利用接口和代码理解能力转向自动化测试。" },
    { target_job_name: "运维工程师", path_note: "结合发布稳定性经验转向 SRE 方向。" },
    { target_job_name: "数据分析师", path_note: "利用数据建模基础转向数据分析。" },
  ];
};

const boundedScore = (score) => {
  const value = Number(score || 0);
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
};

const unique = (items) => {
  const seen = new Set();
  return (items || []).filter((item) => {
    const value = String(item || "").trim();
    if (!value || seen.has(value)) return false;
    seen.add(value);
    return true;
  });
};

let searchTimer = null;
watch([keyword, categoryFilter], () => {
  if (searchTimer) window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    jobPage.value = 1;
    loadJobs();
  }, 300);
});

watch(activeResumeId, async (id) => {
  activeResumeVersionId.value = null;
  if (id) await loadResumeVersions(id);
});

onMounted(loadAll);
</script>

<style scoped>
.resume-delivery-page {
  width: min(1840px, 100%);
  color: var(--text-primary, #eaf7ff);
}

.delivery-console {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: center;
}

.console-title,
.job-title,
.section-label {
  font-weight: 700;
}

.console-controls {
  display: grid;
  grid-template-columns: minmax(180px, 260px) minmax(160px, 220px) minmax(220px, 1fr);
  gap: 12px;
  margin-top: 12px;
}

.console-hint,
.job-meta,
.job-company,
.job-summary,
.transfer-item span {
  color: rgba(229, 244, 255, 0.72);
}

.console-hint {
  margin-top: 10px;
}

.console-stats {
  display: flex;
  gap: 12px;
}

.console-stats div {
  min-width: 92px;
  padding: 14px;
  border: 1px solid rgba(111, 255, 233, 0.16);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.66);
}

.console-stats span {
  display: block;
  margin-bottom: 6px;
  color: rgba(229, 244, 255, 0.68);
}

.console-stats strong {
  font-size: 24px;
}

.job-toolbar {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) 220px;
  gap: 12px;
  margin: 18px 0;
}

.job-card-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  align-items: start;
  min-height: 240px;
  gap: 18px;
}

.job-pagination {
  display: flex;
  justify-content: center;
  margin-top: 22px;
}

.job-card {
  display: flex;
  min-height: 790px;
  flex-direction: column;
  gap: 16px;
  padding: 22px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 8px;
  background: #172239;
  box-shadow: 0 20px 42px rgba(3, 7, 18, 0.28);
}

.job-card-head,
.job-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.job-title {
  color: #ffffff;
  font-size: 22px;
  line-height: 1.35;
}

.job-company {
  margin-top: 4px;
  font-size: 13px;
}

.delivery-pill {
  flex: 0 0 auto;
  padding: 7px 14px;
  border-radius: 999px;
  background: #ffffff;
  color: #2f80ed;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}

.delivery-pill.delivered {
  color: #16a34a;
}

.job-summary {
  min-height: 56px;
  margin: 0;
  color: #c8d7ec;
  font-size: 18px;
  line-height: 1.8;
}

.requirement-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.requirement-grid div {
  min-width: 0;
  min-height: 136px;
  padding: 14px 12px;
  border: 1px solid rgba(203, 213, 225, 0.13);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.34);
}

.requirement-grid span {
  display: block;
  margin-bottom: 10px;
  color: #c7d2e2;
  font-size: 13px;
}

.requirement-grid strong {
  display: block;
  color: #ffffff;
  font-size: 15px;
  line-height: 1.65;
}

.posting-info-section {
  padding: 12px;
  border: 1px solid rgba(203, 213, 225, 0.12);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.22);
}

.posting-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.posting-fact {
  min-width: 0;
  padding: 9px 10px;
  border-radius: 7px;
  background: rgba(37, 66, 91, 0.58);
}

.posting-fact span,
.posting-section-item span {
  display: block;
  margin-bottom: 4px;
  color: #98b4d3;
  font-size: 12px;
}

.posting-fact strong {
  display: block;
  overflow: hidden;
  color: #ffffff;
  font-size: 14px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.posting-section-list {
  display: grid;
  gap: 8px;
}

.posting-section-item {
  min-width: 0;
  padding: 10px 11px;
  border-left: 3px solid #38bdf8;
  border-radius: 7px;
  background: rgba(30, 41, 59, 0.72);
}

.posting-section-item p {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: #d7e6f8;
  font-size: 14px;
  line-height: 1.65;
  white-space: pre-line;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.posting-section-item.expanded p {
  display: block;
  overflow: visible;
}

.inline-toggle {
  width: fit-content;
  padding: 0;
  border: 0;
  background: transparent;
  color: #93c5fd;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
}

.card-section {
  display: grid;
  gap: 10px;
}

.section-label {
  color: #ffffff;
  font-size: 20px;
  line-height: 1.2;
}

.tag-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.soft-tag {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  max-width: 100%;
  padding: 5px 12px;
  border-radius: 999px;
  background: #ffffff;
  font-size: 14px;
  line-height: 1.25;
  white-space: normal;
  word-break: break-word;
}

.skill-tag {
  color: #2f80ed;
}

.cert-tag {
  color: #d8922f;
}

.dimension-list {
  display: grid;
  gap: 10px;
}

.dimension-item {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
}

.dimension-name {
  color: #cfdbeb;
  font-size: 15px;
}

.dimension-meter {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 34px;
  gap: 7px;
  align-items: center;
}

.dimension-track {
  position: relative;
  height: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: #e5edf6;
}

.dimension-fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: inherit;
  background: #4aa8ff;
}

.dimension-fill.strong {
  background: #68bf45;
}

.dimension-score {
  color: rgba(203, 213, 225, 0.58);
  font-size: 16px;
}

.dimension-check {
  width: 18px;
  height: 18px;
  border: 1px solid #4ade80;
  border-radius: 50%;
  color: #4ade80;
  font-size: 12px;
  line-height: 17px;
  text-align: center;
}

.path-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.path-line span {
  padding: 10px 12px;
  border-radius: 8px;
  background: #25425b;
  color: #ffffff;
  font-size: 16px;
  line-height: 1.25;
}

.transfer-list {
  display: grid;
  gap: 10px;
}

.transfer-item {
  display: grid;
  gap: 7px;
  padding: 13px 14px;
  border-left: 3px solid #facc15;
  border-radius: 6px;
  background: rgba(55, 65, 81, 0.76);
}

.transfer-item strong {
  color: #ffffff;
  font-size: 16px;
  line-height: 1.3;
}

.transfer-item span {
  color: #cbd5e1;
  font-size: 16px;
  line-height: 1.45;
}

.job-actions {
  margin-top: auto;
  align-items: center;
  justify-content: space-between;
  flex-wrap: nowrap;
}

.job-actions .el-button {
  min-width: 68px;
  min-height: 42px;
  margin-left: 0;
  border-radius: 12px;
  font-weight: 700;
}

.job-actions .el-button:first-child {
  min-width: 120px;
}

@media (max-width: 1600px) {
  .resume-delivery-page {
    width: min(1380px, 100%);
  }

  .job-card-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1180px) {
  .resume-delivery-page {
    width: min(920px, 100%);
  }

  .job-card-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .delivery-console,
  .console-controls,
  .job-toolbar {
    grid-template-columns: 1fr;
  }

  .console-stats {
    width: 100%;
  }

  .console-stats div {
    flex: 1;
  }

  .job-card-grid {
    grid-template-columns: 1fr;
  }

  .job-card {
    min-height: auto;
    padding: 20px;
  }

  .requirement-grid {
    grid-template-columns: 1fr;
  }

  .posting-facts {
    grid-template-columns: 1fr;
  }

  .job-actions {
    flex-wrap: wrap;
  }
}
</style>
