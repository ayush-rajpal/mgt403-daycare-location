"""
MGT-403 Data Project -- Problem Set 5: Cost Drivers in Childcare

Inputs (in ./data):
  oews/oesmYYma.zip            BLS OEWS metropolitan & nonmetropolitan area files, May 2015-2022
  county_oews_crosswalk.csv    course-provided county x year -> OEWS area crosswalk
  census_api_key.txt           your Census API key (one line; never printed or logged)
  cpi_u_annual.csv             CPI-U (CUUR0000SA0) annual averages (BLS)

Outputs (in ./output): panel CSV, figures, tables, results.json and results.txt.

Run:  python ps5.py
"""
import io
import json
import os
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf
from scipy import stats

from common import (OUT_PS5 as OUT, OEWS_DIR, OEWS_EXTRACT, ACS_DIR, ACS_LABELS, CROSSWALK, CPI,
                    CENSUS_KEY_FILE)
YEARS = list(range(2015, 2023))
SOC = "39-9011"  # Childcare Workers

# ACS 5-year variables named in the assignment
ACS_VARS = ["B19301_001E", "B01001_001E", "B23008_002E", "B23008_004E", "B23008_010E", "B23008_013E",
            "B25064_001E", "B15002_019E", "B15002_032E", "B15002_033E", "B15002_034E", "B15002_035E",
            "B23022_026E", "B23022_029E"]

# Predictors reported in the descriptive table, with display labels
PREDICTORS = {
    "wage_annual": "Childcare-worker mean annual wage, OEWS ($)",
    "wage_hourly": "Childcare-worker mean hourly wage, OEWS ($)",
    "per_capita_income": "Per-capita income ($)",
    "pop_total": "Total population",
    "kids_under6": "Own children under 6",
    "kids_under6_allpar_lf": "Under-6 w/ all resident parents in labor force",
    "median_gross_rent": "Median gross rent ($/month)",
    "female_college_share": "Share women 25+ with bachelor's+",
    "female_ftyr_share": "Share women 16-64 full-time year-round",
    "under6_share": "Share kids under 6 (of population)",
    "under6_careneed_share": "Share kids under 6 who need care (of population)",
}

log_lines, results = [], {}


def log(s=""):
    print(s)
    log_lines.append(str(s))


# ---------------------------------------------------------------------------
# Q1. ACS 5-year estimates via the Census API
# ---------------------------------------------------------------------------
def census_key():
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        if not CENSUS_KEY_FILE.exists():
            raise SystemExit("ACS extracts are missing and no Census API key was found. Set CENSUS_API_KEY or put "
                             "your key in census_api_key.txt at the repository root (https://api.census.gov/data/key_signup.html).")
        key = CENSUS_KEY_FILE.read_text(encoding="utf-8").strip()
    return key


def census_get(url_base, params):
    """GET a Census API endpoint; the key is added here so it never appears in logs or errors."""
    q = urllib.parse.urlencode({**params, "key": census_key()}, safe=":*,")
    try:
        with urllib.request.urlopen(f"{url_base}?{q}", timeout=120) as r:
            return json.load(r)
    except Exception as e:  # do not echo the URL (it contains the key)
        raise RuntimeError(f"Census API request to {url_base} failed: {type(e).__name__}") from None


def load_acs():
    frames = []
    for y in YEARS:
        cache = ACS_DIR / f"acs5_{y}_county.csv"
        if not cache.exists():
            rows = census_get(f"https://api.census.gov/data/{y}/acs/acs5",
                              {"get": "NAME," + ",".join(ACS_VARS), "for": "county:*", "in": "state:*"})
            pd.DataFrame(rows[1:], columns=rows[0]).to_csv(cache, index=False)
        d = pd.read_csv(cache, dtype=str)
        d["year"] = y
        frames.append(d)
    acs = pd.concat(frames, ignore_index=True)
    acs["county_fips"] = acs["state"].str.zfill(2) + acs["county"].str.zfill(3)
    for v in ACS_VARS:
        acs[v] = pd.to_numeric(acs[v], errors="coerce")
        acs.loc[acs[v] < 0, v] = np.nan  # Census annotation codes (e.g. -666666666) = not available
    acs["per_capita_income"] = acs["B19301_001E"]
    acs["pop_total"] = acs["B01001_001E"]
    acs["kids_under6"] = acs["B23008_002E"]
    acs["kids_under6_allpar_lf"] = acs[["B23008_004E", "B23008_010E", "B23008_013E"]].sum(axis=1, min_count=3)
    acs["median_gross_rent"] = acs["B25064_001E"]
    acs["female_college_share"] = (acs[["B15002_032E", "B15002_033E", "B15002_034E", "B15002_035E"]]
                                   .sum(axis=1, min_count=4) / acs["B15002_019E"])
    acs["female_ftyr_share"] = acs["B23022_029E"] / acs["B23022_026E"]
    acs["under6_share"] = acs["kids_under6"] / acs["pop_total"]
    acs["under6_careneed_share"] = acs["kids_under6_allpar_lf"] / acs["pop_total"]
    return acs


def check_acs_labels():
    """Confirm every variable code means the same thing in every vintage (metadata needs no key)."""
    cache = ACS_LABELS
    if cache.exists():
        labels = json.loads(cache.read_text())
    else:
        labels = {}
        for y in YEARS:
            for v in ACS_VARS:
                with urllib.request.urlopen(f"https://api.census.gov/data/{y}/acs/acs5/variables/{v}.json",
                                            timeout=60) as r:
                    labels[f"{y}|{v}"] = json.load(r)["label"]
        cache.write_text(json.dumps(labels, indent=1))
    # ignore punctuation/case and the dollar-year in income labels ("in 2015 inflation-adjusted dollars")
    norm = lambda s: re.sub(r"\b20\d\d\b", "YYYY", s.replace(":", "").lower())
    bad = [v for v in ACS_VARS if len({norm(labels[f"{y}|{v}"]) for y in YEARS}) != 1]
    return labels, bad


# ---------------------------------------------------------------------------
# Q2. OEWS childcare-worker wages by area
# ---------------------------------------------------------------------------
def load_oews():
    cache = OEWS_EXTRACT
    if cache.exists():
        return pd.read_csv(cache, dtype={"oews_area": str, "AREA": str, "file": str})
    frames = []
    for y in YEARS:
        z = zipfile.ZipFile(OEWS_DIR / f"oesm{y % 100:02d}ma.zip")
        # MSA_ = metro areas (2015-17: large metros only as divisions); aMSA_ = whole large metros
        # (2015-17 only); BOS_ = nonmetropolitan areas
        for name in z.namelist():
            base = name.split("/")[-1]
            if base.startswith("~$") or not base.lower().endswith("_dl.xlsx"):
                continue
            df = pd.read_excel(io.BytesIO(z.read(name)), sheet_name=0, dtype=str)
            df.columns = [c.strip().upper().replace(" ", "_") for c in df.columns]
            df = df.rename(columns={"AREA_NAME": "AREA_TITLE"})
            d = df[df["OCC_CODE"] == SOC].copy()
            d["year"], d["file"] = y, base
            frames.append(d[["year", "file", "AREA", "AREA_TITLE", "TOT_EMP", "H_MEAN", "A_MEAN"]])
    o = pd.concat(frames, ignore_index=True)
    o["oews_area"] = o["AREA"].str.zfill(7)  # 7-character code, as in the crosswalk
    o.to_csv(cache, index=False)
    return o


# ---------------------------------------------------------------------------
# Build the year x county metro panel (Q3)
# ---------------------------------------------------------------------------
cw = pd.read_csv(CROSSWALK, dtype=str)
cw["year"] = cw["year"].astype(int)
oews = load_oews()
acs = load_acs()
labels, bad_labels = check_acs_labels()
cpi = pd.read_csv(CPI).set_index("year")["cpi_u"]

log("=== Q1. ACS 5-year county data ===")
log(f"ACS rows (county x year): {len(acs):,}; per year: {acs.groupby('year').size().to_dict()}")
log(f"Variable labels identical across 2015-2022 vintages: {not bad_labels} {bad_labels or ''}")
results["q1"] = {"rows_per_year": {int(k): int(v) for k, v in acs.groupby("year").size().items()},
                 "labels_consistent": not bad_labels,
                 "labels_2022": {v: labels[f"2022|{v}"] for v in ACS_VARS}}

log("\n=== Q2. OEWS childcare-worker (SOC 39-9011) area wages ===")
log(oews.groupby(["year", "file"]).size().to_string())
dup = oews.duplicated(["year", "oews_area"]).sum()
log(f"Duplicate year x area rows across files: {dup}")
oews["wage_annual"] = pd.to_numeric(oews["A_MEAN"], errors="coerce")  # '*' = suppressed -> NaN
oews["wage_hourly"] = pd.to_numeric(oews["H_MEAN"], errors="coerce")
oews["childcare_emp"] = pd.to_numeric(oews["TOT_EMP"], errors="coerce")
log(f"Suppressed ('*') annual wage cells: {oews['wage_annual'].isna().sum()}")

log("\n=== Q3. Merge to year x county, metro sample ===")
metro_cw = cw[cw["oews_area"].str.startswith("00")].copy()
# The crosswalk also lists two retired FIPS codes next to their current replacements (12025 Dade -> 12086
# Miami-Dade; 51515 Bedford city -> 51019 Bedford County). They never appear in any ACS vintage and would
# double-count their metro's wage, so drop codes that are absent from the ACS in every year.
retired = sorted(set(metro_cw["county_fips"]) - set(acs["county_fips"]))
metro_cw = metro_cw[~metro_cw["county_fips"].isin(retired)]
results["retired_fips"] = retired
log(f"Dropped retired FIPS codes (absent from every ACS vintage): {retired}")
panel = metro_cw.merge(oews[["year", "oews_area", "wage_annual", "wage_hourly", "childcare_emp", "file"]],
                       on=["year", "oews_area"], how="left", validate="m:1")
acs_cols = ["county_fips", "year", "NAME"] + list(PREDICTORS)[2:] + ACS_VARS
panel = panel.merge(acs[acs_cols], on=["county_fips", "year"], how="left", validate="1:1", indicator="acs_merge")
assert not panel.duplicated(["year", "county_fips"]).any()
cov = panel.groupby("year").agg(
    metro_counties=("county_fips", "size"),
    no_oews_row=("file", lambda s: s.isna().sum()),
    wage_missing=("wage_annual", lambda s: s.isna().sum()),
    acs_missing=("acs_merge", lambda s: (s == "left_only").sum()),
    rent_missing=("median_gross_rent", lambda s: s.isna().sum()))
cov["wage_missing_pct"] = 100 * cov["wage_missing"] / cov["metro_counties"]
log(cov.round(2).to_string())
cov.to_csv(OUT / "q3_merge_coverage.csv")
miss_acs = panel[panel["acs_merge"] == "left_only"][["year", "county_fips", "state_abbr", "area_title"]]
log("County-years with no ACS match:\n" + miss_acs.groupby(["year", "state_abbr"]).size().to_string())
results["q3"] = {
    "coverage": cov.reset_index().to_dict("records"),
    "no_acs": miss_acs.groupby(["year", "state_abbr"]).size().reset_index(name="n").to_dict("records"),
    "wage_missing_areas_2022": sorted(panel[(panel.year == 2022) & panel.wage_annual.isna()]["area_title"].unique()),
    "rows": len(panel), "dup_oews": int(dup),
    "oews_files": oews.groupby(["year", "file"]).size().reset_index(name="n").to_dict("records"),
}
panel.drop(columns=["acs_merge", "file"]).to_csv(OUT / "ps5_county_panel.csv", index=False)

# ---------------------------------------------------------------------------
# Q4. Descriptive table, 2022
# ---------------------------------------------------------------------------
log("\n=== Q4. 2022 descriptive statistics (metro counties) ===")
p22 = panel[panel["year"] == 2022]
desc = pd.DataFrame({lab: {"Mean": p22[v].mean(), "SD": p22[v].std(), "N": p22[v].notna().sum(),
                           "Min": p22[v].min(), "Max": p22[v].max()}
                     for v, lab in PREDICTORS.items()}).T
log(desc.round(4).to_string())
desc.to_csv(OUT / "q4_descriptives_2022.csv")
results["q4"] = {"table": {v: desc.loc[lab].to_dict() for v, lab in PREDICTORS.items()},
                 "labels": PREDICTORS, "n_counties": len(p22),
                 "n_areas_with_wage": int(p22.loc[p22.wage_annual.notna(), "oews_area"].nunique())}

# ---------------------------------------------------------------------------
# Q5. Real (2022 $) trends in wages and rents
# ---------------------------------------------------------------------------
log("\n=== Q5. Real (2022 $) wages and rents ===")
panel["deflator"] = cpi.loc[2022] / panel["year"].map(cpi)
for v in ["wage_annual", "wage_hourly", "median_gross_rent", "per_capita_income"]:
    panel[f"{v}_real"] = panel[v] * panel["deflator"]


def mean_ci(x):
    x = x.dropna()
    n, m, s = len(x), x.mean(), x.std()
    h = stats.t.ppf(0.975, n - 1) * s / np.sqrt(n)
    return n, m, m - h, m + h


trend_rows = []
for series in ["wage_annual", "median_gross_rent"]:
    ok = panel.dropna(subset=[series]).groupby("county_fips")["year"].nunique()
    balanced = set(ok[ok == len(YEARS)].index)
    for y, g in panel.groupby("year"):
        n, m, lo, hi = mean_ci(g[f"{series}_real"])
        trend_rows.append({"series": series, "year": y, "N": n, "mean_real": m, "ci_low": lo, "ci_high": hi,
                           "mean_nominal": g[series].mean(),
                           "mean_real_balanced": g.loc[g.county_fips.isin(balanced), f"{series}_real"].mean(),
                           "N_balanced": len(balanced)})
trend = pd.DataFrame(trend_rows)
trend.to_csv(OUT / "q5_trends.csv", index=False)
for s in ["wage_annual", "median_gross_rent"]:
    log(f"\n{s}:\n" + trend[trend.series == s].drop(columns="series").round(2).to_string(index=False))
results["q5"] = {"trend": trend.to_dict("records"), "cpi": {int(k): v for k, v in cpi.items()}}

fig, axes = plt.subplots(1, 2, figsize=(14, 5.6))
spec = [("wage_annual", "Childcare-worker mean annual wage", "#2a6fdb"),
        ("median_gross_rent", "Median gross rent ($/month)", "#c0504d")]
for ax, (s, title, col) in zip(axes, spec):
    t = trend[trend.series == s]
    ax.plot(t.year, t.mean_real, marker="o", color=col, label="Real, 2022 \\$ (all counties; 95% CI shaded)")
    ax.fill_between(t.year, t.ci_low, t.ci_high, color=col, alpha=0.15)
    ax.plot(t.year, t.mean_real_balanced, ls="--", color=col, alpha=0.8,
            label=f"Real, 2022 \\$ (balanced panel, N={t.N_balanced.iloc[0]})")
    ax.plot(t.year, t.mean_nominal, ls=":", marker=".", color="grey", label="Nominal \\$ (all counties)")
    ax.set_title(title + " — mean across metro counties")
    ax.set_xticks(YEARS)
    ax.set_xlabel("Year (OEWS May reference year / ACS 5-year end year)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2)
axes[0].set_ylabel("Dollars per year")
axes[1].set_ylabel("Dollars per month")
fig.suptitle("Childcare-worker wages and rents in metro counties, 2015-2022 (CPI-U, constant 2022 dollars)")
fig.tight_layout()
fig.savefig(OUT / "q5_wage_rent_trends.png", dpi=150)
plt.close(fig)

# ---------------------------------------------------------------------------
# Q6. Real wages 2022 vs 2019
# ---------------------------------------------------------------------------
log("\n=== Q6. Real childcare-worker annual wage: 2022 vs 2019 ===")
w = panel.pivot_table(index="county_fips", columns="year", values="wage_annual_real")
pair = w[[2019, 2022]].dropna()
d = pair[2022] - pair[2019]
n, dbar, sd = len(d), d.mean(), d.std()
se = sd / np.sqrt(n)
t_p = dbar / se
p_p = 2 * stats.t.sf(abs(t_p), n - 1)
chk = stats.ttest_rel(pair[2022], pair[2019])
q6 = {"paired": {"n": n, "mean2019": pair[2019].mean(), "mean2022": pair[2022].mean(), "dbar": dbar, "sd": sd,
                 "se": se, "t": t_p, "df": n - 1, "p": p_p, "scipy_t": chk.statistic, "scipy_p": chk.pvalue,
                 "tcrit": stats.t.ppf(0.975, n - 1),
                 "ci": [dbar - stats.t.ppf(0.975, n - 1) * se, dbar + stats.t.ppf(0.975, n - 1) * se],
                 "share_up": (d > 0).mean()}}
x19 = panel.loc[panel.year == 2019, "wage_annual_real"].dropna()
x22 = panel.loc[panel.year == 2022, "wage_annual_real"].dropna()
wt = stats.ttest_ind(x22, x19, equal_var=False)
q6["welch"] = {"n2019": len(x19), "n2022": len(x22), "mean2019": x19.mean(), "mean2022": x22.mean(),
               "sd2019": x19.std(), "sd2022": x22.std(), "t": wt.statistic, "p": wt.pvalue, "df": wt.df}
# One observation per OEWS metro area (wages are measured at this level)
a = (panel[panel.year.isin([2019, 2022])].drop_duplicates(["year", "oews_area"])
     .pivot_table(index="oews_area", columns="year", values="wage_annual_real")[[2019, 2022]].dropna())
ra = stats.ttest_rel(a[2022], a[2019])
q6["metro_paired"] = {"n": len(a), "mean2019": a[2019].mean(), "mean2022": a[2022].mean(),
                      "dbar": (a[2022] - a[2019]).mean(), "t": ra.statistic, "p": ra.pvalue,
                      "share_up": ((a[2022] - a[2019]) > 0).mean()}
nom = panel.pivot_table(index="county_fips", columns="year", values="wage_annual").loc[pair.index]
q6["nominal"] = {"mean2019": nom[2019].mean(), "mean2022": nom[2022].mean()}
q6["cpi_change"] = cpi.loc[2022] / cpi.loc[2019] - 1
for k, v in q6.items():
    log(f"{k}: {v}")
results["q6"] = q6

# ---------------------------------------------------------------------------
# Q7. Bivariate regression, 2022: wage on female college share
# ---------------------------------------------------------------------------
log("\n=== Q7. OLS: childcare-worker annual wage (2022 $) on female college share, 2022 ===")
reg = p22.dropna(subset=["wage_annual", "female_college_share"])
ols = smf.ols("wage_annual ~ female_college_share", data=reg).fit()
hc1 = smf.ols("wage_annual ~ female_college_share", data=reg).fit(cov_type="HC1")
clu = smf.ols("wage_annual ~ female_college_share", data=reg).fit(
    cov_type="cluster", cov_kwds={"groups": pd.factorize(reg["oews_area"])[0]})
log(ols.summary().as_text())
b = "female_college_share"
# Hand check of the slope: cov(x, y) / var(x)
slope_hand = np.cov(reg[b], reg["wage_annual"])[0, 1] / reg[b].var()
q7 = {"n": int(ols.nobs), "coef": ols.params[b], "intercept": ols.params["Intercept"], "se": ols.bse[b],
      "t": ols.tvalues[b], "p": ols.pvalues[b], "ci": list(ols.conf_int().loc[b]), "r2": ols.rsquared,
      "se_hc1": hc1.bse[b], "p_hc1": hc1.pvalues[b], "se_cluster": clu.bse[b], "p_cluster": clu.pvalues[b],
      "t_cluster": clu.tvalues[b], "n_clusters": int(reg["oews_area"].nunique()), "slope_hand": slope_hand,
      "x_mean": reg[b].mean(), "x_sd": reg[b].std(), "y_mean": reg["wage_annual"].mean(),
      "y_sd": reg["wage_annual"].std(), "corr": reg[[b, "wage_annual"]].corr().iloc[0, 1]}
log(f"Q7 summary: {q7}")
results["q7"] = q7

fig, ax = plt.subplots(figsize=(7.5, 5))
ax.scatter(reg[b] * 100, reg["wage_annual"], s=10, alpha=0.45, color="#2a6fdb", edgecolor="none")
xs = np.linspace(reg[b].min(), reg[b].max(), 50)
ax.plot(xs * 100, q7["intercept"] + q7["coef"] * xs, color="black", lw=1.8,
        label=f"OLS fit: wage = {q7['intercept']:,.0f} + {q7['coef']:,.0f} × share  (R² = {q7['r2']:.3f})")
ax.set_xlabel("Women 25+ with a bachelor's degree or higher (% of women 25+), 2022 ACS 5-year")
ax.set_ylabel("Childcare-worker mean annual wage, 2022 ($)")
ax.set_title(f"Childcare-worker wages vs. female college share, metro counties 2022 (N = {q7['n']:,})", fontsize=10)
ax.legend(frameon=True, framealpha=0.9, fontsize=8.5, loc="lower right")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "q7_scatter_wage_college.png", dpi=150)
plt.close(fig)

(OUT / "results.json").write_text(json.dumps(results, indent=1, default=float), encoding="utf-8")
(OUT / "results.txt").write_text("\n".join(log_lines), encoding="utf-8")
