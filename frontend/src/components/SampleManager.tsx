import type { EvalSample } from '../types';

export function SampleManager({ samples }: { samples: EvalSample[] }) {
  return <section className="panel"><div className="panel-head"><span>Evaluation Samples</span><b>{samples.length || 'empty'}</b></div>{samples.length ? samples.map((sample) => <article className="list-item" key={sample.id}><b>{sample.status === 'labeled' ? '已标注' : '待标注'}</b><span>{sample.query}</span><p>{sample.keywords.join('、') || '等待补充 expected_keywords'}</p></article>) : <p className="empty">成功任务会自动沉淀为样本，补标后导出 reviewed 回归集。</p>}</section>;
}
