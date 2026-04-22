<template>
  <div class="login-page">
    <DynamicBackground :particle-count="150" primary-color="#00d4ff" secondary-color="#0066ff" :speed="0.3" />
    <div class="bg-orb orb-left"></div>
    <div class="bg-orb orb-right"></div>
    <div class="bg-grid"></div>

    <div class="login-shell">
      <section class="brand-panel">
        <div class="brand-top">
          <div class="brand-badge">Career Agent</div>
          <div class="brand-live">
            <span class="live-dot"></span>
            智能体在线
          </div>
        </div>

        <div class="hero-copy">
          <h1>大学生职业规划 AI 智能体系统</h1>
          <p class="hero-desc">
            围绕岗位知识库、学生画像、人岗匹配、成长反馈与企业投递形成闭环，适合课程设计、毕业答辩和项目演示。
          </p>
        </div>

        <div class="metric-grid">
          <div v-for="item in metrics" :key="item.label" class="metric-card">
            <div class="metric-icon">
              <component :is="item.icon" />
            </div>
            <el-statistic :value="item.value" :title="item.label" />
            <div class="metric-tip">{{ item.tip }}</div>
          </div>
        </div>

        <div class="capability-grid">
          <div v-for="item in highlights" :key="item.title" class="capability-card">
            <div class="capability-head">
              <el-avatar :size="42" class="capability-avatar">
                <component :is="item.icon" />
              </el-avatar>
              <div>
                <div class="capability-title">{{ item.title }}</div>
                <div class="capability-sub">{{ item.sub }}</div>
              </div>
            </div>
            <div class="capability-text">{{ item.text }}</div>
            <el-progress :percentage="item.progress" :stroke-width="8" :show-text="false" />
          </div>
        </div>

        <div class="workflow-card">
          <div class="workflow-top">
            <div class="workflow-title">主流程闭环</div>
            <div class="workflow-sub">从画像到投递再到企业复评</div>
          </div>
          <el-steps :active="7" finish-status="success" simple class="workflow-steps">
            <el-step title="岗位采集" />
            <el-step title="画像生成" />
            <el-step title="匹配分析" />
            <el-step title="成长规划" />
            <el-step title="简历优化" />
            <el-step title="一键投递" />
            <el-step title="企业复评" />
          </el-steps>
          <div class="workflow-tags">
            <el-tag v-for="item in workflowTags" :key="item" round effect="light">{{ item }}</el-tag>
          </div>
        </div>
      </section>

      <section class="auth-panel">
        <div class="auth-head">
          <div class="auth-eyebrow">统一认证入口</div>
          <h2>{{ authMode === 'login' ? '登录后进入对应角色工作台' : '注册后自动进入系统' }}</h2>
          <p>{{ authMode === 'login' ? '学生、企业、管理员会看到完全不同的界面与操作视角。' : '公开注册支持学生和企业账号，信息会直接写入当前业务数据库。' }}</p>
        </div>

        <div class="auth-mode-switch">
          <button type="button" :class="['mode-pill', { active: authMode === 'login' }]" @click="switchMode('login')">登录</button>
          <button type="button" :class="['mode-pill', { active: authMode === 'register' }]" @click="switchMode('register')">注册</button>
        </div>

        <el-tabs v-model="activePreset" class="role-tabs" @tab-change="handleRoleChange">
          <el-tab-pane v-for="account in displayAccountCards" :key="account.type" :name="account.type">
            <template #label>
              <span class="tab-label">
                <component :is="account.icon" />
                {{ account.label }}
              </span>
            </template>

            <div class="role-preview">
              <div class="role-preview-top">
                <el-avatar :size="48" class="role-avatar">
                  <component :is="account.icon" />
                </el-avatar>
                <div>
                  <div class="role-preview-title">{{ account.previewTitle }}</div>
                  <div class="role-preview-desc">{{ account.description }}</div>
                </div>
              </div>
              <div class="role-tag-list">
                <el-tag v-for="tag in account.tags" :key="tag" round effect="plain">{{ tag }}</el-tag>
              </div>
              <div v-if="authMode === 'login'" class="quick-account">
                <span>演示账号：</span>
                <strong>{{ account.username }}</strong>
                <span>/</span>
                <strong>{{ account.password }}</strong>
                <el-button text type="primary" @click="fillLogin(account.type)">一键填充</el-button>
              </div>
              <div v-else class="quick-account register-hint-row">
                <span>注册身份：</span>
                <strong>{{ account.label }}</strong>
                <span>·</span>
                <span>{{ account.registerTip }}</span>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>

        <div class="form-card">
          <el-form v-if="authMode === 'login'" ref="loginFormRef" :model="loginForm" :rules="loginRules" label-position="top" @submit.prevent="submitLogin">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="loginForm.username" size="large" clearable placeholder="请输入用户名">
                <template #prefix>
                  <el-icon><User /></el-icon>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item label="密码" prop="password">
              <el-input v-model="loginForm.password" size="large" type="password" show-password placeholder="请输入密码">
                <template #prefix>
                  <el-icon><Lock /></el-icon>
                </template>
              </el-input>
            </el-form-item>

            <div class="assist-row">
              <div class="assist-card">
                <div class="assist-title">进入后你会看到</div>
                <div class="assist-list">
                  <span v-for="item in currentPreviewPoints" :key="item" class="assist-pill">{{ item }}</span>
                </div>
              </div>
              <div class="assist-card mini-card">
                <div class="assist-title">推荐操作</div>
                <div class="assist-mini">{{ currentRecommendedAction }}</div>
              </div>
            </div>

            <div class="submit-row">
              <el-button class="ghost-btn" @click="fillLogin(activePreset)">填入当前角色账号</el-button>
              <el-button type="primary" size="large" class="submit-btn" @click="submitLogin">进入系统</el-button>
            </div>
          </el-form>

          <el-form v-else ref="registerFormRef" :model="registerForm" :rules="registerRules" label-position="top" @submit.prevent="submitRegister">
            <div class="register-grid two">
              <el-form-item label="用户名" prop="username">
                <el-input v-model="registerForm.username" size="large" clearable placeholder="设置登录用户名">
                  <template #prefix>
                    <el-icon><User /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="姓名 / 联系人" prop="real_name">
                <el-input v-model="registerForm.real_name" size="large" clearable placeholder="请输入姓名或企业联系人">
                  <template #prefix>
                    <el-icon><UserFilled /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
            </div>

            <div class="register-grid two">
              <el-form-item label="密码" prop="password">
                <el-input v-model="registerForm.password" size="large" type="password" show-password placeholder="至少 6 位密码">
                  <template #prefix>
                    <el-icon><Lock /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="确认密码" prop="confirm_password">
                <el-input v-model="registerForm.confirm_password" size="large" type="password" show-password placeholder="请再次输入密码">
                  <template #prefix>
                    <el-icon><Lock /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
            </div>

            <div class="register-grid two">
              <el-form-item label="邮箱" prop="email">
                <el-input v-model="registerForm.email" size="large" clearable placeholder="请输入邮箱">
                  <template #prefix>
                    <el-icon><Message /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="手机号" prop="phone">
                <el-input v-model="registerForm.phone" size="large" clearable placeholder="请输入手机号">
                  <template #prefix>
                    <el-icon><Phone /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
            </div>

            <template v-if="registerForm.role_code === 'student'">
              <div class="register-grid two">
                <el-form-item label="学号" prop="student_no">
                  <el-input v-model="registerForm.student_no" size="large" clearable placeholder="请输入学号">
                    <template #prefix>
                      <el-icon><School /></el-icon>
                    </template>
                  </el-input>
                </el-form-item>
                <el-form-item label="年级" prop="grade">
                  <el-input v-model="registerForm.grade" size="large" clearable placeholder="例如 2023 级" />
                </el-form-item>
              </div>
              <div class="register-grid two">
                <el-form-item label="专业" prop="major">
                  <el-input v-model="registerForm.major" size="large" clearable placeholder="请输入专业" />
                </el-form-item>
                <el-form-item label="学院" prop="college">
                  <el-input v-model="registerForm.college" size="large" clearable placeholder="请输入学院" />
                </el-form-item>
              </div>
            </template>

            <template v-else>
              <div class="register-grid two">
                <el-form-item label="企业名称" prop="company_name">
                  <el-input v-model="registerForm.company_name" size="large" clearable placeholder="请输入企业名称">
                    <template #prefix>
                      <el-icon><OfficeBuilding /></el-icon>
                    </template>
                  </el-input>
                </el-form-item>
                <el-form-item label="所属行业" prop="industry">
                  <el-input v-model="registerForm.industry" size="large" clearable placeholder="请输入所属行业" />
                </el-form-item>
              </div>
              <div class="register-grid two">
                <el-form-item label="企业类型" prop="company_type">
                  <el-input v-model="registerForm.company_type" size="large" clearable placeholder="例如 科技公司 / 国企" />
                </el-form-item>
                <el-form-item label="企业规模" prop="company_size">
                  <el-input v-model="registerForm.company_size" size="large" clearable placeholder="例如 50-150 人" />
                </el-form-item>
              </div>
              <el-form-item label="企业地址" prop="address">
                <el-input v-model="registerForm.address" size="large" clearable placeholder="请输入企业地址" />
              </el-form-item>
            </template>

            <div class="assist-row register-assist-row">
              <div class="assist-card">
                <div class="assist-title">注册完成后会创建</div>
                <div class="assist-list">
                  <span v-for="item in registerCreatePoints" :key="item" class="assist-pill">{{ item }}</span>
                </div>
              </div>
              <div class="assist-card mini-card">
                <div class="assist-title">数据库写入说明</div>
                <div class="assist-mini">账号信息会写入当前配置的业务数据库；如果你当前后端连的是 MySQL，就会直接写入 MySQL。</div>
              </div>
            </div>

            <div class="submit-row">
              <el-button class="ghost-btn" @click="resetRegister">重置填写</el-button>
              <el-button type="primary" size="large" class="submit-btn" @click="submitRegister">注册并进入系统</el-button>
            </div>
          </el-form>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, markRaw, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";
import DynamicBackground from "@/components/common/DynamicBackground.vue";
import {
  Connection,
  Cpu,
  DataAnalysis,
  Lock,
  Management,
  Message,
  Monitor,
  OfficeBuilding,
  Phone,
  Promotion,
  School,
  TrendCharts,
  User,
  UserFilled,
} from "@element-plus/icons-vue";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();
const loginFormRef = ref();
const registerFormRef = ref();
const authMode = ref("login");
const activePreset = ref("student");

const loginForm = reactive({
  username: "student01",
  password: "student123",
});

const createRegisterForm = () => ({
  role_code: "student",
  username: "",
  real_name: "",
  password: "",
  confirm_password: "",
  email: "",
  phone: "",
  student_no: "",
  grade: "",
  major: "",
  college: "",
  company_name: "",
  company_type: "",
  company_size: "",
  industry: "",
  address: "",
});

const registerForm = reactive(createRegisterForm());

const accountCards = [
  {
    type: "student",
    label: "学生端",
    username: "student01",
    password: "student123",
    icon: markRaw(UserFilled),
    previewTitle: "学生成长驾驶舱",
    description: "体验画像、匹配、成长规划、简历管理与一键投递。",
    tags: ["画像生成", "成长路径", "简历管理", "企业投递"],
    points: ["深色成长主页", "岗位推荐", "简历管理"],
    recommend: "先生成画像，再查看匹配结果和成长路径。",
    registerTip: "创建学生账号，并初始化学生档案。",
  },
  {
    type: "enterprise",
    label: "企业端",
    username: "enterprise01",
    password: "enterprise123",
    icon: markRaw(OfficeBuilding),
    previewTitle: "企业人才筛选工作台",
    description: "查看简历投递箱、候选人画像摘要、简历预览与企业复评。",
    tags: ["候选人池", "简历预览", "筛选工作台", "企业复评"],
    points: ["候选人列表", "右侧简历预览", "专业分布统计"],
    recommend: "先看高匹配候选人，再进入简历预览和复评。",
    registerTip: "创建企业账号，并初始化企业档案。",
  },
  {
    type: "admin",
    label: "管理员端",
    username: "admin",
    password: "admin123",
    icon: markRaw(Management),
    previewTitle: "平台中控驾驶舱",
    description: "查看业务库、Milvus 知识库、用户数量、投递闭环与系统状态。",
    tags: ["系统运行状态", "MySQL 状态", "Milvus 状态", "全局治理"],
    points: ["中控驾驶舱", "角色分布", "数据库状态卡"],
    recommend: "优先展示中控首页，再切换到企业端闭环。",
    registerTip: "管理员账号仅支持后台预置，不开放公开注册。",
  },
];

const presets = {
  student: { username: "student01", password: "student123" },
  enterprise: { username: "enterprise01", password: "enterprise123" },
  admin: { username: "admin", password: "admin123" },
};

const metrics = [
  { label: "角色端", value: 3, tip: "学生 / 企业 / 管理员", icon: markRaw(Monitor) },
  { label: "核心闭环", value: 8, tip: "覆盖完整求职成长链路", icon: markRaw(Connection) },
  { label: "智能能力", value: 6, tip: "画像、匹配、规划、优化等", icon: markRaw(Cpu) },
];

const highlights = [
  {
    title: "岗位知识库",
    sub: "Milvus 向量检索",
    text: "支持岗位画像、岗位关系图谱与向量知识库检索联动。",
    progress: 92,
    icon: markRaw(DataAnalysis),
  },
  {
    title: "学生智能画像",
    sub: "六维能力建模",
    text: "自动生成学生六维能力画像、差距项和成长趋势。",
    progress: 89,
    icon: markRaw(TrendCharts),
  },
  {
    title: "简历管理",
    sub: "文档与图片简历",
    text: "支持文档简历、图片简历识别、简历优化和 Word 导出。",
    progress: 87,
    icon: markRaw(Promotion),
  },
  {
    title: "企业协同闭环",
    sub: "投递到复评",
    text: "学生可一键投递简历，企业端直接查看候选人并复评。",
    progress: 90,
    icon: markRaw(OfficeBuilding),
  },
];

const workflowTags = ["岗位画像", "学生画像", "匹配分析", "成长规划", "简历优化", "企业投递", "复评优化"];

const loginRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};

const validateConfirmPassword = (_, value, callback) => {
  if (!value) return callback(new Error("请再次输入密码"));
  if (value !== registerForm.password) return callback(new Error("两次输入的密码不一致"));
  callback();
};

const registerRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  real_name: [{ required: true, message: "请输入姓名或联系人", trigger: "blur" }],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    { min: 6, message: "密码至少 6 位", trigger: "blur" },
  ],
  confirm_password: [{ validator: validateConfirmPassword, trigger: "blur" }],
  student_no: [
    {
      validator: (_, value, callback) => {
        if (registerForm.role_code !== "student") return callback();
        if (!value) return callback(new Error("请输入学号"));
        callback();
      },
      trigger: "blur",
    },
  ],
  company_name: [
    {
      validator: (_, value, callback) => {
        if (registerForm.role_code !== "enterprise") return callback();
        if (!value) return callback(new Error("请输入企业名称"));
        callback();
      },
      trigger: "blur",
    },
  ],
};

const displayAccountCards = computed(() =>
  authMode.value === "register" ? accountCards.filter((item) => item.type !== "admin") : accountCards
);
const currentAccount = computed(() => displayAccountCards.value.find((item) => item.type === activePreset.value) || displayAccountCards.value[0]);
const currentPreviewPoints = computed(() => currentAccount.value?.points || []);
const currentRecommendedAction = computed(() => currentAccount.value?.recommend || "登录后查看系统核心能力。");
const registerCreatePoints = computed(() =>
  registerForm.role_code === "student"
    ? ["users 用户表", "students 学生表", "JWT 登录态"]
    : ["users 用户表", "enterprise_profiles 企业表", "JWT 登录态"]
);

const fillLogin = (type) => {
  activePreset.value = type;
  Object.assign(loginForm, presets[type]);
};

const resetRegister = () => {
  Object.assign(registerForm, createRegisterForm(), { role_code: registerForm.role_code });
};

const switchMode = (mode) => {
  authMode.value = mode;
  if (mode === "register" && activePreset.value === "admin") {
    activePreset.value = "student";
  }
  if (mode === "register") {
    registerForm.role_code = activePreset.value;
  }
};

const handleRoleChange = (name) => {
  activePreset.value = name;
  if (authMode.value === "login") {
    fillLogin(name);
  } else {
    registerForm.role_code = name;
  }
};

const submitLogin = async () => {
  const valid = await loginFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  await auth.login(loginForm);
  ElMessage.success("登录成功，已进入对应角色工作台");
  router.push("/assistant");
};

const submitRegister = async () => {
  const valid = await registerFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  const payload = {
    username: registerForm.username,
    password: registerForm.password,
    real_name: registerForm.real_name,
    role_code: registerForm.role_code,
    email: registerForm.email,
    phone: registerForm.phone,
    student_no: registerForm.student_no,
    grade: registerForm.grade,
    major: registerForm.major,
    college: registerForm.college,
    company_name: registerForm.company_name,
    company_type: registerForm.company_type,
    company_size: registerForm.company_size,
    industry: registerForm.industry,
    address: registerForm.address,
  };
  await auth.register(payload);
  ElMessage.success("注册成功，账号信息已写入业务数据库");
  router.push("/assistant");
};
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  padding: 24px;
  background:
    radial-gradient(circle at 10% 12%, rgba(56, 189, 248, 0.12), transparent 22%),
    radial-gradient(circle at 86% 18%, rgba(216, 239, 227, 0.92), transparent 18%),
    linear-gradient(135deg, #eef4f2 0%, #f4f8f6 38%, #edf3f8 100%);
}

.bg-orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(16px);
  pointer-events: none;
}

.orb-left {
  left: -120px;
  bottom: -120px;
  width: 340px;
  height: 340px;
  background: radial-gradient(circle, rgba(91, 192, 190, 0.24), rgba(91, 192, 190, 0.02));
}

.orb-right {
  right: -80px;
  top: -120px;
  width: 360px;
  height: 360px;
  background: radial-gradient(circle, rgba(56, 189, 248, 0.18), rgba(56, 189, 248, 0.02));
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgba(255, 255, 255, 0.24) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 0.24) 1px, transparent 1px);
  background-size: 32px 32px;
  opacity: 0.26;
  mask-image: radial-gradient(circle at center, #000 38%, transparent 92%);
  pointer-events: none;
}

.login-shell {
  position: relative;
  z-index: 1;
  width: min(1320px, 100%);
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1.08fr 0.92fr;
  gap: 24px;
}

.brand-panel,
.auth-panel {
  border-radius: 32px;
  overflow: hidden;
  box-shadow: 0 28px 80px rgba(15, 23, 42, 0.12);
}

.brand-panel {
  padding: 34px;
  color: #fff;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0)),
    linear-gradient(145deg, #0b132b 0%, #1c2541 48%, #3a506b 100%);
}

.brand-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.brand-badge,
.brand-live,
.auth-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 12px;
  letter-spacing: 0.08em;
}

.brand-badge,
.brand-live {
  background: rgba(111, 255, 233, 0.12);
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #6fffe9;
  box-shadow: 0 0 0 6px rgba(111, 255, 233, 0.16);
}

.hero-copy h1 {
  margin: 22px 0 14px;
  font-size: 46px;
  line-height: 1.1;
}

.hero-desc {
  max-width: 580px;
  margin: 0;
  font-size: 17px;
  line-height: 1.9;
  color: rgba(255, 255, 255, 0.86);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 28px;
}

.metric-card {
  padding: 18px;
  border-radius: 22px;
  background: rgba(111, 255, 233, 0.08);
  border: 1px solid rgba(111, 255, 233, 0.14);
}

.metric-icon {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: rgba(111, 255, 233, 0.14);
  margin-bottom: 8px;
}

.metric-tip {
  margin-top: 8px;
  color: rgba(255, 255, 255, 0.72);
  font-size: 12px;
  line-height: 1.7;
}

.capability-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.capability-card {
  padding: 18px;
  border-radius: 24px;
  background: rgba(111, 255, 233, 0.08);
  border: 1px solid rgba(111, 255, 233, 0.14);
}

.capability-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.capability-avatar {
  background: rgba(111, 255, 233, 0.14);
  color: #fff;
}

.capability-title {
  font-size: 17px;
  font-weight: 700;
}

.capability-sub {
  margin-top: 4px;
  color: rgba(255, 255, 255, 0.72);
  font-size: 12px;
}

.capability-text {
  margin: 14px 0 12px;
  color: rgba(255, 255, 255, 0.82);
  line-height: 1.78;
}

.workflow-card {
  margin-top: 22px;
  padding: 22px;
  border-radius: 28px;
  background: rgba(11, 19, 43, 0.26);
  border: 1px solid rgba(111, 255, 233, 0.12);
}

.workflow-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.workflow-title {
  font-size: 16px;
  font-weight: 700;
}

.workflow-sub {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.74);
}

.workflow-steps {
  margin-top: 16px;
  border-radius: 18px;
  background: rgba(111, 255, 233, 0.08);
}

.workflow-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.auth-panel {
  padding: 30px;
  background: rgba(246, 251, 248, 0.94);
  backdrop-filter: blur(16px);
}

.auth-eyebrow {
  background: rgba(216, 239, 227, 0.9);
  color: #24544d;
}

.auth-head h2 {
  margin: 12px 0 8px;
  font-size: 30px;
  color: #0f172a;
}

.auth-head p {
  margin: 0;
  color: #5d7a74;
  line-height: 1.8;
}

.auth-mode-switch {
  display: inline-flex;
  gap: 8px;
  padding: 6px;
  margin-top: 20px;
  border-radius: 999px;
  background: #e8f2ed;
}

.mode-pill {
  border: none;
  background: transparent;
  color: #5d7a74;
  padding: 10px 18px;
  border-radius: 999px;
  font-weight: 700;
  cursor: pointer;
}

.mode-pill.active {
  background: linear-gradient(135deg, #24544d, #5bc0be);
  color: #fff;
  box-shadow: 0 12px 24px rgba(36, 84, 77, 0.16);
}

.role-tabs {
  margin-top: 22px;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.role-preview {
  padding: 18px;
  border-radius: 24px;
  background: linear-gradient(180deg, #f6fbf8, #edf5f0);
  border: 1px solid #d8e8e1;
}

.role-preview-top {
  display: flex;
  align-items: center;
  gap: 14px;
}

.role-avatar {
  background: linear-gradient(135deg, #3a506b, #5bc0be);
  color: #fff;
}

.role-preview-title {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.role-preview-desc {
  margin-top: 6px;
  color: #5d7a74;
  line-height: 1.7;
}

.role-tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.quick-account {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
  color: #5d7a74;
}

.quick-account strong {
  color: #0f172a;
}

.form-card {
  margin-top: 18px;
  padding: 20px;
  border-radius: 26px;
  background: #fdfefd;
  border: 1px solid #dde9e4;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.register-grid {
  display: grid;
  gap: 14px;
}

.register-grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.assist-row {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 12px;
  margin-top: 8px;
}

.assist-card {
  padding: 14px 16px;
  border-radius: 20px;
  background: #f3f8f5;
  border: 1px solid #dbe8e2;
}

.assist-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.assist-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.assist-pill {
  padding: 8px 12px;
  border-radius: 999px;
  background: #d8efe3;
  color: #24544d;
  font-size: 12px;
  font-weight: 600;
}

.assist-mini {
  margin-top: 10px;
  color: #5d7a74;
  line-height: 1.8;
}

.submit-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 18px;
}

.ghost-btn {
  border-radius: 999px;
}

.submit-btn {
  min-width: 200px;
  border: none;
  border-radius: 999px;
  background: linear-gradient(135deg, #24544d, #5bc0be);
  box-shadow: 0 20px 40px rgba(36, 84, 77, 0.16);
}

:deep(.el-statistic__head) {
  color: rgba(255, 255, 255, 0.76);
}

:deep(.el-statistic__content) {
  color: #ffffff;
}

:deep(.el-step.is-simple .el-step__title) {
  color: #fff;
}

:deep(.role-tabs .el-tabs__nav-wrap::after) {
  background-color: #dbe8e2;
}

@media (max-width: 1100px) {
  .login-shell,
  .assist-row,
  .metric-grid,
  .capability-grid,
  .register-grid.two {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .login-page {
    padding: 14px;
  }

  .brand-panel,
  .auth-panel {
    padding: 22px;
  }

  .hero-copy h1 {
    font-size: 34px;
  }

  .workflow-top,
  .submit-row,
  .brand-top {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
