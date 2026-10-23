<template>
  <div class="login-container">
    <el-card class="login-card">
      <h2 class="title">智聘引擎 InWriting</h2>
      <el-form @submit.prevent="handleLogin">
        <el-form-item>
          <el-input
            v-model="username"
            placeholder="用户名 (reviewer)"
            size="large"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            placeholder="密码 (123456)"
            size="large"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          native-type="submit"
          size="large"
          class="login-btn"
          :loading="loading"
          >登 录</el-button
        >
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useUserStore } from "../stores/user";
import axios from "axios";
import { ElMessage } from "element-plus";

const username = ref("");
const password = ref("");
const loading = ref(false);
const router = useRouter();
const userStore = useUserStore();

const handleLogin = async () => {
  if (!username.value || !password.value)
    return ElMessage.warning("请输入账号密码");
  loading.value = true;
  try {
    const params = new URLSearchParams();
    params.append("username", username.value);
    params.append("password", password.value);
    const res = await axios.post("/api/auth/login", params);
    userStore.setToken(res.data.access_token);
    ElMessage.success("登录成功");
    router.push("/home");
  } catch (error) {
    ElMessage.error("登录失败，请检查账号密码");
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: radial-gradient(circle at center, #1e293b, #0f172a);
}
.login-card {
  width: 400px;
  background: rgba(30, 41, 59, 0.8);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(56, 189, 248, 0.2);
}
.title {
  text-align: center;
  color: #38bdf8;
  margin-bottom: 30px;
  letter-spacing: 2px;
}
.login-btn {
  width: 100%;
  margin-top: 10px;
  background: linear-gradient(to right, #0284c7, #38bdf8);
  border: none;
}
</style>
