"""
Independent re-computation of the key results, written separately from the pipeline (plain numpy least squares,
its own merge and screening code), compared with outputs/final/results.json. Exits with an error if anything differs.

Reads NDCP prices straight from data/raw/NDCP2022.xlsx when it has been downloaded, otherwise from the extract.
Run:  python checks/verify_results.py   (run_all.py runs it last)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, EXT, OUT = ROOT / "data" / "raw", ROOT / "data" / "extracts", ROOT / "outputs"
R = json.load(open(OUT / "final" / "results.json", encoding="utf-8"))
fails = []


def chk(name, mine, theirs, tol=1e-6):
    ok = (mine is None and theirs is None) or (abs(float(mine) - float(theirs)) <= tol * max(1.0, abs(float(theirs))))
    print(("PASS " if ok else "FAIL ") + f"{name}: independent={mine}  reported={theirs}")
    if not ok:
        fails.append(name)


def ols(y, X):
    X = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    n, k = X.shape
    s2 = e @ e / (n - k)
    XtXi = np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(s2 * XtXi))
    r2 = 1 - e @ e / ((y - y.mean()) @ (y - y.mean()))
    return b, se, e, r2, X, XtXi


def cluster_se(X, e, XtXi, g):
    n, k = X.shape
    G = len(np.unique(g))
    meat = np.zeros((k, k))
    for gg in np.unique(g):
        s = X[g == gg].T @ e[g == gg]
        meat += np.outer(s, s)
    V = XtXi @ meat @ XtXi * (G / (G - 1)) * ((n - 1) / (n - k))
    return np.sqrt(np.diag(V))


# ---------------- raw inputs ----------------
_cols = ["STATE_ABBREVIATION", "COUNTY_FIPS_CODE", "STUDYYEAR", "MCPRESCHOOL", "MCINFANT", "MCTODDLER", "_75CPRESCHOOL"]
if (RAW / "NDCP2022.xlsx").exists():
    print("NDCP source: raw workbook data/raw/NDCP2022.xlsx")
    nd = pd.read_excel(RAW / "NDCP2022.xlsx", usecols=_cols)
else:
    print("NDCP source: data/extracts/ndcp_2015_2022.csv (download the workbook to check against the raw file)")
    nd = pd.read_csv(EXT / "ndcp_2015_2022.csv", usecols=_cols)
nd = nd[nd.STUDYYEAR.between(2015, 2022)].copy()
nd["fips"] = nd.COUNTY_FIPS_CODE.astype(int).map(lambda v: f"{v:05d}")
nd["year"] = nd.STUDYYEAR.astype(int)
ext = pd.read_csv(EXT / "ndcp_2015_2022.csv")
print("extract rows == source rows:", len(ext) == len(nd),
      "| preschool identical:", np.allclose(ext.MCPRESCHOOL.values, nd.MCPRESCHOOL.values, equal_nan=True))
pan = pd.read_csv(OUT / "ps5" / "ps5_county_panel.csv", dtype={"county_fips": str, "oews_area": str})
cpi = pd.read_csv(RAW / "cpi_u_annual.csv").set_index("year")["cpi_u"]
ab = pd.read_csv(RAW / "ndcp_appendixB_imputations.csv", keep_default_na=False)

nd["zone"] = nd.groupby(["STATE_ABBREVIATION", "year", "MCPRESCHOOL"]).fips.transform("size")
d = pan.merge(nd[["fips", "year", "MCPRESCHOOL", "MCINFANT", "MCTODDLER", "zone"]], left_on=["county_fips", "year"],
              right_on=["fips", "year"], how="left")
d = d.merge(ab, on=["state_abbr", "year"], how="left")
d["codes"] = d.codes.fillna("not listed")
preds = ["wage_annual", "median_gross_rent", "per_capita_income", "pop_total", "kids_under6", "kids_under6_allpar_lf",
         "female_college_share", "female_ftyr_share", "under6_share", "under6_careneed_share"]
d = d[d.MCPRESCHOOL.notna() & d[preds].notna().all(axis=1)].copy()
f = cpi[2022] / d.year.map(cpi)
d["p"] = d.MCPRESCHOOL * f; d["w"] = d.wage_annual * f / 1000; d["r"] = d.median_gross_rent * f / 100

print("\n=== Q1 ===")
chk("analysis rows", len(d), R["q1"]["rows"], 0)
chk("analysis counties", d.county_fips.nunique(), R["q1"]["counties"], 0)
for c in R["q1"]["coverage"]:
    chk(f"rows {c['year']}", (d.year == c["year"]).sum(), c["analysis_rows"], 0)

print("\n=== Q2 (2022) ===")
d22 = d[d.year == 2022]
for v in ["MCPRESCHOOL", "MCTODDLER", "MCINFANT", "wage_annual", "median_gross_rent", "female_college_share",
          "kids_under6_allpar_lf", "per_capita_income"]:
    x = d22[v].dropna()
    t = R["q2"]["table"][v]
    chk(f"{v} mean", x.mean(), t["Mean"]); chk(f"{v} sd", x.std(), t["SD"]); chk(f"{v} N", len(x), t["N"], 0)

print("\n=== Q3/Q4 (2022, nominal = real) ===")
y = d22.MCPRESCHOOL.values; W = d22.wage_annual.values / 1000; Rn = d22.median_gross_rent.values / 100
g = d22.oews_area.values
for key, X, names in [("a", W, ["wage_k"]), ("b", Rn, ["rent_h"]), ("c", np.column_stack([W, Rn]), ["wage_k", "rent_h"])]:
    b, se, e, r2, XX, XtXi = ols(y, X)
    cse = cluster_se(XX, e, XtXi, g)
    q = R["q4"][key]
    chk(f"({key}) intercept", b[0], q["coef"]["Intercept"])
    for i, nm in enumerate(names, 1):
        chk(f"({key}) {nm} coef", b[i], q["coef"][nm]); chk(f"({key}) {nm} se", se[i], q["se"][nm])
        chk(f"({key}) {nm} cluster se", cse[i], q["se_cluster"][nm])
    chk(f"({key}) R2", r2, q["r2"])
cr = np.corrcoef(W, Rn)[0, 1]
chk("corr wage-rent", cr, R["q4"]["ovb"]["corr_wage_rent"])
dl = ols(Rn, W)[0][1]
chk("OVB wage identity", R["q4"]["c"]["coef"]["wage_k"] + R["q4"]["c"]["coef"]["rent_h"] * dl, R["q4"]["a"]["coef"]["wage_k"])
# heteroskedasticity claim (Breusch-Pagan, regress e^2 on X)
b, se, e, r2, XX, _ = ols(y, np.column_stack([W, Rn]))
bp = ols(e ** 2, np.column_stack([W, Rn]))[3] * len(y)
from scipy import stats
print(f"Breusch-Pagan LM = {bp:.1f}, p = {stats.chi2.sf(bp, 2):.2e}  (claim: spread widens with cost)")

print("\n=== Year-by-year cost model, premiums ===")
d["pred"] = np.nan; d["prem"] = np.nan; d["prem_pct"] = np.nan
for yr, gg in d.groupby("year"):
    b, se, e, r2, XX, _ = ols(gg.p.values, gg[["w", "r"]].values)
    d.loc[gg.index, "pred"] = XX @ b; d.loc[gg.index, "prem"] = e
    bl, _, el, _, _, _ = ols(np.log(gg.p.values), np.log(gg[["w", "r"]].values))
    d.loc[gg.index, "prem_pct"] = 100 * (np.exp(el) - 1)
    m = R["yr_models"][str(yr)]
    chk(f"{yr} b_wage", b[1], m["b_wage"]); chk(f"{yr} b_rent", b[2], m["b_rent"]); chk(f"{yr} R2", r2, m["r2"])

Wd = d.pivot_table(index="county_fips", columns="year", values="prem")
g22 = d[d.year == 2022].set_index("county_fips")
rec = Wd[[2019, 2020, 2021, 2022]]
sc = pd.DataFrame({"score": rec.mean(axis=1), "ny": rec.notna().sum(axis=1), "npos": (rec > 0).sum(axis=1)})
sc = sc.join(g22[["area_title", "zone", "codes", "kids_under6_allpar_lf", "NAME", "MCPRESCHOOL", "pred", "prem"]], how="inner")
el = sc[(sc.ny >= 3) & (sc.npos == sc.ny) & (sc.zone <= 2) & ~sc.codes.str.contains("3|6") & (sc.kids_under6_allpar_lf >= 2000)]
print(f"\nfunnel: scored={len(sc)} years_ok={(sc.ny >= 3).sum()} stable={((sc.ny >= 3) & (sc.npos == sc.ny)).sum()} "
      f"eligible={len(el)} metros={el.area_title.nunique()}  | reported {R['funnel']}")
top = el.sort_values("score", ascending=False).drop_duplicates("area_title").head(10)
rep = [t["county_fips"] for t in R["top10"]]
print("TOP-10 identical (same order):", list(top.index) == rep)
for t, (fips, r) in zip(R["top10"], top.iterrows()):
    chk(f"{r.NAME[:22]} price", r.MCPRESCHOOL, t["MCPRESCHOOL"]); chk(f"{r.NAME[:22]} pred", r.pred, t["pred"])
    chk(f"{r.NAME[:22]} score", r.score, t["score"])
print("avg 2022 premium of picks:", round(top.prem.mean(), 2), "| avg price", round(top.MCPRESCHOOL.mean(), 2),
      "| avg pred", round(top.pred.mean(), 2), "| pct", round(top.prem.mean() / top.pred.mean() * 100, 1))
print("picks' avg premium by year:", Wd.loc[top.index].mean().round(1).to_dict())
print("picks with a 2015 value:", Wd.loc[top.index, 2015].notna().sum())

print("\n=== Stability ===")
for L in (1, 7):
    xs, ys = [], []
    for yr in range(2015, 2023 - L):
        pr = Wd[[yr, yr + L]].dropna(); xs += list(pr[yr]); ys += list(pr[yr + L])
    chk(f"lag {L} corr", np.corrcoef(xs, ys)[0, 1], R["stability"]["lag"][L - 1]["corr_all"])
q = pd.DataFrame({"e": Wd[[2015, 2016, 2017, 2018]].mean(axis=1), "l": rec.mean(axis=1)}).dropna()
qe, ql = pd.qcut(q.e, 5, labels=False), pd.qcut(q.l, 5, labels=False)
chk("top quintile stays", ((qe == 4) & (ql == 4)).sum() / (qe == 4).sum(), R["stability"]["top_q_stay"])
chk("top quintile top-2", ((qe == 4) & (ql >= 3)).sum() / (qe == 4).sum(), R["stability"]["top_q_top2"])

print("\n=== Back-test (as of 2018) ===")
g18 = d[d.year == 2018].set_index("county_fips")
f18 = Wd[[2015, 2016, 2017, 2018]]
s18 = pd.DataFrame({"score": f18.mean(axis=1), "ny": f18.notna().sum(axis=1), "npos": (f18 > 0).sum(axis=1)}).join(
    g18[["area_title", "zone", "codes", "kids_under6_allpar_lf", "NAME"]], how="inner")
e18 = s18[(s18.ny >= 3) & (s18.npos == s18.ny) & (s18.zone <= 2) & ~s18.codes.str.contains("3|6") & (s18.kids_under6_allpar_lf >= 2000)]
t18 = e18.sort_values("score", ascending=False).drop_duplicates("area_title").head(10)
p22 = Wd[2022].reindex(t18.index)
print("back-test picks:", list(t18.NAME))
chk("back-test picks' 2022 premium", p22.mean(), R["backtest"]["picks_prem_2022_mean"])
print("picks with 2022 data:", p22.notna().sum(), "| all positive:", (p22.dropna() > 0).all(),
      "| states of missing:", sorted(set(t18.loc[p22.isna()].NAME.str.split(", ").str[-1])))
dec = pd.DataFrame({"f": f18.mean(axis=1), "p": Wd[2022]}).dropna()
dec["d"] = pd.qcut(dec.f, 10, labels=False)
chk("decile 10 mean 2022", dec[dec.d == 9].p.mean(), R["backtest"]["deciles"][9]["prem2022"])
chk("decile 1 mean 2022", dec[dec.d == 0].p.mean(), R["backtest"]["deciles"][0]["prem2022"])
chk("corr formation-2022", dec[["f", "p"]].corr().iloc[0, 1], R["backtest"]["corr_formation_2022"])

print("\n=== Characteristics (2022) ===")
z = g22.copy()
Xc = np.column_stack([z.per_capita_income / 1e4, z.female_college_share * 10, z.female_ftyr_share * 10,
                      z.under6_careneed_share * 100, np.log(z.pop_total)])
b, se, e, r2, XX, XtXi = ols(z.prem.values, Xc)
cse = cluster_se(XX, e, XtXi, z.oews_area.values)
for i, nm in enumerate(["pci_10k", "college_10", "ftyr_10", "careneed_pp", "log_pop"], 1):
    chk(f"char {nm} coef", b[i], R["chars"]["coef"][nm]); chk(f"char {nm} cluster se", cse[i], R["chars"]["se"][nm])
chk("char R2", r2, R["chars"]["r2"])

print("\n=== State FE / between-state share ===")
sm = z.groupby("state_abbr").prem.transform("mean")
chk("between-state share", sm.var() / z.prem.var(), R["prem_between_state_share"])
D = pd.get_dummies(z.state_abbr, drop_first=True).astype(float).values
b, se, e, r2, XX, _ = ols(z.prem.values * 0 + z.p.values, np.column_stack([z.w, z.r, D]))
chk("state-FE R2", r2, R["state_fe"]["r2"])

print("\n=== Zone / data-quality claims ===")
print("share of analysis county-years sharing price with >=1 other county:", round((d.zone > 1).mean(), 3))
print("2022 median zone:", d22.zone.median(), "| 2022 share zone<=2:", round((d22.zone <= 2).mean(), 3))

print("\n=== Price evidence behind each pick and % premium ===")
for t, e in zip(R["top10"], R["evidence"]):
    g = d[d.county_fips == t["county_fips"]].set_index("year")
    pct = 100 * g.loc[2022, "prem"] / g.loc[2022, "pred"]
    sv = g[~g.codes.str.contains("5|6")]
    dr = g[~g.codes.str.contains("3|4|5|6")]
    chk(f"{t['NAME'][:22]} % premium", pct, t["prem_share_pct"])
    chk(f"{t['NAME'][:22]} survey-year premium", sv.prem.iloc[-1], e["survey_prem"])
    chk(f"{t['NAME'][:22]} fully-reported premium", dr.prem.iloc[-1], e["direct_prem"])
    if sv.index.max() != e["survey_year"] or dr.index.max() != e["direct_year"]:
        fails.append(f"{t['NAME']} evidence years")

print("\nFAILURES:", fails if fails else "none")
sys.exit(1 if fails else 0)
