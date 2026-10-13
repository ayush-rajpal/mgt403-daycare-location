# Data

Everything the pipeline reads lives here. Paths are defined once in [`src/common.py`](../src/common.py).

## `raw/` — original inputs

| File | What it is | Source | Used by |
|---|---|---|---|
| `county_oews_crosswalk.csv` | County × year → OEWS metro/nonmetro area code and title (course-provided) | MGT-403 course materials | steps 1, 3 |
| `cpi_u_annual.csv` | CPI-U annual averages, series CUUR0000SA0, 2015–2022 | [BLS](https://www.bls.gov/cpi/) (API) | steps 1, 3, 5, 6 |
| `ndcp_appendixB_imputations.csv` | NDCP imputation codes by state × year, transcribed from Appendix B (report pp. 49–50) and checked cell by cell (416 cells) | [NDCP Technical Report, Sept 2024](https://www.dol.gov/sites/dolgov/files/WB/National-Database-of-Childcare-Prices-Technical-Report.pdf) | step 5 |
| `cb_2022_us_county_20m.zip`, `cb_2022_us_state_20m.zip` | County and state outlines (map only) | [Census cartographic boundary files](https://www2.census.gov/geo/tiger/GENZ2022/shp/) | step 5 |
| `NDCP2022.xlsx` *(not committed, 88 MB)* | National Database of Childcare Prices, county level, 2008–2022 | [DOL Women's Bureau](https://www.dol.gov/agencies/wb/topics/featured-childcare) | rebuilds `extracts/ndcp_2015_2022.csv` |
| `oews/oesmYYma.zip` *(not committed, 275 MB)* | BLS OEWS metropolitan & nonmetropolitan area files, May 2015–2022 | `https://www.bls.gov/oes/special-requests/oesmYYma.zip` | rebuilds `extracts/oews_39-9011.csv` |

The two large files are public downloads: `python src/download_raw_data.py` fetches them (or download them in a browser and save to the paths above).

## `extracts/` — small extracts of the large raw files (committed, so the pipeline runs without downloads)

| File | Contents | Built by |
|---|---|---|
| `ndcp_2015_2022.csv` | NDCP rows for 2015–2022; columns: state, county, FIPS, year, median center-based infant/toddler/preschool weekly prices, their age-aggregation flags, 75th-percentile preschool price | `common.load_ndcp()` from `NDCP2022.xlsx` |
| `oews_39-9011.csv` | OEWS rows for SOC 39-9011 Childcare Workers, every area and year (mean annual and hourly wage, employment) | step 3 from the OEWS zips |
| `acs5_YYYY_county.csv` | ACS 5-year county estimates, 2015–2022 vintages, for the variables listed in the assignment | step 3 via the Census API (needs a key) |
| `acs_labels.json` | ACS variable labels by vintage, used to confirm every code means the same thing in every year | step 3 |

To rebuild every extract from the raw sources: `python src/download_raw_data.py --rebuild`, then `python run_all.py`.
For the ACS files, delete `extracts/acs5_*.csv` and set a Census API key (`CENSUS_API_KEY` environment variable or a
`census_api_key.txt` file at the repository root — both are git-ignored).
