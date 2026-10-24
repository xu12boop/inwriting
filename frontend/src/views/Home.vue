<template>
  <div class="home-container">
    <!-- 背景光晕 -->
    <div class="bg-glow"></div>

    <header class="header">
      <h2 class="logo-text">智聘引擎 InWriting</h2>
      <el-button type="danger" plain round @click="handleLogout"
        >退出登录</el-button
      >
    </header>

    <div class="main-content">
      <!-- 左侧：简历上传区 -->
      <div class="glass-card upload-card">
        <h3 class="card-title">📄 投递你的简历</h3>

        <el-upload
          class="upload-demo"
          drag
          action="#"
          :auto-upload="false"
          :on-change="handleFileChange"
          :limit="1"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">拖拽文件至此，或 <em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">
              支持 PDF / DOCX 格式，文件大小不超过 10MB
            </div>
          </template>
        </el-upload>

        <div class="input-group">
          <label>目标岗位</label>
          <el-input
            v-model="targetJob"
            placeholder="例如：AI应用开发实习生"
            size="large"
          />
        </div>

        <el-button
          type="primary"
          class="action-btn"
          size="large"
          :loading="uploading"
          @click="submitResume"
        >
          {{ uploading ? "AI 正在深度解析中..." : "🚀 开始解析并匹配" }}
        </el-button>

        <!-- 面试官选择区 -->
        <div v-if="resumeData" class="interview-setup fade-in">
          <h4 class="sub-title">🎭 选择你的专属面试官</h4>
          <div class="radio-group">
            <div
              class="radio-card"
              :class="{ active: interviewType === 'tech' }"
              @click="interviewType = 'tech'"
            >
              <div class="icon">👨‍💻</div>
              <div class="text">技术面</div>
              <div class="desc">深挖代码底层</div>
            </div>
            <div
              class="radio-card"
              :class="{ active: interviewType === 'hr' }"
              @click="interviewType = 'hr'"
            >
              <div class="icon">👩‍💼</div>
              <div class="text">HR 面</div>
              <div class="desc">考察团队情商</div>
            </div>
            <div
              class="radio-card"
              :class="{ active: interviewType === 'stress' }"
              @click="interviewType = 'stress'"
            >
              <div class="icon">😈</div>
              <div class="text">压力面</div>
              <div class="desc">地狱级施压</div>
            </div>
          </div>

          <el-button
            type="success"
            class="action-btn start-btn"
            size="large"
            @click="startInterview"
          >
            🎙️ 进入全真模拟面试
          </el-button>
        </div>
      </div>

      <!-- 右侧：真实解析结果 -->
      <div class="glass-card result-card">
        <h3 class="card-title">📊 简历洞察报告</h3>

        <div v-if="!resumeData" class="empty-state">
          <el-empty description="暂无数据，请先上传简历进行 AI 解析" />
        </div>

        <div v-else class="result-content fade-in">
          <!-- 科技感匹配度圆环 -->
          <div class="score-wrapper">
            <div
              class="score-ring"
              :style="{ '--percent': (resumeData.match_score || 75) + '%' }"
            >
              <div class="score-inner">
                <span class="num">{{ resumeData.match_score || 75 }}</span>
                <span class="label">Match Score</span>
              </div>
            </div>
          </div>

          <div class="skills-section">
            <h4 class="sub-title">核心技能提取</h4>
            <div class="tags">
              <el-tag
                v-for="skill in resumeData.parsed_json?.skills || []"
                :key="skill"
                class="skill-tag"
                effect="dark"
              >
                {{ skill }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useUserStore } from "../stores/user";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { UploadFilled } from "@element-plus/icons-vue";
import request from "../api/request";

const userStore = useUserStore();
const router = useRouter();

const targetJob = ref("AI应用开发实习生");
const file = ref(null);
const uploading = ref(false);
const resumeData = ref(null);
const interviewType = ref("tech");

const handleLogout = () => {
  userStore.logout();
  router.push("/login");
};

const handleFileChange = (uploadFile) => {
  file.value = uploadFile.raw;
};

const submitResume = async () => {
  if (!file.value) return ElMessage.warning("请先选择一份简历");
  if (!targetJob.value) return ElMessage.warning("请输入目标岗位");

  uploading.value = true;
  const formData = new FormData();
  formData.append("file", file.value);
  formData.append("target_job", targetJob.value);

  try {
    const res = await request.post("/resume/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    resumeData.value = res;
    ElMessage.success("简历解析成功！");
  } catch (error) {
    console.error("上传报错详情:", error);
    ElMessage.error("解析失败，请重试");
  } finally {
    uploading.value = false;
  }
};

const startInterview = async () => {
  if (!resumeData.value) return ElMessage.warning("请先解析简历");

  try {
    const res = await request.post("/interview/start", {
      resume_id: resumeData.value.id,
      target_job: targetJob.value,
      interview_type: interviewType.value,
    });
    router.push({
      path: "/interview",
      query: { id: res.id, type: interviewType.value },
    });
  } catch (error) {
    ElMessage.error("创建面试失败");
  }
};
</script>

<style scoped>
/* 全局容器 */
.home-container {
  min-height: 100vh;
  background-color: #0b1120;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.bg-glow {
  position: absolute;
  width: 800px;
  height: 800px;
  background: radial-gradient(
    circle,
    rgba(56, 189, 248, 0.08) 0%,
    transparent 60%
  );
  top: -200px;
  right: -200px;
  z-index: 0;
}

/* 顶栏 */
.header {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
  height: 70px;
  background: rgba(15, 23, 42, 0.7);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.logo-text {
  margin: 0;
  color: #f8fafc;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 1px;
  background: linear-gradient(90deg, #38bdf8, #818cf8);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* 主体布局 */
.main-content {
  position: relative;
  z-index: 1;
  display: flex;
  padding: 40px;
  gap: 40px;
  flex: 1;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

/* 毛玻璃卡片基底 */
.glass-card {
  flex: 1;
  background: rgba(30, 41, 59, 0.4);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  padding: 30px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
  transition:
    transform 0.3s ease,
    box-shadow 0.3s ease;
}
.glass-card:hover {
  transform: translateY(-5px);
  box-shadow:
    0 25px 50px rgba(0, 0, 0, 0.4),
    0 0 20px rgba(56, 189, 248, 0.1);
}

.card-title {
  color: #f1f5f9;
  margin-top: 0;
  margin-bottom: 25px;
  font-size: 18px;
  font-weight: 600;
}
.sub-title {
  color: #94a3b8;
  font-size: 14px;
  margin: 20px 0 15px 0;
}

/* 上传区域美化 */
:deep(.el-upload-dragger) {
  background: rgba(15, 23, 42, 0.5);
  border: 2px dashed rgba(56, 189, 248, 0.4);
  border-radius: 16px;
  padding: 40px 20px;
  transition: all 0.3s;
}
:deep(.el-upload-dragger:hover) {
  border-color: #38bdf8;
  background: rgba(56, 189, 248, 0.05);
}
:deep(.el-icon--upload) {
  color: #38bdf8;
  font-size: 50px;
  margin-bottom: 15px;
}
:deep(.el-upload__text) {
  color: #cbd5e1;
}
:deep(.el-upload__text em) {
  color: #38bdf8;
  font-style: normal;
  font-weight: bold;
}

/* 输入框与按钮 */
.input-group {
  margin-top: 25px;
}
.input-group label {
  display: block;
  color: #94a3b8;
  margin-bottom: 10px;
  font-size: 14px;
}
:deep(.el-input__wrapper) {
  background-color: rgba(15, 23, 42, 0.6);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.1) inset;
  border-radius: 10px;
}
.action-btn {
  width: 100%;
  margin-top: 25px;
  border-radius: 10px;
  font-weight: bold;
  letter-spacing: 1px;
  background: linear-gradient(135deg, #0ea5e9 0%, #3b82f6 100%);
  border: none;
  transition: all 0.3s;
}
.action-btn:hover {
  box-shadow: 0 0 20px rgba(14, 165, 233, 0.4);
  transform: translateY(-2px);
}
.start-btn {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}
.start-btn:hover {
  box-shadow: 0 0 20px rgba(16, 185, 129, 0.4);
}

/* 面试官选择卡片 */
.interview-setup {
  margin-top: 30px;
  padding-top: 25px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}
.radio-group {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
}
.radio-card {
  flex: 1;
  padding: 15px;
  border-radius: 12px;
  text-align: center;
  cursor: pointer;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
}
.radio-card:hover {
  background: rgba(56, 189, 248, 0.1);
}
.radio-card.active {
  background: rgba(56, 189, 248, 0.15);
  border-color: #38bdf8;
  box-shadow: 0 0 15px rgba(56, 189, 248, 0.2);
}
.radio-card .icon {
  font-size: 24px;
  margin-bottom: 5px;
}
.radio-card .text {
  color: #f1f5f9;
  font-weight: bold;
  font-size: 14px;
}
.radio-card .desc {
  color: #64748b;
  font-size: 12px;
  margin-top: 5px;
}

/* 右侧匹配度圆环 */
.result-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 10px;
}
.score-wrapper {
  margin: 20px 0 40px 0;
}
.score-ring {
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: conic-gradient(
    #38bdf8 var(--percent),
    rgba(255, 255, 255, 0.05) 0
  );
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
  box-shadow: 0 0 30px rgba(56, 189, 248, 0.2);
}
.score-ring::before {
  content: "";
  position: absolute;
  inset: 5px;
  border-radius: 50%;
  background: #0f172a;
}
.score-inner {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.score-inner .num {
  font-size: 56px;
  font-weight: 900;
  color: #38bdf8;
  line-height: 1;
  text-shadow: 0 0 15px rgba(56, 189, 248, 0.5);
}
.score-inner .label {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 5px;
  letter-spacing: 2px;
}

/* 技能标签 */
.skills-section {
  width: 100%;
}
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.skill-tag {
  background: rgba(56, 189, 248, 0.1) !important;
  border: 1px solid rgba(56, 189, 248, 0.3) !important;
  color: #38bdf8 !important;
  border-radius: 6px;
  padding: 0 12px;
  height: 32px;
  line-height: 30px;
}

.fade-in {
  animation: fadeIn 0.6s ease-out;
}
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
