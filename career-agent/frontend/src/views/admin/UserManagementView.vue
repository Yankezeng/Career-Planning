<template>
  <div class="page-shell">
    <PageHeader :title="text.pageTitle" :description="text.pageDesc" />

    <div class="two-col">
      <SectionCard :title="text.listTitle">
        <el-table :data="users">
          <el-table-column prop="username" :label="text.username" min-width="130" />
          <el-table-column prop="real_name" :label="text.realName" width="120" />
          <el-table-column prop="role" :label="text.role" width="120" />
          <el-table-column prop="department" :label="text.department" min-width="140" />
          <el-table-column prop="classroom" :label="text.classroom" min-width="120" />
        </el-table>
      </SectionCard>

      <SectionCard :title="text.createTitle">
        <el-form :model="form" label-position="top">
          <el-form-item :label="text.username">
            <el-input v-model="form.username" />
          </el-form-item>
          <el-form-item :label="text.password">
            <el-input v-model="form.password" show-password />
          </el-form-item>
          <el-form-item :label="text.realName">
            <el-input v-model="form.real_name" />
          </el-form-item>
          <el-form-item :label="text.roleCode">
            <el-select v-model="form.role_code">
              <el-option :label="text.admin" value="admin" />
              <el-option :label="text.student" value="student" />
              <el-option :label="text.enterprise" value="enterprise" />
            </el-select>
          </el-form-item>
          <el-form-item :label="text.email">
            <el-input v-model="form.email" />
          </el-form-item>
          <el-form-item :label="text.phone">
            <el-input v-model="form.phone" />
          </el-form-item>
        </el-form>

        <div class="actions">
          <el-button @click="resetForm">{{ text.reset }}</el-button>
          <el-button type="primary" @click="create">{{ text.create }}</el-button>
        </div>
      </SectionCard>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { adminApi } from "@/api";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";

const text = {
  pageTitle: "\u7528\u6237\u7ba1\u7406",
  pageDesc: "\u7ba1\u7406\u7ba1\u7406\u5458\u3001\u5b66\u751f\u4e0e\u4f01\u4e1a\u7aef\u6d4b\u8bd5\u8d26\u53f7\u3002",
  listTitle: "\u7528\u6237\u5217\u8868",
  createTitle: "\u65b0\u589e\u7528\u6237",
  username: "\u7528\u6237\u540d",
  password: "\u5bc6\u7801",
  realName: "\u59d3\u540d",
  role: "\u89d2\u8272",
  roleCode: "\u89d2\u8272\u4ee3\u7801",
  department: "\u9662\u7cfb",
  classroom: "\u73ed\u7ea7",
  email: "\u90ae\u7bb1",
  phone: "\u7535\u8bdd",
  admin: "\u7ba1\u7406\u5458",
  student: "\u5b66\u751f",
  enterprise: "\u4f01\u4e1a",
  reset: "\u91cd\u7f6e",
  create: "\u521b\u5efa\u7528\u6237",
  createSuccess: "\u7528\u6237\u5df2\u521b\u5efa",
  fillRequired: "\u8bf7\u5148\u586b\u5199\u7528\u6237\u540d\u3001\u5bc6\u7801\u548c\u59d3\u540d"
};

const users = ref([]);
const form = reactive({
  username: "",
  password: "123456",
  real_name: "",
  role_code: "student",
  email: "",
  phone: ""
});

const load = async () => {
  users.value = (await adminApi.users()).data || [];
};

const resetForm = () => {
  form.username = "";
  form.password = "123456";
  form.real_name = "";
  form.role_code = "student";
  form.email = "";
  form.phone = "";
};

const create = async () => {
  if (!form.username || !form.password || !form.real_name) {
    ElMessage.warning(text.fillRequired);
    return;
  }
  await adminApi.createUser(form);
  ElMessage.success(text.createSuccess);
  resetForm();
  await load();
};

onMounted(load);
</script>

<style scoped>
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
