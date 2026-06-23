import { useState } from 'react';
import type { EvalSample, SceneId } from '../types';

interface SampleManagerProps { samples: EvalSample[]; sceneId: SceneId; onLabel?: (id: string, keywords: string[]) => void | Promise<void>; onExport?: (sceneId: SceneId) => void | Promise<void>; }

export function SampleManager({ samples, sceneId, onLabel, onExport }: SampleManagerProps) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  return <section className="panel"><div className="panel-head"><span>Eval Samples</span><button className="mini-action" onClick={() => onExport?.(sceneId)}>导出 reviewed</button></div>{samples.length ? samples.map((sample) => <div className="list-item" key={sample.id}><b>{sample.query}</b><p>{sample.status}</p><input className="label-input" value={drafts[sample.id] ?? sample.keywords.join(',')} onChange={(event) => setDrafts((prev) => ({ ...prev, [sample.id]: event.target.value }))} placeholder="关键词，用逗号分隔" /><div className="ops-row"><button onClick={() => onLabel?.(sample.id, (drafts[sample.id] ?? sample.keywords.join(',')).split(',').map((item) => item.trim()).filter(Boolean))}>保存标签</button></div></div>) : <div><p className="empty">暂无沉淀样本</p><button className="mini-action" onClick={() => onExport?.(sceneId)}>导出当前 reviewed 数据集</button></div>}</section>;
}
