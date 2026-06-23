import { Activity, Bot, Database, ShieldCheck } from 'lucide-react';
import type { SceneConfig } from '../types';

interface SidebarProps { scenes: SceneConfig[]; current: SceneConfig; onSceneChange: (id: SceneConfig['id']) => void; }

export function Sidebar({ scenes, current, onSceneChange }: SidebarProps) {
  return <aside className="sidebar">
    <div className="brand"><div className="brand-icon"><Bot size={22} /></div><div><b>Agent Workbench</b><span>企业任务型智能体</span></div></div>
    <label className="field-label">业务场景</label>
    <select className="scene-select" value={current.id} onChange={(event) => onSceneChange(event.target.value as SceneConfig['id'])}>{scenes.map((scene) => <option key={scene.id} value={scene.id}>{scene.name}</option>)}</select>
    <div className="side-card"><p>{current.description}</p></div>
    <nav className="nav-list"><a><Activity size={16} />质量看板</a><a><ShieldCheck size={16} />人工复核</a><a><Database size={16} />样本沉淀</a></nav>
    <div className="side-footer">API: <code>{import.meta.env.VITE_AGENT_API_BASE || 'mock fallback'}</code></div>
  </aside>;
}
