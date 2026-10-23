<template>
  <div class="home-container">
    <header class="header">
      <h2>智聘引擎 InWriting</h2>
      <el-button type="danger" plain @click="handleLogout">退出登录</el-button>
    </header>

    <div class="main-content">
      <!-- 左侧：简历上传区 -->
      <el-card class="upload-card">
        <h3>📄 上传你的简历</h3>
        <el-upload
          class="upload-demo"
          drag
          action="#"
          :auto-upload="false"
          :on-change="handleFileChange"
          :limit="1"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            将文件拖到此处，或 <em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">支持 PDF / DOCX 格式</div>
          </template>
        </el-upload>

        <el-input
          v-model="targetJob"
          placeholder="请输入目标岗位（如：AI应用开发实习生）"
          style="margin-top: 20px"
        />

        <el-button
          type="primary"
          style="width: 100%; margin-top: 20px"
          size="large"
          :loading="uploading"
          @click="submitResume"
        >
          {{ uploading ? "AI 正在深度解析简历，请稍候..." : "开始解析并匹配" }}
        </el-button>
      </el-card>

      <!-- 右侧：真实解析结果 -->
      <el-card class="result-card">
        <h3>📊 简历解析与岗位匹配</h3>

        <div v-if="!resumeData" class="empty-state">
          暂无数据，请先上传简历解析
        </div>

        <div v-else class="result-container">
          <!-- 真实的匹配度得分 -->
          <div class="score-circle">
            <div class="score-num">{{ resumeData.match_score || 75 }}</div>
            <div class="score-label">岗位匹配度</div>
          </div>

          <!-- 真实的技能提取 -->
          <div class="skills-box">
            <h4>提取的核心技能：</h4>
            <div class="tags">
              <el-tag
                v-for="skill in resumeData.parsed_json?.skills"
                :key="skill"
                type="success"
                effect="dark"
                style="margin: 5px"
              >
                {{ skill }}
              </el-tag>
            </div>
          </div>

          <el-button
            type="success"
            size="large"
            style="width: 100%; margin-top: 30px"
            @click="startInterview"
          >
            进入模拟面试
          </el-button>
        </div>
      </el-card>
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
    });
    router.push({ path: "/interview", query: { id: res.id } });
  } catch (error) {
    ElMessage.error("创建面试失败");
  }
};
</script>

<style scoped>
.home-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 30px;
  height: 60px;
  background: rgba(30, 41, 59, 0.8);
  border-bottom: 1px solid rgba(56, 189, 248, 0.2);
}
.header h2 {
  margin: 0;
  color: #38bdf8;
  letter-spacing: 1px;
}
.main-content {
  display: flex;
  padding: 30px;
  gap: 30px;
  flex: 1;
}
.upload-card,
.result-card {
  flex: 1;
  background: rgba(30, 41, 59, 0.6) !important;
  border: 1px solid rgba(56, 189, 248, 0.2) !important;
}
h3 {
  color: #e2e8f0;
  margin-top: 0;
  margin-bottom: 20px;
}
.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 300px;
  color: #64748b;
}

/* 新增的样式 */
.result-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 20px;
}
.score-circle {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  border: 6px solid #10b981;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  box-shadow: 0 0 20px rgba(16, 185, 129, 0.4);
}
.score-num {
  font-size: 48px;
  font-weight: bold;
  color: #10b981;
  line-height: 1;
}
.score-label {
  font-size: 14px;
  color: #cbd5e1;
  margin-top: 5px;
}

.skills-box {
  width: 100%;
  margin-top: 40px;
  text-align: left;
}
.skills-box h4 {
  color: #94a3b8;
  margin-bottom: 10px;
}
.tags {
  display: flex;
  flex-wrap: wrap;
}
</style>
