import type { ChatMessage, ChatResponse, DashboardSummary, EvalSample, ReviewItem, SceneConfig, SceneId, TraceEvent } from '../types';
import { dashboard, initialMessages, reviews, samples, scenes, traces } from '../mockData';

const API_BASE = (import.meta.env.VITE_AGENT_API_BASE as string | undefined) ?? '';
const USE_MOCK_API = API_BASE === 'mock';

const sceneGradients: Record<SceneId, [string, string]> = {
  zhisaotong: ['#22d3ee', '#6366f1'],
  ecommerce: ['#fb7185', '#f97316'],
  hr: ['#a78bfa', '#2563eb'],
  property: ['#34d399', '#14b8a6'],
};

function normalizeScene(raw: Partial<SceneConfig>): SceneConfig {
  const id = (raw.id || 'zhisaotong') as SceneId;
  return {
    id,
    name: raw.name || id,
    description: raw.description || '',
    tools: raw.tools || [],
    gradient: raw.gradient || sceneGradients[id] || ['#22d3ee', '#6366f1'],
  };
}

function normalizeDashboard(raw: unknown): DashboardSummary {
  const source = raw as {
    reviews?: { total?: number; open?: number; high_risk?: number; highRisk?: number };
    samples?: { total?: number; labeled?: number; unlabeled?: number; label_rate?: number; labelRate?: number };
    datasets?: {
      seed_cases?: number;
      seedCases?: number;
      reviewed_cases?: number;
      reviewedCases?: number;
      total_cases?: number;
      totalCases?: number;
      by_scene?: Record<string, { seed_cases?: number; reviewed_cases?: number; total_cases?: number }>;
      byScene?: DashboardSummary['datasets']['byScene'];
    };
  };
  const datasetByScene = source.datasets?.byScene || Object.fromEntries(
    Object.entries(source.datasets?.by_scene || {}).map(([scene, stats]) => [
      scene,
      { seedCases: stats.seed_cases || 0, reviewedCases: stats.reviewed_cases || 0, totalCases: stats.total_cases || 0 },
    ]),
  );
  return {
    reviews: {
      total: source.reviews?.total || 0,
      open: source.reviews?.open || 0,
      highRisk: source.reviews?.highRisk || source.reviews?.high_risk || 0,
    },
    samples: {
      total: source.samples?.total || 0,
      labeled: source.samples?.labeled || 0,
      unlabeled: source.samples?.unlabeled || 0,
      labelRate: source.samples?.labelRate || source.samples?.label_rate || 0,
    },
    datasets: {
      seedCases: source.datasets?.seedCases || source.datasets?.seed_cases || 0,
      reviewedCases: source.datasets?.reviewedCases || source.datasets?.reviewed_cases || 0,
      totalCases: source.datasets?.totalCases || source.datasets?.total_cases || 0,
      byScene: datasetByScene,
    },
  };
}

async function getJson<T>(path: string, fallback: T, normalize?: (raw: unknown) => T): Promise<T> {
  if (USE_MOCK_API) return fallback;
  try {
    const response = await fetch(`${API_BASE}${path}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const raw = await response.json();
    return normalize ? normalize(raw) : (raw as T);
  } catch {
    return fallback;
  }
}

async function postJson<T>(path: string, body: unknown, fallback: T): Promise<T> {
  if (USE_MOCK_API) return fallback;
  try {
    const response = await fetch(`${API_BASE}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const raw = await response.json();
    return { answer: raw.answer, taskId: raw.task_id, events: raw.events, requiresConfirmation: raw.requires_confirmation } as T;
  } catch {
    return fallback;
  }
}

export const api = {
  scenes: () => getJson<SceneConfig[]>('/api/scenes', scenes, (raw) => (raw as Partial<SceneConfig>[]).map(normalizeScene)),
  dashboard: () => getJson<DashboardSummary>('/api/dashboard', dashboard, normalizeDashboard),
  messages: () => getJson<ChatMessage[]>('/api/messages', initialMessages),
  traces: () => getJson<TraceEvent[]>('/api/traces', traces),
  reviews: () => getJson<ReviewItem[]>('/api/reviews', reviews),
  samples: () => getJson<EvalSample[]>('/api/samples', samples),
  chat: (sceneId: string, message: string, confirmedActions: string[] = []) => postJson<ChatResponse>('/api/chat', { scene_id: sceneId, message, confirmed_actions: confirmedActions }, { answer: `已收到「${message}」。当前使用 mock fallback，配置 VITE_AGENT_API_BASE 后将调用 Python Agent API。`, events: [] }),
};
