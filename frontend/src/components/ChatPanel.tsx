import { SendHorizonal } from 'lucide-react';
import type { ChatMessage, ConfirmationRequest, SceneConfig } from '../types';

interface ChatPanelProps {
  scene: SceneConfig;
  messages: ChatMessage[];
  onSend: (message: string) => void | Promise<void>;
  isSending: boolean;
  error: string | null;
  pendingConfirmation: ConfirmationRequest | null;
  onConfirm: () => void;
}

export function ChatPanel({ scene, messages, onSend, isSending, error, pendingConfirmation, onConfirm }: ChatPanelProps) {
  const quick = ['你能帮我做什么？', '当前场景常见问题有哪些？', '生成服务质量概览报告'];
  return <section className="panel chat-panel"><div className="panel-head"><span>Agent Chat</span><b>{scene.name}</b></div><div className="message-list">{messages.map((message, index) => <div className={`message ${message.role}`} key={`${message.role}-${index}`}><span>{message.role === 'user' ? '你' : 'Agent'}</span><p>{message.content}</p></div>)}{isSending && <div className="message assistant"><span>Agent</span><p>正在执行任务并生成轨迹...</p></div>}</div>{error && <div className="chat-error">{error}</div>}{pendingConfirmation && <div className="confirm-card"><b>{pendingConfirmation.title}</b><p>{pendingConfirmation.reason}</p><button onClick={onConfirm} disabled={isSending}>确认继续执行</button></div>}<div className="quick-row">{quick.map((item) => <button key={item} disabled={isSending} onClick={() => onSend(item)}>{item}</button>)}</div><form className="composer" onSubmit={(event) => { event.preventDefault(); const form = event.currentTarget; const input = form.elements.namedItem('message') as HTMLInputElement; if (input.value.trim()) { void onSend(input.value.trim()); input.value = ''; } }}><input name="message" disabled={isSending} placeholder="输入任务、问题或报告诉求..." /><button disabled={isSending}><SendHorizonal size={18} /></button></form></section>;
}
