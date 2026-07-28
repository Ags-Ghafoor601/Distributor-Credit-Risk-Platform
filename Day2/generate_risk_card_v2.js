const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle
} = require("docx");
const fs = require("fs");

const RED = "C0392B";
const AMBER = "B8860B";
const GREEN = "1E8449";
const DARK = "1A1A1A";
const GREY = "666666";
const LIGHT_GREY = "F2F2F2";

const FLAG_COLOR = {
  "RED (High Risk)": RED,
  "AMBER (Moderate)": AMBER,
  "GREEN (Reliable)": GREEN,
};
const FLAG_EMOJI = {
  "RED (High Risk)": "🔴",
  "AMBER (Moderate)": "🟠",
  "GREEN (Reliable)": "🟢",
};
const RECOMMENDED_ACTION = {
  "RED (High Risk)": "Do not increase credit limit. Consider requiring partial upfront payment or cash-on-delivery terms on future orders.",
  "AMBER (Moderate)": "Maintain current credit limit. Monitor closely and reassess in 3 months.",
  "GREEN (Reliable)": "Eligible for credit limit review or increase based on strong payment history.",
};

// Turns a reason-code entry + the dealer's raw data into a plain-language sentence.
function reasonSentence(dealer, reason) {
  const dir = reason.direction === "increases_risk" ? "Increases risk" : "Reduces risk";
  let detail = "";
  switch (reason.factor) {
    case "Cheque bounce history":
      detail = `Bounced ${(dealer.bounce_rate_lifetime * 100).toFixed(1)}% of cheques historically.`;
      break;
    case "Late payment pattern (excluding Eid/Ramzan)":
      detail = `Averages ${dealer.avg_days_late_nonseasonal.toFixed(1)} days late on payments, even outside Eid/Ramzan periods.`;
      break;
    case "Inconsistent / unpredictable payment timing":
      detail = `Payment timing varies by roughly ${dealer.payment_volatility.toFixed(1)} days, making cash flow hard to predict.`;
      break;
    case "Inflation-adjusted credit exposure":
      detail = `Real (PKR-inflation-adjusted) exposure is a contributing factor to this dealer's overall risk sizing.`;
      break;
    case "Declining order activity":
      detail = `Recent order frequency trend is a contributing signal of changing business activity.`;
      break;
    case "Salesman's track record with similar dealers":
      detail = `${dealer.salesman_name || "This dealer's salesman"} has an elevated default rate among other dealers they manage.`;
      break;
    case "Elevated risk in dealer's territory":
      detail = `Dealers in ${dealer.city} show above-average risk as a group.`;
      break;
    default:
      detail = "";
  }
  return { header: `${dir} — ${reason.factor}`, detail };
}

function labelValueRow(label, value, valueColor) {
  return new TableRow({
    children: [
      new TableCell({
        width: { size: 4000, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill: "FFFFFF" },
        borders: { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE } },
        children: [new Paragraph({ children: [new TextRun({ text: label, color: GREY, size: 20 })] })],
      }),
      new TableCell({
        width: { size: 5000, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill: "FFFFFF" },
        borders: { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE } },
        children: [new Paragraph({ children: [new TextRun({ text: String(value), bold: true, color: valueColor || DARK, size: 20 })] })],
      }),
    ],
  });
}

function buildRiskCard(dealer) {
  const flagColor = FLAG_COLOR[dealer.risk_flag] || DARK;
  const emoji = FLAG_EMOJI[dealer.risk_flag] || "";
  const action = RECOMMENDED_ACTION[dealer.risk_flag] || "";
  const isContradiction = dealer.is_salesman_favorite && dealer.risk_flag === "RED (High Risk)";

  const reasonParagraphs = dealer.top_reasons.flatMap((r, i) => {
    const s = reasonSentence(dealer, r);
    return [
      new Paragraph({
        spacing: { after: 30 },
        children: [
          new TextRun({ text: `${i + 1}. `, bold: true }),
          new TextRun({ text: s.header, bold: true }),
        ],
      }),
      new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: s.detail, color: GREY })] }),
    ];
  });

  const identityRows = [
    labelValueRow("Dealer Name", dealer.dealer_name),
    labelValueRow("City / Territory", dealer.city),
    labelValueRow("Sector", dealer.sector),
    labelValueRow("Assigned Salesman", `${dealer.salesman_name || dealer.salesman_id} (${dealer.salesman_id})`),
  ];
  if (isContradiction) {
    identityRows.push(labelValueRow("Salesman Relationship", "Marked as a trusted / favorite account", RED));
  }

  const children = [
    new Paragraph({ children: [new TextRun({ text: "[ DISTRIBUTOR LETTERHEAD ]", color: GREY, size: 18, italics: true })] }),
    new Paragraph({
      spacing: { before: 100, after: 300 },
      children: [new TextRun({ text: "Dealer Credit Risk Card", bold: true, size: 40, color: DARK })],
    }),
    new Paragraph({
      spacing: { after: 300 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "CCCCCC" } },
      children: [new TextRun({ text: "Generated from historical payment data — internal decision support only", italics: true, color: GREY, size: 18 })],
    }),
    new Table({ width: { size: 9000, type: WidthType.DXA }, columnWidths: [4000, 5000], rows: identityRows }),
    new Paragraph({ spacing: { before: 400 }, children: [] }),
    new Table({
      width: { size: 9000, type: WidthType.DXA },
      columnWidths: [4500, 4500],
      rows: [new TableRow({
        children: [
          new TableCell({
            width: { size: 4500, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: LIGHT_GREY },
            margins: { top: 200, bottom: 200, left: 200, right: 200 },
            children: [
              new Paragraph({ children: [new TextRun({ text: "CREDIT SCORE", size: 18, color: GREY })] }),
              new Paragraph({ children: [new TextRun({ text: String(Math.round(dealer.credit_score)), bold: true, size: 56, color: flagColor })] }),
              new Paragraph({ children: [new TextRun({ text: "out of 300–900", size: 16, color: GREY })] }),
            ],
          }),
          new TableCell({
            width: { size: 4500, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: LIGHT_GREY },
            margins: { top: 200, bottom: 200, left: 200, right: 200 },
            children: [
              new Paragraph({ children: [new TextRun({ text: "RISK FLAG", size: 18, color: GREY })] }),
              new Paragraph({ children: [new TextRun({ text: `${emoji} ${dealer.risk_flag}`, bold: true, size: 28, color: flagColor })] }),
              new Paragraph({ children: [new TextRun({ text: `Model confidence (ranking, not exact probability): ${(dealer.risk_probability_calibrated * 100).toFixed(1)}%`, size: 15, color: GREY })] }),
            ],
          }),
        ],
      })],
    }),
    new Paragraph({ spacing: { before: 400, after: 150 }, children: [new TextRun({ text: "Key Contributing Factors", bold: true, size: 26, color: DARK })] }),
    ...reasonParagraphs,
    new Paragraph({
      spacing: { after: 150 },
      border: { top: { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC" } },
      children: [new TextRun({ text: "Recommended Action", bold: true, size: 26, color: DARK })],
    }),
    new Paragraph({
      spacing: { after: 300 },
      children: [new TextRun({
        text: isContradiction
          ? `${action} Recommend a direct conversation with the assigned salesman given this account's trusted status contradicts the payment record.`
          : action,
      })],
    }),
    new Paragraph({
      border: { top: { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC" } },
      spacing: { before: 200 },
      children: [new TextRun({
        text: "This score is generated from historical payment behavior only and does not replace human judgment. Risk tier (RED/AMBER/GREEN) reflects the model's relative ranking within this portfolio; the exact numeric score will sharpen in precision as more historical data becomes available.",
        italics: true, size: 16, color: GREY,
      })],
    }),
  ];

  return new Document({
    sections: [{
      properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1000, bottom: 1000, left: 1100, right: 1100 } } },
      children,
    }],
  });
}

// ---------------------------------------------------------------------------
// CLI: node generate_risk_card_v2.js D0080
//      node generate_risk_card_v2.js --all-red
//      node generate_risk_card_v2.js --all-favorites-red   (the demo set)
// ---------------------------------------------------------------------------
const data = JSON.parse(fs.readFileSync("dealer_cards_data.json", "utf8"));
const args = process.argv.slice(2);

let targets = [];
if (args.includes("--all-red")) {
  targets = data.filter(d => d.risk_flag === "RED (High Risk)");
} else if (args.includes("--all-favorites-red")) {
  targets = data.filter(d => d.risk_flag === "RED (High Risk)" && d.is_salesman_favorite);
} else if (args.length > 0) {
  targets = data.filter(d => args.includes(d.dealer_id));
} else {
  console.log("Usage: node generate_risk_card_v2.js <DEALER_ID> [<DEALER_ID> ...] | --all-red | --all-favorites-red");
  process.exit(1);
}

if (targets.length === 0) {
  console.log("No matching dealers found.");
  process.exit(1);
}

(async () => {
  for (const dealer of targets) {
    const doc = buildRiskCard(dealer);
    const buffer = await Packer.toBuffer(doc);
    const filename = `${dealer.dealer_id}_Risk_Card.docx`;
    fs.writeFileSync(filename, buffer);
    console.log(`Generated: ${filename}  (score ${Math.round(dealer.credit_score)}, ${dealer.risk_flag})`);
  }
})();
