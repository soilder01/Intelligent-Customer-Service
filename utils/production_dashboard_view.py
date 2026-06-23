"""Streamlit rendering helpers for the Agent production-loop dashboard."""
from __future__ import annotations

from typing import Any, Mapping

from utils.production_loop import build_production_dashboard


def scene_dataset_stats(summary: Mapping[str, Any], scene_id: str) -> dict[str, int]:
    """Return dataset stats for one scene with stable zero defaults."""
    stats = ((summary.get("datasets") or {}).get("by_scene") or {}).get(scene_id, {})
    return {
        "seed_cases": int(stats.get("seed_cases", 0)),
        "reviewed_cases": int(stats.get("reviewed_cases", 0)),
        "total_cases": int(stats.get("total_cases", 0)),
    }


def render_production_dashboard(st_module: Any, current_scene_id: str | None = None) -> dict[str, Any]:
    """Render a compact production-loop dashboard in Streamlit and return summary."""
    summary = build_production_dashboard()
    reviews = summary.get("reviews", {})
    samples = summary.get("samples", {})
    datasets = summary.get("datasets", {})

    st_module.caption(f"生成时间：{summary.get('generated_at', '')}")
    col1, col2 = st_module.columns(2)
    col1.metric("待复核", reviews.get("open", 0))
    col2.metric("高风险", reviews.get("high_risk", 0))

    col3, col4 = st_module.columns(2)
    col3.metric("待标注样本", samples.get("unlabeled", 0))
    col4.metric("标注率", f"{samples.get('label_rate', 0):.0%}")

    if current_scene_id:
        scene_stats = scene_dataset_stats(summary, current_scene_id)
        st_module.caption(
            "当前场景回归用例："
            f"seed {scene_stats['seed_cases']} / "
            f"reviewed {scene_stats['reviewed_cases']} / "
            f"total {scene_stats['total_cases']}"
        )
    else:
        st_module.caption(
            "全量回归用例："
            f"seed {datasets.get('seed_cases', 0)} / "
            f"reviewed {datasets.get('reviewed_cases', 0)} / "
            f"total {datasets.get('total_cases', 0)}"
        )

    with st_module.expander("查看场景分布", expanded=False):
        by_scene = datasets.get("by_scene") or {}
        if not by_scene:
            st_module.caption("暂无回归数据集")
        else:
            rows = [
                {
                    "场景": scene,
                    "Seed 用例": stats.get("seed_cases", 0),
                    "Reviewed 用例": stats.get("reviewed_cases", 0),
                    "总用例": stats.get("total_cases", 0),
                }
                for scene, stats in sorted(by_scene.items())
            ]
            st_module.table(rows)
    return summary
