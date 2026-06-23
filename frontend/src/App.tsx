import { useEffect, useMemo, useState } from 'react';
import { api } from './api/client';
import { ChatPanel } from './components/ChatPanel';
import { Hero } from './components/Hero';
import { QualityDashboard } from './components/QualityDashboard';
import { ReviewQueue } from './components/ReviewQueue';
import { SampleManager } from './components/SampleManager';
import { Sidebar } from './components/Sidebar';
import { TraceTimeline } from './components/TraceTimeline';
import type { ChatMessage, DashboardSummary, EvalSample, ReviewItem, SceneConfig, SceneId, TraceEvent } from './types';
import './styles.css';

export default function App() {
  const [scenes, setScenes] = useState<SceneConfig[]>([]);
  const [sceneId, setSceneId] = useState<SceneId>('zhisaotong');
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [samples, setSamples] = useState<EvalSample[]>([]);

  useEffect(() => {
    Promise.all([api.scenes(), api.dashboard(), api.messages(), api.traces(), api.reviews(), api.samples()]).then(([sceneData, dashboardData, messageData, traceData, reviewData, sampleData]) => {
      setScenes(sceneData); setDashboard(dashboardData); setMessages(messageData); setEvents(traceData); setReviews(reviewData); setSamples(sampleData);
      if (sceneData[0]) setSceneId(sceneData[0].id);
    });
  }, []);

  const currentScene = useMemo(() => scenes.find((scene) => scene.id === sceneId) ?? scenes[0], [sceneId, scenes]);
  if (!currentScene || !dashboard) return <div className="boot">正在启动 Agent Workbench...</div>;

  const handleSend = async (content: string) => {
    setMessages((prev) => [...prev, { role: 'user', content }]);
    const result = await api.chat(sceneId, content);
    setMessages((prev) => [...prev, { role: 'assistant', content: result.requiresConfirmation ? `需要确认：${result.requiresConfirmation.title}。${result.requiresConfirmation.reason}` : result.answer }]);
    if (result.events?.length) {
      setEvents(result.events);
      return;
    }
    const risk: TraceEvent['risk'] = content.includes('报告') ? 'medium' : 'low';
    setEvents((prev) => [{ time: new Date().toLocaleTimeString(), stage: 'frontend_command', detail: content, risk }, ...prev].slice(0, 8));
  };

  return <div className="app-shell"><Sidebar scenes={scenes} current={currentScene} onSceneChange={setSceneId} /><main className="workspace"><Hero scene={currentScene} /><QualityDashboard summary={dashboard} scene={currentScene} /><div className="work-grid"><ChatPanel scene={currentScene} messages={messages} onSend={handleSend} /><div className="right-stack"><TraceTimeline events={events} /><ReviewQueue items={reviews.filter((item) => item.scene === sceneId)} /><SampleManager samples={samples.filter((sample) => sample.scene === sceneId)} /></div></div></main></div>;
}
