<template>
  <el-drawer :model-value="visible" size="42%" :with-header="false" @close="$emit('update:visible', false)">
    <div class="drawer-head">
      <div class="title">{{ card?.title || "详情" }}</div>
      <el-button text @click="$emit('update:visible', false)">关闭</el-button>
    </div>
    <component :is="panelComponent" :card="card || {}" />
  </el-drawer>
</template>

<script setup>
import { computed } from "vue";
import CandidateRankPanel from "./panels/CandidateRankPanel.vue";
import GapAnalysisPanel from "./panels/GapAnalysisPanel.vue";
import GrowthPathPanel from "./panels/GrowthPathPanel.vue";
import MatchOverviewPanel from "./panels/MatchOverviewPanel.vue";
import ProfileSummaryPanel from "./panels/ProfileSummaryPanel.vue";
import ReportPreviewPanel from "./panels/ReportPreviewPanel.vue";

const props = defineProps({
  visible: { type: Boolean, default: false },
  card: { type: Object, default: () => ({}) },
});

defineEmits(["update:visible"]);

const panelComponent = computed(() => {
  const type = props.card?.type;
  if (type === "profile_card") return ProfileSummaryPanel;
  if (type === "match_card") return MatchOverviewPanel;
  if (type === "gap_card") return GapAnalysisPanel;
  if (type === "growth_card") return GrowthPathPanel;
  if (type === "report_card") return ReportPreviewPanel;
  if (type === "candidate_rank_card") return CandidateRankPanel;
  return ProfileSummaryPanel;
});
</script>

<style scoped>
.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}
</style>