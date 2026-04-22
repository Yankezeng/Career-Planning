<template>
  <div v-if="auth.role !== 'student'" class="selector-wrap">
    <el-select :model-value="modelValue" placeholder="请选择学生" style="width: 280px" @change="updateValue">
      <el-option v-for="item in students" :key="item.id" :label="`${item.name} - ${item.major || '未填写专业'}`" :value="item.id" />
    </el-select>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { enterpriseApi } from "@/api";
import { useAuthStore } from "@/stores/auth";

const props = defineProps({
  modelValue: { type: Number, default: null },
});

const emit = defineEmits(["update:modelValue", "change"]);
const auth = useAuthStore();
const students = ref([]);

const updateValue = (value) => {
  emit("update:modelValue", value);
  emit("change", value);
};

onMounted(async () => {
  if (auth.role === "student") return;
  try {
    const res = await enterpriseApi.students();
    students.value = res.data || [];
    if (!props.modelValue && students.value.length) {
      updateValue(students.value[0].id);
    }
  } catch (_) {
    students.value = [];
  }
});
</script>

<style scoped>
.selector-wrap {
  margin-bottom: 16px;
}
</style>
