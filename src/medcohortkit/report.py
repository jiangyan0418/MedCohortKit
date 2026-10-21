"""Static, escaped HTML reports with a portable numerical audit trail."""

from __future__ import annotations

import html
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [json_safe(x) for x in value]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    if value is pd.NA:
        return None
    return value


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(json_safe(value), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")


def _display_number(value: float) -> str:
    if not np.isfinite(value):
        return "—" if np.isnan(value) else ("∞" if value > 0 else "−∞")
    if value != 0 and abs(value) < 0.0001:
        return f"{value:.3e}"
    return f"{value:.4f}"


def _table(frame: pd.DataFrame) -> str:
    return frame.to_html(index=False, escape=True, border=0, na_rep="—", float_format=_display_number)


def _notes(values) -> str:
    return "<ul>" + "".join(f"<li>{html.escape(str(x))}</li>" for x in values) + "</ul>"


def forest_plot(coefficients: pd.DataFrame, path: Path, outcome: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    frame = coefficients.loc[coefficients["term"] != "Intercept"].reset_index(drop=True)
    if frame.empty:
        return
    with plt.rc_context({"font.family": "DejaVu Sans", "svg.fonttype": "none",
                         "svg.hashsalt": "medcohortkit-v0.1", "font.size": 10}):
        fig, ax = plt.subplots(figsize=(8.8, max(3.3, 0.5 * len(frame) + 1.6)))
        y = np.arange(len(frame))
        ax.hlines(y, frame["ci_low"], frame["ci_high"], color="#3c7e90", linewidth=2.2)
        ax.scatter(frame["estimate"], y, color="#174957", s=40, zorder=3)
        ax.axvline(0, color="#c26a48", linestyle="--", linewidth=1)
        ax.set_yticks(y, frame["term"])
        ax.invert_yaxis()
        ax.set_xlabel(f"Adjusted coefficient for {outcome} (95% CI)")
        ax.set_title("Covariate-adjusted associations", loc="left", fontweight="bold", pad=16)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.grid(axis="x", color="#e8eef0", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0, pad=8)
        fig.tight_layout()
        fig.savefig(path, format="svg", metadata={"Date": None, "Creator": "MedCohortKit"})
        plt.close(fig)


def write_report(out: Path, title: str, tables: dict, audit: dict) -> None:
    parts = []
    meta = audit["analyses"]
    table = tables["table1"].copy()
    labels = meta["table1"].get("group_labels", [])
    if len(labels) == 2:
        table.rename(columns={"group_1": f"Group 1: {labels[0]}", "group_2": f"Group 2: {labels[1]}"}, inplace=True)
    parts.append("<section><h2>01 · Cohort description / 基线描述</h2>" + _table(table)
                 + _notes(meta["table1"].get("notes", [])) + "</section>")
    if "comparisons" in tables:
        parts.append("<section><h2>02 · Prespecified comparisons / 组间比较</h2>" + _table(tables["comparisons"])
                     + _notes(meta["comparisons"].get("notes", [])) + "</section>")
    else:
        parts.append("<section><h2>02 · Group comparisons / 组间比较</h2><p>Independent group tests were not requested. "
                     "Baseline tables remain descriptive.</p></section>")
    if "regression" in tables:
        m = meta["linear"]
        parts.append("<section><h2>03 · Adjusted linear model / 多元线性回归</h2>"
                     + f"<p><strong>{html.escape(m['covariance'])}</strong> covariance · "
                     + f"{m['n_used']} complete observations · {m['n_dropped']} omitted · "
                     + f"inference df = {m['inference_df']:g}</p>"
                     + "<p>Reference categories: " + html.escape(str(m.get("categorical_reference", {}))) + "</p>"
                     + '<img class="forest" src="forest.svg" alt="Regression coefficients with 95% confidence intervals">'
                     + _table(tables["regression"]) + _notes(m.get("notes", [])) + "</section>")
    if "icc" in tables:
        parts.append("<section><h2>04 · Measurement reliability / 测量一致性</h2>" + _table(tables["icc"])
                     + _notes(meta["icc"].get("notes", [])) + "</section>")
    parts.append("<section><h2>Reproducibility / 可复现记录</h2><p>Input SHA-256: <code>"
                 + html.escape(audit["input"]["sha256"]) + "</code></p><p>The full configuration, dependency versions, "
                 "analysis choices, and numerical results are in <a href=\"audit.json\">audit.json</a>.</p>"
                 + _notes(audit.get("notes", [])) + "</section>")
    content = "".join(parts)
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — MedCohortKit</title>
<style>
:root{{--ink:#183742;--muted:#607882;--accent:#156777;--line:#dbe6e9;--paper:#fff;--bg:#f3f7f7}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1240px;margin:auto;padding:38px 24px 60px}}header{{padding:26px 0 28px;border-bottom:3px solid var(--accent)}}
.brand{{font-size:13px;letter-spacing:.13em;font-weight:750;color:var(--accent)}}h1{{font-size:31px;line-height:1.25;margin:16px 0}}
.intro{{color:var(--muted);max-width:900px}}.metrics{{display:flex;gap:16px;flex-wrap:wrap;margin:24px 0}}
.metric{{background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:16px 22px;min-width:170px}}
.metric strong{{display:block;font-size:27px}}.metric span{{color:var(--muted);font-size:13px}}
section{{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:24px;margin:22px 0;overflow-x:auto}}
h2{{font-size:20px;margin:0 0 16px}}p{{margin:10px 0}}table{{border-collapse:collapse;font-size:12px;width:100%;white-space:normal}}
th{{background:#eaf2f4;text-align:left;padding:10px;border-bottom:2px solid #b9cfd5;overflow-wrap:anywhere}}
td{{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top;min-width:60px;overflow-wrap:anywhere}}
tr:nth-child(even){{background:#fafcfc}}ul{{color:var(--muted);font-size:13px;padding-left:20px}}li{{margin:7px 0}}
.forest{{width:100%;max-width:900px;display:block;margin:10px 0 24px}}code{{font-size:12px;overflow-wrap:anywhere}}a{{color:var(--accent)}}
footer{{font-size:12px;color:var(--muted)}}@media print{{body{{background:white}}main{{max-width:none;padding:0}}section{{border-radius:0;break-inside:avoid}}}}
</style></head><body><main>
<header><div class="brand">MEDCOHORTKIT · REPRODUCIBLE RESEARCH</div><h1>{html.escape(title)}</h1>
<p class="intro">Local, auditable cohort statistics. Tables report their denominators; models report their uncertainty method. "Significant" does not by itself establish clinical importance or causality.</p></header>
<div class="metrics"><div class="metric"><strong>{audit['input']['n_rows']}</strong><span>Observation rows / 观测记录</span></div>
<div class="metric"><strong>{audit['input']['n_subjects']}</strong><span>Unique subjects / 独立编号数</span></div>
<div class="metric"><strong>{audit['input']['repeated_rows']}</strong><span>Additional rows per subject / 重复记录</span></div>
<div class="metric"><strong>v{html.escape(audit['version'])}</strong><span>Analysis package / 工具版本</span></div></div>
{content}<footer>Generated {html.escape(audit['generated_at_utc'])}. MedCohortKit is an early-stage research tool; study-design and method suitability require scientific review.</footer>
</main></body></html>'''
    (out / "report.html").write_text(page, encoding="utf-8")
