<template>
  <div ref="chartRef" :style="{ height, width: '100%' }"></div>
</template>

<script setup>
import * as echarts from "echarts";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: "320px" },
});

const chartRef = ref(null);
let chartInstance;

const render = async () => {
  await nextTick();
  if (!chartRef.value) return;
  chartInstance ||= echarts.init(chartRef.value);
  chartInstance.setOption(props.option, true);
  chartInstance.resize();
};

const resize = () => {
  chartInstance?.resize();
};

onMounted(() => {
  render();
  window.addEventListener("resize", resize);
});

watch(() => props.option, render, { deep: true });

onBeforeUnmount(() => {
  window.removeEventListener("resize", resize);
  chartInstance?.dispose();
});
</script>
