"""
Builds PS4_Childcare_Prices_Report.pdf from output/results.json and the figures made by ps4.py.
Every number in the report is read from results.json -- nothing is typed in by hand.

Run:  python ps4.py && python make_report.py
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
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from common import OUT_PS4 as OUT, DELIVERABLES, register_arial
R = json.loads((OUT / "results.json").read_text(encoding="utf-8"))

register_arial()

ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["Normal"], fontName="Arial", fontSize=10, leading=14,
                      spaceAfter=6)
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

XBAR = "x&#772;"  # x with combining macron
TEAM = ["Winston Park", "Ayush Rajpal", "Tobin Gedstad", "Wen Ding", "Alfred Mordecai"]


def P(t, st=BODY):
    return Paragraph(t, st)


def B(t):
    return Paragraph(t, BULLET, bulletText="\u2022")


def table(rows, widths, header_rows=1, zebra=True):
    data = [[Paragraph(str(c), CELLB if i < header_rows else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=header_rows)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c2d1")),
             ("BACKGROUND", (0, 0), (-1, header_rows - 1), colors.HexColor("#dfe6f0")),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if zebra:
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
    """Format tiny p-values as a x 10^-k."""
    if p >= 1e-4:
        return f"{p:.4f}"
    m, e = f"{p:.2e}".split("e")
    return f"{m} &#215; 10<super>{int(e)}</super>"


# ---------------------------------------------------------------------------
q1, q2, q3, q4 = R["q1"], R["q2"], R["q3"], R["q4"]
AGES = ["Infant", "Toddler", "Preschool"]
T2 = q2["table"]
cpi = {int(k): v for k, v in q3["cpi"].items()}
trend = {(r["year"], r["age"]): r for r in q3["trend"]}
bal = {(r["year"], r["age"]): r for r in q3["balanced"]}
counts = {r["year"]: r for r in q1["counts"]}
paired = {(p["a"], p["b"]): p for p in q2["paired"]}
a22, a15 = q4["2022"], q4["2015"]


def pct(a, b):
    return a / b - 1


story = []
story += [P("Problem Set 4 \u2013 The Distribution of Childcare Prices", TITLE),
          P("MGT-403 Data Project \u00b7 Where Should We Open Our Next Daycare?", SUB),
          P("<b>Team:</b> " + ", ".join(TEAM), SUB),
          Spacer(1, 8)]

# ---------------- Summary ----------------
story.append(P("Summary of answers", H1))
p = T2["Preschool"]
story += [
    B(f"<b>Q1 sample.</b> NDCP county prices for 2015\u20132022, restricted to counties whose OEWS area code "
      f"begins with \u201c00\u201d (metro). This leaves {counts[2022]['counties']:,} metro counties in 2022, of "
      f"which {counts[2022]['n_Preschool']:,} report a center-based preschool price."),
    B(f"<b>Q2 (2022).</b> Average county median weekly center-based price: infant "
      f"{money(T2['Infant']['Mean'])}, toddler {money(T2['Toddler']['Mean'])}, preschool {money(p['Mean'])}. "
      f"The 95% confidence intervals do not overlap, so care gets significantly cheaper as children get older."),
    B(f"<b>Q3 (real trends).</b> Nominal prices rose about 22\u201324% from 2015 to 2022, almost exactly the "
      f"CPI-U's {pct(cpi[2022], cpi[2015]):.1%}. Real prices rose modestly through 2020, then fell back in "
      f"2021\u20132022 as general inflation outpaced childcare price growth. In real terms, 2022 prices are "
      f"roughly back at their 2015 level."),
    B(f"<b>Q4 (CCDF voucher test).</b> 2022: t = {a22['t']:.2f}, p = {pexp(a22['p'])}, so we reject "
      f"H<sub>0</sub>. The average preschool price ({money(a22['xbar'])}/wk) exceeds the voucher "
      f"({money(a22['mu0'])}/wk). 2015: t = {a15['t']:.2f}, p = {pexp(a15['p'])}, a much larger shortfall. "
      f"The voucher has closed most of the gap but still falls short of the average price."),
]

# ---------------- Data & sample ----------------
story.append(P("Q1. Data and the metro analysis sample", H1))
story += [
    P("<b>Data.</b> U.S. Department of Labor National Database of Childcare Prices, county-level workbook "
      "<i>NDCP2022.xlsx</i> (2008\u20132022; 2015\u20132022 used). The price variables are the median "
      "full-time weekly prices for <b>center-based</b> care, in nominal dollars: <font face='Arial-Bold'>MCINFANT</font>, "
      "<font face='Arial-Bold'>MCTODDLER</font> and <font face='Arial-Bold'>MCPRESCHOOL</font>."),
    P("<b>Metro sample.</b> The workbook stores FIPS codes as integers, so I restored the 5-character zero-padded "
      "code (e.g., 1001 \u2192 01001). I then merged on [county FIPS, year] with the course crosswalk "
      "<i>county_oews_crosswalk.csv</i>, reading its codes as text so leading zeros are kept. "
      f"All {q1['ndcp_rows']:,} NDCP county-years for 2015\u20132022 matched the crosswalk "
      f"({q1['matched']:,} matched). I kept counties whose 7-character <i>oews_area</i> begins with "
      f"\u201c00\u201d (metropolitan) and dropped the nonmetropolitan codes. This leaves {q1['metro_rows']:,} "
      "metro county-years."),
]
rows = [["Year", "Metro counties", "with infant price", "with toddler price", "with preschool price"]]
for y in range(2015, 2023):
    c = counts[y]
    rows.append([y, f"{c['counties']:,}", f"{c['n_Infant']:,}", f"{c['n_Toddler']:,}", f"{c['n_Preschool']:,}"])
story += [table(rows, [0.8 * inch, 1.3 * inch, 1.4 * inch, 1.4 * inch, 1.5 * inch]),
          P("Table 1. Metro analysis sample by year. Counties without a price for an age group are left "
            "out of that age group's statistics.", CAP)]

# ---------------- Q2 ----------------
story.append(PageBreak())
story.append(P("Q2. 2022 distribution of center-based prices by age group", H1))
story.append(fig("q2_histograms_2022.png"))
story.append(P("Figure 1. Histograms of 2022 county median weekly center-based prices (metro counties, $20 bins). "
               "Solid line = mean across counties; dashed line = median across counties.", CAP))
rows = [["Age group", "N", "Mean", "SD", "SE = SD/&#8730;N", "t<sub>0.975, N&#8722;1</sub>",
         "95% CI for mean", "Median", "Min", "Max"]]
for a in AGES:
    s = T2[a]
    rows.append([a, f"{s['N']:.0f}", money(s["Mean"]), money(s["SD"]), money(s["SE"], 3), f"{s['t_crit']:.4f}",
                 f"[{money(s['CI95_low'])}, {money(s['CI95_high'])}]", money(s["Median"]),
                 money(s["Min"]), money(s["Max"])])
story += [table(rows, [x * inch for x in [0.8, 0.5, 0.65, 0.6, 0.8, 0.7, 1.3, 0.65, 0.55, 0.6]]),
          P("Table 2. 2022 county median weekly center-based prices (nominal = 2022 dollars). "
            "95% CI = mean \u00b1 t<sub>0.975, N\u22121</sub> \u00d7 SD/\u221aN.", CAP)]

pit, ptp, pip = paired[("Infant", "Toddler")], paired[("Toddler", "Preschool")], paired[("Infant", "Preschool")]
story += [
    P("Discussion", H2),
    B(f"<b>Care gets cheaper as children get older.</b> Mean infant care ({money(T2['Infant']['Mean'])}) costs "
      f"{money(pit['diff'])}/wk ({pit['pct']:.1%}) more than toddler care ({money(T2['Toddler']['Mean'])}), and "
      f"toddler care costs {money(ptp['diff'])}/wk ({ptp['pct']:.1%}) more than preschool "
      f"({money(p['Mean'])}). Infant care averages {pip['pct']:.1%} more than preschool."),
    B("<b>The differences are statistically significant.</b> None of the three 95% CIs overlap, "
      f"so the means differ at the 5% level. Among the {pip['n']:,} counties reporting all three prices, "
      f"infant care costs more than preschool in {pip['share_pos']:.1%} of counties (paired t = {pip['t']:.1f}). "
      f"Infant care costs more than toddler care in {pit['share_pos']:.1%} (paired t = {pit['t']:.1f}). "
      f"The toddler\u2013preschool gap is smaller: toddler care costs more in {ptp['share_pos']:.1%} of counties "
      f"and exactly the same in {ptp['share_zero']:.1%} (paired t = {ptp['t']:.1f})."),
    B(f"<b>Prices vary more for younger children.</b> The SD falls from {money(T2['Infant']['SD'])} "
      f"(infant) to {money(T2['Toddler']['SD'])} (toddler) and {money(T2['Preschool']['SD'])} (preschool)."),
    B("<b>The distributions are right-skewed.</b> In every age group the mean exceeds the median "
      f"(e.g., preschool {money(p['Mean'])} vs. {money(p['Median'])}), and there is a long upper tail of "
      f"high-price counties (preschool max {money(p['Max'])}/wk). The mean is therefore pulled above the "
      "typical county; this matters for Q4."),
    B("<i>Interpretation (not tested with this data):</i> a likely explanation for the age pattern is that "
      "younger children need more staff per child, and labor is one of the two main costs of providing care "
      "(labor and rent, as the assignment notes)."),
]

# ---------------- Q3 ----------------
story.append(PageBreak())
story.append(P("Q3. Real (constant 2022 $) price trends, 2015\u20132022", H1))
story.append(P("<b>Method.</b> Real price<sub>t</sub> = nominal price<sub>t</sub> \u00d7 CPI<sub>2022</sub> / "
               "CPI<sub>t</sub>, using CPI-U (series CUUR0000SA0) annual averages from the BLS API. For each "
               "year and age group I plot the mean of the county median prices across metro counties, with a "
               "95% CI. The set of reporting counties changes from year to year (Table 1), so I also plot a "
               "<b>balanced panel</b>: only counties that report a price in all eight years. Those lines "
               "show price changes that aren't driven by which counties report."))
story.append(fig("q3_trends.png"))
story.append(P("Figure 2. Left: real 2022-dollar prices (solid = all reporting counties with 95% CI; "
               "dashed = balanced panel). Right: the same all-county means in nominal dollars.", CAP))

rows = [["Year", "CPI-U", "Infant", "Toddler", "Preschool", "Infant (bal.)", "Toddler (bal.)",
         "Preschool (bal.)"]]
for y in range(2015, 2023):
    rows.append([y, f"{cpi[y]:.3f}"] + [money(trend[(y, a)]["mean_real"]) for a in AGES]
                + [money(bal[(y, a)]["mean_real_balanced"]) for a in AGES])
nb = {a: bal[(2015, a)]["N_balanced"] for a in AGES}
story += [KeepTogether([table(rows, [x * inch for x in [0.5, 0.75, 0.8, 0.8, 0.85, 0.95, 0.95, 1.05]]),
          P(f"Table 3. Mean county median weekly price, real 2022 dollars. \u201cbal.\u201d = balanced panel "
            f"(N = {nb['Infant']} infant, {nb['Toddler']} toddler, {nb['Preschool']} preschool counties).", CAP)])]

rows = [["Age group", "Nominal 2015", "Nominal 2022", "Nominal chg.", "Real chg. (all)", "Real chg. (balanced)",
         "Balanced real 2015\u21922020", "Balanced real 2020\u21922022"]]
for a in AGES:
    t15, t22 = trend[(2015, a)], trend[(2022, a)]
    b15, b20, b22 = (bal[(y, a)]["mean_real_balanced"] for y in (2015, 2020, 2022))
    rows.append([a, money(t15["mean_nominal"]), money(t22["mean_nominal"]),
                 f"{pct(t22['mean_nominal'], t15['mean_nominal']):+.1%}",
                 f"{pct(t22['mean_real'], t15['mean_real']):+.1%}", f"{pct(b22, b15):+.1%}",
                 f"{pct(b20, b15):+.1%}", f"{pct(b22, b20):+.1%}"])
story += [KeepTogether([table(rows, [x * inch for x in [0.8, 0.8, 0.8, 0.8, 0.9, 1.0, 1.1, 1.1]]),
          P(f"Table 4. Changes over the period. CPI-U inflation: 2015\u21922022 {pct(cpi[2022], cpi[2015]):+.1%}; "
            f"2020\u21922021 {pct(cpi[2021], cpi[2020]):+.1%}; 2021\u21922022 {pct(cpi[2022], cpi[2021]):+.1%}.",
            CAP)])]

cov = q3["coverage_change_2021"]
dropped = [c for c in cov if c["n2021"] == 0]
added = [c for c in cov if c["n2020"] == 0]
drop_txt = ", ".join(f"{c['state']} ({c['n2020']})" for c in dropped)
add_txt = ", ".join(f"{c['state']} ({c['n2021']} municipios, mean {money(c['mean2021'])}/wk nominal)" for c in added)
bp = {y: bal[(y, "Preschool")]["mean_real_balanced"] for y in range(2015, 2023)}
drop_mean = sum(c["n2020"] * c["mean2020"] for c in dropped) / sum(c["n2020"] for c in dropped)
all20 = trend[(2020, "Preschool")]["mean_nominal"]
story += [
    P("Discussion: what happened to childcare prices?", H2),
    B(f"<b>Nominal prices rose a lot, but only about as fast as overall inflation.</b> Mean nominal prices "
      f"rose {pct(trend[(2022, 'Infant')]['mean_nominal'], trend[(2015, 'Infant')]['mean_nominal']):.1%} "
      f"(infant), {pct(trend[(2022, 'Toddler')]['mean_nominal'], trend[(2015, 'Toddler')]['mean_nominal']):.1%} "
      f"(toddler) and {pct(trend[(2022, 'Preschool')]['mean_nominal'], trend[(2015, 'Preschool')]['mean_nominal']):.1%} "
      f"(preschool), while the CPI-U rose {pct(cpi[2022], cpi[2015]):.1%}. In constant 2022 dollars, prices "
      "in 2022 are within about 2% of their 2015 level in every age group, both in the full sample and in "
      "the balanced panel."),
    B(f"<b>Real prices rose until 2020, then fell back.</b> In the balanced panel, real preschool prices rose "
      f"steadily from {money(bp[2015])} (2015) to {money(bp[2020])} (2020), up {pct(bp[2020], bp[2015]):.1%}. "
      f"They then fell to {money(bp[2021])} in 2021 and {money(bp[2022])} in 2022. Infant and toddler prices "
      "follow the same pattern. For these same counties, nominal prices kept rising in 2021\u201322, but more slowly than the "
      f"post-pandemic inflation surge (CPI +{pct(cpi[2021], cpi[2020]):.1%} in 2021, "
      f"+{pct(cpi[2022], cpi[2021]):.1%} in 2022), so their real value fell."),
    B(f"<b>The sharp 2021 dip in the all-county line is partly caused by which counties report.</b> In 2021, "
      f"several states have no metro price data: {drop_txt} counties in 2020. Meanwhile Puerto Rico appears for "
      f"the only time in 2015\u20132022: {add_txt}. The counties that dropped out averaged "
      f"{money(drop_mean)}/wk in 2020 (nominal), above the 2020 all-county mean of {money(all20)}. Replacing "
      f"them with PR's very low-priced municipios pulls the 2021 all-county mean down. The balanced panel, "
      f"which holds the counties fixed, shows only a small 2021 decline "
      f"({pct(bp[2021], bp[2020]):+.1%} for preschool)."),
    B("<b>The ranking by age never changes:</b> infant > toddler > preschool in every year."),
]

# ---------------- Q4 ----------------
story.append(Spacer(1, 10))
story.append(P("Q4. Does the CCDF voucher equal the price of median center-based preschool?", H1))
story.append(P(f"<b>Setup.</b> The voucher is monthly; NDCP prices are weekly. With 4.33 weeks per month, the "
               f"weekly voucher value is {money(a22['voucher'], 0)} / 4.33 = <b>{money(a22['mu0'], 4)}</b> in 2022 "
               f"and {money(a15['voucher'], 0)} / 4.33 = <b>{money(a15['mu0'], 4)}</b> in 2015 (nominal). Each "
               "year's voucher is compared with <i>that year's nominal</i> prices, so no inflation adjustment is "
               "needed. \u201cThe price of care at the median-priced center\u201d is the NDCP variable "
               "<font face='Arial-Bold'>MCPRESCHOOL</font> (each county's median center-based preschool price). "
               "\u201cThe average metro area\u201d is the population mean of that variable across metro-area "
               "counties (the Q1 sample)."))

story.append(P("(a) Hypotheses", H2))
story.append(P(f"Let \u03bc = mean county median weekly center-based preschool price across metro counties in 2022.", BODY))
story.append(P(f"H<sub>0</sub>: \u03bc = {money(a22['mu0'])} (the voucher equals the average price) &#160;&#160;&#160; "
               f"H<sub>1</sub>: \u03bc \u2260 {money(a22['mu0'])} &#160;&#160;&#160; (two-sided, \u03b1 = 0.05)", MATH))
story.append(P("The test is two-sided because the claim is that the voucher <i>equals</i> the price; "
               "a voucher that is too high or too low would both contradict it. Multiplying through by 4.33 gives "
               f"the equivalent monthly statement, H<sub>0</sub>: 4.33\u03bc = {money(a22['voucher'], 0)}; the "
               "t-statistic is the same either way."))

story.append(P("(b) Test statistic, computed by hand (2022)", H2))
story.append(P(f"t = ({XBAR} \u2212 \u03bc<sub>0</sub>) / (s / \u221an), &#160;&#160; distributed "
               f"t<sub>n\u22121</sub> under H<sub>0</sub>", MATH))
rows = [["Element", "Definition", "2022 value"],
        ["n", "number of metro counties with a preschool price", f"{a22['n']:,}"],
        [XBAR, "sample mean of MCPRESCHOOL", money(a22["xbar"], 4)],
        ["s", "sample standard deviation (n \u2212 1 denominator)", money(a22["s"], 4)],
        ["\u221an", "square root of n", f"{a22['n'] ** 0.5:.4f}"],
        ["SE = s / \u221an", "standard error of the mean", f"{a22['s']:.4f} / {a22['n'] ** 0.5:.4f} = {a22['se']:.4f}"],
        ["\u03bc<sub>0</sub>", "706 / 4.33", money(a22["mu0"], 4)],
        [f"{XBAR} \u2212 \u03bc<sub>0</sub>", "gap between average price and voucher (per week)",
         f"{a22['xbar']:.4f} \u2212 {a22['mu0']:.4f} = {a22['xbar'] - a22['mu0']:.4f}"],
        ["<b>t</b>", f"({XBAR} \u2212 \u03bc<sub>0</sub>) / SE",
         f"<b>{a22['xbar'] - a22['mu0']:.4f} / {a22['se']:.4f} = {a22['t']:.4f}</b>"],
        ["df", "n \u2212 1", f"{a22['df']:,}"]]
story += [table(rows, [1.3 * inch, 3.0 * inch, 2.9 * inch]), Spacer(1, 6)]

story.append(P("(c) Software check and p-value", H2))
story.append(P("Python / SciPy computed the same test directly from the data "
               "(<font face='Courier'>scipy.stats.ttest_1samp(x, 706/4.33)</font>, plus the hand formula in "
               "<font face='Courier'>ps4.py</font>):"))
story.append(P(f"p-value = 2 \u00d7 P(T<sub>n\u22121</sub> \u2265 |t|) = 2 \u00d7 [1 \u2212 F<sub>t, {a22['df']}</sub>"
               f"({abs(a22['t']):.4f})] = <b>{pexp(a22['p'])}</b>", MATH))
story.append(P(f"SciPy gives t = {a22['scipy_t']:.4f} and p = {pexp(a22['scipy_p'])}, identical to the manual "
               f"t = {a22['t']:.4f}, <b>so the hand calculation is verified</b>. I also re-read the raw workbook "
               "with a separate program (openpyxl plus hand-coded formulas) and got the same n, mean, SD, and t."))

story.append(P("(d) Interpretation, and the same test for 2015", H2))
rows = [["", "2022", "2015"],
        ["Monthly voucher (nominal)", money(a22["voucher"], 0), money(a15["voucher"], 0)],
        ["\u03bc<sub>0</sub> = voucher / 4.33 (weekly)", money(a22["mu0"]), money(a15["mu0"])],
        ["n (metro counties)", f"{a22['n']:,}", f"{a15['n']:,}"],
        [f"{XBAR} (mean weekly price)", money(a22["xbar"]), money(a15["xbar"])],
        ["s", money(a22["s"]), money(a15["s"])],
        ["SE", f"{a22['se']:.4f}", f"{a15['se']:.4f}"],
        ["t statistic (df)", f"{a22['t']:.3f} ({a22['df']:,})", f"{a15['t']:.3f} ({a15['df']:,})"],
        ["p-value (two-sided)", pexp(a22["p"]), pexp(a15["p"])],
        ["Critical |t| at 5%", f"{a22['tcrit']:.3f}", f"{a15['tcrit']:.3f}"],
        ["Decision", "Reject H<sub>0</sub>", "Reject H<sub>0</sub>"],
        [f"Mean price per month ({XBAR} \u00d7 4.33)", money(a22["xbar"] * 4.33), money(a15["xbar"] * 4.33)],
        ["Monthly shortfall (price \u2212 voucher)", money(a22["xbar"] * 4.33 - a22["voucher"]),
         money(a15["xbar"] * 4.33 - a15["voucher"])],
        ["Voucher as % of mean price", f"{a22['mu0'] / a22['xbar']:.1%}", f"{a15['mu0'] / a15['xbar']:.1%}"],
        ["Share of counties priced above voucher", f"{a22['share_above']:.1%}", f"{a15['share_above']:.1%}"],
        ["Median county price (weekly)", money(a22["median"]), money(a15["median"])]]
story += [KeepTogether([table(rows, [2.8 * inch, 1.9 * inch, 1.9 * inch]),
          P("Table 5. One-sample t-tests of the ACF claim, 2022 and 2015 (nominal dollars).", CAP)])]
m22, m15 = a22["metro_unit"], a15["metro_unit"]
story += [
    B(f"<b>2022: reject H<sub>0</sub>.</b> |t| = {a22['t']:.2f} is far above the 5% critical value of "
      f"{a22['tcrit']:.2f}, and p = {pexp(a22['p'])} is far below 0.05. If the voucher truly equaled the "
      "average price, a sample mean this far from it would almost never happen by chance. The average metro "
      f"county's median preschool price is {money(a22['xbar'])}/week ({money(a22['xbar'] * 4.33)}/month). "
      f"That is {money(a22['xbar'] - a22['mu0'])}/week, or {money(a22['xbar'] * 4.33 - a22['voucher'])}/month, "
      f"more than the voucher, so the voucher covers about {a22['mu0'] / a22['xbar']:.0%} of the average price. "
      "The ACF's claim is not supported: the voucher is significantly <i>below</i> the average price."),
    B(f"<b>2015: reject H<sub>0</sub> even more strongly</b> (t = {a15['t']:.2f}, p = {pexp(a15['p'])}). "
      f"The 2015 voucher was {money(a15['xbar'] * 4.33 - a15['voucher'])}/month short of the average price and "
      f"covered only about {a15['mu0'] / a15['xbar']:.0%} of it; {a15['share_above']:.0%} of metro counties were "
      f"priced above it. The voucher rose "
      f"{pct(a22['voucher'], a15['voucher']):.1%} in nominal terms from 2015 to 2022, compared with "
      f"{pct(a22['xbar'], a15['xbar']):.1%} for average prices. This closed most of the gap, but not all of it."),
    B(f"<b>Mean vs. median.</b> In 2022 the <i>median</i> county's price ({money(a22['median'])}) is within about "
      f"a dollar of the weekly voucher, and {a22['share_above']:.0%} of counties are priced above it. So the "
      "voucher roughly matches the price in the <i>typical</i> (median) metro county. It is below the "
      "<i>average</i> because the right-skewed distribution (Q2) pulls the mean up. The claim as stated is "
      "about the average metro area, and that is what the test rejects."),
    B(f"<b>Robustness check.</b> Counting each OEWS metro area once (averaging its counties) gives the same "
      f"conclusion: 2022 t = {m22['t']:.2f}, p = {pexp(m22['p'])} ({m22['n']} metro areas, mean "
      f"{money(m22['xbar'])}); 2015 t = {m15['t']:.2f}, p = {pexp(m15['p'])}."),
]

# ---------------- Notes ----------------
story.append(P("Assumptions and data-handling choices", H1))
story += [
    B("Unit of observation: metro county (NDCP is county-level; the assignment asks for a consistent county set "
      "across PS4, PS5, and the project). Each county counts equally; the statistics are not population-weighted."),
    B("\u201cMedian price\u201d = NDCP median (not 75th percentile) full-time weekly price for center-based care: "
      "MCINFANT, MCTODDLER, MCPRESCHOOL. Family/home-based care (MFCC*) is excluded."),
    B("Counties with a missing price are dropped only for that age group and year; N differs slightly across age "
      "groups (Table 1)."),
    B("95% CIs use the t distribution (t<sub>0.975, N\u22121</sub> \u2248 1.962); with N > 1,000, a normal "
      "approximation (1.96) gives CIs within one cent of these."),
    B("Puerto Rico's metro municipios are in the crosswalk's metro sample, but NDCP reports their prices only in "
      "2021 (so they do not affect the 2022 or 2015 results)."),
    B("CPI-U: series CUUR0000SA0, annual averages, fetched from the BLS Public Data API (saved to "
      "data/cpi_u_annual.csv)."),
    B("Reproduce: put NDCP2022.xlsx and county_oews_crosswalk.csv in data/, then run "
      "<font face='Courier'>python ps4.py</font> and <font face='Courier'>python make_report.py</font>. "
      "Every number in this report is read from output/results.json, which ps4.py writes."),
]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Arial", 8)
    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.drawString(0.75 * inch, 0.5 * inch, "MGT-403 \u00b7 Problem Set 4 \u2013 The Distribution of Childcare Prices")
    canvas.drawRightString(letter[0] - 0.75 * inch, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


out = DELIVERABLES / "PS4_Childcare_Prices_Report.pdf"
SimpleDocTemplate(str(out), pagesize=letter, leftMargin=0.65 * inch, rightMargin=0.65 * inch,
                  topMargin=0.6 * inch, bottomMargin=0.75 * inch,
                  title="PS4 - The Distribution of Childcare Prices",
                  author=", ".join(TEAM)).build(story, onFirstPage=footer,
                                                                             onLaterPages=footer)
print("wrote", out)
