<template>
  <div class="report-container">
    <header class="header">
      <h2>📊 面试能力评估报告</h2>
      <el-button type="primary" plain @click="router.push('/home')"
        >返回工作台</el-button
      >
    </header>

    <div v-if="loading" class="loading-box">
      <el-icon class="is-loading"><Loading /></el-icon>
      <p>正在拼命读取 AI 评估数据...</p>
    </div>

    <!-- 注意这里用了 v-show，保证 DOM 一定会存在 -->
    <div v-show="!loading && reportData" class="main-content">
      <!-- 左侧：雷达图 -->
      <el-card class="chart-card">
        <h3>核心能力画像</h3>
        <!-- 强制写死宽高，防止被 flex 挤压成 0 -->
        <div ref="radarChartRef" style="width: 100%; height: 400px"></div>

        <div class="score-box">
          <p>
            综合得分：<span class="score">{{ reportData?.overall_score }}</span>
            分
          </p>
        </div>
      </el-card>

      <!-- 右侧：AI 总结与学习计划 (生成式 UI) -->
      <el-card class="plan-card">
        <h3>面试官评语</h3>
        <p class="summary">{{ reportData?.summary }}</p>

        <h3 style="margin-top: 30px">📚 AI 推荐学习路线</h3>
        <el-checkbox-group v-model="completedTasks">
          <div
            v-for="(item, index) in reportData?.learning_plan"
            :key="index"
            class="task-item"
          >
            <el-checkbox :label="item.task" border>
              {{ item.task }}
            </el-checkbox>
          </div>
        </el-checkbox-group>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import request from "../api/request";
import { ElMessage } from "element-plus";
import { Loading } from "@element-plus/icons-vue";
import * as echarts from "echarts";

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const reportData = ref(null);
const radarChartRef = ref(null);
const completedTasks = ref([]);
let chartInstance = null;

onMounted(async () => {
  const interviewId = route.query.id;
  if (!interviewId) {
    ElMessage.error("参数错误");
    return router.push("/home");
  }

  try {
    const res = await request.post(`/report/generate/${interviewId}`);
    reportData.value = res;
  } catch (error) {
    console.error("获取报告失败", error);
    ElMessage.error("获取报告失败");
  } finally {
    loading.value = false;
  }
});

// 🚨 核心修复：监听 reportData 的变化。数据一变，等 DOM 渲染完就立刻画图
watch(
  reportData,
  async (newData) => {
    if (newData) {
      await nextTick();
      initChart();
    }
  },
  { deep: true },
);

const initChart = () => {
  if (!radarChartRef.value || !reportData.value) {
    console.warn("雷达图容器未准备好");
    return;
  }

  if (chartInstance) {
    chartInstance.dispose(); // 销毁旧实例，防止热更新冲突
  }

  chartInstance = echarts.init(radarChartRef.value);

  const data = reportData.value.radar_data || {};
  const indicators = Object.keys(data).map((key) => ({ name: key, max: 100 }));
  const values = Object.values(data);

  const option = {
    tooltip: {},
    radar: {
      indicator: indicators,
      axisName: { color: "#38bdf8", fontSize: 14 },
      splitArea: {
        areaStyle: {
          color: ["rgba(56, 189, 248, 0.05)", "rgba(56, 189, 248, 0.1)"],
        },
      },
    },
    series: [
      {
        name: "能力评估",
        type: "radar",
        data: [
          {
            value: values,
            name: "候选人",
            itemStyle: { color: "#38bdf8" },
            areaStyle: { color: "rgba(56, 189, 248, 0.4)" },
          },
        ],
      },
    ],
  };
  chartInstance.setOption(option);
};

// 窗口缩放时自适应
window.addEventListener("resize", () => {
  if (chartInstance) chartInstance.resize();
});
</script>

<style scoped>
.report-container {
  min-height: 100vh;
  background: #0f172a;
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
}
.loading-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 60vh;
  color: #38bdf8;
  font-size: 20px;
}

.main-content {
  display: flex;
  padding: 30px;
  gap: 30px;
}
.chart-card,
.plan-card {
  flex: 1;
  background: rgba(30, 41, 59, 0.6) !important;
  border: 1px solid rgba(56, 189, 248, 0.2) !important;
  color: #e2e8f0;
}
h3 {
  color: #38bdf8;
  margin-top: 0;
}

.score-box {
  text-align: center;
  font-size: 18px;
  margin-top: 10px;
}
.score {
  font-size: 36px;
  color: #10b981;
  font-weight: bold;
}

.summary {
  line-height: 1.8;
  color: #cbd5e1;
  background: rgba(0, 0, 0, 0.2);
  padding: 15px;
  border-radius: 8px;
}

.task-item {
  margin-bottom: 15px;
}
:deep(.el-checkbox.is-bordered) {
  width: 100%;
  height: auto;
  padding: 15px;
  white-space: normal;
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(56, 189, 248, 0.3);
}
:deep(.el-checkbox__label) {
  color: #e2e8f0 !important;
  line-height: 1.5;
}
</style>
