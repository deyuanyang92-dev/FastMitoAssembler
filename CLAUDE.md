# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastMitoAssembler (`fma`) is a pipeline for mitochondrial genome assembly and annotation. It orchestrates multiple bioinformatics tools (MEANGS, NOVOPlasty, GetOrganelle, MitoZ) in isolated conda environments to avoid dependency conflicts.

**Core Feature**: All tools support both **Snakemake** and **Python** execution backends. Python backend requires no Snakemake installation, making the tool more lightweight and universal.

## ⚠️ Critical: MEANGS scaffold_seeds.fas Bug

**MEANGS in deepin mode writes `scaffold_seeds.fas` to CWD, not sample directory!**

```python
# MEANGS source code (hardcoded filename)
mitoSeeds='scaffold_seeds.fas'  # Writes to CWD!
```

**Impact**: Parallel runs will overwrite each other's seed files.

**Solution**: Each sample MUST run in isolated working directory:
```python
# Correct: isolate each sample
work_dir = output_dir / sample
subprocess.Popen(cmd, cwd=str(work_dir))  # scaffold_seeds.fas goes to work_dir
```

**Verification**:
```bash
# Wrong: only one seed file (last sample wins)
/output/scaffold_seeds.fas

# Correct: each sample has its own seed
/output/sample1/scaffold_seeds.fas
/output/sample2/scaffold_seeds.fas
```

## Common Commands

### Installation & Setup
```bash
# Install package in development mode
pip install -e .

# Install all tool environments (MEANGS, NOVOPlasty, GetOrganelle, MitoZ)
fma prepare tools

# Prepare databases
fma prepare ncbitaxa
fma prepare organelle -a animal_mt

# Verify installation
fma check
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_check.py

# Run integration tests (requires real snakemake)
FMA_INTEGRATION=1 pytest tests/test_integration.py
```

### Running the Pipeline
```bash
# Initialize project config
fma init

# Run specific stages (both backends supported)
fma meangs --backend python --reads_dir /data
fma novoplasty --backend python --reads_dir /data
fma getorganelle --backend python --reads_dir /data
fma mitoz --backend python --result_dir result

# Run chained workflows (both backends supported)
fma mg-nov --backend python --reads_dir /data      # MEANGS -> NOVOPlasty
fma mg-get --backend python --reads_dir /data      # MEANGS -> GetOrganelle
fma mg-nov-get --backend python --reads_dir /data  # MEANGS -> NOVOPlasty -> GetOrganelle

# Run full pipeline (Snakemake backend)
fma run --configfile config.yaml

# Dry-run to preview
fma run --configfile config.yaml --dryrun
```

## Execution Backends

All tools support two execution modes:

### Snakemake Backend (Default)

- **All tools supported**: MEANGS, NOVOPlasty, GetOrganelle, MitoZ
- **Best for**: Complex workflow orchestration, dependency management
- **Requires**: Snakemake installation

```bash
# Default Snakemake backend
fma getorganelle --reads_dir /data --samples S1 S2
```

### Python Backend (Optional)

- **All tools supported**: MEANGS, NOVOPlasty, GetOrganelle, MitoZ
- **Best for**: Simple batch processing, lightweight deployment
- **Requires**: No Snakemake dependency

```bash
# Python backend - no Snakemake needed
fma getorganelle --backend python --parallel-jobs 5 --reads_dir /data

# Additional Python backend options
fma meangs --backend python --force          # Force re-run
fma novoplasty --backend python --overwrite  # Overwrite existing output
fma mitoz --backend python --no-resume       # Don't resume incomplete runs
```

### Backend Comparison

| Tool | Snakemake Backend | Python Backend | Runner Class |
|------|-------------------|----------------|--------------|
| MEANGS | ✓ | ✓ | `MeangsRunner` |
| NOVOPlasty | ✓ | ✓ | `NovoplastyRunner` |
| GetOrganelle | ✓ | ✓ | `GetOrganelleRunner` |
| MitoZ | ✓ | ✓ | `MitozRunner` |

### Chained Workflows

| Command | Pipeline | Python Backend |
|---------|----------|----------------|
| mg-nov | MEANGS → NOVOPlasty | ✓ |
| mg-get | MEANGS → GetOrganelle | ✓ |
| mg-nov-get | MEANGS → NOVOPlasty → GetOrganelle | ✓ |

## Architecture

### Two-Layer Environment System
```
FastMitoAssembler (main env)          ← pipeline orchestrator (CLI + workflow)
├── FastMitoAssembler-meangs          ← MEANGS tool
├── FastMitoAssembler-novoplasty      ← NOVOPlasty tool
├── FastMitoAssembler-getorganelle    ← GetOrganelle tool
└── FastMitoAssembler-mitoz           ← MitoZ tool
```

Each bioinformatics tool runs in its own isolated conda environment. Tool locations are stored in `~/.config/FastMitoAssembler/tool_envs.yaml`.

### Key Components

**CLI Layer** (`FastMitoAssembler/bin/`):
- `main.py` - Click-based CLI entry point
- `_stages.py` - Individual stage commands with `--backend` option
- `_workflow.py` - Snakemake workflow execution, sample detection, config merging
- `_check.py` - Tool environment detection and validation
- `_config.py` - Tool configuration management
- `runners/` - Python backend runners (Snakemake-free execution)
  - `_base_runner.py` - Abstract base class with common logic
  - `_meangs_runner.py` - MEANGS runner
  - `_novoplasty_runner.py` - NOVOPlasty runner
  - `_getorganelle_runner.py` - GetOrganelle runner (implemented)
  - `_mitoz_runner.py` - MitoZ runner

**Workflow Layer** (`FastMitoAssembler/smk/`):
- `main.smk` - Snakemake entry point, defines all stage targets
- `config.yaml` - Default configuration template
- `rules/*.smk` - Tool-specific Snakemake rules

### Python Runner Design

All Python runners follow a common pattern:

```python
class BaseRunner:
    def build_command(self, **kwargs) -> List[str]:
        """Build command-line arguments"""
        raise NotImplementedError

    def is_sample_done(self, output_dir: Path) -> bool:
        """Check if sample already completed"""
        raise NotImplementedError

    def run_single(self, sample: str, **kwargs) -> Dict:
        """Execute single sample with Popen streaming"""

    def run_batch(self, samples: Dict, parallel_jobs: int = 3, **kwargs) -> List[Dict]:
        """Parallel batch execution with ThreadPoolExecutor"""
```

**Key Features**:
- Popen streaming (avoids buffer deadlock)
- Checkpoint detection (auto-resume incomplete runs)
- ThreadPoolExecutor parallel execution
- Success keyword detection from logs

### Configuration Flow

1. `fma init` creates `config.yaml` from template
2. CLI options override config file values
3. `_workflow.py` merges defaults + file + CLI options
4. Snakemake receives final config via `--configfile` (or Python runner uses directly)

### Sample Detection

Samples are auto-detected from `reads_dir` using suffix patterns:
- `fq_path_pattern: '{sample}/{sample}_1.clean.fq.gz'`
- `fastq_pos: recursive` (search subdirs), `subdir` (one level), or `flat` (no subdirs)

### Seed Handling

The pipeline supports multiple seed sources for assembly:
- **MEANGS**: Auto-generates seed from reads
- **NOVOPlasty**: `novoplasty_seed_source: user|meangs`
- **GetOrganelle**: `getorganelle_seed_source: none|meangs|novoplasty`

## Test Results

Testing has been conducted in `new-test/` directory:

```
new-test/
├── getorganelle-test/
│   ├── snakemake/          # Snakemake backend test results
│   ├── python/             # Python backend test results
│   ├── logs/               # Test logs
│   ├── TEST_REPORT.md      # Test report
│   └── IMPLEMENTATION_REPORT.md
└── pipeline-test/          # Full pipeline tests
    ├── 1.getorganelle/     # GetOrganelle assembly
    ├── 2.summary/          # Results summary
    ├── 3.mitoz/            # MitoZ annotation
    ├── 4.reorder/          # Gene reorder
    ├── 5.genes/            # Gene extraction
    ├── 6.blast/            # BLAST annotation
    └── final_report/       # Final report
```

## Important Patterns

### Adding New Parameters

1. Add to `CONFIG_ARGUMENTS` in `_workflow.py`
2. Add to `config.yaml` with documentation
3. Add Click option in `_stages.py` if stage-specific
4. Update Snakemake rule to use the parameter

### Tool Environment Configuration

Tools can be configured via:
```bash
# Auto-detect and save
fma check --save

# Manual configuration
fma config set meangs --conda-env my_env
fma config set mitoz --bin-dir /opt/mitoz/bin
```

### Testing Strategy

- Unit tests mock `snakemake` module (see `conftest.py`)
- Integration tests set `FMA_INTEGRATION=1` to use real Snakemake
- Test fixtures should not require actual tool installations

## File References

- Main Snakefile: `FastMitoAssembler/smk/main.smk`
- Default config: `FastMitoAssembler/smk/config.yaml`
- Python runners: `FastMitoAssembler/bin/runners/`
- Tool environments: `~/.config/FastMitoAssembler/tool_envs.yaml`
- Version info: `FastMitoAssembler/version.json`
