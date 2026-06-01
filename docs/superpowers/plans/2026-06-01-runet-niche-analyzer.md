# Runet Niche Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a testable MVP that ranks up to 100 Runet niche directions and writes CSV/Markdown recommendations.

**Architecture:** The tool is a small Python package with separated models, CSV I/O, market-data providers, scoring, reporting, and CLI orchestration. The first provider is deterministic demo data; real Yandex API integration can be added behind the same provider interface.

**Tech Stack:** Python 3.10+, standard library, pytest.

---

## File Structure

- `pyproject.toml` — package metadata, console script, pytest config.
- `README.md` — setup, CSV format, commands, API notes.
- `examples/directions.csv` — sample input for a 100-row compatible batch.
- `src/brainshtorm/__init__.py` — package version.
- `src/brainshtorm/models.py` — dataclasses and verdict constants.
- `src/brainshtorm/io.py` — CSV parsing, validation, CSV output.
- `src/brainshtorm/providers.py` — provider protocol and deterministic demo provider.
- `src/brainshtorm/scoring.py` — score calculation, verdict, recommendations.
- `src/brainshtorm/reporting.py` — Markdown report rendering.
- `src/brainshtorm/cli.py` — command line entrypoint.
- `tests/test_io.py` — CSV validation tests.
- `tests/test_scoring.py` — score and verdict tests.
- `tests/test_reporting.py` — report rendering tests.
- `tests/test_cli.py` — end-to-end CLI test.

## Tasks

### Task 1: CSV Validation

**Files:**
- Create: `tests/test_io.py`
- Create: `src/brainshtorm/models.py`
- Create: `src/brainshtorm/io.py`

- [ ] **Step 1: Write failing tests**

```python
def test_read_directions_accepts_valid_csv(tmp_path):
    path = tmp_path / "directions.csv"
    path.write_text(
        "direction,region,budget_rub,max_difficulty,project_type\n"
        "ремонт роботов пылесосов,Москва,150000,6,leadgen\n",
        encoding="utf-8",
    )

    directions = read_directions_csv(path)

    assert len(directions) == 1
    assert directions[0].direction == "ремонт роботов пылесосов"
    assert directions[0].budget_rub == 150000
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/test_io.py -v`
Expected: import failure because the package is not implemented yet.

- [ ] **Step 3: Implement models and CSV parser**

Create dataclasses for `DirectionInput`, parser validation for required columns, max 100 rows, positive budget, and difficulty range 1-10.

- [ ] **Step 4: Run tests and confirm pass**

Run: `pytest tests/test_io.py -v`
Expected: all `test_io.py` tests pass.

### Task 2: Scoring Engine

**Files:**
- Create: `tests/test_scoring.py`
- Create: `src/brainshtorm/scoring.py`
- Modify: `src/brainshtorm/models.py`

- [ ] **Step 1: Write failing tests**

```python
def test_high_quality_direction_gets_take_verdict():
    direction = DirectionInput("ремонт роботов пылесосов", "Москва", 150000, 6, "leadgen")
    metrics = MarketMetrics(
        demand=8500,
        trend=0.28,
        regional_affinity=1.25,
        commercial_intent=0.85,
        competition=0.35,
        estimated_launch_budget=110000,
        estimated_difficulty=5,
        seasonality=0.2,
        risk_level=0.1,
    )

    result = score_direction(direction, metrics)

    assert result.verdict == "take"
    assert result.score >= 75
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/test_scoring.py -v`
Expected: missing scoring implementation.

- [ ] **Step 3: Implement score calculation**

Implement normalized factor scores, risk penalty, verdict thresholds, and concise recommendations.

- [ ] **Step 4: Run tests and confirm pass**

Run: `pytest tests/test_scoring.py -v`
Expected: all scoring tests pass.

### Task 3: Reporting

**Files:**
- Create: `tests/test_reporting.py`
- Create: `src/brainshtorm/reporting.py`

- [ ] **Step 1: Write failing tests**

```python
def test_markdown_report_contains_ranked_verdicts():
    report = render_markdown_report([assessment])

    assert "# Runet Niche Analyzer Report" in report
    assert "ремонт роботов пылесосов" in report
    assert "take" in report
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/test_reporting.py -v`
Expected: missing report implementation.

- [ ] **Step 3: Implement Markdown report renderer**

Render summary counts, top candidates, and per-direction details.

- [ ] **Step 4: Run tests and confirm pass**

Run: `pytest tests/test_reporting.py -v`
Expected: all reporting tests pass.

### Task 4: CLI and Demo Provider

**Files:**
- Create: `tests/test_cli.py`
- Create: `src/brainshtorm/providers.py`
- Create: `src/brainshtorm/cli.py`
- Create: `src/brainshtorm/__init__.py`
- Create: `pyproject.toml`
- Create: `examples/directions.csv`

- [ ] **Step 1: Write failing tests**

```python
def test_cli_writes_csv_and_markdown(tmp_path):
    input_path = tmp_path / "directions.csv"
    output_dir = tmp_path / "out"
    input_path.write_text(sample_csv, encoding="utf-8")

    exit_code = main([str(input_path), "--output-dir", str(output_dir), "--provider", "demo"])

    assert exit_code == 0
    assert (output_dir / "analysis.csv").exists()
    assert (output_dir / "report.md").exists()
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/test_cli.py -v`
Expected: missing CLI/provider implementation.

- [ ] **Step 3: Implement provider and CLI**

Implement deterministic metrics from seed text, CLI args, output directory creation, CSV and Markdown writing.

- [ ] **Step 4: Run tests and confirm pass**

Run: `pytest tests/test_cli.py -v`
Expected: CLI test passes.

### Task 5: Documentation and Verification

**Files:**
- Create: `README.md`

- [ ] **Step 1: Document setup and usage**

Include install command, example command, CSV schema, demo provider behavior, and future Yandex API variables.

- [ ] **Step 2: Run full verification**

Run: `python -m pytest -v`
Expected: all tests pass.

Run: `python -m brainshtorm.cli examples/directions.csv --output-dir out/demo --provider demo`
Expected: `out/demo/analysis.csv` and `out/demo/report.md` are written.

- [ ] **Step 3: Commit and push**

Run:

```bash
git add -A
git commit -m "feat: add runet niche analyzer mvp"
git push
```

Expected: commit is pushed to `origin/master`.

