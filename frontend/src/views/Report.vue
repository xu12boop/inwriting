<template>
  <div class="report-wrapper">
    <div class="bg-glow"></div>

    <header class="glass-header">
      <h2 class="logo-text">📊 面试能力评估报告</h2>
      <div class="header-actions">
        <el-button type="success" plain round @click="exportReport"
          >导出 / 打印</el-button
        >
        <el-button type="primary" plain round @click="router.push('/home')"
          >返回工作台</el-button
        >
      </div>
    </header>

    <div v-if="loading" class="loading-box">
      <el-icon class="is-loading"><Loading /></el-icon>
      <p>AI 正在复盘面试表现...</p>
    </div>

    <div v-show="!loading && reportData" class="main-content">
      <div class="top-row">
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

      <!-- 逐题复盘：把"哪一轮答得好、哪一轮虚"落到具体问答上 -->
      <div v-if="reviews.length" class="glass-card reviews-card">
        <h3 class="section-title">🔍 逐题复盘</h3>
        <div class="review-list">
          <div
            v-for="(item, index) in reviews"
            :key="index"
            class="review-item"
            :class="'v-' + item.verdict"
          >
            <div class="review-head">
              <span class="review-no">第 {{ index + 1 }} 轮</span>
              <span class="review-verdict">{{ verdictLabel(item.verdict) }}</span>
            </div>
            <div v-if="item.question" class="review-q">
              <span class="q-tag">问</span>{{ item.question }}
            </div>
            <div v-if="item.answer_digest" class="review-a">
              <span class="a-tag">答</span>{{ item.answer_digest }}
            </div>
            <div v-if="item.comment" class="review-comment">{{ item.comment }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import request from "../api/request";
import { ElMessage } from "element-plus";
import { Loading } from "@element-plus/icons-vue";
import * as echarts from "echarts";
import type { ReportData, RadarData } from "../types";

const route = useRoute();
const router = useRouter();

const loading = ref<boolean>(true);
const reportData = ref<ReportData | null>(null);
const radarChartRef = ref<HTMLElement | null>(null);
const completedTasks = ref<string[]>([]);
let chartInstance: any = null;

// 老报告没有逐题点评（列为 NULL），此时整块隐藏，不留空壳
const reviews = computed(() => reportData.value?.question_reviews ?? []);

const VERDICT_LABEL: Record<string, string> = {
  good: "答得扎实",
  ok: "基本达标",
  weak: "需要补",
};
const verdictLabel = (v: string): string => VERDICT_LABEL[v] ?? "待评估";

// 不引入新依赖：直接用浏览器打印，配合 @media print 输出白底可存档版
const exportReport = (): void => {
  ElMessage.success("在打印面板里选择「另存为 PDF」即可保存");
  setTimeout(() => window.print(), 300);
};

onMounted(async () => {
  const interviewId = (route.query.id as string) ?? null;
  if (!interviewId) return router.push("/home");

  try {
    let res;
    try {
      // 优先读取面试结束时已生成（含视觉统计）的报告，避免重复生成覆盖
      res = await request.get(`/report/${interviewId}`);
    } catch (e: any) {
      if (e?.response?.status === 404) {
        // 报告尚未生成（异常路径），兜底触发一次生成
        res = await request.post(`/report/generate/${interviewId}`);
      } else {
        throw e;
      }
    }
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

  const data: RadarData = reportData.value.radar_data || {};
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
  flex-direction: column;
  padding: 40px;
  gap: 30px;
  flex: 1;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}
.top-row {
  display: flex;
  gap: 40px;
  flex: 1;
}
.header-actions {
  display: flex;
  gap: 12px;
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

/* 逐题复盘 */
.review-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.review-item {
  padding: 16px 18px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-left: 3px solid rgba(148, 163, 184, 0.5);
}
.review-item.v-good {
  border-left-color: #10b981;
}
.review-item.v-ok {
  border-left-color: #38bdf8;
}
.review-item.v-weak {
  border-left-color: #f59e0b;
}
.review-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.review-no {
  font-size: 12px;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}
.review-verdict {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 20px;
  color: #cbd5e1;
  background: rgba(255, 255, 255, 0.06);
}
.v-good .review-verdict {
  color: #6ee7b7;
  background: rgba(16, 185, 129, 0.12);
}
.v-ok .review-verdict {
  color: #7dd3fc;
  background: rgba(56, 189, 248, 0.12);
}
.v-weak .review-verdict {
  color: #fcd34d;
  background: rgba(245, 158, 11, 0.12);
}
.review-q,
.review-a {
  display: flex;
  gap: 8px;
  font-size: 13.5px;
  line-height: 1.7;
  margin-bottom: 6px;
  word-break: break-word;
}
.review-q {
  color: #e2e8f0;
}
.review-a {
  color: #94a3b8;
}
.q-tag,
.a-tag {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  line-height: 18px;
  text-align: center;
  border-radius: 5px;
  font-size: 11px;
  margin-top: 2px;
}
.q-tag {
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.14);
}
.a-tag {
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.14);
}
.review-comment {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed rgba(255, 255, 255, 0.07);
  font-size: 13px;
  line-height: 1.7;
  color: #cbd5e1;
}

/* 打印 / 另存 PDF：白底、去按钮、不拆卡片 */
@media print {
  @page {
    margin: 14mm;
  }
  .report-wrapper {
    background: #fff !important;
    min-height: auto;
  }
  .bg-glow,
  .header-actions {
    display: none !important;
  }
  .glass-header {
    background: #fff !important;
    border-bottom: 1px solid #ddd;
    padding: 0 0 12px;
    height: auto;
  }
  .logo-text {
    color: #111 !important;
  }
  .main-content {
    padding: 16px 0 !important;
    gap: 16px;
    max-width: 100%;
  }
  .top-row {
    flex-direction: column;
    gap: 16px;
  }
  .glass-card,
  .review-item {
    background: #fff !important;
    border: 1px solid #ddd !important;
    box-shadow: none !important;
    backdrop-filter: none !important;
    break-inside: avoid;
  }
  .section-title,
  .summary-content,
  .task-text,
  .review-q,
  .review-a,
  .review-comment,
  .total-score .label {
    color: #111 !important;
  }
  .summary-content {
    background: #fafafa !important;
  }
  .echarts-container {
    height: 320px;
  }
  .review-list {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
