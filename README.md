# Where Should We Open Our Next Daycare?

**MGT-403 Data Project (Yale SOM)** · Team: Winston Park, Ayush Rajpal, Tobin Gedstad, Wen Ding, Alfred Mordecai

A national for-profit childcare provider wants to open new center-based preschools. We look for U.S. metro counties
where **preschool prices are high relative to what local costs (childcare-worker wages and rent) predict**, using three
public data sources: DOL childcare prices (NDCP), BLS wages (OEWS) and Census ACS demographics, 2015–2022.

Everything here (every table, figure, PDF and the slide deck) is regenerated from the code with
one command.

## Results at a glance
* **Ten recommended counties** (one per metro): Stearns MN, Norfolk MA, McLean IL, Howard MD, King WA, DuPage IL,
  Champaign IL, Montgomery MD, Worcester MA, Washtenaw MI. On average they charge **$85/week (+37%) more** than their
  wages and rents predict.
* **Reliability:** the price model fits held-out metros about as well as in sample (R² 0.60 vs 0.61); a back-test run as
  of 2018 picked counties that were still $70/week above prediction in 2022; county premiums persist for years.
* **Caveat:** 7 of the 10 picks' 2022 prices are NDCP estimates between state surveys; see the evidence table in the
  analysis PDF. The premium measures pricing power, not profit.

## Deliverables (`deliverables/`)
| File | What it is |
|---|---|
| `Daycare_Expansion_Deck.pptx` | Final presentation (6 slides, speaker notes) |
| `PreAnalysis_and_Final_Analysis.pdf` | Pre-analysis Q1–Q4 and the final project analysis (a)–(e) |
| `Appendix_Data_and_Model_Choices.pdf` | Data handling decisions, model choices, robustness, reproducibility |
| `PS4_Childcare_Prices_Report.pdf`, `PS5_Cost_Drivers_Report.pdf` | Problem Sets 4 and 5 (earlier parts of the project) |

## How to recreate everything

### 1. Install the prerequisites (once)
* **Python 3.11 or newer**: <https://www.python.org/downloads/> (tested with 3.14). Check with `python --version`
  (on some systems the command is `python3`).
* **Node.js 18 or newer**: <https://nodejs.org> (tested with 24). Only needed for the slide deck. Check with `node --version`.
* **Git**: <https://git-scm.com> (or use GitHub's green **Code → Download ZIP** button and unzip instead of cloning).

### 2. Get the code and install the packages
```bash
git clone https://github.com/ayush-rajpal/mgt403-daycare-location.git
cd mgt403-daycare-location
python -m venv .venv                 # optional but recommended: a clean environment
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run the whole pipeline (about 30 seconds)
```bash
python run_all.py
```
This needs **no downloads and no API key**: small extracts of the large raw files are already in `data/extracts/`.
`run_all.py` installs the one Node package (pptxgenjs) the first time, then runs these steps in order and prints `ok`
after each:

| # | Script | What it does | Writes to |
|---|---|---|---|
| 1 | `src/step1_ps4_prices.py` | PS4: childcare price distribution, real trends, CCDF voucher test | `outputs/ps4/` |
| 2 | `src/step2_ps4_report.py` | PS4 report | `deliverables/PS4_Childcare_Prices_Report.pdf` |
| 3 | `src/step3_ps5_cost_panel.py` | PS5: year × county panel (OEWS wages + ACS + crosswalk) and its analysis | `outputs/ps5/` |
| 4 | `src/step4_ps5_report.py` | PS5 report | `deliverables/PS5_Cost_Drivers_Report.pdf` |
| 5 | `src/step5_final_analysis.py` | Pre-analysis Q1–Q4 and the final project analysis | `outputs/final/` |
| 6 | `src/step6_final_documents.py` | Analysis PDF and appendix PDF | `deliverables/` |
| 7 | `src/step7_final_deck.js` | Six-slide deck | `deliverables/Daycare_Expansion_Deck.pptx` |
| ✓ | `checks/verify_results.py` | Recomputes the key results with separate code; stops with an error if anything differs | screen |

It ends with `FAILURES: none` and `All steps finished.` Every number in the PDFs and slides is read from
`outputs/*/results.json`, so a fresh run reproduces the committed files exactly (only the embedded creation dates
differ).

To re-run a single step, run its script from the repository root, e.g. `python src/step5_final_analysis.py`
(steps read the outputs of earlier steps, so run them in order the first time).

### 4. Optional: rebuild from the original raw data
The committed extracts were made from public files. To recreate them from scratch:
1. **NDCP prices and OEWS wages** (≈360 MB):
   ```bash
   python src/download_raw_data.py --rebuild   # downloads NDCP2022.xlsx and the OEWS zips, deletes the extracts
   python run_all.py                           # steps 1, 3 and 5 rebuild the extracts from the raw files
   ```
   Some government sites block scripted downloads; if a file fails, the script prints the URL and the exact path to
   save it to after downloading it in a browser.
2. **Census ACS data** (needs a free key from <https://api.census.gov/data/key_signup.html>):
   delete `data/extracts/acs5_*.csv`, then either set the environment variable `CENSUS_API_KEY` or save the key in a
   file named `census_api_key.txt` at the repository root (both are git-ignored), and run `python run_all.py`.

When `data/raw/NDCP2022.xlsx` is present, `checks/verify_results.py` also checks the prices against the raw workbook.
Sources and contents of every data file are listed in [`data/README.md`](data/README.md).

### Troubleshooting
* `Node.js is required for the slide deck`: install Node.js (step 1), then re-run.
* `ModuleNotFoundError`: run `pip install -r requirements.txt` in the same environment you run `python` from.
* PDFs use Arial when it is installed and a bundled look-alike font otherwise, so they build on Windows, macOS and Linux.

## Where everything is
```
run_all.py                     one command: runs every step below, then the checks
src/
  common.py                    all file paths in one place + shared helpers
  step1_ps4_prices.py          PS4: price distribution, real trends, CCDF voucher test   -> outputs/ps4/
  step2_ps4_report.py          PS4 report PDF                                            -> deliverables/
  step3_ps5_cost_panel.py      PS5: year x county panel = OEWS wages + ACS + crosswalk   -> outputs/ps5/
  step4_ps5_report.py          PS5 report PDF                                            -> deliverables/
  step5_final_analysis.py      Pre-analysis Q1-Q4, price model, premiums, top 10,        -> outputs/final/
                               reliability, characteristics, stability, figures
  step6_final_documents.py     Analysis PDF + appendix PDF                               -> deliverables/
  step7_final_deck.js          Slide deck (Yale blue)                                    -> deliverables/
  apply_theme.js               writes the deck's theme colors (helper for step 7)
  download_raw_data.py         optional: fetch the large public raw files
checks/verify_results.py       independent recomputation of the key results
data/raw/                      original inputs (see data/README.md)
data/extracts/                 small extracts of large raw files (NDCP, OEWS, ACS)
outputs/ps4|ps5|final/         tables (CSV), figures (PNG), results.json, results.txt
deliverables/                  PDFs and slide deck
```
Each step reads only from `data/` and the `outputs/` of earlier steps; every number in the PDFs and slides is read
from `outputs/*/results.json` or the output CSVs, never typed by hand.

## Method in brief
1. **Data.** Merge NDCP county prices (median weekly center-based preschool price) onto the PS5 year × county panel of
   metro counties (OEWS childcare-worker wage via the course crosswalk, ACS 5-year rent and demographics); convert to
   2022 dollars with CPI-U. 8,146 county-years with complete data.
2. **Price model.** Each year, regress price on wage and rent; a county's **premium** is actual minus predicted price.
3. **Screens.** Positive premium in every observed year 2019–22; a county-specific price (no shared rate-zone price,
   no state-level or propensity-score imputation); ≥ 2,000 young children with working parents; one county per metro.
4. **Checks.** Grouped cross-validation, a 2018 back-test, four alternative scoring rules, stability over time, and
   the NDCP imputation evidence behind each pick.

## Notes
* `data/raw/county_oews_crosswalk.csv` was provided by the MGT-403 course; all other inputs are public government data.
* The Census API key is never committed (`census_api_key.txt` and `.env` are git-ignored).
* The analysis code, documents and slides were built with an AI coding assistant (Claude Code) at the team's request
  and re-verified independently; see Appendix A8.
