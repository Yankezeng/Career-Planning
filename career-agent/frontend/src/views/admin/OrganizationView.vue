<template>
  <div class="page-shell">
    <PageHeader title="班级/院系管理页" description="查看当前院系和班级基础数据。" />
    <div class="two-col">
      <SectionCard title="院系列表">
        <el-table :data="departments">
          <el-table-column prop="name" label="院系名称" />
          <el-table-column prop="description" label="说明" />
        </el-table>
      </SectionCard>
      <SectionCard title="班级列表">
        <el-table :data="classes">
          <el-table-column prop="name" label="班级名称" />
          <el-table-column prop="grade" label="年级" />
          <el-table-column prop="department_id" label="院系ID" />
        </el-table>
      </SectionCard>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { adminApi } from "@/api";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";

const departments = ref([]);
const classes = ref([]);

onMounted(async () => {
  departments.value = (await adminApi.departments()).data || [];
  classes.value = (await adminApi.classes()).data || [];
});
</script>
