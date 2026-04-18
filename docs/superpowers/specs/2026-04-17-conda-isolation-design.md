# Design: Per-Rule Conda Isolation for FastMitoAssembler

**Date:** 2026-04-17  
**Status:** Approved

## Problem

All bioinformatics tools (MEANGS, NOVOPlasty, GetOrganelle, SPAdes, MitoZ, BLAST, seqkit) are installed in a single conda environment. Upgrading any one tool (e.g., MitoZ to 3.6) risks dependency conflicts that break the entire environment. Initial installation is also complex, requiring manual `mamba install` of 6+ tools.

## Goals

- Independent tool upgrades without environment conflicts
- Simpler initial installation
- Compatible with local workstations and conda-based HPC clusters (SGE/SLURM)

## Solution: Snakemake `--use-conda` with per-rule environments

Each Snakemake rule gets its own minimal conda environment file. Snakemake creates and caches these environments automatically on first run. The main FastMitoAssembler environment is stripped down to only what the CLI itself needs.

## Architecture

```
Main environment (FastMitoAssembler)
  Dependencies: snakemake, click, jinja2, pyyaml, ete3

Per-rule tool environments (managed by Snakemake)
  smk/envs/meangs.yaml       → rule MEANGS
  smk/envs/novoplasty.yaml   → rule NOVOPlasty
  smk/envs/getorganelle.yaml → rule GetOrganelle
  smk/envs/mitoz.yaml        → rule MitozAnnotate
```

`NOVOPlasty_config` uses a pure Python `run:` block and requires no conda directive.

## File Changes

### New files: `FastMitoAssembler/smk/envs/`

**`envs/meangs.yaml`**
```yaml
channels: [yccscucib, bioconda, conda-forge, defaults]
dependencies:
  - meangs
  - seqkit
  - pip:
    - genbank
```

**`envs/novoplasty.yaml`**
```yaml
channels: [bioconda, conda-forge, defaults]
dependencies:
  - novoplasty
  - seqkit
```

**`envs/getorganelle.yaml`**
```yaml
channels: [bioconda, conda-forge, defaults]
dependencies:
  - getorganelle
  - seqkit
```

**`envs/mitoz.yaml`**
```yaml
channels: [bioconda, conda-forge, defaults]
dependencies:
  - mitoz>=3.6
```

### Modified: `environment.yml`

Stripped to main env dependencies only:
```yaml
name: FastMitoAssembler
channels: [conda-forge, defaults]
dependencies:
  - python=3.9
  - snakemake>=7
  - click
  - jinja2
  - pyyaml
  - ete3
```

### Modified: `FastMitoAssembler/smk/main.smk`

Add `conda:` directive to each rule with an external shell command:

```python
rule MEANGS:
    conda: "envs/meangs.yaml"
    ...

rule NOVOPlasty:
    conda: "envs/novoplasty.yaml"
    ...

rule GetOrganelle:
    conda: "envs/getorganelle.yaml"
    ...

rule MitozAnnotate:
    conda: "envs/mitoz.yaml"
    ...
```

### Modified: `FastMitoAssembler/bin/_run.py`

Add `--use-conda` (default `True`) and `--conda-prefix` options, pass them to `snakemake.snakemake()`:

```python
@click.option('--use-conda/--no-use-conda', default=True, show_default=True,
              help='use conda environments for each rule')
@click.option('--conda-prefix', default=None,
              help='directory to store conda environments (shared across projects)')
```

## Installation Flow (After)

```bash
# 1. Create slim main environment
mamba create -n FastMitoAssembler -c conda-forge python=3.9 snakemake click jinja2 pyyaml ete3
conda activate FastMitoAssembler

# 2. Install FastMitoAssembler
pip install FastMitoAssembler

# 3. Prepare databases (tool envs built automatically on first run)
FastMitoAssembler prepare ncbitaxa
FastMitoAssembler prepare organelle -a animal_mt
```

## Usage

```bash
# Normal run (--use-conda is on by default)
FastMitoAssembler run --configfile config.yaml --cores 8

# HPC: share conda env cache across projects to avoid rebuilding
FastMitoAssembler run --configfile config.yaml --cores 8 \
    --conda-prefix ~/.conda/snakemake-envs
```

## Upgrading a Tool

To upgrade MitoZ to a new version: edit `envs/mitoz.yaml`, change the version pin, then re-run. Snakemake detects the env file change and rebuilds only the MitoZ environment. All other tool environments are unaffected.

## Trade-offs

- First run is slower while Snakemake builds the tool environments (one-time cost, cached after)
- `--use-conda` requires `conda` to be on PATH when Snakemake runs (always true in the FastMitoAssembler conda environment)
