// The palette and the parts every slide of the deck shares.

const { SlideSpec } = require("./render");

const COLOR = {
  ink: "17213A",
  inkSoft: "33405F",
  mist: "EEF2F7",
  mistDeep: "DCE3EE",
  line: "C5CEDC",
  muted: "5A6478",
  white: "FFFFFF",
  accent: "E09A2D",
  accentLight: "FBEBD0",
  pass: "2F8653",
  passLight: "E2F1E8",
  problem: "C23B4E",
  problemLight: "F8E1E4",
};

const SLIDE_COUNT = 13;
const LEFT = 0.6;
const RIGHT = 12.733;
const CONTENT_WIDTH = RIGHT - LEFT;
const CONTENT_TOP = 1.85;

// A light content slide: title, one-line lede, the code it rests on, and
// its number.
function createContentSlide(number, title, lede, codeLine) {
  const spec = new SlideSpec(COLOR.white);
  spec.text(LEFT, 0.4, CONTENT_WIDTH, 0.75, title, {
    font: "head",
    size: 28,
    bold: true,
    color: COLOR.ink,
    valign: "middle",
    name: "Title",
  });
  spec.text(LEFT, 1.15, CONTENT_WIDTH, 0.45, lede, {
    size: 15,
    color: COLOR.muted,
    valign: "middle",
    name: "Lede",
  });
  spec.text(LEFT, 6.98, 10.8, 0.3, `Code: ${codeLine}`, {
    font: "mono",
    size: 10,
    color: COLOR.muted,
    valign: "middle",
    name: "Code line",
  });
  spec.text(11.73, 6.98, 1.0, 0.3, `${number} / ${SLIDE_COUNT}`, {
    size: 10,
    color: COLOR.muted,
    align: "right",
    valign: "middle",
    name: "Slide number",
  });
  return spec;
}

function createDarkSlide() {
  return new SlideSpec(COLOR.ink);
}

// A rounded label: a filled shape with one centred line of text.
function addChip(spec, x, y, w, h, text, options = {}) {
  spec.rect(x, y, w, h, {
    fill: options.fill || COLOR.mist,
    border: options.border,
    radius: Math.min(h / 2, 0.12),
  });
  spec.text(x + 0.08, y, w - 0.16, h, text, {
    font: options.font || "body",
    size: options.size || 11,
    bold: options.bold ?? true,
    color: options.color || COLOR.ink,
    align: options.align || "center",
    valign: "middle",
  });
}

// A card: a rounded tinted panel with paragraphs inside it.
function addCard(spec, x, y, w, h, paragraphs, options = {}) {
  spec.rect(x, y, w, h, {
    fill: options.fill || COLOR.mist,
    border: options.border,
    radius: 0.1,
  });
  const inset = options.inset ?? 0.18;
  spec.text(x + inset, y + inset, w - 2 * inset, h - 2 * inset, paragraphs, {
    size: options.size || 12,
    color: options.color || COLOR.ink,
    spaceAfter: options.spaceAfter ?? 4,
    valign: options.valign || "top",
  });
}

// A number in a circle.
function addBadge(spec, x, y, diameter, label, options = {}) {
  spec.rect(x, y, diameter, diameter, {
    fill: options.fill || COLOR.ink,
    radius: diameter / 2,
  });
  spec.text(x, y, diameter, diameter, label, {
    size: options.size || 14,
    bold: true,
    color: options.color || COLOR.white,
    align: "center",
    valign: "middle",
  });
}

module.exports = {
  COLOR,
  LEFT,
  RIGHT,
  CONTENT_WIDTH,
  CONTENT_TOP,
  createContentSlide,
  createDarkSlide,
  addChip,
  addCard,
  addBadge,
};
