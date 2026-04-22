export const menuGroups = [
  {
    title: "AI 工作台",
    items: [{ path: "/assistant", label: "AI 对话首页", roles: ["student", "enterprise", "admin"] }],
  },
  {
    title: "学生工作台",
    items: [
      { path: "/student/resume", label: "简历管理", roles: ["student"] },
      { path: "/student/resume-delivery", label: "投递简历", roles: ["student"] },
      { path: "/matches/center", label: "人岗匹配", roles: ["student"] },
      { path: "/student/job-graph", label: "岗位图谱中心", roles: ["student"] },
      { path: "/career/center", label: "职业规划", roles: ["student"] },
    ],
  },
  {
    title: "企业工作台",
    items: [
      { path: "/enterprise/deliveries", label: "企业简历中心", roles: ["enterprise"] },
      { path: "/dashboard", label: "企业仪表盘", roles: ["enterprise"] },
      { path: "/graph/relations", label: "岗位关系图谱", roles: ["enterprise"] },
    ],
  },
  {
    title: "管理工作台",
    items: [
      { path: "/dashboard", label: "系统中控台", roles: ["admin"] },
      { path: "/admin/llm-monitor", label: "模型监控", roles: ["admin"] },
      { path: "/jobs", label: "岗位知识库", roles: ["admin"] },
      { path: "/graph/relations", label: "岗位关系图谱", roles: ["admin"] },
      { path: "/admin/configs", label: "系统参数配置", roles: ["admin"] },
    ],
  },
];

export const assistantWorkspaceRoutes = {
  search: "/assistant?panel=search",
  assets: "/assistant?panel=assets",
  gallery: "/assistant?panel=gallery",
};
