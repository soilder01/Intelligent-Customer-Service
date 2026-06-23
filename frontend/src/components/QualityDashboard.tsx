import type { DashboardSummary, SceneConfig } from '../types';

export function QualityDashboard({ summary, scene }: { summary: DashboardSummary; scene: SceneConfig }) {
  const sceneStats = summary.datasets.byScene[scene.id] ?? { seedCases: 0, reviewedCases: 0, totalCases: 0 };
  const cards = [
    ['待复核', summary.reviews.open], ['高风险', summary.reviews.highRisk], ['待标注样本', summary.samples.unlabeled], ['标注率', `${Math.round(summary.samples.labelRate * 100)}%`],
    ['Seed 用例', sceneStats.seedCases], ['Reviewed 用例', sceneStats.reviewedCases],
  ];
  return <section className="panel dashboard-panel"><div className="panel-head"><span>Quality Dashboard</span><b>{scene.name}</b></div><div className="metric-grid">{cards.map(([label, value]) => <div className="metric-card" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div></section>;
}
