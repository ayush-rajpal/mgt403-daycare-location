"""
Optional: re-download the public raw data and rebuild the extracts in data/extracts/.
The repository already contains the extracts, so this is only needed to verify them from scratch.

    python src/download_raw_data.py            # download what is missing
    python src/download_raw_data.py --rebuild  # also delete the extracts so steps 1/3/5 rebuild them from raw files

Sources
  NDCP2022.xlsx   U.S. Dept. of Labor, National Database of Childcare Prices (2008-2022)
                  https://www.dol.gov/agencies/wb/topics/featured-childcare
  oesmYYma.zip    BLS Occupational Employment and Wage Statistics, metro/nonmetro area files, May 2015-2022
                  https://www.bls.gov/oes/special-requests/oesmYYma.zip
  ACS 5-year      Census API (needs a free key): https://api.census.gov/data/key_signup.html
                  -> rebuilt automatically by step 3 when data/extracts/acs5_YYYY_county.csv is missing
  CPI-U           BLS series CUUR0000SA0 (annual averages), already in data/raw/cpi_u_annual.csv
  Boundaries      Census cartographic boundary files 2022 (20m), already in data/raw/

Some government sites reject scripted downloads. If a download fails, download the file in a browser and save it
to the path printed below.
"""
import sys
import urllib.request

from common import NDCP_XLSX, NDCP_EXTRACT, OEWS_DIR, OEWS_EXTRACT, ACS_DIR, ACS_LABELS

UA = {"User-Agent": "Mozilla/5.0 (research reproduction; MGT-403 data project)"}
FILES = [("https://www.dol.gov/sites/dolgov/files/WB/NDCP2022.xlsx", NDCP_XLSX)]
FILES += [(f"https://www.bls.gov/oes/special-requests/oesm{y % 100:02d}ma.zip", OEWS_DIR / f"oesm{y % 100:02d}ma.zip")
          for y in range(2015, 2023)]


def fetch(url, dest):
    if dest.exists():
        print(f"  have  {dest.name}")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
            data = r.read()
        if data[:2] not in (b"PK",):  # xlsx and zip files both start with PK
            raise ValueError("server returned a web page instead of the file")
        dest.write_bytes(data)
        print(f"  got   {dest.name} ({len(data) / 1e6:.1f} MB)")
        return True
    except Exception as e:
        print(f"  FAILED {dest.name}: {e}\n         download manually: {url}\n         and save as: {dest}")
        return False


if __name__ == "__main__":
    ok = all([fetch(u, d) for u, d in FILES])
    if "--rebuild" in sys.argv:
        if not ok:
            sys.exit("Not rebuilding extracts because some raw files are missing.")
        for f in [NDCP_EXTRACT, OEWS_EXTRACT]:
            f.unlink(missing_ok=True)
        print("Deleted NDCP and OEWS extracts; run  python run_all.py  to rebuild them from the raw files.")
        print("(ACS extracts are kept; delete data/extracts/acs5_*.csv and set CENSUS_API_KEY to re-pull them.)")
    print("done" if ok else "some files need a manual download (see above)")
