// Slides 7 to 9: change-summary verification, its live result, and the
// test that a suite can be added without touching core or app.

const {
  COLOR,
  LEFT,
  RIGHT,
  CONTENT_TOP,
  createContentSlide,
  addChip,
  addBadge,
} = require("./deck_parts");

const STATUS_STYLE = {
  own: { fill: COLOR.problem, color: COLOR.white, border: undefined },
  below: { fill: COLOR.accent, color: COLOR.ink, border: undefined },
  none: { fill: COLOR.passLight, color: COLOR.ink, border: COLOR.pass },
};

function buildVerificationSlide() {
  const spec = createContentSlide(
    7,
    "Change summaries are checked level by level, accuracy first",
    "Each hunk's summary is judged against its code; each level above, against the checked summaries below it.",
    "klint/catalog/change_summary/ · klint/resources/catalog/change_summary/summary_checks.json",
  );
  const levels = [
    ["Commit", "The root package's summary"],
    ["Package", "Evidence: its files' and packages' checked summaries"],
    ["File", "Evidence: its hunks' checked summaries"],
    ["Hunk", "Evidence: its code, from git diff -U0"],
  ];
  const levelWidth = 3.75;
  levels.forEach(([name, evidence], index) => {
    const y = CONTENT_TOP + index * 1.2;
    const isHunk = name === "Hunk";
    spec.rect(LEFT, y, levelWidth, 0.92, { fill: isHunk ? COLOR.ink : COLOR.mist, radius: 0.1 });
    spec.text(LEFT + 0.18, y + 0.08, levelWidth - 0.36, 0.36, name, {
      font: "head", size: 15, bold: true, color: isHunk ? COLOR.white : COLOR.ink, valign: "middle",
    });
    spec.text(LEFT + 0.18, y + 0.44, levelWidth - 0.36, 0.42, evidence, {
      size: 11, color: isHunk ? "D7DEEB" : COLOR.inkSoft,
    });
    if (index > 0) {
      spec.line(LEFT + levelWidth / 2, y - 0.02, LEFT + levelWidth / 2, y - 0.26, {
        color: COLOR.accent, width: 2, isArrow: true,
      });
    }
  });
  spec.text(LEFT, CONTENT_TOP + 4.75, levelWidth, 0.35, "Judged deepest first: hunks, files, packages, commit", {
    size: 11, color: COLOR.muted, italic: true, valign: "middle",
  });

  const checksX = 4.75;
  const checksWidth = 4.6;
  spec.text(checksX, CONTENT_TOP, checksWidth, 0.36, "Five checks", {
    font: "head", size: 15, bold: true, color: COLOR.ink, valign: "middle",
  });
  const checks = [
    ["No false statement", "accuracy", "every level"],
    ["No unsupported reason", "accuracy", "every level"],
    ["No contradiction with the level below", "accuracy", "file, package"],
    ["Covers every change", "completeness", "every level"],
    ["Covers the key changes", "completeness", "every level"],
  ];
  checks.forEach(([name, tag, levelsAsked], index) => {
    const y = CONTENT_TOP + 0.5 + index * 0.78;
    spec.rect(checksX, y, checksWidth, 0.66, { fill: COLOR.mist, radius: 0.1 });
    spec.text(checksX + 0.15, y + 0.06, 3.0, 0.32, name, { size: 12, bold: true, color: COLOR.ink, valign: "middle" });
    spec.text(checksX + 0.15, y + 0.36, 3.0, 0.26, levelsAsked, { size: 10, color: COLOR.muted, valign: "middle" });
    const isAccuracy = tag === "accuracy";
    addChip(spec, checksX + checksWidth - 1.32, y + 0.17, 1.2, 0.32, tag, {
      fill: isAccuracy ? COLOR.ink : COLOR.mistDeep,
      color: isAccuracy ? COLOR.white : COLOR.ink,
      size: 9.5,
    });
  });
  spec.text(checksX, CONTENT_TOP + 4.45, checksWidth, 0.65,
    "Asked as inference: the evidence is the premise, the summary the hypothesis. Accuracy findings are listed first.",
    { size: 11, color: COLOR.muted },
  );

  const legendX = 9.75;
  const legendWidth = RIGHT - legendX;
  spec.text(legendX, CONTENT_TOP, legendWidth, 0.36, "Answers", {
    font: "head", size: 15, bold: true, color: COLOR.ink, valign: "middle",
  });
  [["Accurate", COLOR.passLight, COLOR.ink], ["Inaccurate: a problem", COLOR.problem, COLOR.white], ["Cannot tell", COLOR.mist, COLOR.ink]]
    .forEach(([label, fill, color], index) => {
      addChip(spec, legendX, CONTENT_TOP + 0.5 + index * 0.45, legendWidth, 0.36, label, { fill, color, size: 11, align: "left" });
    });
  spec.text(legendX, CONTENT_TOP + 1.95, legendWidth, 0.36, "Roll-up", {
    font: "head", size: 15, bold: true, color: COLOR.ink, valign: "middle",
  });
  [["OWN PROBLEM", STATUS_STYLE.own], ["DESCENDANT PROBLEM", STATUS_STYLE.below], ["NO PROBLEM", STATUS_STYLE.none]]
    .forEach(([label, style], index) => {
      addChip(spec, legendX, CONTENT_TOP + 2.45 + index * 0.45, legendWidth, 0.36, label, { ...style, size: 10.5, align: "left" });
    });
  spec.text(legendX, CONTENT_TOP + 3.9, legendWidth, 1.2,
    "A summary whose own checks pass still shows where a problem sits below it.",
    { size: 11, color: COLOR.muted },
  );
  spec.addNotes(
    [
      "Claim: summaries are checked bottom-up, hunk evidence is code, upper evidence is the checked summaries below; accuracy first.",
      "Levels: AuditableHunkSummaryUnit, AuditableFileSummaryUnit, AuditablePackageSummaryUnit (catalog/change_summary/units/). The root package's summary is the commit's (document_reader.py, ROOT_PACKAGE_PATH). ChangeSummaryExtractor (extraction/change_summary_extractor.py) reads the JSON document into this tree.",
      "Evidence: HunkSummaryRenderer (renderers/hunk_summary_renderer.py) shows the hunk's diff as the premise. FileSummaryRenderer and PackageSummaryRenderer (renderers/upper_level_summary.py) show the checked summaries one level down, each with what its own checks found, and no code. Premise and hypothesis wording: renderers/premise_and_hypothesis.py; chosen from probes on kev-4b in #55.",
      "Checks: summary_checks.json has five rules: no_false_statement, no_unsupported_reason, no_contradiction_with_level_below (file and package only), covers_every_change, covers_key_changes; tags accuracy or completeness (SummaryCheckTag). The kind ranks ACCURACY before COMPLETENESS (ranked_tags in catalog/change_summary/__init__.py).",
      "Answers: SUMMARY_ACCURACY_SCALE (summary_accuracy_scale.py): accurate, inaccurate (the only problem), cannot_tell.",
      "Order and roll-up: AuditOrder.CHILDREN_FIRST (core/models/audit_order.py), applied by Auditor._order_levels. RollUpStatus (core/models/roll_up_status.py) set by FindingRollUp (app/pipeline/roll_up.py).",
      "Before: no audit order, no roll-up, one answer scale with code wording, findings without their rule's tags (D6, D12).",
    ].join("\n\n"),
  );
  return spec;
}

function addTreeNode(spec, x, y, w, h, label, status, options = {}) {
  const style = STATUS_STYLE[status];
  spec.rect(x, y, w, h, { fill: style.fill, border: style.border, radius: 0.08 });
  spec.text(x + 0.1, y, w - 0.2, h, label, {
    size: options.size || 11, bold: true, color: style.color, valign: "middle",
  });
}

function buildResultsSlide() {
  const spec = createContentSlide(
    8,
    "Real change: both planted errors caught, no false alarm",
    "Commit d35fa76 of this repository, summarized as an agent would. Live judge: kev-4b.",
    "examples/change_summary/ · klint/cli/change_summary_audit.py · live runs in #55, repeated on wave-6",
  );
  const headerY = CONTENT_TOP;
  const columns = [[LEFT, 1.2, "Commit"], [2.0, 1.9, "Packages (2)"], [4.1, 2.25, "Files (4)"], [6.55, 1.75, "Hunks (10)"]];
  columns.forEach(([x, w, label]) => {
    spec.text(x, headerY, w, 0.3, label, { size: 11, bold: true, color: COLOR.muted, valign: "middle" });
  });
  const files = [
    ["extraction delegator", "below", ["none", "none", "own", "none"]],
    ["file metadata unit", "none", ["none", "none", "none", "none"]],
    ["delegator tests", "none", ["none"]],
    ["project audit test", "none", ["none"]],
  ];
  const fileYs = [2.35, 3.15, 4.35, 5.15];
  files.forEach(([label, status, hunks], index) => {
    const y = fileYs[index];
    addTreeNode(spec, 4.1, y, 2.25, 0.55, label, status);
    spec.line(3.9, y + 0.275, 4.08, y + 0.275, { color: COLOR.line, width: 1.25 });
    hunks.forEach((hunkStatus, hunkIndex) => {
      const style = STATUS_STYLE[hunkStatus];
      const x = 6.55 + hunkIndex * 0.42;
      spec.rect(x, y + 0.1, 0.34, 0.34, { fill: style.fill, border: style.border, radius: 0.05 });
      spec.text(x, y + 0.1, 0.34, 0.34, `${hunkIndex + 1}`, { size: 9, bold: true, color: style.color, align: "center", valign: "middle" });
    });
  });
  addTreeNode(spec, 2.0, 2.73, 1.9, 0.6, "src/catalog/ code/common", "below", { size: 10.5 });
  addTreeNode(spec, 2.0, 4.73, 1.9, 0.6, "tests", "own");
  spec.line(3.9, 2.625, 3.9, 3.425, { color: COLOR.line, width: 1.25 });
  spec.line(3.9, 4.625, 3.9, 5.425, { color: COLOR.line, width: 1.25 });
  addTreeNode(spec, LEFT, 3.73, 1.2, 0.6, "./", "below");
  spec.line(1.8, 3.03, 1.98, 3.03, { color: COLOR.line, width: 1.25 });
  spec.line(1.8, 5.03, 1.98, 5.03, { color: COLOR.line, width: 1.25 });
  spec.line(1.8, 3.03, 1.8, 5.03, { color: COLOR.line, width: 1.25 });

  spec.text(LEFT, 5.95, 7.7, 0.85, [
    [{ text: "Planted 1, hunk 3: ", bold: true }, { text: "says the delegator raises ValueError for binary files; the code returns a unit." }],
    [{ text: "Planted 2, package tests: ", bold: true }, { text: "gives a memory reason nothing in the change supports." }],
  ], { size: 11.5, color: COLOR.ink, spaceAfter: 3 });

  const statX = 8.75;
  const statWidth = RIGHT - statX;
  const stats = [
    ["2 of 2", "planted errors flagged as their own problem", COLOR.problem],
    ["0", "other summaries flagged; 9 failing answers, all on the two planted summaries", COLOR.ink],
    ["exit 0 · exit 1", "clean document passes; planted document fails, for the Stop hook to block", COLOR.ink],
    ["8%", "of answers 'cannot tell' (6 of 75), none on a planted summary", COLOR.ink],
  ];
  stats.forEach(([value, label, color], index) => {
    const y = CONTENT_TOP + index * 1.2;
    spec.text(statX, y, statWidth, 0.55, value, { size: 28, bold: true, color, valign: "middle" });
    spec.text(statX, y + 0.55, statWidth, 0.55, label, { size: 11.5, color: COLOR.muted });
  });
  spec.addNotes(
    [
      "Claim: on a real change, klint-change-summary flags exactly the two planted errors and passes the clean document.",
      "The example: examples/change_summary/ holds summaries.json and summaries_with_planted_errors.json for commit d35fa76 ('Listing a binary file by name only in the project audit'); hunk code from git diff -U0 d35fa76^ d35fa76: 4 files, 10 hunks, 2 packages (src/catalog/code/common, tests) and the root package. The paths are the repository's as they were at that commit.",
      "Live results, #55 (kev.serve with jaredpalmer/kev-4b): summaries.json exits 0 ('Every summary passed its checks'). summaries_with_planted_errors.json exits 1: 17 units, 75 answers: 60 accurate, 9 inaccurate, 6 cannot tell. The 9 inaccurate answers are on hunk src/catalog/code/common/extractors/traits_based_extraction_delegator.py#3 (4 checks) and package tests/ (5 checks); both have OWN PROBLEM. Their ancestors (the delegator file, the package src/catalog/code/common and ./) have DESCENDANT PROBLEM. Two runs gave identical answers.",
      "Repeated on the wave 6 code (issue-14 head df56562, tree identical to wave-6 adf1dfd), KLINT_JUDGE_MODE=remote: the same 75 answers, field by field.",
      "Labels on the slide: extraction delegator = src/catalog/code/common/extractors/traits_based_extraction_delegator.py; file metadata unit = src/catalog/code/common/units/file_metadata.py; delegator tests = tests/catalog/code/common/extractors/test_traits_based_extraction_delegator.py; project audit test = tests/cli/test_project_audit.py.",
      "Beyond the curated example (#55, single plants, not committed): caught a false file summary, an unsupported reason in a hunk, a false commit summary and an unsupported reason in a file; missed one subtle false hunk summary.",
      "How an agent produces the JSON and is sent back: docs/change-summary-stop-hook.md (a Stop hook with a 3-retry cap, no MCP server), tested by hand in #55.",
    ].join("\n\n"),
  );
  return spec;
}

function buildExtensibilitySlide() {
  const spec = createContentSlide(
    9,
    "A new suite runs end to end without touching core or app",
    "One test builds a whole suite in test code, adds it next to the built-in ones, and runs it as a command.",
    "tests/app/test_suite_plugins.py · tests/support/notes_suite.py",
  );
  const steps = [
    ["Write the parts", "A unit, an extractor, a renderer, a rule loader and its own answer scale (polite / rude)", "NoteUnit · NoteExtractor · NoteRenderer · POLITENESS_SCALE"],
    ["List one kind of audit", "The suite returns one AuditKind from list_audit_kinds()", "NotesSuite(BaseSuite)"],
    ["Add the suite", "One binding adds it to the suites the app can draw on", "multibind(list[BaseSuite], to=[NotesSuite])"],
    ["Run it as a command", "Exit 1 with a 'Rude' finding on each note, judged on the suite's own scale", "AuditCommandApp.run([folder, '--json'])"],
  ];
  steps.forEach(([name, detail, code], index) => {
    const y = CONTENT_TOP + index * 1.17;
    addBadge(spec, LEFT, y + 0.12, 0.55, String(index + 1), { fill: COLOR.accent, color: COLOR.ink, size: 16 });
    spec.text(LEFT + 0.8, y, 6.2, 0.38, name, { font: "head", size: 15, bold: true, color: COLOR.ink, valign: "middle" });
    spec.text(LEFT + 0.8, y + 0.38, 6.2, 0.36, detail, { size: 12, color: COLOR.ink, valign: "middle" });
    spec.text(LEFT + 0.8, y + 0.74, 6.2, 0.3, code, { font: "mono", size: 10, color: COLOR.muted, valign: "middle" });
  });
  const panelX = 8.1;
  const panelWidth = RIGHT - panelX;
  spec.rect(panelX, CONTENT_TOP, panelWidth, 4.0, { fill: COLOR.ink, radius: 0.12 });
  spec.text(panelX + 0.35, CONTENT_TOP + 0.3, panelWidth - 0.7, 1.0, "0 lines", {
    font: "head", size: 44, bold: true, color: COLOR.accent, valign: "middle",
  });
  spec.text(panelX + 0.35, CONTENT_TOP + 1.3, panelWidth - 0.7, 0.4, "changed in core or app for a new suite", {
    size: 14, bold: true, color: COLOR.white, valign: "middle",
  });
  spec.text(panelX + 0.35, CONTENT_TOP + 1.95, panelWidth - 0.7, 2.5, [
    { runs: "Wave 5 did it for real: the change-summary suite and its command added 1,181 lines; in core and app only one docstring changed.", spaceAfter: 10 },
    { runs: "Two kinds with different scales run in one process, and a kind id offered twice is refused before any run." },
  ], { size: 12.5, color: "D7DEEB" });
  spec.addNotes(
    [
      "Claim: a suite written only in test code runs end to end through the real command app, with no change to core or app.",
      "tests/app/test_suite_plugins.py: test_command_for_a_suite_added_in_test_code_runs_end_to_end builds the app with binding_overrides=[add_the_notes_suite] and asserts exit code PROBLEMS_FOUND (1), the examined notes, a 'Rude' answer on each note, and the rule asked about each subject. test_two_kinds_with_different_scales_run_in_one_process runs the code suite's file_contents kind and the notes kind side by side. test_two_suites_offering_one_kind_id_stop_the_run_from_being_built checks the duplicate id.",
      "tests/support/notes_suite.py: NoteUnit, NoteExtractor (BaseUnitExtractor[ScannedTarget]), NoteRenderer, FixedRuleLoader, POLITENESS_SCALE, NotesSuite (a DirectoryTreeSourceFactory that leaves out drafts/), and NotesDocumentSuite (a JSON document from disk or memory).",
      "Wave 5 numbers: git diff --stat e712070 50d2685 -- klint: 25 files, 1,181 insertions; -- klint/core klint/app: one file, klint/core/interfaces/renderer.py, a docstring of 3 lines.",
      "Before: adding a kind meant editing the AuditMode enum, the match in AuditPipeline and wiring.py (review, style A).",
    ].join("\n\n"),
  );
  return spec;
}

module.exports = { buildVerificationSlide, buildResultsSlide, buildExtensibilitySlide };
