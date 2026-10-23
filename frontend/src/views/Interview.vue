<template>
  <div class="interview-container">
    <header class="header">
      <h2>AI 模拟面试间</h2>
      <div>
        <el-button
          type="warning"
          @click="finishInterview"
          :loading="generatingReport"
        >
          生成评估报告
        </el-button>
        <el-button type="danger" plain @click="router.push('/home')"
          >退出</el-button
        >
      </div>
    </header>

    <div class="chat-box" ref="chatBoxRef">
      <div
        v-for="(msg, index) in chatList"
        :key="index"
        :class="['message', msg.role]"
      >
        <div class="avatar">{{ msg.role === "ai" ? "AI" : "我" }}</div>
        <div class="bubble">
          {{ msg.content }}
          <span v-if="msg.role === 'ai' && msg.typing" class="cursor">|</span>
        </div>
      </div>
    </div>

    <div class="input-box">
      <el-input
        v-model="userInput"
        placeholder="输入你的回答，按回车发送..."
        @keyup.enter="sendMessage"
        :disabled="isTyping || generatingReport"
      />
      <el-button type="primary" @click="sendMessage" :loading="isTyping"
        >发送</el-button
      >
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from "vue";
import { useRouter, useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { useUserStore } from "../stores/user";
import request from "../api/request";

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();

const interviewId = ref(null);
const chatList = ref([]);
const userInput = ref("");
const isTyping = ref(false);
const generatingReport = ref(false);
const chatBoxRef = ref(null);

// 自动滚动到最底部
const scrollToBottom = async () => {
  await nextTick();
  if (chatBoxRef.value) {
    chatBoxRef.value.scrollTop = chatBoxRef.value.scrollHeight;
  }
};

// 结束面试，生成报告
const finishInterview = async () => {
  if (chatList.value.length <= 1) {
    return ElMessage.warning("请至少回答一个面试问题再生成报告");
  }

  generatingReport.value = true;
  try {
    ElMessage.info("AI 正在根据面试表现生成评估报告，请稍候...");
    await request.post(`/report/generate/${interviewId.value}`);
    ElMessage.success("报告生成成功！");
    router.push({ path: "/report", query: { id: interviewId.value } });
  } catch (error) {
    console.error("生成报告报错详情:", error);
    ElMessage.error("生成报告失败，请重试");
  } finally {
    generatingReport.value = false;
  }
};

// 发送聊天消息
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

  // 打字机队列渲染器
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
    console.error("对话失败:", error);
    isFetchFinished = true;
    chatList.value[targetIndex].content = "抱歉，网络连接中断。";
    chatList.value[targetIndex].typing = false;
    isTyping.value = false;
  }
};

onMounted(() => {
  // 获取 URL 里的 id 参数
  interviewId.value = route.query.id;
  if (!interviewId.value) {
    ElMessage.error("面试 ID 丢失，请重新开始");
    router.push("/home");
    return;
  }

  chatList.value.push({
    role: "ai",
    content:
      "你好，我是今天的面试官。我已经看过了你的简历，准备好开始了吗？请先简单介绍一下你自己。",
    typing: false,
  });
});
</script>

<style scoped>
.interview-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0f172a;
}
.header {
  height: 60px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 30px;
  background: rgba(30, 41, 59, 0.8);
  border-bottom: 1px solid rgba(56, 189, 248, 0.2);
}
.header h2 {
  margin: 0;
  color: #38bdf8;
}
.chat-box {
  flex: 1;
  overflow-y: auto;
  padding: 30px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.message {
  display: flex;
  gap: 15px;
  max-width: 80%;
}
.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}
.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #38bdf8;
  color: #0f172a;
  display: flex;
  justify-content: center;
  align-items: center;
  font-weight: bold;
  flex-shrink: 0;
}
.message.user .avatar {
  background: #10b981;
}
.bubble {
  background: #1e293b;
  padding: 15px 20px;
  border-radius: 10px;
  color: #e2e8f0;
  line-height: 1.6;
  border: 1px solid rgba(56, 189, 248, 0.2);
  white-space: pre-wrap;
}
.message.user .bubble {
  background: #0284c7;
  border: none;
  color: white;
}
.cursor {
  animation: blink 1s infinite;
  color: #38bdf8;
  font-weight: bold;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
.input-box {
  padding: 20px 30px;
  background: rgba(30, 41, 59, 0.8);
  display: flex;
  gap: 15px;
  border-top: 1px solid rgba(56, 189, 248, 0.2);
}
</style>
