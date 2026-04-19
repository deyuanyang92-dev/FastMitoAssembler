# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

`FastMitoAssembler` is a Python CLI tool that wraps a Snakemake workflow for fast, accurate assembly and annotation of mitochondrial genomes from paired-end Illumina reads. It chains four external tools in sequence: MEANGS → NOVOPlasty → GetOrganelle → MitoZ.

## Build & Install

```bash
# Build distribution packages
bash build.sh

# Install locally (editable for development)
pip install -e .

# Install from built wheel
pip install -U dist/FastMitoAssembler*.whl
```

## Environment Setup

```bash
# Create slim main environment (tool envs are auto-built on first run by Snakemake)
mamba create -n FastMitoAssembler -c conda-forge \
    python=3.9 "snakemake>=7" click jinja2 pyyaml ete3
conda activate FastMitoAssembler
pip install FastMitoAssembler
```

## CLI Commands

```bash
# Show help and paths to bundled Snakefile/config templates
FastMitoAssembler --help

# Prepare databases (run once before first use)
FastMitoAssembler prepare ncbitaxa
FastMitoAssembler prepare organelle -a animal_mt

# Run the workflow (--use-conda is on by default; tool envs built automatically on first run)
FastMitoAssembler run --configfile config.yaml --cores 8
FastMitoAssembler run --configfile config.yaml --dryrun  # preview without executing

# HPC: share tool envs across projects to avoid rebuilding
FastMitoAssembler run --configfile config.yaml --conda-prefix ~/.conda/snakemake-envs

# Upgrade a single tool: edit smk/envs/<tool>.yaml, re-run — Snakemake rebuilds only that env

# Run directly with snakemake (useful for advanced options)
snakemake -s /path/to/FastMitoAssembler/smk/main.smk -c config.yaml --cores 4 --use-conda
```

## Architecture

The entry point is `FastMitoAssembler/bin/main.py`, which registers two CLI command groups via Click:
- `run` (`bin/_run.py`): validates inputs, merges CLI args with configfile/optionfile, then calls `snakemake.snakemake()` directly
- `prepare` (`bin/_other.py`): sets up GetOrganelle databases and ete3.NCBITaxa

The Snakemake workflow lives entirely in `FastMitoAssembler/smk/main.smk`. It defines five rules executed in order:
1. **MEANGS** — detects the mitochondrial seed sequence from raw reads (or accepts a provided `.fasta`/`.gbk` as `seed_input`)
2. **NOVOPlasty_config** — renders a Jinja2 template (`config.py`) into a NOVOPlasty config file
3. **NOVOPlasty** — assembles the mitochondrial genome
4. **GetOrganelle** — re-assembles using the NOVOPlasty output as a seed; subsets input to 5G data if reads exceed that threshold
5. **MitozAnnotate** — annotates the assembled genome and produces `circos.png`, `summary.txt`, and a `.gbf` GenBank file

`FastMitoAssembler/__init__.py` exposes the bundled Snakefile path and loads defaults from `smk/config.yaml` and `smk/options.yaml` at import time.

## Configuration

Two YAML files control the workflow:

**`config.yaml`** — biological/sample parameters:
```yaml
reads_dir: '../data/'
samples: ['sample1']
fq_path_pattern: '{sample}/{sample}_1.clean.fq.gz'  # _2 derived by replacing '1' with '2'
organelle_database: 'animal_mt'
genetic_code: 5        # mitochondrial genetic code
clade: 'Annelida-segmented-worms'
genome_min_size: 12000
genome_max_size: 22000
```

**`options.yaml`** — Snakemake execution options (cores, cluster submission string, etc.):
```yaml
cluster: "qsub -V -cwd -S /bin/bash -e logs/sge/ -o logs/sge/"
cores: 4
```

CLI flags override `options.yaml`; `configfile` values override CLI flags for biological parameters.
