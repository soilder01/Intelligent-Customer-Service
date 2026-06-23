import type { ReviewItem } from '../types';

interface ReviewQueueProps { items: ReviewItem[]; onStatusChange?: (id: string, status: ReviewItem['status']) => void | Promise<void>; }

export function ReviewQueue({ items, onStatusChange }: ReviewQueueProps) {
  return <section className="panel"><div className="panel-head"><span>Human Review</span><b>{items.length} 项</b></div>{items.length ? items.map((item) => <div className="list-item" key={item.id}><b>{item.reason}</b><span>{item.query}</span><p>{item.status}</p><div className="ops-row"><button onClick={() => onStatusChange?.(item.id, 'reviewed')}>标记已复核</button><button onClick={() => onStatusChange?.(item.id, 'ignored')}>忽略</button></div></div>) : <p className="empty">当前场景暂无待复核项</p>}</section>;
}
