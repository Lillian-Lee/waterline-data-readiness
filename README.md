# Waterline: Checking Water Data Before It Is Reported

## Why I built this project

Before a water services team reports on water pipes or planned construction and renewal projects, it needs to know what the figures mean and whether the source files can be compared. This project shows those checks with public water data, then uses a separate fictional example to practise following up a data difference.

The advertised Data and Analytics Specialist role asks for clear reporting, useful analysis, data quality and governance. This project demonstrates a small part of that work. It is an independent portfolio project. It does not use Waitī Waters data or describe work done for the company.

This is relevant to Waitī Waters because its [public October 2026 board update](https://www.waitiwaters.co.nz/site_files/55862/upload_files/PublicBoardpack15October2026.2.pdf?dl=1) says the organisation was requesting data files from councils to assess data quality and the work needed to clean and migrate them. The update also describes work on measures for internal performance and external reporting. Waterline does not use those company files; it shows a small, related task: check what the data says, record gaps and avoid reporting a comparison until the details are confirmed.

## What I did

**Public data:** I reviewed 25 pipe records from a South Wairarapa public asset layer and selected water service measures from Taumata Arowai's 2024/25 workbook. I checked what each source describes, looked for missing values and recorded where the workbook figures came from.

**Fictional example:** I created two versions of a small asset and capital-project register (a list of assets and planned projects). The records include differences that could affect a report, such as a changed ID, missing information, a different budget period or an unclear amount unit. I recorded why each difference matters and what type of owner should check it. One fictional confirmation updates a working copy and the report; the original file stays unchanged.

## What the review found

- All 25 pipe records have a condition grade and installation date. The source's criticality field is blank in all 25. The data owner would need to explain what this field means and where those values are held.
- The workbook includes four selected measures for Carterton, Masterton, South Wairarapa and Tararua. Tararua's values are present, but its confidence ratings are blank.
- The pipe list describes individual pipes. The workbook reports one set of measures per water service organisation. There is no verified link between the two, so I kept them separate instead of presenting them as a combined result.

The public data supports a description of these records, but it cannot confirm the condition of the whole network or support engineering, risk or investment decisions.

In the fictional example, confirming one amount unit made 7 of 12 project estimates comparable, up from 6. The NZD 25,000 difference is between estimates, not actual spending. Five estimates still could not be compared fairly.

## How I checked the data

1. Kept a record of each source, its date and the fields used.
2. Checked for missing values and repeated IDs.
3. Checked whether two records had the same ID, reporting period, scope and amount unit before comparing them.
4. Wrote down each unresolved question, why it could affect the report and who could answer it.
5. In the fictional example, recorded one confirmation, updated a working copy and recalculated the report without changing the original file.

## Sources and records

- **Pipe data:** [South Wairarapa 3Waters asset layer](https://services7.arcgis.com/2ECs938g489DMWjt/arcgis/rest/services/SWDC_3Waters_Asset_Data/FeatureServer/13). The extract contains the first 25 records marked `In Use`, sorted by asset ID. It is a small fixed sample, not a random sample or a full export. Wellington Water Ltd requires attribution and warns that accuracy may vary. The data is not for detailed engineering design.
- **Water service measures:** [Taumata Arowai's 2024/25 Network Environmental Performance Measures workbook](https://catalogue.data.govt.nz/dataset/network-environmental-performance-report-24-25/resource/c347b182-79a6-4f06-aa43-a9e4e0be17d1). The workbook is released under CC BY 3.0 New Zealand. The selected measures cover pipe condition grading, grading method, pipes rated poor or very poor, and average pipe age.
- The [public data dictionary](data/reference/data-dictionary.csv) and [fictional data dictionary](data/simulated/reconciliation/data-dictionary.csv) explain the fields. The [source list](data/source-register.csv) and [file record](data/snapshot-manifest.csv) show where the data came from and which local files were used. The extracted workbook values include exact sheet and cell references in [this CSV](data/reference/nepm_organisation_metrics.csv).

## Open the reports

- [Public data findings](reports/index.html)
- [Fictional two-snapshot example](reports/simulated/index.html)

The fictional example is clearly labelled and is kept separate from the public data. It does not represent Waitī Waters or any council's actual records or decisions.

## Rebuild the reports

Use Python 3.10 or later from this folder:

```text
python scripts/analyse.py
python scripts/generate_scenario.py
python scripts/reconcile_scenario.py
```

To recreate the selected workbook extract from the original Excel file, install the packages in `requirements.txt` and run `python scripts/extract_nepm.py`.

## Project folders

- `data/` holds the public source files, extracted data, field definitions and fictional inputs.
- `reports/` holds the two report pages and their supporting tables.
- `scripts/` holds the data extraction and analysis steps.

