"""Compare the fixed synthetic snapshots and write an auditable review report."""

from __future__ import annotations

import csv
import html
import json
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "simulated" / "reconciliation"
REVIEW_FILE = INPUT_DIR / "review_log.csv"
OUTPUT_DIR = ROOT / "reports" / "simulated"

ISSUE_FIELDS = [
    "record_class",
    "case_id",
    "data_domain",
    "issue_type",
    "source_snapshot",
    "source_region",
    "record_key",
    "source_record_refs",
    "observed_values",
    "potential_reporting_impact",
    "review_owner_role",
    "review_status",
    "scenario_only",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def asset_key(row: dict[str, str]) -> tuple[str, str]:
    return row["source_region"], row["source_asset_id"]


def project_key(row: dict[str, str]) -> tuple[str, str]:
    return row["source_region"], row["source_project_id"]


def index_unique(rows: list[dict[str, str]], key_fn, label: str) -> dict[tuple[str, str], dict[str, str]]:
    indexed: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = key_fn(row)
        if key in indexed:
            raise ValueError(f"{label} has a duplicate composite key: {key}")
        indexed[key] = row
    return indexed


def apply_simulated_confirmation(
    current_rows: list[dict[str, str]], review_rows: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    reviewed = deepcopy(current_rows)
    decisions: list[dict[str, object]] = []
    allowed_fields = {"amount_unit"}
    for review in review_rows:
        if review["record_class"] != "SIMULATED" or review["review_status"] != "SIMULATED_CONFIRMED":
            continue
        if review["public_source_changed"].lower() != "false":
            raise ValueError("A simulated review must not alter a public source")
        if review["change_applied_to_derived_copy"].lower() != "true":
            raise ValueError("The confirmed example must be applied to a derived copy")
        if review["field_name"] not in allowed_fields:
            raise ValueError(f"This scenario does not allow changes to {review['field_name']}")

        region, local_id = review["record_key"].split("|", maxsplit=1)
        matches = [
            row
            for row in reviewed
            if row["source_region"] == region and row["source_project_id"] == local_id
        ]
        if len(matches) != 1:
            raise ValueError(f"Review case {review['case_id']} matched {len(matches)} rows")
        target = matches[0]
        if target[review["field_name"]] != review["observed_value"]:
            raise ValueError(f"Observed value does not match the source row for {review['case_id']}")

        original_value = target[review["field_name"]]
        target["source_amount_unit"] = original_value
        target[review["field_name"]] = review["simulated_confirmed_value"]
        target["derived_review_case_id"] = review["case_id"]
        target["derivation_note"] = "Simulated owner confirmation; raw snapshot remains unchanged."
        decisions.append(
            {
                "record_class": "SIMULATED",
                "case_id": review["case_id"],
                "source_region": region,
                "record_key": review["record_key"],
                "field_name": review["field_name"],
                "source_value": original_value,
                "derived_value": review["simulated_confirmed_value"],
                "review_owner_role": review["review_owner_role"],
                "review_status": "Applied to derived copy only",
                "source_snapshot": review["source_snapshot"],
                "source_record_ref": review["source_record_ref"],
                "public_source_changed": "false",
            }
        )
    return reviewed, decisions


def compare_projects(
    baseline_rows: list[dict[str, str]], current_rows: list[dict[str, str]], comparison_label: str
) -> list[dict[str, object]]:
    baseline = index_unique(baseline_rows, project_key, "Snapshot S1 projects")
    current = index_unique(current_rows, project_key, comparison_label)
    keys = sorted(set(baseline) | set(current))
    comparisons: list[dict[str, object]] = []

    for key in keys:
        old = baseline.get(key)
        new = current.get(key)
        reasons: list[str] = []
        old_nzd = ""
        new_nzd = ""
        difference = ""
        percentage_change = ""

        if old is None or new is None:
            status = "Held: no matching composite key"
            reasons.append("The source-region and source-project key appears in only one snapshot.")
        else:
            for label, row in (("S1", old), ("current", new)):
                if not row["amount_value"].strip():
                    reasons.append(f"{label} amount is blank")
                if row["currency"] != "NZD":
                    reasons.append(f"{label} currency is not the agreed NZD currency")
                if row["amount_unit"] not in {"NZD", "NZD000"}:
                    reasons.append(f"{label} amount unit is unresolved")
            for field, label in (
                ("budget_period", "budget period differs"),
                ("estimate_basis", "estimate basis differs"),
                ("scope_version", "scope version differs"),
            ):
                if old[field] != new[field]:
                    reasons.append(label)

            if reasons:
                status = "Held: confirm comparability"
            else:
                old_factor = 1000 if old["amount_unit"] == "NZD000" else 1
                new_factor = 1000 if new["amount_unit"] == "NZD000" else 1
                old_nzd = round(float(old["amount_value"]) * old_factor, 2)
                new_nzd = round(float(new["amount_value"]) * new_factor, 2)
                difference = round(new_nzd - old_nzd, 2)
                percentage_change = round((difference / old_nzd) * 100, 2) if old_nzd else ""
                status = "Comparable estimates"

        comparisons.append(
            {
                "record_class": "SIMULATED",
                "source_region": key[0],
                "source_project_id": key[1],
                "s1_source_ref": old["source_record_ref"] if old else "",
                "current_source_ref": new["source_record_ref"] if new else "",
                "s1_amount": old["amount_value"] if old else "",
                "s1_unit": old["amount_unit"] if old else "",
                "current_amount": new["amount_value"] if new else "",
                "current_unit": new["amount_unit"] if new else "",
                "s1_amount_nzd": old_nzd,
                "current_amount_nzd": new_nzd,
                "difference_nzd": difference,
                "change_percent": percentage_change,
                "comparison_status": status,
                "hold_reasons": "; ".join(reasons),
                "owner_role": new["owner_role"] if new else "",
            }
        )
    return comparisons


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    assets_a = read_csv(INPUT_DIR / "assets_snapshot_a.csv")
    assets_b = read_csv(INPUT_DIR / "assets_snapshot_b.csv")
    projects_a = read_csv(INPUT_DIR / "projects_snapshot_a.csv")
    projects_b = read_csv(INPUT_DIR / "projects_snapshot_b.csv")
    review_rows = read_csv(REVIEW_FILE)

    if any(row["record_class"] != "SIMULATED" for rows in (assets_a, assets_b, projects_a, projects_b) for row in rows):
        raise ValueError("All reconciliation input rows must be labelled SIMULATED")
    assets_a_by_key = index_unique(assets_a, asset_key, "Snapshot S1 assets")
    assets_b_by_key = index_unique(assets_b, asset_key, "Snapshot S2 assets")
    asset_differences: list[dict[str, object]] = []
    issues: list[dict[str, object]] = []

    def add_issue(
        case_id: str,
        domain: str,
        issue_type: str,
        snapshot: str,
        region: str,
        record_key: str,
        source_refs: str,
        values: str,
        impact: str,
        owner: str,
        status: str = "Open in simulation",
    ) -> None:
        issues.append(
            {
                "record_class": "SIMULATED",
                "case_id": case_id,
                "data_domain": domain,
                "issue_type": issue_type,
                "source_snapshot": snapshot,
                "source_region": region,
                "record_key": record_key,
                "source_record_refs": source_refs,
                "observed_values": values,
                "potential_reporting_impact": impact,
                "review_owner_role": owner,
                "review_status": status,
                "scenario_only": "true",
            }
        )

    old_local_ids = Counter(row["source_asset_id"] for row in assets_a)
    local_id_collisions = {key: count for key, count in old_local_ids.items() if count > 1}
    add_issue(
        "SIM-A-001",
        "asset",
        "Source IDs repeat across regions",
        "S1 and S2",
        "All four fictional regions",
        "source_asset_id",
        "All four source registers",
        f"{len(local_id_collisions)} local ID values recur across regions",
        "Different regions can use the same ID. Include the region with the ID so records are not mixed up.",
        "Data migration lead",
    )

    asset_fields = (
        ("installed_year", "Installation year changed", "Asset information owner", "Ask the data owner which year is correct before reporting asset age."),
        ("condition_grade", "Condition grade changed", "Asset information owner", "The grading scale is not defined, so we cannot tell whether this change is better or worse."),
        ("criticality", "Criticality value is now missing", "Asset information owner", "Ask where the value came from and what it means. Leave it unknown until confirmed."),
        ("operational_status", "Status changed but no date is given", "Asset information owner", "The record says the asset is no longer in service, but gives no date. Check when this took effect."),
    )
    old_only = sorted(set(assets_a_by_key) - set(assets_b_by_key))
    new_only = sorted(set(assets_b_by_key) - set(assets_a_by_key))
    paired_old: set[tuple[str, str]] = set()
    paired_new: set[tuple[str, str]] = set()
    old_by_region: dict[str, list[tuple[str, str]]] = defaultdict(list)
    new_by_region: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for key in old_only:
        old_by_region[key[0]].append(key)
    for key in new_only:
        new_by_region[key[0]].append(key)
    for region in sorted(set(old_by_region) & set(new_by_region)):
        if len(old_by_region[region]) == 1 and len(new_by_region[region]) == 1:
            old_key = old_by_region[region][0]
            new_key = new_by_region[region][0]
            paired_old.add(old_key)
            paired_new.add(new_key)
            old_row = assets_a_by_key[old_key]
            new_row = assets_b_by_key[new_key]
            case = "SIM-A-002"
            record_key = f"{region}|{old_key[1]} -> {new_key[1]}"
            impact = "Because the ID changed, this may look like one asset removed and another added. Ask the migration lead whether both IDs refer to the same asset before reporting the count."
            asset_differences.append(
                {
                    "record_class": "SIMULATED",
                    "case_id": case,
                    "source_region": region,
                    "record_key": record_key,
                    "changed_field": "source_asset_id",
                    "s1_value": old_key[1],
                    "s2_value": new_key[1],
                    "s1_source_ref": old_row["source_record_ref"],
                    "s2_source_ref": new_row["source_record_ref"],
                    "review_owner_role": "Data migration lead",
                    "review_status": "Open in simulation",
                }
            )
            add_issue(case, "asset", "Asset ID changed between versions", "S1 and S2", region, record_key, f"{old_row['source_record_ref']}; {new_row['source_record_ref']}", f"S1={old_key[1]}; S2={new_key[1]}", impact, "Data migration lead")

    for key in sorted(set(assets_a_by_key) | set(assets_b_by_key)):
        if key in paired_old or key in paired_new:
            continue
        old = assets_a_by_key.get(key)
        new = assets_b_by_key.get(key)
        record_key = f"{key[0]}|{key[1]}"
        if old is None or new is None:
            source_a = old["source_record_ref"] if old else ""
            source_b = new["source_record_ref"] if new else ""
            case = f"SIM-A-{len(asset_differences) + 2:03d}"
            values = f"S1={key[1] if old else 'not present'}; S2={key[1] if new else 'not present'}"
            impact = "The changed ID may make the same asset look like one removal and one new asset. Check whether the IDs refer to the same pipe."
            asset_differences.append(
                {
                    "record_class": "SIMULATED",
                    "case_id": case,
                    "source_region": key[0],
                    "record_key": record_key,
                    "changed_field": "source_asset_id",
                    "s1_value": key[1] if old else "",
                    "s2_value": key[1] if new else "",
                    "s1_source_ref": source_a,
                    "s2_source_ref": source_b,
                    "review_owner_role": "Data migration lead",
                    "review_status": "Open in simulation",
                }
            )
            add_issue(case, "asset", "No matching region and ID between versions", "S1 and S2", key[0], record_key, f"{source_a}; {source_b}", values, impact, "Data migration lead")
            continue

        for field, issue_type, owner, impact in asset_fields:
            if old[field] == new[field]:
                continue
            case = f"SIM-A-{len(asset_differences) + 2:03d}"
            asset_differences.append(
                {
                    "record_class": "SIMULATED",
                    "case_id": case,
                    "source_region": key[0],
                    "record_key": record_key,
                    "changed_field": field,
                    "s1_value": old[field],
                    "s2_value": new[field],
                    "s1_source_ref": old["source_record_ref"],
                    "s2_source_ref": new["source_record_ref"],
                    "review_owner_role": owner,
                    "review_status": "Open in simulation",
                }
            )
            issue = issue_type
            if field == "operational_status" and not new["status_effective_date"]:
                issue = "Status changed but no date was recorded"
            add_issue(case, "asset", issue, "S1 and S2", key[0], record_key, f"{old['source_record_ref']}; {new['source_record_ref']}", f"S1={old[field]}; S2={new[field]}", impact, owner)

    projects_a_by_key = index_unique(projects_a, project_key, "Snapshot S1 projects")
    projects_b_by_key = index_unique(projects_b, project_key, "Snapshot S2 projects")
    project_id_counts = Counter(row["source_project_id"] for row in projects_a)
    repeated_project_ids = sum(count > 1 for count in project_id_counts.values())
    add_issue(
        "SIM-C-001",
        "capital project",
        "Project ID values repeat in different regions",
        "S1 and S2",
        "All four fictional regions",
        "source_project_id",
        "All four fictional project files",
        f"{repeated_project_ids} project ID values recur across regions",
        "The same project ID appears in different regions. Include the region when matching records so different projects are not confused.",
        "Programme data steward",
    )

    before = compare_projects(projects_a, projects_b, "Snapshot S2 before review")
    reviewed_projects_b, decision_rows = apply_simulated_confirmation(projects_b, review_rows)
    after = compare_projects(projects_a, reviewed_projects_b, "Snapshot S2 derived after review")
    reviewed_fields = list(projects_b[0]) + ["source_amount_unit", "derived_review_case_id", "derivation_note"]
    write_csv(OUTPUT_DIR / "reviewed_projects_snapshot_b.csv", reviewed_projects_b, reviewed_fields)
    write_csv(OUTPUT_DIR / "review_decision_log.csv", decision_rows, list(decision_rows[0]) if decision_rows else [])
    write_csv(OUTPUT_DIR / "project_comparison_before_review.csv", before, list(before[0]))
    write_csv(OUTPUT_DIR / "project_comparison_after_review.csv", after, list(after[0]))
    write_csv(
        OUTPUT_DIR / "asset_snapshot_differences.csv",
        asset_differences,
        list(asset_differences[0]) if asset_differences else [],
    )

    review_by_key = {row["record_key"]: row for row in review_rows if row["record_class"] == "SIMULATED"}
    for row in before:
        reason = str(row["hold_reasons"])
        if "amount unit is unresolved" in reason:
            review_key = f"{row['source_region']}|{row['source_project_id']}"
            review = review_by_key.get(review_key)
            if review:
                add_issue(
                    review["case_id"],
                    "capital project",
                    "Amount unit is unclear",
                    "S2",
                    row["source_region"],
                    review["record_key"],
                    review["source_record_ref"],
                    f"S1={row['s1_amount']} {row['s1_unit']}; S2={row['current_amount']} {row['current_unit']}; simulated confirmation={review['simulated_confirmed_value']}",
                    "Snapshot 1 shows NZD 850,000. Snapshot 2 shows 875, but the unit is unknown. Do not compare them until the finance owner confirms the unit.",
                    review["review_owner_role"],
                    "Resolved in simulation; real confirmation still required",
                )

    # Add targeted project issues for the differences that remain open.
    issue_specs = {
        "Council A|CP-03": ("Estimate type changed (approved estimate vs forecast)", "Programme manager", "One amount is an approved estimate and the other is a current forecast. They are different types of estimate, so do not compare them as a change."),
        "Council B|CP-01": ("Financial year changed", "Programme manager", "The amounts cover different financial years, so they do not show a change over the same period."),
        "Council B|CP-02": ("Project scope changed", "Programme manager", "The project includes different work in each version, so the amounts cannot be compared fairly."),
        "Council C|CP-01": ("Current amount is missing", "Project finance owner", "The latest amount is blank. Ask the finance owner to confirm the value or explain why it is missing."),
        "Council C|CP-03": ("Project ID changed between versions", "Data migration lead", "This may be a new project or the same project with a new ID. Check before counting it as added or removed."),
        "Council D|CP-03": ("No owner is listed", "Programme data steward", "There is no named role to answer questions about this project. Assign an owner before review."),
    }
    after_by_key = {(str(row["source_region"]), str(row["source_project_id"])): row for row in reviewed_projects_b}
    for key_text, (issue_type, owner, impact) in issue_specs.items():
        region, project_id = key_text.split("|", maxsplit=1)
        new = after_by_key.get((region, project_id))
        renamed_new = None
        if region == "Council C" and project_id == "CP-03":
            renamed_new = after_by_key.get((region, "CP-03-RECODED"))
        old = projects_a_by_key.get((region, project_id))
        refs = "; ".join(row["source_record_ref"] for row in (old, new, renamed_new) if row)
        values = " | ".join(
            f"S1 {field}={old[field]}" for field in ("amount_value", "amount_unit", "budget_period", "estimate_basis", "scope_version")
        ) if old else ""
        if new:
            values += " | " + " | ".join(
                f"S2 {field}={new[field]}" for field in ("amount_value", "amount_unit", "budget_period", "estimate_basis", "scope_version")
            )
        if renamed_new:
            values += f" | S2 source_project_id={renamed_new['source_project_id']} | S2 amount_value={renamed_new['amount_value']} {renamed_new['amount_unit']}"
        case = f"SIM-C-{len(issues) + 1:03d}"
        add_issue(case, "capital project", issue_type, "S1 and S2", region, key_text, refs, values, impact, owner)

    write_csv(OUTPUT_DIR / "issue_register.csv", issues, ISSUE_FIELDS)
    comparable_before = [row for row in before if row["comparison_status"] == "Comparable estimates"]
    comparable_after = [row for row in after if row["comparison_status"] == "Comparable estimates"]
    confirmed_change = next((row for row in after if row["source_region"] == "Council D" and row["source_project_id"] == "CP-02"), None)
    summary = {
        "record_class": "SIMULATED",
        "snapshot_s1": "2025-06-30",
        "snapshot_s2": "2025-10-31",
        "asset_rows": {"s1": len(assets_a), "s2": len(assets_b)},
        "asset_composite_key_matches": len(set(assets_a_by_key) & set(assets_b_by_key)),
        "asset_keys_only_in_s1": len(set(assets_a_by_key) - set(assets_b_by_key)),
        "asset_keys_only_in_s2": len(set(assets_b_by_key) - set(assets_a_by_key)),
        "project_rows": {"s1": len(projects_a), "s2": len(projects_b)},
        "projects_comparable_before_review": len(comparable_before),
        "projects_comparable_after_simulated_review": len(comparable_after),
        "confirmed_case_change_nzd": confirmed_change["difference_nzd"] if confirmed_change else None,
        "confirmed_case_change_percent": confirmed_change["change_percent"] if confirmed_change else None,
        "issue_count": len(issues),
        "open_issue_count": sum(row["review_status"] == "Open in simulation" for row in issues),
        "resolved_in_simulation_issue_count": sum(row["review_status"].startswith("Resolved in simulation") for row in issues),
        "simulated_confirmations_applied_to_derived_copy": len(decision_rows),
        "public_data_changed": False,
        "project_asset_link_created": False,
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


    display_labels = {
        "asset": "Asset",
        "capital project": "Capital project",
        "source_asset_id": "Asset ID field",
        "source_project_id": "Project ID field",
        "Data migration lead": "Migration lead",
        "Asset information owner": "Asset data owner",
        "Programme data steward": "Project data owner",
        "Programme manager": "Project manager",
        "Project finance owner": "Finance owner",
        "Open in simulation": "Still open in this example",
        "Resolved in simulation; real confirmation still required": "Confirmed in this fictional example only",
    }
    issue_rows = "".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(str(display_labels.get(row[field], row[field])))}</td>"
            for field in ("data_domain", "issue_type", "source_region", "record_key", "potential_reporting_impact", "review_owner_role", "review_status")
        )
        + "</tr>"
        for row in issues
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Waterline | Fictional two-version data example</title>
  <style>
    :root {{ color-scheme:light; --ink:#172d3b; --muted:#526777; --line:#d7e0e5; --blue:#155c78; --pale:#eef5f7; --amber:#825b12; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; background:#f5f7f8; color:var(--ink); font:16px/1.55 "Segoe UI",Arial,sans-serif; }}
    main {{ max-width:1120px; margin:36px auto; padding:0 24px 48px; }} header {{ background:linear-gradient(120deg,#16364a,#1b687d); color:#fff; border-radius:14px; padding:30px 34px; }}
    .flag {{ display:inline-block; padding:4px 9px; border-radius:5px; background:#fff1c9; color:#62450c; font-size:.78rem; font-weight:700; letter-spacing:.04em; }} h1 {{ margin:13px 0 8px; line-height:1.15; }} header p {{ color:#e1eef1; max-width:790px; margin-bottom:0; }}
    section {{ background:white; border:1px solid var(--line); border-radius:12px; padding:22px; margin-top:20px; }} h2 {{ margin:0 0 12px; font-size:1.2rem; }}
    .cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:18px; }} .card {{ background:#fff; border:1px solid var(--line); border-radius:9px; padding:14px; }} .value {{ color:var(--blue); font-size:1.65rem; font-weight:700; }} .label {{ color:var(--muted); font-size:.9rem; }}
    .callout {{ border-left:4px solid #d1a24b; background:#fff9eb; padding:12px 15px; }} table {{ width:100%; border-collapse:collapse; font-size:.88rem; }} th,td {{ text-align:left; vertical-align:top; padding:9px 8px; border-bottom:1px solid var(--line); }} th {{ background:var(--pale); }} .scroll {{ overflow-x:auto; }} .small {{ color:var(--muted); font-size:.9rem; }} a {{ color:var(--blue); }} footer {{ color:var(--muted); font-size:.85rem; margin-top:18px; }}
    @media(max-width:800px) {{ .cards {{ grid-template-columns:repeat(2,1fr); }} }} @media(max-width:460px) {{ .cards {{ grid-template-columns:1fr; }} header {{ padding:24px 20px; }} }}
  </style>
</head>
<body><main>
  <header><span class="flag">SIMULATED EXAMPLE · ALL RECORDS ARE FICTIONAL</span><h1>What changed between the two data versions?</h1><p>This example compares fictional records from 30 June 2025 and 31 October 2025. It shows how to check changes in asset and capital-project records, record why they matter and ask the right role to confirm them. It uses no Waitī Waters or council records.</p></header>
  <div class="cards">
    <div class="card"><div class="value">{len(assets_a)} + {len(projects_a)}</div><div class="label">Assets and capital projects in each version</div></div>
    <div class="card"><div class="value">{summary['asset_composite_key_matches']}/24</div><div class="label">Assets matched by region and ID</div></div>
    <div class="card"><div class="value">{len(comparable_before)}/12 → {len(comparable_after)}/12</div><div class="label">Estimates that can be compared before and after confirmation</div></div>
    <div class="card"><div class="value">{len(decision_rows)}</div><div class="label">Fictional unit correction; original file unchanged</div></div>
  </div>
  <section><h2>What the example shows</h2><p>Compare project amounts only when they refer to the same project, financial year, scope of work and type of estimate, and when the currency and unit are confirmed. One fictional finance owner confirms that an amount is in thousands of New Zealand dollars. That means 7 of 12 projects have comparable estimates, up from 6.</p><p>The NZD 25,000 difference is between estimates, not actual spending. For five projects, the two estimates still cannot be compared fairly. The original data file is unchanged.</p></section>
  <section><h2>Why this matters to Waitī Waters</h2><p>In its <a href="https://www.waitiwaters.co.nz/site_files/55862/upload_files/PublicBoardpack15October2026.2.pdf?dl=1">public October 2026 update</a>, Waitī Waters said it was requesting council data files to assess how much cleaning and migration work was needed. It also described developing measures for internal performance and external reporting.</p><p>This fictional exercise does not use those files. It shows a related step: check whether records and amounts can be compared, record what needs confirmation, and keep unclear figures out of the report until someone checks them.</p><p class="small">The region names, records, dates, amounts and review roles are fictional. The suggested roles are examples, not actual Waitī Waters responsibilities.</p></section>
  <section><h2>Differences to check</h2><p class="small">For each example, the table says what changed, why it could affect a report, which role could check it and whether it is still open in this fictional exercise.</p><div class="scroll"><table><thead><tr><th>Record type</th><th>What changed</th><th>Example region</th><th>Record ID</th><th>Why it matters</th><th>Role to ask</th><th>Status in example</th></tr></thead><tbody>{issue_rows}</tbody></table></div></section>
  <section><h2>How the comparisons are made</h2><ul><li>Match records using both the region and its local ID. Different regions may reuse the same ID.</li><li>Compare amounts only when the project, financial year, work scope, estimate type, currency and unit match.</li><li>If information is missing or unclear, leave the amount out until a data owner confirms it.</li><li>Do not connect a project to a pipe without a verified link. Keep this fictional data separate from the public records.</li></ul><p><a href="issue_register.csv">Open the full issue list</a> · <a href="project_comparison_before_review.csv">See results before confirmation</a> · <a href="project_comparison_after_review.csv">See results after confirmation</a></p></section>
  <footer><a href="../../README.md">Back to Waterline project overview</a> · <a href="../index.html">Open the public-data report</a></footer>
</main></body></html>"""
    (OUTPUT_DIR / "index.html").write_text(page, encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

