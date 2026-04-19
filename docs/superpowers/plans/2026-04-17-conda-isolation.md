# Conda Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Isolate each bioinformatics tool (MEANGS, NOVOPlasty, GetOrganelle, MitoZ) into its own Snakemake-managed conda environment so tools can be upgraded independently without conflicts.

**Architecture:** Each Snakemake rule gains a `conda:` directive pointing to a minimal per-tool environment YAML in `smk/envs/`. The main FastMitoAssembler environment is stripped to only snakemake + CLI dependencies. The `run` CLI command passes `use_conda=True` by default with an optional `--conda-prefix` for shared HPC caching.

**Tech Stack:** Snakemake ≥7 (use_conda / conda_prefix params), conda/mamba, Click, Python 3.9

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `FastMitoAssembler/smk/envs/meangs.yaml` | Conda env for MEANGS rule |
| Create | `FastMitoAssembler/smk/envs/novoplasty.yaml` | Conda env for NOVOPlasty rule |
| Create | `FastMitoAssembler/smk/envs/getorganelle.yaml` | Conda env for GetOrganelle rule |
| Create | `FastMitoAssembler/smk/envs/mitoz.yaml` | Conda env for MitozAnnotate rule |
| Create | `tests/test_run_options.py` | Tests for CLI option passing |
| Modify | `FastMitoAssembler/smk/main.smk` | Add `conda:` to MEANGS, NOVOPlasty, GetOrganelle, MitozAnnotate rules |
| Modify | `FastMitoAssembler/bin/_run.py` | Add `--use-conda/--no-use-conda` and `--conda-prefix` options |
| Modify | `environment.yml` | Strip to slim main env |
| Modify | `README.md` | Update installation instructions |

---

### Task 1: Create conda env files for each tool

**Files:**
- Create: `FastMitoAssembler/smk/envs/meangs.yaml`
- Create: `FastMitoAssembler/smk/envs/novoplasty.yaml`
- Create: `FastMitoAssembler/smk/envs/getorganelle.yaml`
- Create: `FastMitoAssembler/smk/envs/mitoz.yaml`

- [ ] **Step 1: Create the envs directory and meangs.yaml**

```bash
mkdir -p FastMitoAssembler/smk/envs
```

Write `FastMitoAssembler/smk/envs/meangs.yaml`:
```yaml
channels:
  - yccscucib
  - bioconda
  - conda-forge
  - defaults
dependencies:
  - meangs
  - seqkit
  - pip:
    - genbank
```

- [ ] **Step 2: Create novoplasty.yaml**

Write `FastMitoAssembler/smk/envs/novoplasty.yaml`:
```yaml
channels:
  - bioconda
  - conda-forge
  - defaults
dependencies:
  - novoplasty
  - seqkit
```

- [ ] **Step 3: Create getorganelle.yaml**

Write `FastMitoAssembler/smk/envs/getorganelle.yaml`:
```yaml
channels:
  - bioconda
  - conda-forge
  - defaults
dependencies:
  - getorganelle
  - seqkit
```

- [ ] **Step 4: Create mitoz.yaml**

Write `FastMitoAssembler/smk/envs/mitoz.yaml`:
```yaml
channels:
  - bioconda
  - conda-forge
  - defaults
dependencies:
  - mitoz>=3.6
```

- [ ] **Step 5: Validate all four files parse as valid YAML**

```bash
python -c "
import yaml, pathlib
for f in pathlib.Path('FastMitoAssembler/smk/envs').glob('*.yaml'):
    data = yaml.safe_load(f.read_text())
    assert 'channels' in data and 'dependencies' in data, f'{f}: missing required keys'
    print(f'OK: {f}')
"
```

Expected output:
```
OK: FastMitoAssembler/smk/envs/meangs.yaml
OK: FastMitoAssembler/smk/envs/novoplasty.yaml
OK: FastMitoAssembler/smk/envs/getorganelle.yaml
OK: FastMitoAssembler/smk/envs/mitoz.yaml
```

- [ ] **Step 6: Commit**

```bash
git add FastMitoAssembler/smk/envs/
git commit -m "feat: add per-rule conda environment files"
```

---

### Task 2: Add conda directives to Snakefile

**Files:**
- Modify: `FastMitoAssembler/smk/main.smk`

The path passed to `conda:` is relative to the Snakefile's location (`smk/`), so `"envs/meangs.yaml"` resolves to `smk/envs/meangs.yaml`. `NOVOPlasty_config` uses a pure Python `run:` block and needs no conda directive.

- [ ] **Step 1: Add conda directive to rule MEANGS**

In `FastMitoAssembler/smk/main.smk`, locate `rule MEANGS:` and add `conda:` after the `message:` line (or any position before `shell:`):

```python
rule MEANGS:
    input:
        fq1=FQ1,
        fq2=FQ2,
    output:
        seed_fas=seed_fas,
    params:
        outdir=MEANGS_DIR(),
        seed_input=SEED_INPUT,
    conda: "envs/meangs.yaml"
    message: "MEANGS for sample: {wildcards.sample}"
    log: LOG_DIR.joinpath('{sample}', 'meangs.log')
    benchmark: BENCHMARK_DIR.joinpath('{sample}', 'meangs.stat')
    shell:
        ...
```

- [ ] **Step 2: Add conda directive to rule NOVOPlasty**

In `rule NOVOPlasty:`, add `conda: "envs/novoplasty.yaml"` after `params:` block and before `message:`:

```python
rule NOVOPlasty:
    input:
        novoplasty_config=novoplasty_config,
    output:
        novoplasty_fasta=novoplasty_fasta,
    params:
        output_path = NOVOPLASTY_DIR(),
    conda: "envs/novoplasty.yaml"
    message: "NOVOPlasty for sample: {wildcards.sample}"
    log: LOG_DIR.joinpath('{sample}', 'novoplasty.log')
    benchmark: BENCHMARK_DIR.joinpath('{sample}', 'novoplasty.stat')
    shell:
        ...
```

- [ ] **Step 3: Add conda directive to rule GetOrganelle**

In `rule GetOrganelle:`, add `conda: "envs/getorganelle.yaml"` after `params:` and before `message:`:

```python
rule GetOrganelle:
    input:
        fq1=FQ1,
        fq2=FQ2,
        novoplasty_fasta=novoplasty_fasta,
    output:
        organelle_fasta_new=organelle_fasta_new,
    params:
        output_path=ORGANELLE_DIR(),
        output_path_temp=ORGANELLE_DIR("organelle"),
    conda: "envs/getorganelle.yaml"
    message: "GetOrganelle for sample: {wildcards.sample}"
    log: LOG_DIR.joinpath('{sample}', 'get_organelle.log')
    benchmark: BENCHMARK_DIR.joinpath('{sample}', 'get_organelle.stat')
    shell:
        ...
```

- [ ] **Step 4: Add conda directive to rule MitozAnnotate**

In `rule MitozAnnotate:`, add `conda: "envs/mitoz.yaml"` after `params:` and before `message:`:

```python
rule MitozAnnotate:
    input:
        fq1=FQ1,
        fq2=FQ2,
        organelle_fasta_new=organelle_fasta_new,
    output:
        circos=MITOZ_ANNO_RESULT_DIR("circos.png"),
        summary=MITOZ_ANNO_RESULT_DIR("summary.txt"),
        genbank=MITOZ_ANNO_RESULT_DIR(f"{{sample}}_{ORGANELLE_DB}.get_organelle.fasta_mitoscaf.fa.gbf"),
    params:
        outdir=MITOZ_ANNO_DIR()
    conda: "envs/mitoz.yaml"
    message: "MitozAnnotate for sample: {wildcards.sample}"
    log: LOG_DIR.joinpath('{sample}', 'mitoz_annotate.log')
    benchmark: BENCHMARK_DIR.joinpath('{sample}', 'mitoz_annotate.stat')
    shell:
        ...
```

- [ ] **Step 5: Verify Snakefile syntax**

```bash
python -c "
import ast, re
content = open('FastMitoAssembler/smk/main.smk').read()
rules_with_shell = ['MEANGS', 'NOVOPlasty', 'GetOrganelle', 'MitozAnnotate']
for rule in rules_with_shell:
    assert f'conda: \"envs/' in content or \"conda: 'envs/\" in content, f'missing conda directive'
    pattern = rf'rule {rule}:.*?conda:.*?\"envs/'
    assert re.search(pattern, content, re.DOTALL), f'rule {rule}: missing conda directive'
    print(f'OK: rule {rule} has conda directive')
"
```

Expected:
```
OK: rule MEANGS has conda directive
OK: rule NOVOPlasty has conda directive
OK: rule GetOrganelle has conda directive
OK: rule MitozAnnotate has conda directive
```

- [ ] **Step 6: Commit**

```bash
git add FastMitoAssembler/smk/main.smk
git commit -m "feat: add per-rule conda directives to Snakefile"
```

---

### Task 3: Update CLI to expose --use-conda and --conda-prefix

**Files:**
- Modify: `FastMitoAssembler/bin/_run.py`
- Create: `tests/test_run_options.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_run_options.py`:

```python
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from FastMitoAssembler.bin.main import cli


def _make_runner():
    return CliRunner()


def _base_args():
    return [
        'run',
        '--reads_dir', '/tmp/reads',
        '--samples', 'S1',
        '--dryrun',
    ]


def test_use_conda_true_by_default():
    runner = _make_runner()
    with patch('snakemake.snakemake') as mock_smk, \
         patch('os.path.isfile', return_value=True):
        result = runner.invoke(cli, _base_args())
        call_kwargs = mock_smk.call_args[1]
        assert call_kwargs.get('use_conda') is True, \
            f"use_conda should default to True, got: {call_kwargs}"


def test_no_use_conda_flag_disables():
    runner = _make_runner()
    with patch('snakemake.snakemake') as mock_smk, \
         patch('os.path.isfile', return_value=True):
        result = runner.invoke(cli, _base_args() + ['--no-use-conda'])
        call_kwargs = mock_smk.call_args[1]
        assert call_kwargs.get('use_conda') is False


def test_conda_prefix_passed_when_provided():
    runner = _make_runner()
    with patch('snakemake.snakemake') as mock_smk, \
         patch('os.path.isfile', return_value=True):
        result = runner.invoke(cli, _base_args() + ['--conda-prefix', '/shared/envs'])
        call_kwargs = mock_smk.call_args[1]
        assert call_kwargs.get('conda_prefix') == '/shared/envs'


def test_conda_prefix_absent_when_not_provided():
    runner = _make_runner()
    with patch('snakemake.snakemake') as mock_smk, \
         patch('os.path.isfile', return_value=True):
        result = runner.invoke(cli, _base_args())
        call_kwargs = mock_smk.call_args[1]
        assert 'conda_prefix' not in call_kwargs or call_kwargs['conda_prefix'] is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pip install pytest
pytest tests/test_run_options.py -v
```

Expected: 4 FAILs (AttributeError or AssertionError — `use_conda` not yet in options).

- [ ] **Step 3: Update _run.py**

In `FastMitoAssembler/bin/_run.py`, add two new options after the existing `--dryrun` option:

```python
@click.option('--use-conda/--no-use-conda', default=True, show_default=True,
              help='use conda environments for each rule')
@click.option('--conda-prefix', default=None,
              help='directory to store conda environments (shared across projects)')
```

Then update the `options` dict construction inside the `run` function. Replace:

```python
options = {
    'cores': kwargs['cores'],
    'dryrun': kwargs['dryrun'],
    'printshellcmds': True,
}
```

with:

```python
options = {
    'cores': kwargs['cores'],
    'dryrun': kwargs['dryrun'],
    'printshellcmds': True,
    'use_conda': kwargs['use_conda'],
}
if kwargs['conda_prefix']:
    options['conda_prefix'] = kwargs['conda_prefix']
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_run_options.py -v
```

Expected:
```
PASSED tests/test_run_options.py::test_use_conda_true_by_default
PASSED tests/test_run_options.py::test_no_use_conda_flag_disables
PASSED tests/test_run_options.py::test_conda_prefix_passed_when_provided
PASSED tests/test_run_options.py::test_conda_prefix_absent_when_not_provided
```

- [ ] **Step 5: Commit**

```bash
git add FastMitoAssembler/bin/_run.py tests/test_run_options.py
git commit -m "feat: add --use-conda and --conda-prefix options to run command"
```

---

### Task 4: Simplify environment.yml

**Files:**
- Modify: `environment.yml`

- [ ] **Step 1: Replace environment.yml content**

Overwrite `environment.yml` with the slim main environment:

```yaml
name: FastMitoAssembler
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.9
  - snakemake>=7
  - click
  - jinja2
  - pyyaml
  - ete3
```

Note: `genbank` is called as a shell command only inside the MEANGS rule, so it belongs in `envs/meangs.yaml` (already there), not the main env. The bioinformatics tools (MEANGS, NOVOPlasty, GetOrganelle, MitoZ, seqkit, BLAST) are removed — they are now managed per-rule.

- [ ] **Step 2: Verify the file is valid YAML with expected keys**

```bash
python -c "
import yaml
data = yaml.safe_load(open('environment.yml').read())
assert data['name'] == 'FastMitoAssembler'
assert 'snakemake>=7' in data['dependencies'] or any('snakemake' in str(d) for d in data['dependencies'])
bioinf_tools = {'meangs', 'novoplasty', 'getorganelle', 'mitoz', 'blast', 'spades'}
flat = ' '.join(str(d) for d in data['dependencies']).lower()
for tool in bioinf_tools:
    assert tool not in flat, f'tool {tool} should not be in main environment.yml'
print('OK: environment.yml is slim and valid')
"
```

Expected:
```
OK: environment.yml is slim and valid
```

- [ ] **Step 3: Commit**

```bash
git add environment.yml
git commit -m "feat: slim down environment.yml to main env dependencies only"
```

---

### Task 5: Update README installation instructions

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the Installation section**

In `README.md`, replace the entire `### Installation` section (from `#### 1. create environment` through the end of the install block) with:

```markdown
### Installation

#### 1. Create environment

```bash
# Recommended: use mamba for faster solving
mamba create -n FastMitoAssembler -c conda-forge \
    python=3.9 "snakemake>=7" click jinja2 pyyaml ete3
```

#### 2. Activate environment

```bash
conda activate FastMitoAssembler
```

#### 3. Install FastMitoAssembler

```bash
pip install FastMitoAssembler
# or from source
pip install -U dist/FastMitoAssembler*.whl
```

Tool environments (MEANGS, NOVOPlasty, GetOrganelle, MitoZ) are created automatically
by Snakemake on first run — no manual installation needed.
Each tool lives in its own isolated environment, so upgrading one tool never breaks others.
```

- [ ] **Step 2: Update the Run Workflow section to mention --use-conda default**

Find the existing `FastMitoAssembler run --help` usage block and add a note:

```markdown
# --use-conda is on by default; all tool environments are auto-created on first run
FastMitoAssembler run --configfile config.yaml --cores 8

# HPC: share tool environments across projects to avoid rebuilding
FastMitoAssembler run --configfile config.yaml --cores 8 \
    --conda-prefix ~/.conda/snakemake-envs
```

- [ ] **Step 3: Verify README still reads correctly**

```bash
python -c "
content = open('README.md').read()
assert 'mamba create' in content
assert '--conda-prefix' in content
assert 'mamba install' not in content or content.index('mamba install') > content.index('mamba create'), \
    'old mamba install steps should be removed'
print('OK: README updated')
"
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update installation instructions for conda-isolated workflow"
```

---

### Task 6: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update installation commands in CLAUDE.md**

Replace the Environment Setup section:

```markdown
## Environment Setup

```bash
# Create slim main environment (tool envs are auto-built on first run)
mamba create -n FastMitoAssembler -c conda-forge \
    python=3.9 "snakemake>=7" click jinja2 pyyaml ete3
conda activate FastMitoAssembler
pip install FastMitoAssembler
```
```

- [ ] **Step 2: Add upgrade workflow note to CLI Commands section**

After the existing run examples, add:

```markdown
# Upgrade a single tool: edit smk/envs/<tool>.yaml, re-run — Snakemake rebuilds only that env
# Share envs across projects on HPC:
FastMitoAssembler run --configfile config.yaml --conda-prefix ~/.conda/snakemake-envs
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for conda-isolated workflow"
```
