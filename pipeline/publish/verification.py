"""The Verification page: issued outlooks compared with what happened (Phase 6, D016).

Three outcome sources, each compared with the outlooks actually published (archive/forecasts.csv):
  1. Satellite chlorophyll-a over the outlook week (the forecast target). An outlook issued on t
     is verifiable once imagery to t+7 exists; its outcome is the training label rule exactly
     (clear-sky-weighted mean anomaly over t+1..t+7, >= 2 cloud-free days, above the area's
     training 90th percentile for the issue month; models/label_thresholds_tas.json).
     Scores: Brier score against the climatology baseline, and the outcome rate per tier.
  2. ShellMAP harvest-status changes (labels/status_snapshots.csv), with the area's highest
     outlook tier in the 7 days before.
  3. Biotoxin News results at or above PALT alert levels or toxin limits
     (pipeline.labels.biotoxin_news), with the highest tier in the growing area in the 7 days
     before sampling.
(2) and (3) are context, not scores: closures have many causes, and chlorophyll-a is a proxy.

Written daily by pipeline.forecast.daily: site/verification.html and site/verification.json.
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.config import REPO_ROOT
from pipeline.features import target as T
from pipeline.forecast import score
from pipeline.labels import biotoxin_news
from pipeline.labels.tas_lookup import match_key
from pipeline.model.baselines import climatology
from pipeline.publish import site as sitemod
from pipeline.publish import web

THRESHOLDS_PATH = REPO_ROOT / "models" / "label_thresholds_tas.json"
EVALUATION_PATH = REPO_ROOT / "models" / "evaluation_tas.json"
LOOKBACK_DAYS = 7
TIER_RANK = {"Low": 0, "Moderate": 1, "High": 2}


def load_thresholds(path: Path = THRESHOLDS_PATH) -> pd.DataFrame:
    """area_id, month, threshold (log10 anomaly)."""
    return pd.DataFrame(json.loads(path.read_text(encoding="utf-8"))["thresholds"])


def observed_outcomes(
    chl: pd.DataFrame,
    dep: score.Deployment,
    area_ids: list[str],
    thresholds: pd.DataFrame,
    start: pd.Timestamp,
    latest: pd.Timestamp,
) -> pd.DataFrame:
    """Per area and issue date: forward-week mean anomaly and outcome y (NaN if unverifiable).

    Only issue dates whose whole week (t+1..t+7) is covered by imagery up to `latest` count.
    Returns an empty table when there is no imagery after the first issue date yet.
    """
    if latest < start:
        return pd.DataFrame(columns=["area_id", "date", "fwd_mean", "y", "complete"])
    anoms = score.anomaly_table(chl, dep, area_ids, start, latest)
    parts = []
    for _, g in anoms.groupby("area_id", sort=False):
        g = g.sort_values("date")
        mean, n = T.forward_window(g["anomaly"], weights=g["weight"])
        parts.append(g[["area_id", "date"]].assign(fwd_mean=mean.where(n >= T.MIN_VALID_DAYS)))
    out = pd.concat(parts, ignore_index=True)
    out["month"] = out["date"].dt.month
    out = out.merge(thresholds, on=["area_id", "month"], how="left")
    complete = out["date"] + pd.Timedelta(days=T.HORIZON_DAYS) <= latest
    ok = complete & out["fwd_mean"].notna() & out["threshold"].notna()
    out["complete"] = complete
    out["y"] = np.where(ok, (out["fwd_mean"] > out["threshold"]).astype(float), np.nan)
    return out


def verify(issued: pd.DataFrame, outcomes: pd.DataFrame, dep: score.Deployment) -> pd.DataFrame:
    """Issued outlooks joined with outcomes and the climatology baseline probability."""
    if issued.empty:
        return pd.DataFrame(
            columns=["issue_date", "area_id", "p", "tier", "y", "p_clim", "complete"]
        )
    v = issued.assign(date=pd.to_datetime(issued["issue_date"]))
    v = v.merge(outcomes[["area_id", "date", "y", "complete"]], on=["area_id", "date"], how="left")
    v["p_clim"] = climatology(v, dep.climatology).to_numpy()
    v["complete"] = v["complete"].fillna(False).astype(bool)
    return v


def summarise(v: pd.DataFrame) -> dict:
    """Counts, outcome rate, Brier scores (outlook vs climatology) and per-tier outcome rates."""
    done = v[v["y"].notna()]
    out = {
        "issued": int(len(v)),
        "first_issue": v["issue_date"].min() if len(v) else None,
        "verified": int(len(done)),
        "unverifiable_cloud": int((v["complete"] & v["y"].isna()).sum()),
        "pending": int((~v["complete"]).sum()),
    }
    if len(done):
        y, p, pc = done["y"].to_numpy(), done["p"].to_numpy(float), done["p_clim"].to_numpy(float)
        bs, bs_clim = float(np.mean((p - y) ** 2)), float(np.mean((pc - y) ** 2))
        out.update(
            {
                "period": [done["issue_date"].min(), done["issue_date"].max()],
                "observed_rate": float(y.mean()),
                "brier": bs,
                "brier_climatology": bs_clim,
                "brier_skill": (1 - bs / bs_clim) if bs_clim > 0 else None,
                "tiers": {
                    t: {
                        "n": int((done["tier"] == t).sum()),
                        "rate": float(done.loc[done["tier"] == t, "y"].mean())
                        if (done["tier"] == t).any()
                        else None,
                    }
                    for t in ("High", "Moderate", "Low")
                },
            }
        )
    return out


def _norm(name: str) -> str:
    """Comparable growing-area name: drop '(...)', keep letters only, lower case."""
    return re.sub(r"[^a-z]", "", re.sub(r"\(.*?\)", "", str(name)).lower())


def prior_tier(issued: pd.DataFrame, area_ids: list[str], on: pd.Timestamp) -> str | None:
    """Highest tier issued for any of `area_ids` in the LOOKBACK_DAYS before date `on`."""
    if issued.empty or not area_ids:
        return None
    d = pd.to_datetime(issued["issue_date"])
    w = issued[
        issued["area_id"].isin(area_ids) & (d < on) & (d >= on - pd.Timedelta(days=LOOKBACK_DAYS))
    ]
    if w.empty:
        return None
    return max(w["tier"], key=lambda t: TIER_RANK.get(t, -1))


def status_changes(
    meta: pd.DataFrame, issued: pd.DataFrame, path: Path = sitemod.SNAPSHOTS
) -> pd.DataFrame:
    """ShellMAP status changes between consecutive archived snapshots, with the prior tier."""
    cols = ["date", "area", "change", "reason", "tier_before"]
    if not path.exists():
        return pd.DataFrame(columns=cols)
    s = pd.read_csv(path, parse_dates=["date"])
    s = s[s["region"] == "tas"].sort_values(["area_id", "date"])
    s["prev"] = s.groupby("area_id")["status"].shift()
    ch = s[s["prev"].notna() & (s["status"] != s["prev"])]
    by_key = meta.set_index("match_key")["area_id"].to_dict()
    rows = []
    for r in ch.itertuples():
        ours = by_key.get(match_key(r.area_id))
        rows.append(
            {
                "date": r.date,
                "area": f"{r.growing_area}, {r.harvest_area}",
                "change": f"{r.prev.title()} → {r.status.title()}",
                "reason": r.reason,
                "tier_before": prior_tier(issued, [ours] if ours else [], r.date),
            }
        )
    return pd.DataFrame(rows, columns=cols)


def biotoxin_findings(meta: pd.DataFrame, issued: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Notable Biotoxin News results with the growing area's highest prior tier, plus counts."""
    toxins, phyto = biotoxin_news.load_all()
    found = biotoxin_news.notable(toxins, phyto)
    areas_by_ga = meta.groupby(meta["growing_area"].map(_norm))["area_id"].apply(list).to_dict()
    found["tier_before"] = [
        prior_tier(issued, areas_by_ga.get(_norm(r.growing_area), []), r.sample_date)
        for r in found.itertuples()
    ]
    info = {
        "issues": int(toxins["source_file"].nunique()) if len(toxins) else 0,
        "latest_issue": toxins["issued"].max() if len(toxins) else None,
        "samples": int(toxins[["growing_area", "sample_date"]].drop_duplicates().shape[0])
        if len(toxins)
        else 0,
    }
    return found.sort_values("sample_date", ascending=False), info


def _fmt_date(d) -> str:
    """'19 Nov 2026' (or '–' when missing)."""
    if d is None or pd.isna(d):
        return "–"
    ts = pd.Timestamp(d)
    return f"{ts.day} {ts:%b %Y}"


def _pct(x) -> str:
    """0.634 -> '63%' (or '–' when missing)."""
    return "–" if x is None or pd.isna(x) else f"{x * 100:.0f}%"


def markdown_page(
    summary: dict,
    changes: pd.DataFrame,
    findings: pd.DataFrame,
    bt: dict,
    first_check: pd.Timestamp | None,
) -> str:
    """The page body in markdown (rendered with the site template)."""
    lines = [
        "# Verification",
        "",
        "Published outlooks compared with observed outcomes. Records begin "
        f"{_fmt_date(summary.get('first_issue'))}. Updated daily.",
        "",
        "## Satellite outcome",
        "",
        "Outcome: 7-day mean chlorophyll-a above the area's monthly 90th percentile "
        "(the forecast target).",
        "",
    ]
    if summary.get("verified", 0) == 0:
        when = f" Expected from {_fmt_date(first_check)}." if first_check is not None else ""
        lines += [
            "No outlooks verified yet. An outlook can be verified once imagery for its full "
            f"week is available.{when}",
            "",
        ]
    else:
        lines += [
            "| Measure | Value |",
            "|---|---|",
            f"| Outlooks verified | {summary['verified']:,} "
            f"({summary['period'][0]} to {summary['period'][1]}) |",
            f"| Outcome rate | {_pct(summary['observed_rate'])} |",
            f"| Brier score: outlook / climatology | {summary['brier']:.3f} / "
            f"{summary['brier_climatology']:.3f} |",
            f"| Brier skill score vs climatology | {summary['brier_skill']:+.2f} |",
            "",
            "| Tier | Outlooks | Outcome rate |",
            "|---|---|---|",
        ]
        for t, d in summary["tiers"].items():
            lines.append(f"| {t} | {d['n']:,} | {_pct(d['rate'])} |")
        lines += [
            "",
            f"Not verifiable (fewer than 2 cloud-free days): {summary['unverifiable_cloud']:,}. "
            f"Pending: {summary['pending']:,}. Small samples; interpret with caution.",
            "",
        ]
    lines += [
        "## ShellMAP status changes",
        "",
        "Changes in official harvest status, with the area's highest outlook tier in the "
        "preceding 7 days. "
        "Closures have many causes; this is context, not a score.",
        "",
    ]
    if changes.empty:
        lines += ["No status changes recorded since archiving began (18 Nov 2026).", ""]
    else:
        lines += [
            "| Date | Area | Change | Reason | Outlook tier, prior 7 days |",
            "|---|---|---|---|---|",
        ]
        for r in changes.itertuples():
            lines.append(
                f"| {_fmt_date(r.date)} | {r.area} | {r.change} | {r.reason} | "
                f"{r.tier_before or '–'} |"
            )
        lines.append("")
    lines += [
        "## Biotoxin News",
        "",
        "Phytoplankton at or above ShellMAP alert levels (PALT) and toxins above maximum limits, "
        "with the growing area's highest outlook tier in the 7 days before sampling.",
        f"Issues archived: {bt['issues']} (latest issued {_fmt_date(bt['latest_issue'])}); "
        f"samples: {bt['samples']}.",
        "",
    ]
    if findings.empty:
        lines += ["No results at or above alert levels in the archived issues.", ""]
    else:
        lines += [
            "| Sample date | Growing area | Result | Outlook tier, prior 7 days |",
            "|---|---|---|---|",
        ]
        for r in findings.itertuples():
            lines.append(
                f"| {_fmt_date(r.sample_date)} | {r.growing_area} | {r.finding} | "
                f"{r.tier_before or 'no outlook issued'} |"
            )
        lines.append("")
    lines += reference_section()
    lines += [
        "Source: Biotoxin News and harvest status © State of Tasmania (NRE Tas, ShellMAP), "
        "non-commercial use.",
        "",
    ]
    return "\n".join(lines)


def reference_section(path: Path = EVALUATION_PATH) -> list[str]:
    """Independent test results from Phase 3 (static), for comparison."""
    if not path.exists():
        return []
    ev = json.loads(path.read_text(encoding="utf-8"))["primary"]
    names = {
        "persistence": "Outlook method",
        "climatology": "Climatology",
        "bgc": "Copernicus BGC model",
    }
    lines = [
        "## Reference: independent test, 2024–2026",
        "",
        "Scored once before release (model version 1.0). "
        f"Outcome rate {_pct(ev['positive_rate'])}.",
        "",
        "| Method | PR-AUC | Brier score |",
        "|---|---|---|",
    ]
    for k, label in names.items():
        m = ev["overall"][k]
        lines.append(f"| {label} | {m['pr_auc']:.2f} | {m['brier']:.3f} |")
    lines += ["", "Details: [model card](model-card.html).", ""]
    return lines


def write(
    site: Path,
    chl: pd.DataFrame,
    issued: pd.DataFrame,
    dep: score.Deployment,
    meta: pd.DataFrame,
    latest: pd.Timestamp,
) -> dict:
    """Compute everything and write site/verification.html and site/verification.json."""
    area_ids = meta["area_id"].tolist()
    if len(issued):
        start = pd.to_datetime(issued["issue_date"]).min()
        outcomes = observed_outcomes(chl, dep, area_ids, load_thresholds(), start, latest)
    else:
        outcomes = pd.DataFrame(columns=["area_id", "date", "y", "complete"])
    v = verify(issued, outcomes, dep)
    summary = summarise(v)
    changes = status_changes(meta, issued)
    findings, bt = biotoxin_findings(meta, issued)
    first_check = (
        pd.to_datetime(summary["first_issue"]) + pd.Timedelta(days=T.HORIZON_DAYS + 2)
        if summary.get("first_issue")
        else None
    )
    body = web.render_markdown(markdown_page(summary, changes, findings, bt, first_check))
    (site / "verification.html").write_text(
        web.render_page("Verification", body, "verification.html"), encoding="utf-8"
    )
    sitemod.write_json(
        site / "verification.json",
        {
            "summary": summary,
            "status_changes": changes.to_dict(orient="records"),
            "biotoxin_news": {**bt, "findings": findings.to_dict(orient="records")},
        },
    )
    return summary
