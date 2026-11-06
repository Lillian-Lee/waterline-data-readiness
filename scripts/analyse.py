"""Summarise the captured public water-data extracts and write a review report."""

from __future__ import annotations

import csv
import html
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET_FILE = ROOT / "data" / "raw" / "swdc_potable_water_pipes_sample.csv"
NEPM_FILE = ROOT / "data" / "reference" / "nepm_organisation_metrics.csv"
REVIEW_FILE = ROOT / "data" / "simulated" / "review_workflow.csv"
REPORT_DIR = ROOT / "reports"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    assets = read_csv(ASSET_FILE)
    metrics = read_csv(NEPM_FILE)
    reviews = read_csv(REVIEW_FILE)

    ids = [row["asset_id"] for row in assets]
    missing_criticality = sum(not row["criticality"].strip() for row in assets)
    missing_condition = sum(not row["condition_grade"].strip() for row in assets)
    missing_install_date = sum(not row["date_installed_epoch_ms"].strip() for row in assets)
    statuses = Counter(row["operational_status"] for row in assets)
    materials = Counter(row["material"] for row in assets)
    grades = Counter(row["condition_grade"] for row in assets)
    lengths = [float(row["length_m"]) for row in assets if row["length_m"].strip()]
    diameters = [float(row["diameter_mm"]) for row in assets if row["diameter_mm"].strip()]
    oldest = min(
        (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=int(row["date_installed_epoch_ms"]))).date()
        for row in assets
        if row["date_installed_epoch_ms"].strip()
    )
    newest = max(
        (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=int(row["date_installed_epoch_ms"]))).date()
        for row in assets
        if row["date_installed_epoch_ms"].strip()
    )

    findings = [
        {
            "dataset": "SWDC potable-water pipe sample",
            "finding": "Criticality is blank in every row in this extract.",
            "observed_count": missing_criticality,
            "denominator": len(assets),
            "status": "Observed in deterministic 25-row extract",
            "interpretation": "The extract does not provide criticality values for these records. This does not establish that the full source layer or council systems lack them.",
        },
        {
            "dataset": "SWDC potable-water pipe sample",
            "finding": "Condition grade is populated in every row in this extract.",
            "observed_count": len(assets) - missing_condition,
            "denominator": len(assets),
            "status": "Observed in deterministic 25-row extract",
            "interpretation": "This first-by-ID sample is not random or representative and must not be compared as a rate with the organisation-level NEPM figure.",
        },
        {
            "dataset": "SWDC potable-water pipe sample",
            "finding": "Installation dates span the captured source records.",
            "observed_count": f"{oldest} to {newest}",
            "denominator": len(assets),
            "status": "Converted from source epoch milliseconds",
            "interpretation": "Dates before 1970 are valid Unix timestamps. Their age or condition meaning requires domain context and is not classified as an error here.",
        },
        {
            "dataset": "Taumata Arowai NEPM 2024/25",
            "finding": "Tararua has four selected metric values but no provider confidence ratings.",
            "observed_count": "4 confidence values missing",
            "denominator": "4 selected metrics",
            "status": "Values traced to workbook cells; confidence remains blank",
            "interpretation": "The source workbook contains values for D-R9.1, D-R9.2, D-R10 and D-R12. Its confidence cells are blank for Tararua. Preserve those blanks; do not infer a confidence category.",
        },
    ]
    write_csv(
        REPORT_DIR / "quality_findings.csv",
        findings,
        ["dataset", "finding", "observed_count", "denominator", "status", "interpretation"],
    )

    verified = [row for row in metrics if row["extraction_status"] == "verified_from_workbook"]
    summary = {
        "asset_extract": {
            "source_file": str(ASSET_FILE.relative_to(ROOT)).replace("\\", "/"),
            "record_count": len(assets),
            "unique_asset_ids": len(set(ids)),
            "duplicate_asset_ids": len(ids) - len(set(ids)),
            "status_counts": dict(statuses),
            "missing_criticality": missing_criticality,
            "missing_condition_grade": missing_condition,
            "missing_install_date": missing_install_date,
            "total_pipe_length_m_in_extract": round(sum(lengths), 2),
            "diameter_range_mm": [min(diameters), max(diameters)],
            "material_counts": dict(materials),
            "condition_grade_counts": dict(grades),
            "installation_date_range_utc": [str(oldest), str(newest)],
            "representativeness": "Deterministic first 25 records by asset_id; not a representative sample.",
        },
        "nepm_extract": {
            "reporting_period": "2024-2025",
            "verified_organisations": sorted({row["organisation"] for row in verified}),
            "held_for_manual_verification": [
                row["organisation"] for row in metrics if row["extraction_status"] != "verified_from_workbook"
            ],
            "comparison_rule": "Organisation-level NEPM metrics are not joined to individual asset records.",
        },
    }
    (REPORT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    south = [row for row in verified if row["organisation"] == "South Wairarapa District Council"]

    metric_labels = {
        "D-R9.1": "Pipes with a condition grade",
        "D-R9.2": "Method used to grade pipe condition",
        "D-R10": "Pipes rated poor or very poor",
        "D-R12": "Average age of water pipes",
    }
    metric_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(row['organisation'])}</td>"
        f"<td>{html.escape(metric_labels.get(row['metric_code'], row['metric_label']))}</td>"
        f"<td>{html.escape(row['value'])} {html.escape(row['unit'])}</td>"
        f"<td>{html.escape(row['data_confidence'] or 'Not given')}</td>"
        "</tr>"
        for row in verified
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Waterline | Public water data review</title>
  <style>
    :root {{ color-scheme: light; --ink:#162b3c; --muted:#526777; --line:#d6e0e6; --blue:#155c78; --pale:#eef5f7; --amber:#815b17; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; background:#f5f7f8; color:var(--ink); font:16px/1.55 "Segoe UI",Arial,sans-serif; }}
    main {{ max-width:1080px; margin:40px auto; padding:0 24px 56px; }}
    header {{ padding:34px 38px; border-radius:14px; color:white; background:linear-gradient(120deg,#12384b,#18768a); }}
    header p {{ max-width:740px; color:#e0eef1; margin-bottom:0; }} .eyebrow {{ text-transform:uppercase; letter-spacing:.12em; font-size:.76rem; font-weight:700; }}
    h1 {{ font-size:2.2rem; line-height:1.15; margin:.55rem 0; }} h2 {{ font-size:1.25rem; margin:0 0 14px; }}
    section {{ margin-top:24px; background:white; border:1px solid var(--line); border-radius:12px; padding:24px; }}
    .cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:20px; }}
    .card {{ border:1px solid var(--line); border-radius:10px; padding:16px; background:white; }} .value {{ font-size:1.7rem; font-weight:700; color:var(--blue); }} .label {{ color:var(--muted); font-size:.9rem; }}
    table {{ width:100%; border-collapse:collapse; font-size:.92rem; }} th,td {{ text-align:left; padding:10px 9px; border-bottom:1px solid var(--line); vertical-align:top; }} th {{ color:#314c5b; background:var(--pale); }}
    .note {{ border-left:4px solid #d1a24b; padding:12px 15px; background:#fff9eb; color:#594719; }} .small {{ font-size:.9rem; color:var(--muted); }}
    footer {{ margin-top:22px; color:var(--muted); font-size:.86rem; }}
    @media(max-width:760px) {{ .cards {{ grid-template-columns:repeat(2,1fr); }} section {{ overflow-x:auto; }} }}
    @media(max-width:430px) {{ .cards {{ grid-template-columns:1fr; }} header {{ padding:26px 22px; }} h1 {{ font-size:1.8rem; }} }}
  </style>
</head>
<body>
<main>
  <header>
    <div class="eyebrow">Waterline · Public data review</div>
    <h1>Can these water figures be reported together?</h1>
    <p>A water services analyst may receive pipe records and organisation-wide measures from different sources. This review checks what each source says and whether the figures can be compared.</p>
  </header>
  <div class="cards" aria-label="Extract summary">
    <div class="card"><div class="value">{len(assets)}</div><div class="label">Pipe records in the sample</div></div>
    <div class="card"><div class="value">{len(set(ids))}</div><div class="label">Different pipe IDs in the sample</div></div>
    <div class="card"><div class="value">{missing_criticality}/{len(assets)}</div><div class="label">Rows with no criticality value</div></div>
    <div class="card"><div class="value">4 × 4</div><div class="label">Four measures checked for four organisations</div></div>
  </div>
  <section><h2>What this means for reporting</h2><p>This sample can describe the 25 pipe records, but it cannot tell us about every pipe in the network. The source's criticality field is blank in all 25 rows. Tararua's four selected workbook values are present, but the workbook does not give confidence ratings for them.</p><p>One file describes individual pipes. The other reports measures for each water service organisation. There is no verified link showing which pipes are counted in each organisation's figures, so report them separately.</p><p>For a water services team, these checks help prevent a small sample being mistaken for a whole-network result. Ask the data owners to clarify the blank fields before relying on them. This review does not assess pipe safety, engineering needs or investment priority.</p><h3>Why this is relevant to Waitī Waters</h3><p>In its <a href="https://www.waitiwaters.co.nz/site_files/55862/upload_files/PublicBoardpack15October2026.2.pdf?dl=1">public October 2026 update</a>, Waitī Waters said it had requested council data files to assess data quality and the work needed to clean and move information into new systems. It also described developing measures for internal performance and external reporting. This review uses public data, but demonstrates a related task: checking definitions and gaps before reporting figures.</p><p><a href="simulated/index.html">See how the separate fictional example handles changes between two versions of a dataset</a>.</p></section>
  <section>
    <h2>Water service measures reported for 2024/25</h2>
    <p class="small">These figures come from Taumata Arowai's 2024/25 workbook. They describe each organisation, not the 25 sample pipes. The rating is the workbook's own view of how reliable each figure is; “Not given” means no rating was supplied.</p>
    <table><thead><tr><th>Organisation</th><th>Measure</th><th>Value reported</th><th>Data confidence rating</th></tr></thead><tbody>{metric_rows}</tbody></table>
  </section>
  <section>
    <h2>What we found in the pipe sample</h2>
    <ul>
      <li>These are the first {len(assets)} in-use records sorted by ID, not a random sample. The findings apply only to these records.</li>
      <li>All {len(assets)} rows include a condition grade and installation date.</li>
      <li>The source's criticality field is blank in all {missing_criticality} rows. The data owner should explain what the field means and where its values are kept.</li>
      <li>The sample contains {sum(lengths):,.2f} metres of pipe. This is not the total length of the network.</li>
      <li>The source does not explain its material codes or condition-grade scale, so this report leaves them as supplied.</li>
    </ul>
    <div class="note"><strong>Missing rating in the workbook:</strong> Tararua has values for all four selected measures, but no data confidence ratings are shown. No rating was supplied, and none has been guessed.</div>
  </section>
  <section>
    <h2>Questions for the data owners</h2>
    <ul>
      <li>What do the material codes and condition grades mean?</li>
      <li>Where is the criticality information held, and how is it defined?</li>
      <li>How were the organisation-wide measures calculated, and what do the confidence ratings mean?</li>
    </ul>
    <p class="small">A separate fictional review note shows how an analyst could record a question about the missing criticality values. It does not add information to the public data.</p>
    <p class="small">The pipe source is maintained by Wellington Water Ltd. It warns that accuracy may vary and the data is not for detailed engineering design. This review does not assess regulatory compliance or make investment recommendations.</p>
  </section>
  <footer><a href="../README.md">Project overview, sources and method</a></footer>
</main>
</body>
</html>
"""
    (REPORT_DIR / "index.html").write_text(page, encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()


