// Builds Daycare_Expansion_Deck.pptx from output/results.json and the figures made by project.py.
// Run:  node src/step7_final_deck.js   (after step 5; or python run_all.py)
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const OUT = path.join(__dirname, "..", "outputs", "final");
const R = JSON.parse(fs.readFileSync(path.join(OUT, "results.json"), "utf8"));
const FILE = path.join(__dirname, "..", "deliverables", "Daycare_Expansion_Deck.pptx");

// ---------- theme: Yale blue shades on white ----------
const THEME = {
  name: "Yale Blue",
  headFontFace: "Cambria",
  bodyFontFace: "Arial",
  colors: {
    dk1: "222222", lt1: "FFFFFF", dk2: "00356B", lt2: "EEF4FB",
    accent1: "00356B", accent2: "286DC0", accent3: "63AAFF", accent4: "C9DDF5",
    accent5: "4A4A4A", accent6: "978D85", hlink: "286DC0", folHlink: "00356B",
  },
};
const HEX = { yale: "00356B", mid: "286DC0", light: "63AAFF", pale: "C9DDF5", tint: "EEF4FB", grey: "4A4A4A", lgrey: "8A8A8A" };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Where should we open our next daycare?";
pres.author = "MGT-403 Data Project team";
const C = pres.SchemeColor;

const FOOT = "MGT-403 Data Project  |  Sources: DOL National Database of Childcare Prices 2015-22, BLS OEWS (SOC 39-9011), Census ACS 5-year; CPI-U, 2022 $";
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: "FFFFFF" },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 12.33, h: 0.85, fontFace: "Cambria",
        fontSize: 28, bold: true, color: C.text2, align: "left", valign: "middle", margin: 0 }, text: "" } },
    { text: { text: FOOT, options: { x: 0.5, y: 7.05, w: 11.3, h: 0.3, fontSize: 9, color: C.accent5, fontFace: "Arial", margin: 0 } } },
  ],
  slideNumber: { x: 12.33, y: 7.05, w: 0.5, h: 0.3, fontSize: 9, color: C.accent5, fontFace: "Arial", align: "right" },
});
pres.defineSlideMaster({ title: "TITLE", background: { color: "FFFFFF" }, objects: [] });

// ---------- helpers ----------
function pngSize(f) { const b = fs.readFileSync(f); return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; }
const fmt$ = (v, d = 0) => "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (v, d = 0) => (100 * v).toFixed(d) + "%";
const top = R.top10;
const short = (n) => n.replace(" County", "").replace(" Municipality", "");
const metro = (a) => a.split(",")[0].split("-")[0];

// Confidence: how many of the four alternative scoring rules keep the county in the top 10
const ALT = ["Log model (% premium)", "2022 premium only", "Survey years only", "Within-state premium (state FE)"];
top.forEach((t) => { t.kept = ALT.filter((k) => R.robust_sets[k].includes(t.county_fips)).length; });
const conf = (k) => (k === 4 ? "High" : k === 3 ? "Medium" : "Watch");
const nAll4 = top.filter((t) => t.kept === 4).length;
// Price evidence (NDCP imputation codes) behind each pick, from project.py
const EV = Object.fromEntries(R.evidence.map((e) => [e.county_fips, e]));
const est22 = (t) => EV[t.county_fips].est_2022;          // 2022 price is a between-survey estimate (code 5)
const nEst = top.filter(est22).length;
const svYears = [...new Set(top.filter(est22).map((t) => EV[t.county_fips].survey_year))].sort().join(", ");
const allSvPos = top.filter(est22).every((t) => EV[t.county_fips].survey_prem > 0);
const sgn$ = (v) => (v < 0 ? "−$" : "+$") + Math.abs(Math.round(v)).toLocaleString("en-US");
const pct4 = top.filter((t) => EV[t.county_fips].pctile_imputed_2022);   // states flagged for percentile imputation
const dirStr = pct4.map((t) => `${short(t.NAME).replace(/, (\w+)$/, "")} ${sgn$(EV[t.county_fips].direct_prem)} (${EV[t.county_fips].direct_year})`).join(", ");

const avg = (a) => a.reduce((s, x) => s + x, 0) / a.length;
const premAvg = avg(top.map((t) => t.prem));
const predAvg = avg(top.map((t) => t.pred));
const paths = R.stability.top10_paths;
const yrAvg = (y) => avg(Object.values(paths).map((p) => p[y]).filter((v) => v !== null));
const bt = R.backtest, cv = R.cv, st = R.stability;
const lag = st.lag;

function stat(slide, x, y, w, h, big, label, name) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: C.background2 }, line: { color: C.background2 },
    rectRadius: 0.08, objectName: name + " card" });
  slide.addText(big, { x: x + 0.25, y: y + 0.15, w: w - 0.5, h: 0.75, fontFace: "Cambria", fontSize: 32, bold: true,
    color: C.accent1, margin: 0, valign: "middle", isTextBox: true, objectName: name + " value" });
  slide.addText(label, { x: x + 0.25, y: y + 0.92, w: w - 0.5, h: h - 1.05, fontSize: 13, color: C.text1, margin: 0,
    valign: "top", isTextBox: true, objectName: name + " label" });
}

// =====================================================================
// Slide 1 -- Title + executive summary
// =====================================================================
pres.addSection({ title: "Summary" });
let s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Summary" });
s.addText("MGT-403 DATA PROJECT  ·  RECOMMENDATION TO THE STRATEGY GROUP", { x: 0.6, y: 0.55, w: 12, h: 0.35, fontSize: 13,
  bold: true, color: C.accent2, charSpacing: 2, margin: 0, isTextBox: true, objectName: "kicker" });
s.addText("Where should we open our next preschools?", { x: 0.6, y: 1.0, w: 12, h: 0.95, fontFace: "Cambria", fontSize: 40,
  bold: true, color: C.text2, margin: 0, isTextBox: true, objectName: "deck title" });
s.addText("Ten metro counties where center-based preschool prices run well above what local childcare wages and rents predict, and have stayed there",
  { x: 0.6, y: 1.95, w: 11.6, h: 0.85, fontSize: 18, color: C.accent5, margin: 0, isTextBox: true, objectName: "subtitle" });
const cw = 3.85, cg = 0.39, cy = 3.15, ch = 2.05;
stat(s, 0.6, cy, cw, ch, "+" + fmt$(premAvg) + " / week",
  `Average 2022 premium of our 10 picks over the price their local wages and rents predict (${fmt$(top.reduce((a, t) => a + t.MCPRESCHOOL, 0) / 10)} actual vs ${fmt$(predAvg)} predicted, +${pct(premAvg / predAvg)})`, "premium");
stat(s, 0.6 + cw + cg, cy, cw, ch, `${R.funnel.scored_2022.toLocaleString()} → ${R.funnel.size} → 10`,
  "Metro counties scored, counties passing every screen (persistence, county-specific price, market size), and picks (one per metro)", "funnel");
stat(s, 0.6 + 2 * (cw + cg), cy, cw, ch, "+" + fmt$(bt.picks_prem_2022_mean) + " / week",
  `Back-test: of the 10 counties picked with 2015-18 data, the ${bt.n_with_2022} with 2022 prices were ${fmt$(bt.picks_prem_2022_mean)} above prediction in 2022 on average; all ${bt.n_with_2022} above it`, "backtest");
s.addText([
  { text: "Lead markets: ", options: { bold: true, color: C.accent1 } },
  { text: top.filter((t) => t.kept === 4).map((t) => short(t.NAME).replace(/, (\w+)$/, "")).join(", ") + " counties: " },
  { text: `the ${nAll4} picks that stay in the top 10 under every alternative scoring rule we tried.` },
], { x: 0.6, y: 5.5, w: 12.1, h: 0.6, fontSize: 15, color: C.text1, margin: 0, isTextBox: true, objectName: "bottom line" });
s.addText("Team: Winston Park, Ayush Rajpal, Tobin Gedstad, Wen Ding, Alfred Mordecai", { x: 0.6, y: 6.55, w: 9, h: 0.35,
  fontSize: 12, color: C.accent5, margin: 0, isTextBox: true, objectName: "team" });
s.addText(FOOT.replace("MGT-403 Data Project  |  ", "") + "  |  Code and data: github.com/ayush-rajpal/mgt403-daycare-location", { x: 0.6, y: 6.9, w: 12.1, h: 0.3, fontSize: 9, color: C.accent5,
  margin: 0, isTextBox: true, objectName: "sources" });
s.addNotes(
  `Bottom line: we recommend ten metro counties where families pay far more for center-based preschool than local labor and rent costs would predict. ` +
  `"Attractive" means a high price relative to cost, so we model price as a function of childcare-worker wages and median gross rent, and rank counties on the gap. The gap is not a profit figure: it measures pricing power relative to local cost conditions. ` +
  `On average our picks charge ${fmt$(premAvg)} a week more than their wages and rents predict. We screened ${R.funnel.scored_2022} metro counties with 2022 prices; ` +
  `${R.funnel.size} passed every screen; we take the best county in each of ten different metros. A back-test shows the approach would have worked if we had run it in 2018.`);

// =====================================================================
// Slide 2 -- (a) Top-10 list + map
// =====================================================================
pres.addSection({ title: "Recommendation" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Recommendation" });
s.addText("Ten counties where prices exceed what local wages and rents predict", { placeholder: "title" });
const hdr = (t, al = "center") => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.yale }, align: al, valign: "middle" } });
const rows = [[hdr("#"), hdr("County", "left"), hdr("Metro area", "left"), hdr("2022 price"), hdr("Predicted"), hdr("Premium"), hdr("Confi-dence")]];
top.forEach((t, i) => {
  const f = { fill: { color: i % 2 ? "FFFFFF" : HEX.tint } };
  rows.push([
    { text: String(t.rank), options: { ...f, align: "center", bold: true, color: HEX.yale } },
    { text: short(t.NAME).replace(/, (\w+)$/, ", ") + t.state_abbr, options: { ...f, bold: true } },
    { text: metro(t.area_title), options: { ...f } },
    { text: fmt$(t.MCPRESCHOOL) + (est22(t) ? "*" : ""), options: { ...f, align: "right" } },
    { text: fmt$(t.pred), options: { ...f, align: "right" } },
    { text: "+" + fmt$(t.prem), options: { ...f, align: "right", bold: true, color: HEX.yale } },
    { text: conf(t.kept), options: { ...f, align: "center", color: t.kept === 4 ? HEX.yale : t.kept === 3 ? HEX.mid : HEX.lgrey, bold: t.kept === 4 } },
  ]);
});
s.addTable(rows, { x: 0.5, y: 1.35, w: 6.75, colW: [0.35, 1.7, 1.25, 0.8, 0.95, 0.8, 0.9], fontSize: 11, fontFace: "Arial", valign: "middle",
  color: "222222", border: { type: "solid", pt: 0.5, color: "D6E2F0" }, rowH: 0.36, margin: [0.03, 0.06, 0.03, 0.06],
  objectName: "top-10 table" });
const mp = pngSize(path.join(OUT, "fig_map_premium.png"));
s.addImage({ path: path.join(OUT, "fig_map_premium.png"), x: 7.45, y: 1.35, w: 5.4, h: 5.4 * mp.h / mp.w, objectName: "premium map" });
s.addText("Map: average 2019-22 premium over predicted price for each metro county; numbers mark our picks.",
  { x: 7.45, y: 1.45 + 5.4 * mp.h / mp.w, w: 5.4, h: 0.45, fontSize: 10, color: C.accent5, italic: true, margin: 0, isTextBox: true, objectName: "map caption" });
s.addText([
  { text: "Premium", options: { bold: true } },
  { text: " = actual median weekly center-based preschool price minus the price predicted from local childcare-worker wages and median gross rent: pricing power relative to those cost conditions, not a profit figure. Ranked on the 2019-22 average; table shows 2022. " },
  { text: "Confidence", options: { bold: true } },
  { text: " = stays in the top 10 under all 4 alternative scoring rules (High), 3 of 4 (Medium), or fewer (Watch). " },
  { text: "*", options: { bold: true } },
  { text: ` 2022 price is an NDCP estimate between state surveys (${nEst} of 10 picks; latest actual survey ${svYears}): confirm with a field price check.` },
], { x: 0.5, y: 5.45, w: 6.75, h: 1.45, fontSize: 10, color: C.accent5, margin: 0, isTextBox: true, objectName: "table note" });
const nxt = R.next10.slice(0, 3).map((t) => short(t.NAME));
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.45, y: 5.15, w: 5.4, h: 1.6, fill: { color: C.background2 }, line: { color: C.background2 },
  rectRadius: 0.08, objectName: "beyond top-10 card" });
s.addText([
  { text: "Next in line: ", options: { bold: true, color: C.accent1 } },
  { text: nxt.join("; ") + " (ranks 11-13).", options: { breakLine: true } },
  { text: "Verify-first: ", options: { bold: true, color: C.accent1 } },
  { text: "Arlington VA, Rochester & Twin Cities MN, Milwaukee & Madison WI show large premiums, but their 2022 prices are shared rate-zone prices or propensity-score estimates, not county-specific." },
], { x: 7.65, y: 5.25, w: 5.0, h: 1.4, fontSize: 12, color: C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: "beyond top-10 text" });
s.addNotes(
  `These are our ten recommendations, one per metro area so that we are not betting twice on the same labor and rental market. ` +
  `The gap between the actual price and the predicted price ranges from ${fmt$(top[9].prem)} to ${fmt$(top[0].prem)} a week in 2022. ` +
  `Six counties are 'High' confidence: they stay in the top ten whether we measure the premium in dollars or percent, use 2022 only, use survey years only, or compare only within the same state. ` +
  `Worcester and Washtenaw are weaker and could be swapped for the next in line. ` +
  `Prices marked with an asterisk are NDCP estimates for a year between state surveys${allSvPos ? `; those counties' latest actual surveys (${svYears}) also showed premiums` : ""}, but they should be confirmed with a field price check. ` +
  `The verify-first list has large premiums but no county-specific price, so we would not commit before a field price survey.`);

// =====================================================================
// Slide 3 -- (b) Methodology and reliability
// =====================================================================
pres.addSection({ title: "Method" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("Method: predict price from local wages and rent, then rank the gap", { placeholder: "title" });
const m22 = R.yr_models["2022"];
const steps = [
  ["Build the panel", `Metro counties x 2015-22: NDCP median center-based preschool price, OEWS childcare-worker wage (metro level), ACS rent and demand; all in 2022 dollars. ${R.q1.rows.toLocaleString()} county-years.`],
  ["Price model, each year", `price = a + b·wage + c·rent (OLS). 2022: price = ${m22.a.toFixed(0)} + ${m22.b_wage.toFixed(1)}×wage($000) + ${m22.b_rent.toFixed(1)}×rent($100); R² = ${m22.r2.toFixed(2)}.`],
  ["Score the premium", "Premium = actual − predicted price. Score = average premium 2019-22, so one noisy year cannot carry a county."],
  ["Screen and pick", `Above the prediction in every observed year 2019-22 (≥ 3 of 4); a county-specific price (no shared rate-zone price or state-level / propensity-score imputation; NDCP between-survey estimates kept); ≥ ${R.rules.min_kids.toLocaleString()} under-6 kids with working parents. Best county per metro.`],
];
steps.forEach(([h, d], i) => {
  const y = 1.33 + i * 1.07;
  s.addShape(pres.shapes.OVAL, { x: 0.5, y: y + 0.05, w: 0.5, h: 0.5, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: `step ${i + 1} circle` });
  s.addText(String(i + 1), { x: 0.5, y: y + 0.05, w: 0.5, h: 0.5, fontSize: 18, bold: true, color: "FFFFFF", align: "center", valign: "middle",
    margin: 0, isTextBox: true, objectName: `step ${i + 1} number` });
  s.addText([{ text: h, options: { bold: true, color: C.accent1, fontSize: 15, breakLine: true } }, { text: d, options: { fontSize: 13 } }],
    { x: 1.2, y, w: 5.6, h: i === 3 ? 1.35 : 1.02, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: `step ${i + 1} text` });
});
s.addText("Back-test: rank with 2015-18 data, check 2022", { x: 7.2, y: 1.35, w: 5.6, h: 0.4, fontSize: 15, bold: true,
  color: C.accent1, margin: 0, isTextBox: true, objectName: "backtest header" });
s.addImage({ path: path.join(OUT, "fig_backtest_deciles.png"), x: 7.2, y: 1.8, w: 5.6, h: 5.6 * 840 / 1280, objectName: "backtest chart" });
const chips = [
  [cv["Wage + rent (cost model)"].r2_oos.toFixed(2), `out-of-sample R² (5-fold, whole metros held out) vs ${cv["Wage + rent (cost model)"].r2_in.toFixed(2)} in sample: little sign of overfitting`],
  ["+" + fmt$(bt.picks_prem_2022_mean), `avg 2022 premium of the 2018 picks that still had prices (${bt.n_with_2022} of 10, all above prediction)`],
  [`${R.robust["Survey years only"].overlap}/10`, "picks unchanged when we drop interpolated years or compare only within each state"],
];
chips.forEach(([v, l], i) => {
  const x = 0.5 + i * 4.18;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 5.95, w: 3.95, h: 0.95, fill: { color: C.background2 }, line: { color: C.background2 },
    rectRadius: 0.08, objectName: `chip ${i + 1}` });
  s.addText([{ text: v + "  ", options: { fontFace: "Cambria", fontSize: 22, bold: true, color: C.accent1 } },
    { text: l, options: { fontSize: 11, color: C.text1 } }],
    { x: x + 0.15, y: 5.98, w: 3.7, h: 0.9, margin: 0, valign: "middle", isTextBox: true, objectName: `chip ${i + 1} text` });
});
s.addNotes(
  `We fit a simple price model every year: price on childcare-worker wages and median gross rent, both in 2022 dollars. In 2022 it explains ${pct(m22.r2)} of the variation in prices. ` +
  `The residual is the premium: how much more families pay than local wages and rents would predict. It measures pricing power, not actual operating cost or profit. We average it over 2019-22 and apply four screens. ` +
  `Reliability: holding out whole metro areas, the model still explains ${pct(cv["Wage + rent (cost model)"].r2_oos)} of prices. ` +
  `The back-test is the key evidence: counties in the top decile of premium in 2015-18 were still about ${fmt$(bt.deciles[9].prem2022)} above their predicted price in 2022, while the bottom decile stayed about ${fmt$(-bt.deciles[0].prem2022)} below it. ` +
  `Of the ten counties our rules would have picked in 2018, the ${bt.n_with_2022} that still had 2022 price data averaged ${fmt$(bt.picks_prem_2022_mean)} above their predicted price in 2022, and all were above it; the other ${10 - bt.n_with_2022} are in states with no usable 2022 county prices.`);

// =====================================================================
// Slide 4 -- (c) Market characteristics
// =====================================================================
pres.addSection({ title: "Market characteristics" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Market characteristics" });
s.addText("Winning markets: affluent, highly educated, with deep demand", { placeholder: "title" });
const P = R.profile;
const prow = (lab, k, f) => [lab, f(P[k]["Top 10 (mean)"]), f(P[k]["All metro counties (mean)"])];
const ptab = [
  prow("Weekly preschool price", "Weekly preschool price ($)", (v) => fmt$(v)),
  prow("Predicted price (wages + rent)", "Predicted price ($)", (v) => fmt$(v)),
  prow("Childcare-worker wage", "Childcare-worker wage ($/yr)", (v) => fmt$(v)),
  prow("Median gross rent / month", "Median gross rent ($/mo)", (v) => fmt$(v)),
  prow("Per-capita income", "Per-capita income ($)", (v) => fmt$(v)),
  prow("Women 25+ with bachelor's+", "Women 25+ w/ bachelor's+", (v) => pct(v)),
  prow("Under-6 kids, all parents working", "Under-6 needing care (#)", (v) => Math.round(v).toLocaleString()),
];
const prof = [[hdr("2022 averages", "left"), hdr("Our 10 picks"), hdr("All metro counties")]].concat(
  ptab.map((r, i) => r.map((c, j) => ({ text: c, options: { fill: { color: i % 2 ? "FFFFFF" : HEX.tint }, align: j ? "right" : "left",
    bold: j === 1, valign: "middle", color: j === 1 ? HEX.yale : "222222" } }))));
s.addTable(prof, { x: 0.5, y: 1.4, w: 6.1, colW: [2.9, 1.5, 1.7], fontSize: 13, fontFace: "Arial", valign: "middle", border: { type: "solid", pt: 0.5, color: "D6E2F0" },
  rowH: 0.42, margin: [0.03, 0.08, 0.03, 0.08], objectName: "profile table" });
s.addText("What predicts a premium? (2022 OLS, standardized)", { x: 7.0, y: 1.35, w: 5.85, h: 0.4, fontSize: 15, bold: true,
  color: C.accent1, margin: 0, isTextBox: true, objectName: "chars header" });
s.addImage({ path: path.join(OUT, "fig_characteristics.png"), x: 7.0, y: 1.8, w: 5.85, h: 5.85 * 760 / 1280, objectName: "characteristics chart" });
s.addText(`Dark bars are significant at 5% (SEs clustered by metro). Female college share is the most robust signal; it holds within states too. Together these explain only ${pct(R.chars.r2)} of the premium, so they guide where to look next rather than replace the measured premium.`,
  { x: 7.0, y: 5.35, w: 5.85, h: 0.85, fontSize: 11, color: C.accent5, margin: 0, isTextBox: true, objectName: "chars caption" });
s.addText([
  { text: "We screen on:  ", options: { bold: true, color: C.accent1 } },
  { text: "(1) premium over the wage-and-rent price prediction  (2) persistence 2019-22  (3) county-specific prices  (4) ≥ 2,000 under-6 children with working parents.  " },
  { text: "Next-wave signal: ", options: { bold: true, color: C.accent1 } },
  { text: "(5) college-educated, higher-income families." },
], { x: 0.5, y: 6.3, w: 12.35, h: 0.6, fontSize: 13, color: C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: "chosen characteristics" });
s.addNotes(
  `Our picks are not just expensive markets; they are expensive relative to what their wages and rents predict. Their average price is ${fmt$(P["Weekly preschool price ($)"]["Top 10 (mean)"])} vs ${fmt$(P["Weekly preschool price ($)"]["All metro counties (mean)"])}, but their wages and rents predict only ${fmt$(P["Predicted price ($)"]["Top 10 (mean)"])}. ` +
  `They have much higher per-capita income and a much higher share of college-educated women (${pct(P["Women 25+ w/ bachelor's+"]["Top 10 (mean)"])} vs ${pct(P["Women 25+ w/ bachelor's+"]["All metro counties (mean)"])}), which signals willingness to pay for quality early education. ` +
  `In a regression of the premium on demand characteristics, female college share is positive and significant, and remains so within states; the share of young children who need care is also positive. ` +
  `But these explain only about ${pct(R.chars.r2)} of the premium, which is why the premium itself is our first screen.`);

// =====================================================================
// Slide 5 -- (d) Stability over time
// =====================================================================
pres.addSection({ title: "Stability" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Stability" });
s.addText("Premiums persist, so today's gap is a reasonable guide to tomorrow's", { placeholder: "title" });
s.addImage({ path: path.join(OUT, "fig_stability.png"), x: 0.6, y: 1.3, w: 12.1, h: 12.1 * 840 / 2200, objectName: "stability chart" });
const tk = [
  [`${lag[0].corr_all.toFixed(2)} → ${lag[6].corr_all.toFixed(2)}`, `correlation of county premiums 1 → 7 years apart; survey years only: ${lag[0].corr_survey.toFixed(2)} → ${lag[6].corr_survey.toFixed(2)}, a similar pattern`],
  [pct(st.top_q_stay), `of top-fifth counties in 2015-18 were still top-fifth in 2019-22 (${pct(st.top_q_top2)} in the top two-fifths)`],
  [`${fmt$(yrAvg("2015"))} → ${fmt$(yrAvg("2022"))}`, "average premium of our picks, 2015 → 2022: the gap has widened, not closed"],
];
tk.forEach(([v, l], i) => {
  const x = 0.6 + i * 4.1;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 6.0, w: 3.85, h: 0.95, fill: { color: C.background2 }, line: { color: C.background2 },
    rectRadius: 0.08, objectName: `takeaway ${i + 1}` });
  s.addText([{ text: v + "  ", options: { fontFace: "Cambria", fontSize: 20, bold: true, color: C.accent1 } },
    { text: l, options: { fontSize: 11, color: C.text1 } }],
    { x: x + 0.15, y: 6.02, w: 3.6, h: 0.9, margin: 0, valign: "middle", isTextBox: true, objectName: `takeaway ${i + 1} text` });
});
s.addNotes(
  `Is a high premium a lasting feature of a market or a one-year blip? County premiums are highly persistent: the correlation is ${lag[0].corr_all.toFixed(2)} one year apart and still ${lag[6].corr_all.toFixed(2)} seven years apart. ` +
  `Because NDCP fills in some years between state surveys, we repeated this with survey years only, and persistence is similar. ` +
  `${pct(st.top_q_stay)} of counties in the top fifth in 2015-18 were still in the top fifth in 2019-22. ` +
  `Our ten picks have been above their predicted price every year since 2019, and their average premium rose from about ${fmt$(yrAvg("2015"))} to ${fmt$(yrAvg("2022"))}. ` +
  `One pick dipped slightly below the line in 2017, which is why we score on recent years.`);

// =====================================================================
// Slide 6 -- (e) What the model is missing / next steps
// =====================================================================
pres.addSection({ title: "Next steps" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Next steps" });
s.addText("Before committing capital: what our model does not yet see", { placeholder: "title" });
const cards = [
  ["Competition and capacity", "Number of licensed centers, waitlists and vacancies. A premium can signal a shortage that rivals are already moving to fill."],
  ["Public pre-K and subsidies", "Expanding state pre-K and CCDF voucher rates can cap what families pay, especially for 4-year-olds."],
  ["State rules and true labor cost", `Staff-to-child ratios, licensing and benefits differ by state. ${pct(R.prem_between_state_share)} of the premium's variation is between states, partly rules and partly survey methods.`],
  ["Commercial real estate", "We use residential rent as a proxy. Lease rates, build-out cost, zoning and outdoor-space rules need site-level quotes."],
  ["Price data quality", `NDCP prices come from state market-rate surveys. ${nEst} of our 10 picks' 2022 prices are between-survey estimates (Stearns MN's from its 2021 survey).`],
  ["Demand trajectory", "Births and under-5 population trends, in-migration, return-to-office patterns and income growth. We see levels, not momentum."],
];
cards.forEach(([h, d], i) => {
  const col = i % 3, row = Math.floor(i / 3);
  const x = 0.5 + col * 4.18, y = 1.4 + row * 2.2;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 3.95, h: 2.0, fill: { color: C.background2 }, line: { color: C.background2 },
    rectRadius: 0.08, objectName: `factor ${i + 1} card` });
  s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.2, w: 0.42, h: 0.42, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: `factor ${i + 1} dot` });
  s.addText(String(i + 1), { x: x + 0.2, y: y + 0.2, w: 0.42, h: 0.42, fontSize: 14, bold: true, color: "FFFFFF", align: "center", valign: "middle",
    margin: 0, isTextBox: true, objectName: `factor ${i + 1} number` });
  s.addText(h, { x: x + 0.75, y: y + 0.18, w: 3.05, h: 0.46, fontSize: 15, bold: true, color: C.accent1, margin: 0, valign: "middle",
    isTextBox: true, objectName: `factor ${i + 1} title` });
  s.addText(d, { x: x + 0.2, y: y + 0.72, w: 3.6, h: 1.2, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    objectName: `factor ${i + 1} text` });
});
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 5.85, w: 12.35, h: 0.95, fill: { color: C.accent1 }, line: { color: C.accent1 },
  rectRadius: 0.08, objectName: "next step band" });
s.addText([
  { text: "Next step: ", options: { bold: true } },
  { text: "a field price survey and competitor scan in the 10 picks plus the verify-first metros, then site-level lease quotes, before final selection." },
], { x: 0.75, y: 5.9, w: 11.9, h: 0.85, fontSize: 15, color: "FFFFFF", margin: 0, valign: "middle", isTextBox: true, objectName: "next step text" });
s.addNotes(
  `Our screen is a strong first cut but deliberately simple. Six things matter for final selection that the data do not capture. ` +
  `Most important: competition and capacity, because a high premium may mean undersupply that others will fill, and public pre-K expansion, which competes directly with paid preschool. ` +
  `Costs beyond wages and residential rent differ by state, and ${pct(R.prem_between_state_share)} of the premium's variation is between states, so part of it may reflect regulation or survey methods rather than real pricing power. ` +
  `Finally, price data quality: we excluded shared rate-zone prices and state-level or propensity-score imputations, but kept NDCP's estimates for years between state surveys. ` +
  `${nEst} of the ten picks' 2022 prices are such estimates. In Illinois and Maryland the latest surveys also carry an imputed-percentile flag, and the last fully reported surveys showed smaller premiums (${dirStr}). ` +
  `So the field price check should start there and with Stearns County.`);

// ---------- write ----------
(async () => {
  await pres.writeFile({ fileName: FILE });
  const { applyTheme } = require("./apply_theme.js");  // writes THEME colors into the deck's theme part
  await applyTheme(FILE, THEME);
  console.log("wrote", FILE);
})();
