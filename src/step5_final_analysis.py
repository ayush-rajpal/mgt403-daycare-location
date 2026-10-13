"""
MGT-403 Data Project -- Pre-Analysis (Prices and Costs) + Final Project (Where should we open our next daycare?)

Inputs (paths defined in src/common.py)
  outputs/ps5/ps5_county_panel.csv              year x county metro panel built in step 3 (OEWS wages + ACS, crosswalked)
  data/raw/cpi_u_annual.csv                     CPI-U (CUUR0000SA0) annual averages
  data/extracts/ndcp_2015_2022.csv              DOL National Database of Childcare Prices (county level)
  data/raw/ndcp_appendixB_imputations.csv       NDCP Technical Report (Sept 2024) Appendix B, imputation codes by state x year
  data/raw/cb_2022_us_*_20m.zip                 Census cartographic boundaries (map only)

Outputs (outputs/final): analysis dataset, tables (CSV), figures (PNG), results.json, results.txt

Run:  python src/step5_final_analysis.py   (after step 3; or python run_all.py)
"""
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
import statsmodels.formula.api as smf
from scipy import stats

from common import (RAW, OUT_FINAL as OUT, OUT_PS5, CPI, APPENDIX_B, COUNTY_SHAPES, STATE_SHAPES,
                    load_ndcp as load_ndcp_raw)
YEARS = list(range(2015, 2023))
RECENT = [2019, 2020, 2021, 2022]          # scoring window for the recommendation
FORMATION = [2015, 2016, 2017, 2018]       # back-test window (what we would have known in 2018)
MIN_KIDS = 2000                            # market-size floor: under-6 children with all parents working
MAX_ZONE = 2                               # price must be (nearly) county-specific: shared by <= 2 counties in state
SEED = 403

# Yale palette (blue shades on white)
YALE, MID, LIGHT, PALE, GREY, LGREY = "#00356B", "#286DC0", "#63AAFF", "#C9DDF5", "#4A4A4A", "#DDDDDD"
plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.edgecolor": "#888888",
                     "axes.labelcolor": GREY, "xtick.color": GREY, "ytick.color": GREY,
                     "axes.titleweight": "bold", "axes.titlecolor": YALE})

PREDICTORS = {  # ACS + OEWS predictors carried from PS5 (the analysis dataset requires all non-missing)
    "wage_annual": "Childcare-worker mean annual wage (OEWS, $)",
    "median_gross_rent": "Median gross rent ($/month)",
    "per_capita_income": "Per-capita income ($)",
    "pop_total": "Total population",
    "kids_under6": "Own children under 6",
    "kids_under6_allpar_lf": "Under-6 w/ all resident parents in labor force",
    "female_college_share": "Share women 25+ with bachelor's+",
    "female_ftyr_share": "Share women 16-64 full-time year-round",
    "under6_share": "Share kids under 6 (of population)",
    "under6_careneed_share": "Share kids under 6 who need care (of population)",
}
log_lines, R = [], {}


def log(s=""):
    print(s)
    log_lines.append(str(s))


def clean(o):
    """Make numpy/pandas objects JSON-serialisable."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(color="#EEEEEE", lw=0.8)
    ax.set_axisbelow(True)


# =====================================================================================================
# 1. BUILD THE ANALYSIS DATASET
# =====================================================================================================
def load_ndcp():
    n = load_ndcp_raw()
    n["county_fips"] = n["COUNTY_FIPS_CODE"].astype(int).astype(str).str.zfill(5)  # restore leading zeros
    n["year"] = n["STUDYYEAR"].astype(int)
    # Price-zone size: how many counties (metro + nonmetro) in the state report the identical preschool price that
    # year. Many state market-rate surveys publish one price per rate zone, so a shared price is not a local price.
    n["zone_n"] = n.groupby(["STATE_ABBREVIATION", "year", "MCPRESCHOOL"])["county_fips"].transform("size")
    n.loc[n["MCPRESCHOOL"].isna(), "zone_n"] = np.nan
    return n


panel = pd.read_csv(OUT_PS5 / "ps5_county_panel.csv", dtype={"county_fips": str, "oews_area": str})
cpi = pd.read_csv(CPI).set_index("year")["cpi_u"]
ndcp = load_ndcp()
appb = pd.read_csv(APPENDIX_B, keep_default_na=False)  # 'NA' is a code here

m = panel.merge(ndcp[["county_fips", "year", "COUNTY_NAME", "MCPRESCHOOL", "MCINFANT", "MCTODDLER", "zone_n"]],
                on=["county_fips", "year"], how="left", validate="1:1", indicator=True)
assert (m["_merge"] == "both").all(), "every metro county-year should exist in NDCP"
m = m.drop(columns="_merge").merge(appb, on=["state_abbr", "year"], how="left")
m["codes"] = m["codes"].fillna("not listed")
m["interp"] = m["codes"].str.contains("5")              # estimate for a year between state surveys
m["state_level"] = m["codes"].str.contains("3")         # county prices imputed from state-level data
m["psm"] = m["codes"].str.contains("6")                 # propensity-score-match imputation (CA, NC, VA 2022)
m["survey_year"] = ~(m["interp"] | m["psm"])

# Real 2022 dollars (CPI-U annual average)
m["deflator"] = cpi.loc[2022] / m["year"].map(cpi)
m["price"] = m["MCPRESCHOOL"] * m["deflator"]                         # $/week, real
m["wage_k"] = m["wage_annual"] * m["deflator"] / 1000                 # $000s/year, real
m["rent_h"] = m["median_gross_rent"] * m["deflator"] / 100            # $100s/month, real
m["pci_10k"] = m["per_capita_income"] * m["deflator"] / 10000         # $10,000s, real
m["college_10"] = m["female_college_share"] * 10                      # per 10 percentage points
m["ftyr_10"] = m["female_ftyr_share"] * 10
m["careneed_pp"] = m["under6_careneed_share"] * 100                   # per 1 percentage point
m["log_pop"] = np.log(m["pop_total"].where(m["pop_total"] > 0))

m["analysis"] = m["MCPRESCHOOL"].notna() & m[list(PREDICTORS)].notna().all(axis=1)
A = m[m["analysis"]].copy()

log("=== PRE-ANALYSIS Q1. Analysis dataset (year x county, metro counties, non-missing price & predictors) ===")
cov = m.groupby("year").agg(metro_counties=("county_fips", "size"),
                            preschool_price=("MCPRESCHOOL", "count"),
                            wage=("wage_annual", "count"), rent=("median_gross_rent", "count"),
                            all_predictors=("analysis", lambda s: None),
                            analysis_rows=("analysis", "sum"))
cov["all_predictors"] = m[m[list(PREDICTORS)].notna().all(axis=1)].groupby("year").size()
cov["price_but_missing_predictor"] = cov["preschool_price"] - cov["analysis_rows"]
log(cov.to_string())
cov.to_csv(OUT / "pa_q1_sample.csv")
drop = m[m["MCPRESCHOOL"].notna() & ~m["analysis"]]
why = pd.Series({v: int(drop[v].isna().sum()) for v in PREDICTORS})
log("Rows with a price but a missing predictor, by variable:\n" + why[why > 0].to_string())
R["q1"] = {"coverage": cov.reset_index().to_dict("records"), "rows": len(A), "counties": A.county_fips.nunique(),
           "missing_by_var": why[why > 0].to_dict(),
           "drop_states_2022": drop[drop.year == 2022].groupby("state_abbr").size().to_dict()}
keep_cols = (["year", "county_fips", "NAME", "state_abbr", "oews_area", "area_title", "MCPRESCHOOL", "MCINFANT",
              "MCTODDLER"] + list(PREDICTORS) + ["wage_hourly", "childcare_emp", "zone_n", "codes", "deflator",
                                                 "price", "wage_k", "rent_h"])
A[keep_cols].to_csv(OUT / "analysis_dataset.csv", index=False)

# =====================================================================================================
# 2. PRE-ANALYSIS Q2 -- descriptive table, 2022
# =====================================================================================================
log("\n=== PRE-ANALYSIS Q2. 2022 descriptive statistics (analysis dataset) ===")
A22 = A[A.year == 2022].copy()
DESC = {"MCPRESCHOOL": "Median weekly price, center-based preschool ($)",
        "MCTODDLER": "Median weekly price, center-based toddler ($)",
        "MCINFANT": "Median weekly price, center-based infant ($)",
        "wage_annual": PREDICTORS["wage_annual"], "wage_hourly": "Childcare-worker mean hourly wage (OEWS, $)",
        **{k: v for k, v in PREDICTORS.items() if k != "wage_annual"},
        "childcare_emp": "Childcare-worker employment in the metro area (OEWS)",
        "zone_n": "Counties in the state reporting this exact price (NDCP)"}
desc = pd.DataFrame({lab: {"Mean": A22[v].mean(), "SD": A22[v].std(), "N": int(A22[v].notna().sum()),
                           "Min": A22[v].min(), "Median": A22[v].median(), "Max": A22[v].max()}
                     for v, lab in DESC.items()}).T
log(desc.round(3).to_string())
desc.to_csv(OUT / "pa_q2_descriptives_2022.csv")
R["q2"] = {"table": {k: desc.loc[v].to_dict() for k, v in DESC.items()}, "labels": DESC, "n": len(A22),
           "n_areas": A22.oews_area.nunique(), "n_states": A22.state_abbr.nunique()}

# =====================================================================================================
# 3. PRE-ANALYSIS Q3 -- scatter plots with fitted lines, 2022
# =====================================================================================================
log("\n=== PRE-ANALYSIS Q3. Price vs wages and rents, 2022 ===")
sc = {}
fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
for ax, (x, xl) in zip(axes, [("wage_k", "Childcare-worker mean annual wage, 2022 ($000s)"),
                              ("rent_h", "Median gross rent, 2022 ($100s per month)")]):
    r = smf.ols(f"MCPRESCHOOL ~ {x}", A22).fit()
    sc[x] = {"b": r.params[x], "a": r.params["Intercept"], "r2": r.rsquared, "corr": A22[[x, "MCPRESCHOOL"]].corr().iloc[0, 1],
             "n": int(r.nobs)}
    ax.scatter(A22[x], A22["MCPRESCHOOL"], s=12, color=MID, alpha=0.45, edgecolor="none")
    xs = np.linspace(A22[x].min(), A22[x].max(), 50)
    ax.plot(xs, r.params["Intercept"] + r.params[x] * xs, color=YALE, lw=2.2)
    unit = r"\$1,000/yr wage" if x == "wage_k" else r"\$100/month rent"
    ax.text(0.03, 0.96, f"Fitted: price = {r.params['Intercept']:.1f} + {r.params[x]:.2f} × x\n"
                        f"+{unit} → +\\${r.params[x]:.2f}/week\nR² = {r.rsquared:.3f}   N = {int(r.nobs):,}",
            transform=ax.transAxes, va="top", fontsize=9, color=GREY,
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=LGREY))
    ax.set_xlabel(xl)
    ax.set_ylabel("Median weekly preschool price, center-based ($)")
    style(ax)
    log(f"{x}: {sc[x]}")
axes[0].set_title("Preschool price vs childcare-worker wage")
axes[1].set_title("Preschool price vs median gross rent")
fig.suptitle("Metro counties, 2022 (NDCP prices, OEWS wages, ACS 5-year rents) with OLS fitted lines",
             fontsize=11, color=GREY)
fig.tight_layout()
fig.savefig(OUT / "pa_q3_scatter_price_costs.png", dpi=170)
plt.close(fig)
R["q3"] = sc

# =====================================================================================================
# 4. PRE-ANALYSIS Q4 -- univariate vs multivariate regressions, 2022
# =====================================================================================================
log("\n=== PRE-ANALYSIS Q4. OLS of preschool price on wages and rents, 2022 ===")
groups = pd.factorize(A22["oews_area"])[0]
specs = {"a": "MCPRESCHOOL ~ wage_k", "b": "MCPRESCHOOL ~ rent_h", "c": "MCPRESCHOOL ~ wage_k + rent_h"}
q4 = {}
for k, f in specs.items():
    ols = smf.ols(f, A22).fit()
    clu = smf.ols(f, A22).fit(cov_type="cluster", cov_kwds={"groups": groups})
    hc1 = smf.ols(f, A22).fit(cov_type="HC1")
    q4[k] = {"formula": f, "n": int(ols.nobs), "r2": ols.rsquared, "adj_r2": ols.rsquared_adj,
             "coef": ols.params.to_dict(), "se": ols.bse.to_dict(), "t": ols.tvalues.to_dict(),
             "p": ols.pvalues.to_dict(), "ci": {c: list(ols.conf_int().loc[c]) for c in ols.params.index},
             "se_cluster": clu.bse.to_dict(), "t_cluster": clu.tvalues.to_dict(), "p_cluster": clu.pvalues.to_dict(),
             "se_hc1": hc1.bse.to_dict(), "rmse": np.sqrt(ols.mse_resid)}
    log(f"({k}) {f}\n{ols.summary().tables[1]}\nR2={ols.rsquared:.4f}; cluster(OEWS area) SE={clu.bse.round(3).to_dict()}")
# Omitted-variable-bias decomposition (exact in sample): b_uni = b_multi + b_other * delta
d_rw = smf.ols("rent_h ~ wage_k", A22).fit().params["wage_k"]      # rent on wage
d_wr = smf.ols("wage_k ~ rent_h", A22).fit().params["rent_h"]      # wage on rent
bw, br = q4["c"]["coef"]["wage_k"], q4["c"]["coef"]["rent_h"]
q4["ovb"] = {"corr_wage_rent": A22[["wage_k", "rent_h"]].corr().iloc[0, 1], "delta_rent_on_wage": d_rw,
             "delta_wage_on_rent": d_wr, "wage_uni_check": bw + br * d_rw, "rent_uni_check": br + bw * d_wr,
             "vif": 1 / (1 - A22[["wage_k", "rent_h"]].corr().iloc[0, 1] ** 2),
             "sd_wage_k": A22.wage_k.std(), "sd_rent_h": A22.rent_h.std(), "sd_price": A22.MCPRESCHOOL.std()}
log(f"OVB: {q4['ovb']}")
# Mechanical labor-cost pass-through benchmark: $1,000/yr extra pay per worker spread over the children one worker
# supervises. Preschool staff:child ratios are typically ~1:10 (state rules range roughly 1:7 to 1:15).
q4["passthrough_per_child_week"] = {r: 1000 / 52 / r for r in (7, 10, 15)}
R["q4"] = q4

# =====================================================================================================
# 5. FINAL PROJECT -- cost-based price model and the "price premium"
# =====================================================================================================
log("\n=== FINAL. Year-by-year cost model: real price ~ real wage + real rent ===")
COST = "price ~ wage_k + rent_h"
yr_models, parts = {}, []
for y, g in A.groupby("year"):
    r = smf.ols(COST, g).fit()
    rl = smf.ols("np.log(price) ~ np.log(wage_k) + np.log(rent_h)", g).fit()
    yr_models[y] = {"n": int(r.nobs), "a": r.params["Intercept"], "b_wage": r.params["wage_k"],
                    "b_rent": r.params["rent_h"], "r2": r.rsquared, "rmse": np.sqrt(r.mse_resid)}
    parts.append(g.assign(pred=r.fittedvalues, prem=r.resid, prem_pct=100 * (np.exp(rl.resid) - 1)))
    log(f"{y}: {yr_models[y]}")
A = pd.concat(parts)
A["prem_share"] = A["prem"] / A["pred"]
R["yr_models"] = yr_models

# State fixed-effect version (premium relative to other counties in the same state), 2022 -- robustness
A22 = A[A.year == 2022].copy()
fe = smf.ols(COST + " + C(state_abbr)", A22).fit()
A22["prem_fe"] = fe.resid
R["state_fe"] = {"r2": fe.rsquared, "b_wage": fe.params["wage_k"], "b_rent": fe.params["rent_h"],
                 "r2_nofe": yr_models[2022]["r2"]}
# Share of premium variance that is between states
st_mean = A22.groupby("state_abbr")["prem"].transform("mean")
R["prem_between_state_share"] = st_mean.var() / A22["prem"].var()


# ---------- Model reliability: grouped (by metro area) 5-fold cross-validation, 2022 ----------
def grouped_cv(df, formula, k=5, seed=SEED, logy=False):
    areas = df["oews_area"].unique()
    rng = np.random.default_rng(seed)
    fold = dict(zip(rng.permutation(areas), np.arange(len(areas)) % k))
    f = df["oews_area"].map(fold)
    pred = pd.Series(index=df.index, dtype=float)
    for i in range(k):
        tr, te = df[f != i], df[f == i]
        r = smf.ols(formula, tr).fit()
        p = r.predict(te)
        pred.loc[te.index] = np.exp(p) * np.exp(r.mse_resid / 2) if logy else p
    y = df["price"]
    return {"r2_oos": 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum(),
            "rmse_oos": np.sqrt(((y - pred) ** 2).mean()), "mae_oos": (y - pred).abs().mean()}


DEMAND = "pci_10k + college_10 + ftyr_10 + careneed_pp + log_pop"
cv_specs = {"Mean only": ("price ~ 1", False), "Wage only": ("price ~ wage_k", False),
            "Rent only": ("price ~ rent_h", False), "Wage + rent (cost model)": (COST, False),
            "Log wage + log rent": ("np.log(price) ~ np.log(wage_k) + np.log(rent_h)", True),
            "Cost model + demand characteristics": (COST + " + " + DEMAND, False)}
cv = {}
for name, (f, lg) in cv_specs.items():
    ins = smf.ols(f, A22).fit()
    cv[name] = grouped_cv(A22, f, logy=lg) | {"r2_in": ins.rsquared, "k_params": len(ins.params)}
log("\nGrouped 5-fold CV by OEWS area, 2022:\n" + pd.DataFrame(cv).T.round(3).to_string())
R["cv"] = cv

# ---------- (c) Market characteristics that predict the premium ----------
log("\n=== FINAL (c). What predicts a positive premium? 2022, SE clustered by OEWS area ===")
g22 = pd.factorize(A22["oews_area"])[0]
pc = smf.ols("prem ~ " + DEMAND, A22).fit(cov_type="cluster", cov_kwds={"groups": g22})
log(pc.summary().tables[1])
Z = A22.copy()
zvars = ["pci_10k", "college_10", "ftyr_10", "careneed_pp", "log_pop"]
for v in zvars:
    Z[v] = (Z[v] - Z[v].mean()) / Z[v].std()
pcz = smf.ols("prem ~ " + DEMAND, Z).fit(cov_type="cluster", cov_kwds={"groups": g22})
R["chars"] = {"coef": pc.params.to_dict(), "se": pc.bse.to_dict(), "p": pc.pvalues.to_dict(), "r2": pc.rsquared,
              "n": int(pc.nobs), "std_coef": pcz.params.to_dict(), "std_se": pcz.bse.to_dict(),
              "std_p": pcz.pvalues.to_dict(),
              "bivariate_corr": {v: A22[["prem", v]].corr().iloc[0, 1] for v in zvars}}
# Same regression with state fixed effects (within-state) -- do the signs survive?
pcfe = smf.ols("prem ~ " + DEMAND + " + C(state_abbr)", Z).fit(cov_type="cluster", cov_kwds={"groups": g22})
R["chars"]["std_coef_fe"] = {v: pcfe.params[v] for v in zvars}
R["chars"]["std_p_fe"] = {v: pcfe.pvalues[v] for v in zvars}
log(f"standardized: {pd.Series(R['chars']['std_coef']).round(2).to_dict()}; within-state: "
    f"{pd.Series(R['chars']['std_coef_fe']).round(2).to_dict()}")

# =====================================================================================================
# 6. COUNTY SCORES AND THE TOP-10
# =====================================================================================================
W = A.pivot_table(index="county_fips", columns="year", values="prem")
Wp = A.pivot_table(index="county_fips", columns="year", values="prem_pct")
info22 = A22.set_index("county_fips")


def score_window(years, ref_year):
    w = W.reindex(columns=years)
    s = pd.DataFrame({"score": w.mean(axis=1), "n_years": w.notna().sum(axis=1),
                      "n_pos": (w > 0).sum(axis=1), "has_ref": w[ref_year].notna()})
    s["score_pct"] = Wp.reindex(columns=years).mean(axis=1)
    return s


def pick(s, ref, n=10):
    """Eligibility rules, then one county per metro area, ranked by average premium."""
    e = s.join(ref, how="inner")
    e["elig_years"] = e["has_ref"] & (e["n_years"] >= 3)
    e["elig_stable"] = e["n_pos"] == e["n_years"]
    e["elig_local_price"] = (e["zone_n"] <= MAX_ZONE) & ~e["state_level"] & ~e["psm"]
    e["elig_size"] = e["kids_under6_allpar_lf"] >= MIN_KIDS
    e["eligible"] = e[["elig_years", "elig_stable", "elig_local_price", "elig_size"]].all(axis=1)
    ranked = e[e.eligible].sort_values("score", ascending=False)
    ranked["metro_rank"] = ranked.groupby("area_title").cumcount() + 1
    top = ranked[ranked.metro_rank == 1].head(n)
    return e, ranked, top


ref_cols = ["NAME", "state_abbr", "area_title", "oews_area", "MCPRESCHOOL", "pred", "prem", "prem_pct", "zone_n",
            "codes", "state_level", "psm", "interp", "kids_under6_allpar_lf", "pop_total", "wage_annual",
            "median_gross_rent", "per_capita_income", "female_college_share", "female_ftyr_share",
            "under6_careneed_share", "prem_fe"]
S = score_window(RECENT, 2022)
E, ranked, TOP = pick(S, info22[ref_cols])
E.to_csv(OUT / "county_scores_2019_2022.csv")
TOP = TOP.copy()
TOP["rank"] = np.arange(1, len(TOP) + 1)
TOP["prem_fe_rank_in_state"] = [
    int((A22[A22.state_abbr == r.state_abbr]["prem_fe"] > r.prem_fe).sum() + 1) for r in TOP.itertuples()]
TOP["n_in_state"] = [int((A22.state_abbr == r.state_abbr).sum()) for r in TOP.itertuples()]
TOP["prem_share_pct"] = 100 * TOP["prem"] / TOP["pred"]   # dollar premium as % of the predicted price
TOP.to_csv(OUT / "top10_recommended.csv")
# Price evidence behind each pick: NDCP imputation codes, the latest survey year (no between-survey or PSM estimate,
# codes 5/6) and the latest year with no imputation flag at all (codes 3-6), with the premium in each
EVID = []
for f in TOP.index:
    g = A[A.county_fips == f].set_index("year").sort_index()
    sv = g[~g["codes"].str.contains("5|6")]
    dr = g[~g["codes"].str.contains("3|4|5|6")]
    EVID.append({"county_fips": f, "codes_2022": g.loc[2022, "codes"],
                 "est_2022": bool(g.loc[2022, "interp"] or g.loc[2022, "psm"]),
                 "pctile_imputed_2022": "4" in g.loc[2022, "codes"],
                 "survey_year": int(sv.index.max()) if len(sv) else None,
                 "survey_prem": float(sv["prem"].iloc[-1]) if len(sv) else None,
                 "survey_codes": str(sv["codes"].iloc[-1]) if len(sv) else None,
                 "direct_year": int(dr.index.max()) if len(dr) else None,
                 "direct_prem": float(dr["prem"].iloc[-1]) if len(dr) else None,
                 "direct_codes": str(dr["codes"].iloc[-1]) if len(dr) else None})
R["evidence"] = EVID
log("Price evidence behind the picks:\n" + pd.DataFrame(EVID).round(1).to_string())
log("\n=== FINAL (a). TOP-10 (avg real premium 2019-2022, eligibility rules, one county per metro) ===")
log(TOP[["rank", "NAME", "area_title", "score", "n_years", "MCPRESCHOOL", "pred", "prem", "prem_pct", "prem_fe",
         "zone_n", "codes", "kids_under6_allpar_lf"]].round(1).to_string())
funnel = {"scored_2022": int(S.has_ref.sum()),
          "years_ok": int(E.elig_years.sum()),
          "years_stable": int((E.elig_years & E.elig_stable).sum()),
          "local_price": int((E.elig_years & E.elig_stable & E.elig_local_price).sum()),
          "size": int(E.eligible.sum()), "metros": int(ranked.area_title.nunique())}
log(f"Funnel: {funnel}")
NEXT = ranked[ranked.metro_rank == 1].iloc[10:20]
# High-premium counties that failed only the local-price rule (zone/state-level/PSM priced): verify locally
WATCH = (E[E.elig_years & E.elig_stable & E.elig_size & ~E.elig_local_price]
         .sort_values("score", ascending=False))
WATCH = WATCH[WATCH.groupby("area_title").cumcount() == 0].head(10)
log("Next 10:\n" + NEXT[["NAME", "area_title", "score"]].round(1).to_string())
log("Watch list (premium, but price not locally measured):\n" +
    WATCH[["NAME", "area_title", "score", "zone_n", "codes"]].round(1).to_string())
R["top10"] = clean(TOP.reset_index().to_dict("records"))
R["next10"] = clean(NEXT.reset_index()[["county_fips", "NAME", "area_title", "score", "MCPRESCHOOL", "pred"]]
                    .to_dict("records"))
R["watch"] = clean(WATCH.reset_index()[["county_fips", "NAME", "area_title", "score", "zone_n", "codes", "MCPRESCHOOL"]]
                   .to_dict("records"))
R["funnel"] = funnel
R["rules"] = {"recent": RECENT, "min_kids": MIN_KIDS, "max_zone": MAX_ZONE}

# Profile: recommended vs all metro counties (2022)
prof_vars = {"MCPRESCHOOL": "Weekly preschool price ($)", "pred": "Predicted price ($)",
             "prem": "Premium over predicted price ($/wk)", "wage_annual": "Childcare-worker wage ($/yr)",
             "median_gross_rent": "Median gross rent ($/mo)", "per_capita_income": "Per-capita income ($)",
             "female_college_share": "Women 25+ w/ bachelor's+", "female_ftyr_share": "Women full-time year-round",
             "under6_careneed_share": "Under-6 needing care (% pop)", "kids_under6_allpar_lf": "Under-6 needing care (#)"}
prof = pd.DataFrame({"Top 10 (mean)": TOP[list(prof_vars)].mean(), "All metro counties (mean)": A22[list(prof_vars)].mean(),
                     "All metro (median)": A22[list(prof_vars)].median()})
prof.index = [prof_vars[i] for i in prof.index]
prof.to_csv(OUT / "top10_profile.csv")
R["profile"] = prof.to_dict("index")

# =====================================================================================================
# 7. ROBUSTNESS OF THE TOP-10 (alternative definitions)
# =====================================================================================================
def topset(s):
    return set(pick(s, info22[ref_cols])[2].index)


base = set(TOP.index)
rob = {}
s_pct = S.copy(); s_pct["score"] = s_pct["score_pct"]
rob["Log model (% premium)"] = topset(s_pct)
s22 = score_window([2022], 2022); s22["n_years"] = S["n_years"]; s22["n_pos"] = S["n_pos"]
rob["2022 premium only"] = topset(s22)
# survey years only (drop interpolated / PSM years)
Ws = A[A.survey_year].pivot_table(index="county_fips", columns="year", values="prem").reindex(columns=RECENT)
s_sv = S.copy(); s_sv["score"] = Ws.mean(axis=1)
rob["Survey years only"] = topset(s_sv.dropna(subset=["score"]))
# state fixed effects (within-state premium, 2022)
s_fe = S.copy(); s_fe["score"] = info22["prem_fe"]
rob["Within-state premium (state FE)"] = topset(s_fe)
rob_tab = {k: {"overlap": len(base & v), "of": len(v)} for k, v in rob.items()}
rob_tab["Top-10 still above within-state prediction"] = {"overlap": int((TOP.prem_fe > 0).sum()), "of": len(TOP)}
log(f"\nRobustness overlaps with baseline top-10: {rob_tab}")
R["robust"] = rob_tab
R["robust_sets"] = {k: sorted(v) for k, v in rob.items()}

# =====================================================================================================
# 8. RELIABILITY: BACK-TEST (pretend it is 2018) AND (d) STABILITY OF PREMIUMS
# =====================================================================================================
log("\n=== FINAL (b). Back-test: choose with 2015-2018 data, evaluate on 2022 ===")
info18 = A[A.year == 2018].set_index("county_fips")
info18["prem_fe"] = np.nan
S18 = score_window(FORMATION, 2018)
_, ranked18, TOP18 = pick(S18, info18[ref_cols])
w22 = W[2022]
bt = {"n_picked": len(TOP18), "n_with_2022": int(w22.reindex(TOP18.index).notna().sum()),
      "picks_prem_2022_mean": w22.reindex(TOP18.index).mean(),
      "picks_prem_2019_22_mean": W.reindex(TOP18.index)[RECENT].mean(axis=1).mean(),
      "picks_share_pos_2022": (w22.reindex(TOP18.index).dropna() > 0).mean(),
      "picks_formation_score": TOP18.score.mean(),
      "all_counties_prem_2022_mean": w22.mean(),
      "eligible_pool_prem_2022_mean": w22.reindex(ranked18.index).mean(),
      "picks": clean(TOP18.reset_index()[["county_fips", "NAME", "area_title", "score"]]
                     .assign(prem2022=lambda d: d.county_fips.map(w22)).to_dict("records")),
      "overlap_with_2022_top10": len(set(TOP18.index) & base)}
# decile analysis on all counties with formation score and 2022 premium
dec = pd.DataFrame({"f": S18.score, "p22": w22}).dropna()
dec["decile"] = pd.qcut(dec.f, 10, labels=False) + 1
bt["deciles"] = dec.groupby("decile").agg(formation=("f", "mean"), prem2022=("p22", "mean"), n=("p22", "size")).reset_index().to_dict("records")
bt["corr_formation_2022"] = dec[["f", "p22"]].corr().iloc[0, 1]
bt["slope_2022_on_formation"] = smf.ols("p22 ~ f", dec).fit().params["f"]
bt["spearman"] = stats.spearmanr(dec.f, dec.p22).statistic
log({k: v for k, v in bt.items() if k not in ("picks", "deciles")})
log("Back-test picks:\n" + pd.DataFrame(bt["picks"]).round(1).to_string())
R["backtest"] = bt

log("\n=== FINAL (d). Stability of county premiums ===")
corr = W.corr()
lag = []
Wsv = A[A.survey_year].pivot_table(index="county_fips", columns="year", values="prem")
for k in range(1, 8):
    xs, ys, xs2, ys2 = [], [], [], []
    for y in YEARS:
        if y + k in W.columns and y in W.columns:
            pr = W[[y, y + k]].dropna(); xs += list(pr[y]); ys += list(pr[y + k])
        if y in Wsv.columns and y + k in Wsv.columns:
            pr = Wsv[[y, y + k]].dropna(); xs2 += list(pr[y]); ys2 += list(pr[y + k])
    lag.append({"lag": k, "corr_all": np.corrcoef(xs, ys)[0, 1], "n_all": len(xs),
                "corr_survey": np.corrcoef(xs2, ys2)[0, 1] if len(xs2) > 30 else np.nan, "n_survey": len(xs2)})
lag = pd.DataFrame(lag)
log(lag.round(3).to_string())
# Quintile persistence: top quintile in 2015-2018 average -> share still top quintile in 2019-2022 average
q = pd.DataFrame({"early": W[FORMATION].mean(axis=1), "late": W[RECENT].mean(axis=1)}).dropna()
q["qe"] = pd.qcut(q.early, 5, labels=False); q["ql"] = pd.qcut(q.late, 5, labels=False)
trans = pd.crosstab(q.qe, q.ql, normalize="index")
stab = {"corr_matrix": corr.round(3).to_dict(), "lag": lag.to_dict("records"),
        "top_q_stay": trans.loc[4, 4], "top_q_top2": trans.loc[4, [3, 4]].sum(), "bottom_q_stay": trans.loc[0, 0],
        "n_q": len(q), "corr_early_late": q[["early", "late"]].corr().iloc[0, 1],
        "top10_paths": {f: W.loc[f].to_dict() for f in TOP.index},
        "top10_min_prem_by_year": W.loc[TOP.index].min().to_dict(),
        "share_counties_sign_same_2019_2022": ((W[2019] > 0) == (W[2022] > 0))[W[[2019, 2022]].notna().all(axis=1)].mean()}
log(f"Top-quintile persistence: {stab['top_q_stay']:.2f} stay top quintile; {stab['top_q_top2']:.2f} stay top two")
log(f"corr(2015-18 avg, 2019-22 avg) = {stab['corr_early_late']:.3f}")
R["stability"] = stab
R["transition"] = trans.round(3).to_dict()

# =====================================================================================================
# 9. FIGURES FOR THE DECK
# =====================================================================================================
SHORT = {f: r.NAME.replace(" County", "").replace(" Municipality", "").split(",")[0] + ", " + r.state_abbr
         for f, r in TOP.iterrows()}

# (1) Dumbbell: predicted vs actual 2022 price for the top-10
fig, ax = plt.subplots(figsize=(7.6, 4.6))
t = TOP.iloc[::-1]
yy = np.arange(len(t))
ax.hlines(yy, t.pred, t.MCPRESCHOOL, color=PALE, lw=6, zorder=1)
ax.scatter(t.pred, yy, s=70, color="white", edgecolor=MID, lw=2, zorder=2, label="Predicted price (from local wages + rent)")
ax.scatter(t.MCPRESCHOOL, yy, s=70, color=YALE, zorder=3, label="Actual median price")
for yi, r in zip(yy, t.itertuples()):
    ax.text(r.MCPRESCHOOL + 6, yi, f"+${r.prem:.0f}", va="center", fontsize=9, color=YALE, fontweight="bold")
ax.set_yticks(yy, [f"{int(r['rank'])}. {SHORT[f]}" for f, r in t.iterrows()])
ax.set_xlabel("Median weekly price, center-based preschool, 2022 ($)")
ax.set_xlim(100, max(t.MCPRESCHOOL) + 55)
style(ax); ax.grid(axis="y", visible=False)
ax.legend(frameon=False, loc="lower right", fontsize=8.5)
fig.tight_layout(); fig.savefig(OUT / "fig_top10_dumbbell.png", dpi=200); plt.close(fig)

# (2) Map: average premium 2019-2022 for scored metro counties, top-10 marked
def read_shapes(zipname):
    z = zipfile.ZipFile(RAW / zipname)
    base = [n[:-4] for n in z.namelist() if n.endswith(".shp")][0]
    import shapefile
    rdr = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")),
                           shx=io.BytesIO(z.read(base + ".shx")))
    return rdr


def polys(shape):
    pts, parts = shape.points, list(shape.parts) + [len(shape.points)]
    return [np.array(pts[parts[i]:parts[i + 1]]) for i in range(len(parts) - 1)]


try:
    cty, sts = read_shapes("cb_2022_us_county_20m.zip"), read_shapes("cb_2022_us_state_20m.zip")
    skip = {"02", "15", "72", "60", "66", "69", "78"}
    avg = S.score
    fig, ax = plt.subplots(figsize=(11, 6.4))
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("yb", ["#F1F6FC", PALE, LIGHT, MID, YALE])
    norm = matplotlib.colors.Normalize(0, 100)
    patches_none, patches_neg, patches_pos, cols = [], [], [], []
    cent = {}
    for sr, shp in zip(cty.records(), cty.shapes()):
        st, fips = sr["STATEFP"], sr["GEOID"]
        if st in skip:
            continue
        ps = polys(shp)
        cent[fips] = np.vstack(ps).mean(axis=0) if ps else None
        v = avg.get(fips, np.nan)
        for p in ps:
            if np.isnan(v):
                patches_none.append(Polygon(p))
            elif v <= 0:
                patches_neg.append(Polygon(p))
            else:
                patches_pos.append(Polygon(p)); cols.append(v)
    ax.add_collection(PatchCollection(patches_none, facecolor="#F7F7F7", edgecolor="none"))
    ax.add_collection(PatchCollection(patches_neg, facecolor="#D9D9D9", edgecolor="white", lw=0.2))
    pc_ = PatchCollection(patches_pos, cmap=cmap, norm=norm, edgecolor="white", lw=0.2)
    pc_.set_array(np.array(cols)); ax.add_collection(pc_)
    for sr, shp in zip(sts.records(), sts.shapes()):
        if sr["STATEFP"] in skip:
            continue
        for p in polys(shp):
            ax.plot(p[:, 0], p[:, 1], color="#9A9A9A", lw=0.5)
    placed = []
    for f, r in TOP.iterrows():
        if f in cent and cent[f] is not None:
            x0, y0 = cent[f]
            x, y = x0, y0
            # nudge markers that would sit on top of an earlier one (e.g. Howard & Montgomery, MD) with a leader line
            while any(np.hypot(x - a, y - b) < 1.1 for a, b in placed):
                x, y = x + 0.9, y - 1.0
            if (x, y) != (x0, y0):
                ax.plot([x0, x], [y0, y], color=YALE, lw=0.8, zorder=4)
                ax.scatter(x0, y0, s=12, color=YALE, zorder=5)
            placed.append((x, y))
            ax.scatter(x, y, s=170, color=YALE, edgecolor="white", lw=1.5, zorder=5)
            ax.text(x, y, str(int(r["rank"])), color="white", fontsize=7.5, fontweight="bold", ha="center",
                    va="center", zorder=6)
    ax.set_xlim(-125, -66.5); ax.set_ylim(24.3, 49.6); ax.set_aspect(1.25); ax.axis("off")
    cb = fig.colorbar(pc_, ax=ax, fraction=0.025, pad=0.01, shrink=0.7)
    cb.set_label("Avg. premium over predicted price, 2019-22 ($/week)", color=GREY)
    cb.outline.set_visible(False)
    ax.text(-124.5, 25.2, "Grey = price at or below the wage-and-rent prediction    Light = no price data / not metro",
            fontsize=8.5, color=GREY)
    fig.tight_layout(); fig.savefig(OUT / "fig_map_premium.png", dpi=200, bbox_inches="tight", pad_inches=0.05); plt.close(fig)
    R["map"] = True
except Exception as e:  # map is illustrative only
    log(f"Map skipped: {e}")
    R["map"] = False

# (3) Methodology: actual vs cost-predicted, 2022, top-10 highlighted
fig, ax = plt.subplots(figsize=(6.4, 5.0))
ax.scatter(A22.pred, A22.MCPRESCHOOL, s=11, color=LIGHT, alpha=0.5, edgecolor="none", label="Metro county, 2022")
ax.scatter(TOP.pred, TOP.MCPRESCHOOL, s=48, color=YALE, edgecolor="white", lw=0.8, zorder=3, label="Recommended")
lim = [80, 520]
ax.plot(lim, lim, color=GREY, lw=1, ls="--")
ax.text(512, 105, "dashed line: actual price = predicted price", fontsize=8, color=GREY, ha="right", va="bottom")
ax.set_xlim(lim); ax.set_ylim(lim)
m22 = yr_models[2022]
icpt = f"{m22['a']:.0f}".replace("-", "−")  # typographic minus on the intercept only
ax.set_xlabel(rf"Predicted weekly price (\$) = {icpt} + {m22['b_wage']:.1f}×wage(\$000) + "
              rf"{m22['b_rent']:.1f}×rent(\$100)")
ax.set_ylabel("Actual median weekly preschool price ($)")
ax.legend(frameon=False, loc="upper left", fontsize=8.5)
style(ax)
fig.tight_layout(); fig.savefig(OUT / "fig_actual_vs_predicted.png", dpi=200); plt.close(fig)

# (4) Back-test deciles
dd = pd.DataFrame(bt["deciles"])
fig, ax = plt.subplots(figsize=(6.4, 4.2))
ax.bar(dd.decile, dd.prem2022, color=[YALE if v > 0 else "#BDBDBD" for v in dd.prem2022], width=0.7)
ax.axhline(0, color=GREY, lw=0.8)
for x, v in zip(dd.decile, dd.prem2022):
    ax.text(x, v + (3 if v >= 0 else -3), f"{v:+.0f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=8.5,
            color=GREY)
ax.set_xticks(dd.decile)
ax.set_ylim(dd.prem2022.min() - 12, dd.prem2022.max() + 10)
ax.set_xlabel("Decile of county premium measured in 2015-2018 (1 = lowest, 10 = highest)")
ax.set_ylabel("Average premium in 2022 ($/week)")
style(ax); ax.grid(axis="x", visible=False)
fig.tight_layout(); fig.savefig(OUT / "fig_backtest_deciles.png", dpi=200); plt.close(fig)

# (5) Characteristics: standardized coefficients
lab = {"pci_10k": "Per-capita income", "college_10": "Women with bachelor's+", "ftyr_10": "Women working full-time",
       "careneed_pp": "Under-6 kids needing care (share)", "log_pop": "Population (log)"}
cz = pd.DataFrame({"b": R["chars"]["std_coef"], "se": R["chars"]["std_se"], "p": R["chars"]["std_p"]}).loc[zvars]
cz = cz.sort_values("b")
fig, ax = plt.subplots(figsize=(6.4, 3.8))
yy = np.arange(len(cz))
ax.barh(yy, cz.b, xerr=1.96 * cz.se, color=[YALE if (p < .05 and b > 0) else (LIGHT if p < .05 else LGREY)
                                             for b, p in zip(cz.b, cz.p)],
        error_kw=dict(ecolor=GREY, lw=1, capsize=3), height=0.6)
ax.axvline(0, color=GREY, lw=0.8)
ax.set_yticks(yy, [lab[v] for v in cz.index])
ax.set_xlabel("Change in premium ($/week) per 1-SD increase, 95% CI")
style(ax); ax.grid(axis="y", visible=False)
fig.tight_layout(); fig.savefig(OUT / "fig_characteristics.png", dpi=200); plt.close(fig)

# (6) Stability: correlation by lag (all vs survey years) + top-10 paths
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1, 1.2]})
ax = axes[0]
ax.plot(lag.lag, lag.corr_all, marker="o", color=YALE, lw=2, label="All county-years")
ax.plot(lag.lag, lag.corr_survey, marker="s", color=LIGHT, lw=2, ls="--", label="Survey years only (no interpolation)")
for x, v, v2 in zip(lag.lag, lag.corr_all, lag.corr_survey):
    above = not (v2 > v)  # put the label on the side away from the survey-years line
    ax.text(x, v + (0.03 if above else -0.065), f"{v:.2f}", ha="center", fontsize=8, color=YALE)
ax.set_ylim(0, 1.05); ax.set_xlabel("Years apart"); ax.set_ylabel("Correlation of county premiums")
ax.set_title("County premiums persist for years", fontsize=10.5)
ax.legend(frameon=False, fontsize=8.5, loc="lower left"); style(ax)
ax = axes[1]
others = W.reindex(columns=YEARS)
q10, q90 = others.quantile(0.1), others.quantile(0.9)
ax.fill_between(YEARS, q10, q90, color=PALE, alpha=0.6, label="Middle 80% of metro counties")
for f in TOP.index:
    ax.plot(YEARS, W.loc[f].reindex(YEARS), color=MID, lw=1.1, alpha=0.8)
ax.plot(YEARS, W.loc[TOP.index].reindex(columns=YEARS).mean(), color=YALE, lw=3, label="Recommended counties (average)")
ax.axhline(0, color=GREY, lw=0.8)
ax.set_xticks(YEARS); ax.set_ylabel(r"Premium over predicted price (\$/week, 2022 \$)")
ax.set_title("Recommended counties: above the predicted price every year 2019-22", fontsize=10.5)
ax.legend(frameon=False, fontsize=8.5, loc="upper left"); style(ax)
fig.tight_layout(); fig.savefig(OUT / "fig_stability.png", dpi=200); plt.close(fig)

(OUT / "results.json").write_text(json.dumps(clean(R), indent=1), encoding="utf-8")
(OUT / "results.txt").write_text("\n".join(log_lines), encoding="utf-8")
log("\nDone.")
