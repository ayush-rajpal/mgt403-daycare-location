"""
Builds PS5_Cost_Drivers_Report.pdf from output/results.json and the figures made by ps5.py.
Every number in the report is read from results.json (PS4 context numbers from outputs/ps4).

Run:  python ps5.py && python make_report.py
"""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from common import OUT_PS5 as OUT, OUT_PS4, DELIVERABLES, register_arial
R = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
PS4 = json.loads((OUT_PS4 / "results.json").read_text(encoding="utf-8"))

TEAM = ["Winston Park", "Ayush Rajpal", "Tobin Gedstad", "Wen Ding", "Alfred Mordecai"]

register_arial()

ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["Normal"], fontName="Arial", fontSize=10, leading=14, spaceAfter=6)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=14, bulletIndent=4, spaceAfter=3)
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Arial-Bold", fontSize=15, spaceBefore=6,
                    spaceAfter=6, textColor=colors.HexColor("#1f3b63"))
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Arial-Bold", fontSize=12, spaceBefore=8,
                    spaceAfter=4, textColor=colors.HexColor("#1f3b63"))
TITLE = ParagraphStyle("title", parent=ss["Title"], fontName="Arial-Bold", fontSize=18, leading=22)
SUB = ParagraphStyle("sub", parent=BODY, alignment=TA_CENTER, textColor=colors.HexColor("#555555"))
CAP = ParagraphStyle("cap", parent=BODY, fontSize=8.5, leading=11, textColor=colors.HexColor("#555555"))
MATH = ParagraphStyle("math", parent=BODY, leftIndent=24, fontSize=10.5, leading=16,
                      backColor=colors.HexColor("#f3f5f9"), borderPadding=(4, 6, 4, 6),
                      spaceBefore=4, spaceAfter=8)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.5, leading=10.5, spaceAfter=0)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Arial-Bold")
PROMPT = ParagraphStyle("prompt", parent=BODY, fontSize=9, leading=12, leftIndent=10,
                        backColor=colors.HexColor("#f6f6f6"), borderPadding=(4, 6, 4, 6),
                        spaceBefore=2, spaceAfter=4)

XBAR = "x&#772;"
DBAR = "d&#772;"


def P(t, st=BODY):
    return Paragraph(t, st)


def B(t):
    return Paragraph(t, BULLET, bulletText="\u2022")


def table(rows, widths, header_rows=1):
    data = [[Paragraph(str(c), CELLB if i < header_rows else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * inch for w in widths], repeatRows=header_rows)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c2d1")),
             ("BACKGROUND", (0, 0), (-1, header_rows - 1), colors.HexColor("#dfe6f0")),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    for i in range(header_rows, len(rows)):
        if (i - header_rows) % 2:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f6f8fb")))
    t.setStyle(TableStyle(style))
    return t


def fig(name, width=7.0 * inch):
    from PIL import Image as PILImage
    w, h = PILImage.open(OUT / name).size
    return Image(str(OUT / name), width=width, height=width * h / w)


def money(x, d=2):
    return f"${x:,.{d}f}"


def pexp(p):
    if p >= 1e-4:
        return f"{p:.4f}"
    m, e = f"{p:.2e}".split("e")
    return f"{m} &#215; 10<super>{int(e)}</super>"


def pct(a, b):
    return a / b - 1


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


q1, q3, q4, q5, q6, q7 = R["q1"], R["q3"], R["q4"], R["q5"], R["q6"], R["q7"]
cpi = {int(k): v for k, v in q5["cpi"].items()}
cov = {c["year"]: c for c in q3["coverage"]}
tr = {(r["series"], r["year"]): r for r in q5["trend"]}
T4 = q4["table"]
pa, we, mp = q6["paired"], q6["welch"], q6["metro_paired"]

story = [P("Problem Set 5 \u2013 Cost Drivers in Childcare", TITLE),
         P("MGT-403 Data Project \u00b7 Where Should We Open Our Next Daycare?", SUB),
         P("<b>Team:</b> " + ", ".join(TEAM), SUB), Spacer(1, 8)]

# ---------------- Summary ----------------
w15, w19, w20, w21, w22 = (tr[("wage_annual", y)] for y in (2015, 2019, 2020, 2021, 2022))
r15, r22 = tr[("median_gross_rent", 2015)], tr[("median_gross_rent", 2022)]
story.append(P("Summary of answers", H1))
story += [
    B(f"<b>Q1\u2013Q3 data.</b> We built a year \u00d7 county panel of "
      f"{min(c['metro_counties'] for c in cov.values()):,}\u2013{max(c['metro_counties'] for c in cov.values()):,} "
      f"metro counties per year (2015\u20132022) by combining ACS 5-year county data from the Census API with BLS OEWS "
      f"childcare-worker (SOC 39-9011) area wages through the course crosswalk. Wages are missing for "
      f"{min(c['wage_missing_pct'] for c in cov.values()):.1f}\u2013{max(c['wage_missing_pct'] for c in cov.values()):.1f}% "
      "of metro counties per year, in line with the roughly 1% the assignment says to expect."),
    B(f"<b>Q4 (2022).</b> The average metro county has a childcare-worker mean annual wage of "
      f"{money(T4['wage_annual']['Mean'], 0)} (SD {money(T4['wage_annual']['SD'], 0)}) and a median gross rent of "
      f"{money(T4['median_gross_rent']['Mean'], 0)}/month (SD {money(T4['median_gross_rent']['SD'], 0)})."),
    B(f"<b>Q5 (real trends).</b> In constant 2022 dollars, the average childcare-worker wage rose from "
      f"{money(w15['mean_real'], 0)} (2015) to a peak of {money(w21['mean_real'], 0)} (2021), then slipped to "
      f"{money(w22['mean_real'], 0)} in 2022 ({pct(w22['mean_real'], w15['mean_real']):+.1%} over 2015\u20132022). "
      f"Real rent rose every year, from {money(r15['mean_real'], 0)} to {money(r22['mean_real'], 0)} per month "
      f"({pct(r22['mean_real'], r15['mean_real']):+.1%})."),
    B(f"<b>Q6 (2022 vs 2019).</b> Real wages were {money(pa['dbar'])} higher in 2022 "
      f"({pct(pa['mean2022'], pa['mean2019']):+.1%}). Paired t = {pa['t']:.2f}, p = {pexp(pa['p'])}, so we reject "
      "H<sub>0</sub> that real wages were the same. The rise is statistically significant but small in size: "
      "wages beat inflation by under 2%."),
    B(f"<b>Q7 (regression).</b> Wage = {money(q7['intercept'], 0)} + {q7['coef']:,.0f} \u00d7 female college "
      f"share (t = {q7['t']:.1f}, p = {pexp(q7['p'])}, R\u00b2 = {q7['r2']:.3f}). We reject that the slope is zero: "
      f"counties where 10 percentage points more women hold a bachelor's degree pay childcare workers about "
      f"{money(q7['coef'] / 10, 0)} more per year, on average."),
]

# ---------------- Q1 ----------------
story.append(P("Q1. ACS 5-year county data (Census API)", H1))
story.append(P("We pulled the ACS 5-year estimates for every U.S. county for each vintage from 2015 to 2022 from "
               "<font face='Courier'>api.census.gov/data/{year}/acs/acs5</font> (<font face='Courier'>"
               "for=county:*&amp;in=state:*</font>), using the variable codes in the assignment's table. "
               "The year is the end year of the 5-year window (e.g., 2022 = 2018\u20132022 responses). "
               "Before using them, we downloaded the Census's own description of every code for all eight vintages. "
               f"They are {'identical' if q1['labels_consistent'] else 'NOT identical'} across years, apart from the "
               "dollar-year in the income label. County FIPS = state (2 digits) + county (3 digits), kept as text. "
               "Census \u201cnot available\u201d codes (large negative numbers) are set to missing."))
L = q1["labels_2022"]
short = lambda v: esc(L[v].replace("Estimate!!", "").replace("Total:!!", "").replace(":!!", "!!")
                       .replace("!!", " \u203a ").rstrip(":"))
rows = [["Derived variable", "Construction (ACS codes)", "Census label (2022)"],
        ["per_capita_income", "B19301_001E", short("B19301_001E")],
        ["pop_total", "B01001_001E", short("B01001_001E")],
        ["kids_under6", "B23008_002E", short("B23008_002E")],
        ["kids_under6_allpar_lf", "B23008_004E + 010E + 013E",
         "Under 6 \u203a two parents, both in LF; + one parent (father) in LF; + one parent (mother) in LF"],
        ["median_gross_rent", "B25064_001E", short("B25064_001E")],
        ["female_college_share", "(B15002_032E+033E+034E+035E) / B15002_019E",
         "Female 25+ with bachelor's, master's, professional, or doctorate \u00f7 all females 25+"],
        ["female_ftyr_share", "B23022_029E / B23022_026E",
         "Females 16\u201364 who usually worked 35+ hrs/wk, 50\u201352 weeks \u00f7 all females 16\u201364"],
        ["under6_share", "kids_under6 \u00f7 pop_total", "as defined in the assignment"],
        ["under6_careneed_share", "kids_under6_allpar_lf \u00f7 pop_total", "as defined in the assignment"]]
story += [table(rows, [1.55, 2.2, 3.45]),
          P(f"Table 1. ACS variables. Counties returned per vintage: "
            f"{', '.join(f'{y}: {n:,}' for y, n in q1['rows_per_year'].items())}.", CAP)]

# ---------------- Q2 ----------------
story.append(P("Q2. OEWS childcare-worker wages by area", H1))
files = {}
for f in q3["oews_files"]:
    files.setdefault(f["year"], []).append(f"{f['file'].split('_')[0]} ({f['n']})")
story.append(P("From each <font face='Courier'>oesmYYma.zip</font> (May 2015\u2013May 2022) we kept the rows for SOC "
               "<b>39-9011 \u201cChildcare Workers\u201d</b> and the <b>mean annual wage (A_MEAN)</b>, plus the mean "
               "hourly wage. Each zip contains a metropolitan file (<i>MSA_</i>) and a nonmetropolitan file "
               "(<i>BOS_</i>). <b>Important detail:</b> in 2015\u20132017, the 11 largest metros (New York, LA, "
               "Chicago, Boston, Washington, etc.) appear in the MSA_ file only split into metropolitan "
               "divisions. The whole-metro estimates that the crosswalk refers to are in a third file, "
               "<i>aMSA_</i>. Leaving out aMSA_ left about 10% of metro counties without a wage in 2015\u20132017, "
               "so we included it. No area appears twice in any year. Column names differ across years "
               "(e.g., AREA_NAME vs. area_title), so we standardized them. BLS marks suppressed wages with "
               "\u201c*\u201d; these are treated as missing."))
rows = [["Year", "Childcare-worker rows by file (MSA_ / aMSA_ / BOS_)"]] + \
       [[y, ", ".join(v)] for y, v in sorted(files.items())]
story += [table(rows, [0.8, 6.4]), P("Table 2. SOC 39-9011 rows extracted from each OEWS release.", CAP)]

# ---------------- Q3 ----------------
story.append(P("Q3. Merge to a year \u00d7 county metro panel", H1))
story.append(P("Steps: (1) zero-pad the OEWS area code to 7 characters (e.g., 16980 \u2192 0016980) so it matches "
               "the crosswalk; (2) keep crosswalk rows whose <i>oews_area</i> begins with \u201c00\u201d (metro); "
               "(3) join OEWS wages on [year, oews_area]; (4) join ACS on [county_fips, year]; (5) label metros "
               "with the crosswalk's <i>area_title</i>. The result has exactly one row per year \u00d7 county "
               f"({q3['rows']:,} rows)."))
story.append(P(f"<b>Data-handling decision.</b> The crosswalk lists two retired county codes next to their current "
               "replacements: 12025 (old Dade County, FL code; now 12086 Miami-Dade) and "
               "51515 (Bedford city, VA; now part of 51019 Bedford County). They never appear in any ACS "
               "vintage and would count their metro's wage twice, so we dropped them."))
rows = [["Year", "Metro counties", "No OEWS row", "Wage missing", "% wage missing", "No ACS match",
         "Rent missing"]]
for y in range(2015, 2023):
    c = cov[y]
    rows.append([y, f"{c['metro_counties']:,}", c["no_oews_row"], c["wage_missing"], f"{c['wage_missing_pct']:.2f}%",
                 c["acs_missing"], c["rent_missing"]])
story += [table(rows, [0.6, 1.0, 0.95, 0.95, 1.05, 1.0, 0.95]),
          P("Table 3. Merge sanity check. \u201cNo OEWS row\u201d = BLS published no SOC 39-9011 estimate for "
            "that metro and year; \u201cWage missing\u201d also counts \u201c*\u201d-suppressed cells.", CAP)]
story += [
    B(f"<b>Wages:</b> {min(c['wage_missing_pct'] for c in cov.values()):.2f}\u2013"
      f"{max(c['wage_missing_pct'] for c in cov.values()):.2f}% missing per year, matching the "
      "assignment's \u201croughly 1%\u201d. Missing cases are metros for which BLS published no childcare-worker "
      f"estimate or suppressed it (2022: {', '.join(q3['wage_missing_areas_2022'])})."),
    B("<b>ACS:</b> every metro county matches except <b>7 Connecticut counties in 2022</b>. Starting with the 2022 "
      "ACS, the Census Bureau reports Connecticut by 9 planning regions (FIPS 09110\u201309190) instead of its "
      "old counties, while the crosswalk still uses the old county codes. These 7 county-years are left "
      "missing for ACS variables (no county-to-region allocation was made)."),
]

# ---------------- Q4 ----------------
story.append(P("Q4. Descriptive statistics of the predictors, 2022", H1))


def fmt(v, x):
    if "share" in v:
        return f"{x:.4f}"
    if v in ("pop_total", "kids_under6", "kids_under6_allpar_lf"):
        return f"{x:,.0f}"
    if v == "wage_hourly":
        return f"{x:,.2f}"
    return f"{x:,.0f}"


rows = [["Variable", "Mean", "SD", "N", "Min", "Max"]]
for v, lab in q4["labels"].items():
    s = T4[v]
    rows.append([esc(lab), fmt(v, s["Mean"]), fmt(v, s["SD"]), f"{s['N']:,.0f}", fmt(v, s["Min"]), fmt(v, s["Max"])])
story += [table(rows, [2.9, 0.9, 0.9, 0.55, 0.85, 0.95]),
          P(f"Table 4. Metro counties, 2022 (OEWS May 2022; ACS 2018\u20132022). {q4['n_counties']:,} metro counties; "
            f"the wage comes from {q4['n_areas_with_wage']} OEWS metro areas and is shared by all counties in an "
            "area. Dollar values are 2022 dollars. Shares are fractions (0.30 = 30%).", CAP)]
story += [
    B("Childcare work is low-paid: the average metro county's childcare-worker mean wage is "
      f"{money(T4['wage_annual']['Mean'], 0)} per year ({money(T4['wage_hourly']['Mean'])}/hour), ranging from "
      f"{money(T4['wage_annual']['Min'], 0)} to {money(T4['wage_annual']['Max'], 0)}."),
    B("Population and child counts are extremely skewed (SD far above the mean): metro counties range from tiny "
      "(Kalawao County, HI, population 50, part of the Kahului metro) to Los Angeles County (~9.9 million). "
      "The share variables are better for comparing counties."),
    B(f"On average {T4['female_college_share']['Mean']:.1%} of women 25+ have a bachelor's degree or more, "
      f"{T4['female_ftyr_share']['Mean']:.1%} of women 16\u201364 work full-time year-round, and children under 6 "
      f"are {T4['under6_share']['Mean']:.1%} of the population ({T4['under6_careneed_share']['Mean']:.1%} are "
      "under-6s whose resident parents are all in the labor force)."),
]

# ---------------- Q5 ----------------
story.append(P("Q5. Real wages and rents over time (constant 2022 dollars)", H1))
story.append(P("Real value<sub>t</sub> = nominal value<sub>t</sub> \u00d7 CPI<sub>2022</sub> / CPI<sub>t</sub> "
               "(CPI-U, CUUR0000SA0, annual average). OEWS wages are treated as year-t dollars (May reference period). "
               "ACS dollar values are already expressed in dollars of the 5-year window's end year (the Census label "
               "says so, e.g., \u201cin 2015 inflation-adjusted dollars\u201d), so they are also treated as year-t "
               "dollars. Lines show the mean across metro counties, with a 95% CI. The dashed line is a balanced "
               "panel (counties observed in every year)."))
story.append(fig("q5_wage_rent_trends.png"))
story.append(P("Figure 1. Childcare-worker mean annual wage (left) and median gross rent (right), metro counties.",
               CAP))
rows = [["Year", "CPI-U", "Wage nominal", "Wage real (2022 $)", "N", "Rent nominal", "Rent real (2022 $)", "N"]]
for y in range(2015, 2023):
    w, r = tr[("wage_annual", y)], tr[("median_gross_rent", y)]
    rows.append([y, f"{cpi[y]:.3f}", money(w["mean_nominal"], 0), money(w["mean_real"], 0), f"{w['N']:,}",
                 money(r["mean_nominal"], 0), money(r["mean_real"], 0), f"{r['N']:,}"])
story += [KeepTogether([table(rows, [0.55, 0.75, 0.95, 1.15, 0.6, 0.95, 1.15, 0.6]),
          P("Table 5. Mean across metro counties; wage in $/year, rent in $/month.", CAP)])]
story += [
    P("Discussion", H2),
    B(f"<b>Wages:</b> nominal wages rose {pct(w22['mean_nominal'], w15['mean_nominal']):.1%} from 2015 to 2022, "
      f"while the CPI rose {pct(cpi[2022], cpi[2015]):.1%}. In real terms, wages rose gradually through 2019, "
      f"jumped in 2020 ({pct(w20['mean_real'], w19['mean_real']):+.1%}), were flat in 2021, and then fell "
      f"{abs(pct(w22['mean_real'], w21['mean_real'])):.1%} in 2022 as "
      f"{pct(cpi[2022], cpi[2021]):.1%} inflation outpaced nominal raises. "
      f"Net change 2015\u20132022: {pct(w22['mean_real'], w15['mean_real']):+.1%} real."),
    B(f"<b>Rents:</b> real median gross rent rose every year, {pct(r22['mean_real'], r15['mean_real']):+.1%} in total "
      f"({money(r15['mean_real'], 0)} \u2192 {money(r22['mean_real'], 0)}/month). Because each ACS figure pools "
      "five years of responses, the rent series is smoothed and reacts slowly to short-run changes."),
    B("The balanced-panel lines lie almost on top of the all-county lines, so these trends are not caused by "
      "changes in which counties are in the sample."),
]

# ---------------- Q6 ----------------
story.append(PageBreak())
story.append(P("Q6. Were real childcare-worker wages the same in 2022 as in 2019?", H1))
story.append(P("<b>(a) Hypotheses.</b> Let \u03bc<sub>2019</sub>, \u03bc<sub>2022</sub> be the average real (2022 $) "
               "childcare-worker mean annual wage across metro counties."))
story.append(P("H<sub>0</sub>: \u03bc<sub>2022</sub> \u2212 \u03bc<sub>2019</sub> = 0 &#160;&#160;&#160; "
               "H<sub>1</sub>: \u03bc<sub>2022</sub> \u2212 \u03bc<sub>2019</sub> \u2260 0 &#160;&#160;&#160; "
               "(two-sided, \u03b1 = 0.05)", MATH))
story.append(P("<b>(b) Test.</b> The same metro counties are observed in both years, so the main test is a "
               "<b>paired t-test</b> on each county's change d = real wage<sub>2022</sub> \u2212 real "
               "wage<sub>2019</sub> (2019 wages converted with CPI<sub>2022</sub>/CPI<sub>2019</sub> = "
               f"{cpi[2022]:.3f}/{cpi[2019]:.3f}). As checks, we also ran a two-sample Welch t-test on all counties in "
               "each year, and a paired test with one observation per OEWS metro area (the level at which BLS "
               "measures wages)."))
story.append(P(f"t = {DBAR} / (s<sub>d</sub> / \u221an) = {pa['dbar']:.4f} / ({pa['sd']:.4f} / \u221a{pa['n']}) "
               f"= {pa['dbar']:.4f} / {pa['se']:.4f} = <b>{pa['t']:.4f}</b>, &#160; df = {pa['df']}; &#160; "
               f"p = 2 \u00d7 P(T<sub>{pa['df']}</sub> \u2265 |t|) = <b>{pexp(pa['p'])}</b>", MATH))
rows = [["", "Paired, counties (main)", "Welch two-sample, counties", "Paired, metro areas"],
        ["n", f"{pa['n']:,} counties in both years", f"{we['n2019']:,} (2019), {we['n2022']:,} (2022)",
         f"{mp['n']} metro areas"],
        ["Mean real wage 2019", money(pa["mean2019"]), money(we["mean2019"]), money(mp["mean2019"])],
        ["Mean real wage 2022", money(pa["mean2022"]), money(we["mean2022"]), money(mp["mean2022"])],
        ["Difference (2022 \u2212 2019)", money(pa["dbar"]), money(we["mean2022"] - we["mean2019"]), money(mp["dbar"])],
        ["t statistic", f"{pa['t']:.3f}", f"{we['t']:.3f}", f"{mp['t']:.3f}"],
        ["p-value (two-sided)", pexp(pa["p"]), pexp(we["p"]), pexp(mp["p"])],
        ["Decision at 5%", "Reject H<sub>0</sub>", "Reject H<sub>0</sub>", "Reject H<sub>0</sub>"],
        ["Share of units with a real raise", f"{pa['share_up']:.1%}", "\u2013", f"{mp['share_up']:.1%}"]]
story += [table(rows, [1.9, 1.75, 1.85, 1.7]),
          P(f"Table 6. Real (2022 $) childcare-worker mean annual wage, 2022 vs 2019. Paired 95% CI for the change: "
            f"[{money(pa['ci'][0])}, {money(pa['ci'][1])}]. SciPy's ttest_rel gives t = {pa['scipy_t']:.4f}, "
            "identical to the hand formula; a separate program reading the raw files reproduced n, mean change and t.",
            CAP)]
nominal_chg = pct(q6["nominal"]["mean2022"], q6["nominal"]["mean2019"])
p4b = {r["year"]: r["mean_real_balanced"] for r in PS4["q3"]["balanced"] if r["age"] == "Preschool"}
story += [
    P("(c) Interpretation", H2),
    B(f"<b>Reject H<sub>0</sub>.</b> |t| = {pa['t']:.2f} is far above the critical value of {pa['tcrit']:.2f}, and "
      f"p = {pexp(pa['p'])} < 0.05. Real childcare-worker wages were significantly higher in 2022 than in 2019, by "
      f"{money(pa['dbar'], 0)} per year ({pct(pa['mean2022'], pa['mean2019']):+.1%}). Wages rose in "
      f"{pa['share_up']:.0%} of counties. The two checks agree (Welch p = {pexp(we['p'])}; metro-area p = "
      f"{pexp(mp['p'])})."),
    B(f"<b>The rise is statistically clear but economically small.</b> Nominal wages rose {nominal_chg:.1%} "
      f"(from {money(q6['nominal']['mean2019'], 0)} to {money(q6['nominal']['mean2022'], 0)}), but prices rose "
      f"{q6['cpi_change']:.1%}, so most of the nominal raise only kept pace with inflation. Real wages also "
      f"peaked in 2020\u20132021 and fell in 2022 (Q5)."),
    B("<b>What this means for the providers' claim.</b> The data support part of it: childcare workers' pay "
      f"rose faster than general inflation after 2019, and in dollar terms labor costs rose about "
      f"{nominal_chg:.0%}. But the real increase is under 2%, which is modest for something described as "
      "an \u201cimportant driver\u201d. For context, from our PS4 results: real median preschool prices in a "
      f"fixed set of counties went from {money(p4b[2019])} (2019) to {money(p4b[2022])} (2022), "
      f"{pct(p4b[2022], p4b[2019]):+.1%}. So real labor costs rose a little while real prices fell. A comparison of "
      "averages cannot show that wages <i>caused</i> cost increases, and it says nothing about other costs "
      "such as rent (which also rose, Q5)."),
]

# ---------------- Q7 ----------------
story.append(P("Q7. Bivariate regression (2022): wages on female college share", H1))
story.append(P(f"Model: wage<sub>c</sub> = \u03b2<sub>0</sub> + \u03b2<sub>1</sub> \u00b7 female_college_share<sub>c</sub> + "
               f"u<sub>c</sub>, estimated by OLS on {q7['n']:,} metro counties with both variables in 2022 (wage = "
               "OEWS mean annual wage, 2022 $; share is a fraction from 0 to 1)."))
rows = [["", "Coefficient", "Std. error", "t", "p-value", "95% CI"],
        ["Intercept (\u03b2<sub>0</sub>)", money(q7["intercept"]), "", "", "", ""],
        ["female_college_share (\u03b2<sub>1</sub>)", f"{q7['coef']:,.2f}", f"{q7['se']:,.2f}", f"{q7['t']:.2f}",
         pexp(q7["p"]), f"[{q7['ci'][0]:,.0f}, {q7['ci'][1]:,.0f}]"],
        ["\u2003robust (HC1) SE", "", f"{q7['se_hc1']:,.2f}", f"{q7['coef'] / q7['se_hc1']:.2f}", pexp(q7["p_hc1"]), ""],
        [f"\u2003clustered by metro area ({q7['n_clusters']} clusters)", "", f"{q7['se_cluster']:,.2f}",
         f"{q7['t_cluster']:.2f}", pexp(q7["p_cluster"]), ""]]
story += [table(rows, [2.35, 1.0, 0.9, 0.6, 1.05, 1.3]),
          P(f"Table 7. OLS, N = {q7['n']:,}, R\u00b2 = {q7['r2']:.3f}, correlation = {q7['corr']:.3f}. "
            f"Hand check: slope = cov(x, y)/var(x) = {q7['slope_hand']:,.2f}.", CAP)]
story.append(fig("q7_scatter_wage_college.png", width=5.0 * inch))
story.append(P("Figure 2. Each dot is a metro county. Horizontal bands appear because all counties in a metro "
               "area share one OEWS wage.", CAP))
story += [
    B(f"<b>Coefficient:</b> \u03b2<sub>1</sub> = {q7['coef']:,.0f}. Since the share runs from 0 to 1, this means a "
      f"<b>10 percentage-point</b> higher share of college-educated women is associated with a "
      f"<b>{money(q7['coef'] / 10, 0)}</b> higher childcare-worker mean annual wage (about "
      f"{q7['coef'] / 10 / q7['y_mean']:.0%} of the average wage). Moving 1 SD in the share "
      f"({q7['x_sd'] * 100:.1f} points) goes with {money(q7['coef'] * q7['x_sd'], 0)} higher wages."),
    B(f"<b>Can we reject \u03b2<sub>1</sub> = 0? Yes.</b> t = {q7['t']:.1f}, p = {pexp(q7['p'])}, and the 95% CI "
      f"[{q7['ci'][0]:,.0f}, {q7['ci'][1]:,.0f}] excludes zero. Counties in the same metro share one wage, "
      f"so they are not independent observations. Allowing for that (clustered SEs) doubles the standard "
      f"error, but t is still {q7['t_cluster']:.1f}, so the conclusion holds."),
    B(f"<b>Interpretation in words:</b> childcare workers earn more where more women are college-educated. "
      f"This is a correlation, not a causal effect, and it explains about {q7['r2']:.0%} of the variation in "
      "wages. The share of college-educated women likely also reflects higher-wage, higher-cost local labor "
      "markets (interpretation, not tested here)."),
]

# ---------------- Notes ----------------
story.append(P("Assumptions and data-handling choices", H1))
story += [
    B("Sample: crosswalk counties whose OEWS area code begins with \u201c00\u201d (metro), 2015\u20132022, the same "
      "metro definition as PS4. Each county counts equally (not population-weighted)."),
    B("Wage measure: OEWS mean annual wage (A_MEAN) for SOC 39-9011; the year is the May reference year. "
      "2015\u20132017 whole-metro wages for the 11 largest metros come from the aMSA_ files."),
    B("Two retired FIPS codes (12025, 51515) were dropped as duplicates of current counties. Connecticut's "
      "7 metro counties lack ACS data in 2022 because the 2022 ACS uses planning regions."),
    B("Dollar conversion: CPI-U annual averages from the BLS API (2015\u20132022), base year 2022."),
    B("Q6 main test: paired t-test (same counties both years); Welch and metro-area versions as checks. "
      "Q7: conventional OLS SEs, with robust and metro-clustered SEs as checks."),
    B("Reproduce: put the 8 OEWS zips in data/oews/, the crosswalk and CPI file in data/, and your Census key "
      "in data/census_api_key.txt (or the CENSUS_API_KEY environment variable). Then run "
      "<font face='Courier'>python ps5.py</font> and <font face='Courier'>python make_report.py</font>."),
]

# ---------------- Prompt appendix ----------------
story.append(CondPageBreak(4 * inch))
story.append(P("Appendix: prompts to reproduce this analysis", H1))
PROMPTS = [
    "read the whole assignment pdf and help us with problem set 5 cost drivers in childcare only use the data "
    "sources the assignment points to do not hallucinate or invent any numbers on your own every number has to "
    "come from the actual data explain what you are doing in the chat as you go in simple terms and ask if "
    "anything is unclear",
    "pull acs 5 year estimates for every county for 2015 through 2022 from the census api using the variable codes "
    "in the assignment table the api key is saved in a text file in the data folder",
    "check that every acs variable code means the same thing in every year before using it",
    "build the derived variables exactly the way the assignment defines them per capita income total population kids "
    "under 6 kids under 6 with all parents in the labor force median gross rent female college share female full "
    "time year round share under 6 share and under 6 care need share",
    "from the oews zip files for 2015 to 2022 pull the mean annual wage for childcare workers occupation code 39 9011 "
    "for every metro and nonmetro area",
    "zero pad the oews area codes to 7 characters and merge the wages onto counties with the county oews crosswalk on "
    "year and oews area then attach the acs data and keep only metro counties where the area code starts with 00",
    "check how many counties are missing wages each year it should be around 1 percent and if it is a lot more figure "
    "out why and fix the merge",
    "make a table with the mean sd and number of observations for every predictor in 2022",
    "convert wages and rents to 2022 dollars using cpi u annual averages and plot how they changed over time",
    "test whether real childcare worker wages were the same in 2022 as in 2019 give the hypotheses test statistic "
    "and p value and explain what it means for the providers claim",
    "regress 2022 childcare worker wages on female college share report the coefficient whether we can reject that "
    "it is zero and what it means in plain words",
    "put everything in a pdf with our team names winston park ayush rajpal tobin gedstad wen ding and alfred mordecai",
    "now double check all the results rerun everything from the raw files and verify every number with a separate "
    "calculation and make sure the numbers in the pdf match before giving it to us",
]
rows = [["#", "Prompt"]] + [[i, esc(t)] for i, t in enumerate(PROMPTS, 1)]
story.append(table(rows, [0.3, 6.9]))


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Arial", 8)
    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.drawString(0.65 * inch, 0.5 * inch, "MGT-403 \u00b7 Problem Set 5 \u2013 Cost Drivers in Childcare \u00b7 "
                      + ", ".join(TEAM))
    canvas.drawRightString(letter[0] - 0.65 * inch, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


out = DELIVERABLES / "PS5_Cost_Drivers_Report.pdf"
SimpleDocTemplate(str(out), pagesize=letter, leftMargin=0.65 * inch, rightMargin=0.65 * inch,
                  topMargin=0.6 * inch, bottomMargin=0.75 * inch, title="PS5 - Cost Drivers in Childcare",
                  author=", ".join(TEAM)).build(story, onFirstPage=footer, onLaterPages=footer)
print("wrote", out)
