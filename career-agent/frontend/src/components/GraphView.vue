<template>
  <div ref="chartRef" class="graph-canvas"></div>
</template>

<script setup>
import * as echarts from "echarts";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  graph: { type: Object, default: () => ({ nodes: [], links: [] }) },
  focusId: { type: Number, default: null },
  focusMode: { type: Boolean, default: false },
});

const chartRef = ref();
let chart;
let resizeObserver;
const palette = ["#1d4ed8", "#0f766e", "#b45309", "#be123c", "#6d28d9", "#0f766e", "#4338ca", "#0369a1"];

const colorForCategory = (category) => {
  const text = String(category || "综合");
  const hash = Array.from(text).reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return palette[hash % palette.length];
};

const initChart = () => {
  if (!chartRef.value) return;
  chart = echarts.init(chartRef.value, null, { renderer: "canvas" });
};

const handleResize = () => {
  chart?.resize();
};

const render = async () => {
  await nextTick();
  if (!chartRef.value) return;
  if (!chart) initChart();
  
  const nodes = props.graph.nodes || [];
  const links = props.graph.links || [];
  const degreeMap = new Map(nodes.map((item) => [item.id, 0]));
  const neighborIds = new Set();

  for (const item of links) {
    degreeMap.set(item.source, (degreeMap.get(item.source) || 0) + 1);
    degreeMap.set(item.target, (degreeMap.get(item.target) || 0) + 1);
    if (props.focusId && item.source === props.focusId) neighborIds.add(item.target);
    if (props.focusId && item.target === props.focusId) neighborIds.add(item.source);
  }

  chart.setOption({
    tooltip: {
      formatter: (params) => {
        if (params.dataType === "edge") {
          const edge = params.data || {};
          return [
            `<strong>${edge.value || "岗位关联"}</strong>`,
            edge.reason || "用于展示岗位之间的迁移或成长关联。",
          ].join("<br/>");
        }

        const node = params.data || {};
        const degree = degreeMap.get(node.id) || 0;
        return [
          `<strong>${node.name || ""}</strong>`,
          `类别：${node.category || "综合"}`,
          `关联边数：${degree}`,
        ].join("<br/>");
      },
    },
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        layoutAnimation: true,
        scaleLimit: { min: 0.7, max: 2.4 },
        emphasis: { focus: "adjacency" },
        label: { show: true, position: "right", fontSize: 12, distance: 14 },
        force: { repulsion: 1200, edgeLength: [180, 280], gravity: 0.02, layoutAnimation: true },
        data: nodes.map((item) => {
          const isFocus = props.focusId === item.id;
          const isNeighbor = neighborIds.has(item.id);
          const degree = degreeMap.get(item.id) || 0;
          return {
            ...item,
            symbolSize: isFocus ? 74 : isNeighbor ? 58 : Math.min(52, 38 + degree * 1.5),
            itemStyle: {
              color: isFocus ? "#ea580c" : isNeighbor ? "#0f766e" : colorForCategory(item.category),
            },
            label: {
              fontSize: isFocus ? 15 : 12,
              fontWeight: isFocus ? 700 : 500,
            },
          };
        }),
        links: links.map((item) => {
          const isFocusLink = props.focusId && (item.source === props.focusId || item.target === props.focusId);
          const isVisible = item.visible !== false;
          
          let lineColor = "#94a3b8";
          if (item.relation_type === "技能关联") lineColor = "#5470c6";
          else if (item.relation_type === "同类型") lineColor = "#91cc75";
          else if (item.relation_type === "同企业") lineColor = "#fac858";
          else if (item.relation_type === "垂直晋升") lineColor = "#22c55e";
          else if (item.relation_type === "换岗路径") lineColor = "#f97316";
          
          let opacity = isFocusLink ? 0.9 : 0.28;
          if (props.focusMode) {
            opacity = isVisible ? 1.0 : 0.03;
          }
          
          return {
            source: item.source,
            target: item.target,
            value: item.relation_type,
            reason: item.reason,
            lineStyle: {
              width: isFocusLink ? 2.4 : 1,
              opacity: opacity,
              color: isFocusLink ? "#0f766e" : lineColor,
              curveness: 0.16,
            },
          };
        }),
        edgeLabel: { show: false },
      },
    ],
  });
};

onMounted(() => {
  initChart();
  resizeObserver = new ResizeObserver(handleResize);
  if (chartRef.value) {
    resizeObserver.observe(chartRef.value);
  }
  setTimeout(() => {
    render();
  }, 100);
});

watch(() => props.graph, () => {
  setTimeout(() => {
    render();
  }, 50);
}, { deep: true });

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chart?.dispose();
  chart = null;
});
</script>

<style scoped>
.graph-canvas {
  width: 100%;
  height: 700px;
}

@media (max-width: 960px) {
  .graph-canvas {
    height: 560px;
  }
}
</style>
