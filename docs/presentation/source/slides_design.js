// Slides 3 to 7: how klint is built.

const {
  COLOR,
  LEFT,
  RIGHT,
  CONTENT_TOP,
  createContentSlide,
  addChip,
  addBadge,
} = require("./deck_parts");

function buildLayersSlide() {
  const spec = createContentSlide(
    3,
    "Five layers; imports flow one way, and a tool checks it",
    "A layer may import only the layers below it. import-linter fails the check on any other import.",
    "pyproject.toml [tool.importlinter] · klint/{cli,app,catalog,infra,core}/",
  );
  const layers = [
    ["cli", "Three commands: parse, call the use case, print; exit 0, 1 or 2", "cli/"],
    ["app", "The use case: one pipeline in five stages; settings; wiring", "app/pipeline/"],
    ["catalog", "Suites: domain-neutral, code, change summary", "catalog/"],
    ["infra", "Rule-pack loading; the judge over HTTP or in process", "infra/"],
    ["core", "Ports, models and the auditor", "core/"],
  ];
  const fills = ["E9EEF6", "DFE6F1", "D3DCEA", "C7D2E3", COLOR.ink];
  const bandWidth = 7.3;
  const bandHeight = 0.78;
  layers.forEach(([name, description, folder], index) => {
    const y = CONTENT_TOP + index * (bandHeight + 0.14);
    const isCore = name === "core";
    const textColor = isCore ? COLOR.white : COLOR.ink;
    spec.rect(LEFT, y, bandWidth, bandHeight, { fill: fills[index], radius: 0.1 });
    spec.text(LEFT + 0.2, y, 1.3, bandHeight, name, {
      font: "head", size: 19, bold: true, color: textColor, valign: "middle",
    });
    spec.text(LEFT + 1.5, y, 4.2, bandHeight, description, {
      size: 13, color: textColor, valign: "middle",
    });
    spec.text(LEFT + 5.8, y, 1.35, bandHeight, folder, {
      font: "mono", size: 10.5, color: isCore ? "C9D3E6" : COLOR.inkSoft,
      valign: "middle", align: "right",
    });
  });
  const arrowX = LEFT + bandWidth + 0.35;
  spec.line(arrowX, CONTENT_TOP + 0.1, arrowX, CONTENT_TOP + 4.3, {
    color: COLOR.accent, width: 2.5, isArrow: true,
  });
  spec.text(arrowX + 0.12, CONTENT_TOP + 1.6, 0.5, 1.3, "imports", {
    size: 11, color: COLOR.muted, valign: "middle",
  });

  const panelX = 8.95;
  const panelWidth = RIGHT - panelX;
  spec.text(panelX, CONTENT_TOP, panelWidth, 0.4, "import-linter contracts", {
    font: "head", size: 16, bold: true, color: COLOR.ink, valign: "middle",
  });
  const contracts = [
    "Layers: cli > app > catalog > infra > core",
    "Suites: app and core import no named suite",
    "The domain-neutral suite imports no named suite",
    "Named suites do not import one another",
    "Language-neutral code does not import one language",
  ];
  contracts.forEach((contract, index) => {
    const y = CONTENT_TOP + 0.55 + index * 0.76;
    spec.rect(panelX, y, panelWidth, 0.64, { fill: COLOR.mist, radius: 0.1 });
    spec.text(panelX + 0.15, y, panelWidth - 1.1, 0.64, contract, {
      size: 11.5, color: COLOR.ink, valign: "middle",
    });
    addChip(spec, panelX + panelWidth - 0.85, y + 0.17, 0.72, 0.3, "KEPT", {
      fill: COLOR.passLight, color: COLOR.pass, size: 9.5,
    });
  });
  spec.addNotes(
    [
      "Claim: five layers, one-way imports, checked by a tool.",
      "Where: pyproject.toml, [tool.importlinter] holds five contracts. The first is the layers contract cli > app > catalog > infra > core. The other four are forbidden or independence contracts: app and core import neither klint.catalog.code nor klint.catalog.change_summary; klint.catalog.domain_neutral imports neither; klint.catalog.code and klint.catalog.change_summary are independent; klint.catalog.code.language_neutral does not import klint.catalog.code.python.",
      "Check: uv run lint-imports prints 'Contracts: 5 kept, 0 broken' on wave-6.",
      "Layer contents: cli/file_audit.py, structure_audit.py, change_summary_audit.py and runner.py (AuditCommandApp); app/pipeline/audit_pipeline.py (AuditPipeline) with acquisition.py, rule_selection.py, auditing.py, roll_up.py, ranking.py; app/settings.py (AppSettings), app/wiring.py (KlintModule); catalog/domain_neutral, catalog/code, catalog/change_summary; infra/rule_loader (RulePackLoader), infra/system_one (HttpSystemOneJudge, InProcessSystemOneJudge); core/interfaces (ports), core/models, core/auditor.py (Auditor).",
      "Before (review of Oct 18): the same chain existed, but app imported a code-suite class (D1). That import is gone, and the second contract now forbids it.",
    ].join("\n\n"),
  );
  return spec;
}

function buildPortsSlide() {
  const spec = createContentSlide(
    4,
    "The app's boundaries are ports in core; adapters plug in",
    "Twelve abstract classes in core/interfaces; their adapters live in catalog, infra and cli.",
    "klint/core/interfaces/*.py · klint/core/models/audit_kind.py (UnitSource)",
  );
  const cards = [
    ["Input", "BaseAuditSourceFactory", "Directory tree from disk; JSON document from disk or memory", "catalog/domain_neutral/sources/"],
    ["Extraction", "BaseUnitExtractor[T]", "File contents, project structure, change summaries, whole file", "catalog/*/extraction/"],
    ["File traits", "BaseFileTraitsIdentifier", "Language from the extension, tags from the file, klint.json overrides", "catalog/domain_neutral/|file_traits_identifiers/"],
    ["Rules", "BaseRuleSource, BaseRuleLoader", "JSON rule files; rule packs chosen by unit type, language and tags", "infra/rule_loader/"],
    ["Evidence", "BaseUnitRenderer", "Seven renderers, one per unit class, within a character budget", "catalog/*/renderers/"],
    ["Judge", "BaseJudge", "A System One server over HTTP, or kev in process", "infra/system_one/"],
    ["Suites", "BaseSuite", "Domain-neutral, code, change summary", "catalog/"],
    ["Progress", "Audit and scan listeners", "The progress bar and skipped-unit lines of the CLI", "cli/"],
  ];
  const gap = 0.25;
  const cardWidth = (RIGHT - LEFT - 3 * gap) / 4;
  const cardHeight = 2.3;
  cards.forEach(([role, port, adapters, folder], index) => {
    const x = LEFT + (index % 4) * (cardWidth + gap);
    const y = CONTENT_TOP + Math.floor(index / 4) * (cardHeight + 0.25);
    spec.rect(x, y, cardWidth, cardHeight, { fill: COLOR.mist, radius: 0.1 });
    spec.text(x + 0.18, y + 0.15, cardWidth - 0.36, 0.38, role, {
      font: "head", size: 16, bold: true, color: COLOR.ink, valign: "middle",
    });
    spec.text(x + 0.18, y + 0.55, cardWidth - 0.36, 0.5, port, {
      font: "mono", size: 10.5, bold: true, color: COLOR.accent, valign: "top",
    });
    spec.text(x + 0.18, y + 1.0, cardWidth - 0.36, 0.85, adapters, {
      size: 12, color: COLOR.ink, valign: "top",
    });
    spec.text(x + 0.18, y + cardHeight - 0.55, cardWidth - 0.36, 0.42, folder.split("|"), {
      font: "mono", size: 8.5, color: COLOR.muted, valign: "bottom",
    });
  });
  spec.addNotes(
    [
      "Claim: the boundaries the app and core depend on are ports in core/interfaces; their adapters sit in catalog, infra or cli. The one implementation in core, UnitSource (core/models/audit_kind.py), only joins a source factory to an extractor. The code suite also has its own extension points inside the suite, BaseFileMetadataExtractor and BaseDirectoryUnitFactory (catalog/code/language_neutral/extraction/), with Python and language-neutral adapters; the app never sees them.",
      "The twelve ports: source.py (BaseAuditSource, BaseAuditSourceFactory), extractor.py (BaseUnitExtractor, generic over its input), unit_source.py (BaseUnitSource), file_traits_identifier.py (BaseFileTraitsIdentifier), rule_source.py (BaseRuleSource), rule_loader.py (BaseRuleLoader), renderer.py (BaseUnitRenderer), judge.py (BaseJudge), suite.py (BaseSuite), audit_progress_listener.py, scan_progress_listener.py.",
      "Adapters: DirectoryTreeSource(Factory) and JsonDocumentSource(Factory) in catalog/domain_neutral/sources; FileContentsExtractor, ProjectStructureExtractor (catalog/code), ChangeSummaryExtractor (catalog/change_summary), WholeFileExtractor (catalog/domain_neutral); ExtensionFileTraitsIdentifier, TagDetectingFileTraitsIdentifier, OverridingFileTraitsIdentifier; JsonFileRuleSource and RulePackLoader in infra/rule_loader; renderers WholeFileRenderer, FileMetadataRenderer, DirectoryRenderer, PythonPackageRenderer, HunkSummaryRenderer, FileSummaryRenderer, PackageSummaryRenderer; HttpSystemOneJudge and InProcessSystemOneJudge in infra/system_one; DomainNeutralSuite, CodeSuite, ChangeSummarySuite; the CLI's _ProgressListener and TerminalScanProgressListener. UnitSource (core/models/audit_kind.py) joins a source factory to an extractor.",
      "The judge contract is typed: BaseJudge.answer(JudgeRequest) -> list[JudgeAnswer] (core/models/judge_exchange.py). mypy forbids an explicit Any anywhere in klint/ (pyproject.toml, disallow_any_explicit).",
      "Before: the extraction port took only a scanned file, input was always a disk path, and the judge contract was Mapping[str, Any] both ways (D2, D3).",
    ].join("\n\n"),
  );
  return spec;
}

function buildSuitesSlide() {
  const spec = createContentSlide(
    5,
    "Suites are plugins: each one supplies whole kinds of audit",
    "A kind of audit is one AuditKind value. The app looks it up by id and never imports a named suite.",
    "klint/core/models/audit_kind.py · klint/core/interfaces/suite.py · klint/app/audit_kind_registry.py",
  );
  const boxWidth = 3.6;
  const steps = [
    ["A suite's module", "multibind(list[BaseSuite], to=[ChangeSummarySuite])"],
    ["BaseSuite", "list_audit_kinds()\nregister_unit_types(registry)"],
    ["AuditKindRegistry", "find_audit_kind(kind_id); a kind id offered twice stops the build"],
  ];
  steps.forEach(([name, detail], index) => {
    const y = CONTENT_TOP + index * 1.55;
    spec.rect(LEFT, y, boxWidth, 1.15, { fill: index === 1 ? COLOR.ink : COLOR.mist, radius: 0.1 });
    const textColor = index === 1 ? COLOR.white : COLOR.ink;
    spec.text(LEFT + 0.18, y + 0.1, boxWidth - 0.36, 0.38, name, {
      font: "head", size: 15, bold: true, color: textColor, valign: "middle",
    });
    spec.text(LEFT + 0.18, y + 0.5, boxWidth - 0.36, 0.6, detail.split("\n"), {
      font: "mono", size: 10, color: index === 1 ? "D7DEEB" : COLOR.inkSoft,
    });
    if (index < steps.length - 1) {
      spec.line(LEFT + boxWidth / 2, y + 1.17, LEFT + boxWidth / 2, y + 1.53, {
        color: COLOR.accent, width: 2, isArrow: true,
      });
    }
  });
  const tableX = 4.6;
  spec.table(
    tableX,
    CONTENT_TOP,
    [1.75, 3.15, 3.23],
    [
      ["AuditKind field", "Code suite: project structure", "Change-summary suite"],
      ["Input", "A path on disk", "A path on disk, or bytes in memory"],
      ["Source → extractor", "Directory tree → ProjectStructureExtractor", "JSON document → ChangeSummaryExtractor"],
      ["Rules", "Built-in packs, chosen by language and tags", "summary_checks.json: five checks"],
      ["Answer scale", "Pass · Fail · Irrelevant · Lack of evidence", "Accurate · Inaccurate · Cannot tell"],
      ["Renderers", "File metadata, directory, Python package", "Hunk, file and package summary"],
      ["Audit order", "All at once", "Children first"],
      ["Ranked tags", "None", "Accuracy, then completeness"],
    ].map((row, rowIndex) =>
      rowIndex === 0 ? row : [{ text: row[0], bold: true }, row[1], row[2]],
    ),
    {
      size: 11.5, rowHeight: 0.5, color: COLOR.ink, fill: COLOR.white,
      headerColor: COLOR.white, headerFill: COLOR.inkSoft, borderColor: COLOR.line,
    },
  );
  spec.text(tableX, 6.05, 8.13, 0.6,
    "Each row is a field of AuditKind; the last field, the character budget, is 2,000 for both. The domain-neutral suite offers no kind: it registers the file unit the others build on.",
    { size: 11, color: COLOR.muted },
  );
  spec.addNotes(
    [
      "Claim: a suite supplies whole kinds of audit; the app never imports a named suite.",
      "BaseSuite (core/interfaces/suite.py) has two methods: list_audit_kinds() and register_unit_types(registry). AuditKind (core/models/audit_kind.py) holds kind_id, accepted_input_kinds, unit_source (UnitSource = source factory + extractor), rule_loader, answer_scale, unit_class_to_renderer, ranked_tags, audit_order and character_budget (DEFAULT_CHARACTER_BUDGET = 2_000 in core/models/render_input.py).",
      "Registration: each suite's injector module multibinds itself into list[BaseSuite]: CodeSuiteModule (catalog/code/__init__.py), ChangeSummarySuiteModule (catalog/change_summary/__init__.py), DomainNeutralSuiteModule (catalog/domain_neutral/__init__.py). The commands install all three through BuiltInSuitesModule (catalog/__init__.py), chosen in cli/wiring.py. KlintModule.provide_audit_kind_registry (app/wiring.py) builds AuditKindRegistry from every suite's kinds; AuditPipeline.run_audit calls find_audit_kind(request.audit_kind_id).",
      "Table sources: CodeSuite.list_audit_kinds (catalog/code/__init__.py) for project_structure: DirectoryTreeSourceFactory, ProjectStructureExtractor, PRACTICE_SCALE (catalog/code/language_neutral/practice_scale.py), FileMetadataRenderer, DirectoryRenderer, PythonPackageRenderer. ChangeSummarySuite.list_audit_kinds: JsonDocumentSourceFactory, ChangeSummaryExtractor, summary_checks.json, SUMMARY_ACCURACY_SCALE (summary_accuracy_scale.py), the three summary renderers, ranked_tags (ACCURACY, COMPLETENESS), AuditOrder.CHILDREN_FIRST.",
      "Duplicate kind ids: tests/app/test_suite_plugins.py::test_two_suites_offering_one_kind_id_stop_the_run_from_being_built.",
      "Before: audit kinds were a closed enum with a match in AuditPipeline, and one global answer scale (D1, D6).",
    ].join("\n\n"),
  );
  return spec;
}

function buildRunSlide() {
  const spec = createContentSlide(
    6,
    "One run, stage by stage, behind one call",
    "Every caller sends an AuditRequest to AuditPipeline.run_audit and gets an AuditOutcome back.",
    "klint/app/pipeline/ (stage files) · klint/app/audit_kind_registry.py · klint/core/auditor.py · klint/cli/exit_code.py",
  );
  const callers = [
    ["klint · klint-structure · klint-change-summary", COLOR.mist, COLOR.ink],
    ["Claude Code Stop hook, through the command", COLOR.mist, COLOR.ink],
    ["An API or a web UI: not built, same call", COLOR.white, COLOR.muted],
  ];
  const callerWidth = 3.9;
  callers.forEach(([label, fill, color], index) => {
    const x = LEFT + index * (callerWidth + 0.215);
    addChip(spec, x, CONTENT_TOP, callerWidth, 0.5, label, {
      fill, color, size: 11.5, border: index === 2 ? COLOR.line : undefined,
    });
    spec.line(x + callerWidth / 2, CONTENT_TOP + 0.52, x + callerWidth / 2, CONTENT_TOP + 0.9, {
      color: COLOR.line, width: 1.5, isArrow: true, isDashed: index === 2,
    });
  });
  spec.rect(LEFT, CONTENT_TOP + 0.95, RIGHT - LEFT, 0.55, { fill: COLOR.ink, radius: 0.1 });
  spec.text(LEFT, CONTENT_TOP + 0.95, RIGHT - LEFT, 0.55,
    [[{ text: "AuditPipeline.run_audit(AuditRequest) ", font: "mono", bold: true }, { text: "→ AuditOutcome: report, files read, units selected" }]],
    { size: 13, color: COLOR.white, align: "center", valign: "middle" },
  );
  const stages = [
    ["Find the kind", "By id, among the suites' kinds", "audit_kind_registry.py"],
    ["Acquire units", "Source reads the input; extractor gives units", "acquisition.py"],
    ["Select rules", "By unit type, language and tags", "rule_selection.py"],
    ["Audit", "Renderer writes the evidence; judge answers", "auditing.py"],
    ["Roll up", "Own problem, problem below, or none", "roll_up.py"],
    ["Rank", "Problems first, then ranked tags", "ranking.py"],
  ];
  const gap = 0.22;
  const stageWidth = (RIGHT - LEFT - 5 * gap) / 6;
  const stageY = CONTENT_TOP + 1.85;
  stages.forEach(([name, detail, file], index) => {
    const x = LEFT + index * (stageWidth + gap);
    spec.rect(x, stageY, stageWidth, 2.15, { fill: COLOR.mist, radius: 0.1 });
    addBadge(spec, x + 0.15, stageY + 0.15, 0.42, String(index + 1), { fill: COLOR.accent, color: COLOR.ink, size: 13 });
    spec.text(x + 0.15, stageY + 0.65, stageWidth - 0.3, 0.4, name, {
      font: "head", size: 14, bold: true, color: COLOR.ink, valign: "middle",
    });
    spec.text(x + 0.15, stageY + 1.05, stageWidth - 0.3, 0.7, detail, { size: 11.5, color: COLOR.ink });
    spec.text(x + 0.15, stageY + 1.75, stageWidth - 0.25, 0.3, file, { font: "mono", size: 8.5, color: COLOR.muted, valign: "middle" });
    if (index < stages.length - 1) {
      spec.line(x + stageWidth + 0.02, stageY + 1.07, x + stageWidth + gap - 0.02, stageY + 1.07, {
        color: COLOR.accent, width: 2, isArrow: true,
      });
    }
  });
  spec.text(LEFT, 6.2, RIGHT - LEFT, 0.55,
    [[
      { text: "The commands turn the outcome into an exit code: ", color: COLOR.muted },
      { text: "0", bold: true }, { text: " no problem · ", color: COLOR.muted },
      { text: "1", bold: true }, { text: " problems found · ", color: COLOR.muted },
      { text: "2", bold: true }, { text: " the audit could not run, or no unit could be audited", color: COLOR.muted },
    ]],
    { size: 13, color: COLOR.ink, valign: "middle" },
  );
  spec.addNotes(
    [
      "Claim: one call serves every entry point, and a run is a fixed list of named stages.",
      "AuditPipeline.run_audit (app/pipeline/audit_pipeline.py): find_audit_kind (AuditKindRegistry), then AuditPreparer.prepare_audit (app/pipeline/audit_preparer.py), which runs UnitAcquisition.acquire_units (acquisition.py) and RuleSelection.select_rules (rule_selection.py); then UnitAuditing.audit_units (auditing.py), which hands the units to Auditor (core/auditor.py); then FindingRollUp.roll_up (roll_up.py) and FindingRanking.rank_findings (ranking.py). AuditRequest carries audit_input, audit_kind_id, custom_rule_source, min_confidence and two progress listeners; AuditOutcome carries report, scanned_file_count and selected_unit_ids.",
      "Auditor: renders each unit with the kind's renderer, asks the judge one JudgeRequest per unit, at most 8 units at a time (_MAX_CONCURRENT_AUDITS). With CHILDREN_FIRST it judges one depth of nesting at a time, deepest first (_order_levels).",
      "Ranking: on a unit, findings come by the sort rank of their answer (problems first), then by ranked tag, then confidence, then rule id (FindingRanking docstring).",
      "Callers: cli/runner.py (AuditCommandApp.run_with_arguments) only parses, calls run_audit and prints; ExitCode in cli/exit_code.py (NO_PROBLEMS 0, PROBLEMS_FOUND 1, RUN_ERROR 2). The Stop hook in docs/change-summary-stop-hook.md runs klint-change-summary --json. No API or web UI exists; they would call the same method.",
      "Before: AuditPipeline only prepared; the run was joined in cli/runner.py and the exit code was always 0 (D4).",
    ].join("\n\n"),
  );
  return spec;
}

module.exports = { buildLayersSlide, buildPortsSlide, buildSuitesSlide, buildRunSlide };
