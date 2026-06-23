import type { ChatMessage, ChatResponse, DashboardSummary, EvalSample, HealthStatus, ReviewItem, SceneConfig, SceneId, TraceEvent } from '../types';
import { dashboard, initialMessages, reviews, samples, scenes, traces } from '../mockData';

const API_BASE = (import.meta.env.VITE_AGENT_API_BASE as string | undefined) ?? '';
const USE_MOCK_API = API_BASE === 'mock';
const mockHealth: HealthStatus = { status: 'ok', mode: 'demo', apiOnline: false, modelKeyConfigured: false };
const sceneGradients: Record<SceneId, [string, string]> = { zhisaotong: ['#22d3ee', '#6366f1'], ecommerce: ['#fb7185', '#f97316'], hr: ['#a78bfa', '#2563eb'], property: ['#34d399', '#14b8a6'] };

function normalizeScene(raw: Partial<SceneConfig>): SceneConfig { const id = (raw.id || 'zhisaotong') as SceneId; return { id, name: raw.name || id, description: raw.description || '', tools: raw.tools || [], gradient: raw.gradient || sceneGradients[id] || ['#22d3ee', '#6366f1'] }; }
function normalizeHealth(raw: unknown): HealthStatus { const s = raw as { status?: string; mode?: 'demo' | 'live'; api_online?: boolean; apiOnline?: boolean; model_key_configured?: boolean; modelKeyConfigured?: boolean; generated_at?: string; generatedAt?: string }; return { status: s.status || 'ok', mode: s.mode || 'demo', apiOnline: s.apiOnline ?? s.api_online ?? true, modelKeyConfigured: s.modelKeyConfigured ?? s.model_key_configured ?? false, generatedAt: s.generatedAt || s.generated_at }; }
function normalizeDashboard(raw: unknown): DashboardSummary { const s = raw as { reviews?: { total?: number; open?: number; high_risk?: number; highRisk?: number }; samples?: { total?: number; labeled?: number; unlabeled?: number; label_rate?: number; labelRate?: number }; datasets?: { seed_cases?: number; seedCases?: number; reviewed_cases?: number; reviewedCases?: number; total_cases?: number; totalCases?: number; by_scene?: Record<string, { seed_cases?: number; reviewed_cases?: number; total_cases?: number }>; byScene?: DashboardSummary['datasets']['byScene'] } }; const byScene = s.datasets?.byScene || Object.fromEntries(Object.entries(s.datasets?.by_scene || {}).map(([scene, stats]) => [scene, { seedCases: stats.seed_cases || 0, reviewedCases: stats.reviewed_cases || 0, totalCases: stats.total_cases || 0 }])); return { reviews: { total: s.reviews?.total || 0, open: s.reviews?.open || 0, highRisk: s.reviews?.highRisk || s.reviews?.high_risk || 0 }, samples: { total: s.samples?.total || 0, labeled: s.samples?.labeled || 0, unlabeled: s.samples?.unlabeled || 0, labelRate: s.samples?.labelRate || s.samples?.label_rate || 0 }, datasets: { seedCases: s.datasets?.seedCases || s.datasets?.seed_cases || 0, reviewedCases: s.datasets?.reviewedCases || s.datasets?.reviewed_cases || 0, totalCases: s.datasets?.totalCases || s.datasets?.total_cases || 0, byScene } }; }

async function getJson<T>(path: string, fallback: T, normalize?: (raw: unknown) => T): Promise<T> { if (USE_MOCK_API) return fallback; try { const response = await fetch(`${API_BASE}${path}`); if (!response.ok) throw new Error(`HTTP ${response.status}`); const raw = await response.json(); return normalize ? normalize(raw) : (raw as T); } catch { return fallback; } }
async function postJson<T>(path: string, body: unknown, fallback: T): Promise<T> { if (USE_MOCK_API) return fallback; try { const response = await fetch(`${API_BASE}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); if (!response.ok) throw new Error(`HTTP ${response.status}`); return (await response.json()) as T; } catch { return fallback; } }

export const api = {
  health: () => getJson<HealthStatus>('/api/health', mockHealth, normalizeHealth),
  scenes: () => getJson<SceneConfig[]>('/api/scenes', scenes, (raw) => (raw as Partial<SceneConfig>[]).map(normalizeScene)),
  dashboard: () => getJson<DashboardSummary>('/api/dashboard', dashboard, normalizeDashboard),
  messages: () => getJson<ChatMessage[]>('/api/messages', initialMessages),
  traces: () => getJson<TraceEvent[]>('/api/traces', traces),
  reviews: () => getJson<ReviewItem[]>('/api/reviews', reviews),
  samples: () => getJson<EvalSample[]>('/api/samples', samples),
  chat: async (sceneId: string, message: string, confirmedActions: string[] = []) => {
    const raw = await postJson<Record<string, unknown>>('/api/chat', { scene_id: sceneId, message, confirmed_actions: confirmedActions }, { answer: `已收到「${message}」。当前为 Demo fallback，后端不可用时会用该结果保持页面可演示。`, events: [], mode: 'demo' });
    return { answer: raw.answer as string, taskId: raw.task_id as string | null, events: raw.events as TraceEvent[], requiresConfirmation: raw.requires_confirmation as ChatResponse['requiresConfirmation'], mode: raw.mode as ChatResponse['mode'] };
  },
  updateReviewStatus: (reviewId: string, status: ReviewItem['status']) => postJson('/api/reviews/' + reviewId + '/status', { status }, { ok: true }),
  labelSample: (sampleId: string, expectedKeywords: string[], note = '') => postJson('/api/samples/' + sampleId + '/label', { expected_keywords: expectedKeywords, note }, { ok: true }),
  exportReviewed: (sceneId?: string) => postJson<{ ok: boolean; path?: string }>('/api/datasets/export-reviewed', { scene_id: sceneId }, { ok: true, path: 'eval/datasets/mock_reviewed.jsonl' }),
};
