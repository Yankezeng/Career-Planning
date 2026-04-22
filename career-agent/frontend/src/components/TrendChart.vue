<template>
  <div ref="chartRef" style="height: 320px; width: 100%"></div>
</template>

<script setup>
import * as echarts from "echarts";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  trend: { type: Object, default: () => ({ labels: [], completion_rates: [], skill_counts: [] }) },
});

const chartRef = ref();
let chart;

const render = async () => {
  await nextTick();
  if (!chartRef.value) return;
  chart ||= echarts.init(chartRef.value);
  chart.setOption({
    tooltip: { trigger: "axis" },
    legend: { data: ["完成率", "新增技能数"] },
    xAxis: { type: "category", data: props.trend.labels || [] },
    yAxis: [{ type: "value", max: 100 }, { type: "value" }],
    series: [
      { name: "完成率", type: "line", smooth: true, data: props.trend.completion_rates || [] },
      { name: "新增技能数", type: "bar", yAxisIndex: 1, data: props.trend.skill_counts || [] },
    ],
  });
};

onMounted(render);
watch(() => props.trend, render, { deep: true });
onBeforeUnmount(() => chart?.dispose());
</script>
