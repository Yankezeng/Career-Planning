<template>
  <div class="page-shell archive-page">
    <PageHeader title="学生档案中心" description="在统一工作台中维护基础档案、技能标签与能力画像，支持一键刷新画像。">
      <div class="header-actions">
        <el-button @click="loadAll">刷新档案</el-button>
        <el-button type="primary" :loading="generating" @click="generateProfile">生成 / 刷新画像</el-button>
      </div>
    </PageHeader>

    <div class="metric-grid">
      <SectionCard v-for="item in summaryCards" :key="item.label" class="metric-card">
        <div class="metric-label">{{ item.label }}</div>
        <div class="metric-value">{{ item.value }}</div>
        <div class="metric-tip">{{ item.tip }}</div>
      </SectionCard>
    </div>

    <div class="archive-grid">
      <SectionCard title="基础档案">
        <el-form :model="form" label-position="top" class="profile-form">
          <div class="form-grid three">
            <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
            <el-form-item label="性别"><el-input v-model="form.gender" /></el-form-item>
            <el-form-item label="学号"><el-input v-model="form.student_no" /></el-form-item>
            <el-form-item label="年级"><el-input v-model="form.grade" /></el-form-item>
            <el-form-item label="专业"><el-input v-model="form.major" /></el-form-item>
            <el-form-item label="学院"><el-input v-model="form.college" /></el-form-item>
            <el-form-item label="电话"><el-input v-model="form.phone" /></el-form-item>
            <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
            <el-form-item label="目标城市"><el-input v-model="form.target_city" /></el-form-item>
          </div>

          <div class="form-grid two">
            <el-form-item label="兴趣方向（逗号分隔）"><el-input v-model="interestText" /></el-form-item>
            <el-form-item label="目标行业"><el-input v-model="form.target_industry" /></el-form-item>
          </div>

          <el-form-item label="教育经历">
            <el-input v-model="form.education_experience" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item label="个人简介">
            <el-input v-model="form.bio" type="textarea" :rows="4" />
          </el-form-item>
        </el-form>

        <div class="form-actions">
          <el-button type="primary" @click="save">保存档案</el-button>
          <el-button plain @click="router.push('/assistant')">返回 AI 对话</el-button>
        </div>
      </SectionCard>

      <SectionCard title="能力画像快照">
        <template v-if="profile">
          <div class="profile-side">
            <div class="maturity-card">
              <div class="maturity-title">职业成熟度</div>
              <div class="maturity-value">{{ profile.maturity_level || readinessLabel }}</div>
              <div class="maturity-desc">{{ profile.summary || summaryText }}</div>
            </div>

            <AnalysisChart :option="radarOption" height="280px" />

            <div class="profile-block">
              <div class="block-title">能力标签</div>
              <div class="tag-list">
                <el-tag v-for="tag in displayTags" :key="tag" round>{{ tag }}</el-tag>
              </div>
            </div>

            <div class="insight-grid">
              <div class="insight-card strength">
                <div class="block-title">优势项</div>
                <div v-for="item in displayStrengths" :key="item" class="insight-item">{{ item }}</div>
              </div>
              <div class="insight-card weakness">
                <div class="block-title">待提升项</div>
                <div v-for="item in displayWeaknesses" :key="item" class="insight-item">{{ item }}</div>
              </div>
            </div>

            <div class="form-actions profile-actions">
              <el-button type="primary" plain @click="router.push('/profile/insight')">查看完整分析</el-button>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="empty-state">
            <div class="empty-title">当前还没有能力画像</div>
            <div class="empty-desc">先补全基础档案并保存，再点击“生成 / 刷新画像”，系统会自动分析六维能力结构。</div>
            <el-button type="primary" :loading="generating" @click="generateProfile">立即生成画像</el-button>
          </div>
        </template>
      </SectionCard>
    </div>

    <SectionCard title="技能清单与画像输入">
      <div class="section-tip">技能标签会直接参与能力画像计算与人岗匹配推荐。</div>
      <div class="tag-list skill-tags">
        <el-tag v-for="item in skills" :key="item.id" closable round @close="removeSkill(item.id)">
          {{ item.name }}
        </el-tag>
      </div>
      <div class="skill-editor">
        <el-input v-model="newSkill" placeholder="例如：Python / Vue 3 / SQL / 数据分析" @keyup.enter="addSkill" />
        <el-button type="primary" @click="addSkill">新增技能</el-button>
      </div>
    </SectionCard>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { studentApi } from "@/api";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";
import AnalysisChart from "@/components/AnalysisChart.vue";

const router = useRouter();

const form = reactive({
  name: "",
  gender: "",
  student_no: "",
  grade: "",
  major: "",
  college: "",
  phone: "",
  email: "",
  interests: [],
  target_industry: "",
  target_city: "",
  education_experience: "",
  bio: "",
});

const skills = ref([]);
const profile = ref(null);
const newSkill = ref("");
const generating = ref(false);

const dimensionLabelMap = {
  professional_score: "专业能力",
  practice_score: "实践能力",
  communication_score: "沟通协作",
  learning_score: "学习成长",
  innovation_score: "创新能力",
  professionalism_score: "职业素养",
};

const scoreEntries = computed(() => [
  { key: "professional_score", label: "专业能力", value: Number(profile.value?.professional_score || 0) },
  { key: "practice_score", label: "实践能力", value: Number(profile.value?.practice_score || 0) },
  { key: "communication_score", label: "沟通协作", value: Number(profile.value?.communication_score || 0) },
  { key: "learning_score", label: "学习成长", value: Number(profile.value?.learning_score || 0) },
  { key: "innovation_score", label: "创新能力", value: Number(profile.value?.innovation_score || 0) },
  { key: "professionalism_score", label: "职业素养", value: Number(profile.value?.professionalism_score || 0) },
]);

const prettifyToken = (token) => {
  if (!token) return "";
  return dimensionLabelMap[token] || String(token).replace(/_/g, " ");
};

const interestText = computed({
  get: () => (form.interests || []).join(", "),
  set: (value) => {
    form.interests = value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  },
});

const averageScore = computed(() => {
  const scores = scoreEntries.value.map((item) => item.value);
  if (!scores.length) return 0;
  return Number((scores.reduce((sum, item) => sum + item, 0) / scores.length).toFixed(1));
});

const readinessLabel = computed(() => {
  if (averageScore.value >= 85) return "高成熟冲刺型";
  if (averageScore.value >= 70) return "稳定成长型";
  if (averageScore.value >= 55) return "基础提升型";
  return "起步积累型";
});

const displayStrengths = computed(() => {
  const list = (profile.value?.strengths || []).map(prettifyToken).filter(Boolean);
  return list.length ? list : ["项目实践", "表达沟通"];
});

const displayWeaknesses = computed(() => {
  const list = (profile.value?.weaknesses || []).map(prettifyToken).filter(Boolean);
  return list.length ? list : ["专业深度", "行业理解"];
});

const summaryText = computed(() => {
  if (!profile.value) return "暂无画像摘要";
  return `当前综合均分 ${averageScore.value} 分，建议优先提升 ${displayWeaknesses.value[0]}，并继续放大 ${displayStrengths.value[0]}。`;
});

const displayTags = computed(() => {
  const list = (profile.value?.ability_tags || []).map(prettifyToken).filter(Boolean);
  return list.length ? list : ["学习成长", "职业素养"];
});

const archiveCompletion = computed(() => {
  const fields = [
    form.name,
    form.gender,
    form.student_no,
    form.grade,
    form.major,
    form.college,
    form.phone,
    form.email,
    form.target_city,
    form.target_industry,
    form.education_experience,
    form.bio,
    ...(form.interests || []),
  ];
  const filled = fields.filter((item) => String(item || "").trim()).length;
  return Math.min(100, Math.round((filled / 12) * 100));
});

const summaryCards = computed(() => [
  {
    label: "档案完整度",
    value: `${archiveCompletion.value}%`,
    tip: "字段越完整，画像与匹配结果越稳定",
  },
  {
    label: "技能标签数",
    value: `${skills.value.length} 项`,
    tip: "技能标签将直接用于能力评分与匹配",
  },
  {
    label: "当前画像均分",
    value: profile.value ? `${averageScore.value}` : "待生成",
    tip: profile.value ? "六维能力平均分" : "生成画像后展示最新均分",
  },
  {
    label: "当前成熟度",
    value: profile.value?.maturity_level || readinessLabel.value,
    tip: "根据档案、技能和成长记录综合评估",
  },
]);

const radarOption = computed(() => ({
  backgroundColor: "transparent",
  tooltip: { trigger: "item" },
  radar: {
    radius: "64%",
    splitNumber: 5,
    axisName: {
      color: "#5b677a",
      fontSize: 13,
    },
    splitArea: {
      areaStyle: {
        color: ["rgba(15, 98, 254, 0.04)", "rgba(15, 98, 254, 0.02)"],
      },
    },
    axisLine: { lineStyle: { color: "#d6deeb" } },
    splitLine: { lineStyle: { color: "#eaf0f8" } },
    indicator: scoreEntries.value.map((item) => ({ name: item.label, max: 100 })),
  },
  series: [
    {
      type: "radar",
      data: [
        {
          value: scoreEntries.value.map((item) => item.value),
          areaStyle: { color: "rgba(15, 98, 254, 0.15)" },
          lineStyle: { color: "#0f62fe", width: 3 },
          itemStyle: { color: "#0f62fe" },
        },
      ],
    },
  ],
}));

const loadAll = async () => {
  const [meRes, skillRes, profileRes] = await Promise.all([
    studentApi.me(),
    studentApi.listResource("skills"),
    studentApi.getProfile().catch(() => ({ data: null })),
  ]);
  Object.assign(form, meRes.data || {});
  form.interests = Array.isArray(meRes.data?.interests) ? meRes.data.interests : [];
  skills.value = skillRes.data || [];
  profile.value = profileRes.data || null;
};

const save = async () => {
  await studentApi.updateMe({ ...form, interests: form.interests || [] });
  ElMessage.success("学生档案已更新");
};

const generateProfile = async () => {
  generating.value = true;
  try {
    const res = await studentApi.generateProfile();
    profile.value = res.data || null;
    ElMessage.success("学生能力画像已生成");
  } finally {
    generating.value = false;
  }
};

const addSkill = async () => {
  const value = newSkill.value.trim();
  if (!value) return;
  await studentApi.createResource("skills", {
    name: value,
    level: "熟练",
    category: "技能",
  });
  newSkill.value = "";
  await loadAll();
  ElMessage.success("技能已加入档案");
};

const removeSkill = async (id) => {
  await studentApi.deleteResource("skills", id);
  await loadAll();
  ElMessage.success("技能已移除");
};

onMounted(loadAll);
</script>

<style scoped>
.archive-page {
  gap: 16px;
}

.header-actions,
.form-actions,
.skill-editor {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.metric-card :deep(.el-card__body) {
  padding: 14px 16px;
}

.metric-label {
  color: #6b7280;
  font-size: 12px;
}

.metric-value {
  margin-top: 8px;
  font-size: 28px;
  line-height: 1.1;
  font-weight: 700;
  color: #111827;
}

.metric-tip,
.section-tip {
  margin-top: 8px;
  color: #6b7280;
  line-height: 1.7;
  font-size: 13px;
}

.archive-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
  gap: 16px;
}

.form-grid {
  display: grid;
  gap: 14px;
}

.form-grid.three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.form-grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.form-actions {
  margin-top: 8px;
}

.profile-side {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.maturity-card {
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid #e3e9f3;
  background: linear-gradient(135deg, rgba(15, 98, 254, 0.08), rgba(0, 166, 166, 0.08));
}

.maturity-title,
.block-title {
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
}

.maturity-value {
  margin-top: 8px;
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
}

.maturity-desc {
  margin-top: 8px;
  line-height: 1.7;
  color: #475569;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.skill-tags {
  margin: 14px 0 16px;
}

.profile-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.insight-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.insight-card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid #e5ebf5;
}

.insight-card.strength {
  background: #f1f8f3;
}

.insight-card.weakness {
  background: #fff8f0;
}

.insight-item {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.72);
  color: #334155;
  line-height: 1.5;
}

.empty-state {
  min-height: 360px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  gap: 12px;
}

.empty-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}

.empty-desc {
  max-width: 520px;
  color: #64748b;
  line-height: 1.8;
}

@media (max-width: 1200px) {
  .archive-grid,
  .form-grid.three {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .archive-grid,
  .form-grid.two,
  .form-grid.three,
  .insight-grid {
    grid-template-columns: 1fr;
  }
}
</style>
