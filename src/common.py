"""
Shared paths and helpers used by every step of the pipeline.

Folder layout (all paths are relative to the repository root):
  data/raw/        original inputs (small ones are committed; large public downloads are fetched by
                   src/download_raw_data.py and git-ignored)
  data/extracts/   small extracts of the large raw files, committed so the pipeline runs without downloading
  outputs/ps4|ps5|final/   tables, figures and results.json written by each analysis step
  deliverables/    the PDFs and the slide deck
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
EXTRACTS = ROOT / "data" / "extracts"
OUT_PS4 = ROOT / "outputs" / "ps4"
OUT_PS5 = ROOT / "outputs" / "ps5"
OUT_FINAL = ROOT / "outputs" / "final"
DELIVERABLES = ROOT / "deliverables"
for _d in (RAW, EXTRACTS, OUT_PS4, OUT_PS5, OUT_FINAL, DELIVERABLES):
    _d.mkdir(parents=True, exist_ok=True)

# ---- inputs ----
NDCP_XLSX = RAW / "NDCP2022.xlsx"                      # DOL National Database of Childcare Prices (88 MB, downloaded)
NDCP_EXTRACT = EXTRACTS / "ndcp_2015_2022.csv"         # the columns/years we use, extracted from NDCP_XLSX
OEWS_DIR = RAW / "oews"                                # BLS OEWS oesmYYma.zip files (275 MB, downloaded)
OEWS_EXTRACT = EXTRACTS / "oews_39-9011.csv"           # SOC 39-9011 rows extracted from the OEWS zips
ACS_DIR = EXTRACTS                                     # acs5_YYYY_county.csv pulled from the Census API
ACS_LABELS = EXTRACTS / "acs_labels.json"              # ACS variable labels by vintage (consistency check)
CROSSWALK = RAW / "county_oews_crosswalk.csv"          # course-provided county x year -> OEWS area crosswalk
CPI = RAW / "cpi_u_annual.csv"                         # BLS CPI-U (CUUR0000SA0) annual averages
APPENDIX_B = RAW / "ndcp_appendixB_imputations.csv"    # NDCP Technical Report Appendix B, transcribed
COUNTY_SHAPES = RAW / "cb_2022_us_county_20m.zip"      # Census cartographic boundaries (map only)
STATE_SHAPES = RAW / "cb_2022_us_state_20m.zip"
CENSUS_KEY_FILE = ROOT / "census_api_key.txt"          # optional; git-ignored. Or set env var CENSUS_API_KEY

NDCP_COLS = ["STATE_NAME", "STATE_ABBREVIATION", "COUNTY_NAME", "COUNTY_FIPS_CODE", "STUDYYEAR", "MCINFANT",
             "MCTODDLER", "MCPRESCHOOL", "MCInfant_flag", "MCToddler_flag", "MCPreschool_flag", "_75CPRESCHOOL"]


def load_ndcp():
    """NDCP county prices 2015-2022 (raw columns). Builds the extract from the workbook if it is missing."""
    if not NDCP_EXTRACT.exists():
        if not NDCP_XLSX.exists():
            raise SystemExit(f"Missing {NDCP_EXTRACT.name} and {NDCP_XLSX.name}: run  python src/download_raw_data.py")
        df = pd.read_excel(NDCP_XLSX, usecols=NDCP_COLS)
        df[df.STUDYYEAR.between(2015, 2022)][NDCP_COLS].to_csv(NDCP_EXTRACT, index=False)
    return pd.read_csv(NDCP_EXTRACT)


def register_arial():
    """Register an 'Arial' font family for reportlab: real Arial on Windows/macOS, a metric-compatible or bundled
    fallback elsewhere, so the PDFs build on any machine."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import matplotlib
    mpl = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    candidates = [
        [Path("C:/Windows/Fonts") / f for f in ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf")],
        [Path("/System/Library/Fonts/Supplemental") / f for f in
         ("Arial.ttf", "Arial Bold.ttf", "Arial Italic.ttf", "Arial Bold Italic.ttf")],
        [Path("/usr/share/fonts/truetype/liberation") / f for f in
         ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf",
          "LiberationSans-BoldItalic.ttf")],
        [mpl / f for f in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf")],
    ]
    files = next(c for c in candidates if all(p.exists() for p in c))
    for name, f in zip(("Arial", "Arial-Bold", "Arial-Italic", "Arial-BoldItalic"), files):
        pdfmetrics.registerFont(TTFont(name, str(f)))
    pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic",
                                  boldItalic="Arial-BoldItalic")
