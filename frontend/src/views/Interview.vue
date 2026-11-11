<template>
  <div class="interview-wrapper">
    <div class="aurora-bg"></div>

    <header class="glass-header">
      <h2 class="role-title">
        <span v-if="interviewType === 'hr'">👩‍💼 HR 综合面试间</span>
        <span v-else-if="interviewType === 'stress'">😈 极限压力面试间</span>
        <span v-else>👨‍💻 深度技术面试间</span>
      </h2>
      <div class="header-right">
        <div class="round-chip" :class="{ over: interviewOver }">
          <span class="round-main">第 {{ Math.max(answeredRounds, 1) }} / {{ maxRounds }} 轮</span>
          <span class="round-sub">{{
            interviewOver ? "面试已结束，正在生成报告" : "答完一轮自动追问"
          }}</span>
        </div>
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

    <div class="workspace">
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

      <!-- 🧠 决策面板：把规划 Agent 每轮的判断摊开，让"为什么这么问"可见 -->
      <aside class="decision-panel" :class="{ collapsed: !panelOpen }">
        <div class="panel-head">
          <span class="panel-title">面试官决策</span>
          <button class="panel-toggle" @click="panelOpen = !panelOpen">
            {{ panelOpen ? "收起" : "展开" }}
          </button>
        </div>

        <div v-show="panelOpen" class="panel-body">
          <div v-if="!plan.has_plan" class="panel-empty">{{ planHint }}</div>

          <template v-else>
            <div class="decision-badge" :class="decisionMeta.cls">
              {{ decisionMeta.label }}
              <span class="decision-key">{{ plan.decision }}</span>
            </div>

            <div class="panel-block">
              <div class="panel-label">聚焦点</div>
              <div class="panel-text">{{ focusMain || "—" }}</div>
              <div v-if="focusRef" class="panel-ref">
                <span class="ref-tag">检索依据</span>
                <span class="ref-text">{{ focusRef }}</span>
              </div>
            </div>

            <div class="panel-block">
              <div class="panel-label">为什么这么问</div>
              <div class="panel-text">{{ plan.reasoning || "—" }}</div>
            </div>

            <div class="panel-block" v-if="plan.tool_calls.length">
              <div class="panel-label">本轮调用工具</div>
              <div class="tool-list">
                <span class="tool-chip" v-for="t in plan.tool_calls" :key="t.name">{{
                  t.name
                }}</span>
              </div>
            </div>

            <div class="panel-foot">规划 Agent · 每轮刷新一次</div>
          </template>
        </div>
      </aside>
    </div>

    <!-- 🚨 摄像头监考悬浮窗 -->
    <div
      class="camera-monitor"
      :class="panelOpen ? 'shift-left' : 'shift-min'"
      v-show="cameraActive"
    >
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
        :placeholder="
          interviewOver
            ? '本次面试已结束，正在生成评估报告…'
            : '输入你的回答，按 Enter 发送...'
        "
        class="chat-input"
        @keyup.enter="sendMessage"
        :disabled="isTyping || generatingReport || interviewOver"
      />
      <el-button
        type="primary"
        class="send-btn"
        @click="sendMessage"
        :loading="isTyping"
        :disabled="interviewOver"
        >发送</el-button
      >
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from "vue";
import { useRouter, useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { useUserStore } from "../stores/user";
import request from "../api/request";
import { API_BASE } from "../api/base";
import { FaceLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";
import type { ChatMessage } from "../types";

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();

const interviewId = ref<string | null>(null);
const interviewType = ref<string>("tech");
const chatList = ref<ChatMessage[]>([]);
const userInput = ref<string>("");
const isTyping = ref<boolean>(false);
const generatingReport = ref<boolean>(false);
const chatBoxRef = ref<HTMLElement | null>(null);

// ================= 决策面板与轮次进度 =================
// 一场面试问几轮：技术面最多、压力面最短，符合真实面试的节奏差异。
const ROUND_LIMIT: Record<string, number> = { tech: 6, hr: 5, stress: 4 };
const maxRounds = computed<number>(() => ROUND_LIMIT[interviewType.value] ?? 6);
const answeredRounds = ref<number>(0);
const interviewOver = ref<boolean>(false);
const panelOpen = ref<boolean>(true);

type PlanView = {
  has_plan: boolean;
  round_no: number;
  max_rounds: number;
  decision: string;
  focus: string;
  reasoning: string;
  tool_calls: { name: string; arguments?: unknown; result?: string }[];
};

const emptyPlan: PlanView = {
  has_plan: false,
  round_no: 0,
  max_rounds: 0,
  decision: "",
  focus: "",
  reasoning: "",
  tool_calls: [],
};
const plan = ref<PlanView>({ ...emptyPlan });
const planFetchedOnce = ref<boolean>(false);

const DECISION_META: Record<string, { label: string; cls: string }> = {
  deepen: { label: "深挖", cls: "d-deepen" },
  switch: { label: "换方向", cls: "d-switch" },
  pressure: { label: "加压", cls: "d-pressure" },
  press: { label: "加压", cls: "d-pressure" },
  close: { label: "收尾", cls: "d-close" },
};

const decisionMeta = computed(() => {
  const raw = (plan.value.decision || "").toLowerCase();
  for (const key of Object.keys(DECISION_META)) {
    if (raw.includes(key)) return DECISION_META[key];
  }
  return { label: "待判定", cls: "d-idle" };
});

// focus 里可能被 planner 追加了"参考资料：[工具:xxx] …"，拆开显示，避免正文被工具原文淹没
const focusMain = computed(
  () => (plan.value.focus || "").split("\n参考资料：")[0].trim(),
);
const focusRef = computed(() => {
  const parts = (plan.value.focus || "").split("\n参考资料：");
  if (parts.length < 2) return "";
  return parts.slice(1).join(" ").replace(/\s+/g, " ").slice(0, 200);
});

const planHint = computed(() => {
  if (interviewOver.value) {
    return "面试已结束，正在为你生成评估报告。往轮的判断仍可在这里回看。";
  }
  if (answeredRounds.value === 0) {
    return "开场轮不做规划：面试官直接出题，省掉十几秒等待。你答完第一轮，这里会显示它的判断。";
  }
  if (answeredRounds.value === 1) {
    return "第一轮用来定基线，规划 Agent 从第二轮开始介入。再答一轮，这里会显示它为什么这么问。";
  }
  return "本轮规划尚未返回，通常在你开始回答后 1-2 秒内刷新。";
});

/** 拉取最近一轮规划结果；失败静默处理，不让侧栏接口影响面试主流程 */
const loadPlan = async () => {
  if (!interviewId.value) return;
  try {
    const res: any = await request.get(`/interview/plan/${interviewId.value}`);
    if (res?.has_plan) {
      plan.value = {
        has_plan: true,
        round_no: res.round_no ?? 0,
        max_rounds: res.max_rounds ?? 0,
        decision: res.decision ?? "",
        focus: res.focus ?? "",
        reasoning: res.reasoning ?? "",
        tool_calls: Array.isArray(res.tool_calls) ? res.tool_calls : [],
      };
      planFetchedOnce.value = true;
    } else if (!planFetchedOnce.value) {
      plan.value = { ...emptyPlan };
    }
  } catch {
    /* 决策面板属于展示层，取不到就当没有 */
  }
};

// 摄像头相关变量
const videoRef = ref<HTMLVideoElement | null>(null);
const cameraActive = ref<boolean>(false);
const lookingAwayCount = ref<number>(0);
const currentStatus = ref<string>("初始化中...");
const hasWarning = ref<boolean>(false); // 👈 新增：专门控制颜色

let faceLandmarker: any = null;
let stream: MediaStream | null = null;
let lastVideoTime = -1;
let animationFrameId: number | null = null;
let lastWarningTime = 0; // 👈 新增：防误报节流阀

const scrollToBottom = async () => {
  await nextTick();
  if (chatBoxRef.value) {
    chatBoxRef.value.scrollTop = chatBoxRef.value.scrollHeight;
  }
};

// ================= 摄像头与视觉推理逻辑 =================
// 静态资源前缀（兼容部署到子路径）
const ASSET_BASE = import.meta.env.BASE_URL;

// 加载超时保护：网络或模型异常时给出明确提示，而不是永久卡在“模型加载中”
const withTimeout = <T,>(p: Promise<T>, ms: number, label: string): Promise<T> => {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error(`${label} 超时（${ms / 1000}s）`)),
      ms,
    );
    p.then((v) => {
      clearTimeout(timer);
      resolve(v);
    }).catch((e) => {
      clearTimeout(timer);
      reject(e);
    });
  });
};

const createLandmarker = (resolver: any, delegate: "GPU" | "CPU") =>
  FaceLandmarker.createFromOptions(resolver, {
    baseOptions: {
      // 模型已随项目打包在 public/models 下，不再依赖境外 storage.googleapis.com
      modelAssetPath: `${ASSET_BASE}models/face_landmarker.task`,
      delegate,
    },
    runningMode: "VIDEO",
    numFaces: 1,
  });

const initCameraAndAI = async () => {
  // 浏览器只在「安全上下文」（HTTPS / localhost / 127.0.0.1）下暴露 navigator.mediaDevices。
  // 通过 http://公网IP 访问时该对象为 undefined，直接调用 .getUserMedia 会抛 TypeError，
  // 提示会变成一段看不懂的英文。这里提前判空，给出可读的中文说明。
  if (!navigator.mediaDevices?.getUserMedia) {
    cameraActive.value = false;
    currentStatus.value = "当前环境不支持摄像头";
    hasWarning.value = false;
    console.warn(
      "[视觉监考] mediaDevices 不可用，已跳过 | isSecureContext =",
      window.isSecureContext,
      "| origin =",
      window.location.origin,
    );
    ElMessage.warning(
      window.isSecureContext
        ? "当前浏览器未提供摄像头接口，视觉监考已跳过（面试仍可正常进行）"
        : "当前为 HTTP 访问，浏览器安全策略禁止调用摄像头；视觉监考需 HTTPS 或 localhost（面试仍可正常进行）",
    );
    return;
  }

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

    // wasm 使用 node_modules 内同版本资源（1.1.1），避免 JS 与 wasm 跨版本不匹配导致静默挂死
    const filesetResolver = await withTimeout(
      FilesetResolver.forVisionTasks(`${ASSET_BASE}mediapipe/wasm`),
      20000,
      "MediaPipe WASM 加载",
    );

    let landmarker: any;
    try {
      landmarker = await withTimeout(
        createLandmarker(filesetResolver, "GPU"),
        30000,
        "人脸模型加载",
      );
    } catch (gpuError) {
      // 部分机器/无 GPU 的浏览器中 GPU delegate 会失败，回退 CPU 推理
      console.warn("⚠️ GPU 推理初始化失败，回退 CPU 模式:", gpuError);
      landmarker = await withTimeout(
        createLandmarker(filesetResolver, "CPU"),
        30000,
        "人脸模型加载(CPU)",
      );
    }
    faceLandmarker = landmarker;
    console.log("✅ MediaPipe 模型加载成功");
    currentStatus.value = "正常监考中";
    hasWarning.value = false;
    detectFace();
  } catch (error) {
    console.error("❌ 摄像头或模型加载失败:", error);
    const msg = error instanceof Error ? error.message : String(error);
    const name = error instanceof DOMException ? error.name : "";

    // 按浏览器错误类型给出可区分的提示，避免把"没授权"和"模型加载失败"混为一谈
    let status = "视觉监考不可用";
    let tip = `视觉监考模型加载失败：${msg}（面试仍可正常进行）`;
    if (name === "NotAllowedError" || name === "SecurityError") {
      status = "摄像头未授权";
      tip = "未获取到摄像头权限，视觉监考已跳过（面试仍可正常进行）";
    } else if (name === "NotFoundError" || name === "OverconstrainedError") {
      status = "未检测到摄像头";
      tip = "未检测到可用摄像头，视觉监考已跳过（面试仍可正常进行）";
    } else if (name === "NotReadableError") {
      status = "摄像头被占用";
      tip = "摄像头可能被其他程序占用，视觉监考已跳过（面试仍可正常进行）";
    }

    if (stream) cameraActive.value = true;
    currentStatus.value = status;
    hasWarning.value = true;
    ElMessage.error(tip);
  }
};

const detectFace = () => {
  if (!videoRef.value || !faceLandmarker) return;
  const video = videoRef.value;

  if (video.currentTime !== lastVideoTime && video.videoWidth > 0) {
    lastVideoTime = video.currentTime;
    let results: any;
    try {
      results = faceLandmarker.detectForVideo(video, performance.now());
    } catch (e) {
      // 单帧推理失败（如视频尚未就绪）不应中断整个监考循环
      console.warn("人脸检测单帧异常，已跳过:", e);
      animationFrameId = requestAnimationFrame(detectFace);
      return;
    }

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
  if (faceLandmarker) {
    try {
      faceLandmarker.close();
    } catch {
      /* 已释放则忽略 */
    }
    faceLandmarker = null;
  }
});
// =======================================================

const finishInterview = async () => {
  if (chatList.value.length <= 1)
    return ElMessage.warning("请至少回答一个问题");
  // 自动收尾与手动点击可能同时触发，这里加锁，避免重复请求互相覆盖报告
  if (generatingReport.value) return;
  generatingReport.value = true;
  try {
    ElMessage.info("AI 正在复盘面试表现，约需 30-90 秒，请稍候…");
    await request.post(
      `/report/generate/${interviewId.value}?look_away=${lookingAwayCount.value}`,
    );
    ElMessage.success("报告生成成功！");
    router.push({ path: "/report", query: { id: interviewId.value } });
  } catch (error: any) {
    // 把真实原因显示出来：超时 / 网络中断 / 后端报错，三种处置方式完全不同
    const isTimeout =
      error?.code === "ECONNABORTED" || /timeout/i.test(error?.message || "");
    const detail = isTimeout
      ? "生成超时，模型响应过慢，请点「生成评估报告」重试"
      : error?.response?.data?.detail || error?.message || "未知错误";
    ElMessage.error(`报告生成失败：${detail}`);
    console.error("[report] 生成失败", error?.response?.status, error);
  } finally {
    generatingReport.value = false;
  }
};

const sendMessage = async () => {
  if (interviewOver.value || !userInput.value.trim() || isTyping.value) return;

  const text = userInput.value;
  userInput.value = "";
  answeredRounds.value += 1;
  const roundNo = answeredRounds.value;
  chatList.value.push({ role: "user", content: text });
  scrollToBottom();

  isTyping.value = true;
  chatList.value.push({ role: "ai", content: "", typing: true });
  const targetIndex = chatList.value.length - 1;

  let textQueue: string[] = [];
  let isFetchFinished: boolean = false;

  const renderQueue = async () => {
    while (true) {
      if (textQueue.length > 0) {
        chatList.value[targetIndex].content += textQueue.shift() ?? "";
        chatList.value = [...chatList.value];
        scrollToBottom();
        await new Promise((resolve) => setTimeout(resolve, 30));
      } else if (isFetchFinished) {
        chatList.value[targetIndex].typing = false;
        isTyping.value = false;
        // 到达轮次上限：这一句是面试官的收尾，随后自动跳到报告页
        if (roundNo >= maxRounds.value && !interviewOver.value) {
          interviewOver.value = true;
          ElMessage.success(
            `本次面试共 ${maxRounds.value} 轮，已结束，正在生成评估报告…`,
          );
          setTimeout(() => {
            void finishInterview();
          }, 1800);
        }
        break;
      } else {
        await new Promise((resolve) => setTimeout(resolve, 50));
      }
    }
  };

  try {
    const response = await fetch(`${API_BASE}/interview/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${userStore.token}`,
      },
      body: JSON.stringify({
        interview_id: interviewId.value,
        user_message: text,
        round_no: roundNo,
        max_rounds: maxRounds.value,
      }),
    });

    if (!response.ok) throw new Error("网络请求失败");
    if (!response.body) throw new Error("浏览器不支持流式响应");
    // 规划在流式开始前就已算完，此刻拉取即可让右栏先于提问刷新
    void loadPlan();
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
            textQueue.push(...(data.content as string).split(""));
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
  interviewId.value = (route.query.id as string) ?? null;
  interviewType.value = (route.query.type as string) || "tech";
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
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
/* 左右两栏：左对话、右决策。workspace 接管原来的 flex:1 */
.workspace {
  position: relative;
  z-index: 1;
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}
.chat-area {
  position: relative;
  z-index: 1;
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 30px 40px;
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

/* ================= 决策面板 ================= */
.decision-panel {
  position: relative;
  z-index: 2;
  width: 340px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: rgba(15, 23, 42, 0.55);
  border-left: 1px solid rgba(255, 255, 255, 0.07);
  backdrop-filter: blur(16px);
  transition: width 0.22s ease;
}
.decision-panel.collapsed {
  width: 44px;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 16px 16px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.panel-title {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #94a3b8;
}
.panel-toggle {
  border: none;
  background: rgba(56, 189, 248, 0.12);
  color: #38bdf8;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}
.panel-toggle:hover {
  background: rgba(56, 189, 248, 0.24);
}
.decision-panel.collapsed .panel-head {
  padding: 14px 0;
  justify-content: center;
}
.decision-panel.collapsed .panel-title {
  display: none;
}
.decision-panel.collapsed .panel-toggle {
  writing-mode: vertical-rl;
  padding: 10px 4px;
}
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.panel-empty {
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
  padding: 8px 2px;
}
.decision-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  align-self: flex-start;
  padding: 7px 14px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  border: 1px solid transparent;
}
.decision-key {
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: 11px;
  font-weight: 400;
  opacity: 0.65;
}
.d-deepen {
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.1);
  border-color: rgba(56, 189, 248, 0.28);
}
.d-switch {
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.1);
  border-color: rgba(167, 139, 250, 0.28);
}
.d-pressure {
  color: #fbbf24;
  background: rgba(251, 191, 36, 0.1);
  border-color: rgba(251, 191, 36, 0.28);
}
.d-close {
  color: #34d399;
  background: rgba(52, 211, 153, 0.1);
  border-color: rgba(52, 211, 153, 0.28);
}
.d-idle {
  color: #94a3b8;
  background: rgba(148, 163, 184, 0.1);
  border-color: rgba(148, 163, 184, 0.24);
}
.panel-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.panel-label {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: #64748b;
  text-transform: uppercase;
}
.panel-text {
  font-size: 13.5px;
  line-height: 1.75;
  color: #cbd5e1;
  white-space: pre-wrap;
  word-break: break-word;
}
.panel-ref {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-top: 2px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(56, 189, 248, 0.06);
  border-left: 2px solid rgba(56, 189, 248, 0.5);
}
.ref-tag {
  flex-shrink: 0;
  font-size: 10.5px;
  color: #38bdf8;
  padding-top: 2px;
  white-space: nowrap;
}
.ref-text {
  font-size: 12px;
  line-height: 1.7;
  color: #94a3b8;
  word-break: break-word;
}
.tool-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tool-chip {
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: 11.5px;
  padding: 4px 10px;
  border-radius: 7px;
  color: #c4b5fd;
  background: rgba(139, 92, 246, 0.12);
  border: 1px solid rgba(139, 92, 246, 0.25);
}
.tool-digest {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.7;
  color: #94a3b8;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  word-break: break-word;
}
.panel-foot {
  margin-top: auto;
  padding-top: 10px;
  font-size: 11px;
  color: #475569;
  border-top: 1px dashed rgba(255, 255, 255, 0.06);
}

/* 顶栏轮次角标 */
.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}
.round-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  padding: 6px 14px;
  border-radius: 10px;
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.22);
  transition: all 0.25s;
}
.round-main {
  font-size: 14px;
  font-weight: 600;
  color: #7dd3fc;
  font-variant-numeric: tabular-nums;
}
.round-sub {
  font-size: 11px;
  color: #64748b;
}
.round-chip.over {
  background: rgba(52, 211, 153, 0.1);
  border-color: rgba(52, 211, 153, 0.3);
}
.round-chip.over .round-main {
  color: #6ee7b7;
}

@media (max-width: 1200px) {
  .decision-panel {
    width: 300px;
  }
  .chat-area {
    padding: 24px 24px;
  }
}
@media (max-width: 980px) {
  .decision-panel {
    width: 260px;
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
/* 决策栏展开时给摄像头让位，避免被右栏压住 */
.camera-monitor.shift-left {
  right: 364px;
}
.camera-monitor.shift-min {
  right: 68px;
}
@media (max-width: 1200px) {
  .camera-monitor.shift-left {
    right: 324px;
  }
}
@media (max-width: 980px) {
  .camera-monitor.shift-left {
    right: 284px;
  }
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
