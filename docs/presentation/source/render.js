// Draws one slide spec two ways: as PowerPoint shapes (pptxgenjs) and as
// HTML, so that the .pptx and the PDF printed from the HTML show the same
// slides. Every position is in inches on a 13.333 x 7.5 slide.

const SLIDE_WIDTH = 13.333;
const SLIDE_HEIGHT = 7.5;
const PX_PER_INCH = 96;

// Fonts that ship with Office and macOS, so the PDF matches the .pptx.
const FONT = { head: "Arial", body: "Arial", mono: "Courier New" };

class SlideSpec {
  constructor(background) {
    this.background = background;
    this.items = [];
    this.notes = "";
  }

  rect(x, y, w, h, options = {}) {
    this.items.push({ kind: "rect", x, y, w, h, ...options });
  }

  // paragraphs: a string, or a list of paragraphs; a paragraph is a string,
  // a list of runs, or { runs, bullet, spaceAfter }. A run is a string or
  // { text, bold, italic, color, font, size }.
  text(x, y, w, h, paragraphs, options = {}) {
    this.items.push({ kind: "text", x, y, w, h, paragraphs, ...options });
  }

  line(x1, y1, x2, y2, options = {}) {
    this.items.push({ kind: "line", x1, y1, x2, y2, ...options });
  }

  // rows: a list of rows of cells; a cell is a string or { text, bold, color,
  // fill, font, align }. The first row is the header.
  table(x, y, columnWidths, rows, options = {}) {
    this.items.push({ kind: "table", x, y, columnWidths, rows, ...options });
  }

  addNotes(notes) {
    this.notes = notes;
  }
}

function listParagraphs(paragraphs) {
  const list = Array.isArray(paragraphs) ? paragraphs : [paragraphs];
  return list.map((paragraph) => {
    if (typeof paragraph === "string" || Array.isArray(paragraph)) {
      return { runs: paragraph };
    }
    return paragraph;
  });
}

function listRuns(runs) {
  const list = Array.isArray(runs) ? runs : [runs];
  return list.map((run) => (typeof run === "string" ? { text: run } : run));
}

// PowerPoint ---------------------------------------------------------------

function drawSlideInPptx(pres, spec) {
  const slide = pres.addSlide();
  slide.background = { color: spec.background };
  for (const item of spec.items) {
    if (item.kind === "rect") drawRectInPptx(pres, slide, item);
    if (item.kind === "text") drawTextInPptx(slide, item);
    if (item.kind === "line") drawLineInPptx(pres, slide, item);
    if (item.kind === "table") drawTableInPptx(slide, item);
  }
  if (spec.notes) slide.addNotes(spec.notes);
}

function drawRectInPptx(pres, slide, item) {
  const isRounded = Boolean(item.radius);
  slide.addShape(
    isRounded ? pres.shapes.ROUNDED_RECTANGLE : pres.shapes.RECTANGLE,
    {
      x: item.x,
      y: item.y,
      w: item.w,
      h: item.h,
      fill: item.fill ? { color: item.fill } : { type: "none" },
      line: item.border
        ? { color: item.border, width: item.borderWidth || 1 }
        : { type: "none" },
      rectRadius: isRounded ? item.radius : undefined,
      objectName: item.name,
    },
  );
}

function drawTextInPptx(slide, item) {
  const paragraphs = listParagraphs(item.paragraphs);
  const runs = [];
  paragraphs.forEach((paragraph, paragraphIndex) => {
    const paragraphRuns = listRuns(paragraph.runs);
    paragraphRuns.forEach((run, runIndex) => {
      const isLastRun = runIndex === paragraphRuns.length - 1;
      const isLastParagraph = paragraphIndex === paragraphs.length - 1;
      runs.push({
        text: run.text,
        options: {
          bold: run.bold ?? item.bold ?? false,
          italic: run.italic ?? false,
          color: run.color || item.color,
          fontFace: FONT[run.font || item.font || "body"],
          fontSize: run.size || item.size,
          bullet: paragraph.bullet ? { indent: 14 } : false,
          paraSpaceAfter: paragraph.spaceAfter ?? item.spaceAfter ?? 0,
          align: item.align || "left",
          breakLine: isLastRun && !isLastParagraph,
        },
      });
    });
  });
  slide.addText(runs, {
    x: item.x,
    y: item.y,
    w: item.w,
    h: item.h,
    margin: [0, 0, 0, 0],
    valign: item.valign || "top",
    fit: "none",
    isTextBox: true,
    objectName: item.name,
  });
}

function drawLineInPptx(pres, slide, item) {
  slide.addShape(pres.shapes.LINE, {
    x: Math.min(item.x1, item.x2),
    y: Math.min(item.y1, item.y2),
    w: Math.abs(item.x2 - item.x1),
    h: Math.abs(item.y2 - item.y1),
    flipH: item.x2 < item.x1,
    flipV: item.y2 < item.y1,
    line: {
      color: item.color,
      width: item.width || 1.25,
      endArrowType: item.isArrow ? "triangle" : undefined,
      dashType: item.isDashed ? "dash" : "solid",
    },
  });
}

function drawTableInPptx(slide, item) {
  const rows = item.rows.map((row, rowIndex) =>
    row.map((cell) => {
      const cellSpec = typeof cell === "string" ? { text: cell } : cell;
      const isHeader = rowIndex === 0;
      return {
        text: cellSpec.text,
        options: {
          bold: cellSpec.bold ?? isHeader,
          color: cellSpec.color || (isHeader ? item.headerColor : item.color),
          fill: { color: cellSpec.fill || (isHeader ? item.headerFill : item.fill) },
          fontFace: FONT[cellSpec.font || "body"],
          fontSize: cellSpec.size || item.size,
          align: cellSpec.align || "left",
          valign: "middle",
          margin: [0.05, 0.1, 0.05, 0.1],
        },
      };
    }),
  );
  slide.addTable(rows, {
    x: item.x,
    y: item.y,
    w: item.columnWidths.reduce((sum, width) => sum + width, 0),
    colW: item.columnWidths,
    rowH: item.rowHeight,
    border: { type: "solid", pt: 0.75, color: item.borderColor },
  });
}

// HTML ---------------------------------------------------------------------

function toPx(inches) {
  return `${(inches * PX_PER_INCH).toFixed(2)}px`;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function placeBox(item) {
  return `left:${toPx(item.x)};top:${toPx(item.y)};width:${toPx(item.w)};height:${toPx(item.h)};`;
}

function drawRectInHtml(item) {
  const fill = item.fill ? `background:#${item.fill};` : "";
  const border = item.border
    ? `border:${item.borderWidth || 1}pt solid #${item.border};box-sizing:border-box;`
    : "";
  const radius = item.radius ? `border-radius:${toPx(item.radius)};` : "";
  return `<div class="rect" style="${placeBox(item)}${fill}${border}${radius}"></div>`;
}

function drawRunInHtml(item, run) {
  const style = [
    `font-family:'${FONT[run.font || item.font || "body"]}'`,
    `font-weight:${(run.bold ?? item.bold) ? 700 : 400}`,
    run.italic ? "font-style:italic" : "",
    `color:#${run.color || item.color}`,
    `font-size:${run.size || item.size}pt`,
  ].filter(Boolean);
  return `<span style="${style.join(";")}">${escapeHtml(run.text)}</span>`;
}

function drawTextInHtml(item) {
  const justify = { top: "flex-start", middle: "center", bottom: "flex-end" };
  const paragraphs = listParagraphs(item.paragraphs).map((paragraph) => {
    const runs = listRuns(paragraph.runs).map((run) => drawRunInHtml(item, run));
    const spaceAfter = paragraph.spaceAfter ?? item.spaceAfter ?? 0;
    const bullet = paragraph.bullet ? " bullet" : "";
    return `<p class="para${bullet}" style="margin:0 0 ${spaceAfter}pt 0;text-align:${item.align || "left"}">${runs.join("")}</p>`;
  });
  return `<div class="text" style="${placeBox(item)}justify-content:${justify[item.valign || "top"]};font-size:${item.size}pt">${paragraphs.join("")}</div>`;
}

function drawLineInHtml(item, index) {
  const marker = item.isArrow ? `marker-end="url(#arrow-${index})"` : "";
  const dash = item.isDashed ? 'stroke-dasharray="6 4"' : "";
  const width = ((item.width || 1.25) * 4) / 3;
  return `<svg class="line" width="${toPx(SLIDE_WIDTH)}" height="${toPx(SLIDE_HEIGHT)}">
    <defs><marker id="arrow-${index}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 z" fill="#${item.color}"/></marker></defs>
    <line x1="${item.x1 * PX_PER_INCH}" y1="${item.y1 * PX_PER_INCH}" x2="${item.x2 * PX_PER_INCH}" y2="${item.y2 * PX_PER_INCH}" stroke="#${item.color}" stroke-width="${width}" ${dash} ${marker}/></svg>`;
}

function drawTableInHtml(item) {
  const columns = item.columnWidths.map((width) => `<col style="width:${toPx(width)}">`);
  const rows = item.rows.map((row, rowIndex) => {
    const isHeader = rowIndex === 0;
    const cells = row.map((cell) => {
      const cellSpec = typeof cell === "string" ? { text: cell } : cell;
      const style = [
        `font-family:'${FONT[cellSpec.font || "body"]}'`,
        `font-weight:${(cellSpec.bold ?? isHeader) ? 700 : 400}`,
        `color:#${cellSpec.color || (isHeader ? item.headerColor : item.color)}`,
        `background:#${cellSpec.fill || (isHeader ? item.headerFill : item.fill)}`,
        `font-size:${cellSpec.size || item.size}pt`,
        `text-align:${cellSpec.align || "left"}`,
        `border:0.75pt solid #${item.borderColor}`,
        // A cell's CSS height leaves out its padding; PowerPoint's row height does not.
        `height:${toPx(item.rowHeight - 0.11)}`,
      ];
      return `<td style="${style.join(";")}">${escapeHtml(cellSpec.text)}</td>`;
    });
    return `<tr>${cells.join("")}</tr>`;
  });
  return `<table style="left:${toPx(item.x)};top:${toPx(item.y)}"><colgroup>${columns.join("")}</colgroup>${rows.join("")}</table>`;
}

function drawSlideInHtml(spec) {
  const parts = spec.items.map((item, index) => {
    if (item.kind === "rect") return drawRectInHtml(item);
    if (item.kind === "text") return drawTextInHtml(item);
    if (item.kind === "line") return drawLineInHtml(item, index);
    return drawTableInHtml(item);
  });
  return `<section class="slide" style="background:#${spec.background}">${parts.join("\n")}</section>`;
}

// Marks a text box whose text does not fit, so that a check can find it.
const FIT_CHECK_SCRIPT = `<script>
for (const box of document.querySelectorAll('.text')) {
  if (box.scrollHeight > box.clientHeight + 1 || box.scrollWidth > box.clientWidth + 1) {
    box.classList.add('overflow');
    box.setAttribute('data-overflow', box.textContent.slice(0, 60));
  }
}
</script>`;

function writeDeckHtml(specs) {
  const style = `
    @page { size: ${SLIDE_WIDTH}in ${SLIDE_HEIGHT}in; margin: 0; }
    html, body { margin: 0; padding: 0; }
    .slide { position: relative; width: ${toPx(SLIDE_WIDTH)}; height: ${toPx(SLIDE_HEIGHT)};
      overflow: hidden; page-break-after: always; break-after: page; }
    .rect, .text, .line, table { position: absolute; }
    .line { left: 0; top: 0; pointer-events: none; }
    .text { display: flex; flex-direction: column; overflow: hidden; line-height: 1.2; }
    .para.bullet { padding-left: 14pt; text-indent: -10pt; }
    .para.bullet::before { content: "\\2022"; display: inline-block; width: 10pt; text-indent: 0; }
    table { border-collapse: collapse; table-layout: fixed; }
    td { padding: ${toPx(0.05)} ${toPx(0.1)}; vertical-align: middle; line-height: 1.15; }
    .overflow { outline: 3px solid red; }`;
  const slides = specs.map(drawSlideInHtml).join("\n");
  return `<!doctype html><html><head><meta charset="utf-8"><title>klint architecture</title><style>${style}</style></head><body>${slides}${FIT_CHECK_SCRIPT}</body></html>`;
}

module.exports = {
  SLIDE_WIDTH,
  SLIDE_HEIGHT,
  SlideSpec,
  drawSlideInPptx,
  writeDeckHtml,
};
