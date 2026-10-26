<template>
  <div class="interview-wrapper">
    <div class="aurora-bg"></div>

    <header class="glass-header">
      <h2 class="role-title">
        <span v-if="interviewType === 'hr'">👩‍💼 HR 综合面试间</span>
        <span v-else-if="interviewType === 'stress'">😈 极限压力面试间</span>
        <span v-else>👨‍💻 深度技术面试间</span>
      </h2>
      <div>
        <el-button
          type="warning"
          round
          @click="finishInterview"
          :loading="generatingReport"
          >生成评估报告</el-button
        >
        <el-button
          type="danger"
          plain
          round
          @click="router.push('/home')"
          style="margin-left: 10px"
          >退出</el-button
        >
      </div>
    </header>

    <div class="chat-area" ref="chatBoxRef">
      <div
        v-for="(msg, index) in chatList"
        :key="index"
        :class="['message-row', msg.role]"
      >
        <div class="avatar" :class="interviewType">
          {{
            msg.role === "ai"
              ? interviewType === "hr"
                ? "HR"
                : interviewType === "stress"
                  ? "魔"
                  : "技"
              : "我"
          }}
        </div>
        <div class="bubble" :class="[msg.role, interviewType]">
          {{ msg.content }}
          <span v-if="msg.role === 'ai' && msg.typing" class="cursor">|</span>
        </div>
      </div>
    </div>

    <!-- 🚨 摄像头监考悬浮窗 -->
    <div class="camera-monitor" v-show="cameraActive">
      <video ref="videoRef" autoplay playsinline muted></video>

      <!-- 修复：只有当 hasWarning 为 true 时才变红 -->
      <div class="camera-status" :class="{ warning: hasWarning }">
        <div class="dot"></div>
        {{ currentStatus }}
      </div>
    </div>

    <div class="glass-footer">
      <el-input
        v-model="userInput"
        placeholder="输入你的回答，按 Enter 发送..."
        class="chat-input"
        @keyup.enter="sendMessage"
        :disabled="isTyping || generatingReport"
      />
      <el-button
        type="primary"
        class="send-btn"
        @click="sendMessage"
        :loading="isTyping"
        >发送</el-button
      >
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from "vue";
import { useRouter, useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { useUserStore } from "../stores/user";
import request from "../api/request";
import { FaceLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();

const interviewId = ref(null);
const interviewType = ref("tech");
const chatList = ref([]);
const userInput = ref("");
const isTyping = ref(false);
const generatingReport = ref(false);
const chatBoxRef = ref(null);

// 摄像头相关变量
const videoRef = ref(null);
const cameraActive = ref(false);
const lookingAwayCount = ref(0);
const currentStatus = ref("初始化中...");
const hasWarning = ref(false); // 👈 新增：专门控制颜色

let faceLandmarker = null;
let stream = null;
let lastVideoTime = -1;
let animationFrameId = null;
let lastWarningTime = 0; // 👈 新增：防误报节流阀

const scrollToBottom = async () => {
  await nextTick();
  if (chatBoxRef.value) {
    chatBoxRef.value.scrollTop = chatBoxRef.value.scrollHeight;
  }
};

// ================= 摄像头与视觉推理逻辑 =================
const initCameraAndAI = async () => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: false,
    });
    if (videoRef.value) {
      videoRef.value.srcObject = stream;
      cameraActive.value = true;
      currentStatus.value = "模型加载中";
    }

    const filesetResolver = await FilesetResolver.forVisionTasks(
      "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0/wasm",
    );
    faceLandmarker = await FaceLandmarker.createFromOptions(filesetResolver, {
      baseOptions: {
        modelAssetPath:
          "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task", // 换回谷歌官方稳定链接
        delegate: "GPU",
      },
      runningMode: "VIDEO",
      numFaces: 1,
    });
    console.log("✅ MediaPipe 模型加载成功");
    currentStatus.value = "正常监考中";
    hasWarning.value = false;
    detectFace();
  } catch (error) {
    console.error("❌ 摄像头或模型加载失败:", error);
    if (stream) cameraActive.value = true;
    currentStatus.value = "模型加载失败";
    hasWarning.value = true;
  }
};

const detectFace = () => {
  if (!videoRef.value || !faceLandmarker) return;
  const video = videoRef.value;

  if (video.currentTime !== lastVideoTime && video.videoWidth > 0) {
    lastVideoTime = video.currentTime;
    const results = faceLandmarker.detectForVideo(video, performance.now());

    const now = Date.now();

    // 情况1：如果没有任何人脸（离开画面）
    if (!results.faceLandmarks || results.faceLandmarks.length === 0) {
      currentStatus.value = "❌ 检测不到人脸";
      hasWarning.value = true;

      // 🚨 节流阀：距离上次报错超过 2 秒才记录一次，防止一秒加几十次
      if (now - lastWarningTime > 2000) {
        lookingAwayCount.value++;
        lastWarningTime = now;
        console.log(
          "⚠️ 检测不到人脸，离开画面！总次数:",
          lookingAwayCount.value,
        );
      }
    }
    // 情况2：检测到脸了，但偏了
    else {
      const nose = results.faceLandmarks[0][1];
      const noseX = nose.x;

      // 放宽到 0.2 ~ 0.8，正常坐在电脑前轻微晃动不会报警
      if (noseX < 0.2 || noseX > 0.8) {
        currentStatus.value = "⚠️ 视线偏离";
        hasWarning.value = true;
        if (now - lastWarningTime > 2000) {
          lookingAwayCount.value++;
          lastWarningTime = now;
          console.log(
            "⚠️ 视线偏离屏幕！当前鼻尖X:",
            noseX.toFixed(2),
            "总次数:",
            lookingAwayCount.value,
          );
        }
      } else {
        // 回到中间，恢复正常
        currentStatus.value = "正常监考中";
        hasWarning.value = false;
      }
    }
  }
  animationFrameId = requestAnimationFrame(detectFace);
};

onUnmounted(() => {
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
  }
});
// =======================================================

const finishInterview = async () => {
  if (chatList.value.length <= 1)
    return ElMessage.warning("请至少回答一个问题");
  generatingReport.value = true;
  try {
    ElMessage.info("AI 正在复盘面试表现并生成报告...");
    await request.post(
      `/report/generate/${interviewId.value}?look_away=${lookingAwayCount.value}`,
    );
    ElMessage.success("报告生成成功！");
    router.push({ path: "/report", query: { id: interviewId.value } });
  } catch (error) {
    ElMessage.error("生成失败");
  } finally {
    generatingReport.value = false;
  }
};

const sendMessage = async () => {
  if (!userInput.value.trim() || isTyping.value) return;

  const text = userInput.value;
  userInput.value = "";
  chatList.value.push({ role: "user", content: text });
  scrollToBottom();

  isTyping.value = true;
  chatList.value.push({ role: "ai", content: "", typing: true });
  const targetIndex = chatList.value.length - 1;

  let textQueue = [];
  let isFetchFinished = false;

  const renderQueue = async () => {
    while (true) {
      if (textQueue.length > 0) {
        chatList.value[targetIndex].content += textQueue.shift();
        chatList.value = [...chatList.value];
        scrollToBottom();
        await new Promise((resolve) => setTimeout(resolve, 30));
      } else if (isFetchFinished) {
        chatList.value[targetIndex].typing = false;
        isTyping.value = false;
        break;
      } else {
        await new Promise((resolve) => setTimeout(resolve, 50));
      }
    }
  };

  try {
    const response = await fetch("http://127.0.0.1:8001/interview/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${userStore.token}`,
      },
      body: JSON.stringify({
        interview_id: interviewId.value,
        user_message: text,
      }),
    });

    if (!response.ok) throw new Error("网络请求失败");
    renderQueue();

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        isFetchFinished = true;
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        if (part.startsWith("data: ")) {
          const dataStr = part.substring(6);
          if (dataStr === "[DONE]") {
            isFetchFinished = true;
            break;
          }
          try {
            const data = JSON.parse(dataStr);
            textQueue.push(...data.content.split(""));
          } catch (e) {}
        }
      }
    }
  } catch (error) {
    isFetchFinished = true;
    chatList.value[targetIndex].content = "网络异常，请重试。";
    chatList.value[targetIndex].typing = false;
    isTyping.value = false;
  }
};

onMounted(() => {
  interviewId.value = route.query.id;
  interviewType.value = route.query.type || "tech";
  if (!interviewId.value) return router.push("/home");

  let welcome = "你好，我是今天的面试官。简历我看过了，准备好开始了吗？";
  if (interviewType.value === "hr")
    welcome =
      "你好呀，我是公司的 HR。别紧张，咱们就像聊天一样，先做个自我介绍吧。";
  if (interviewType.value === "stress")
    welcome =
      "简历我看了，非常一般。直接说说你最能拿得出手的项目，别浪费我时间。";

  chatList.value.push({ role: "ai", content: welcome, typing: false });

  initCameraAndAI();
});
</script>

<style scoped>
/* 样式保持不变，只要把 hasWarning 绑上去就行 */
.interview-wrapper {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #0b1120;
  position: relative;
  overflow: hidden;
}
.aurora-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  background:
    radial-gradient(
      circle at 15% 50%,
      rgba(56, 189, 248, 0.08),
      transparent 40%
    ),
    radial-gradient(
      circle at 85% 30%,
      rgba(129, 140, 248, 0.08),
      transparent 40%
    );
}
.glass-header,
.glass-footer {
  position: relative;
  z-index: 10;
  background: rgba(15, 23, 42, 0.7);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.glass-header {
  height: 70px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
}
.glass-footer {
  padding: 20px 40px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  border-bottom: none;
  display: flex;
  gap: 15px;
}
.role-title {
  margin: 0;
  font-size: 20px;
  font-weight: bold;
  background: linear-gradient(90deg, #38bdf8, #c084fc);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.chat-area {
  position: relative;
  z-index: 1;
  flex: 1;
  overflow-y: auto;
  padding: 30px 15%;
  display: flex;
  flex-direction: column;
  gap: 25px;
}
.message-row {
  display: flex;
  gap: 15px;
  max-width: 85%;
}
.message-row.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}
.avatar {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  justify-content: center;
  align-items: center;
  font-weight: bold;
  flex-shrink: 0;
  font-size: 15px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}
.avatar.hr {
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: white;
}
.avatar.stress {
  background: linear-gradient(135deg, #ef4444, #b91c1c);
  color: white;
}
.avatar.tech {
  background: linear-gradient(135deg, #0ea5e9, #0284c7);
  color: white;
}
.message-row.user .avatar {
  background: linear-gradient(135deg, #10b981, #047857);
}
.bubble {
  padding: 16px 22px;
  border-radius: 16px;
  font-size: 15px;
  line-height: 1.7;
  white-space: pre-wrap;
  backdrop-filter: blur(10px);
}
.bubble.ai {
  background: rgba(30, 41, 59, 0.8);
  color: #e2e8f0;
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-top-left-radius: 4px;
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
}
.bubble.user {
  background: linear-gradient(135deg, #0ea5e9, #3b82f6);
  color: white;
  border-top-right-radius: 4px;
  box-shadow: 0 10px 20px rgba(14, 165, 233, 0.2);
}
.chat-input {
  flex: 1;
}
:deep(.chat-input .el-input__wrapper) {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 12px;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.1) inset;
  padding: 8px 20px;
}
:deep(.chat-input .el-input__inner) {
  color: #f1f5f9;
  font-size: 15px;
}
.send-btn {
  border-radius: 12px;
  padding: 0 30px;
  font-weight: bold;
  background: linear-gradient(135deg, #38bdf8, #2563eb);
  border: none;
}
.cursor {
  animation: blink 1s infinite;
  color: #38bdf8;
  font-weight: bold;
  margin-left: 2px;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}

/* 摄像头监考悬浮窗 */
.camera-monitor {
  position: absolute;
  bottom: 100px;
  right: 40px;
  width: 220px;
  height: 165px;
  border-radius: 12px;
  overflow: hidden;
  border: 2px solid rgba(56, 189, 248, 0.5);
  box-shadow: 0 0 20px rgba(56, 189, 248, 0.2);
  z-index: 100;
  background: #000;
  transition: all 0.3s ease;
}
.camera-monitor:has(.warning) {
  border-color: #ef4444;
  box-shadow: 0 0 20px rgba(239, 68, 68, 0.4);
}
.camera-monitor video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform: scaleX(-1);
}
.camera-status {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  background: rgba(0, 0, 0, 0.7);
  color: #38bdf8;
  font-size: 13px;
  font-weight: bold;
  padding: 6px 10px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.3s;
}
.camera-status.warning {
  background: rgba(239, 68, 68, 0.9);
  color: white;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #38bdf8;
  animation: pulse 1s infinite alternate;
}
.camera-status.warning .dot {
  background: #fff;
}
@keyframes pulse {
  from {
    opacity: 1;
  }
  to {
    opacity: 0.3;
  }
}
</style>
