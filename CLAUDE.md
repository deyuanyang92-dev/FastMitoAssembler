# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

`FastMitoAssembler` (aliases: `fma`, `FMA`) is a Python CLI tool that wraps a Snakemake workflow for fast, accurate assembly and annotation of mitochondrial genomes from paired-end Illumina reads. It chains four external tools in sequence: MEANGS → NOVOPlasty → GetOrganelle → MitoZ.

## Response Rules

The user is a researcher and bioinformatics expert. Every factual claim — about tool behavior, author recommendations, best practices, or scientific consensus — MUST trace to a verifiable source. The rule is about **sourcing**, not about *how* the information was recalled.

### What counts as a verifiable source

1. **Source code** — cite `file:line` (e.g., `meangs.py:199`)
2. **Tool `--help` / `--version` output** — run and quote the relevant lines
3. **Official docs / GitHub README / FAQ** — URL + direct quote
4. **Published papers** — DOI + the specific claim
5. **Upstream issues / PRs** — GitHub URL + quote
6. **Memory / CLAUDE.md entries that themselves cite one of the above** — valid, because the citation is what makes the claim trustworthy. Example: the "MEANGS output files" section in this file cites `meangs.py:199` — reusing that claim is fine; no need to re-verify every time.

### What is NOT acceptable

- Unsourced claims of any origin: "I remember X", "it's commonly known that X", "best practice says X" — without a concrete source, these do not belong in a response.
- Memory entries that are just summaries with no underlying citation.
- Confident-sounding generalizations filled in where a source lookup would have been easy.

### When a cited memory may be stale

Memories freeze at write-time. Tool versions, APIs, and file layouts drift. Before acting on a cited memory (especially one that names a file path, function, or flag), if the stakes are high (workflow behavior, destructive actions, user-facing decisions), re-read the source to confirm it still says what the memory claims. If the source has moved on, update the memory rather than argue from the stale version.

### When evidence is unavailable

- Say explicitly: "I don't have a verifiable source for this — please verify before acting."
- Do NOT fill gaps with plausible-sounding claims.
- Offer to fetch the source (WebFetch / source code / `--help`) if the user wants the gap closed.

### Fairness

- Present technical tradeoffs without bias toward any single approach.
- Before critiquing a design decision, first look for the author's stated rationale (README, paper, issue threads). Assume the design has a reason until proven otherwise.
- Distinguish "I disagree with this choice" (opinion) from "this choice is objectively wrong" (requires source-backed evidence). Label opinions as opinions.

### Recorded failure modes (specific past mistakes in this project)

- **Suggesting `fastp` / quality trimming** for NOVOPlasty or GetOrganelle input without checking author guidance. NOVOPlasty README and GetOrganelle FAQ both advise against Phred-based quality trimming (SPAdes' BayesHammer inside GetOrganelle does its own error correction; NOVOPlasty's seed-and-extend is sensitive to read-end truncation). **Adapter removal is a separate operation and IS expected** — the project's `.clean.fq.gz` filename convention implies adapter-removed-but-not-quality-trimmed reads.
- **Critiquing the NOVOPlasty → GetOrganelle serial chain as redundant** without looking up the design rationale. Documented reasons: (1) NOVOPlasty output as seed accelerates GetOrganelle extending rounds; (2) NOVOPlasty has no assembly-graph output — GetOrganelle provides `.fastg` for Bandage visualization, enabling reviewer-verifiable circularity and repeat-resolution inspection.
- **Answering MEANGS output-file questions from uncited memory.** Cited memory (with `meangs.py:199` reference) is fine to reuse; unsourced recall is not. This has been corrected ≥10 times.

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
genetic_code: 5                              # MitoZ: NCBI genetic code table

# NOVOPlasty parameters
novoplasty_genome_min_size: 12000
novoplasty_genome_max_size: 22000
novoplasty_kmer_size: 33
novoplasty_max_mem_gb: 10

# MitoZ parameters
mitoz_clade: 'Annelida-segmented-worms'      # must match MitoZ --clade enum
mitoz_thread_number: 20

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

## Tool-specific notes

### MEANGS output files (deepin vs non-deepin)

**Source of truth:** upstream `meangs.py` (v1.3.1, git HEAD `43e8154` as of 2026-04-20). Verified locally at `/mnt/d/Claude/other_softs/meangs/meangs.py`. Older bioconda builds pin v1.0 and differ — see "Version differences" below.

#### Invocation shape

`meangs.py -1 R1.fq.gz -2 R2.fq.gz -o {prefix} [--deepin] [--clip]` run from CWD creates `CWD/{prefix}/` and writes all outputs with nested prefix `{prefix}/{prefix}_*`.

#### Files written inside `{prefix}/` (both modes)

| File | Notes |
|---|---|
| `{prefix}_1.input.fas`, `{prefix}_2.input.fas` | QC'd reads (deleted unless `--keepIntMed`) |
| `{prefix}_1_hmmout`, `{prefix}_1_hmmout_tbl` (and `_2`) | nhmmer scan of reads |
| `{prefix}_MatchReadNames` | mito-matching read IDs |
| `{prefix}_matched_{prefix}_1.input.fas` (and `_2`) | subsetted reads (deleted unless `--keepIntMed`) |
| `paired.fa`, `unpaired.fa` | from ReadsIsolation.py |
| `{prefix}_scaffolds.fa` | raw assembler output |
| `{prefix}_hmmout_tbl`, `{prefix}_hmmout_tbl_sorted.gff` | nhmmer on scaffolds + parsed GFF |
| **`{prefix}_detected_mito.fas`** | **primary assembly in NON-deepin mode** |

#### Additional files in `--deepin` mode

Inside `{prefix}/`:
- `{prefix}_deep_scaffolds.fa`
- `{prefix}_deep_hmmout_tbl`, `{prefix}_deep_hmmout_tbl_sorted.gff`
- **`{prefix}_deep_detected_mito.fas`** — **primary assembly in deepin mode**

**Outside `{prefix}/` (in the CWD where meangs.py was invoked):**
- **`scaffold_seeds.fas`** — v1.3.1+ only. Intermediate seed consumed by the second assembler pass; left behind on exit. `mitoSeeds='scaffold_seeds.fas'` is a bare relative path in source (`meangs.py:199`), so it lands in Python's CWD, NOT inside `{prefix}/`. Running multiple samples from the same CWD will overwrite this file.

#### Additional files in `--clip` mode (requires `--deepin`)

In the CWD (NOT `{prefix}/`):
- `mito_cliped.fas` — from `tools/detercirc.py`, default output prefix `mito_cliped` with no path join (`detercirc.py:25,92,100`). Same CWD-collision caveat as `scaffold_seeds.fas`.

#### Primary-file lookup for batch chaining

Code that auto-sources a seed from MEANGS output MUST branch on `meangs_deepin`:

1. `meangs_deepin: true` → `{prefix}/{prefix}_deep_detected_mito.fas`
2. else → `{prefix}/{prefix}_detected_mito.fas`

No other fallback is needed — `mito.fasta` appears in neither v1.0 nor v1.3.1 source. The `{prefix}/mito.fasta` branch at `smk/main.smk:196` is dead code and can be removed in a separate cleanup.

#### Version differences (v1.0 bioconda vs v1.3.1 upstream)

| Behavior | v1.0 (bioconda `meangs`) | v1.3.1 (upstream GitHub) |
|---|---|---|
| Deepin seed file | Reuses `{prefix}_detected_mito.fas` in place — no separate file | Writes `scaffold_seeds.fas` to CWD via `scaffold2seed.py` |
| Single-end input (`-1` only) | Not supported | Supported |
| QC quality threshold | Hard-coded `-q 0.01` | Configurable via `-q` flag (default 0.05) |

`smk/envs/meangs.yaml` installs the bioconda build (v1.0). Users who wire in upstream v1.3.1 via `tool_envs.meangs.bin_dir` will see the extra `scaffold_seeds.fas` (and `mito_cliped.fas` with `--clip`) in the Snakemake working directory.

---

### NOVOPlasty config parameters

NOVOPlasty is configured via a rendered config file (`2.NOVOPlasty/config.txt`), not CLI flags. The Jinja2 template is in `FastMitoAssembler/config.py`.

**Relevant config.yaml parameters (all prefixed `novoplasty_`):**

| Parameter | NOVOPlasty field | Notes |
|---|---|---|
| `novoplasty_genome_min_size` | `Genome Range` (lower) | bp; animal mt typically 12000–17000 |
| `novoplasty_genome_max_size` | `Genome Range` (upper) | bp |
| `novoplasty_kmer_size` | `K-mer` | default 33; try 21 or 45 if assembly fails |
| `novoplasty_max_mem_gb` | `Max memory` | GB RAM limit |
| `read_length` | `Read Length` | shared with MEANGS; 150 for standard Illumina |
| `insert_size` | `Insert size` | shared with MEANGS; 300 for standard PE |

**Output files (in `result/{sample}/2.NOVOPlasty/`):**

| File | Notes |
|---|---|
| `config.txt` | rendered Jinja2 config (from NOVOPlasty_config rule) |
| `Circularized_assembly_{sample}.fasta` or `Assembled_reads_{sample}.fasta` | raw NOVOPlasty output (wildcard `*{sample}.fasta`) |
| **`{sample}.novoplasty.fasta`** | **post-processed output (seqkit replace strips `+xxx`); fed to GetOrganelle `-s`** |
| `contigs_tmp_{sample}.txt`, `log_{sample}.txt` | deleted if `cleanup: true` |

**Debugging:** If NOVOPlasty produces no output fasta, check: (1) seed size — too short (<200 bp) often fails; (2) kmer size — increase if low-coverage; (3) genome size range — must include actual mt size.

---

### GetOrganelle output files

**Version in bundled env:** v1.7.7.0 (`smk/envs/getorganelle.yaml`). Source of truth: `get_organelle_from_reads.py --help`.

**Invocation shape (from `smk/main.smk`):**
```
get_organelle_from_reads.py --continue \
  -1 {sample}_1.sub.fq.gz -2 {sample}_2.sub.fq.gz \
  -F {organelle_database} \
  -o organelle \
  -s {novoplasty_fasta} \
  {getorganelle_flags}   # assembled from getorganelle_* config keys
```
Run from `result/{sample}/3.GetOrganelle/`. The `.sub.fq.gz` inputs are only created when `subsample_gb > 0` (default 5 Gb); when `subsample_gb: 0` the rule feeds raw `{input.fq1}` / `{input.fq2}` through directly.

**Config keys (all under `config.yaml`; blank = NOT forwarded, so GetOrganelle picks its own `-F`-dependent default):**

| Config key | GetOrganelle flag | Default if unset (v1.8.0.1, per `--help`) |
|---|---|---|
| `getorganelle_threads` | `-t` | we ship 4; upstream default is 1 |
| `getorganelle_rounds` | `-R` | `-F`-based: animal_mt=10, embplant_pt=15, embplant_mt/fungus_mt=30 |
| `getorganelle_kmers` | `-k` | `21,55,85,115` |
| `getorganelle_max_reads` | `--max-reads` | `-F`-based: animal_mt=3E8, embplant_mt/fungus_mt=7.5E7, others=1.5E7 |
| `getorganelle_reduce_reads_for_coverage` | `--reduce-reads-for-coverage` | 500 (soft bound; not `inf`) |
| `getorganelle_word_size` | `-w` | auto-estimated from read length |
| `getorganelle_max_extending_len` | `--max-extending-len` | no cap |
| `getorganelle_all_data: true` | — | convenience: sets `--max-reads inf` + `--reduce-reads-for-coverage inf` |
| `subsample_gb` | — (pipeline-local) | 5 Gb cap per mate before GetOrganelle; `0` disables |

Why blank keys are NOT forwarded: GetOrganelle's own defaults depend on `-F`, so a single hardcoded value would be wrong for anyone not running `animal_mt`. Pattern mirrors `/mnt/d/Claude/get.py:1340–1352`. Source of truth for defaults: `/mnt/d/Claude/other_softs/organelle_software_knowledge_pack/help_outputs/get_organelle_from_reads.full_help.txt`.

**Output files (in `result/{sample}/3.GetOrganelle/organelle/`):**

| File | Keep? | Notes |
|---|---|---|
| `*.complete.graph*.path_sequence.fasta` | ✅ | circular assembly — primary result |
| `*.scaffolds.graph*.path_sequence.fasta` | ✅ | linear/scaffold if no circular found |
| `*.fastg` | ✅ **always keep** | Bandage graph visualization |
| `*.gfa` | ✅ | GFA format graph |
| `filtered_spades/` | ❌ cleanup | SPAdes intermediate (~GB); deleted if `cleanup: true` |
| `extended*.fq` | ❌ cleanup | extended read pool |

**Final output processed by smk:**
```
result/{sample}/3.GetOrganelle/{organelle_database}.get_organelle.fasta
```
Created by `seqkit replace` renaming headers: circular → `{sample} topology=circular`, scaffold → `{sample} topology=linear`.

**Debugging:** If GetOrganelle fails with "no reads matched seed", the NOVOPlasty fasta may be empty or contain nuclear contamination. Check `{sample}.novoplasty.fasta` first with `grep -c ">"`. If `--continue` causes stale-state issues, delete the `organelle/` subdirectory and rerun.

---

### MitoZ annotate parameters

**Version:** v3.4 or v3.5 (both available as conda envs; check `smk/envs/mitoz.yaml` for bundled version). Source of truth: `mitoz annotate --help`.

**Invocation shape (from `smk/main.smk`):**
```
mitoz annotate \
  --outprefix {sample} \
  --thread_number {mitoz_thread_number} \
  --fastafiles {organelle_fasta} \
  --fq1 {fq1} --fq2 {fq2} \
  --species_name "{sample}" \
  --genetic_code {genetic_code} \
  --clade {mitoz_clade}
```
Run from `result/{sample}/4.MitozAnnotate/`.

**Key parameters in config.yaml:**

| Parameter | MitoZ flag | Notes |
|---|---|---|
| `mitoz_thread_number` | `--thread_number` | default 20; parallel HMM searches |
| `mitoz_clade` | `--clade` | must be one of the enum values below |
| `genetic_code` | `--genetic_code` | NCBI table number; `auto` if omitted (inferred from clade) |

**Valid `mitoz_clade` values** (from v3.5 `--help`):
`Chordata`, `Arthropoda`, `Echinodermata`, `Annelida-segmented-worms`, `Bryozoa`, `Mollusca`, `Nematoda`, `Nemertea-ribbon-worms`, `Porifera-sponges`

Note: `meangs_clade` accepts a broader set including `Cnidaria` and `Others`. If using a clade supported by MEANGS but not MitoZ, set `meangs_clade` to the broader value and `mitoz_clade` to the closest MitoZ-supported equivalent.

**Output files (in `result/{sample}/4.MitozAnnotate/{sample}.{organelle_db}.get_organelle.fasta.result/`):**

| File | Notes |
|---|---|
| **`circos.png`** | circular annotation plot (final pipeline target) |
| **`summary.txt`** | gene list + statistics (final pipeline target) |
| **`{sample}_{organelle_db}.get_organelle.fasta_mitoscaf.fa.gbf`** | GenBank format annotation (final pipeline target; for NCBI submission) |
| `tmp_*` | temporary files; deleted if `cleanup: true` |

**Debugging:** If MitoZ fails with "no PCG found", check: (1) `mitoz_clade` is correct; (2) `genetic_code` matches the species (e.g., code 5 for most invertebrates, code 2 for vertebrate mt); (3) input fasta has valid `topology=circular` or `topology=linear` in the header (set by the smk seqkit step).

---

## Tool chaining I/O reference

Debug dictionary for the MEANGS → NOVOPlasty → GetOrganelle → MitoZ chain.

Optional upstream step: if `fastp.enabled: true` in `config.yaml`, an adapter-only trimming rule (`fastp --detect_adapter_for_pe -Q -L`) runs first and its output feeds every downstream rule. Flags `-Q` and `-L` disable quality and length filtering — adapter removal only, per NOVOPlasty / GetOrganelle author guidance against Phred quality trimming. Disabled by default because the `*.clean.fq.gz` convention assumes adapters already removed.

```
result/{sample}/
├── 0.fastp/                               ← only when fastp.enabled: true
│   ├── {sample}_1.adapter.fq.gz
│   └── {sample}_2.adapter.fq.gz
├── 1.MEANGS/
│   └── {sample}_deep_detected_mito.fas    ← fed to NOVOPlasty config as Seed Input
│       (non-deepin: {sample}_detected_mito.fas)
├── 2.NOVOPlasty/
│   ├── config.txt                          ← Jinja2-rendered NOVOPlasty config
│   └── {sample}.novoplasty.fasta           ← fed to GetOrganelle -s
├── 3.GetOrganelle/
│   ├── {organelle_db}.get_organelle.fasta  ← fed to MitoZ --fastafiles
│   └── organelle/
│       ├── *.fastg                         ← Bandage visualization (NEVER delete)
│       └── filtered_spades/                ← deletable (~GB)
└── 4.MitozAnnotate/
    └── {sample}.{organelle_db}.get_organelle.fasta.result/
        ├── circos.png                      ← final target
        ├── summary.txt                     ← final target
        └── {sample}_{organelle_db}..._mitoscaf.fa.gbf  ← final target
```

**Common chain breakpoints and diagnosis:**

| Symptom | Most likely cause | Check |
|---|---|---|
| MEANGS rule fails | Low mitochondrial read fraction; wrong clade | Check `1.MEANGS/*.log.err`; try reducing `meangs_reads` |
| `seed_fas` is empty (0 sequences) | MEANGS found no mt reads | Inspect `{sample}_detected_mito.fas` directly |
| NOVOPlasty produces no `*{sample}.fasta` | Seed too short; genome size range too narrow | Check `2.NOVOPlasty/log_{sample}.txt` |
| GetOrganelle "no reads matched" | NOVOPlasty fasta empty or wrong organism | `grep -c ">" 2.NOVOPlasty/{sample}.novoplasty.fasta` |
| GetOrganelle stalls at max rounds | Coverage too low or kmer list needs adjustment | Raise `getorganelle_rounds` or narrow `getorganelle_kmers` |
| MitoZ "no PCG found" | Wrong clade or genetic code | Verify `mitoz_clade` and `genetic_code` |
| MitoZ topology error | Missing topology tag in fasta header | Check `3.GetOrganelle/{organelle_db}.get_organelle.fasta` headers |
