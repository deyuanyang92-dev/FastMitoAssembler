# FastMitoAssembler User Manual

**Version 0.0.2b0**

FastMitoAssembler is a Snakemake-based pipeline for assembling and annotating mitochondrial genomes from Illumina short-read sequencing data. It chains multiple assembly tools with automatic seed propagation and produces standardized output with a bilingual Materials and Methods report.

---

## 1. Overview

### What FastMitoAssembler Does

FastMitoAssembler takes paired-end Illumina reads as input and produces assembled, annotated mitochondrial genomes. It automates the entire workflow from raw reads through seed detection, assembly, annotation, and result summarization.

### Key Features

- **Multi-tool chaining**: Automatically propagates assembly results as seeds between MEANGS, NOVOPlasty, and GetOrganelle
- **Automatic seed detection**: MEANGS performs reference-free seed identification, eliminating the need for manual seed sequences
- **Flexible subcommand interface**: 8 stage commands allow running any subset of the pipeline
- **Isolated per-tool environments**: Each bioinformatics tool runs in its own conda environment, preventing dependency conflicts
- **Global + project configuration**: Set tool paths once globally, override per-project
- **Automatic sample detection**: Discovers samples from directory structure with configurable suffix patterns
- **Bilingual report**: Generates Materials and Methods text in both English and Chinese
- **Standardized output**: Consistent FASTA headers and summary TSV across all assemblers

### Supported Organisms

FastMitoAssembler supports mitochondrial genome assembly for:
- **Animals** (default): Annelida, Arthropoda, Chordata, Mollusca, Nematoda, and others
- **Fungi**: Fungal mitochondrial genomes
- **Plants**: Plant mitochondrial genomes (via GetOrganelle databases)

### Pipeline Architecture

```
MEANGS (seed detection)
    |
    +---> NOVOPlasty (assembly) ---+
    |                              |
    +---> GetOrganelle (assembly) -+---> MitoZ (annotation) ---> Summary
```

The full pipeline runs: MEANGS → GetOrganelle → NOVOPlasty → MitoZ annotation → Summary collection. Any subset can be run independently via subcommands.

---

## 2. Installation

### 2.1 Quick Install (conda + pip)

```bash
# Create and activate a conda environment
conda create -n fma python=3.12 -y
conda activate fma

# Install FastMitoAssembler
pip install FastMitoAssembler

# Verify
fma --version
fma --help
```

### 2.2 Install from Source

```bash
git clone https://github.com/your-repo/FastMitoAssembler.git
cd FastMitoAssembler
pip install -e .
```

### 2.3 Verify Installation

```bash
fma --version    # should print 0.0.2b0
fma --help       # lists all subcommands
```

FastMitoAssembler provides three entry points: `fma`, `FMA`, and `FastMitoAssembler`. They are identical.

### 2.4 Tool Environment Setup

FastMitoAssembler orchestrates four external tools, each requiring its own environment. Choose one of these setup methods:

**Method A: Interactive wizard (recommended for first-time users)**

```bash
fma setup
```

This walks you through configuring each tool interactively. For each tool you can choose: conda environment, bin directory, or script path.

**Method B: Automatic conda environment creation**

```bash
fma prepare tools
```

Creates four isolated conda environments (`FastMitoAssembler-meangs`, `FastMitoAssembler-novoplasty`, `FastMitoAssembler-getorganelle`, `FastMitoAssembler-mitoz`) and saves them to global config. Options:

```bash
# Recreate environments from scratch
fma prepare tools --force

# Install only specific tools
fma prepare tools --tool meangs --tool getorganelle

# Create envs but don't save to global config
fma prepare tools --no-save
```

**Method C: Manual per-tool configuration**

```bash
# Point to an existing conda environment
fma config set meangs --conda-env my-meangs-env

# Point to a directory containing the tool binary
fma config set novoplasty --bin-dir /usr/local/bioinfo/novoplasty

# Point to a specific script
fma config set meangs --script-path /path/to/meangs.py

# Skip validation (use with caution)
fma config set mitoz --conda-env my-mitoz --no-check
```

**Method D: Verify tools are accessible**

```bash
fma check                    # shows status of all tools
fma check --configfile config.yaml   # reads project tool_envs
fma check --save             # saves validated tools to global config
```

### 2.5 Database Preparation

**NCBI Taxonomy database (required by MitoZ):**

```bash
fma prepare ncbitaxa
# Or with a pre-downloaded taxdump:
fma prepare ncbitaxa --taxdump_file taxdump.tar.gz
```

**GetOrganelle organelle database:**

```bash
# Add the animal mitochondrial database
fma prepare organelle -a animal_mt

# Add all databases
fma prepare organelle -a all

# List currently configured databases
fma prepare organelle --list
```

Available databases: `embplant_pt`, `embplant_mt`, `embplant_nr`, `fungus_mt`, `fungus_nr`, `animal_mt`, `other_pt`.

### 2.6 Updating

```bash
pip install --upgrade FastMitoAssembler

# Then update tool environments if needed
fma prepare tools --force
```

---

## 3. Quick Start

This example uses the 3-sample Annelida dataset (POL1, POL10, POL11).

**Step 1: Initialize the project**

```bash
cd /path/to/project
fma init
```

This creates `config.yaml` in the current directory. Edit it to match your data:

**Step 2: Edit config.yaml**

```yaml
reads_dir: /path/to/reads        # directory containing sample subdirectories
samples: [POL1, POL10, POL11]    # sample names
result_dir: fma_result
organelle_database: animal_mt
genetic_code: 5
mitoz_clade: Annelida-segmented-worms
mitoz_thread_number: 16
meangs_thread: 16
meangs_reads: 500000
meangs_species_class: A-worms
```

**Step 3: Run the pipeline**

```bash
fma run --configfile config.yaml --cores 48 --no-use-conda
```

**Expected output:**

```
fma_result/
  POL1/
    1.MEANGS/          # seed detection results
    2.NOVOPlasty/      # NOVOPlasty assembly
    3.GetOrganelle/    # GetOrganelle assembly
    4.MitozAnnotate/   # MitoZ annotation
  POL10/
    ...
  POL11/
    ...
  summary/
    summary_all.fasta       # all assembled sequences
    summary_report.tsv      # tab-separated summary table
  Materials_and_Methods.txt # bilingual report
```

---

## 4. Configuration

### 4.1 fma init

```bash
# Create config.yaml with defaults
fma init

# Also create options.yaml for Snakemake options
fma init --options

# Custom output filename
fma init -o my_config.yaml

# Force overwrite existing config
fma init --force
```

### 4.2 config.yaml Reference

Every parameter with type, default, and description:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `reads_dir` | path | (required) | Root directory containing FASTQ files |
| `samples` | list | `[]` | Sample names; auto-detected if empty |
| `fq1` | path | | Direct single-sample R1 FASTQ path |
| `fq2` | path | | Direct single-sample R2 FASTQ path |
| `sample_name` | string | | Required when fq1/fq2 are set |
| `result_dir` | path | `result` | Output directory |
| `fq_path_pattern` | string | `{sample}/{sample}_1.clean.fq.gz` | R1 path pattern |
| `fq2_path_pattern` | string | | R2 path pattern (derived from fq_path_pattern if empty) |
| `fastq_pos` | string | `recursive` | FASTQ layout: `recursive`, `subdir`, or `flat` |
| `organelle_database` | string | `animal_mt` | GetOrganelle database type |
| `novoplasty_genome_min_size` | int | `12000` | NOVOPlasty minimum expected genome size (bp) |
| `novoplasty_genome_max_size` | int | `22000` | NOVOPlasty maximum expected genome size (bp) |
| `novoplasty_kmer_size` | int | `33` | NOVOPlasty K-mer size |
| `novoplasty_max_mem_gb` | int | `10` | NOVOPlasty RAM limit (GB) |
| `read_length` | int | `150` | Read length |
| `insert_size` | int | `300` | Insert size |
| `mitoz_clade` | string | `Annelida-segmented-worms` | MitoZ taxonomic clade |
| `genetic_code` | int | `5` | NCBI genetic code table |
| `mitoz_thread_number` | int | `20` | MitoZ threads |
| `meangs_thread` | int | `4` | MEANGS threads |
| `meangs_reads` | int | `2000000` | MEANGS reads to sample |
| `meangs_deepin` | bool | `true` | MEANGS deeper assembly mode |
| `meangs_quality` | float | `0.05` | MEANGS low-quality base threshold |
| `meangs_species_class` | string | `Arthropoda` | MEANGS species class (A-worms, Arthropoda, Chordata, etc.) |
| `meangs_clip` | bool | `false` | MEANGS clipping |
| `meangs_keepIntMED` | bool | `false` | MEANGS keep intermediate |
| `meangs_skipassem` | bool | `false` | MEANGS skip assembly |
| `meangs_skipqc` | bool | `false` | MEANGS skip QC |
| `meangs_skiphmm` | bool | `false` | MEANGS skip HMM |
| `meangs_skipextend` | bool | `false` | MEANGS skip extension |
| `meangs_path` | path | | Direct path to meangs.py |
| `cleanup` | bool | `false` | Remove intermediate files after each step |
| `getorganelle_threads` | int | `4` | GetOrganelle threads |
| `getorganelle_rounds` | int | | GetOrganelle extension rounds (blank = auto) |
| `getorganelle_kmers` | string | | GetOrganelle K-mer sizes (blank = auto) |
| `getorganelle_max_reads` | int | | GetOrganelle max reads (blank = auto) |
| `getorganelle_reduce_reads_for_coverage` | int | | Coverage reduction (blank = auto) |
| `getorganelle_word_size` | int | | GetOrganelle word size (blank = auto) |
| `getorganelle_max_extending_len` | int | | Max extension length (blank = auto) |
| `getorganelle_all_data` | bool | `false` | Use all reads (sets max-reads and coverage to inf) |
| `subsample_gb` | float | `5` | Subsample reads to N GB before GetOrganelle (0 = all) |
| `fastp.enabled` | bool | `false` | Enable fastp adapter trimming |
| `fastp.mode` | string | `adapter_only` | fastp trimming mode |
| `fastp.extra_args` | string | | Additional fastp arguments |
| `seed_input` | path | | User-provided seed FASTA or GenBank file |
| `seed_mode` | string | `single` | Seed mode: `single` or `by-sample` |
| `seed_missing` | string | `fail` | Missing seed behavior: `fail` or `skip` |
| `genes` | string | | Specific genes for GetOrganelle |
| `assembly_fasta` | path | | External assembly for MitoZ annotation |
| `novoplasty_seed_source` | string | `auto` | NOVOPlasty seed: `auto`, `user`, `meangs` |
| `getorganelle_seed_source` | string | `auto` | GetOrganelle seed: `auto`, `none`, `user`, `meangs`, `novoplasty` |
| `mitoz_input_source` | string | `auto` | MitoZ input: `auto`, `assembly_fasta`, `summary`, `getorganelle`, `novoplasty` |
| `summary_dir` | path | | Custom summary directory |
| `tool_envs` | dict | | Per-tool environment configuration |

### 4.3 CLI Parameters

FastMitoAssembler provides 39 CLI parameters via the `common_workflow_options` decorator. These override config.yaml values:

| CLI Flag | Config Key | Type | Default |
|----------|-----------|------|---------|
| `-r, --reads_dir` | reads_dir | path | |
| `-o, --result_dir` | result_dir | path | `result` |
| `-d, --organelle_database` | organelle_database | string | `animal_mt` |
| `-s, --samples` | samples | list | |
| `--fq1` | fq1 | path | |
| `--fq2` | fq2 | path | |
| `--sample_name` | sample_name | string | |
| `--fq_path_pattern` | fq_path_pattern | string | `{sample}/{sample}_1.clean.fq.gz` |
| `--fq2_path_pattern` | fq2_path_pattern | string | |
| `--meangs_path` | meangs_path | path | |
| `--genetic_code` | genetic_code | int | `5` |
| `--novoplasty_genome_min_size` | novoplasty_genome_min_size | int | `12000` |
| `--novoplasty_genome_max_size` | novoplasty_genome_max_size | int | `22000` |
| `--insert_size` | insert_size | int | `300` |
| `--novoplasty_kmer_size` | novoplasty_kmer_size | int | `33` |
| `--read_length` | read_length | int | `150` |
| `--novoplasty_max_mem_gb` | novoplasty_max_mem_gb | int | `10` |
| `--suffix_fq` | | string | `_1.clean.fq.gz,_2.clean.fq.gz` |
| `--fastq_pos` | fastq_pos | choice | `recursive` |
| `--seed_input` | seed_input | path | |
| `--seed_mode` | seed_mode | choice | `single` |
| `--seed_missing` | seed_missing | choice | `fail` |
| `--genes` | genes | string | |
| `--assembly_fasta` | assembly_fasta | path | |
| `--mitoz_input_source` | mitoz_input_source | choice | `auto` |
| `--getorganelle_seed_source` | getorganelle_seed_source | choice | `auto` |
| `--novoplasty_seed_source` | novoplasty_seed_source | choice | `auto` |
| `--snakefile` | | path | bundled |
| `--configfile` | | path | |
| `--optionfile` | | path | |
| `--cores` | | int | `4` |
| `--dryrun` | | flag | `false` |
| `--use-conda/--no-use-conda` | | flag | `true` |
| `--conda-prefix` | | path | |
| `--keepgoing` | | flag | `false` |
| `--unlock` | | flag | `false` |

### 4.4 Sample Detection Modes

When `samples` is not set in config.yaml, FastMitoAssembler auto-detects samples from the directory structure using `--suffix_fq` and `--fastq_pos`.

**Recursive mode** (default) -- searches all subdirectories:

```bash
fma run -r /data/reads --suffix_fq "_1.clean.fq.gz,_2.clean.fq.gz" --fastq_pos recursive
```

Directory layout:
```
reads/
  POL1/
    POL1_1.clean.fq.gz
    POL1_2.clean.fq.gz
  POL10/
    POL10_1.clean.fq.gz
    POL10_2.clean.fq.gz
```

**Subdir mode** -- only one level of subdirectories, sample name = directory name:

```bash
fma run -r /data/reads --suffix_fq "_1.fq.gz,_2.fq.gz" --fastq_pos subdir
```

**Flat mode** -- all files in the root directory, sample name from filename:

```bash
fma run -r /data/reads --suffix_fq ".R1.fastq.gz,.R2.fastq.gz" --fastq_pos flat
```

**Multiple suffix patterns** -- separate with semicolons:

```bash
fma run -r /data/reads --suffix_fq "_1.fq.gz,_2.fq.gz;.R1.fq.gz,.R2.fq.gz"
```

### 4.5 Direct Single-Sample Mode

For analyzing a single sample without creating a config.yaml:

```bash
fma run --fq1 /data/sample1_R1.fq.gz --fq2 /data/sample1_R2.fq.gz --sample_name SAMPLE1
```

All three flags (`--fq1`, `--fq2`, `--sample_name`) must be provided together.

---

## 5. Pipeline Modes

### 5.1 fma run -- Full Pipeline

Runs the complete pipeline: MEANGS → GetOrganelle → NOVOPlasty → MitoZ → Summary.

```bash
fma run --configfile config.yaml --cores 48 --no-use-conda
```

### 5.2 fma meangs -- Seed Detection Only

Runs MEANGS to detect mitochondrial seed sequences from reads.

```bash
fma meangs --configfile config.yaml --cores 16 --no-use-conda
```

### 5.3 fma novoplasty -- NOVOPlasty Assembly

Runs NOVOPlasty assembly. Requires a seed (`--seed_input` or `--novoplasty_seed_source`).

```bash
# With a user-provided seed
fma novoplasty --configfile config.yaml --seed_input /path/to/seed.fasta --cores 16 --no-use-conda

# Without explicit seed (uses built-in auto mode)
fma novoplasty --configfile config.yaml --cores 16 --no-use-conda
```

### 5.4 fma getorganelle -- GetOrganelle Assembly

Runs GetOrganelle assembly.

```bash
fma getorganelle --configfile config.yaml --cores 16 --no-use-conda
```

### 5.5 fma mitoz -- MitoZ Annotation

Runs MitoZ annotation on previously assembled sequences.

```bash
# Annotate GetOrganelle output using MEANGS as seed source
fma mitoz --configfile config.yaml \
  --mitoz_input_source getorganelle \
  --getorganelle_seed_source meangs \
  --cores 16 --no-use-conda
```

### 5.6 fma mg-nov -- MEANGS → NOVOPlasty

Runs MEANGS seed detection followed by NOVOPlasty assembly using the MEANGS result as seed.

```bash
fma mg-nov --configfile config.yaml --cores 32 --no-use-conda
```

### 5.7 fma mg-get -- MEANGS → GetOrganelle

Runs MEANGS seed detection followed by GetOrganelle assembly using the MEANGS result as seed.

```bash
fma mg-get --configfile config.yaml --cores 32 --no-use-conda
```

### 5.8 fma mg-nov-get -- MEANGS → NOVOPlasty → GetOrganelle

Chains all three assemblers: MEANGS detects the seed, NOVOPlasty performs initial assembly, and GetOrganelle refines the result.

```bash
fma mg-nov-get --configfile config.yaml --cores 48 --no-use-conda
```

### 5.9 fma summary -- Collect Results

Collects all assembly and annotation results into standardized summary files.

```bash
fma summary --configfile config.yaml --cores 4 --no-use-conda
```

Output files:
- `summary/summary_all.fasta` -- all assembled sequences with standardized headers
- `summary/summary_report.tsv` -- tab-separated table with sample, software, length, GC%, topology, etc.

---

## 6. Seed Management

### 6.1 Auto Seed via MEANGS (Default)

When no seed is provided, MEANGS performs reference-free mitochondrial sequence detection from reads. This is the recommended approach.

```bash
# MEANGS runs automatically as part of the pipeline
fma run --configfile config.yaml --cores 48 --no-use-conda
```

### 6.2 User-Providvided Seed

Provide a seed FASTA or GenBank file:

```bash
# FASTA seed (single mode uses first record)
fma novoplasty --configfile config.yaml --seed_input /data/seed.fasta

# GenBank file (ORIGIN section is extracted automatically)
fma getorganelle --configfile config.yaml --seed_input /data/reference.gb
```

Gzipped files (`.fasta.gz`, `.gb.gz`) are supported.

### 6.3 Seed Modes

**Single mode** (default): Uses the first record from the seed file for all samples.

```bash
fma run --seed_input seed.fasta --seed_mode single
```

**By-sample mode**: Matches record names to sample names. Each sample gets its own seed.

```bash
fma run --seed_input multi_seed.fasta --seed_mode by-sample
```

The multi-record FASTA should have record names matching your samples:
```
>POL1
ATCGATCG...
>POL10
GCTAGCTA...
```

### 6.4 Seed Missing Behavior

When a seed is required but not found:

**Fail mode** (default): Stops with an error.

```bash
fma run --seed_input seed.fasta --seed_mode by-sample --seed_missing fail
```

**Skip mode**: Creates an empty placeholder and continues with remaining samples.

```bash
fma run --seed_input seed.fasta --seed_mode by-sample --seed_missing skip
```

---

## 7. Tool Environment Management

### 7.1 How tool_envs Work

FastMitoAssembler uses a two-layer environment architecture:

1. **Orchestrator environment**: The conda environment where FastMitoAssembler itself is installed
2. **Per-tool environments**: Each bioinformatics tool (MEANGS, NOVOPlasty, GetOrganelle, MitoZ) runs in its own isolated environment

This isolation means upgrading one tool never breaks the others. Tool environments are configured at two levels:
- **Global**: `~/.config/FastMitoAssembler/tool_envs.yaml` (applies to all projects)
- **Project**: `tool_envs` section in `config.yaml` (overrides global for this project)

### 7.2 fma setup -- Interactive Wizard

```bash
fma setup
```

Walks through each of the 4 tools (meangs, novoplasty, getorganelle, mitoz). For each tool, choose:
- Conda environment name
- Binary directory
- Script path
- Skip

### 7.3 fma prepare tools -- Automatic

```bash
# Create all tool environments
fma prepare tools

# Force recreate
fma prepare tools --force

# Specific tools only
fma prepare tools --tool meangs --tool mitoz
```

### 7.4 fma config set/show/reset -- Manual

```bash
# Set a tool's conda environment
fma config set meangs --conda-env my-meangs-env

# Set binary directory
fma config set novoplasty --bin-dir /opt/novoplasty

# Set script path
fma config set meangs --script-path /home/user/tools/meangs.py

# Show current configuration
fma config show

# Reset a specific tool
fma config reset meangs

# Reset all tools
fma config reset all
```

### 7.5 Using Custom Conda Environments

If you already have conda environments with the tools installed:

```yaml
# In config.yaml
tool_envs:
  meangs:
    conda_env: my-meangs
  novoplasty:
    conda_env: my-novoplasty
  getorganelle:
    conda_env: my-getorganelle
  mitoz:
    conda_env: my-mitoz
```

### 7.6 Using System-Installed Tools

If tools are installed system-wide or via modules:

```bash
fma config set meangs --bin-dir /usr/local/bioinfo/meangs/bin
```

### 7.7 Using Script Paths

For tools invoked via interpreter (MEANGS uses Python, NOVOPlasty uses Perl):

```bash
fma config set meangs --script-path /path/to/meangs.py
fma config set novoplasty --script-path /path/to/NOVOPlasty.pl

# Or via CLI flag (meangs only):
fma run --meangs-path /path/to/meangs.py
```

---

## 8. Advanced Usage

### 8.1 Customizing GetOrganelle Parameters

```yaml
# In config.yaml
getorganelle_threads: 16
getorganelle_rounds: 15
getorganelle_kmers: "21,45,65,85,105"
getorganelle_max_reads: 50000000
getorganelle_all_data: true
```

Most GetOrganelle parameters default to blank, which lets GetOrganelle choose appropriate values based on the organelle type (`-F` flag). Only set these if you need to override the defaults.

### 8.2 Customizing NOVOPlasty Parameters

```yaml
novoplasty_genome_min_size: 15000
novoplasty_genome_max_size: 25000
novoplasty_kmer_size: 39
novoplasty_max_mem_gb: 100
read_length: 150
insert_size: 268
```

### 8.3 Customizing MEANGS Parameters

```yaml
meangs_thread: 16
meangs_reads: 500000      # reduce for faster speed
meangs_deepin: true       # deeper assembly (slower but better)
meangs_quality: 0.05
meangs_species_class: A-worms
```

Available MEANGS species classes: `A-worms`, `Arthropoda`, `Bryozoa`, `Chordata`, `Echinodermata`, `Mollusca`, `Nematoda`, `N-worms`, `Porifera-sponges`.

### 8.4 Customizing MitoZ Annotation

```yaml
genetic_code: 5           # NCBI genetic code table
mitoz_clade: Annelida-segmented-worms
mitoz_thread_number: 16
```

Common genetic codes: 2 (vertebrate mitochondria), 5 (invertebrate mitochondria), 14 (flatworm mitochondria).

### 8.5 MitoZ Input Source Selection

Control which assembly MitoZ annotates:

```bash
# Auto-select (default): tries getorganelle → novoplasty → meangs
--mitoz_input_source auto

# Use a specific assembler's output
--mitoz_input_source getorganelle
--mitoz_input_source novoplasty

# Use an external FASTA file
--mitoz_input_source assembly_fasta --assembly_fasta /path/to/assembly.fasta

# Use the best result from the summary
--mitoz_input_source summary
```

### 8.6 GetOrganelle Seed Source Selection

```bash
# No seed (GetOrganelle's own database discovery)
--getorganelle_seed_source none

# User-provided seed
--getorganelle_seed_source user

# Use MEANGS output as seed
--getorganelle_seed_source meangs

# Use NOVOPlasty output as seed
--getorganelle_seed_source novoplasty
```

### 8.7 NOVOPlasty Seed Source Selection

```bash
# User-provided seed (via --seed_input)
--novoplasty_seed_source user

# Use MEANGS output as seed
--novoplasty_seed_source meangs
```

### 8.8 External Assembly FASTA for Annotation

If you have an assembly from another tool and want to annotate it with MitoZ:

```bash
fma mitoz --configfile config.yaml \
  --assembly_fasta /path/to/my_assembly.fasta \
  --mitoz_input_source assembly_fasta
```

### 8.9 Resource Control

```bash
# Use 48 cores
fma run --configfile config.yaml --cores 48 --no-use-conda

# Dry run (show what would be done)
fma run --configfile config.yaml --dryrun

# Continue past failed jobs
fma run --configfile config.yaml --keepgoing
```

### 8.10 Cleanup Intermediate Files

```yaml
# In config.yaml
cleanup: true
```

When enabled, intermediate files (sorted temp files, MitoZ input FASTA) are removed after each step completes.

### 8.11 Subsample Reads Before GetOrganelle

```yaml
# Subsample to 5 GB of reads (default)
subsample_gb: 5

# Use all reads
subsample_gb: 0
```

### 8.12 Optional fastp Adapter Trimming

By default, FastMitoAssembler expects adapter-trimmed reads. If your reads still have adapters:

```yaml
fastp:
  enabled: true
  mode: adapter_only
  extra_args: ''    # e.g. '-G' to disable polyG trimming on NovaSeq
```

---

## 9. Output Description

### 9.1 Directory Structure

```
result_dir/
  {sample}/
    1.MEANGS/
      animal_mt.meangs.fasta         # MEANGS assembled sequences
    2.NOVOPlasty/
      {sample}_mito.fasta            # NOVOPlasty assembled sequences
    3.GetOrganelle/
      animal_mt.get_organelle.fasta  # GetOrganelle assembled sequences
    4.MitozAnnotate/
      {sample}.{sample}.mitoz_input.fasta.result/
        summary.txt                  # MitoZ annotation summary
        cds/                         # coding sequences
        genes/                       # gene annotations
        rrna/                        # rRNA annotations
        trna/                        # tRNA annotations
  summary/
    POL1.meangs.fasta               # per-sample per-tool summary FASTA
    POL1.novoplasty.fasta
    POL1.getorganelle.fasta
    POL1.mg-nov.fasta
    POL1.mg-get.fasta
    POL1.mg-nov-get.fasta
    summary_all.fasta               # combined FASTA
    summary_report.tsv              # summary table
  Materials_and_Methods.txt         # bilingual report
  logs/
    {sample}/
      meangs.log
      novoplasty.log
      getorganelle.log
      mitoz_annotate.log
      mitoz_annotate.log.err
  benchmarks/
    {sample}/
      meangs.stat
      novoplasty.stat
      getorganelle.stat
      mitoz_annotate.stat
```

### 9.2 Summary Files

**summary_report.tsv** -- Tab-separated table with columns:
- `sample`: Sample name
- `software`: Assembly tool used
- `pipeline`: Pipeline mode (meangs, novoplasty, getorganelle, mg-nov, mg-get, mg-nov-get)
- `locus`: Genome locus (mt, nr, unknown)
- `source_file`: Path to source FASTA
- `record_id`: Full FASTA header
- `length`: Sequence length (bp)
- `gc_percent`: GC content percentage
- `n_count`: Number of N bases
- `topology`: circular, linear, or unknown
- `status`: ok or empty
- `output_fasta`: Path to summary FASTA
- `notes`: Additional notes

**summary_all.fasta** -- Combined FASTA with standardized headers:
```
>POL1|software=getorganelle|pipeline=mg-get|locus=mt|idx=1|topology=linear|length=16117
ATCGATCGATCG...
```

### 9.3 Per-Tool Outputs

| Tool | Output | Description |
|------|--------|-------------|
| MEANGS | `animal_mt.meangs.fasta` | Assembled mitochondrial sequences |
| NOVOPlasty | `{sample}_mito.fasta` | Assembled circular/linear genome |
| GetOrganelle | `animal_mt.get_organelle.fasta` | Assembled genome (may be multi-record for linear) |
| MitoZ | `summary.txt` | Gene annotation summary |

### 9.4 Materials and Methods Report

The report is generated in both English and Chinese, including:
- Pipeline version and tool versions
- Parameters used
- Assembly method description
- Citation list for all tools

---

## 10. Troubleshooting

### Common Errors and Solutions

**Error: "samples must supply"**
- Solution: Provide `samples` in config.yaml, or use `--samples` on CLI, or use `--fq1 --fq2 --sample_name` for single samples

**Error: "reads file not exists"**
- Solution: Check that FASTQ files exist at the expected paths. Verify `reads_dir` and `fq_path_pattern` in config.yaml

**Error: "seed_input is required"**
- Solution: Provide `--seed_input` or run `fma meangs` first to generate a seed

**Error: "conda env configured but tool not found"**
- Solution: Run `fma check` to diagnose. Fix with `fma config set <tool> --conda-env <correct-env>`

**MitoZ annotation fails with "sorted.tmp" error**
- This was a known issue with seqkit on multi-record FASTA. Fixed in v0.0.2 (uses pure awk instead of seqkit)

**Snakemake error: "Directory locked"**
- Solution: `fma run --configfile config.yaml --unlock`

### Resuming Interrupted Runs

Snakemake tracks completed steps. Simply re-run the same command:

```bash
fma run --configfile config.yaml --cores 48 --no-use-conda
```

Snakemake will skip already-completed steps and resume from where it stopped.

### Dry Run

To preview what would be executed without actually running:

```bash
fma run --configfile config.yaml --dryrun
```

---

## 11. Parameter Reference

### Complete Parameter Table

| Parameter | CLI Flag | Type | Default | Description |
|-----------|----------|------|---------|-------------|
| reads_dir | `-r, --reads_dir` | path | | Root directory of FASTQ files |
| result_dir | `-o, --result_dir` | path | `result` | Output directory |
| organelle_database | `-d, --organelle_database` | string | `animal_mt` | GetOrganelle database |
| samples | `-s, --samples` | list | `[]` | Sample names |
| fq1 | `--fq1` | path | | Single-sample R1 FASTQ |
| fq2 | `--fq2` | path | | Single-sample R2 FASTQ |
| sample_name | `--sample_name` | string | | Sample name for direct mode |
| fq_path_pattern | `--fq_path_pattern` | string | `{sample}/{sample}_1.clean.fq.gz` | R1 path pattern |
| fq2_path_pattern | `--fq2_path_pattern` | string | | R2 path pattern |
| meangs_path | `--meangs_path` | path | | Path to meangs.py |
| genetic_code | `--genetic_code` | int | `5` | NCBI genetic code |
| novoplasty_genome_min_size | `--novoplasty_genome_min_size` | int | `12000` | Min genome size (bp) |
| novoplasty_genome_max_size | `--novoplasty_genome_max_size` | int | `22000` | Max genome size (bp) |
| insert_size | `--insert_size` | int | `300` | Insert size |
| novoplasty_kmer_size | `--novoplasty_kmer_size` | int | `33` | K-mer size |
| read_length | `--read_length` | int | `150` | Read length |
| novoplasty_max_mem_gb | `--novoplasty_max_mem_gb` | int | `10` | RAM limit (GB) |
| suffix_fq | `--suffix_fq` | string | `_1.clean.fq.gz,_2.clean.fq.gz` | FASTQ suffix pattern |
| fastq_pos | `--fastq_pos` | choice | `recursive` | FASTQ layout mode |
| seed_input | `--seed_input` | path | | Seed FASTA/GenBank file |
| seed_mode | `--seed_mode` | choice | `single` | Seed mode |
| seed_missing | `--seed_missing` | choice | `fail` | Missing seed behavior |
| genes | `--genes` | string | | Target genes |
| assembly_fasta | `--assembly_fasta` | path | | External assembly FASTA |
| mitoz_input_source | `--mitoz_input_source` | choice | `auto` | MitoZ input source |
| getorganelle_seed_source | `--getorganelle_seed_source` | choice | `auto` | GetOrganelle seed source |
| novoplasty_seed_source | `--novoplasty_seed_source` | choice | `auto` | NOVOPlasty seed source |
| snakefile | `--snakefile` | path | bundled | Custom Snakefile |
| configfile | `--configfile` | path | | Config YAML file |
| optionfile | `--optionfile` | path | | Snakemake options YAML |
| cores | `--cores` | int | `4` | CPU cores |
| dryrun | `--dryrun` | flag | | Preview without executing |
| use_conda | `--use-conda/--no-use-conda` | flag | `true` | Use conda per rule |
| conda_prefix | `--conda-prefix` | path | | Shared conda env directory |
| keepgoing | `--keepgoing` | flag | | Continue past failures |
| unlock | `--unlock` | flag | | Unlock working directory |

### Config-Only Parameters

These parameters are available in config.yaml but not as CLI flags:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| mitoz_clade | string | `Annelida-segmented-worms` | MitoZ taxonomic clade |
| mitoz_thread_number | int | `20` | MitoZ threads |
| meangs_thread | int | `4` | MEANGS threads |
| meangs_reads | int | `2000000` | MEANGS reads to sample |
| meangs_deepin | bool | `true` | MEANGS deep assembly |
| meangs_quality | float | `0.05` | MEANGS quality threshold |
| meangs_species_class | string | `Arthropoda` | MEANGS species class |
| cleanup | bool | `false` | Remove intermediate files |
| subsample_gb | float | `5` | Subsample reads (GB) |
| getorganelle_threads | int | `4` | GetOrganelle threads |
| getorganelle_rounds | int | | Extension rounds |
| getorganelle_kmers | string | | K-mer sizes |
| getorganelle_max_reads | int | | Max reads |
| getorganelle_reduce_reads_for_coverage | int | | Coverage cap |
| getorganelle_word_size | int | | Word size |
| getorganelle_max_extending_len | int | | Max extension length |
| getorganelle_all_data | bool | `false` | Use all reads |
| summary_dir | path | | Custom summary directory |
| tool_envs | dict | | Per-tool environment config |

---

## 12. FAQ

**Q: What organisms does FastMitoAssembler support?**
A: It supports mitochondrial genome assembly for animals, fungi, and plants. The default configuration targets animal mitochondria. Change `organelle_database` for other taxa.

**Q: Do I need to provide a seed sequence?**
A: No. MEANGS performs reference-free seed detection automatically. You only need a seed if running NOVOPlasty or GetOrganelle standalone without MEANGS.

**Q: Can I use my own conda environments?**
A: Yes. Use `fma config set <tool> --conda-env <env_name>` to point FastMitoAssembler to your existing environments.

**Q: How do I resume a failed run?**
A: Simply re-run the same command. Snakemake skips completed steps automatically.

**Q: What if a sample has no mitochondrial signal?**
A: MEANGS may produce no output. Use `--seed_missing skip` to skip such samples rather than failing.

**Q: Can I run just the annotation step?**
A: Yes. Use `fma mitoz --configfile config.yaml --mitoz_input_source getorganelle` to annotate existing GetOrganelle output.

**Q: How much RAM do I need?**
A: Typical runs need 8-32 GB depending on read depth. Set `novoplasty_max_mem_gb` to limit NOVOPlasty memory usage.

**Q: Can I analyze a single sample without a config file?**
A: Yes. Use `fma run --fq1 R1.fq.gz --fq2 R2.fq.gz --sample_name SAMPLE1`.

**Q: What genetic code should I use?**
A: For invertebrate mitochondria use code 5 (default). For vertebrate mitochondria use code 2. See NCBI's genetic code tables for others.

**Q: How do I get the assembled sequences?**
A: After running, check `summary/summary_all.fasta` for all assembled sequences, or look in per-sample directories for per-tool output.

**Q: Can I use long reads (PacBio/Nanopore)?**
A: No. FastMitoAssembler currently only supports Illumina paired-end short reads.

**Q: Where are logs stored?**
A: In `{result_dir}/logs/{sample}/` with separate log files for each tool.

**Q: How do I report bugs?**
A: Open an issue on the GitHub repository with the log file and config.yaml.
