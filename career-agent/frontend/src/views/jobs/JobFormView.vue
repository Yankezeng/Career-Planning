<template>
  <div class="page-shell">
    <PageHeader title="新增/编辑岗位页" description="支持手动维护岗位画像，并可调用 Mock AI 自动生成结构化岗位画像。">
      <el-button v-if="jobId" type="success" @click="generateAI">AI 生成岗位画像</el-button>
      <el-button type="primary" @click="save">保存岗位</el-button>
    </PageHeader>
    <SectionCard>
      <el-form :model="form" label-position="top">
        <div class="two-col">
          <el-form-item label="岗位名称"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="岗位类别"><el-input v-model="form.category" /></el-form-item>
          <el-form-item label="所属行业"><el-input v-model="form.industry" /></el-form-item>
          <el-form-item label="薪资区间"><el-input v-model="form.salary_range" /></el-form-item>
        </div>
        <el-form-item label="岗位描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <div class="three-col">
          <el-form-item label="学历要求"><el-input v-model="form.degree_requirement" /></el-form-item>
          <el-form-item label="专业要求"><el-input v-model="form.major_requirement" /></el-form-item>
          <el-form-item label="实习要求"><el-input v-model="form.internship_requirement" /></el-form-item>
        </div>
        <el-form-item label="工作内容"><el-input v-model="form.work_content" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="发展方向"><el-input v-model="form.development_direction" type="textarea" :rows="2" /></el-form-item>
        <div class="three-col">
          <el-form-item label="核心技能标签（逗号分隔）"><el-input v-model="coreSkillText" /></el-form-item>
          <el-form-item label="通用能力标签（逗号分隔）"><el-input v-model="commonSkillText" /></el-form-item>
          <el-form-item label="证书要求（逗号分隔）"><el-input v-model="certificateText" /></el-form-item>
        </div>
      </el-form>
    </SectionCard>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive } from "vue";
import { ElMessage } from "element-plus";
import { useRoute, useRouter } from "vue-router";
import { jobApi } from "@/api";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";

const route = useRoute();
const router = useRouter();
const jobId = computed(() => route.query.id);
const form = reactive({
  name: "",
  category: "",
  industry: "",
  description: "",
  degree_requirement: "",
  major_requirement: "",
  internship_requirement: "",
  work_content: "",
  development_direction: "",
  salary_range: "",
  skill_weight: 0.4,
  certificate_weight: 0.1,
  project_weight: 0.2,
  soft_skill_weight: 0.1,
  core_skill_tags: [],
  common_skill_tags: [],
  certificate_tags: [],
  job_profile: {},
  skills: [],
  certificates: [],
});

const listToText = (list) => (list || []).join(", ");
const textToList = (text) => text.split(",").map((item) => item.trim()).filter(Boolean);

const coreSkillText = computed({
  get: () => listToText(form.core_skill_tags),
  set: (val) => (form.core_skill_tags = textToList(val)),
});
const commonSkillText = computed({
  get: () => listToText(form.common_skill_tags),
  set: (val) => (form.common_skill_tags = textToList(val)),
});
const certificateText = computed({
  get: () => listToText(form.certificate_tags),
  set: (val) => (form.certificate_tags = textToList(val)),
});

const syncNested = () => {
  form.skills = form.core_skill_tags.map((name) => ({ name, importance: 5, category: "核心技能" }));
  form.certificates = form.certificate_tags.map((name) => ({ name, importance: 4 }));
};

const load = async () => {
  if (!jobId.value) return;
  const res = await jobApi.detail(jobId.value);
  Object.assign(form, res.data);
};

const save = async () => {
  syncNested();
  let savedId;
  if (jobId.value) {
    await jobApi.update(jobId.value, form);
    savedId = Number(jobId.value);
  } else {
    const res = await jobApi.create(form);
    router.replace(`/jobs/create?id=${res.data.id}`);
    savedId = res.data.id;
  }
  ElMessage.success("保存成功");
  return savedId;
};

const generateAI = async () => {
  const id = await save();
  const res = await jobApi.generateProfile(id);
  Object.assign(form, res.data);
  ElMessage.success("AI 画像已生成");
};

onMounted(load);
</script>
