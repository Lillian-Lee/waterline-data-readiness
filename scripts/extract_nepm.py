"""Extract a small, cell-traceable NEPM view from the published workbook."""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = ROOT / "data" / "source_files" / "nepm-2024-2025-final-data-extract.xlsx"
OUTPUT_FILE = ROOT / "data" / "reference" / "nepm_organisation_metrics.csv"
SHEET_NAME = "DW Organisations"
TARGET_ORGANISATIONS = {
    "ACC-00001075": "Carterton District Council",
    "ACC-00001026": "Masterton District Council",
    "ACC-00001109": "South Wairarapa District Council",
    "ACC-00008574": "Tararua District Council",
}
PERIOD = "2024-2025"

METRICS = [
    {
        "code": "D-R9.1",
        "label": "Pipes with condition grading",
        "value_header": "D-R9.1 % of pipes with condition grading",
        "reason_header": "D-R9.1 Reason not available",
        "confidence_header": "D-R9.1 Data confidence",
        "unit": "percent",
    },
    {
        "code": "D-R9.2",
        "label": "Pipe condition grading methodology",
        "value_header": "D-R9.2 Pipe condition grading methodology",
        "reason_header": "D-R9.2 Reason not available",
        "confidence_header": "D-R9.2 Data confidence",
        "unit": "category",
    },
    {
        "code": "D-R10",
        "label": "Pipes in poor or very poor condition",
        "value_header": "D-R10 % pipes in poor or very poor condition",
        "reason_header": "D-R10 Reason not available",
        "confidence_header": "D-R10 Data confidence",
        "unit": "percent",
    },
    {
        "code": "D-R12",
        "label": "Average age of water pipes",
        "value_header": "D-R12 Average age of water pipes (years)",
        "reason_header": "D-R12 Reason not available",
        "confidence_header": "D-R12 Data confidence",
        "unit": "years",
    },
]

FIELDS = [
    "account_id",
    "organisation",
    "reporting_period",
    "metric_code",
    "metric_label",
    "value",
    "unit",
    "methodology",
    "data_confidence",
    "reason_not_available",
    "source_sheet",
    "source_row",
    "source_value_cell",
    "source_reason_cell",
    "source_confidence_cell",
    "extraction_status",
]


def clean(value: object) -> str:
    return "" if value is None else str(value)


def main() -> None:
    if not SOURCE_FILE.exists():
        raise FileNotFoundError(f"Source workbook not found: {SOURCE_FILE}")

    workbook = load_workbook(SOURCE_FILE, data_only=True, read_only=True)
    sheet = workbook[SHEET_NAME]
    headers = [cell.value for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
    columns = {header: index + 1 for index, header in enumerate(headers) if header}
    required_headers = {"Account ID", "Org Name"}
    for metric in METRICS:
        required_headers.update(
            {metric["value_header"], metric["reason_header"], metric["confidence_header"]}
        )
    missing_headers = sorted(required_headers - columns.keys())
    if missing_headers:
        raise ValueError(f"Required workbook columns are missing: {missing_headers}")

    target_rows: dict[str, tuple[int, tuple[object, ...]]] = {}
    for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
        account_id = clean(row[columns["Account ID"] - 1])
        if account_id in TARGET_ORGANISATIONS:
            target_rows[account_id] = (row_number, row)
    missing_accounts = sorted(TARGET_ORGANISATIONS.keys() - target_rows.keys())
    if missing_accounts:
        raise ValueError(f"Target accounts were not found in the workbook: {missing_accounts}")

    extracted: list[dict[str, str]] = []
    for account_id, organisation in TARGET_ORGANISATIONS.items():
        row_number, row = target_rows[account_id]
        if clean(row[columns["Org Name"] - 1]) != organisation:
            raise ValueError(f"Organisation name does not match account {account_id}")
        for metric in METRICS:
            value_column = columns[metric["value_header"]]
            reason_column = columns[metric["reason_header"]]
            confidence_column = columns[metric["confidence_header"]]
            extracted.append(
                {
                    "account_id": account_id,
                    "organisation": organisation,
                    "reporting_period": PERIOD,
                    "metric_code": metric["code"],
                    "metric_label": metric["label"],
                    "value": clean(row[value_column - 1]),
                    "unit": metric["unit"],
                    "methodology": "",
                    "data_confidence": clean(row[confidence_column - 1]),
                    "reason_not_available": clean(row[reason_column - 1]),
                    "source_sheet": SHEET_NAME,
                    "source_row": str(row_number),
                    "source_value_cell": f"{get_column_letter(value_column)}{row_number}",
                    "source_reason_cell": f"{get_column_letter(reason_column)}{row_number}",
                    "source_confidence_cell": f"{get_column_letter(confidence_column)}{row_number}",
                    "extraction_status": "verified_from_workbook",
                }
            )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(extracted)
    workbook.close()
    print(f"Wrote {len(extracted)} metric rows from {SOURCE_FILE.name} to {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
