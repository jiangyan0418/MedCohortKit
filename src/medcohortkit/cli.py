"""Command-line workflows. All statistical calculations run locally."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path
import platform
import shutil
import sys
import tempfile

import numpy as np

from . import __version__
from .descriptive import compare_groups, table_one
from .models import fit_linear
from .reliability import icc_absolute
from .io import load_config, read_data, template_config, validate_config
from .report import forest_plot, json_safe, write_json, write_report


def analyze(data_path: str | Path, config: dict, out: str | Path) -> dict:
    """Validate and compute first; publish outputs only after every analysis succeeds."""
    config = validate_config(config)
    data_path, out = Path(data_path), Path(out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Output must be a new or empty directory; choose a new run folder.")
    data = read_data(data_path, subject_col=config["subject_id"])
    subject = config["subject_id"]
    if subject not in data:
        raise ValueError(f"Missing subject ID column: {subject!r}.")
    ids = data[subject]
    if ids.isna().any() or ids.astype(str).str.strip().eq("").any():
        raise ValueError("Patient IDs must be present on every input row; no IDs are inferred.")
    if ids.astype(str).str.lower().isin(["inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"]).any():
        raise ValueError("Patient IDs must not be infinite values.")
    n_subjects = int(ids.nunique())
    repeated = n_subjects < len(data)
    common = {"group": config["group"], "continuous": config.get("continuous", []),
              "categorical": config.get("categorical", []), "group_order": config.get("group_order")}
    descriptive = table_one(data, **common)
    tables = {"table1": descriptive}
    analyses = {"table1": dict(descriptive.attrs)}
    notes = ["This report contains aggregate research results; review it before sharing.",
             "Missingness is reported per analysis. Complete-case analysis can be biased when missingness is informative.",
             "No normality test, p-value threshold, or automatic covariate selection determines the analysis method."]
    if repeated:
        notes.append("Repeated subject IDs detected. Descriptive counts refer to observations, not unique people; linear inference uses patient clusters when repeats remain after exclusions.")
    comp = config.get("comparisons", {})
    if comp.get("enabled", False):
        comparisons = compare_groups(data, **common, subject_col=subject,
                                     continuous_test=comp.get("continuous_test", "welch"),
                                     adjust_method=comp.get("adjust_method", "fdr_bh"))
        tables["comparisons"] = comparisons
        analyses["comparisons"] = dict(comparisons.attrs)
    if "linear" in config:
        model = fit_linear(data, **config["linear"], subject_col=subject)
        tables["regression"] = model["coefficients"]
        analyses["linear"] = model["metadata"]
    if "icc" in config:
        if repeated:
            raise ValueError("ICC subject-row bootstrap assumes independent patients. This file contains repeated patient IDs; use a prespecified independent target sample in a separate run. Renaming knees does not remove patient clustering.")
        choice = config["icc"]
        reliability = icc_absolute(data, raters=choice["raters"], subject_col=choice.get("subject_id", subject),
                                   n_boot=choice.get("n_boot", 2000), seed=choice.get("seed", 20261022))
        tables["icc"] = reliability["estimates"]
        analyses["icc"] = reliability["metadata"]
    dependencies = {name: importlib.metadata.version(name) for name in ["numpy", "pandas", "scipy", "statsmodels", "matplotlib"]}
    canonical_config = json.dumps(json_safe(config), sort_keys=True, ensure_ascii=False).encode("utf-8")
    audit = {
        "schema_version": "1.0", "package": "medcohortkit", "version": __version__,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": {"sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
                  "n_rows": int(len(data)), "n_subjects": n_subjects,
                  "repeated_rows": int(len(data) - n_subjects)},
        "config_sha256": hashlib.sha256(canonical_config).hexdigest(), "config": config,
        "environment": {"python": platform.python_version(), "dependencies": dependencies},
        "analyses": analyses, "notes": notes,
        "results": {key: value.to_dict(orient="records") for key, value in tables.items()},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".medcohort-", dir=out.parent) as temp:
        staged = Path(temp)
        for key, table in tables.items():
            table.to_csv(staged / f"{key}.csv", index=False, encoding="utf-8-sig", float_format="%.12g")
        if "regression" in tables:
            forest_plot(tables["regression"], staged / "forest.svg", config["linear"]["outcome"])
        write_json(staged / "audit.json", audit)
        write_report(staged, config.get("title", "Clinical cohort analysis"), tables, audit)
        # No previous analysis is overwritten. A failed run never leaves an apparently complete report.
        out.mkdir(exist_ok=True)
        for file in staged.iterdir():
            shutil.move(str(file), out / file.name)
    return json_safe(audit)


def _demo(out: Path, seed: int) -> None:
    from .demo import demo_config, synthetic_cohort
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Demo output must be a new or empty directory.")
    out.mkdir(parents=True, exist_ok=True)
    for name, bilateral in [("independent", False), ("clustered", True)]:
        case = out / name
        case.mkdir()
        data = synthetic_cohort(seed=seed, bilateral=bilateral)
        data_path = case / "synthetic_cohort.csv"
        data.to_csv(data_path, index=False, encoding="utf-8-sig")
        config = demo_config(bilateral=bilateral, seed=seed)
        write_json(case / "analysis.json", config)
        analyze(data_path, config, case / "results")
        print(f"{name}: {(case / 'results' / 'report.html').resolve()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medcohort", description="Local, reproducible clinical cohort statistics.")
    parser.add_argument("--version", action="version", version=f"MedCohortKit {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Generate and analyze two fully synthetic example cohorts.")
    demo.add_argument("--out", type=Path, default=Path("output/demo"))
    demo.add_argument("--seed", type=int, default=20261022)
    run = commands.add_parser("analyze", help="Analyze a local CSV/XLSX using an explicit JSON configuration.")
    run.add_argument("--data", required=True, type=Path)
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--out", required=True, type=Path)
    template = commands.add_parser("template", help="Write an editable example configuration.")
    template.add_argument("--out", type=Path, default=Path("analysis.json"))
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            _demo(args.out, args.seed)
        elif args.command == "analyze":
            analyze(args.data, load_config(args.config), args.out)
            print(f"Report: {(args.out / 'report.html').resolve()}")
        else:
            if args.out.exists():
                raise ValueError("Configuration file already exists; choose a new path.")
            args.out.parent.mkdir(parents=True, exist_ok=True)
            write_json(args.out, template_config())
            print(f"Configuration: {args.out.resolve()}")
    except (ValueError, OSError, KeyError, ImportError) as exc:
        print(f"medcohort: {exc}", file=sys.stderr)
        return 2
    return 0
