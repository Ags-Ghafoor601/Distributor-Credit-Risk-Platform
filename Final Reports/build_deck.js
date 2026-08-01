const pptxgen = require("pptxgenjs");

const NAVY = "1E2761";
const NAVY_DEEP = "14193F";
const ICE = "CADCFC";
const GOLD = "C9A24B";
const GOLD_BRIGHT = "E0C477";
const PARCH = "F7F4EE";
const INK = "1A1A2E";
const GREY = "5A5A72";
const RED = "B3392C";
const AMBER = "A97318";
const GREEN = "1E7A44";
const WHITE = "FFFFFF";

const HEAD = "Cambria";
const BODY = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";           // 13.3 x 7.5
pres.author = "Distributor Credit Risk";
pres.title = "From Gut Feel to Defensible Data";

const W = 13.3, H = 7.5;

// Repeated motif: a small gold dot preceding every section label.
function eyebrow(slide, text, x, y, color) {
  slide.addShape(pres.ShapeType.ellipse, {
    x: x, y: y + 0.055, w: 0.11, h: 0.11, fill: { color: GOLD },
  });
  slide.addText(text, {
    x: x + 0.24, y: y - 0.03, w: 8, h: 0.28, margin: 0,
    fontFace: BODY, fontSize: 11, bold: true, charSpacing: 2,
    color: color || GREY,
  });
}

function title(slide, text, y, color) {
  slide.addText(text, {
    x: 0.75, y: y, w: 11.8, h: 0.85, margin: 0,
    fontFace: HEAD, fontSize: 34, bold: true, color: color || INK,
  });
}

// ---------------------------------------------------------------- 1. TITLE
{
  const s = pres.addSlide();
  s.background = { color: NAVY_DEEP };

  for (let i = 0; i < 9; i++) {
    s.addShape(pres.ShapeType.rect, {
      x: 0, y: 0.62 + i * 0.78, w: W, h: 0.012,
      fill: { color: GOLD_BRIGHT }, line: { type: "none" },
    });
  }
  s.addShape(pres.ShapeType.rect, {
    x: 0, y: 0, w: W, h: H, fill: { color: NAVY_DEEP, transparency: 12 },
    line: { type: "none" },
  });

  s.addText("DISTRIBUTOR CREDIT RISK", {
    x: 0.9, y: 1.85, w: 10, h: 0.3, margin: 0,
    fontFace: BODY, fontSize: 13, bold: true, charSpacing: 4, color: GOLD_BRIGHT,
  });
  s.addText("From Gut Feel to\nDefensible Data", {
    x: 0.85, y: 2.35, w: 11, h: 1.9, margin: 0,
    fontFace: HEAD, fontSize: 50, bold: true, color: WHITE, lineSpacing: 54,
  });
  s.addText(
    "A credit scorecard that reads any distributor's own ledger — and says plainly how far to trust its own answer.",
    { x: 0.9, y: 4.5, w: 9.4, h: 0.8, margin: 0,
      fontFace: BODY, fontSize: 16, color: ICE });

  const stats = [["300–900", "score range"], ["6", "Pakistan-specific signals"],
                 ["0", "black boxes"]];
  stats.forEach(([big, small], i) => {
    const x = 0.9 + i * 3.1;
    s.addText(big, { x: x, y: 5.6, w: 2.9, h: 0.55, margin: 0,
      fontFace: HEAD, fontSize: 26, bold: true, color: GOLD_BRIGHT });
    s.addText(small, { x: x, y: 6.12, w: 2.9, h: 0.3, margin: 0,
      fontFace: BODY, fontSize: 11, color: ICE, charSpacing: 1 });
  });
  s.addNotes("The product is live. Everything in this deck was produced by the deployed system, not a prototype.");
}

// ------------------------------------------------------------- 2. PROBLEM
{
  const s = pres.addSlide();
  s.background = { color: PARCH };
  eyebrow(s, "THE PROBLEM", 0.75, 0.7);
  title(s, "Credit decisions are made on memory and relationship", 1.15);

  s.addShape(pres.ShapeType.roundRect, {
    x: 0.75, y: 2.35, w: 5.5, h: 1.75, rectRadius: 0.06,
    fill: { color: NAVY }, line: { type: "none" },
  });
  s.addText('"Yaar, acha banda hai — de do."', {
    x: 1.05, y: 2.7, w: 4.9, h: 0.5, margin: 0,
    fontFace: HEAD, fontSize: 21, italic: true, color: WHITE });
  s.addText("The salesman vouches. The credit goes out. Nobody checks the ledger.", {
    x: 1.05, y: 3.25, w: 4.9, h: 0.65, margin: 0,
    fontFace: BODY, fontSize: 13, color: ICE });

  const costs = [
    ["3–7%", "of annual revenue lost to bad debt"],
    ["PKR 1M+", "typical single write-off"],
    ["100+ hrs", "a year spent chasing payments"],
  ];
  costs.forEach(([big, small], i) => {
    const y = 2.35 + i * 0.63;
    s.addText(big, { x: 6.9, y: y, w: 2.0, h: 0.42, margin: 0,
      fontFace: HEAD, fontSize: 20, bold: true, color: RED });
    s.addText(small, { x: 8.9, y: y + 0.06, w: 3.7, h: 0.4, margin: 0,
      fontFace: BODY, fontSize: 13, color: INK });
  });

  s.addText(
    "The information needed to decide better is already sitting in the invoice history. It is simply never read.",
    { x: 0.75, y: 4.75, w: 11.5, h: 0.6, margin: 0,
      fontFace: HEAD, fontSize: 17, italic: true, color: NAVY });
  s.addNotes("Frame this as an information problem, not a competence problem. The salesman is not wrong to trust relationships — he just has no counterweight.");
}

// ------------------------------------------------------------ 3. APPROACH
{
  const s = pres.addSlide();
  s.background = { color: PARCH };
  eyebrow(s, "THE APPROACH", 0.75, 0.7);
  title(s, "Six signals drawn from Pakistani distribution", 1.15);

  const feats = [
    ["PDC bounce history", "How often post-dated cheques come back"],
    ["Eid / Ramzan adjustment", "Seasonal lateness is normal — it is discounted"],
    ["Salesman-vouch bias", "Each salesman's own track record, leave-one-out"],
    ["Territory clustering", "Risk that travels with the market, not the dealer"],
    ["PKR-adjusted exposure", "What the credit limit is really worth today"],
    ["Business continuity", "Whether order activity is growing or fading"],
  ];
  feats.forEach(([h, d], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.75 + col * 6.05, y = 2.2 + row * 1.35;
    s.addShape(pres.ShapeType.ellipse, {
      x: x, y: y + 0.06, w: 0.42, h: 0.42, fill: { color: NAVY }, line: { type: "none" } });
    s.addText(String(i + 1), { x: x, y: y + 0.06, w: 0.42, h: 0.42, margin: 0,
      align: "center", valign: "middle", fontFace: BODY, fontSize: 13, bold: true, color: GOLD_BRIGHT });
    s.addText(h, { x: x + 0.62, y: y, w: 5.2, h: 0.34, margin: 0,
      fontFace: BODY, fontSize: 15, bold: true, color: INK });
    s.addText(d, { x: x + 0.62, y: y + 0.36, w: 5.2, h: 0.6, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: GREY });
  });

  s.addText("Every score comes with the reasons behind it — a logistic scorecard, not a neural network.", {
    x: 0.75, y: 6.35, w: 11.5, h: 0.45, margin: 0,
    fontFace: HEAD, fontSize: 15, italic: true, color: NAVY });
  s.addNotes("These six survived multicollinearity screening. Two overlapping ones were merged into a single composite.");
}

// ---------------------------------------------------------- 4. DEMO MOMENT
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  eyebrow(s, "THE MOMENT THAT MATTERS", 0.75, 0.7, GOLD_BRIGHT);
  title(s, "The accounts your team already trusts", 1.15, WHITE);

  s.addShape(pres.ShapeType.roundRect, {
    x: 0.75, y: 2.25, w: 5.3, h: 3.3, rectRadius: 0.05,
    fill: { color: PARCH }, line: { type: "none" },
  });
  s.addText("Ph-Rawalpindi-0080 Traders", { x: 1.05, y: 2.5, w: 4.7, h: 0.35, margin: 0,
    fontFace: BODY, fontSize: 14, bold: true, color: INK });
  s.addText("Salesman: Rizwan Malik · marked as a trusted account", {
    x: 1.05, y: 2.85, w: 4.7, h: 0.32, margin: 0,
    fontFace: BODY, fontSize: 11.5, color: RED });
  s.addText("418", { x: 1.05, y: 3.25, w: 2.2, h: 1.0, margin: 0,
    fontFace: HEAD, fontSize: 52, bold: true, color: RED });
  s.addText("out of 300–900", { x: 1.1, y: 4.22, w: 2.2, h: 0.3, margin: 0,
    fontFace: BODY, fontSize: 10.5, color: GREY });
  s.addText("HIGH RISK", { x: 3.5, y: 3.55, w: 2.3, h: 0.4, margin: 0,
    fontFace: BODY, fontSize: 16, bold: true, color: RED });
  s.addText("Late and inconsistent payment timing · elevated territory risk", {
    x: 1.05, y: 4.65, w: 4.7, h: 0.6, margin: 0,
    fontFace: BODY, fontSize: 12, color: INK });

  s.addText("5", { x: 6.9, y: 2.35, w: 1.5, h: 0.9, margin: 0,
    fontFace: HEAD, fontSize: 54, bold: true, color: GOLD_BRIGHT });
  s.addText("dealers the sales team vouches for were flagged high risk", {
    x: 6.9, y: 3.25, w: 5.3, h: 0.6, margin: 0,
    fontFace: BODY, fontSize: 16, color: WHITE });
  s.addText(
    "This is not an accusation. It is a prompt for a conversation the distributor was never in a position to start — backed by that dealer's own payment record.",
    { x: 6.9, y: 4.1, w: 5.3, h: 1.3, margin: 0,
      fontFace: BODY, fontSize: 13.5, color: ICE });
  s.addNotes("Land on this slide. The whole product exists to surface these five accounts.");
}

// ------------------------------------------------------- 5. NEW EVIDENCE
{
  const s = pres.addSlide();
  s.background = { color: PARCH };
  eyebrow(s, "EVIDENCE", 0.75, 0.7);
  title(s, "Tested on portfolios it had never seen", 1.15);
  s.addText(
    "Six independent portfolios, each with different column names, date formats, currency conventions, sizes and payment cultures — none resembling the data the model was built on.",
    { x: 0.75, y: 2.02, w: 11.5, h: 0.55, margin: 0,
      fontFace: BODY, fontSize: 13.5, color: GREY });

  const rows = [
    [{ text: "Portfolio", options: { bold: true } },
     { text: "Dealers", options: { bold: true, align: "center" } },
     { text: "Risky dealers caught", options: { bold: true, align: "center" } },
     { text: "False alarms", options: { bold: true, align: "center" } },
     { text: "Ranking quality", options: { bold: true, align: "center" } }],
    ["Al-Noor (FMCG, Karachi)", "140", "51 of 51", "0", "1.000"],
    ["Ravi (slow-paying market)", "90", "22 of 22", "0", "1.000"],
    ["Hilal (9-dealer book)", "9", "4 of 4", "0", "1.000"],
  ];
  s.addTable(rows, {
    x: 0.75, y: 2.75, w: 11.5, colW: [4.1, 1.5, 2.6, 1.8, 1.5],
    fontFace: BODY, fontSize: 14, color: INK, valign: "middle",
    border: { type: "solid", color: "DDD6C8", pt: 1 },
    fill: { color: WHITE }, rowH: 0.52,
  });

  s.addShape(pres.ShapeType.roundRect, {
    x: 0.75, y: 5.15, w: 11.5, h: 1.15, rectRadius: 0.05,
    fill: { color: NAVY }, line: { type: "none" } });
  s.addText(
    "Every genuinely risky dealer was flagged for attention. Not one sound dealer was wrongly accused. Sorted by score, the risky accounts ranked below the sound ones without exception.",
    { x: 1.05, y: 5.35, w: 10.9, h: 0.8, margin: 0,
      fontFace: BODY, fontSize: 14.5, color: WHITE });

  s.addText(
    "Measured against known outcomes in constructed portfolios. No real-world defaults have been observed yet — see limitations.",
    { x: 0.75, y: 6.55, w: 11.5, h: 0.35, margin: 0,
      fontFace: BODY, fontSize: 10.5, italic: true, color: GREY });
  s.addNotes("This is the strongest evidence in the deck. Say plainly that ground truth here is constructed, not observed — it protects credibility and the numbers are strong enough to survive the caveat.");
}

// -------------------------------------------------------- 6. ADAPTATION
{
  const s = pres.addSlide();
  s.background = { color: PARCH };
  eyebrow(s, "PORTABILITY", 0.75, 0.7);
  title(s, "It fits itself to each distributor", 1.15);

  const items = [
    ["Reads your column names", "Party Code, Booker, Credit Limit (Rs), Account Opened — no reformatting asked of you"],
    ["Finds its own date window", "Whether the ledger covers 2021 or 2027, it works out which history to learn from"],
    ["Learns your payment norms", "A 60-day-terms market and a 15-day-terms market get different definitions of \"late\""],
    ["Trains on your book when needed", "If the general model is a poor fit, it fits one to your portfolio and cross-validates it first"],
  ];
  items.forEach(([h, d], i) => {
    const y = 2.15 + i * 1.12;
    s.addShape(pres.ShapeType.roundRect, {
      x: 0.75, y: y, w: 11.5, h: 0.95, rectRadius: 0.04,
      fill: { color: WHITE }, line: { type: "none" } });
    s.addShape(pres.ShapeType.ellipse, {
      x: 1.05, y: y + 0.27, w: 0.4, h: 0.4, fill: { color: GOLD }, line: { type: "none" } });
    s.addText(h, { x: 1.68, y: y + 0.12, w: 4.3, h: 0.38, margin: 0,
      fontFace: BODY, fontSize: 15, bold: true, color: INK });
    s.addText(d, { x: 1.68, y: y + 0.48, w: 10.2, h: 0.4, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: GREY });
  });
  s.addNotes("Before this work the system only accepted one exact schema. A real distributor's export was rejected outright.");
}

// -------------------------------------------------------- 7. SELF-AWARENESS
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  eyebrow(s, "HONESTY BY DESIGN", 0.75, 0.7, GOLD_BRIGHT);
  title(s, "It tells you when not to trust it", 1.15, WHITE);
  s.addText(
    "Every run reports how far the numbers can be pushed. A confident-looking score on unsuitable data is worse than no score.",
    { x: 0.75, y: 2.0, w: 11.5, h: 0.5, margin: 0,
      fontFace: BODY, fontSize: 14, color: ICE });

  const cards = [
    [GREEN, "Scores reliable", "The portfolio sits in familiar territory. Use the numbers and the ranking."],
    [AMBER, "Scores indicative", "Somewhat unfamiliar. Rankings hold; treat exact values loosely."],
    [RED, "Use ranking only", "Substantially different. The order is meaningful; the numbers are not."],
  ];
  cards.forEach(([c, h, d], i) => {
    const x = 0.75 + i * 3.93;
    s.addShape(pres.ShapeType.roundRect, {
      x: x, y: 2.75, w: 3.65, h: 2.1, rectRadius: 0.05,
      fill: { color: PARCH }, line: { type: "none" } });
    s.addShape(pres.ShapeType.ellipse, {
      x: x + 0.3, y: 3.05, w: 0.22, h: 0.22, fill: { color: c }, line: { type: "none" } });
    s.addText(h, { x: x + 0.62, y: 2.97, w: 2.8, h: 0.35, margin: 0,
      fontFace: BODY, fontSize: 14.5, bold: true, color: c });
    s.addText(d, { x: x + 0.3, y: 3.45, w: 3.05, h: 1.2, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: INK });
  });

  s.addText(
    "It also refuses outright — when a book is too small to learn from, or shows no defaults at all, it declines to invent a model and says why.",
    { x: 0.75, y: 5.25, w: 11.5, h: 0.9, margin: 0,
      fontFace: HEAD, fontSize: 16, italic: true, color: GOLD_BRIGHT });
  s.addNotes("Tested directly: a nine-dealer book and a book with no defaults both correctly declined rather than producing noise.");
}

// ------------------------------------------------------ 8. ENGINEERING
{
  const s = pres.addSlide();
  s.background = { color: PARCH };
  eyebrow(s, "BUILT TO SURVIVE REAL CONDITIONS", 0.75, 0.7);
  title(s, "Messy exports are the normal case", 1.15);

  const stats = [
    ["99%", "of rows retained from realistically messy exports", GREEN],
    ["58%", "retained from a deliberately damaged file — every dropped row accounted for", AMBER],
    ["63", "automated tests guarding against regression", NAVY],
    ["20+", "defects found and fixed before release", NAVY],
  ];
  stats.forEach(([big, small, c], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.75 + col * 6.05, y = 2.25 + row * 1.75;
    s.addShape(pres.ShapeType.roundRect, {
      x: x, y: y, w: 5.6, h: 1.45, rectRadius: 0.05,
      fill: { color: WHITE }, line: { type: "none" } });
    s.addText(big, { x: x + 0.35, y: y + 0.22, w: 1.9, h: 0.7, margin: 0,
      fontFace: HEAD, fontSize: 34, bold: true, color: c });
    s.addText(small, { x: x + 2.3, y: y + 0.3, w: 3.05, h: 0.9, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: INK });
  });

  s.addText(
    "Mixed date formats, currency as text, blank codes, duplicate rows, invoices that predate their own due date — all handled, all reported.",
    { x: 0.75, y: 5.95, w: 11.5, h: 0.6, margin: 0,
      fontFace: HEAD, fontSize: 15, italic: true, color: NAVY });
  s.addNotes("The quality report is shown to the user every run — nothing is dropped silently.");
}

// ------------------------------------------------------ 9. LIMITATIONS
{
  const s = pres.addSlide();
  s.background = { color: PARCH };
  eyebrow(s, "WHAT WE WILL NOT OVERSTATE", 0.75, 0.7);
  title(s, "Honest limitations", 1.15);

  s.addShape(pres.ShapeType.roundRect, {
    x: 0.75, y: 2.2, w: 5.6, h: 3.9, rectRadius: 0.05,
    fill: { color: WHITE }, line: { type: "none" } });
  s.addText("Confident today", { x: 1.1, y: 2.45, w: 4.9, h: 0.4, margin: 0,
    fontFace: BODY, fontSize: 16, bold: true, color: GREEN });
  s.addText([
    { text: "Ranking dealers from safest to riskiest", options: { bullet: true, breakLine: true } },
    { text: "Surfacing trusted accounts the record contradicts", options: { bullet: true, breakLine: true } },
    { text: "Reading messy real-world exports", options: { bullet: true, breakLine: true } },
    { text: "Explaining every score in plain language", options: { bullet: true } },
  ], { x: 1.1, y: 2.95, w: 4.9, h: 2.9, margin: 0,
       fontFace: BODY, fontSize: 13.5, color: INK, paraSpaceAfter: 10 });

  s.addShape(pres.ShapeType.roundRect, {
    x: 6.95, y: 2.2, w: 5.6, h: 3.9, rectRadius: 0.05,
    fill: { color: NAVY }, line: { type: "none" } });
  s.addText("Still to prove", { x: 7.3, y: 2.45, w: 4.9, h: 0.4, margin: 0,
    fontFace: BODY, fontSize: 16, bold: true, color: GOLD_BRIGHT });
  s.addText([
    { text: "No real dealer default has been observed yet — all validation to date uses constructed portfolios", options: { bullet: true, breakLine: true } },
    { text: "The exact score is directional; the RED / AMBER / GREEN tier is the reliable signal", options: { bullet: true, breakLine: true } },
    { text: "Scores rank within one portfolio — they do not compare across companies", options: { bullet: true } },
  ], { x: 7.3, y: 2.95, w: 4.9, h: 2.9, margin: 0,
       fontFace: BODY, fontSize: 13.5, color: WHITE, paraSpaceAfter: 12 });

  s.addText(
    "Everything on the right resolves the same way: with one real distributor's ledger.",
    { x: 0.75, y: 6.35, w: 11.5, h: 0.45, margin: 0,
      fontFace: HEAD, fontSize: 15, italic: true, color: NAVY });
  s.addNotes("Do not skip this slide. Stating the limit is what makes the rest of the deck credible.");
}

// -------------------------------------------------------- 10. NEXT STEPS
{
  const s = pres.addSlide();
  s.background = { color: NAVY_DEEP };
  for (let i = 0; i < 9; i++) {
    s.addShape(pres.ShapeType.rect, {
      x: 0, y: 0.62 + i * 0.78, w: W, h: 0.012,
      fill: { color: GOLD_BRIGHT }, line: { type: "none" } });
  }
  s.addShape(pres.ShapeType.rect, {
    x: 0, y: 0, w: W, h: H, fill: { color: NAVY_DEEP, transparency: 10 },
    line: { type: "none" } });

  eyebrow(s, "WHAT WE ARE ASKING FOR", 0.75, 0.95, GOLD_BRIGHT);
  title(s, "One ledger, one conversation", 1.4, WHITE);

  const steps = [
    ["Send one export", "Your dealer list, salesman list and invoice history — in whatever format your system already produces."],
    ["We score it", "Within a day, you get a ranked risk table, per-dealer memos, and an honest read on how far to trust the numbers."],
    ["You tell us if it is right", "Sit with whoever chases payments and check the high-risk list against the accounts they actually struggle with."],
  ];
  steps.forEach(([h, d], i) => {
    const y = 2.65 + i * 1.25;
    s.addShape(pres.ShapeType.ellipse, {
      x: 0.85, y: y + 0.05, w: 0.52, h: 0.52, fill: { color: GOLD }, line: { type: "none" } });
    s.addText(String(i + 1), { x: 0.85, y: y + 0.05, w: 0.52, h: 0.52, margin: 0,
      align: "center", valign: "middle", fontFace: HEAD, fontSize: 17, bold: true, color: NAVY_DEEP });
    s.addText(h, { x: 1.6, y: y, w: 10.5, h: 0.4, margin: 0,
      fontFace: BODY, fontSize: 17, bold: true, color: WHITE });
    s.addText(d, { x: 1.6, y: y + 0.42, w: 10.5, h: 0.6, margin: 0,
      fontFace: BODY, fontSize: 13.5, color: ICE });
  });

  s.addText("That last step is the only thing standing between this and a decision you can defend.", {
    x: 0.85, y: 6.5, w: 11.5, h: 0.45, margin: 0,
    fontFace: HEAD, fontSize: 15, italic: true, color: GOLD_BRIGHT });
  s.addNotes("Close by asking for the ledger. The ask is small and concrete.");
}

pres.writeFile({ fileName: "/home/claude/deck/credit_risk_presentation.pptx" })
  .then(() => console.log("written"));
