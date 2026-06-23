import type { TraceEvent } from '../types';

export function TraceTimeline({ events }: { events: TraceEvent[] }) {
  return <section className="panel"><div className="panel-head"><span>Execution Timeline</span><b>{events.length} events</b></div><div className="timeline">{events.map((event) => <div className={`trace ${event.risk ?? 'low'}`} key={`${event.time}-${event.stage}`}><time>{event.time}</time><div><b>{event.stage}</b><p>{event.detail}</p>{event.tool && <small>{event.tool}</small>}</div></div>)}</div></section>;
}
