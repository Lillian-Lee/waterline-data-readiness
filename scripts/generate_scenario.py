"""Create fixed, clearly synthetic source snapshots for the reconciliation demo."""

from __future__ import annotations

import csv
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "simulated" / "reconciliation"
REGIONS = ("Council A", "Council B", "Council C", "Council D")
SNAPSHOTS = (("S1", "2025-06-30"), ("S2", "2025-10-31"))
CLASSIFICATION = "SIMULATED"

ASSET_FIELDS = [
    "record_class",
    "snapshot_id",
    "snapshot_date",
    "source_region",
    "source_system",
    "source_asset_id",
    "asset_type",
    "operational_status",
    "status_effective_date",
    "installed_year",
    "diameter_mm",
    "condition_grade",
    "criticality",
    "owner_role",
    "source_record_ref",
]

PROJECT_FIELDS = [
    "record_class",
    "snapshot_id",
    "snapshot_date",
    "source_region",
    "source_system",
    "source_project_id",
    "project_name",
    "scope_version",
    "budget_period",
    "estimate_basis",
    "amount_value",
    "amount_unit",
    "currency",
    "owner_role",
    "source_record_ref",
]


def write_rows(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_assets(snapshot_id: str, snapshot_date: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for region_index, region in enumerate(REGIONS):
        for local_index in range(1, 7):
            sequence = region_index * 6 + local_index
            asset_id = f"W-{local_index:03d}"
            grade = ((sequence - 1) % 5) + 1
            row: dict[str, object] = {
                "record_class": CLASSIFICATION,
                "snapshot_id": snapshot_id,
                "snapshot_date": snapshot_date,
                "source_region": region,
                "source_system": f"{region} asset register (synthetic)",
                "source_asset_id": asset_id,
                "asset_type": ("Water main", "Pump station", "Reservoir")[sequence % 3],
                "operational_status": "In service",
                "status_effective_date": "",
                "installed_year": 1970 + sequence * 2,
                "diameter_mm": 100 + (sequence % 4) * 50,
                "condition_grade": grade,
                "criticality": ("Low", "Medium", "High")[sequence % 3],
                "owner_role": "Asset information owner",
                "source_record_ref": f"SYN-{snapshot_id}-{region_index + 1}-A{local_index:03d}",
            }
            rows.append(row)

    if snapshot_id == "S2":
        changes = {
            ("Council A", "W-002"): {"installed_year": 1998},
            ("Council B", "W-004"): {"criticality": ""},
            ("Council C", "W-003"): {"condition_grade": 3},
            ("Council C", "W-005"): {"operational_status": "Decommissioned"},
            ("Council D", "W-006"): {"source_asset_id": "W-006-MIGRATED"},
        }
        for row in rows:
            update = changes.get((str(row["source_region"]), str(row["source_asset_id"])))
            if update:
                row.update(update)
    return rows


PROJECT_BASE = {
    ("Council A", "CP-01"): ("Reservoir renewal", "SCOPE-A1", "FY2026/27", "Approved estimate", "1000000", "NZD"),
    ("Council A", "CP-02"): ("Water main renewals", "SCOPE-A2", "FY2026/27", "Approved estimate", "2400", "NZD000"),
    ("Council A", "CP-03"): ("Treatment upgrade", "SCOPE-A3", "FY2026/27", "Approved estimate", "650000", "NZD"),
    ("Council B", "CP-01"): ("Pump station renewal", "SCOPE-B1", "FY2026/27", "Approved estimate", "500000", "NZD"),
    ("Council B", "CP-02"): ("Storage upgrade", "SCOPE-B2", "FY2026/27", "Approved estimate", "700000", "NZD"),
    ("Council B", "CP-03"): ("Water main renewal", "SCOPE-B3", "FY2026/27", "Approved estimate", "450000", "NZD"),
    ("Council C", "CP-01"): ("Treatment plant works", "SCOPE-C1", "FY2026/27", "Approved estimate", "1200000", "NZD"),
    ("Council C", "CP-02"): ("Pipe renewal package", "SCOPE-C2", "FY2026/27", "Approved estimate", "3400", "NZD000"),
    ("Council C", "CP-03"): ("Network resilience works", "SCOPE-C3", "FY2026/27", "Approved estimate", "800000", "NZD"),
    ("Council D", "CP-01"): ("Water supply upgrade", "SCOPE-D1", "FY2026/27", "Approved estimate", "2000000", "NZD"),
    ("Council D", "CP-02"): ("Renewal programme", "SCOPE-D2", "FY2026/27", "Approved estimate", "850000", "NZD"),
    ("Council D", "CP-03"): ("Treatment asset works", "SCOPE-D3", "FY2026/27", "Approved estimate", "510000", "NZD"),
}


def build_projects(snapshot_id: str, snapshot_date: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for (region, project_id), values in PROJECT_BASE.items():
        project_name, scope, period, basis, amount, unit = values
        rows.append(
            {
                "record_class": CLASSIFICATION,
                "snapshot_id": snapshot_id,
                "snapshot_date": snapshot_date,
                "source_region": region,
                "source_system": f"{region} capital programme extract (synthetic)",
                "source_project_id": project_id,
                "project_name": project_name,
                "scope_version": scope,
                "budget_period": period,
                "estimate_basis": basis,
                "amount_value": amount,
                "amount_unit": unit,
                "currency": "NZD",
                "owner_role": "Programme manager",
                "source_record_ref": f"SYN-{snapshot_id}-{region[-1]}-{project_id}",
            }
        )

    if snapshot_id == "S2":
        changes = {
            ("Council A", "CP-01"): {"amount_value": "1100000"},
            ("Council A", "CP-02"): {"amount_value": "2550"},
            ("Council A", "CP-03"): {"estimate_basis": "Current forecast", "amount_value": "690000"},
            ("Council B", "CP-01"): {"budget_period": "FY2027/28", "amount_value": "520000"},
            ("Council B", "CP-02"): {"scope_version": "SCOPE-B2-REV1", "amount_value": "740000"},
            ("Council B", "CP-03"): {"amount_value": "510000"},
            ("Council C", "CP-01"): {"amount_value": ""},
            ("Council C", "CP-02"): {"amount_value": "3510"},
            ("Council C", "CP-03"): {"source_project_id": "CP-03-RECODED", "amount_value": "820000"},
            ("Council D", "CP-01"): {"amount_value": "2100000"},
            ("Council D", "CP-02"): {"amount_value": "875", "amount_unit": "UNCONFIRMED"},
            ("Council D", "CP-03"): {"amount_value": "530000", "owner_role": ""},
        }
        for row in rows:
            update = changes.get((str(row["source_region"]), str(row["source_project_id"])))
            if update:
                row.update(update)
    return rows


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for snapshot_id, snapshot_date in SNAPSHOTS:
        suffix = "a" if snapshot_id == "S1" else "b"
        write_rows(
            OUTPUT_DIR / f"assets_snapshot_{suffix}.csv",
            build_assets(snapshot_id, snapshot_date),
            ASSET_FIELDS,
        )
        write_rows(
            OUTPUT_DIR / f"projects_snapshot_{suffix}.csv",
            build_projects(snapshot_id, snapshot_date),
            PROJECT_FIELDS,
        )
    print("Wrote two clearly labelled synthetic asset and capital-project snapshots.")


if __name__ == "__main__":
    main()
