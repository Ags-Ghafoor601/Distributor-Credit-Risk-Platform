const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, ShadingType, AlignmentType, HeadingLevel, BorderStyle
} = require("docx");
const fs = require("fs");

const RED = "C0392B";
const DARK = "1A1A1A";
const GREY = "666666";
const LIGHT_GREY = "F2F2F2";

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
        children: [new Paragraph({ children: [new TextRun({ text: value, bold: true, color: valueColor || DARK, size: 20 })] })],
      }),
    ],
  });
}

const doc = new Document({
  sections: [{
    properties: {
      page: { size: { width: 12240, height: 15840 }, margin: { top: 1000, bottom: 1000, left: 1100, right: 1100 } },
    },
    children: [
      // Header / letterhead placeholder
      new Paragraph({
        children: [new TextRun({ text: "[ DISTRIBUTOR LETTERHEAD ]", color: GREY, size: 18, italics: true })],
      }),
      new Paragraph({
        spacing: { before: 100, after: 300 },
        children: [new TextRun({ text: "Dealer Credit Risk Card", bold: true, size: 40, color: DARK })],
      }),
      new Paragraph({
        spacing: { after: 300 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "CCCCCC" } },
        children: [new TextRun({ text: "Generated from historical payment data — internal decision support only", italics: true, color: GREY, size: 18 })],
      }),

      // Dealer identity block
      new Table({
        width: { size: 9000, type: WidthType.DXA },
        columnWidths: [4000, 5000],
        rows: [
          labelValueRow("Dealer Name", "Ph-Rawalpindi-0080 Traders"),
          labelValueRow("City / Territory", "Rawalpindi"),
          labelValueRow("Sector", "Pharma"),
          labelValueRow("Assigned Salesman", "Rizwan Malik (SM008)"),
          labelValueRow("Salesman Relationship", "Marked as a trusted / favorite account", RED),
        ],
      }),

      new Paragraph({ spacing: { before: 400 }, children: [] }),

      // Score block
      new Table({
        width: { size: 9000, type: WidthType.DXA },
        columnWidths: [4500, 4500],
        rows: [
          new TableRow({
            children: [
              new TableCell({
                width: { size: 4500, type: WidthType.DXA },
                shading: { type: ShadingType.CLEAR, fill: LIGHT_GREY },
                margins: { top: 200, bottom: 200, left: 200, right: 200 },
                children: [
                  new Paragraph({ children: [new TextRun({ text: "CREDIT SCORE", size: 18, color: GREY })] }),
                  new Paragraph({ children: [new TextRun({ text: "385", bold: true, size: 56, color: RED })] }),
                  new Paragraph({ children: [new TextRun({ text: "out of 300–900", size: 16, color: GREY })] }),
                ],
              }),
              new TableCell({
                width: { size: 4500, type: WidthType.DXA },
                shading: { type: ShadingType.CLEAR, fill: LIGHT_GREY },
                margins: { top: 200, bottom: 200, left: 200, right: 200 },
                children: [
                  new Paragraph({ children: [new TextRun({ text: "RISK FLAG", size: 18, color: GREY })] }),
                  new Paragraph({ children: [new TextRun({ text: "🔴 RED — High Risk", bold: true, size: 32, color: RED })] }),
                  new Paragraph({ children: [new TextRun({ text: "Estimated default probability: 99.9%", size: 16, color: GREY })] }),
                ],
              }),
            ],
          }),
        ],
      }),

      new Paragraph({ spacing: { before: 400, after: 150 }, children: [new TextRun({ text: "Why this dealer is flagged", bold: true, size: 26, color: DARK })] }),

      new Paragraph({
        spacing: { after: 80 },
        children: [
          new TextRun({ text: "1. ", bold: true }),
          new TextRun({ text: "Late payment pattern: ", bold: true }),
          new TextRun({ text: "Averages 37.6 days late on payments, excluding Eid/Ramzan periods — well beyond the 15-day acceptable threshold, even after removing seasonal cash-flow effects." }),
        ],
      }),
      new Paragraph({
        spacing: { after: 80 },
        children: [
          new TextRun({ text: "2. ", bold: true }),
          new TextRun({ text: "Inconsistent payment timing: ", bold: true }),
          new TextRun({ text: "Payment behavior is highly unpredictable month to month — this dealer does not pay late in a stable, plannable way, making cash-flow forecasting for your business unreliable." }),
        ],
      }),
      new Paragraph({
        spacing: { after: 200 },
        children: [
          new TextRun({ text: "3. ", bold: true }),
          new TextRun({ text: "Elevated territory risk: ", bold: true }),
          new TextRun({ text: "Other dealers in this territory also show above-average risk, suggesting a regional pattern beyond this dealer alone." }),
        ],
      }),

      new Paragraph({
        spacing: { after: 150 },
        border: { top: { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC" } },
        children: [new TextRun({ text: "Recommended Action", bold: true, size: 26, color: DARK })],
      }),
      new Paragraph({
        spacing: { after: 300 },
        children: [new TextRun({
          text: "Do not increase credit limit. Consider requiring partial upfront payment or cash-on-delivery terms on future orders. Recommend a direct conversation with the assigned salesman given this account's trusted status contradicts the payment record.",
        })],
      }),

      new Paragraph({
        border: { top: { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC" } },
        spacing: { before: 200 },
        children: [new TextRun({ text: "This score is generated from historical payment behavior only and does not replace human judgment. It is intended to surface patterns that may not be visible in day-to-day relationship management.", italics: true, size: 16, color: GREY })],
      }),
    ],
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync("D0080_Risk_Card.docx", buffer);
  console.log("Risk Card generated.");
});
