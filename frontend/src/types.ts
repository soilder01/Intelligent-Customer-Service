export type SceneId = 'zhisaotong' | 'ecommerce' | 'hr' | 'property';

export interface SceneConfig {
  id: SceneId;
  name: string;
  description: string;
  tools: string[];
  gradient: [string, string];
}

export interface DashboardSummary {
  reviews: { open: number; highRisk: number; total: number };
  samples: { total: number; labeled: number; unlabeled: number; labelRate: number };
  datasets: { seedCases: number; reviewedCases: number; totalCases: number; byScene: Record<string, { seedCases: number; reviewedCases: number; totalCases: number }> };
}

export interface ChatMessage { role: 'user' | 'assistant'; content: string; }
export interface TraceEvent { time: string; stage: string; detail: string; risk?: 'low' | 'medium' | 'high'; tool?: string; }
export interface ReviewItem { id: string; scene: SceneId; reason: string; query: string; status: 'open' | 'reviewed' | 'fixed' | 'ignored'; }
export interface EvalSample { id: string; scene: SceneId; query: string; status: 'unlabeled' | 'labeled'; keywords: string[]; }
export interface ChatResponse { answer: string; taskId?: string | null; events?: TraceEvent[]; requiresConfirmation?: { action: string; title: string; reason: string } | null; }
