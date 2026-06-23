import type { ChatMessage, DashboardSummary, EvalSample, ReviewItem, SceneConfig, TraceEvent } from './types';

export const scenes: SceneConfig[] = [
  { id: 'zhisaotong', name: '智扫通客服', description: '设备使用、故障排查、知识库检索智能客服', tools: ['rag_summarize', 'get_weather', 'get_user_location', 'fetch_external_data'], gradient: ['#22d3ee', '#6366f1'] },
  { id: 'ecommerce', name: '电商售后客服', description: '订单查询、退换货、产品使用、保修政策智能客服', tools: ['rag_summarize', 'get_user_id', 'fetch_external_data'], gradient: ['#fb7185', '#f97316'] },
  { id: 'hr', name: '企业HR助手', description: '员工入职、考勤、薪酬、团建、人事制度智能助手', tools: ['rag_summarize', 'get_current_month', 'fetch_external_data'], gradient: ['#a78bfa', '#2563eb'] },
  { id: 'property', name: '园区物业客服', description: '业主报修、物业费、停车、园区公告智能客服', tools: ['rag_summarize', 'get_weather', 'get_user_location'], gradient: ['#34d399', '#14b8a6'] },
];

export const dashboard: DashboardSummary = {
  reviews: { open: 0, highRisk: 0, total: 0 },
  samples: { total: 0, labeled: 0, unlabeled: 0, labelRate: 0 },
  datasets: {
    seedCases: 20,
    reviewedCases: 0,
    totalCases: 20,
    byScene: {
      zhisaotong: { seedCases: 5, reviewedCases: 0, totalCases: 5 },
      ecommerce: { seedCases: 5, reviewedCases: 0, totalCases: 5 },
      hr: { seedCases: 5, reviewedCases: 0, totalCases: 5 },
      property: { seedCases: 5, reviewedCases: 0, totalCases: 5 },
    },
  },
};

export const initialMessages: ChatMessage[] = [
  { role: 'assistant', content: '你好，我是新版企业 Agent 工作台。你可以切换场景、发起问答、查看执行轨迹，并把真实问题沉淀为评测样本。' },
];

export const traces: TraceEvent[] = [
  { time: '14:44:04', stage: 'intent_detected', detail: '识别用户意图并绑定当前场景', risk: 'low' },
  { time: '14:44:05', stage: 'rag_retrieval', detail: '检索场景知识库并生成带引用的上下文', risk: 'low', tool: 'rag_summarize' },
  { time: '14:44:06', stage: 'quality_gate', detail: '写入任务轨迹，等待 reviewed 样本回归', risk: 'medium' },
];

export const reviews: ReviewItem[] = [];
export const samples: EvalSample[] = [];
