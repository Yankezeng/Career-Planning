import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const redirectWithQuery = (path, extraQuery = {}) => (to) => ({
  path,
  query: { ...to.query, ...extraQuery },
});

const routes = [
  {
    path: "/",
    component: () => import("@/views/home/HomeMiniMaxView.vue"),
    meta: { public: true, title: "首页" },
  },
  {
    path: "/assistant",
    component: () => import("@/views/home/HomeMiniMaxView.vue"),
    meta: { title: "AI 对话首页", roles: ["student", "enterprise", "admin"] },
  },
  {
    path: "/assistant/enterprise",
    redirect: "/assistant",
    meta: { title: "AI 对话首页", roles: ["student", "enterprise", "admin"] },
  },
  {
    path: "/login",
    redirect: { path: "/", query: { login: "1" } },
    meta: { public: true, title: "登录" },
  },
  {
    path: "/app-shell",
    component: () => import("@/layouts/MainLayoutAgent.vue"),
    redirect: "/dashboard",
    children: [
      { path: "/assistant/skills/resume-workbench", redirect: redirectWithQuery("/student/resume"), meta: { title: "简历管理", roles: ["student"] } },
      { path: "/dashboard", component: () => import("@/views/dashboard/DashboardRoleCenterView.vue"), meta: { title: "中控台", roles: ["admin", "student", "enterprise"] } },
      { path: "/jobs", component: () => import("@/views/jobs/JobListView.vue"), meta: { title: "岗位知识库", roles: ["admin", "student", "enterprise"] } },
      { path: "/jobs/create", component: () => import("@/views/jobs/JobFormView.vue"), meta: { title: "新增 / 编辑岗位", roles: ["admin"] } },
      { path: "/jobs/detail", component: () => import("@/views/jobs/JobDetailView.vue"), meta: { title: "岗位详情", roles: ["admin", "student", "enterprise"] } },
      { path: "/jobs/profile", component: () => import("@/views/jobs/JobProfileView.vue"), meta: { title: "岗位画像", roles: ["admin", "student", "enterprise"] } },
      { path: "/graph/relations", component: () => import("@/views/graph/JobRelationGraphView.vue"), meta: { title: "岗位图谱中心", roles: ["admin", "enterprise"] } },
      { path: "/graph/path", component: () => import("@/views/graph/JobDevelopmentPathView.vue"), meta: { title: "岗位发展路径", roles: ["admin", "student", "enterprise"] } },
      { path: "/graph/skills", component: () => import("@/views/graph/JobSkillRelationView.vue"), meta: { title: "岗位技能关联", roles: ["admin", "student", "enterprise"] } },
      { path: "/student/archive", component: () => import("@/views/students/StudentArchiveCenterView.vue"), meta: { title: "学生档案中心", roles: ["student"] } },
      { path: "/student/base", redirect: redirectWithQuery("/student/archive"), meta: { title: "学生档案中心", roles: ["student"] } },
      { path: "/student/resume", component: () => import("@/views/students/ResumeSkillWorkbenchView.vue"), meta: { title: "简历管理", roles: ["student"] } },
      { path: "/student/resume-delivery", component: () => import("@/views/students/StudentResumeDeliveryView.vue"), meta: { title: "投递简历", roles: ["student"] } },
      { path: "/student/job-graph", component: () => import("@/views/students/StudentJobGraphCenterView.vue"), meta: { title: "岗位图谱中心", roles: ["student"] } },
      { path: "/student/projects", redirect: redirectWithQuery("/student/resume", { tab: "experience" }), meta: { title: "简历管理", roles: ["student"] } },
      { path: "/student/internships", redirect: redirectWithQuery("/student/resume", { tab: "experience" }), meta: { title: "简历管理", roles: ["student"] } },
      { path: "/student/achievements", redirect: redirectWithQuery("/student/resume", { tab: "achievement" }), meta: { title: "简历管理", roles: ["student"] } },
      { path: "/student/attachments", redirect: redirectWithQuery("/student/resume", { tab: "resume" }), meta: { title: "简历管理", roles: ["student"] } },
      { path: "/profile/insight", component: () => import("@/views/profile/ProfileInsightView.vue"), meta: { title: "能力综合分析", roles: ["student", "enterprise"] } },
      { path: "/profile/overview", redirect: redirectWithQuery("/profile/insight"), meta: { title: "能力综合分析", roles: ["student", "enterprise"] } },
      { path: "/profile/radar", redirect: redirectWithQuery("/profile/insight"), meta: { title: "能力综合分析", roles: ["student", "enterprise"] } },
      { path: "/profile/analysis", redirect: redirectWithQuery("/profile/insight"), meta: { title: "能力综合分析", roles: ["student", "enterprise"] } },
      { path: "/matches/center", component: () => import("@/views/matches/MatchCenterView.vue"), meta: { title: "人岗匹配工作台", roles: ["student", "enterprise"] } },
      { path: "/matches/list", redirect: redirectWithQuery("/matches/center", { tab: "overview" }), meta: { title: "人岗匹配工作台", roles: ["student", "enterprise"] } },
      { path: "/matches/detail", redirect: redirectWithQuery("/matches/center", { tab: "detail" }), meta: { title: "人岗匹配工作台", roles: ["student", "enterprise"] } },
      { path: "/matches/gaps", redirect: redirectWithQuery("/matches/center", { tab: "gaps" }), meta: { title: "人岗匹配工作台", roles: ["student", "enterprise"] } },
      { path: "/matches/top", redirect: redirectWithQuery("/matches/center", { tab: "overview" }), meta: { title: "人岗匹配工作台", roles: ["student", "enterprise"] } },
      { path: "/career/center", component: () => import("@/views/career/CareerCenterView.vue"), meta: { title: "职业规划工作台", roles: ["admin", "student", "enterprise"] } },
      { path: "/career/goals", redirect: redirectWithQuery("/career/center", { tab: "goal" }), meta: { title: "职业规划工作台", roles: ["student"] } },
      { path: "/career/path", redirect: redirectWithQuery("/career/center", { tab: "path" }), meta: { title: "职业规划工作台", roles: ["admin", "student", "enterprise"] } },
      { path: "/career/tasks", redirect: redirectWithQuery("/career/center", { tab: "tasks" }), meta: { title: "职业规划工作台", roles: ["student"] } },
      { path: "/career/suggestions", redirect: redirectWithQuery("/career/center", { tab: "suggestions" }), meta: { title: "职业规划工作台", roles: ["student"] } },
      { path: "/growth/center", component: () => import("@/views/growth/GrowthCenterView.vue"), meta: { title: "成长跟踪工作台", roles: ["student"] } },
      { path: "/growth/execution", redirect: redirectWithQuery("/growth/center", { tab: "execution" }), meta: { title: "成长跟踪工作台", roles: ["student"] } },
      { path: "/growth/submission", redirect: redirectWithQuery("/growth/center", { tab: "submission" }), meta: { title: "成长跟踪工作台", roles: ["student"] } },
      { path: "/growth/review", redirect: redirectWithQuery("/growth/center", { tab: "review" }), meta: { title: "成长跟踪工作台", roles: ["student"] } },
      { path: "/growth/optimization", redirect: redirectWithQuery("/growth/center", { tab: "optimization" }), meta: { title: "成长跟踪工作台", roles: ["student"] } },
      { path: "/growth/trend", redirect: redirectWithQuery("/growth/center", { tab: "trend" }), meta: { title: "成长跟踪工作台", roles: ["student"] } },
      { path: "/willingness/analysis", component: () => import("@/views/willingness/WillingnessAnalysisView.vue"), meta: { title: "就业意愿分析", roles: ["student"] } },
      { path: "/capability/analysis", component: () => import("@/views/capability/CapabilityAnalysisView.vue"), meta: { title: "岗位能力拆解", roles: ["student"] } },
      { path: "/action/plan", component: () => import("@/views/action/ActionPlanView.vue"), meta: { title: "行动计划", roles: ["student"] } },
      { path: "/personalized/plan", component: () => import("@/views/personalized/PersonalizedPlanView.vue"), meta: { title: "个性化方案", roles: ["student"] } },
      { path: "/enterprise/deliveries", component: () => import("@/views/enterprise/CandidateLibraryView.vue"), meta: { title: "企业简历中心", roles: ["enterprise"] } },
      { path: "/admin/users", component: () => import("@/views/admin/UserManagementView.vue"), meta: { title: "用户管理", roles: ["admin"] } },
      { path: "/admin/org", component: () => import("@/views/admin/OrganizationView.vue"), meta: { title: "班级 / 院系管理", roles: ["admin"] } },
      { path: "/admin/tags", component: () => import("@/views/admin/JobTagManagementView.vue"), meta: { title: "岗位标签管理", roles: ["admin"] } },
      { path: "/admin/llm-monitor", component: () => import("@/views/admin/AdminLlmMonitorView.vue"), meta: { title: "模型监控", roles: ["admin"] } },
      { path: "/admin/configs", component: () => import("@/views/admin/SystemConfigView.vue"), meta: { title: "系统参数配置", roles: ["admin"] } },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (to.meta.public) return true;
  if (!auth.isLoggedIn) return "/login";

  if (!auth.user) {
    try {
      await auth.fetchMe();
    } catch (_) {
      auth.logout();
      return "/login";
    }
  }

  if (to.meta.roles && !to.meta.roles.includes(auth.role)) return auth.role === "admin" ? "/dashboard" : "/assistant";
  return true;
});

export default router;
