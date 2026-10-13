"""
MGT-403 Data Project -- Problem Set 4: The Distribution of Childcare Prices

Inputs (paths defined in src/common.py):
  data/extracts/ndcp_2015_2022.csv  DOL National Database of Childcare Prices, county level (extract of NDCP2022.xlsx)
  county_oews_crosswalk.csv   course-provided county x year -> OEWS area crosswalk
  cpi_u_annual.csv            CPI-U (CUUR0000SA0) annual averages; fetched from the BLS API if absent

Outputs (outputs/ps4): figures (PNG), tables (CSV), and results.txt with every number reported.

Run:  python src/step1_ps4_prices.py   (or python run_all.py)
"""
import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

from common import OUT_PS4 as OUT, CROSSWALK, CPI, load_ndcp as load_ndcp_raw

YEARS = range(2015, 2023)
# NDCP median weekly full-time price, center-based care, by age group
PRICE_VARS = {"MCINFANT": "Infant", "MCTODDLER": "Toddler", "MCPRESCHOOL": "Preschool"}
COLORS = {"Infant": "#2a6fdb", "Toddler": "#e07b39", "Preschool": "#3a9a5b"}
WEEKS_PER_MONTH = 4.33
VOUCHER_MONTHLY = {2022: 706, 2015: 473}  # CCDF center-based preschool voucher, nominal $

log_lines = []
results = {}  # everything reported, consumed by make_report.py


def log(s=""):
    print(s)
    log_lines.append(str(s))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_ndcp():
    cols = ["STATE_NAME", "STATE_ABBREVIATION", "COUNTY_NAME", "COUNTY_FIPS_CODE", "STUDYYEAR", *PRICE_VARS]
    df = load_ndcp_raw()[cols]
    # FIPS is stored as an integer in the workbook; restore the 5-character zero-padded code
    df["county_fips"] = df["COUNTY_FIPS_CODE"].astype(int).astype(str).str.zfill(5)
    df["year"] = df["STUDYYEAR"].astype(int)
    return df[df["year"].isin(YEARS)].copy()


def load_crosswalk():
    cw = pd.read_csv(CROSSWALK, dtype=str)  # keep leading zeros
    cw["year"] = cw["year"].astype(int)
    return cw


def load_cpi():
    path = CPI
    if not path.exists():
        req = urllib.request.Request(
            "https://api.bls.gov/publicAPI/v2/timeseries/data/",
            data=json.dumps({"seriesid": ["CUUR0000SA0"], "startyear": "2015",
                             "endyear": "2022", "annualaverage": True}).encode(),
            headers={"Content-type": "application/json"})
        resp = json.load(urllib.request.urlopen(req))
        rows = [(int(x["year"]), float(x["value"]))
                for x in resp["Results"]["series"][0]["data"] if x["period"] == "M13"]
        pd.DataFrame(rows, columns=["year", "cpi_u"]).sort_values("year").to_csv(path, index=False)
    return pd.read_csv(path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def summarize(x):
    """Mean, SD, N and t-based 95% CI for the mean."""
    x = x.dropna()
    n, mean, sd = len(x), x.mean(), x.std(ddof=1)
    se = sd / np.sqrt(n)
    tcrit = stats.t.ppf(0.975, n - 1)
    return {"N": n, "Mean": mean, "SD": sd, "SE": se, "t_crit": tcrit,
            "CI95_low": mean - tcrit * se, "CI95_high": mean + tcrit * se,
            "Median": x.median(), "Min": x.min(), "Max": x.max()}


def one_sample_t(x, mu0):
    x = x.dropna()
    n, xbar, s = len(x), x.mean(), x.std(ddof=1)
    se = s / np.sqrt(n)
    t = (xbar - mu0) / se
    p = 2 * stats.t.sf(abs(t), n - 1)
    return {"n": n, "xbar": xbar, "s": s, "se": se, "mu0": mu0, "t": t, "df": n - 1, "p": p,
            "tcrit": stats.t.ppf(0.975, n - 1)}


# ---------------------------------------------------------------------------
# Q1. Metro analysis sample
# ---------------------------------------------------------------------------
ndcp, cw, cpi = load_ndcp(), load_crosswalk(), load_cpi()

m = ndcp.merge(cw, on=["county_fips", "year"], how="left", indicator=True, validate="1:1")
log("=== Q1. Sample construction ===")
log(f"NDCP county-years 2015-2022: {len(ndcp):,}")
log(f"  matched to crosswalk: {(m['_merge'] == 'both').sum():,}; unmatched: {(m['_merge'] == 'left_only').sum():,}")
metro = m[m["oews_area"].str.startswith("00", na=False)].drop(columns="_merge").copy()
log(f"Metro sample (oews_area begins '00'): {len(metro):,} county-years")
counts = metro.groupby("year").agg(counties=("county_fips", "size"),
                                   **{f"n_{v}": (k, "count") for k, v in PRICE_VARS.items()})
log(counts.to_string())
counts.to_csv(OUT / "q1_sample_counts.csv")
results["q1"] = {"ndcp_rows": len(ndcp), "matched": int((m["_merge"] == "both").sum()),
                 "metro_rows": len(metro), "counts": counts.reset_index().to_dict("records")}

# ---------------------------------------------------------------------------
# Q2. 2022 distribution of center-based median prices by age group
# ---------------------------------------------------------------------------
log("\n=== Q2. 2022 center-based median weekly prices (nominal = 2022 $) ===")
d22 = metro[metro["year"] == 2022]
tab2 = pd.DataFrame({lab: summarize(d22[var]) for var, lab in PRICE_VARS.items()}).T
log(tab2.round(2).to_string())
tab2.round(4).to_csv(OUT / "q2_summary_2022.csv")
results["q2"] = {"table": tab2.to_dict("index"), "paired": []}

# Paired differences for counties reporting all three ages (supports the age comparison)
both = d22.dropna(subset=list(PRICE_VARS))
log(f"\nCounties with all three prices in 2022: {len(both)}")
for a, b in [("MCINFANT", "MCTODDLER"), ("MCTODDLER", "MCPRESCHOOL"), ("MCINFANT", "MCPRESCHOOL")]:
    diff = both[a] - both[b]
    r = stats.ttest_rel(both[a], both[b])
    results["q2"]["paired"].append({"a": PRICE_VARS[a], "b": PRICE_VARS[b], "n": len(both),
        "diff": diff.mean(), "pct": diff.mean() / both[b].mean(), "share_pos": (diff > 0).mean(),
        "share_zero": (diff == 0).mean(), "t": r.statistic, "p": r.pvalue})
    log(f"  {PRICE_VARS[a]} - {PRICE_VARS[b]}: mean diff ${diff.mean():.2f}/wk "
        f"({diff.mean() / both[b].mean():.1%} of {PRICE_VARS[b]} mean), "
        f"share of counties with diff>0: {(diff > 0).mean():.1%}, share = 0: {(diff == 0).mean():.1%}, "
        f"paired t = {r.statistic:.2f}, p = {r.pvalue:.2g}")

fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
bins = np.arange(0, d22[list(PRICE_VARS)].max().max() + 20, 20)
for ax, (var, lab) in zip(axes, PRICE_VARS.items()):
    x = d22[var].dropna()
    ax.hist(x, bins=bins, color=COLORS[lab], edgecolor="white", alpha=0.9)
    ax.axvline(x.mean(), color="black", lw=1.5, label=f"Mean \\${x.mean():.0f}")
    ax.axvline(x.median(), color="black", lw=1.2, ls="--", label=f"Median \\${x.median():.0f}")
    ax.set_title(f"{lab}  (N={len(x)}, mean=\\${x.mean():.2f}, SD=\\${x.std():.2f})", fontsize=10)
    ax.set_xlabel("Median weekly full-time price, center-based ($)")
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
axes[0].set_ylabel("Number of metro counties")
fig.suptitle("2022 county median center-based childcare prices by age group (metro counties)")
fig.tight_layout()
fig.savefig(OUT / "q2_histograms_2022.png", dpi=150)
plt.close(fig)

# ---------------------------------------------------------------------------
# Q3. Real (2022 $) trends
# ---------------------------------------------------------------------------
log("\n=== Q3. Trends in real (2022 $) prices ===")
cpi = cpi.set_index("year")["cpi_u"]
log("CPI-U annual averages:\n" + cpi.to_string())
metro["deflator"] = cpi.loc[2022] / metro["year"].map(cpi)
for var in PRICE_VARS:
    metro[f"{var}_real"] = metro[var] * metro["deflator"]

rows = []
for (yr, g) in metro.groupby("year"):
    for var, lab in PRICE_VARS.items():
        s = summarize(g[f"{var}_real"])
        nom = g[var].dropna()
        rows.append({"year": yr, "age": lab, "N": s["N"], "mean_real": s["Mean"],
                     "ci_low": s["CI95_low"], "ci_high": s["CI95_high"],
                     "median_real": s["Median"], "mean_nominal": nom.mean()})
trend = pd.DataFrame(rows)
trend.round(2).to_csv(OUT / "q3_trends_real.csv", index=False)
log(trend.pivot(index="year", columns="age", values="mean_real").round(2).to_string())

# Balanced panel: counties reporting a price for the age group in every year 2015-2022
bal_rows = []
for var, lab in PRICE_VARS.items():
    ok = metro.dropna(subset=[var]).groupby("county_fips")["year"].nunique()
    keep = ok[ok == len(YEARS)].index
    g = metro[metro["county_fips"].isin(keep)].groupby("year")[f"{var}_real"].mean()
    for yr, v in g.items():
        bal_rows.append({"year": yr, "age": lab, "N_balanced": len(keep), "mean_real_balanced": v})
bal = pd.DataFrame(bal_rows)
bal.round(2).to_csv(OUT / "q3_trends_real_balanced.csv", index=False)
log("\nBalanced panel (same counties every year):")
log(bal.pivot(index="year", columns="age", values="mean_real_balanced").round(2).to_string())
log("N balanced: " + bal.groupby("age")["N_balanced"].first().to_string().replace("\n", "; "))

log("\nChange 2015 -> 2022, mean across counties:")
for lab in PRICE_VARS.values():
    t = trend[trend.age == lab].set_index("year")
    b = bal[bal.age == lab].set_index("year")
    peak = t["mean_real"].idxmax()
    log(f"  {lab}: nominal ${t.loc[2015, 'mean_nominal']:.2f} -> ${t.loc[2022, 'mean_nominal']:.2f} "
        f"({t.loc[2022, 'mean_nominal'] / t.loc[2015, 'mean_nominal'] - 1:+.1%}); "
        f"real ${t.loc[2015, 'mean_real']:.2f} -> ${t.loc[2022, 'mean_real']:.2f} "
        f"({t.loc[2022, 'mean_real'] / t.loc[2015, 'mean_real'] - 1:+.1%}); "
        f"real peak {peak} (${t.loc[peak, 'mean_real']:.2f}); "
        f"balanced real {b.loc[2015, 'mean_real_balanced'] / 1:.2f} -> {b.loc[2022, 'mean_real_balanced']:.2f} "
        f"({b.loc[2022, 'mean_real_balanced'] / b.loc[2015, 'mean_real_balanced'] - 1:+.1%})")
results["q3"] = {"cpi": {int(k): v for k, v in cpi.items()}, "trend": trend.to_dict("records"),
                 "balanced": bal.to_dict("records")}
log(f"CPI-U inflation 2015 -> 2022: {cpi.loc[2022] / cpi.loc[2015] - 1:+.1%}")

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
for lab in PRICE_VARS.values():
    t = trend[trend.age == lab]
    axes[0].plot(t.year, t.mean_real, marker="o", color=COLORS[lab], label=f"{lab} (all reporting counties)")
    axes[0].fill_between(t.year, t.ci_low, t.ci_high, color=COLORS[lab], alpha=0.15)
    b = bal[bal.age == lab]
    axes[0].plot(b.year, b.mean_real_balanced, ls="--", color=COLORS[lab], alpha=0.8,
                 label=f"{lab} (balanced panel, N={b.N_balanced.iloc[0]})")
    axes[1].plot(t.year, t.mean_nominal, marker="o", color=COLORS[lab], label=lab)
axes[0].set_title("Real (constant 2022 \\$, CPI-U): mean of county median prices, 95% CI shaded")
axes[1].set_title("Nominal \\$: mean of county median prices")
for ax in axes:
    ax.set_xlabel("Year")
    ax.set_ylabel("Weekly full-time price, center-based ($)")
    ax.set_xticks(list(YEARS))
    ax.spines[["top", "right"]].set_visible(False)
axes[0].legend(frameon=False, fontsize=8, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.12))
axes[1].legend(frameon=False, fontsize=8, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
fig.suptitle("Center-based childcare prices in metro counties, 2015-2022")
fig.tight_layout()
fig.savefig(OUT / "q3_trends.png", dpi=150)
plt.close(fig)

# ---------------------------------------------------------------------------
# Q4. Is the CCDF voucher equal to the average median preschool center price?
# ---------------------------------------------------------------------------
log("\n=== Q4. CCDF voucher test (two-sided one-sample t-test, alpha = 0.05) ===")
q4 = {}
for yr, voucher in VOUCHER_MONTHLY.items():
    mu0 = voucher / WEEKS_PER_MONTH
    x = metro.loc[metro["year"] == yr, "MCPRESCHOOL"]  # nominal, same year as the voucher
    r = one_sample_t(x, mu0)
    sp = stats.ttest_1samp(x.dropna(), mu0)  # package check
    q4[yr] = r | {"voucher": voucher, "scipy_t": sp.statistic, "scipy_p": sp.pvalue,
                  "share_above": (x.dropna() > mu0).mean(), "median": x.median()}
    log(f"\n{yr}: voucher ${voucher}/month / {WEEKS_PER_MONTH} = mu0 = ${mu0:.4f}/week")
    log(f"  n = {r['n']}, xbar = {r['xbar']:.4f}, s = {r['s']:.4f}, "
        f"SE = s/sqrt(n) = {r['s']:.4f}/{np.sqrt(r['n']):.4f} = {r['se']:.4f}")
    log(f"  t = (xbar - mu0)/SE = ({r['xbar']:.4f} - {r['mu0']:.4f})/{r['se']:.4f} = {r['t']:.4f}, df = {r['df']}")
    log(f"  p = 2*P(T_{r['df']} > |t|) = {r['p']:.6g}; critical |t| = {r['tcrit']:.4f}")
    log(f"  scipy.stats.ttest_1samp: t = {sp.statistic:.4f}, p = {sp.pvalue:.6g}")
    log(f"  monthly equivalent: mean price x 4.33 = ${r['xbar'] * WEEKS_PER_MONTH:.2f} vs voucher ${voucher}")
    log(f"  share of counties with weekly price above mu0: {(x.dropna() > mu0).mean():.1%}")

# Robustness: one observation per metro area (average of its counties)
log("\nRobustness: metro area as the unit (mean of county prices within each OEWS area)")
for yr, voucher in VOUCHER_MONTHLY.items():
    mu0 = voucher / WEEKS_PER_MONTH
    xa = metro[metro["year"] == yr].groupby("oews_area")["MCPRESCHOOL"].mean()
    r = one_sample_t(xa, mu0)
    q4[yr]["metro_unit"] = r
    log(f"  {yr}: metro areas n = {r['n']}, xbar = {r['xbar']:.2f}, s = {r['s']:.2f}, "
        f"t = {r['t']:.3f}, p = {r['p']:.4g}")

# Reporting-composition check for the 2021 dip: states whose metro preschool coverage changed 2020 -> 2021
cov = (metro[metro["year"].isin([2020, 2021])].groupby(["STATE_ABBREVIATION", "year"])["MCPRESCHOOL"]
       .agg(["count", "mean"]).unstack("year"))
chg = cov[cov[("count", 2020)] != cov[("count", 2021)]]
log("\nStates whose count of metro counties with preschool prices changed 2020 -> 2021:")
log(chg.round(2).to_string())
results["q3"]["coverage_change_2021"] = [
    {"state": st, "n2020": int(r[("count", 2020)]), "n2021": int(r[("count", 2021)]),
     "mean2020": r[("mean", 2020)], "mean2021": r[("mean", 2021)]} for st, r in chg.iterrows()]
results["q4"] = {str(k): v for k, v in q4.items()}

(OUT / "results.json").write_text(json.dumps(results, indent=1, default=float), encoding="utf-8")
(OUT / "results.txt").write_text("\n".join(log_lines), encoding="utf-8")
