# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

`FastMitoAssembler` (aliases: `fma`, `FMA`) is a Python CLI tool that wraps a Snakemake workflow for fast, accurate assembly and annotation of mitochondrial genomes from paired-end Illumina reads. It chains four external tools in sequence: MEANGS → NOVOPlasty → GetOrganelle → MitoZ.

## Build & Install

```bash
# Build distribution packages
bash build.sh

# Install locally (editable for development)
pip install -e .

# Install from built wheel
pip install -U dist/FastMitoAssembler*.whl
```

## Run Tests

```bash
python -m pytest tests/ -v
```

## Environment Setup

```bash
# Create slim main environment (tool envs are auto-built on first run by Snakemake)
mamba create -n FastMitoAssembler -c conda-forge \
    python=3.9 "snakemake>=7" click jinja2 pyyaml ete3
conda activate FastMitoAssembler
pip install git+https://github.com/deyuanyang92-dev/FastMitoAssembler.git
```

## CLI Commands

All commands work with `FastMitoAssembler`, `fma`, or `FMA`.

```bash
# Generate config files in the current directory
fma init                      # creates config.yaml
fma init --options            # also creates options.yaml
fma init --force              # overwrite without prompting

# Check which bioinformatics tools are available
fma check                     # probe each tool (MEANGS, NOVOPlasty, GetOrganelle, MitoZ)
fma check --save              # save working tool configs globally to
                              # ~/.config/FastMitoAssembler/tool_envs.yaml

# Prepare databases (run once before first use)
fma prepare ncbitaxa
fma prepare organelle -a animal_mt

# Run the workflow
fma run --configfile config.yaml --cores 8
fma run --configfile config.yaml --dryrun        # preview without executing
fma run --reads_dir ../data                      # auto-detect samples from reads_dir

# HPC: share tool envs across projects
fma run --configfile config.yaml --conda-prefix ~/.conda/snakemake-envs

# Upgrade a single tool: edit smk/envs/<tool>.yaml, re-run — Snakemake rebuilds only that env
```

## Architecture

The entry point is `FastMitoAssembler/bin/main.py`, which registers CLI command groups via Click:
- `run` (`bin/_run.py`): validates inputs, merges CLI args + configfile + global tool_envs, validates bin_dir entries, then calls `snakemake.snakemake()`
- `prepare` (`bin/_other.py`): sets up GetOrganelle databases and ete3.NCBITaxa
- `init` (`bin/_init.py`): copies bundled config/options templates to the current directory
- `check` (`bin/_check.py`): probes each tool for availability, optionally saves to global config

The Snakemake workflow lives in `FastMitoAssembler/smk/main.smk`. Five rules in order:
1. **MEANGS** — detects mitochondrial seed sequence (or uses provided `.fasta`/`.gbk` as `seed_input`)
2. **NOVOPlasty_config** — renders Jinja2 template into a NOVOPlasty config file
3. **NOVOPlasty** — assembles the mitochondrial genome
4. **GetOrganelle** — re-assembles using NOVOPlasty output as seed; subsets input to 5G if needed
5. **MitozAnnotate** — annotates genome, produces `circos.png`, `summary.txt`, `.gbf`

Each rule has a `tool_prefix` param computed by `_shell_prefix(tool)` in `main.smk`, which supports per-tool conda env or bin_dir overrides.

`FastMitoAssembler/__init__.py` exposes the bundled Snakefile path and loads defaults from `smk/config.yaml` and `smk/options.yaml` at import time.

## Configuration

**`config.yaml`** — biological/sample parameters + tool overrides:
```yaml
reads_dir: '../data/'
samples: ['sample1']          # omit to auto-detect via --suffix_fq
fq_path_pattern: '{sample}/{sample}_1.clean.fq.gz'
organelle_database: 'animal_mt'
genetic_code: 5
clade: 'Annelida-segmented-worms'
genome_min_size: 12000
genome_max_size: 22000

# optional: use existing tool installations instead of auto-built bundled envs
tool_envs:
  mitoz:
    conda_env: 'my_mitoz_env'  # existing conda env name
    bin_dir: ''
  meangs:
    conda_env: ''
    bin_dir: '/opt/meangs/bin'  # directory containing tool binaries
```

**`options.yaml`** — Snakemake execution options:
```yaml
cluster: "qsub -V -cwd -S /bin/bash -e logs/sge/ -o logs/sge/"
cores: 4
```

**Global tool config** — `~/.config/FastMitoAssembler/tool_envs.yaml`: written by `fma check --save`, loaded automatically by every `fma run`. Project `config.yaml` tool_envs override global settings.

CLI flags override `options.yaml`; `configfile` values override CLI flags for biological parameters.
