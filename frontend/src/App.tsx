import { useEffect, useMemo, useState } from 'react';
import { api } from './api/client';
import { ChatPanel } from './components/ChatPanel';
import { Hero } from './components/Hero';
import { QualityDashboard } from './components/QualityDashboard';
import { ReviewQueue } from './components/ReviewQueue';
import { SampleManager } from './components/SampleManager';
import { Sidebar } from './components/Sidebar';
import { TraceTimeline } from './components/TraceTimeline';
import type { ChatMessage, ConfirmationRequest, DashboardSummary, EvalSample, HealthStatus, ReviewItem, SceneConfig, SceneId, TraceEvent } from './types';
import './styles.css';

export default function App() {
  const [scenes, setScenes] = useState<SceneConfig[]>([]);
  const [sceneId, setSceneId] = useState<SceneId>('zhisaotong');
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [samples, setSamples] = useState<EvalSample[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<ConfirmationRequest | null>(null);
  const [pendingMessage, setPendingMessage] = useState('');

  useEffect(() => {
    Promise.all([api.health(), api.scenes(), api.dashboard(), api.messages(), api.traces(), api.reviews(), api.samples()]).then(([healthData, sceneData, dashboardData, messageData, traceData, reviewData, sampleData]) => {
      setHealth(healthData); setScenes(sceneData); setDashboard(dashboardData); setMessages(messageData); setEvents(traceData); setReviews(reviewData); setSamples(sampleData);
      if (sceneData[0]) setSceneId(sceneData[0].id);
    });
  }, []);

  const currentScene = useMemo(() => scenes.find((scene) => scene.id === sceneId) ?? scenes[0], [sceneId, scenes]);
  if (!currentScene || !dashboard) return <div className="boot">正在启动 Agent Workbench...</div>;

  const handleSend = async (content: string, confirmedActions: string[] = []) => {
    setChatError(null); setIsSending(true);
    if (!confirmedActions.length) setMessages((prev) => [...prev, { role: 'user', content }]);
    try {
      const result = await api.chat(sceneId, content, confirmedActions);
      if (result.requiresConfirmation) {
        setPendingConfirmation(result.requiresConfirmation); setPendingMessage(content);
        setMessages((prev) => [...prev, { role: 'assistant', content: `需要确认：${result.requiresConfirmation?.title}。${result.requiresConfirmation?.reason}` }]);
        return;
      }
      setPendingConfirmation(null); setPendingMessage('');
      setMessages((prev) => [...prev, { role: 'assistant', content: result.answer }]);
      if (result.events?.length) setEvents(result.events);
    } catch (error) {
      setChatError(error instanceof Error ? error.message : '发送失败，请稍后重试');
    } finally {
      setIsSending(false);
    }
  };

  const confirmPendingAction = () => {
    if (pendingConfirmation && pendingMessage) void handleSend(pendingMessage, [pendingConfirmation.action]);
  };

  const refreshOpsData = async () => {
    const [dashboardData, reviewData, sampleData] = await Promise.all([api.dashboard(), api.reviews(), api.samples()]);
    setDashboard(dashboardData); setReviews(reviewData); setSamples(sampleData);
  };

  const handleReviewStatus = async (reviewId: string, status: ReviewItem['status']) => {
    await api.updateReviewStatus(reviewId, status);
    await refreshOpsData();
  };

  const handleLabelSample = async (sampleId: string, keywords: string[]) => {
    await api.labelSample(sampleId, keywords);
    await refreshOpsData();
  };

  const handleExportReviewed = async (targetSceneId: SceneId) => {
    const result = await api.exportReviewed(targetSceneId);
    setMessages((prev) => [...prev, { role: 'assistant', content: `Reviewed 数据集已导出：${result.path || '已完成'}` }]);
    await refreshOpsData();
  };

  return <div className="app-shell"><Sidebar scenes={scenes} current={currentScene} onSceneChange={setSceneId} /><main className="workspace"><div className={`status-bar ${health?.mode || 'offline'}`}><span>{health?.mode === 'live' ? 'Live Mode' : 'Demo Mode'}</span><b>{health?.apiOnline ? 'API Online' : 'API Offline'}</b><b>{health?.modelKeyConfigured ? 'Model Key Configured' : 'Model Key Missing'}</b></div><Hero scene={currentScene} /><QualityDashboard summary={dashboard} scene={currentScene} /><div className="work-grid"><ChatPanel scene={currentScene} messages={messages} onSend={handleSend} isSending={isSending} error={chatError} pendingConfirmation={pendingConfirmation} onConfirm={confirmPendingAction} /><div className="right-stack"><TraceTimeline events={events} /><ReviewQueue items={reviews.filter((item) => item.scene === sceneId)} onStatusChange={handleReviewStatus} /><SampleManager samples={samples.filter((sample) => sample.scene === sceneId)} sceneId={sceneId} onLabel={handleLabelSample} onExport={handleExportReviewed} /></div></div></main></div>;
}
