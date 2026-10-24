<template>
  <div class="report-wrapper">
    <div class="bg-glow"></div>

    <header class="glass-header">
      <h2 class="logo-text">📊 面试能力评估报告</h2>
      <el-button type="primary" plain round @click="router.push('/home')"
        >返回工作台</el-button
      >
    </header>

    <div v-if="loading" class="loading-box">
      <el-icon class="is-loading"><Loading /></el-icon>
      <p>AI 正在复盘面试表现...</p>
    </div>

    <div v-show="!loading && reportData" class="main-content">
      <!-- 左侧雷达图 -->
      <div class="glass-card chart-card">
        <h3 class="section-title">核心能力雷达</h3>
        <div ref="radarChartRef" class="echarts-container"></div>

        <div class="total-score">
          <span class="label">综合得分</span>
          <span class="num">{{ reportData?.overall_score }}</span>
        </div>
      </div>

      <!-- 右侧评语与任务 -->
      <div class="right-panel">
        <div class="glass-card summary-card">
          <h3 class="section-title">📝 面试官评语</h3>
          <div class="summary-content">{{ reportData?.summary }}</div>
        </div>

        <div class="glass-card plan-card">
          <h3 class="section-title">🚀 AI 推荐学习路线</h3>
          <el-checkbox-group v-model="completedTasks" class="task-list">
            <div
              v-for="(item, index) in reportData?.learning_plan"
              :key="index"
              class="task-item-wrapper"
            >
              <el-checkbox :label="item.task" class="custom-checkbox">
                <span class="task-text">{{ item.task }}</span>
              </el-checkbox>
            </div>
          </el-checkbox-group>
        </div>
      </div>
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
  if (!interviewId) return router.push("/home");

  try {
    const res = await request.post(`/report/generate/${interviewId}`);
    reportData.value = res;
  } catch (error) {
    ElMessage.error("获取报告失败");
  } finally {
    loading.value = false;
  }
});

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
  if (!radarChartRef.value || !reportData.value) return;
  if (chartInstance) chartInstance.dispose();
  chartInstance = echarts.init(radarChartRef.value);

  const data = reportData.value.radar_data || {};
  const indicators = Object.keys(data).map((key) => ({ name: key, max: 100 }));
  const values = Object.values(data);

  const option = {
    radar: {
      indicator: indicators,
      axisName: { color: "#94a3b8", fontSize: 14 },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.1)" } },
      splitArea: {
        areaStyle: {
          color: ["rgba(56, 189, 248, 0.02)", "rgba(56, 189, 248, 0.05)"],
        },
      },
      axisLine: { lineStyle: { color: "rgba(255,255,255,0.1)" } },
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
            lineStyle: { width: 2, shadowColor: "#38bdf8", shadowBlur: 10 },
            areaStyle: {
              color: new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
                { offset: 0, color: "rgba(56, 189, 248, 0.6)" },
                { offset: 1, color: "rgba(56, 189, 248, 0.1)" },
              ]),
            },
          },
        ],
      },
    ],
  };
  chartInstance.setOption(option);
};
</script>

<style scoped>
.report-wrapper {
  min-height: 100vh;
  background-color: #0b1120;
  position: relative;
  display: flex;
  flex-direction: column;
}
.bg-glow {
  position: absolute;
  width: 600px;
  height: 600px;
  background: radial-gradient(
    circle,
    rgba(56, 189, 248, 0.1) 0%,
    transparent 60%
  );
  bottom: -100px;
  left: -100px;
  z-index: 0;
}

.glass-header {
  position: relative;
  z-index: 10;
  height: 70px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
  background: rgba(15, 23, 42, 0.7);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.logo-text {
  margin: 0;
  color: #f8fafc;
  font-size: 20px;
  font-weight: bold;
}

.loading-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 60vh;
  color: #38bdf8;
  font-size: 18px;
  z-index: 1;
}
.loading-box .el-icon {
  font-size: 40px;
  margin-bottom: 20px;
}

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

.glass-card {
  background: rgba(30, 41, 59, 0.4);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  padding: 30px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
}
.section-title {
  color: #f1f5f9;
  margin-top: 0;
  margin-bottom: 20px;
  font-size: 18px;
  border-left: 4px solid #38bdf8;
  padding-left: 12px;
}

/* 左侧雷达图区域 */
.chart-card {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.echarts-container {
  width: 100%;
  height: 400px;
  flex: 1;
}
.total-score {
  margin-top: 20px;
  text-align: center;
  display: flex;
  justify-content: center;
  align-items: baseline;
  gap: 10px;
}
.total-score .label {
  color: #94a3b8;
  font-size: 16px;
}
.total-score .num {
  font-size: 50px;
  font-weight: 900;
  color: #10b981;
  line-height: 1;
  text-shadow: 0 0 20px rgba(16, 185, 129, 0.4);
}

/* 右侧内容区 */
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 30px;
}
.summary-card {
  flex: 1;
}
.summary-content {
  color: #cbd5e1;
  line-height: 1.8;
  font-size: 15px;
  background: rgba(0, 0, 0, 0.2);
  padding: 20px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

/* 任务列表 */
.plan-card {
  flex: 1;
  overflow-y: auto;
}
.task-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
  width: 100%;
}
.task-item-wrapper {
  width: 100%;
}
.custom-checkbox {
  width: 100%;
  height: auto;
  padding: 16px 20px;
  margin: 0;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  transition: all 0.3s;
}
.custom-checkbox:hover {
  background: rgba(56, 189, 248, 0.1);
  border-color: rgba(56, 189, 248, 0.3);
}
.task-text {
  color: #e2e8f0;
  white-space: normal;
  line-height: 1.5;
  font-size: 14px;
  margin-left: 10px;
}

:deep(.el-checkbox__inner) {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  border-color: rgba(255, 255, 255, 0.2);
}
:deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background-color: #38bdf8;
  border-color: #38bdf8;
}
:deep(.el-checkbox__input.is-checked + .el-checkbox__label) {
  color: #64748b !important;
  text-decoration: line-through;
}
</style>
