<template>
  <div v-loading="loading" class="page-shell profile-page">
    <PageHeader title="能力综合分析" description="将雷达图、优势短板和多维图表整合到同一工作区，快速看清能力结构与提升方向。">
      <div class="header-actions">
        <el-button v-if="auth.role !== 'student'" @click="load">刷新</el-button>
        <el-button v-if="auth.role === 'student'" type="primary" @click="generate">生成 / 刷新画像</el-button>
        <el-button v-if="auth.role === 'student'" :loading="imageLoading" @click="generateImage">生成画像图</el-button>
      </div>
    </PageHeader>

    <StudentScopeSelector v-model="selectedStudentId" @change="load" />

    <template v-if="profile">
      <div class="metric-grid">
        <SectionCard v-for="item in summaryCards" :key="item.label" class="metric-card">
          <div class="metric-label">{{ item.label }}</div>
          <div class="metric-value">{{ item.value }}</div>
          <div class="metric-tip">{{ item.tip }}</div>
        </SectionCard>
      </div>

      <SectionCard v-if="profileImage" title="学生画像图" class="profile-image-card">
        <div class="profile-image-layout">
          <img v-if="profileImageUrl" class="profile-image-preview" :src="profileImageUrl" :alt="profileImagePersona.name || '学生画像图'" />
          <div class="profile-image-info">
            <div class="persona-code">{{ profileImagePersona.code || profileImage.persona_code }}</div>
            <div class="persona-name">{{ profileImagePersona.name || profileImage.persona_name }}</div>
            <div v-if="profileImageMbti.code" class="mbti-row">
              <span>MBTI 倾向</span>
              <strong>{{ profileImageMbti.code }}</strong>
              <em>{{ profileImageMbti.name || "职业风格参考" }}</em>
            </div>
            <p class="persona-summary">{{ profileImage.analysis_summary || profileImagePersona.trait || profileImage.career_conclusion }}</p>
            <div class="persona-keywords">
              <el-tag v-for="item in imageKeywords" :key="item" round>{{ item }}</el-tag>
            </div>
          </div>
        </div>
      </SectionCard>

      <div class="two-col insight-top">
        <SectionCard title="六维能力雷达图">
          <AnalysisChart :option="radarOption" height="380px" />
        </SectionCard>

        <SectionCard title="综合分析摘要">
          <div class="summary-panel">
            <div class="summary-block">
              <div class="summary-title">职业成熟度</div>
              <div class="summary-pill">{{ profile.maturity_level || readinessLabel }}</div>
            </div>

            <div class="summary-block">
              <div class="summary-title">画像总结</div>
              <p class="summary-text">{{ formattedSummary }}</p>
            </div>

            <div class="summary-block">
              <div class="summary-title">能力标签</div>
              <div class="tag-list">
                <el-tag v-for="tag in displayTags" :key="tag" size="large" round>{{ tag }}</el-tag>
              </div>
            </div>

            <div class="summary-block dual">
              <div class="mini-panel strengths">
                <div class="mini-title">优势项</div>
                <div class="mini-list">
                  <div v-for="item in displayStrengths" :key="item" class="mini-item">{{ item }}</div>
                </div>
              </div>
              <div class="mini-panel weaknesses">
                <div class="mini-title">待提升项</div>
                <div class="mini-list">
                  <div v-for="item in displayWeaknesses" :key="item" class="mini-item">{{ item }}</div>
                </div>
              </div>
            </div>
          </div>
        </SectionCard>
      </div>

      <div class="chart-grid">
        <SectionCard title="六维得分柱状图">
          <AnalysisChart :option="scoreBarOption" height="320px" />
        </SectionCard>
        <SectionCard title="能力结构占比图">
          <AnalysisChart :option="abilityPieOption" height="320px" />
        </SectionCard>
        <SectionCard title="提升空间分析图">
          <AnalysisChart :option="gapBarOption" height="320px" />
        </SectionCard>
        <SectionCard title="职业就绪度仪表盘">
          <AnalysisChart :option="readinessGaugeOption" height="320px" />
        </SectionCard>
      </div>

      <div class="two-col">
        <SectionCard title="维度排名趋势图">
          <AnalysisChart :option="rankingLineOption" height="340px" />
        </SectionCard>
        <SectionCard title="优势与短板行动建议">
          <div class="action-section">
            <div class="action-title">优先保留与放大的优势</div>
            <el-timeline>
              <el-timeline-item v-for="item in displayStrengths" :key="`s-${item}`" type="success">
                持续强化 {{ item }}，并沉淀为可验证成果。
              </el-timeline-item>
            </el-timeline>
          </div>

          <div class="action-section">
            <div class="action-title warning">优先补齐的短板</div>
            <el-timeline>
              <el-timeline-item v-for="item in displayWeaknesses" :key="`w-${item}`" type="warning">
                围绕 {{ item }} 设定阶段任务，并在项目中验证提升。
              </el-timeline-item>
            </el-timeline>
          </div>

          <div class="insight-actions">
            <el-button type="primary" @click="router.push('/matches/center?tab=overview')">进入人岗匹配</el-button>
            <el-button plain @click="router.push('/career/center?tab=path')">查看成长路径</el-button>
          </div>
        </SectionCard>
      </div>
    </template>

    <SectionCard v-else title="暂无画像数据" class="empty-card">
      <div class="empty-wrap">
        <div class="empty-title">能力综合分析尚未生成</div>
        <div class="empty-desc">{{ emptyDescription }}</div>
        <el-button v-if="auth.role === 'student'" type="primary" @click="generate">立即生成画像</el-button>
        <el-button v-else plain @click="load">重新加载</el-button>
      </div>
    </SectionCard>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { enterpriseApi, studentApi } from "@/api";
import { useAuthStore } from "@/stores/auth";
import AnalysisChart from "@/components/AnalysisChart.vue";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";
import StudentScopeSelector from "@/components/StudentScopeSelector.vue";

const auth = useAuthStore();
const router = useRouter();
const profile = ref(null);
const loading = ref(false);
const imageLoading = ref(false);
const loadHint = ref("");
const selectedStudentId = ref(null);
const generatedProfileImage = ref(null);
const apiOrigin = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

const dimensionLabelMap = {
  professional_score: "专业能力",
  practice_score: "实践能力",
  communication_score: "沟通协作",
  learning_score: "学习成长",
  innovation_score: "创新能力",
  professionalism_score: "职业素养",
};

const prettifyProfileToken = (value) => {
  if (!value) return "-";
  const normalized = String(value).trim();
  return dimensionLabelMap[normalized] || normalized.replace(/_/g, " ");
};

const prettifyProfileText = (value) => {
  if (!value) return "";
  return Object.entries(dimensionLabelMap).reduce((result, [key, label]) => result.replaceAll(key, label), value);
};

const toAssetUrl = (url) => {
  const text = String(url || "").trim();
  if (!text) return "";
  if (text.startsWith("/uploads/") || text.startsWith("/api/")) return `${apiOrigin}${text}`;
  return text;
};

const dimensions = computed(() => [
  { key: "professional_score", label: "专业能力", value: Number(profile.value?.professional_score || 0), color: "#0f62fe" },
  { key: "practice_score", label: "实践能力", value: Number(profile.value?.practice_score || 0), color: "#00a6a6" },
  { key: "communication_score", label: "沟通协作", value: Number(profile.value?.communication_score || 0), color: "#ff8a34" },
  { key: "learning_score", label: "学习成长", value: Number(profile.value?.learning_score || 0), color: "#7c5cff" },
  { key: "innovation_score", label: "创新能力", value: Number(profile.value?.innovation_score || 0), color: "#ef476f" },
  { key: "professionalism_score", label: "职业素养", value: Number(profile.value?.professionalism_score || 0), color: "#16a34a" },
]);

const averageScore = computed(() => {
  const total = dimensions.value.reduce((sum, item) => sum + item.value, 0);
  return dimensions.value.length ? Number((total / dimensions.value.length).toFixed(1)) : 0;
});

const strongestDimension = computed(() => [...dimensions.value].sort((a, b) => b.value - a.value)[0]);
const weakestDimension = computed(() => [...dimensions.value].sort((a, b) => a.value - b.value)[0]);

const readinessLabel = computed(() => {
  if (averageScore.value >= 85) return "高成熟冲刺型";
  if (averageScore.value >= 70) return "稳定成长型";
  if (averageScore.value >= 55) return "基础提升型";
  return "起步积累型";
});

const defaultSummary = computed(() => `当前平均能力得分约为 ${averageScore.value} 分，建议优先强化 ${weakestDimension.value?.label || "薄弱维度"}，并持续放大 ${strongestDimension.value?.label || "优势维度"}。`);
const formattedSummary = computed(() => prettifyProfileText(profile.value?.summary || defaultSummary.value));

const displayTags = computed(() => {
  const list = (profile.value?.ability_tags || []).map(prettifyProfileToken).filter(Boolean);
  return list.length ? list : ["学习成长", "职业素养"];
});

const displayStrengths = computed(() => {
  const list = (profile.value?.strengths || []).map(prettifyProfileToken).filter(Boolean);
  return list.length ? list : [strongestDimension.value?.label || "项目实践"];
});

const displayWeaknesses = computed(() => {
  const list = (profile.value?.weaknesses || []).map(prettifyProfileToken).filter(Boolean);
  return list.length ? list : [weakestDimension.value?.label || "专业能力"];
});

const profileImage = computed(() => generatedProfileImage.value || profile.value?.raw_metrics?.profile_image || null);
const profileImagePersona = computed(() => profileImage.value?.persona || {});
const mbtiNames = {
  ISTJ: "责任执行型",
  ISFJ: "支持守护型",
  INFJ: "洞察规划型",
  INTJ: "战略分析型",
  ISTP: "实践解决型",
  ISFP: "灵活体验型",
  INFP: "理想探索型",
  INTP: "逻辑探索型",
  ESTP: "行动突破型",
  ESFP: "现场表达型",
  ENFP: "创意启发型",
  ENTP: "创新辩论型",
  ESTJ: "组织推进型",
  ESFJ: "协作服务型",
  ENFJ: "影响引导型",
  ENTJ: "目标统筹型",
};

const deriveMbtiFromCbti = (code) => {
  const text = String(code || "").trim().toUpperCase();
  if (!text) return { code: "", name: "" };
  const mbtiCode = `${text.includes("C") ? "E" : "I"}${text.startsWith("T") ? "N" : "S"}${text.startsWith("T") ? "T" : "F"}${text.includes("S") ? "J" : "P"}`;
  return { code: mbtiCode, name: mbtiNames[mbtiCode] || "职业风格参考" };
};

const profileImageMbti = computed(() => {
  const image = profileImage.value || {};
  const direct = image.mbti && typeof image.mbti === "object" ? image.mbti : {};
  const nested = image.persona?.mbti && typeof image.persona.mbti === "object" ? image.persona.mbti : {};
  const fallback = deriveMbtiFromCbti(image.persona?.code || image.persona_code || "");
  return {
    code: direct.code || nested.code || image.mbti_code || image.persona?.mbti_code || fallback.code,
    name: direct.name || nested.name || image.mbti_name || image.persona?.mbti_name || fallback.name,
  };
});
const profileImageUrl = computed(() => toAssetUrl(profileImage.value?.image_url || profileImage.value?.imageUrl));
const imageKeywords = computed(() => {
  const keywords = profileImage.value?.career_semantics?.keywords || profileImage.value?.keywords || [];
  const fromPersona = [profileImagePersona.value?.code, profileImagePersona.value?.name, profileImageMbti.value?.code, profileImageMbti.value?.name].filter(Boolean);
  return [...fromPersona, ...keywords].slice(0, 8);
});

const emptyDescription = computed(() => {
  if (loadHint.value) return loadHint.value;
  return auth.role === "student"
    ? "点击“生成 / 刷新画像”后即可查看雷达图、差距分析和行动建议。"
    : "请先在上方选择学生，或等待学生完成画像生成。";
});

const summaryCards = computed(() => [
  { label: "综合均分", value: averageScore.value, tip: "六维能力平均分" },
  { label: "最强维度", value: strongestDimension.value?.label || "-", tip: `${strongestDimension.value?.value || 0} 分` },
  { label: "待提升维度", value: weakestDimension.value?.label || "-", tip: `${weakestDimension.value?.value || 0} 分` },
  { label: "能力标签数", value: (profile.value?.ability_tags || []).length, tip: "当前画像识别标签" },
]);

const radarOption = computed(() => ({
  color: ["#0f62fe"],
  tooltip: { backgroundColor: "rgba(255,255,255,0.98)", borderColor: "#dbe7f5", textStyle: { color: "#1f2d3d" } },
  radar: {
    radius: "64%",
    splitNumber: 5,
    axisName: { color: "#425066", fontSize: 14, fontWeight: 600 },
    axisLine: { lineStyle: { color: "#d7e1ee" } },
    splitLine: { lineStyle: { color: "#eef3f8" } },
    splitArea: { areaStyle: { color: ["rgba(15, 98, 254, 0.04)", "rgba(15, 98, 254, 0.02)"] } },
    indicator: dimensions.value.map((item) => ({ name: item.label, max: 100 })),
  },
  series: [{ type: "radar", areaStyle: { color: "rgba(15, 98, 254, 0.18)" }, lineStyle: { width: 3 }, symbolSize: 8, data: [{ value: dimensions.value.map((item) => item.value), name: "能力画像" }] }],
}));

const scoreBarOption = computed(() => ({
  grid: { left: 48, right: 18, top: 24, bottom: 32 },
  tooltip: { trigger: "axis", backgroundColor: "rgba(255,255,255,0.98)", borderColor: "#dbe7f5", textStyle: { color: "#1f2d3d" } },
  xAxis: { type: "category", axisTick: { show: false }, axisLine: { lineStyle: { color: "#d7e1ee" } }, axisLabel: { color: "#5b677a" }, data: dimensions.value.map((item) => item.label) },
  yAxis: { type: "value", min: 0, max: 100, splitLine: { lineStyle: { color: "#eef3f8" } }, axisLabel: { color: "#5b677a" } },
  series: [{ type: "bar", barWidth: 26, itemStyle: { borderRadius: [10, 10, 0, 0], color: (params) => dimensions.value[params.dataIndex]?.color || "#0f62fe" }, data: dimensions.value.map((item) => item.value) }],
}));

const abilityPieOption = computed(() => ({
  tooltip: { trigger: "item", backgroundColor: "rgba(255,255,255,0.98)", borderColor: "#dbe7f5", textStyle: { color: "#1f2d3d" } },
  legend: { bottom: 0, icon: "circle", textStyle: { color: "#5b677a" } },
  series: [{
    type: "pie",
    radius: ["42%", "68%"],
    center: ["50%", "44%"],
    itemStyle: { borderRadius: 8, borderColor: "#fff", borderWidth: 4 },
    label: { formatter: "{b}\n{d}%", color: "#334155", fontWeight: 600 },
    data: dimensions.value.map((item) => ({ value: item.value || 1, name: item.label, itemStyle: { color: item.color } })),
  }],
}));

const gapBarOption = computed(() => ({
  grid: { left: 86, right: 20, top: 18, bottom: 24 },
  tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, backgroundColor: "rgba(255,255,255,0.98)", borderColor: "#dbe7f5", textStyle: { color: "#1f2d3d" } },
  xAxis: { type: "value", min: 0, max: 100, splitLine: { lineStyle: { color: "#eef3f8" } }, axisLabel: { color: "#5b677a" } },
  yAxis: { type: "category", axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: "#5b677a" }, data: dimensions.value.map((item) => item.label) },
  series: [{ type: "bar", barWidth: 16, itemStyle: { borderRadius: 999, color: "#ffd166" }, data: dimensions.value.map((item) => Number((100 - item.value).toFixed(1))) }],
}));

const readinessGaugeOption = computed(() => ({
  series: [{
    type: "gauge",
    startAngle: 210,
    endAngle: -30,
    min: 0,
    max: 100,
    progress: { show: true, width: 16, roundCap: true, itemStyle: { color: "#0f62fe" } },
    axisLine: { lineStyle: { width: 16, color: [[1, "#e7eef8"]] } },
    axisTick: { show: false },
    splitLine: { show: false },
    axisLabel: { distance: 18, color: "#5b677a" },
    pointer: { show: false },
    anchor: { show: false },
    title: { show: true, offsetCenter: [0, "48%"], color: "#64748b", fontSize: 13, lineHeight: 20 },
    detail: { valueAnimation: true, offsetCenter: [0, "6%"], formatter: (value) => `{score|${Number(value).toFixed(1)}}`, rich: { score: { fontSize: 26, fontWeight: 700, color: "#1f2d3d", lineHeight: 30 } } },
    data: [{ value: averageScore.value, name: readinessLabel.value }],
  }],
}));

const rankingLineOption = computed(() => {
  const sorted = [...dimensions.value].sort((a, b) => b.value - a.value);
  return {
    grid: { left: 28, right: 18, top: 24, bottom: 36 },
    tooltip: { trigger: "axis", backgroundColor: "rgba(255,255,255,0.98)", borderColor: "#dbe7f5", textStyle: { color: "#1f2d3d" } },
    xAxis: { type: "category", boundaryGap: false, axisLine: { lineStyle: { color: "#d7e1ee" } }, axisLabel: { color: "#5b677a" }, data: sorted.map((item) => item.label) },
    yAxis: { type: "value", min: 0, max: 100, splitLine: { lineStyle: { color: "#eef3f8" } }, axisLabel: { color: "#5b677a" } },
    series: [{ type: "line", smooth: true, symbolSize: 8, lineStyle: { width: 3, color: "#00a6a6" }, areaStyle: { color: "rgba(0, 166, 166, 0.12)" }, data: sorted.map((item) => item.value) }],
  };
});

const normalizeProfile = (data) => {
  if (!data || typeof data !== "object") return null;
  return Object.keys(data).length ? data : null;
};

const load = async () => {
  loading.value = true;
  loadHint.value = "";
  try {
    if (auth.role === "student") {
      const res = await studentApi.getProfile();
      profile.value = normalizeProfile(res?.data);
      generatedProfileImage.value = null;
      if (!profile.value) loadHint.value = "当前还没有画像数据，请点击“生成 / 刷新画像”开始分析。";
      return;
    }

    if (!selectedStudentId.value) {
      profile.value = null;
      loadHint.value = "请先选择学生后查看能力分析。";
      return;
    }

    const res = await enterpriseApi.studentProfile(selectedStudentId.value);
    profile.value = normalizeProfile(res?.data);
    generatedProfileImage.value = null;
    if (!profile.value) loadHint.value = "该学生暂无画像数据，可先在学生端生成画像。";
  } catch (error) {
    profile.value = null;
    loadHint.value = error?.response?.data?.message || error?.response?.data?.detail || "当前暂时无法获取画像数据，请稍后重试。";
  } finally {
    loading.value = false;
  }
};

const generate = async () => {
  loading.value = true;
  loadHint.value = "";
  try {
    const res = await studentApi.generateProfile();
    profile.value = normalizeProfile(res?.data);
    generatedProfileImage.value = null;
    if (!profile.value) loadHint.value = "画像生成成功，但暂未返回可展示数据。";
  } catch (error) {
    profile.value = null;
    loadHint.value = error?.response?.data?.message || error?.response?.data?.detail || "画像生成失败，请稍后重试。";
  } finally {
    loading.value = false;
  }
};

const generateImage = async () => {
  imageLoading.value = true;
  loadHint.value = "";
  try {
    const res = await studentApi.generateProfileImage();
    generatedProfileImage.value = res?.data || null;
    if (!profile.value) {
      const profileRes = await studentApi.getProfile();
      profile.value = normalizeProfile(profileRes?.data);
    }
  } catch (error) {
    loadHint.value = error?.response?.data?.message || error?.response?.data?.detail || "画像图生成失败，请检查 CBTI 图片资产是否已入库。";
  } finally {
    imageLoading.value = false;
  }
};

onMounted(() => {
  if (auth.role === "student") void load();
});
</script>

<style scoped>
.profile-page {
  gap: 16px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.metric-card :deep(.el-card__body) {
  padding: 14px 16px;
}

.metric-label {
  color: #6b7280;
  font-size: 13px;
}

.metric-value {
  margin-top: 8px;
  font-size: 30px;
  font-weight: 700;
  color: #1f2d3d;
}

.metric-tip {
  margin-top: 8px;
  color: #7b8798;
  font-size: 12px;
}

.insight-top {
  align-items: stretch;
}

.profile-image-layout {
  display: grid;
  grid-template-columns: minmax(220px, 360px) minmax(0, 1fr);
  gap: 18px;
  align-items: center;
}

.profile-image-preview {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #dbe7f5;
  background: #f8fbff;
}

.profile-image-info {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 10px;
}

.persona-code {
  color: #0f62fe;
  font-size: 30px;
  font-weight: 800;
  line-height: 1.1;
}

.persona-name {
  color: #1f2d3d;
  font-size: 20px;
  font-weight: 700;
}

.mbti-row {
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  padding: 10px 12px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.mbti-row span {
  color: #1e3a8a;
  font-size: 13px;
  font-weight: 700;
}

.mbti-row strong {
  color: #0f62fe;
  font-size: 22px;
  line-height: 1;
}

.mbti-row em {
  color: #334155;
  font-size: 13px;
  font-style: normal;
  font-weight: 700;
}

.persona-summary {
  margin: 0;
  color: #5b677a;
  line-height: 1.8;
}

.persona-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.summary-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.summary-block {
  padding: 14px;
  border-radius: 14px;
  background: #f8fbff;
  border: 1px solid #e7eef8;
}

.summary-block.dual {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  background: transparent;
  border: none;
  padding: 0;
}

.summary-title {
  margin-bottom: 10px;
  color: #4b5563;
  font-size: 13px;
  font-weight: 700;
}

.summary-pill {
  display: inline-flex;
  padding: 8px 14px;
  border-radius: 999px;
  background: linear-gradient(135deg, #0f62fe, #00a6a6);
  color: #fff;
  font-weight: 700;
}

.summary-text {
  margin: 0;
  color: #5b677a;
  line-height: 1.8;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.mini-panel {
  padding: 14px;
  border-radius: 14px;
}

.mini-panel.strengths {
  background: #eefaf1;
}

.mini-panel.weaknesses {
  background: #fff6e8;
}

.mini-title {
  margin-bottom: 10px;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.mini-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mini-item {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.76);
  color: #4b5563;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.action-section + .action-section {
  margin-top: 20px;
}

.action-title {
  margin-bottom: 10px;
  color: #16a34a;
  font-size: 14px;
  font-weight: 700;
}

.action-title.warning {
  color: #d97706;
}

.insight-actions {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.empty-card :deep(.el-card__body) {
  padding: 28px;
}

.empty-wrap {
  min-height: 260px;
  border: 1px dashed #d5deeb;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  gap: 10px;
  padding: 20px;
  background: #f9fbff;
}

.empty-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}

.empty-desc {
  color: #64748b;
  line-height: 1.8;
}

@media (max-width: 1100px) {
  .chart-grid,
  .profile-image-layout,
  .summary-block.dual {
    grid-template-columns: 1fr;
  }
}
</style>
