<template>
  <div class="login-wrapper">
    <!-- 背景特效层 -->
    <div class="bg-grid"></div>
    <div class="bg-glow"></div>

    <div class="login-box">
      <!-- 左侧：产品宣发区 -->
      <div class="brand-section">
        <div class="logo">智聘引擎 InWriting</div>
        <h1 class="slogan">AI 驱动的<br />全栈模拟面试平台</h1>

        <div class="features">
          <p>⚡ 简历精准解析 · 能力雷达图</p>
          <p>🤖 多智能体面试 · 压力面/HR面</p>
          <p>🧠 RAG 知识增强 · 生成式 UI</p>
        </div>

        <!-- 🚨 新增：实时数据看板 -->
        <div class="stats-board">
          <div class="stat-item">
            <div class="stat-num">3,248</div>
            <div class="stat-label">累计模拟面试</div>
          </div>
          <div class="stat-item">
            <div class="stat-num">12,590</div>
            <div class="stat-label">生成评估报告</div>
          </div>
        </div>

        <!-- 🚨 新增：实时滚动资讯 (替换掉原来的胶囊) -->
        <div class="live-news">
          <div class="news-icon">🔊</div>
          <div class="news-scroll-container">
            <div class="news-scroll-content">
              <span>🔥 刚刚，来自北京大学的同学完成了「压力面」极限挑战。</span>
              <span>📈 平台今日已生成 1,024 份 AI 深度评估报告。</span>
              <span>🚀 智谱 GLM-4 多智能体引擎运行正常。</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：表单交互区 -->
      <div class="form-section">
        <el-tabs v-model="activeTab" class="custom-tabs" stretch>
          <el-tab-pane label="账 号 登 录" name="login">
            <el-form @submit.prevent="handleLogin" class="auth-form">
              <el-form-item>
                <el-input
                  v-model="form.username"
                  placeholder="请输入用户名"
                  size="large"
                  prefix-icon="User"
                />
              </el-form-item>
              <el-form-item>
                <el-input
                  v-model="form.password"
                  type="password"
                  placeholder="请输入密码"
                  size="large"
                  show-password
                  prefix-icon="Lock"
                />
              </el-form-item>
              <el-button
                type="primary"
                native-type="submit"
                size="large"
                class="submit-btn"
                :loading="loading"
              >
                进入智聘引擎
              </el-button>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="注 册 新 账 号" name="register">
            <el-form @submit.prevent="handleRegister" class="auth-form">
              <el-form-item>
                <el-input
                  v-model="form.username"
                  placeholder="设置用户名"
                  size="large"
                  prefix-icon="User"
                />
              </el-form-item>
              <el-form-item>
                <el-input
                  v-model="form.password"
                  type="password"
                  placeholder="设置密码"
                  size="large"
                  show-password
                  prefix-icon="Lock"
                />
              </el-form-item>
              <el-button
                type="success"
                native-type="submit"
                size="large"
                class="submit-btn"
                :loading="loading"
              >
                立即注册并登录
              </el-button>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from "vue";
import { useRouter } from "vue-router";
import { useUserStore } from "../stores/user";
import axios from "axios";
import { ElMessage } from "element-plus";
import { User, Lock } from "@element-plus/icons-vue";

const router = useRouter();
const userStore = useUserStore();

const activeTab = ref("login");
const loading = ref(false);
const form = reactive({
  username: "",
  password: "",
});

// 登录逻辑
const handleLogin = async () => {
  if (!form.username || !form.password)
    return ElMessage.warning("请输入账号和密码");
  loading.value = true;
  try {
    const params = new URLSearchParams();
    params.append("username", form.username);
    params.append("password", form.password);

    const res = await axios.post("/api/auth/login", params);
    userStore.setToken(res.data.access_token);
    ElMessage.success("登录成功，正在进入工作台...");
    router.push("/home");
  } catch (error) {
    ElMessage.error("登录失败，请检查账号密码");
  } finally {
    loading.value = false;
  }
};

// 注册逻辑
const handleRegister = async () => {
  if (!form.username || !form.password)
    return ElMessage.warning("请输入账号和密码");
  loading.value = true;
  try {
    await axios.post("/api/auth/register", {
      username: form.username,
      password: form.password,
    });
    ElMessage.success("注册成功！正在为您自动登录...");
    await handleLogin();
  } catch (error) {
    if (error.response?.status === 400) {
      ElMessage.error("该用户名已被注册，请更换");
    } else {
      ElMessage.error("注册失败，请重试");
    }
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
/* 全屏科技感背景 */
.login-wrapper {
  position: relative;
  height: 100vh;
  width: 100vw;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #0b1120;
  overflow: hidden;
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(56, 189, 248, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(56, 189, 248, 0.05) 1px, transparent 1px);
  background-size: 40px 40px;
  z-index: 1;
}

.bg-glow {
  position: absolute;
  width: 600px;
  height: 600px;
  background: radial-gradient(
    circle,
    rgba(56, 189, 248, 0.15) 0%,
    transparent 70%
  );
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  filter: blur(40px);
}

/* 主卡片 */
.login-box {
  position: relative;
  z-index: 10;
  display: flex;
  width: 950px;
  height: 560px;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(56, 189, 248, 0.2);
  border-radius: 20px;
  box-shadow:
    0 25px 50px -12px rgba(0, 0, 0, 0.5),
    0 0 40px rgba(56, 189, 248, 0.1);
  overflow: hidden;
}

/* 左侧宣发区 */
.brand-section {
  flex: 1.2;
  padding: 50px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  background: linear-gradient(
    135deg,
    rgba(30, 41, 59, 0.8) 0%,
    rgba(15, 23, 42, 0.8) 100%
  );
  border-right: 1px solid rgba(255, 255, 255, 0.05);
}

.logo {
  font-size: 24px;
  font-weight: 900;
  color: #38bdf8;
  letter-spacing: 2px;
  margin-bottom: 25px;
  text-shadow: 0 0 10px rgba(56, 189, 248, 0.5);
}

.slogan {
  font-size: 38px;
  color: #f8fafc;
  line-height: 1.3;
  margin: 0 0 25px 0;
  font-weight: 800;
}

.features {
  color: #94a3b8;
  line-height: 1.8;
  font-size: 15px;
  margin-bottom: 30px;
}
.features p {
  margin: 8px 0;
}

/* 数据看板 */
.stats-board {
  display: flex;
  gap: 30px;
  margin-bottom: 30px;
  padding: 15px;
  background: rgba(56, 189, 248, 0.05);
  border-radius: 12px;
  border: 1px solid rgba(56, 189, 248, 0.1);
}
.stat-item {
  display: flex;
  flex-direction: column;
}
.stat-num {
  font-size: 24px;
  font-weight: bold;
  color: #10b981;
  font-family: "Courier New", Courier, monospace;
}
.stat-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 5px;
}

/* 滚动资讯 */
.live-news {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 36px;
  padding: 0 15px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 20px;
  overflow: hidden;
  margin-top: auto; /* 推到底部 */
}
.news-icon {
  font-size: 14px;
  animation: pulse 1.5s infinite;
}
.news-scroll-container {
  flex: 1;
  height: 20px;
  overflow: hidden;
  position: relative;
}
.news-scroll-content {
  display: flex;
  flex-direction: column;
  animation: scrollUp 12s linear infinite; /* 无限向上滚动动画 */
}
.news-scroll-content span {
  height: 20px;
  line-height: 20px;
  font-size: 13px;
  color: #cbd5e1;
  white-space: nowrap;
}

@keyframes scrollUp {
  0% {
    transform: translateY(0);
  }
  33% {
    transform: translateY(-20px);
  }
  66% {
    transform: translateY(-40px);
  }
  100% {
    transform: translateY(-60px);
  }
}
@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
  100% {
    opacity: 1;
  }
}

/* 右侧表单区 */
.form-section {
  flex: 1;
  padding: 50px 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

:deep(.custom-tabs .el-tabs__nav-wrap::after) {
  display: none;
}
:deep(.custom-tabs .el-tabs__item) {
  color: #64748b;
  font-size: 16px;
  font-weight: bold;
}
:deep(.custom-tabs .el-tabs__item.is-active) {
  color: #38bdf8;
  text-shadow: 0 0 10px rgba(56, 189, 248, 0.3);
}
:deep(.custom-tabs .el-tabs__active-bar) {
  background-color: #38bdf8;
  box-shadow: 0 0 10px #38bdf8;
}

.auth-form {
  margin-top: 30px;
}
:deep(.el-input__wrapper) {
  background-color: rgba(0, 0, 0, 0.3);
  box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.2) inset;
  border-radius: 8px;
}
:deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 1px #38bdf8 inset,
    0 0 10px rgba(56, 189, 248, 0.2);
}

.submit-btn {
  width: 100%;
  margin-top: 20px;
  border-radius: 8px;
  font-weight: bold;
  letter-spacing: 2px;
  transition: all 0.3s;
}
.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(56, 189, 248, 0.3);
}
</style>
