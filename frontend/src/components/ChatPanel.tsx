import { SendHorizonal } from 'lucide-react';
import type { ChatMessage, SceneConfig } from '../types';

interface ChatPanelProps { scene: SceneConfig; messages: ChatMessage[]; onSend: (message: string) => void | Promise<void>; }

export function ChatPanel({ scene, messages, onSend }: ChatPanelProps) {
  const quick = ['你能帮我做什么？', '当前场景常见问题有哪些？', '生成服务质量概览报告'];
  return <section className="panel chat-panel"><div className="panel-head"><span>Agent Chat</span><b>{scene.name}</b></div><div className="message-list">{messages.map((message, index) => <div className={`message ${message.role}`} key={`${message.role}-${index}`}><span>{message.role === 'user' ? '你' : 'Agent'}</span><p>{message.content}</p></div>)}</div><div className="quick-row">{quick.map((item) => <button key={item} onClick={() => onSend(item)}>{item}</button>)}</div><form className="composer" onSubmit={(event) => { event.preventDefault(); const form = event.currentTarget; const input = form.elements.namedItem('message') as HTMLInputElement; if (input.value.trim()) { onSend(input.value.trim()); input.value = ''; } }}><input name="message" placeholder="输入任务、问题或报告诉求..." /><button><SendHorizonal size={18} /></button></form></section>;
}
