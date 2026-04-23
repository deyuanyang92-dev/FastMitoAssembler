# FastMitoAssembler v002 beta installation

Version: `0.0.2b0`

Git tag: `v002-beta`

Date: 2026-04-23

This guide installs the v002 beta from GitHub for testing. Use a fresh conda
environment so the beta does not disturb an existing production installation.

## 1. Create the main environment

```bash
mamba create -n FastMitoAssembler-v002 -c conda-forge -c bioconda \
    python=3.9 "snakemake>=7" click jinja2 pyyaml ete3

conda activate FastMitoAssembler-v002
```

If `mamba` is not available, replace `mamba create` with `conda create`.

## 2. Install the v002 beta CLI

Install the exact beta tag:

```bash
pip install -U \
    git+https://github.com/deyuanyang92-dev/FastMitoAssembler.git@v002-beta
```

For SSH-based GitHub access:

```bash
pip install -U \
    git+ssh://git@github.com/deyuanyang92-dev/FastMitoAssembler.git@v002-beta
```

Verify:

```bash
fma --version
fma --help
```

Expected version:

```text
FastMitoAssembler version 0.0.2b0
```

## 3. Install external tool environments

FastMitoAssembler is the workflow runner. MEANGS, NOVOPlasty, GetOrganelle,
MitoZ, and optional fastp run through isolated tool environments.

```bash
fma setup
fma prepare tools
```

If the tools already exist on your system, configure or auto-detect them:

```bash
fma check --save
fma config show
```

Manual examples:

```bash
fma config set meangs       --conda-env FastMitoAssembler-meangs
fma config set novoplasty   --conda-env FastMitoAssembler-novoplasty
fma config set getorganelle --conda-env FastMitoAssembler-getorganelle
fma config set mitoz        --conda-env FastMitoAssembler-mitoz
```

## 4. Prepare databases

```bash
fma prepare ncbitaxa
fma prepare organelle -a animal_mt
```

Use the organelle database that matches the samples:

```bash
fma prepare organelle -a embplant_mt
fma prepare organelle -a embplant_pt
fma prepare organelle -a all
```

## 5. Initialize a test project

```bash
mkdir fastmito-v002-test
cd fastmito-v002-test

fma init --options
```

Edit `config.yaml` for the test data. A minimal paired-end batch usually needs:

```yaml
reads_dir: '../data'
samples:
  - sample1
fq_path_pattern: '{sample}/{sample}_1.clean.fq.gz'
fq2_path_pattern: '{sample}/{sample}_2.clean.fq.gz'
result_dir: 'result'
organelle_database: 'animal_mt'
genetic_code: 5
```

For NOVOPlasty seed testing:

```yaml
seed_input: '../seeds/seed.fasta'
seed_mode: single
seed_missing: fail
```

For multi-sample seed testing, the first token after each FASTA header must
match the sample name:

```yaml
seed_input: '../seeds/by_sample_seeds.fasta'
seed_mode: by-sample
seed_missing: fail
```

## 6. Dry-run first

The v002 beta exposes independent tool stages and chain stages. Start with
Snakemake dry-runs:

```bash
fma meangs --configfile config.yaml --dryrun
fma novoplasty --configfile config.yaml --dryrun
fma getorganelle --configfile config.yaml --dryrun
fma mg-nov --configfile config.yaml --dryrun
fma mg-get --configfile config.yaml --dryrun
fma mg-nov-get --configfile config.yaml --dryrun
fma run --configfile config.yaml --dryrun
```

When the dry-run DAG is correct:

```bash
fma mg-nov-get --configfile config.yaml --cores 8
```

## 7. Summary outputs

The v002 summary layer is designed to collect per-tool and per-chain FASTA
outputs under:

```text
result/summary/
```

Expected beta targets include:

```text
{sample}.meangs.fasta
{sample}.novoplasty.fasta
{sample}.getorganelle.fasta
{sample}.mg-nov.fasta
{sample}.mg-get.fasta
{sample}.mg-nov-get.fasta
summary_all.fasta
summary_report.tsv
```

## 8. Flowchart and design notes

- SVG flowchart: `docs/design/fastmito-v002-flowchart.svg`
- Mermaid source: `docs/design/fastmito-v002-flowchart.md`
- v002 design: `docs/design/fastmito-v002.md`
- Software research notes: `docs/software/`

## 9. Update or reinstall the beta

```bash
conda activate FastMitoAssembler-v002
pip install --force-reinstall --no-deps \
    git+https://github.com/deyuanyang92-dev/FastMitoAssembler.git@v002-beta
```

If testing the latest branch after the beta tag:

```bash
pip install -U \
    git+https://github.com/deyuanyang92-dev/FastMitoAssembler.git@master
```

## Beta status

This release is intended for testing the v002 CLI, Snakemake target dispatch,
seed handling, summary collection, and documentation. Full validation with real
external tool runs and databases should still be completed before production
use.
