<template>
  <div class="career-path-graph">
    <div v-if="loading" class="path-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>生成职业发展路径...</span>
    </div>
    <div v-else-if="pathData" class="path-content">
      <div class="path-header">
        <h3 class="path-title">{{ pathData.target_job_name || "职业发展路径" }}</h3>
        <div class="path-stats">
          <el-tag type="success" effect="plain">晋升阶段 {{ verticalPath.length }}</el-tag>
          <el-tag v-if="transferPaths.length" type="warning" effect="plain">转岗方向 {{ transferPaths.length }}</el-tag>
          <el-tag type="info" effect="plain">任务数 {{ tasks.length }}</el-tag>
        </div>
      </div>

      <div class="path-canvas-wrapper">
        <div ref="chartRef" class="path-canvas"></div>
      </div>

      <div class="path-legend">
        <span class="legend-title">节点说明：</span>
        <span class="legend-item"><span class="legend-dot current"></span>当前目标</span>
        <span class="legend-item"><span class="legend-dot promotion"></span>晋升节点</span>
        <span class="legend-item"><span class="legend-dot transfer"></span>转岗方向</span>
      </div>

      <div class="path-tasks-section">
        <h4 class="tasks-title">成长任务清单</h4>
        <div class="task-list">
          <div v-for="(task, idx) in sortedTasks" :key="task.id || idx" class="task-card" :class="`priority-${task.priority}`">
            <div class="task-header">
              <el-tag :type="taskCategoryType(task.category)" size="small">{{ task.category }}</el-tag>
              <span class="task-stage">{{ task.stage_label }}</span>
              <el-tag v-if="task.difficulty_level" :type="taskDifficultyType(task.difficulty_level)" size="small">
                {{ task.difficulty_level }}难度
              </el-tag>
            </div>
            <div class="task-title">{{ task.title }}</div>
            <div v-if="task.description" class="task-desc">{{ task.description }}</div>
            <div v-if="task.related_skills && task.related_skills.length" class="task-skills">
              <el-tag v-for="skill in task.related_skills" :key="skill" size="small" effect="plain">{{ skill }}</el-tag>
            </div>
            <div v-if="task.weekly_tasks && task.weekly_tasks.length" class="task-weekly">
              <span class="weekly-label">每周行动：</span>
              <span v-for="(wt, wi) in task.weekly_tasks" :key="wi" class="weekly-item">{{ wt }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <el-empty v-else description="暂无职业路径数据，请先生成路径" />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Loading } from "@element-plus/icons-vue";
import * as echarts from "echarts";

const props = defineProps({
  pathData: { type: Object, default: null },
  loading: { type: Boolean, default: false },
});

const chartRef = ref();
let chart;
let resizeObserver;

const verticalPath = computed(() => props.pathData?.vertical_path || []);
const transferPaths = computed(() => props.pathData?.transfer_paths || []);
const tasks = computed(() => props.pathData?.tasks || []);

const sortedTasks = computed(() => {
  return [...tasks.value].sort((a, b) => (a.priority || 3) - (b.priority || 3));
});

const taskCategoryType = (cat) => {
  const map = { 学习: "primary", 项目: "success", 实习: "warning", 证书: "info" };
  return map[cat] || "";
};

const taskDifficultyType = (level) => {
  const map = { 高: "danger", 中: "warning", 低: "success" };
  return map[level] || "";
};

const buildGraphNodesAndLinks = () => {
  const nodes = [];
  const links = [];
  const vp = verticalPath.value;
  const tp = transferPaths.value;

  if (!vp.length) return { nodes, links };

  const jobName = props.pathData?.target_job_name || "";

  for (let i = 0; i < vp.length; i++) {
    const stage = vp[i];
    const isCurrent = i === 0;
    nodes.push({
      id: `vp_${i}`,
      name: stage.job_name || `${jobName}-${stage.level}`,
      category: isCurrent ? "current" : "promotion",
      level: stage.level,
      description: stage.description || "",
    });

    if (i > 0) {
      links.push({
        source: `vp_${i - 1}`,
        target: `vp_${i}`,
        relation_type: "垂直晋升",
        value: "晋升",
      });
    }
  }

  for (let j = 0; j < tp.length; j++) {
    const transfer = tp[j];
    const targetName = transfer.job_name || transfer.label || `转岗方向${j + 1}`;
    const transferNodeId = `tp_${j}`;
    nodes.push({
      id: transferNodeId,
      name: targetName,
      category: "transfer",
      description: transfer.description || transfer.requirements || "",
    });

    const sourceIdx = transfer.from_level ? vp.findIndex((s) => s.level === transfer.from_level) : 0;
    const sourceId = `vp_${Math.max(0, sourceIdx)}`;
    links.push({
      source: sourceId,
      target: transferNodeId,
      relation_type: "换岗路径",
      value: "转岗",
    });
  }

  return { nodes, links };
};

const initChart = () => {
  if (!chartRef.value) return;
  chart = echarts.init(chartRef.value, null, { renderer: "canvas" });
};

const render = async () => {
  await nextTick();
  if (!chartRef.value || !chart) return;

  const { nodes, links } = buildGraphNodesAndLinks();
  if (!nodes.length) return;

  const colorMap = {
    current: "#22c55e",
    promotion: "#3b82f6",
    transfer: "#f59e0b",
  };

  chart.setOption({
    tooltip: {
      formatter: (params) => {
        if (params.dataType === "edge") {
          return `<strong>${params.data.value || "关联"}</strong><br/>${params.data.relation_type || ""}`;
        }
        const node = params.data || {};
        return [
          `<strong>${node.name}</strong>`,
          `级别：${node.level || "-"}`,
          `方向：${node.category === "current" ? "当前目标" : node.category === "promotion" ? "晋升" : "转岗"}`,
          node.description ? `说明：${node.description}` : "",
        ].filter(Boolean).join("<br/>");
      },
    },
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        scaleLimit: { min: 0.5, max: 2 },
        emphasis: { focus: "adjacency" },
        label: { show: true, position: "right", fontSize: 13, fontWeight: 600 },
        force: { repulsion: 800, edgeLength: [150, 250], gravity: 0.05 },
        data: nodes.map((n) => ({
          ...n,
          symbolSize: n.category === "current" ? 60 : n.category === "transfer" ? 40 : 48,
          itemStyle: {
            color: colorMap[n.category] || "#94a3b8",
            shadowBlur: n.category === "current" ? 12 : 0,
            shadowColor: "#22c55e",
          },
        })),
        links: links.map((l) => ({
          source: l.source,
          target: l.target,
          value: l.value,
          relation_type: l.relation_type,
          lineStyle: {
            width: 2,
            color: l.relation_type === "垂直晋升" ? "#22c55e" : "#f59e0b",
            curveness: 0.2,
          },
        })),
      },
    ],
  });
};

const handleResize = () => chart?.resize();

onMounted(() => {
  initChart();
  resizeObserver = new ResizeObserver(handleResize);
  if (chartRef.value) resizeObserver.observe(chartRef.value);
  setTimeout(() => render(), 150);
});

watch(() => props.pathData, () => {
  setTimeout(() => render(), 100);
}, { deep: true });

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chart?.dispose();
  chart = null;
});
</script>

<style scoped>
.career-path-graph {
  width: 100%;
}

.path-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 300px;
  color: #64748b;
  font-size: 14px;
}

.path-loading .el-icon {
  font-size: 28px;
}

.path-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.path-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
}

.path-stats {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.path-canvas-wrapper {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  background: #f8fafc;
}

.path-canvas {
  width: 100%;
  height: 450px;
}

.path-legend {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 12px;
  margin-bottom: 24px;
  padding: 8px 12px;
  background: #f1f5f9;
  border-radius: 8px;
  font-size: 13px;
  color: #64748b;
}

.legend-title {
  font-weight: 500;
  color: #475569;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.legend-dot.current {
  background: #22c55e;
}

.legend-dot.promotion {
  background: #3b82f6;
}

.legend-dot.transfer {
  background: #f59e0b;
}

.path-tasks-section {
  margin-top: 24px;
}

.tasks-title {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  transition: box-shadow 0.2s;
}

.task-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.task-card.priority-1 {
  border-left: 4px solid #ef4444;
}

.task-card.priority-2 {
  border-left: 4px solid #f59e0b;
}

.task-card.priority-3 {
  border-left: 4px solid #3b82f6;
}

.task-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.task-stage {
  font-size: 13px;
  color: #64748b;
}

.task-title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 6px;
}

.task-desc {
  font-size: 13px;
  color: #64748b;
  line-height: 1.6;
  margin-bottom: 8px;
}

.task-skills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.task-weekly {
  font-size: 12px;
  color: #94a3b8;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.weekly-label {
  font-weight: 500;
  color: #64748b;
}

.weekly-item::after {
  content: "、";
  color: #cbd5e1;
}

.weekly-item:last-child::after {
  content: "";
}

@media (max-width: 768px) {
  .path-canvas {
    height: 350px;
  }
}
</style>
