import type { ReviewItem } from '../types';

export function ReviewQueue({ items }: { items: ReviewItem[] }) {
  return <section className="panel"><div className="panel-head"><span>Review Queue</span><b>{items.length || 'clear'}</b></div>{items.length ? items.map((item) => <article className="list-item" key={item.id}><b>{item.id}</b><span>{item.reason}</span><p>{item.query}</p></article>) : <p className="empty">暂无待复核任务，高风险与失败任务会自动进入这里。</p>}</section>;
}
