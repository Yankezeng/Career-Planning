import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@/layouts/MainLayout.vue": fileURLToPath(new URL("./src/layouts/MainLayoutAgent.vue", import.meta.url)),
      "@/views/assistant/AssistantHomeView.vue": fileURLToPath(new URL("./src/views/assistant/AssistantEnterpriseHomeView.vue", import.meta.url)),
      "@/views/auth/LoginView.vue": fileURLToPath(new URL("./src/views/auth/LoginEnterpriseView.vue", import.meta.url)),
      "@/views/dashboard/DashboardView.vue": fileURLToPath(new URL("./src/views/dashboard/DashboardRoleCenterView.vue", import.meta.url)),
      "@/views/enterprise/ResumeInboxView.vue": fileURLToPath(new URL("./src/views/enterprise/CandidateLibraryView.vue", import.meta.url)),
      "@/views/matches/MatchListView.vue": fileURLToPath(new URL("./src/views/matches/MatchCenterView.vue", import.meta.url)),
      "@/views/matches/MatchDetailView.vue": fileURLToPath(new URL("./src/views/matches/MatchCenterView.vue", import.meta.url)),
      "@/views/matches/GapAnalysisView.vue": fileURLToPath(new URL("./src/views/matches/MatchCenterView.vue", import.meta.url)),
      "@/views/matches/TopJobsView.vue": fileURLToPath(new URL("./src/views/matches/MatchCenterView.vue", import.meta.url)),
      "@/views/career/CareerGoalSettingView.vue": fileURLToPath(new URL("./src/views/career/CareerCenterView.vue", import.meta.url)),
      "@/views/career/PersonalizedPathView.vue": fileURLToPath(new URL("./src/views/career/CareerCenterView.vue", import.meta.url)),
      "@/views/career/LearningTasksView.vue": fileURLToPath(new URL("./src/views/career/CareerCenterView.vue", import.meta.url)),
      "@/views/career/SuggestionsView.vue": fileURLToPath(new URL("./src/views/career/CareerCenterView.vue", import.meta.url)),
      "@/views/growth/GrowthExecutionView.vue": fileURLToPath(new URL("./src/views/growth/GrowthCenterView.vue", import.meta.url)),
      "@/views/growth/GrowthSubmissionView.vue": fileURLToPath(new URL("./src/views/growth/GrowthCenterView.vue", import.meta.url)),
      "@/views/growth/StageReviewView.vue": fileURLToPath(new URL("./src/views/growth/GrowthCenterView.vue", import.meta.url)),
      "@/views/growth/OptimizationView.vue": fileURLToPath(new URL("./src/views/growth/GrowthCenterView.vue", import.meta.url)),
      "@/views/growth/GrowthTrendView.vue": fileURLToPath(new URL("./src/views/growth/GrowthCenterView.vue", import.meta.url)),
      "@/views/reports/ReportPreviewView.vue": fileURLToPath(new URL("./src/views/reports/ReportCenterView.vue", import.meta.url)),
      "@/views/reports/ReportExportView.vue": fileURLToPath(new URL("./src/views/reports/ReportCenterView.vue", import.meta.url)),
      "@/views/students/ResumeManagerView.vue": fileURLToPath(new URL("./src/views/students/ResumeSkillWorkbenchView.vue", import.meta.url)),
      "@/views/students/StudentBaseInfoView.vue": fileURLToPath(new URL("./src/views/students/StudentArchiveCenterView.vue", import.meta.url)),
      "@/views/students/ProjectManagerView.vue": fileURLToPath(new URL("./src/views/students/ResumeSkillWorkbenchView.vue", import.meta.url)),
      "@/views/students/InternshipManagerView.vue": fileURLToPath(new URL("./src/views/students/ResumeSkillWorkbenchView.vue", import.meta.url)),
      "@/views/students/AchievementManagerView.vue": fileURLToPath(new URL("./src/views/students/ResumeSkillWorkbenchView.vue", import.meta.url)),
      "@/views/profile/ProfileOverviewView.vue": fileURLToPath(new URL("./src/views/profile/ProfileInsightView.vue", import.meta.url)),
      "@/views/profile/RadarChartView.vue": fileURLToPath(new URL("./src/views/profile/ProfileInsightView.vue", import.meta.url)),
      "@/views/profile/StrengthWeaknessView.vue": fileURLToPath(new URL("./src/views/profile/ProfileInsightView.vue", import.meta.url)),
      "@/utils/menus": fileURLToPath(new URL("./src/utils/menusAgent.js", import.meta.url)),
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
});
