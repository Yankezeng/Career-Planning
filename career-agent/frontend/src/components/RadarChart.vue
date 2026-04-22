<template>
  <div ref="chartRef" style="height: 360px; width: 100%"></div>
</template>

<script setup>
import * as echarts from "echarts";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  data: { type: Object, default: () => ({}) },
});

const chartRef = ref();
let chart;

const render = async () => {
  await nextTick();
  if (!chartRef.value) return;
  chart ||= echarts.init(chartRef.value);
  chart.setOption({
    color: ["#0f62fe"],
    tooltip: {},
    radar: {
      radius: "65%",
      indicator: [
        { name: "专业能力", max: 100 },
        { name: "实践能力", max: 100 },
        { name: "沟通协作", max: 100 },
        { name: "学习成长", max: 100 },
        { name: "创新能力", max: 100 },
        { name: "职业素养", max: 100 },
      ],
    },
    series: [
      {
        type: "radar",
        areaStyle: { color: "rgba(15,98,254,0.18)" },
        data: [
          {
            value: [
              props.data.professional_score || 0,
              props.data.practice_score || 0,
              props.data.communication_score || 0,
              props.data.learning_score || 0,
              props.data.innovation_score || 0,
              props.data.professionalism_score || 0,
            ],
            name: "能力画像",
          },
        ],
      },
    ],
  });
};

onMounted(render);
watch(() => props.data, render, { deep: true });
onBeforeUnmount(() => chart?.dispose());
</script>
