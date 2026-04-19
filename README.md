# Fast Assembler Workflow for MitoGenome
> `FastMitoAssembler` (alias: `fma` / `FMA`) is a software for fast, accurate assembly of mitochondrial genomes and generation of annotation documents.

### Credits

- **Original idea:** Deyuan Yang
- **Original code:** Bioinformatics engineers at Novogene (诺禾元生物科技)
- **Maintenance & updates:** Managed by Deyuan Yang using [Claude Code](https://claude.ai/code) — leveraging AI-assisted development to keep pace with the rapidly evolving bioinformatics ecosystem

### Installation

#### 1. Create environment

```bash
# Recommended: use mamba for faster solving
mamba create -n FastMitoAssembler -c conda-forge \
    python=3.9 "snakemake>=7" click jinja2 pyyaml ete3
```

Tool environments (MEANGS, NOVOPlasty, GetOrganelle, MitoZ) are created automatically
by Snakemake on first run — no manual installation needed.
Each tool lives in its own isolated environment, so upgrading one tool never breaks others.

#### 2. Activate environment

```bash
conda activate FastMitoAssembler
```

#### 3. Install FastMitoAssembler

```bash
pip install git+https://github.com/deyuanyang92-dev/FastMitoAssembler.git
```

### Update

When a new version is released, run:

```bash
conda activate FastMitoAssembler
pip install -U git+https://github.com/deyuanyang92-dev/FastMitoAssembler.git
```

Tool environments (MitoZ, GetOrganelle, etc.) are rebuilt automatically by Snakemake on the next run if their versions changed — no manual action needed.

#### Troubleshooting: `fma` / `FMA` command not found after upgrade

If `pip install -U` shows "Requirement already satisfied" (same version number) and skips reinstalling, the CLI entry points (`fma`, `FMA`) may not be regenerated. Fix with:

```bash
pip install --force-reinstall --no-deps \
    git+https://github.com/deyuanyang92-dev/FastMitoAssembler.git
```

Then verify:
```bash
fma --version
```

### CLI Aliases

After installation, three equivalent commands are available:
```bash
FastMitoAssembler --help
fma --help
FMA --help
```

### Check Tool Availability

If you already have tools installed (in PATH, a conda env, or a local directory):

```bash
# Check which tools are available in the current environment
fma check

# Also read tool_envs from a project config
fma check --configfile config.yaml

# Detect tools and save their locations globally (applies to all future projects)
fma check --save
```

The global config is saved to `~/.config/FastMitoAssembler/tool_envs.yaml` and loaded automatically by every `fma run` — configure once, use everywhere.

To override per-project, add `tool_envs` to your `config.yaml`:
```yaml
tool_envs:
  meangs:
    conda_env: 'my_meangs_env'   # existing conda environment name
    bin_dir: ''
  mitoz:
    conda_env: ''
    bin_dir: '/opt/mitoz/bin'    # directory containing tool binaries
```

### Prepare Database
```bash
FastMitoAssembler prepare

# 1. prepare ete3.NCBITaxa
FastMitoAssembler prepare ncbitaxa # download taxdump.tar.gz automaticlly
FastMitoAssembler prepare ncbitaxa --taxdump_file taxdump.tar.gz 

# 2. prepare database for GetOrganelle
FastMitoAssembler prepare organelle --list  # list configured databases
FastMitoAssembler prepare organelle -a animal_mt  # config a single database
FastMitoAssembler prepare organelle -a animal_mt -a embplant_mt # config multiple databases
FastMitoAssembler prepare organelle -a all  # config all databases
```

### Generate Config Files

```bash
# Generate config.yaml in the current directory
FastMitoAssembler init

# Also generate options.yaml (for Snakemake/cluster settings)
FastMitoAssembler init --options

# Custom output filename
FastMitoAssembler init -o myproject.yaml

# Overwrite existing files without prompting
FastMitoAssembler init --force
```

### Run Workflow

`config.yaml` example:
```yaml
reads_dir: '../data/'
samples: ['2222-4']
fq_path_pattern: '{sample}/{sample}_1.clean.fq.gz' # the reads 1 path pattern relative to `reads_dir`
```
see the main Snakefile and Template configfile with: `FastMitoAssembler --help` 
#### Use with Client
```bash
FastMitoAssembler --help

FastMitoAssembler run --help

# run with configfile [recommended]
# --use-conda is on by default; tool environments are auto-created on first run
FastMitoAssembler run --configfile config.yaml

# run with parameters
FastMitoAssembler run --reads_dir ../data --samples S1 --samples S2

# auto-detect samples from reads directory (no --samples needed)
# default suffix pair: _1.clean.fq.gz,_2.clean.fq.gz
FastMitoAssembler run --reads_dir ../data

# support multiple suffix pairs (separated by ";")
FastMitoAssembler run --reads_dir ../data \
    --suffix_fq '_1.clean.fq.gz,_2.clean.fq.gz;_R1.fastq.gz,_R2.fastq.gz'

# set cores
FastMitoAssembler run --configfile config.yaml --cores 8

# dryrun the workflow
FastMitoAssembler run --configfile config.yaml --dryrun

# HPC: share tool environments across projects to avoid rebuilding
FastMitoAssembler run --configfile config.yaml --cores 8 \
    --conda-prefix ~/.conda/snakemake-envs

# run with options
FastMitoAssembler run --configfile config.yaml --optionfile options.yaml
# cat options.yaml
# printshellcmds: true
# cores: 2
```
#### Use with Snakemake
```bash
# the `main.smk` and `config.yaml` template can be found with command: `FastMitoAssembler`
snakemake -s /path/to/FastMitoAssembler/smk/main.smk -c config.yaml --cores 4

snakemake -s /path/to/FastMitoAssembler/smk/main.smk -c config.yaml --cores 4 --printshellcmds

snakemake -s /path/to/FastMitoAssembler/smk/main.smk -c config.yaml --printshellcmds --dryrun
```

#### Use with Cluster
```bash
mkdir -p logs/sge/
FastMitoAssembler run --configfile config.yaml --optionfile options.yaml
```
```yaml
# options.yaml
cluster: "qsub -V -cwd -S /bin/bash -e logs/sge/ -o logs/sge/"
```

#### Use with Docker
[docker-readme](./docker/README.md)


### Example Results Directory
- `[*]` represents the main result

```
result/
└── 2222-4
    ├── 1.MEANGS
    │   ├── 2222-4
    │   ├── 2222-4_deep_detected_mito.fas  [*]
    │   └── scaffold_seeds.fas
    ├── 2.NOVOPlasty
    │   ├── config.txt
    │   ├── Contigs_1_2222-4.fasta
    │   ├── 2222-4.novoplasty.fasta  [*]
    │   ├── contigs_tmp_2222-4.txt
    │   └── log_2222-4.txt
    ├── 3.GetOrganelle
    │   ├── 2222-4_1.5G.fq.gz
    │   ├── 2222-4_2.5G.fq.gz
    │   ├── 2222-4.fq1.stats.txt
    │   ├── animal_mt.get_organelle.fasta  [*]
    │   └── organelle
    └── 4.MitozAnnotate
        ├── 2222-4.animal_mt.get_organelle.fasta.result  [*]
        └── tmp_2222-4_animal_mt.get_organelle.fasta_mitoscaf.fa

```

##### Softwares Used
- [MEANGS](https://github.com/YanCCscu/meangs)
- [NOVOplasty](https://github.com/Edith1715/NOVOplasty)
- [GetOrganelle](https://github.com/Kinggerm/GetOrganelle)
- [SPAdes](https://github.com/ablab/spades)
- [MitoZ](https://github.com/linzhi2013/MitoZ)
- [NCBI-Blast](https://blast.ncbi.nlm.nih.gov/doc/blast-help/downloadblastdata.html)
