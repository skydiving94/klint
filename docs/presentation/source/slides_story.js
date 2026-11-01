// Slides 1, 2 and 10 to 13: purpose, objectives, quality, debt, trade-offs
// and the recommendation.

const {
  COLOR,
  LEFT,
  RIGHT,
  CONTENT_TOP,
  createContentSlide,
  createDarkSlide,
  addChip,
  addCard,
} = require("./deck_parts");

function buildTitleSlide() {
  const spec = createDarkSlide();
  spec.text(LEFT + 0.3, 0.9, 11, 0.4, "ISSUE #22 · ARCHITECTURE OVERHAUL · AS BUILT ON wave-6", {
    size: 13, bold: true, color: COLOR.accent, valign: "middle",
  });
  spec.text(LEFT + 0.3, 1.5, 11, 1.1, "klint", {
    font: "head", size: 60, bold: true, color: COLOR.white, valign: "middle",
  });
  spec.text(LEFT + 0.3, 2.75, 11.2, 1.6,
    "A small model judge checks claims against evidence: code against rules, and now an AI agent's summaries of its change against the code, from each hunk up to the commit.",
    { font: "head", size: 24, color: COLOR.white },
  );
  const chips = [
    "Waves 0 to 6 · 17 sub-issues",
    "12 debt items: 9 resolved, 3 reduced",
    "461 tests · 5 import contracts kept",
  ];
  chips.forEach((label, index) => {
    addChip(spec, LEFT + 0.3 + index * 3.85, 5.2, 3.6, 0.55, label, {
      fill: COLOR.inkSoft, color: COLOR.white, size: 12.5,
    });
  });
  spec.text(LEFT + 0.3, 6.55, 11, 0.35, "For the director's review of #22 · every claim cites code on wave-6 in the speaker notes", {
    size: 12, color: "AEB8CC", valign: "middle",
  });
  spec.addNotes(
    [
      "Purpose in one line: klint asks a small model judge rule questions about units of evidence; #22 rebuilt it so that it can verify an agent's tiered change summaries, accuracy first, and take new suites without editing core or app.",
      "Numbers: 17 sub-issues in waves 0 to 6 (#23, #13; #24, #17, #25, #19; #26, #18; #27, #28, #29; #30, #31, #12; #32; #14, #33). Debt: slide 11. Tests: uv run pytest on wave-6 gives 461 passed. Contracts: uv run lint-imports gives 5 kept, 0 broken.",
      "Paths in these notes are under klint/ unless they start with tests/, docs/ or examples/, or name pyproject.toml or CLAUDE.md. Branch wave-6 at adf1dfd, plus this deck.",
    ].join("\n\n"),
  );
  return spec;
}

function buildObjectivesSlide() {
  const spec = createContentSlide(
    2,
    "All six objectives are met in code; two leave room by design",
    "#22's objectives in priority order, how each is met, and where.",
    "paths under klint/ unless they start with tests/",
  );
  const met = { text: "Met", bold: true, color: COLOR.pass, fill: COLOR.passLight, align: "center" };
  const ports = { text: "Ports met", bold: true, color: "8A5A12", fill: COLOR.accentLight, align: "center" };
  const room = { text: "Room left", bold: true, color: COLOR.inkSoft, fill: COLOR.mist, align: "center" };
  const where = (text) => ({ text, font: "mono", size: 9.5, color: COLOR.inkSoft });
  spec.table(
    LEFT,
    CONTENT_TOP,
    [3.55, 1.3, 4.65, 2.63],
    [
      ["Objective", "Status", "How it is met", "Where"],
      ["1. Verify an agent's tiered change summaries, accuracy first", met, "One suite and one command check hunk, file, package and commit; accuracy findings come first", where("catalog/change_summary/\ncli/change_summary_audit.py")],
      ["2. Add suites, units, extractors, rule packs, audit kinds without editing core or app", met, "A suite supplies its kinds of audit; a suite written only in tests runs end to end", where("core/interfaces/suite.py\ntests/app/test_suite_plugins.py")],
      ["3. One use case for the CLI, an API, a web UI, a hook or a GUI", met, "AuditPipeline.run_audit serves the three commands and the Stop hook; no API or web UI is built yet", where("app/pipeline/audit_pipeline.py")],
      ["4. Input and rules from any source", ports, "Source and rule-source ports; adapters today: disk tree, JSON from disk or memory, JSON rule files", where("core/interfaces/source.py\ncore/interfaces/rule_source.py")],
      ["5. Keep the one-way layer chain, checked by import-linter", met, "Five contracts, kept at every wave gate", where("pyproject.toml")],
      ["6. Leave room for finer units and other evidence", room, "Units nest; the renderer picked for each unit class decides what evidence the judge reads", where("core/models/unit.py\ncore/models/audit_kind.py")],
    ],
    {
      size: 12, rowHeight: 0.66, color: COLOR.ink, fill: COLOR.white,
      headerColor: COLOR.white, headerFill: COLOR.inkSoft, borderColor: COLOR.line,
    },
  );
  spec.addNotes(
    [
      "Objectives are #22's, in its priority order.",
      "1. ChangeSummarySuite (catalog/change_summary/__init__.py) offers the change_summary kind with ranked_tags (accuracy, completeness); command klint-change-summary (cli/change_summary_audit.py, pyproject.toml [project.scripts]). Live result: slide 8.",
      "2. BaseSuite (core/interfaces/suite.py); AuditKindRegistry (app/audit_kind_registry.py); the contract 'Suites: app and core import no named suite' (pyproject.toml); tests/app/test_suite_plugins.py with tests/support/notes_suite.py (slide 9).",
      "3. AuditPipeline.run_audit(AuditRequest) -> AuditOutcome (app/pipeline/audit_pipeline.py). cli/runner.py parses, calls it and prints. The Stop hook (docs/change-summary-stop-hook.md) runs the command. No API or web UI exists.",
      "4. Ports: BaseAuditSourceFactory / BaseAuditSource (core/interfaces/source.py), BaseRuleSource (core/interfaces/rule_source.py). Inputs: DiskPathInput, InMemoryBytesInput (core/models/audit_input.py). Adapters: DirectoryTreeSourceFactory, JsonDocumentSourceFactory (catalog/domain_neutral/sources/), JsonFileRuleSource (infra/rule_loader/json_file_rule_source.py); AuditRequest.custom_rule_source takes any rule source. Not built: git diff, stream, hook, MCP, database or API adapters.",
      "5. pyproject.toml [tool.importlinter], five contracts (slide 3).",
      "6. AuditableUnit.list_children (core/models/unit.py); AuditKind.unit_class_to_renderer and find_renderer (core/models/audit_kind.py); BaseUnitRenderer (core/interfaces/renderer.py). Finer units and AST extractors are out of scope (#22).",
    ].join("\n\n"),
  );
  return spec;
}

function buildQualitySlide() {
  const spec = createContentSlide(
    10,
    "Quality is checked by tools at every wave gate",
    "Tests, ruff, ruff format, strict mypy and import-linter pass on wave-6, and a live judge run is recorded per wave.",
    "pyproject.toml [tool.pytest] [tool.mypy] [tool.importlinter] · tests/ · klint/cli/exit_code.py",
  );
  const stats = [
    ["461", "tests pass", "Results checked through the commands, the use case and the auditor, with a fake judge", "tests/support/fakes.py"],
    ["strict", "mypy on klint/ and tests/", "No explicit Any allowed anywhere in klint/", "pyproject.toml [tool.mypy]"],
    ["291", "lines, the largest module", "Under the 300-line rule; 146 modules in klint/", "klint/cli/runner.py"],
    ["5 of 5", "import contracts kept", "The layer chain and the suite boundaries", "pyproject.toml"],
    ["30 · 18", "live failures on the examples", "The same before and after the wave 6 renames, field by field", "klint · klint-structure on examples/"],
    ["0 · 1 · 2", "exit codes", "No problem, problems found, could not run: for CI and the Stop hook", "klint/cli/exit_code.py"],
  ];
  const gap = 0.3;
  const cardWidth = (RIGHT - LEFT - 2 * gap) / 3;
  const cardHeight = 2.2;
  stats.forEach(([value, label, detail, source], index) => {
    const x = LEFT + (index % 3) * (cardWidth + gap);
    const y = CONTENT_TOP + Math.floor(index / 3) * (cardHeight + 0.3);
    spec.rect(x, y, cardWidth, cardHeight, { fill: COLOR.mist, radius: 0.1 });
    spec.text(x + 0.25, y + 0.15, cardWidth - 0.5, 0.75, value, {
      font: "head", size: 34, bold: true, color: COLOR.ink, valign: "middle",
    });
    spec.text(x + 0.25, y + 0.9, cardWidth - 0.5, 0.35, label, { size: 13, bold: true, color: COLOR.ink, valign: "middle" });
    spec.text(x + 0.25, y + 1.27, cardWidth - 0.5, 0.55, detail, { size: 11.5, color: COLOR.inkSoft });
    spec.text(x + 0.25, y + cardHeight - 0.38, cardWidth - 0.5, 0.28, source, { font: "mono", size: 9, color: COLOR.muted, valign: "middle" });
  });
  spec.addNotes(
    [
      "Commands (CLAUDE.md): uv run pytest, uv run ruff check ., uv run ruff format --check ., uv run mypy, uv run lint-imports. On wave-6 (adf1dfd): 461 passed; ruff and format clean; mypy 'no issues found'; lint-imports 5 kept, 0 broken.",
      "Tests check results through public entry points with FakeJudge (tests/support/fakes.py); pytest turns any unexpected KlintWarning into a failure (pyproject.toml filterwarnings).",
      "mypy: strict = true for klint and tests; disallow_any_explicit = true for klint.* (pyproject.toml).",
      "File sizes: wc -l over klint/**/*.py: the largest is klint/cli/runner.py with 291 lines; 146 Python modules. Four test files are over 300 lines (slide 11, new debt).",
      "Live: kev.serve with jaredpalmer/kev-4b on port 8009. klint examples/ gives 30 failures and klint-structure examples/mock_bad_project/ gives 18, both exit 1, identical to the wave 5 baseline (#55). Recorded in PR #56 and the wave 6 PR.",
      "Exit codes: ExitCode (cli/exit_code.py), decided by the director on #24 for exit 2.",
    ].join("\n\n"),
  );
  return spec;
}

function buildDebtSlide() {
  const spec = createContentSlide(
    11,
    "The review's debt, re-scored: 269 points down to 32",
    "D1 to D12 from the review of Oct 18, scored again against wave-6. Priority = (impact + risk) × (6 − effort).",
    "see the speaker notes for the file behind each line",
  );
  const resolved = { text: "Resolved", bold: true, color: COLOR.pass, fill: COLOR.passLight, align: "center" };
  const reduced = { text: "Reduced", bold: true, color: "8A5A12", fill: COLOR.accentLight, align: "center" };
  const rows = [
    ["D1", "Closed audit kinds; app imported a code-suite class", "32", "0", resolved],
    ["D2", "Judge contract was Mapping[str, Any] both ways", "28", "0", resolved],
    ["D4", "No end-to-end use case; exit code always 0", "28", "0", resolved],
    ["D3", "Input was always a path on disk", "27", "12", reduced],
    ["D5", "Rules chosen by language alone", "24", "0", resolved],
    ["D6", "One global answer scale and ignore list", "24", "0", resolved],
    ["D8", "Two extraction families and dispatchers", "21", "0", resolved],
    ["D10", "Rule loader over the 300-line limit", "20", "0", resolved],
    ["D12", "No audit order or roll-up", "18", "0", resolved],
    ["D7", "Prompt text built inside units", "16", "12", reduced],
    ["D9", "klint.json both config and rules; KEV_ names; mode a string", "16", "8", reduced],
    ["D11", "Installed package named src", "15", "0", resolved],
  ].map(([id, debt, before, now, state]) => [
    { text: id, bold: true },
    debt,
    { text: before, align: "center", color: COLOR.muted },
    { text: now, align: "center", bold: true },
    state,
  ]);
  spec.table(LEFT, CONTENT_TOP, [0.6, 4.75, 0.8, 0.8, 1.15], [["ID", "Debt in the review", "Before", "Now", "State"], ...rows], {
    size: 11.5, rowHeight: 0.37, color: COLOR.ink, fill: COLOR.white,
    headerColor: COLOR.white, headerFill: COLOR.inkSoft, borderColor: COLOR.line,
  });
  const panelX = 9.0;
  const panelWidth = RIGHT - panelX;
  spec.rect(panelX, CONTENT_TOP, panelWidth, 1.75, { fill: COLOR.ink, radius: 0.12 });
  spec.text(panelX + 0.3, CONTENT_TOP + 0.15, panelWidth - 0.6, 0.85, "269 → 32", {
    font: "head", size: 36, bold: true, color: COLOR.accent, valign: "middle",
  });
  spec.text(panelX + 0.3, CONTENT_TOP + 1.0, panelWidth - 0.6, 0.6, "summed priority · 9 resolved, 3 reduced", {
    size: 12.5, color: COLOR.white, valign: "middle",
  });
  addCard(spec, panelX, CONTENT_TOP + 2.0, panelWidth, 2.35, [
    { runs: [{ text: "New debt found", bold: true, font: "head", size: 14 }], spaceAfter: 6 },
    { runs: "Four test files over 300 lines", bullet: true },
    { runs: "Old names to delete next release: KEV_ settings, klint-project, --all, two rule fields", bullet: true },
    { runs: "action.yml inputs still named kev_*", bullet: true },
    { runs: "Setting names are strings, not an enum", bullet: true },
  ], { size: 11.5, spaceAfter: 5 });
  spec.addNotes(
    [
      "Method: the review's tech-debt score, priority = (impact + risk) × (6 − effort), each from 1 to 5; before = the review's table. A resolved item scores 0; a reduced one is scored on what is left.",
      "D1 resolved: suites supply AuditKind values (core/interfaces/suite.py, core/models/audit_kind.py); AuditKindRegistry (app/audit_kind_registry.py); app imports no named suite (pyproject.toml contract 2).",
      "D2 resolved: JudgeRequest, JudgeQuestion, JudgeAnswer (core/models/judge_exchange.py); BaseJudge.answer (core/interfaces/judge.py); disallow_any_explicit for klint.*.",
      "D4 resolved: AuditPipeline.run_audit (app/pipeline/audit_pipeline.py); ExitCode 0/1/2 (cli/exit_code.py).",
      "D3 reduced, now (2 + 1) × (6 − 2) = 12: source port with two adapters, DirectoryTreeSource and JsonDocumentSource (disk or memory) in catalog/domain_neutral/sources/; extractors generic over their input (core/interfaces/extractor.py). Left: git diff, stream, hook and MCP adapters.",
      "D5 resolved: AuditRule.is_applicable_to checks unit type, language and unit tags (core/models/rule.py); RuleSet.select_rules_for (core/models/rule_set.py); rule sources (core/interfaces/rule_source.py).",
      "D6 resolved: AuditKind.answer_scale per kind (PRACTICE_SCALE, SUMMARY_ACCURACY_SCALE); ignored names per source factory (CODE_IGNORED_NAMES in catalog/code/language_neutral/ignored_names.py).",
      "D8 resolved: one TraitsBasedExtractionDelegator[ExtractorT] (catalog/domain_neutral/extraction/traits_based_extraction_delegator.py) for file contents, file metadata and directory factories (catalog/code/__init__.py).",
      "D10 resolved: the loader is split into rule_pack_reader.py (230 lines), rule_pack_loader.py (186) and json_file_rule_source.py (28) in infra/rule_loader/; app/settings.py is 241; no module in klint/ is over 291.",
      "D12 resolved: AuditOrder.CHILDREN_FIRST (core/models/audit_order.py); RollUpStatus and FindingRollUp (core/models/roll_up_status.py, app/pipeline/roll_up.py).",
      "D7 reduced, now (2 + 2) × (6 − 3) = 12: renderers per unit class (core/interfaces/renderer.py, AuditKind.unit_class_to_renderer) within a 2,000-character budget (core/models/render_input.py; join_lines_within_budget in catalog/domain_neutral/renderers/character_budget.py). Left: the budget counts characters, not the judge's tokens.",
      "D9 reduced, now (1 + 1) × (6 − 2) = 8: JudgeMode enum (app/judge_mode.py); KLINT_JUDGE_* and KLINT_REPLACE_* names, with the KEV_ names as warned aliases (app/deprecated_setting_names.py); a --rules file's settings are ignored with a warning (app/project_config.py). Left: klint.json still holds both settings and rules, on purpose.",
      "D11 resolved: the package is klint/ (pyproject.toml [tool.setuptools.packages.find]).",
      "New debt: test files over 300 lines (tests/cli/test_file_audit.py, tests/infra/rule_loader/test_rule_pack_loader.py, tests/cli/test_structure_audit.py, tests/app/test_settings.py); the aliases listed in PR #56; action.yml inputs kev_mode and friends; KNOWN_SETTING_NAMES in app/project_config.py.",
    ].join("\n\n"),
  );
  return spec;
}

function buildTradeOffsSlide() {
  const spec = createContentSlide(
    12,
    "What we traded, and what we left for later",
    "Each choice below is in the code today; each deferred item has its port or seam already in place.",
    "klint/catalog/change_summary/renderers/ · klint/core/auditor.py · klint/core/interfaces/source.py",
  );
  const columnWidth = (RIGHT - LEFT - 0.4) / 2;
  const tradeOffs = [
    ["Upper levels read the checked summaries, not the diff", "Small context for a 4B judge; a mistake missed below can carry upward"],
    ["Children first", "Each level waits for the one below; units within a level still run together"],
    ["A small local judge, kev-4b", "Cheap and private; 40 to 81% confident on the planted errors; one subtle miss"],
    ["Suites as plugins with dependency injection", "No edit to core or app for a new suite; one registration pattern to learn"],
    ["A 2,000-character budget per subject", "No subject outgrows the judge; a trimmed one says what it left out"],
  ];
  const deferred = [
    ["Git diff, stream, hook and MCP inputs", "The source port is ready"],
    ["An API and a web UI", "They call AuditPipeline.run_audit"],
    ["Finer units and AST extractors for more languages", "Units nest; renderers pick the evidence"],
    ["Kev fine-tuning; the README", "Out of scope; the README waits for release"],
    ["Removing the old names", "Next release: delete the aliases and their tests"],
  ];
  const drawColumn = (x, heading, items, isTradeOff) => {
    spec.text(x, CONTENT_TOP, columnWidth, 0.4, heading, { font: "head", size: 17, bold: true, color: COLOR.ink, valign: "middle" });
    items.forEach(([name, detail], index) => {
      const y = CONTENT_TOP + 0.55 + index * 0.86;
      spec.rect(x, y, columnWidth, 0.74, { fill: isTradeOff ? COLOR.mist : COLOR.white, border: isTradeOff ? undefined : COLOR.line, radius: 0.1 });
      spec.text(x + 0.18, y + 0.05, columnWidth - 0.36, 0.32, name, { size: 12.5, bold: true, color: COLOR.ink, valign: "middle" });
      spec.text(x + 0.18, y + 0.37, columnWidth - 0.36, 0.34, detail, { size: 11, color: COLOR.inkSoft, valign: "middle" });
    });
  };
  drawColumn(LEFT, "Trade-offs we chose", tradeOffs, true);
  drawColumn(LEFT + columnWidth + 0.4, "Deferred, by design", deferred, false);
  spec.addNotes(
    [
      "Evidence for upper levels: the review's decision 3, option 2; FileSummaryRenderer and PackageSummaryRenderer (catalog/change_summary/renderers/upper_level_summary.py) show no code.",
      "Children first: Auditor._order_levels (core/auditor.py) groups units by depth and judges one group at a time; within a group at most 8 run at once (_MAX_CONCURRENT_AUDITS).",
      "Judge: kev-4b served by kev.serve (CLAUDE.md). Confidences on the planted errors, from the live run in #55: 39.6% to 53.2% on hunk 3, 42.4% to 81.2% on the package tests/. #55's extra single plants missed one subtle false hunk summary.",
      "Plugins: BaseSuite plus a module that multibinds list[BaseSuite] (catalog/*/__init__.py), wired with the injector library (app/wiring.py, KlintModule). This is the review's style C trade-off: a registration protocol to learn.",
      "Budget: DEFAULT_CHARACTER_BUDGET = 2_000 (core/models/render_input.py); join_lines_within_budget ends a trimmed text with a line saying what it left out (catalog/domain_neutral/renderers/character_budget.py).",
      "Deferred: BaseAuditSourceFactory (core/interfaces/source.py) for new inputs; AuditPipeline.run_audit for an API or web UI; out of scope in #22: Kev fine-tuning, HITL, new AST extractors, README. Aliases to remove: klint/app/deprecated_setting_names.py, klint/cli/klint_project_alias.py, the --all argument in klint/cli/runner.py, DEPRECATED_FIELD_NAME_TO_FIELD_NAME in klint/infra/rule_loader/rule_pack_reader.py.",
    ].join("\n\n"),
  );
  return spec;
}

function buildRecommendationSlide() {
  const spec = createDarkSlide();
  spec.text(LEFT + 0.3, 0.9, 11, 0.4, "RECOMMENDATION", { size: 13, bold: true, color: COLOR.accent, valign: "middle" });
  spec.text(LEFT + 0.3, 1.4, 11.5, 1.0, "Merge issue-22 into main", {
    font: "head", size: 44, bold: true, color: COLOR.white, valign: "middle",
  });
  const reasons = [
    ["Objective 1 works end to end", "On a real change, both planted errors are flagged and nothing else is"],
    ["The design holds its own rules", "Five import contracts kept; a new suite needs no edit to core or app"],
    ["The debt is down to what we chose to leave", "9 of 12 items resolved, 3 reduced; 461 tests and strict typing guard it"],
  ];
  reasons.forEach(([name, detail], index) => {
    const x = LEFT + 0.3 + index * 3.95;
    spec.rect(x, 3.0, 3.7, 1.8, { fill: COLOR.inkSoft, radius: 0.12 });
    spec.text(x + 0.25, 3.2, 3.2, 0.8, name, { font: "head", size: 17, bold: true, color: COLOR.white });
    spec.text(x + 0.25, 4.05, 3.2, 1.1, detail, { size: 13, color: "D7DEEB" });
  });
  spec.text(LEFT + 0.3, 5.6, 11.5, 0.7, [
    "The issue-22 → main pull request links every sub-issue PR, this deck and the change-summary run.",
    "Deck sources: docs/presentation/source/ · speaker notes: docs/presentation/speaker_notes.md",
  ], { size: 12, color: "AEB8CC", spaceAfter: 2 });
  spec.addNotes(
    [
      "The decision asked of the director: merge the issue-22 → main pull request.",
      "Evidence: slide 8 (live change-summary run, #55, repeated on wave-6), slide 3 (contracts), slide 9 (suite plugin test), slide 10 (quality), slide 11 (debt).",
      "What stays open after the merge is on slide 12: adapters, API and web UI, finer units, and deleting the old names in the next release.",
    ].join("\n\n"),
  );
  return spec;
}

module.exports = {
  buildTitleSlide,
  buildObjectivesSlide,
  buildQualitySlide,
  buildDebtSlide,
  buildTradeOffsSlide,
  buildRecommendationSlide,
};
