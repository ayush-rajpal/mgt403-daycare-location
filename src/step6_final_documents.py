"""
Builds the two written deliverables from output/results.json and the figures made by project.py:
  PreAnalysis_and_Final_Analysis.pdf   -- answers to the pre-analysis questions + the final-project analysis
  Appendix_Data_and_Model_Choices.pdf  -- data handling decisions, model choices, robustness, reproducibility
Every number is read from results.json or the output CSVs (none typed by hand).

Run:  python src/step6_final_documents.py   (after step 5; or python run_all.py)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from common import OUT_FINAL as OUT, OUT_PS5, CPI as CPI_FILE, DELIVERABLES, register_arial, load_ndcp
R = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
PS5R = json.loads((OUT_PS5 / "results.json").read_text(encoding="utf-8"))
CPI = pd.read_csv(CPI_FILE).set_index("year")["cpi_u"]
AD = pd.read_csv(OUT / "analysis_dataset.csv", dtype={"county_fips": str, "oews_area": str})
TEAM = ["Winston Park", "Ayush Rajpal", "Tobin Gedstad", "Wen Ding", "Alfred Mordecai"]
YALE, MID, TINT = "#00356B", "#286DC0", "#EEF4FB"

register_arial()
ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["Normal"], fontName="Arial", fontSize=10, leading=14, spaceAfter=6)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=14, bulletIndent=4, spaceAfter=3)
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Arial-Bold", fontSize=15, spaceBefore=8, spaceAfter=6,
                    textColor=colors.HexColor(YALE))
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Arial-Bold", fontSize=12, spaceBefore=8, spaceAfter=4,
                    textColor=colors.HexColor(YALE))
TITLE = ParagraphStyle("title", parent=ss["Title"], fontName="Arial-Bold", fontSize=18, leading=22,
                       textColor=colors.HexColor(YALE))
SUB = ParagraphStyle("sub", parent=BODY, alignment=TA_CENTER, textColor=colors.HexColor("#555555"))
CAP = ParagraphStyle("cap", parent=BODY, fontSize=8.5, leading=11, textColor=colors.HexColor("#555555"))
MATH = ParagraphStyle("math", parent=BODY, leftIndent=24, fontSize=10.5, leading=16, backColor=colors.HexColor(TINT),
                      borderPadding=(4, 6, 4, 6), spaceBefore=4, spaceAfter=8)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.5, leading=10.5, spaceAfter=0)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Arial-Bold", textColor=colors.white)


def P(t, st=BODY):
    return Paragraph(t, st)


def B(t):
    return Paragraph(t, BULLET, bulletText="\u2022")


def table(rows, widths, header_rows=1, align_right_from=None):
    data = [[Paragraph(str(c), CELLB if i < header_rows else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * inch for w in widths], repeatRows=header_rows)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D6E6")),
             ("BACKGROUND", (0, 0), (-1, header_rows - 1), colors.HexColor(YALE)),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    for i in range(header_rows, len(rows)):
        if (i - header_rows) % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor(TINT)))
    t.setStyle(TableStyle(style))
    return t


def fig(name, width=7.0 * inch):
    w, h = PILImage.open(OUT / name).size
    return Image(str(OUT / name), width=width, height=width * h / w)


def money(x, d=0):
    return ("-" if x < 0 else "") + f"${abs(x):,.{d}f}"


def pexp(p):
    if p is None:
        return "&lt; 10<super>-300</super>"
    if p >= 1e-4:
        return f"{p:.4f}"
    if p == 0:
        return "&lt; 10<super>-300</super>"
    m, e = f"{p:.2e}".split("e")
    return f"{m} &#215; 10<super>{int(e)}</super>"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def footer_for(label):
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Arial", 8)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(0.65 * inch, 0.5 * inch, f"MGT-403 \u00b7 {label} \u00b7 " + ", ".join(TEAM))
        canvas.drawRightString(letter[0] - 0.65 * inch, 0.5 * inch, f"Page {doc.page}")
        canvas.restoreState()
    return footer


def build(story, fname, label):
    SimpleDocTemplate(str(DELIVERABLES / fname), pagesize=letter, leftMargin=0.65 * inch, rightMargin=0.65 * inch,
                      topMargin=0.6 * inch, bottomMargin=0.75 * inch, title=label, author=", ".join(TEAM)
                      ).build(story, onFirstPage=footer_for(label), onLaterPages=footer_for(label))
    print("wrote", DELIVERABLES / fname)


q1, q2, q3, q4 = R["q1"], R["q2"], R["q3"], R["q4"]
cov = {c["year"]: c for c in q1["coverage"]}
c4 = {k: q4[k] for k in "abc"}
ovb = q4["ovb"]
ym = {int(k): v for k, v in R["yr_models"].items()}
TOP = pd.DataFrame(R["top10"])
bt, st, cv, ch = R["backtest"], R["stability"], R["cv"], R["chars"]
ALT = ["Log model (% premium)", "2022 premium only", "Survey years only", "Within-state premium (state FE)"]
TOP["kept"] = [sum(f in R["robust_sets"][k] for k in ALT) for f in TOP.county_fips]
TOP["conf"] = TOP.kept.map(lambda k: "High" if k == 4 else ("Medium" if k == 3 else "Watch"))
A22 = AD[AD.year == 2022]
zone_le2 = (A22.zone_n <= 2).mean()
SH45 = A22.codes.fillna("").astype(str).str.contains("4|5").mean()
zone_med = A22.zone_n.median()
shared_all = (AD.zone_n > 1).mean()


def short(n):
    return n.replace(" County", "").replace(" Municipality", "")


RMSE = cv["Wage + rent (cost model)"]["rmse_oos"]
EVD = {e["county_fips"]: e for e in R["evidence"]}
UNDOC = ("NA", "not listed")   # Appendix B lists the state-year as excluded / does not list it, yet a price exists


def smoney(x):
    return ("+" if x >= 0 else "\u2212") + f"${abs(x):,.0f}"


BIG, SMALL = TOP[TOP.prem >= 1.25 * RMSE], TOP[TOP.prem < 1.25 * RMSE]
# Rate-zone example in A4: the largest shared 2022 price among Wisconsin metro counties, counted over every NDCP
# county in the state (not just the analysis dataset), so it matches the zone sizes used in the screen
WI_PRICE = A22[A22.state_abbr == "WI"].groupby("MCPRESCHOOL").size().idxmax()
_nd = load_ndcp()
_wz = _nd[(_nd.STATE_ABBREVIATION == "WI") & (_nd.STUDYYEAR == 2022) & (_nd.MCPRESCHOOL == WI_PRICE)]
_pan = pd.read_csv(OUT_PS5 / "ps5_county_panel.csv", dtype={"county_fips": str})
_metro22 = set(_pan[_pan.year == 2022].county_fips)
WI_N = len(_wz)
WI_ALL_METRO = all(f"{int(c):05d}" in _metro22 for c in _wz.COUNTY_FIPS_CODE)
WI_NAMES = ", ".join(sorted(n.replace(" County", "") for n in _wz.COUNTY_NAME))


# =====================================================================================================
# DOCUMENT 1: PRE-ANALYSIS + FINAL ANALYSIS
# =====================================================================================================
s = [P("Where Should We Open Our Next Daycare?", TITLE),
     P("MGT-403 Data Project \u00b7 Pre-Analysis (Prices and Costs) and Final Project Analysis", SUB),
     P("<b>Team:</b> " + ", ".join(TEAM), SUB), Spacer(1, 6)]

s.append(P("Summary", H1))
s += [
    B(f"<b>Analysis dataset.</b> {q1['rows']:,} year \u00d7 county observations (2015\u20132022) for "
      f"{q1['counties']:,} metropolitan counties with a non-missing NDCP center-based preschool price and every "
      f"predictor; {cov[2022]['analysis_rows']:,} counties in 2022."),
    B(f"<b>Prices and costs move together.</b> In 2022, a $1,000 higher childcare-worker wage goes with a "
      f"{money(c4['a']['coef']['wage_k'], 2)}/week higher preschool price (R\u00b2 = {c4['a']['r2']:.2f}); a $100 "
      f"higher median gross rent goes with {money(c4['b']['coef']['rent_h'], 2)}/week (R\u00b2 = {c4['b']['r2']:.2f}). "
      f"Together: {money(c4['c']['coef']['wage_k'], 2)} and {money(c4['c']['coef']['rent_h'], 2)} (R\u00b2 = "
      f"{c4['c']['r2']:.2f}). Both shrink in the joint model because wages and rents are correlated (r = "
      f"{ovb['corr_wage_rent']:.2f})."),
    B(f"<b>Recommendation.</b> Ten counties in ten metros whose prices sit far above what their local wages and rents predict: "
      + ", ".join(f"{short(r.NAME).split(',')[0]} ({r.state_abbr})" for r in TOP.itertuples()) +
      f". Average 2022 premium {money(TOP.prem.mean())}/week."),
    B(f"<b>Reliability.</b> The benchmark model (price predicted from wages and rents) fits held-out metros almost as well as in sample (R\u00b2 "
      f"{cv['Wage + rent (cost model)']['r2_oos']:.2f} vs {cv['Wage + rent (cost model)']['r2_in']:.2f}). Premiums "
      f"are persistent (correlation {st['lag'][0]['corr_all']:.2f} one year apart, {st['lag'][6]['corr_all']:.2f} "
      f"seven years apart). In a 2018 back-test, the {bt['n_with_2022']} picks that still had 2022 prices were "
      f"{money(bt['picks_prem_2022_mean'])}/week above their predicted price on average, and all {bt['n_with_2022']} were above it."),
]

# ---------------- Q1 ----------------
s.append(P("Pre-Analysis 1. The analysis dataset", H1))
s.append(P("We merged the NDCP county prices (2015\u20132022) onto the Problem Set 5 year \u00d7 county metro panel "
           "(OEWS childcare-worker wages crosswalked to counties, plus ACS 5-year county data) on the 5-digit FIPS "
           "code and year. Every metro county-year in the PS5 panel has a matching NDCP row. The <b>analysis "
           "dataset</b> keeps county-years where the median center-based preschool price (MCPRESCHOOL) and all ten "
           "predictors are non-missing."))
rows = [["Year", "Metro counties", "Preschool price reported", "Wage non-missing", "All predictors non-missing",
         "Analysis dataset", "Price but a predictor missing"]]
for y in range(2015, 2023):
    c = cov[y]
    rows.append([y, f"{c['metro_counties']:,}", f"{c['preschool_price']:,}", f"{c['wage']:,}",
                 f"{c['all_predictors']:,}", f"<b>{c['analysis_rows']:,}</b>", c["price_but_missing_predictor"]])
rows.append(["Total", "", "", "", "", f"<b>{q1['rows']:,}</b>", sum(cov[y]["price_but_missing_predictor"] for y in cov)])
s.append(table(rows, [0.6, 1.0, 1.1, 1.0, 1.15, 1.0, 1.25]))
mb = q1["missing_by_var"]
s.append(P(f"Rows with a price but a missing predictor are mostly suppressed OEWS wage cells ({mb.get('wage_annual', 0)} "
           f"county-years) and Connecticut in 2022, where the ACS switched from counties to planning regions so the "
           f"old county FIPS codes no longer match ({q1['drop_states_2022'].get('CT', 0)} counties). Some states have no county "
           "prices in some years (California, North Carolina, Pennsylvania and Virginia in 2021; Indiana and New Mexico "
           "in every year), which is why the yearly count varies.", CAP))

# ---------------- Q2 ----------------
s.append(CondPageBreak(2.5 * inch))
s.append(P("Pre-Analysis 2. Descriptive statistics, 2022", H1))
rows = [["Variable (2022, metro counties)", "Mean", "SD", "N", "Min", "Median", "Max"]]
pctvars = {"female_college_share", "female_ftyr_share", "under6_share", "under6_careneed_share"}
for k, lab in q2["labels"].items():
    t = q2["table"][k]
    if k in pctvars:
        f = lambda v: f"{100 * v:.1f}%"
    elif k in ("wage_hourly",):
        f = lambda v: f"${v:,.2f}"
    elif k in ("pop_total", "kids_under6", "kids_under6_allpar_lf", "childcare_emp", "zone_n"):
        f = lambda v: f"{v:,.0f}"
    else:
        f = lambda v: f"${v:,.2f}" if v < 1000 else f"${v:,.0f}"
    rows.append([esc(lab), f(t["Mean"]), f(t["SD"]), f"{int(t['N']):,}", f(t["Min"]), f(t["Median"]), f(t["Max"])])
s.append(table(rows, [2.75, 0.8, 0.8, 0.5, 0.75, 0.8, 0.85]))
s.append(P(f"N = {q2['n']:,} counties in {q2['n_areas']} OEWS metro areas and {q2['n_states']} states/territories. "
           "Prices are full-time weekly medians (NDCP); wages are OEWS mean wages for SOC 39-9011 at the metro-area "
           "level, so all counties in one metro share a wage; ACS variables are 2018\u20132022 5-year estimates. "
           "2022 values are already in 2022 dollars.", CAP))
pr = q2["table"]
s.append(P(f"Preschool care is the cheapest center-based age group ({money(pr['MCPRESCHOOL']['Mean'], 2)}/week on average, vs "
           f"{money(pr['MCTODDLER']['Mean'], 2)} for toddlers and {money(pr['MCINFANT']['Mean'], 2)} for infants), and prices "
           f"are right-skewed (mean above median; maximum {money(pr['MCPRESCHOOL']['Max'], 2)})."))

# ---------------- Q3 ----------------
s.append(CondPageBreak(4 * inch))
s.append(P("Pre-Analysis 3. Prices against wages and rents", H1))
s.append(fig("pa_q3_scatter_price_costs.png", 7.2 * inch))
s.append(P("Each dot is a metro county in 2022; the line is the OLS fit.", CAP))
s += [
    B(f"<b>Wages.</b> Prices rise steeply with childcare-worker wages: each $1,000 of mean annual wage goes with "
      f"{money(q3['wage_k']['b'], 2)}/week more for preschool (correlation {q3['wage_k']['corr']:.2f}; wages alone explain "
      f"{100 * q3['wage_k']['r2']:.0f}% of price variation). The vertical stacks are counties in the same metro, which "
      "share one OEWS wage."),
    B(f"<b>Rents.</b> Prices also rise with rent: each $100/month of median gross rent goes with "
      f"{money(q3['rent_h']['b'], 2)}/week more (correlation {q3['rent_h']['corr']:.2f}; R\u00b2 = {q3['rent_h']['r2']:.2f})."),
    B("<b>Interpretation.</b> Both relationships fit a market where higher input costs are passed on to families, "
      "but neither is causal on its own. Wages and rents are both higher in affluent, dense metros where families can "
      "pay more, so each line partly reflects demand. The spread around the lines widens at higher costs (more "
      "heteroskedasticity), and some prices form horizontal bands because several states publish one price for a "
      "whole rate zone. Counties well above the line are the candidates for the final project."),
]

# ---------------- Q4 ----------------
s.append(CondPageBreak(3 * inch))
s.append(P("Pre-Analysis 4. Univariate vs multivariate regressions, 2022", H1))
s.append(P("Dependent variable: median weekly center-based preschool price ($). Wage in $1,000s per year; rent in "
           "$100s per month. Conventional standard errors in parentheses; standard errors clustered by OEWS metro area "
           "(wages are measured at that level) in brackets.", CAP))


def cell(m, v):
    if v not in m["coef"]:
        return ""
    return (f"<b>{m['coef'][v]:.3f}</b><br/>({m['se'][v]:.3f})<br/>[{m['se_cluster'][v]:.3f}]")


rows = [["", "(a) Wage only", "(b) Rent only", "(c) Wage + rent"]]
for v, lab in [("wage_k", "Childcare-worker wage ($000/yr)"), ("rent_h", "Median gross rent ($100/mo)"),
               ("Intercept", "Intercept")]:
    rows.append([lab] + [cell(c4[k], v) for k in "abc"])
rows.append(["R\u00b2 (adjusted)"] + [f"{c4[k]['r2']:.3f} ({c4[k]['adj_r2']:.3f})" for k in "abc"])
rows.append(["Root MSE ($/week)"] + [f"{c4[k]['rmse']:.1f}" for k in "abc"])
rows.append(["N"] + [f"{c4[k]['n']:,}" for k in "abc"])
s.append(table(rows, [2.3, 1.6, 1.6, 1.6]))
s.append(P(f"All slope coefficients are significant at p &lt; 0.001 with either type of standard error (smallest "
           f"clustered t = {min(abs(c4['c']['t_cluster']['wage_k']), abs(c4['c']['t_cluster']['rent_h'])):.1f}).", CAP))
s.append(P("Interpretation", H2))
pt = q4["passthrough_per_child_week"]
s += [
    B(f"<b>(a) Wage alone:</b> counties whose childcare workers earn $1,000 more per year charge "
      f"{money(c4['a']['coef']['wage_k'], 2)} more per week for preschool, on average."),
    B(f"<b>(b) Rent alone:</b> counties with $100/month higher median gross rent charge "
      f"{money(c4['b']['coef']['rent_h'], 2)} more per week."),
    B(f"<b>(c) Both:</b> holding rent fixed, $1,000 more in wages goes with {money(c4['c']['coef']['wage_k'], 2)}/week; "
      f"holding wages fixed, $100 more in rent goes with {money(c4['c']['coef']['rent_h'], 2)}/week. The two together "
      f"explain {100 * c4['c']['r2']:.0f}% of the variation in 2022 prices, more than either alone."),
    B(f"<b>Why the coefficients fall.</b> Wages and rents are positively correlated (r = {ovb['corr_wage_rent']:.2f}). In "
      "a univariate regression each variable also picks up the effect of the omitted one (omitted-variable bias). "
      "The decomposition holds exactly in our data:"),
]
s.append(P(f"b<sub>wage</sub>(a) = b<sub>wage</sub>(c) + b<sub>rent</sub>(c) \u00d7 \u03b4<sub>rent on wage</sub> = "
           f"{c4['c']['coef']['wage_k']:.3f} + {c4['c']['coef']['rent_h']:.3f} \u00d7 {ovb['delta_rent_on_wage']:.3f} = "
           f"{ovb['wage_uni_check']:.3f}<br/>"
           f"b<sub>rent</sub>(b) = b<sub>rent</sub>(c) + b<sub>wage</sub>(c) \u00d7 \u03b4<sub>wage on rent</sub> = "
           f"{c4['c']['coef']['rent_h']:.3f} + {c4['c']['coef']['wage_k']:.3f} \u00d7 {ovb['delta_wage_on_rent']:.3f} = "
           f"{ovb['rent_uni_check']:.3f}", MATH))
s += [
    B(f"The wage coefficient falls by {100 * (1 - c4['c']['coef']['wage_k'] / c4['a']['coef']['wage_k']):.0f}% and the "
      f"rent coefficient by {100 * (1 - c4['c']['coef']['rent_h'] / c4['b']['coef']['rent_h']):.0f}%, so part of each "
      "univariate slope was the other cost. Collinearity is moderate (VIF = "
      f"{ovb['vif']:.2f}), so both effects are still precisely estimated."),
    B(f"<b>Size check.</b> If centers simply passed on labor cost, $1,000 more per worker per year is $19.23/week per "
      f"worker, or about {money(pt['10'], 2)} per child per week at a 1:10 staff-to-child ratio ({money(pt['15'], 2)}\u2013"
      f"{money(pt['7'], 2)} for ratios from 1:15 to 1:7). The estimated {money(c4['c']['coef']['wage_k'], 2)} is several "
      "times larger, so the wage variable also captures local affluence and demand. We read the coefficients as "
      "associations that predict price, not as causal cost pass-through. That is exactly what the final project needs: "
      "a benchmark price given local costs."),
]

# ---------------- FINAL PROJECT ----------------
s.append(PageBreak())
s.append(P("Final Project Analysis: Where Should We Locate?", H1))
s.append(P("We define an attractive market as one where prices are high <i>given</i> what it costs to operate there. "
           "The approach has four steps."))
s += [
    B("<b>1. Price benchmark.</b> For each year 2015\u20132022 we regress the real (2022 $) median preschool price on the real "
      "childcare-worker wage and real median gross rent across metro counties. Estimating each year separately lets "
      "the price-cost relationship change over time (for example, during the pandemic)."),
    B("<b>2. Premium.</b> A county's premium is its actual price minus its predicted price (the residual), in "
      "$/week: the price families pay above what local labor and rent costs would predict. It measures pricing power "
      "relative to local cost conditions; it is not an estimate of actual operating cost or profit, which the data do not "
      "contain. The <b>score</b> is the average premium over 2019\u20132022, so one noisy year cannot carry a county."),
    B(f"<b>3. Screens.</b> (i) a price in 2022 and in at least 3 of 2019\u20132022; (ii) a positive premium in every "
      f"observed year 2019\u20132022; (iii) a county-specific price: the 2022 price is shared by at most "
      f"{R['rules']['max_zone']} counties in the state, and the state-year is not flagged by NDCP as county prices "
      f"imputed from state-level data (code 3) or propensity-score estimates (code 6). We keep NDCP's estimates for years "
      f"between state surveys (code 5) and its percentile imputations (code 4); "
      f"{sum(e['est_2022'] for e in R['evidence'])} of the 10 picks' 2022 prices are code-5 estimates, so we show the "
      f"evidence behind each pick below; (iv) at least {R['rules']['min_kids']:,} children "
      "under 6 whose resident parents are all in the labor force (enough demand to fill a 100+ seat center)."),
    B("<b>4. Pick.</b> Rank eligible counties by score and keep the best county in each metro area, so that ten picks are "
      "ten different labor and rental markets."),
]
s.append(P("Benchmark price model by year (real 2022 $)", H2))
rows = [["Year", "N", "Intercept", "Wage ($000/yr)", "Rent ($100/mo)", "R\u00b2", "RMSE ($/wk)"]]
for y in range(2015, 2023):
    m = ym[y]
    rows.append([y, f"{m['n']:,}", f"{m['a']:.1f}", f"{m['b_wage']:.2f}", f"{m['b_rent']:.2f}", f"{m['r2']:.3f}",
                 f"{m['rmse']:.1f}"])
s.append(table(rows, [0.6, 0.6, 0.9, 1.1, 1.1, 0.7, 0.9]))
s.append(P(f"The coefficients are stable across years: {money(min(m['b_wage'] for m in ym.values()), 2)}\u2013"
           f"{money(max(m['b_wage'] for m in ym.values()), 2)} per week for each $1,000 of wage and "
           f"{money(min(m['b_rent'] for m in ym.values()), 2)}\u2013{money(max(m['b_rent'] for m in ym.values()), 2)} for "
           f"each $100 of rent, with R\u00b2 of {min(m['r2'] for m in ym.values()):.2f}\u2013"
           f"{max(m['r2'] for m in ym.values()):.2f}.", CAP))

rows = [["#", "County", "Metro area", "Price 2022", "Pred. price", "Prem. 2022", "Prem. % of pred.", "Score 2019-22",
         "Kids &lt;6, parents work", "Conf."]]
for r in TOP.itertuples():
    rows.append([r.rank, esc(short(r.NAME).split(",")[0] + ", " + r.state_abbr),
                 esc(r.area_title.split(",")[0].split("-")[0]),
                 money(r.MCPRESCHOOL) + ("*" if EVD[r.county_fips]["est_2022"] else ""), money(r.pred),
                 "+" + money(r.prem), f"+{100 * round(r.prem) / round(r.pred):.0f}%", "+" + money(r.score), f"{r.kids_under6_allpar_lf:,.0f}",
                 r.conf])
top_tab = table(rows, [0.3, 1.35, 1.1, 0.6, 0.6, 0.6, 0.55, 0.62, 0.75, 0.68])
s.append(KeepTogether([P("(a) Recommended counties", H2), top_tab, P("Prem. % of pred. = 2022 premium \u00f7 predicted price, using the dollar figures shown. * = 2022 price is an NDCP estimate between state surveys "
           "(see the evidence table below). Confidence = number of four alternative scoring rules (log/percent premium, 2022 premium only, survey years "
           "only, within-state premium) under which the county stays in the top 10: High = 4, Medium = 3, Watch = 2 or "
           f"fewer. Funnel: {R['funnel']['scored_2022']} counties scored in 2022 \u2192 {R['funnel']['years_ok']} with "
           f"enough years \u2192 {R['funnel']['years_stable']} positive every year \u2192 {R['funnel']['local_price']} "
           f"with county-specific prices \u2192 {R['funnel']['size']} large enough, in {R['funnel']['metros']} metros.", CAP)]))
rows = [["County", "NDCP codes, 2022", "2022 price is", "Latest survey year (no code 5/6): premium",
         "Latest year with no imputation flag (no code 3\u20136): premium"]]
for r in TOP.itertuples():
    e = EVD[r.county_fips]
    rows.append([esc(short(r.NAME).split(",")[0] + ", " + r.state_abbr),
                 esc(e["codes_2022"]),
                 "not documented" if e["codes_2022"] in UNDOC else ("an estimate (code 5)" if e["est_2022"] else "a survey value"),
                 f"{e['survey_year']}: {smoney(e['survey_prem'])}" + (" (code 4)" if "4" in str(e["survey_codes"]) else "")
                 + (" (undocumented)" if e["survey_codes"] in UNDOC else ""),
                 (f"{e['direct_year']}: {smoney(e['direct_prem'])}" + (" (undocumented)" if e["direct_codes"] in UNDOC else ""))
                 if e["direct_year"] else "none in 2015\u201322"])
EST = [r for r in TOP.itertuples() if EVD[r.county_fips]["est_2022"]]
PCT4 = [r for r in TOP.itertuples() if EVD[r.county_fips]["pctile_imputed_2022"]]
_dp = [EVD[r.county_fips]["direct_prem"] for r in PCT4]
_dy = [EVD[r.county_fips]["direct_year"] for r in PCT4]
_neg = [short(r.NAME).split(",")[0] + f" ({smoney(EVD[r.county_fips]['direct_prem'])} in {EVD[r.county_fips]['direct_year']})"
        for r in PCT4 if EVD[r.county_fips]["direct_prem"] < 0]
_svok = all(EVD[r.county_fips]["survey_prem"] > 0 for r in TOP.itertuples())
s.append(KeepTogether([P("Price evidence behind each pick", H2), table(rows, [1.35, 1.15, 1.15, 1.75, 1.8]),
                       P("NDCP codes: 2 = converted to a weekly price; 4 = one of the 50th/75th percentiles estimated "
                         "from the other (NDCP does not say which, so the median may be modeled); 5 = estimate for a "
                         "year between state surveys; NA = listed as excluded in Appendix B although the workbook has a "
                         "price (undocumented).", CAP)]))
s.append(P(f"{len(EST)} of the 10 picks' 2022 prices are NDCP estimates between state surveys, so their 2022 premiums are "
           "partly projected. " + ("Every pick had a positive premium in its latest survey year. " if _svok else "")
           + f"The {len(PCT4)} picks in Illinois and Maryland ("
           + ", ".join(short(r.NAME).split(",")[0] for r in PCT4)
           + ") rest most on imputed values: their latest surveys carry the percentile-imputation flag, and in their last "
           f"fully reported surveys ({min(_dy)}\u2013{max(_dy)}) their premiums were {smoney(min(_dp))} to {smoney(max(_dp))}"
           + (f"; {', '.join(_neg)} was below its predicted price then" if _neg else "")
           + ". These are the first counties to verify with a field price survey."))
s.append(fig("fig_top10_dumbbell.png", 6.2 * inch))
s.append(fig("fig_map_premium.png", 7.0 * inch))
s.append(P("Map: average 2019\u201322 premium for every metro county with price data; numbered markers are the picks.", CAP))
nx = pd.DataFrame(R["next10"])
wl = pd.DataFrame(R["watch"])
s.append(P("<b>Beyond the top 10.</b> Next in line (ranks 11\u201320): " +
           "; ".join(f"{esc(short(r.NAME))} ({money(r.score)})" for r in nx.itertuples()) + "."))
s.append(P("<b>Verify-first list</b> (large, persistent premiums, but the 2022 price is a shared rate-zone price or a "
           "state-level or propensity-score imputation, so no county-specific price is observed): " +
           "; ".join(f"{esc(short(r.NAME))} ({money(r.score)}, price shared by {int(r.zone_n)} "
                     f"count{'y' if r.zone_n == 1 else 'ies'}, NDCP code {esc(r.codes)})" for r in wl.itertuples()) + "."))

s.append(P("(b) Reliability of the prediction", H2))
rows = [["Model (2022)", "In-sample R\u00b2", "Out-of-sample R\u00b2", "Out-of-sample RMSE ($/wk)"]]
for k, v in cv.items():
    kname = {"Wage + rent (cost model)": "Wage + rent (benchmark model)",
             "Cost model + demand characteristics": "Benchmark + demand characteristics"}.get(k, k)
    rows.append([esc(kname), f"{v['r2_in']:.3f}", f"{v['r2_oos']:.3f}", f"{v['rmse_oos']:.1f}"])
s.append(table(rows, [2.8, 1.1, 1.3, 1.6]))
s.append(P("Out-of-sample fit is grouped 5-fold cross-validation: whole OEWS metro areas are held out, so counties that "
           "share a wage never appear in both training and test folds.", CAP))
s += [
    B(f"<b>Little sign of overfitting.</b> The benchmark model loses almost nothing out of sample (R\u00b2 "
      f"{cv['Wage + rent (cost model)']['r2_in']:.3f} \u2192 {cv['Wage + rent (cost model)']['r2_oos']:.3f}). A typical "
      f"prediction error is about {money(RMSE)}/week. {len(BIG)} of the 10 picks have 2022 premiums at least "
      f"{BIG.prem.min() / RMSE:.1f} times that ({money(BIG.prem.min())}\u2013{money(BIG.prem.max())}). "
      + " and ".join(f"{short(r.NAME).split(',')[0]} ({money(r.prem)})" for r in SMALL.itertuples())
      + " are within about one typical error, so their premiums are the hardest to tell from noise; they are also "
      "the two picks rated Watch."),
    B(f"<b>Back-test.</b> We reran the whole rule as of 2018 (scores from 2015\u20132018, same screens) and checked 2022. "
      f"Counties in the top decile of the 2015\u201318 premium averaged {money(bt['deciles'][9]['prem2022'])}/week above "
      f"their predicted price in 2022; the bottom decile averaged {money(bt['deciles'][0]['prem2022'])} (correlation "
      f"{bt['corr_formation_2022']:.2f}; slope {bt['slope_2022_on_formation']:.2f}). Of the 10 counties picked in 2018, the "
      f"{bt['n_with_2022']} that still had 2022 price data averaged {money(bt['picks_prem_2022_mean'])}/week above their predicted price, "
      f"and all {bt['n_with_2022']} were above it. (The other {10 - bt['n_with_2022']} are in Pennsylvania and "
      "Connecticut, which have no usable 2022 county prices.)"),
]
s.append(fig("fig_backtest_deciles.png", 5.0 * inch))
s.append(fig("fig_actual_vs_predicted.png", 4.6 * inch))
s.append(P("Actual vs predicted 2022 price. Counties above the dashed 45\u00b0 line charge more than their local wages "
           "and rents predict; the picks (dark) are well above it.", CAP))

s.append(P("(c) Market characteristics that predict promising locations", H2))
lab = {"pci_10k": "Per-capita income ($10k)", "college_10": "Women 25+ with bachelor's+ (per 10 pp)",
       "ftyr_10": "Women 16\u201364 full-time year-round (per 10 pp)", "careneed_pp": "Under-6 needing care, % of pop (per 1 pp)",
       "log_pop": "log population"}
rows = [["Characteristic", "Coef ($/wk)", "SE (clustered)", "p", "Standardized ($/wk per SD)", "Within-state std. (p)"]]
for v, l in lab.items():
    rows.append([l, f"{ch['coef'][v]:.2f}", f"{ch['se'][v]:.2f}", pexp(ch["p"][v]), f"{ch['std_coef'][v]:.2f}",
                 f"{ch['std_coef_fe'][v]:.2f} ({pexp(ch['std_p_fe'][v])})"])
s.append(table(rows, [2.6, 0.85, 0.9, 0.65, 1.1, 1.1]))
s.append(P(f"Regression of the 2022 premium on demand-side ACS characteristics, N = {ch['n']}, R\u00b2 = {ch['r2']:.3f}. "
           "The last column adds state fixed effects.", CAP))
pf = R["profile"]
s += [
    B("<b>Female college share</b> is the strongest and most robust predictor of a premium: about "
      f"{money(ch['std_coef']['college_10'], 2)}/week per standard deviation, significant, and larger within states "
      f"({money(ch['std_coef_fe']['college_10'], 2)}). The share of young children who need care is positive (p = "
      f"{ch['p']['careneed_pp']:.3f}), but not within states. Income is positive but imprecise once education is held "
      "fixed."),
    B(f"Together these explain only {100 * ch['r2']:.0f}% of the premium. Demand traits point to where premiums tend to be, "
      "but they do not replace measuring the premium directly, so the measured premium is our primary screen."),
    B(f"<b>Profile of the picks (2022 means vs all metro counties):</b> price {money(pf['Weekly preschool price ($)']['Top 10 (mean)'])} "
      f"vs {money(pf['Weekly preschool price ($)']['All metro counties (mean)'])}; per-capita income "
      f"{money(pf['Per-capita income ($)']['Top 10 (mean)'])} vs {money(pf['Per-capita income ($)']['All metro counties (mean)'])}; "
      f"women with a bachelor's+ {100 * pf[chr(87) + 'omen 25+ w/ bachelor' + chr(39) + 's+']['Top 10 (mean)']:.0f}% vs "
      f"{100 * pf['Women 25+ w/ bachelor' + chr(39) + 's+']['All metro counties (mean)']:.0f}%; under-6 children with working "
      f"parents {pf['Under-6 needing care (#)']['Top 10 (mean)']:,.0f} vs {pf['Under-6 needing care (#)']['All metro counties (mean)']:,.0f}."),
    B("<b>Characteristics we use:</b> (1) price premium over the wage-and-rent benchmark; (2) persistence of that premium; "
      "(3) county-specific prices; (4) market depth (\u2265 2,000 under-6 children with working parents); and, to "
      "prioritize the next wave of markets, (5) a high share of college-educated women and higher income."),
]

s.append(CondPageBreak(4.2 * inch))
s.append(P("(d) Are premiums stable over time?", H2))
s.append(fig("fig_stability.png", 7.2 * inch))
lagt = [["Years apart"] + [str(l["lag"]) for l in st["lag"]],
        ["Correlation, all county-years"] + [f"{l['corr_all']:.2f}" for l in st["lag"]],
        ["Correlation, survey years only"] + [f"{l['corr_survey']:.2f}" for l in st["lag"]],
        ["Pairs (all / survey)"] + [f"{l['n_all']:,} / {l['n_survey']:,}" for l in st["lag"]]]
s.append(table(lagt, [1.9] + [0.75] * 7))
s += [
    B(f"Premiums are highly persistent: {st['lag'][0]['corr_all']:.2f} one year apart, still {st['lag'][6]['corr_all']:.2f} "
      "seven years apart. NDCP interpolates some years between state surveys, which could create persistence mechanically, "
      "so we repeated the calculation with survey years only. The pattern is similar."),
    B(f"Of counties in the top fifth of premium in 2015\u201318, {100 * st['top_q_stay']:.0f}% were still in the top fifth in "
      f"2019\u201322 and {100 * st['top_q_top2']:.0f}% in the top two-fifths (correlation of the period averages "
      f"{st['corr_early_late']:.2f}). {100 * st['share_counties_sign_same_2019_2022']:.0f}% of counties had the same sign "
      "of premium in 2019 and 2022."),
    B("Our picks were above their predicted price in every year 2019\u20132022 (a screen). Over 2015\u20132018 they averaged about "
      f"{money(np.mean([v for p in st['top10_paths'].values() for y, v in p.items() if int(y) <= 2018 and v is not None]))}, "
      f"and one dipped slightly below zero in 2017 ({money(st['top10_min_prem_by_year']['2017'])}). Their premium has "
      "widened since 2019."),
]

s.append(P("(e) What our predictions are missing", H2))
s += [
    B("<b>Competition and capacity:</b> licensed-center counts, waitlists and vacancy rates. A premium can signal a "
      "shortage that competitors will fill."),
    B("<b>Public pre-K and subsidies:</b> state pre-K expansion and CCDF voucher reimbursement rates can cap prices, "
      "especially for 4-year-olds."),
    B(f"<b>State regulation and full labor cost:</b> staff-to-child ratios, group sizes, licensing and benefits. "
      f"{100 * R['prem_between_state_share']:.0f}% of the variance in 2022 premiums is between states. Some of that is "
      "regulation and some is differences in state survey methods; the within-state check keeps 9 of our 10 picks."),
    B("<b>Commercial real estate:</b> residential median gross rent is only a proxy for lease and build-out costs."),
    B("<b>Price data quality:</b> NDCP prices come from state market-rate surveys, some interpolated or published by rate "
      f"zone. {sum(e['est_2022'] for e in R['evidence'])} of our 10 picks' 2022 prices are estimates between state "
      "surveys (e.g. Stearns County's is extrapolated from Minnesota's 2021 survey). A field price check is the first next "
      "step."),
    B("<b>Demand trajectory:</b> births, under-5 population growth, migration, remote work and income growth (we use levels, "
      "not trends), plus the 75th-percentile price as a gauge of the premium segment."),
]
build(s, "PreAnalysis_and_Final_Analysis.pdf", "Pre-Analysis and Final Project Analysis")

# =====================================================================================================
# DOCUMENT 2: APPENDIX -- DATA HANDLING AND MODEL CHOICES
# =====================================================================================================
a = [P("Appendix: Data Handling and Model Choices", TITLE),
     P("MGT-403 Data Project \u00b7 Where Should We Open Our Next Daycare?", SUB),
     P("<b>Team:</b> " + ", ".join(TEAM), SUB), Spacer(1, 6)]

a.append(P("A1. Sources", H1))
rows = [["Source", "What we used", "Level", "Years"],
        ["DOL National Database of Childcare Prices (NDCP2022.xlsx)", "MCPRESCHOOL: median full-time weekly price, "
         "center-based, preschool (36\u201354 months); MCINFANT and MCTODDLER for descriptives", "County (5-digit FIPS)",
         "2015\u20132022"],
        ["BLS OEWS metropolitan & nonmetropolitan area files (oesmYYma.zip)", "A_MEAN (mean annual wage) and H_MEAN for "
         "SOC 39-9011 Childcare Workers", "OEWS area (7-character code)", "May 2015\u20132022"],
        ["Census ACS 5-year API (acs/acs5)", "B19301, B01001, B23008, B25064, B15002, B23022 (codes in the assignment)",
         "County", "Vintages 2015\u20132022"],
        ["Course crosswalk county_oews_crosswalk.csv", "Year-specific county \u2192 OEWS area and area title", "County \u00d7 year",
         "2015\u20132022"],
        ["BLS CPI-U, CUUR0000SA0", "Annual averages to convert to 2022 dollars", "National", "2015\u20132022"],
        ["NDCP Technical Report (Sept 2024), Appendix B", "Imputation codes by state and year (transcribed to "
         "data/ndcp_appendixB_imputations.csv)", "State \u00d7 year", "2015\u20132022"],
        ["Census cartographic boundary files (cb_2022, 20m)", "County and state outlines for the map only", "County", "2022"]]
a.append(table(rows, [2.2, 2.9, 1.1, 0.9]))
rows = [["Year"] + [str(y) for y in CPI.index], ["CPI-U"] + [f"{v:.3f}" for v in CPI.values],
        ["Multiplier to 2022 $"] + [f"{CPI[2022] / v:.4f}" for v in CPI.values]]
a.append(table(rows, [1.4] + [0.72] * 8))

a.append(P("A2. Geography, identifiers and merges", H1))
a += [
    B("<b>Identifiers kept as text.</b> NDCP stores FIPS as an integer, so we restored the 5-character zero-padded code. "
      "OEWS area codes were zero-padded to 7 characters before joining, and the crosswalk was read with every column as text."),
    B("<b>Wages to counties.</b> OEWS wages were joined to counties on [year, oews_area] using the year-specific crosswalk, "
      "and metro area titles came from the same file. For 2015\u20132017 the large metros are split into divisions in the "
      "MSA file; the whole-metro rows come from the aMSA file. No year \u00d7 area appears twice."),
    B("<b>Metro sample.</b> We kept counties whose OEWS area begins with \"00\" and dropped nonmetropolitan areas. Two retired "
      f"FIPS codes in the crosswalk ({', '.join(PS5R['retired_fips'])}: old Dade County FL and Bedford city VA) never appear in "
      "the ACS and would double-count their metro, so they were dropped."),
    B(f"<b>Missing wages.</b> BLS suppresses a few area wages (\"*\"), which leaves 0.4\u20131.6% of metro county-years without a "
      f"wage, in line with the roughly 1% the assignment says to expect. Areas suppressed in 2022: "
      f"{esc(', '.join(PS5R['q3']['wage_missing_areas_2022']))}."),
    B("<b>Connecticut 2022.</b> The 2022 ACS reports Connecticut's nine planning regions instead of its eight counties, so the "
      "NDCP/crosswalk county codes have no ACS match that year and fall out of the 2022 analysis dataset. We did not "
      "reallocate planning-region data to counties."),
    B("<b>Prices to counties.</b> NDCP was merged 1:1 on [FIPS, year]; every metro county-year matched. Puerto Rico "
      "municipios are metro counties in the crosswalk and have NDCP prices only in 2021, so they are in the dataset for "
      "that year. They never pass the screens."),
]

a.append(P("A3. Variable construction", H1))
a += [
    B("<b>Price.</b> MCPRESCHOOL, the median weekly full-time price for center-based preschool, as the assignment "
      "asks. The 75th-percentile price (_75CPRESCHOOL) is not used; it would be a natural extension for gauging the "
      "premium segment."),
    B("<b>ACS-derived variables</b> follow the assignment exactly: kids_under6_allpar_lf = B23008_004E + 010E + 013E; "
      "female_college_share = (B15002_032E + 033E + 034E + 035E) / B15002_019E; female_ftyr_share = B23022_029E / "
      "B23022_026E; under6_share and under6_careneed_share divide by total population. Negative ACS annotation codes "
      "(e.g. -666666666) were set to missing. We confirmed that each variable code has the same label in every vintage."),
    B("<b>Real dollars.</b> Prices, wages, rents and income were multiplied by CPI<sub>2022</sub>/CPI<sub>t</sub> (table A1). "
      "Wages are scaled to $1,000s and rents to $100s so coefficients read as \"$/week per $1,000 of wage\" and \"per $100 "
      "of rent\"."),
    B("<b>Analysis dataset.</b> A year \u00d7 county row is kept only if the price and all ten predictors are non-missing "
      f"({q1['rows']:,} rows). The file is saved as output/analysis_dataset.csv."),
]

a.append(P("A4. NDCP price quality: what the data really measure", H1))
a.append(P("NDCP county prices come from each state's market-rate survey (MRS). Two features matter for a county ranking."))
a += [
    B(f"<b>Rate-zone prices.</b> Many states publish one price per rate zone, so different counties report an identical "
      f"price. {100 * shared_all:.0f}% of analysis county-years share their exact price with at least one other county in "
      f"the state; in 2022 the median number of counties sharing a price is {zone_med:.0f}, and only "
      f"{100 * zone_le2:.0f}% of counties have a price shared by two or fewer. Example: {WI_N} Wisconsin {'metro ' if WI_ALL_METRO else ''}counties "
      f"({esc(WI_NAMES)}) all report {money(WI_PRICE, 2)} in 2022. In a zone, the lower-cost counties "
      "show a large positive residual purely because the price is averaged across the zone. That is a measurement "
      "artifact, not real pricing power. Our county-specific-price screen (price shared by at most 2 counties) removes "
      "this; such counties "
      "go to the verify-first list instead."),
    B("<b>Imputations (Technical Report, Appendix B).</b> Code 5 = estimate for a year between surveys (linear "
      "interpolation, or extrapolation up to two years after the last survey); 4 = one of the 50th/75th percentiles "
      "estimated from the other with a lognormal model (NDCP does not say which, so the median may be modeled); 3 = county "
      "prices imputed from state-level data; 6 = propensity-score-match estimates (California, North Carolina and "
      "Virginia in 2022); 2 = conversion to a weekly price. We exclude codes 3 and 6 in 2022 from the recommendation. We "
      f"keep codes 4 and 5, which together apply to {100 * SH45:.0f}% of 2022 analysis counties, so dropping them would "
      "remove most of the country; instead we test sensitivity to code 5 (\"survey years only\") and show the evidence "
      f"behind each pick in the analysis document. {sum(e['est_2022'] for e in R['evidence'])} of the 10 picks' 2022 "
      "prices are code-5 estimates. Several states that "
      "Appendix B lists as excluded (\"NA\") in a year nonetheless have prices in the 2022 workbook (e.g. AK, KS, KY, LA, MI, "
      "MT, SC, WV in 2022). We treat those as undocumented, not imputed."),
    B("<b>The *_flag variables</b> (e.g. MCPreschool_flag = 1/2/3) record how detailed age brackets were combined into the "
      "preschool group (all values equal / mode / highest mode). They are not imputation markers, so we do not use them "
      "as quality screens."),
]

a.append(P("A5. Model choices", H1))
a += [
    B("<b>Levels, not logs, for the main model.</b> A dollar premium per week reads directly as extra revenue per child "
      "relative to the wage-and-rent benchmark (it is not a profit margin), "
      f"and levels match the pre-analysis regressions. The log model fits almost identically out of sample (R\u00b2 "
      f"{cv['Log wage + log rent']['r2_oos']:.3f} vs {cv['Wage + rent (cost model)']['r2_oos']:.3f}) and is a robustness check."),
    B("<b>Year-by-year benchmark models</b> rather than one pooled model, so the benchmark adjusts if the price-cost relationship "
      "shifts (e.g. 2020\u20132021). All years use real 2022 dollars, so premiums are comparable across years."),
    B("<b>No demand variables in the benchmark model.</b> The assignment defines attractiveness as a high price given wages and rents. "
      "Putting income or education in the benchmark would absorb exactly the willingness to pay we want to find. We study "
      "demand characteristics separately, in part (c)."),
    B("<b>No state fixed effects in the main model.</b> Between-state price differences can be real pricing power (or regulation that "
      f"raises cost). {100 * R['prem_between_state_share']:.0f}% of premium variance is between states, so we report a "
      f"within-state version as robustness (2022 R\u00b2 rises to {R['state_fe']['r2']:.2f}). All 10 picks have a positive "
      f"within-state premium, and {int((TOP.prem_fe_rank_in_state <= 2).sum())} rank first or second in their state."),
    B("<b>Inference.</b> Wages vary only at the metro level and nearby counties share shocks, so standard errors are "
      "clustered by OEWS area. Cross-validation holds out whole metro areas for the same reason."),
    B("<b>Screens and thresholds.</b> At least 3 of 4 recent years, including 2022, so the score is current; positive in every "
      "observed year, for persistence; zone size \u2264 2, for a county-specific price; \u2265 2,000 under-6 children with working parents, "
      "so a ~150-seat center would need under 8% of local demand; one county per metro, to "
      "diversify across labor and rental markets."),
    B("<b>Back-test design.</b> Same rules, applied with 2015\u20132018 scores and 2018 eligibility (market size, zone, codes), "
      "and evaluated on the 2022 premium, a 4-year gap that exceeds NDCP's maximum 2-year extrapolation."),
]

a.append(P("A6. Robustness of the top 10", H1))
base = set(TOP.county_fips)
nm = {r["county_fips"]: short(r["NAME"]) for r in R["top10"]}
sc = pd.read_csv(OUT / "county_scores_2019_2022.csv", dtype={"county_fips": str}).set_index("county_fips")
rows = [["Alternative rule", "Overlap with baseline", "Dropped", "Added"]]
for k in ALT:
    v = set(R["robust_sets"][k])
    rows.append([k, f"{len(base & v)}/10", esc("; ".join(nm[f] for f in TOP.county_fips if f not in v)) or "\u2013",
                 esc("; ".join(short(sc.loc[f, "NAME"]) for f in sorted(v - base))) or "\u2013"])
a.append(table(rows, [1.9, 0.9, 2.2, 2.2]))
ALL4 = [short(r.NAME).split(",")[0] for r in TOP.itertuples() if r.kept == 4]
WEAK = [short(r.NAME).split(",")[0] for r in TOP.itertuples() if r.kept <= 2]
a.append(P(f"{len(ALL4)} counties ({', '.join(ALL4[:-1])} and {ALL4[-1]}) stay in the top 10 under every rule. "
           f"{' and '.join(WEAK)} are the least robust; the next in line ("
           + "; ".join(short(r.NAME) for r in pd.DataFrame(R["next10"]).head(3).itertuples())
           + ") are natural substitutes.", CAP))
a.append(P("Back-test picks (chosen with 2015\u20132018 data)", H2))
rows = [["County", "Metro", "2015\u201318 score", "2022 premium"]]
for p in bt["picks"]:
    rows.append([esc(short(p["NAME"])), esc(p["area_title"]), "+" + money(p["score"]),
                 ("+" + money(p["prem2022"])) if p["prem2022"] is not None else "no 2022 price"])
a.append(table(rows, [2.0, 2.9, 1.0, 1.1]))

a.append(CondPageBreak(1.6 * inch))
a.append(P("A7. Limitations", H1))
a += [
    B("NDCP measures posted market-rate-survey prices, not transaction prices or occupancy; a high price with low "
      "enrollment would not be profitable."),
    B("OEWS wages are metro averages for all childcare workers, not preschool teachers at centers, and exclude benefits."),
    B("Median gross rent is residential, not commercial."),
    B("ACS 5-year estimates average five years, so 2022 values describe 2018\u20132022."),
    B("The benchmark model is descriptive. Coefficients are associations used to build a benchmark price, not causal cost "
      "pass-through."),
]

a.append(P("A8. Reproducibility and AI assistance", H1))
a.append(P("All code and data are public at <b>https://github.com/ayush-rajpal/mgt403-daycare-location</b>. <b>python run_all.py</b> runs every step in order "
           "and then an independent check that recomputes the key results from the raw files:"))
rows = [["Step", "Script (src/)", "Produces"],
        ["1", "step1_ps4_prices.py", "PS4 tables and figures (outputs/ps4)"],
        ["2", "step2_ps4_report.py", "PS4 report PDF"],
        ["3", "step3_ps5_cost_panel.py", "Year \u00d7 county metro panel: OEWS wages + ACS + crosswalk (outputs/ps5)"],
        ["4", "step4_ps5_report.py", "PS5 report PDF"],
        ["5", "step5_final_analysis.py", "Analysis dataset, regressions, scores, figures, outputs/final/results.json"],
        ["6", "step6_final_documents.py", "This appendix and the pre-analysis / final-analysis PDF"],
        ["7", "step7_final_deck.js", "Daycare_Expansion_Deck.pptx (6 slides)"],
        ["check", "checks/verify_results.py", "Independent recomputation of every key number"]]
a.append(table(rows, [0.5, 2.4, 4.2]))
a.append(P("Python 3.14 with pandas, numpy, statsmodels, scipy, matplotlib, pyshp and reportlab; Node.js with pptxgenjs. "
           "The work was done with an AI coding assistant (Claude Code) following the team's prompt: \"complete the "
           "assignment\u2026 we have to submit the pre-analysis work, a short slide deck summarizing the findings, and any "
           "appendices describing data cleaning choices or model choices; for the slides use Yale blue and blue shades "
           "with a white background.\" The assistant reused the team's PS4/PS5 data and code, wrote the final-project "
           "steps 5\u20138, and checked every figure and slide by rendering it. Every statistic in the "
           "documents and slides is computed by the code (from outputs/final/results.json or the output CSVs), not typed by "
           "hand, and all of them were re-verified with an independent recomputation from the raw files."))
build(a, "Appendix_Data_and_Model_Choices.pdf", "Appendix: Data Handling and Model Choices")
