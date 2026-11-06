"""
Fast Assembler Workflow for MitoGenome

Author: Qingdong Su
"""
import os
import sys
from pathlib import Path
from functools import partial

# Use in development
FAST_MITO_AS_PATH = config.get("FAST_MITO_AS_PATH") or os.getenv('FAST_MITO_AS_PATH')
sys.path.insert(0, FAST_MITO_AS_PATH)
from FastMitoAssembler.config import NOVOPLASTY_CONFIG_TPL
from FastMitoAssembler.util import safe_open

# --gui mode, config object not work, need use configfile instead.
# configfile: 'config.yaml'

# ==============================================================
# Configuration information
SAMPLES = config.get("samples")
ORGANELLE_DB = config.get("organelle_database", "animal_mt")
SEED_INPUT = config.get('seed_input')
SEED_INPUT = Path(SEED_INPUT).resolve() if SEED_INPUT else 'none'

# NOVOPlasty configuration
GENOME_MIN_SIZE = config.get('genome_min_size', 12000)
GENOME_MAX_SIZE = config.get('genome_max_size', 30000)
KMER_SIZE = config.get('kmer_size', 39)
MAX_MEM_GB = config.get('max_mem_gb', 10)
READ_LENGTH = int(config.get('read_length', 150))
INSERT_SIZE = config.get('insert_size', 300)
# MitozAnnotate configuration
CLADE = config.get('clade', 'Annelida-segmented-worms')
GENETIC_CODE = config.get('genetic_code', 5)
THREAD_NUMBER = config.get('thread_number', 20)
# ==============================================================

# ==============================================================
# Log directory
LOG_DIR = Path(config.get("log_dir", "logs")).resolve()
# Output directory
RESULT_DIR = Path(config.get("result_dir", "result")).resolve()
SAMPLE_DIR = partial(os.path.join, RESULT_DIR, "{sample}")
MEANGS_DIR = partial(SAMPLE_DIR, "1.MEANGS")
NOVOPLASTY_DIR = partial(SAMPLE_DIR, "2.NOVOPlasty")
ORGANELLE_DIR = partial(SAMPLE_DIR, "3.GetOrganelle")
MITOZ_ANNO_DIR = partial(SAMPLE_DIR, "4.MitozAnnotate")

# v0.03: MitoZ can annotate external FASTA files (batch mitoz), e.g. '/data/{sample}.fasta'
FASTA_PATTERN = config.get('fasta_pattern')
MITOZ_FASTA_NAME = 'input.fasta' if FASTA_PATTERN else f'{ORGANELLE_DB}.get_organelle.fasta'
MITOZ_ANNO_RESULT_DIR = partial(MITOZ_ANNO_DIR, f"{{sample}}.{MITOZ_FASTA_NAME}.result")

# Benchmark directory
BENCHMARK_DIR = Path(config.get("benchmark_dir", "benchmark")).resolve()

# input/output
seed_fas = MEANGS_DIR("{sample}_deep_detected_mito.fas")
novoplasty_config = NOVOPLASTY_DIR("config.txt")
novoplasty_fasta = NOVOPLASTY_DIR("{sample}.novoplasty.fasta")
organelle_fasta_new = ORGANELLE_DIR(f"{ORGANELLE_DB}.get_organelle.fasta")
# ==============================================================

# ==============================================================
# Read data
READS_DIR = Path(config.get("reads_dir") or ".").resolve()
FQ_PATH_PATTERN = config.get('fq_path_pattern', '{sample}/{sample}_1.clean.fq.gz')
RAW_FQ1 = READS_DIR.joinpath(FQ_PATH_PATTERN)
RAW_FQ2 = READS_DIR.joinpath(FQ_PATH_PATTERN.replace('1', '2'))

# v0.03: optional adapter-only trimming with fastp (off by default).
# NOVOPlasty and GetOrganelle recommend raw (not quality-trimmed) reads,
# so only adapters are removed; all downstream steps use the trimmed reads.
FASTP = bool(config.get('fastp', False))
if FASTP:
    FQ1 = SAMPLE_DIR("0.fastp", "{sample}_1.fastp.fq.gz")
    FQ2 = SAMPLE_DIR("0.fastp", "{sample}_2.fastp.fq.gz")
else:
    FQ1, FQ2 = RAW_FQ1, RAW_FQ2

# v0.03: seed for GetOrganelle: novoplasty (default, original design) | meangs | none
# none + seed_input: the MEANGS rule only converts seed_input (MEANGS is not run).
GETORGANELLE_SEED = config.get('getorganelle_seed', 'novoplasty')
if GETORGANELLE_SEED == 'novoplasty':
    GETORGANELLE_SEED_FILE = novoplasty_fasta
elif GETORGANELLE_SEED == 'meangs' or SEED_INPUT != 'none':
    GETORGANELLE_SEED_FILE = seed_fas
else:
    GETORGANELLE_SEED_FILE = None


# FQ1 = READS_DIR.joinpath("{sample}_1.clean.fq.gz")
# FQ2 = READS_DIR.joinpath("{sample}_2.clean.fq.gz")
READS_NUM_5G = round(5e9 / 2 / READ_LENGTH)
CUT_5G_DATA = config.get('cut_5g_data', 'yes')
# ==============================================================

# default target
rule all:
    """
    Specify the output files for all samples using the expand function.
    """
    message: "Congratulations, the pipeline process is complete!"
    input:
        expand(MITOZ_ANNO_RESULT_DIR("circos.png"), sample=SAMPLES),
        expand(MITOZ_ANNO_RESULT_DIR("summary.txt"), sample=SAMPLES),
        expand(MITOZ_ANNO_RESULT_DIR(f"{{sample}}_{ORGANELLE_DB}.get_organelle.fasta_mitoscaf.fa.gbf"), sample=SAMPLES),
    run:
        print('ok')

# v0.03: partial targets
rule meangs_all:
    """MEANGS only."""
    input:
        expand(seed_fas, sample=SAMPLES),

rule getorganelle_all:
    """GetOrganelle only (getorganelle_seed: none), or after MEANGS/NOVOPlasty."""
    input:
        expand(organelle_fasta_new, sample=SAMPLES),

rule mitoz_all:
    """MitoZ annotation only (summary.txt is always produced by MitoZ annotate)."""
    input:
        expand(MITOZ_ANNO_RESULT_DIR("summary.txt"), sample=SAMPLES),

if FASTP:
    rule fastp:
        """
        Adapter-only trimming with fastp.
        - https://github.com/OpenGene/fastp

        -Q disables quality filtering, -L disables length filtering.
        """
        input:
            fq1=RAW_FQ1,
            fq2=RAW_FQ2,
        output:
            fq1=FQ1,
            fq2=FQ2,
        params:
            outdir=SAMPLE_DIR("0.fastp"),
        message: "fastp for sample: {wildcards.sample}"
        log: LOG_DIR.joinpath('{sample}', 'fastp.log')
        benchmark: BENCHMARK_DIR.joinpath('{sample}', 'fastp.stat')
        shell:
            """
            (mkdir -p {params.outdir}
            fastp --detect_adapter_for_pe -Q -L \\
                -i {input.fq1} -I {input.fq2} \\
                -o {output.fq1} -O {output.fq2} \\
                -j {params.outdir}/{wildcards.sample}.fastp.json \\
                -h {params.outdir}/{wildcards.sample}.fastp.html
            ) 2>{log}.err 1>{log}
            """

rule MEANGS:
    """
    Detect and retrieve the longest mitochondrial sequence using MEANGS.
    - https://github.com/YanCCscu/MEANGS/

    Input:
    fq1, fq2: Paired clean FASTQ format files.

    Output:
    seed_fas: A FASTA format file of the detected mitochondrial sequence containing only the longest sequence.

    Parameters:
    outdir: Output directory.
    seed_input: use a input fasta/genbank as seed_fas

    Note:
    Keep the first reads only as output
    """
    input:
        fq1=FQ1,
        fq2=FQ2,
    output:
        seed_fas=seed_fas,
    params:
        outdir=MEANGS_DIR(),
        seed_input=SEED_INPUT,
    message: "MEANGS for sample: {wildcards.sample}"
    log: LOG_DIR.joinpath('{sample}', 'meangs.log')
    benchmark: BENCHMARK_DIR.joinpath('{sample}', 'meangs.stat')
    shell:
        """
        (mkdir -p {params.outdir}
        cd {params.outdir}

        seed_input={params.seed_input}

        if [[ $seed_input =~ \.gb[kf]?$ ]];then
            genbank.py -f fasta $seed_input | seqkit head -n1 -w0 -o {output.seed_fas}
        elif [[ $seed_input =~ \.fa[sta]*$ ]];then
            seqkit head -n1 -w0 -o {output.seed_fas} $seed_input 
        else
            meangs.py \\
                -1 {input.fq1} \\
                -2 {input.fq2} \\
                -o {wildcards.sample} \\
                -t 2 \\
                -n 2000000 \\
                -i 350 \\
                --deepin
            seqkit head -n1 -w0 -o {output.seed_fas} {wildcards.sample}/{wildcards.sample}_deep_detected_mito.fas
        fi) 2>{log}.err 1>{log}
        """

rule NOVOPlasty_config:
    """
    Generate the configuration file for NOVOPlasty.

    Input:
    fq1, fq2: Paired clean FASTQ format files.
    seed_fas: A FASTA format file of the detected mitochondrial sequence containing only the longest sequence obtained by MEANGS.

    Output:
    novoplasty_config: The configuration file for NOVOPlasty.

    Parameters:
    output_path: Output directory.
    """
    input:
        fq1=FQ1,
        fq2=FQ2,
        seed_fas=seed_fas,
    output:
        novoplasty_config=novoplasty_config,
    params:
        output_path=NOVOPLASTY_DIR() + os.path.sep,
    message: "NOVOPlasty_config for sample: {wildcards.sample}"
    run:
        with safe_open(output.novoplasty_config, "w") as out:
            context = NOVOPLASTY_CONFIG_TPL.render(
                seed_fasta=input.seed_fas,
                sample=wildcards.sample,
                fq1=input.fq1,
                fq2=input.fq2,
                output_path=params.output_path,
                genome_min_size=GENOME_MIN_SIZE,
                genome_max_size=GENOME_MAX_SIZE,
                kmer_size=KMER_SIZE,
                max_mem_gb=MAX_MEM_GB,
                read_length=READ_LENGTH,
                insert_size=INSERT_SIZE,
            )
            out.write(context)

rule NOVOPlasty:
    """
    Assemble mitochondrial genome using NOVOPlasty.
    - https://github.com/Edith1715/NOVOplasty

    Input:
    fq1, fq2: Paired clean FASTQ format files.
    novoplasty_config: The configuration file for NOVOPlasty.

    Output:
    novoplasty_contigs_new: The assembled mitochondrial genome in FASTA format.
    """
    input:
        novoplasty_config=novoplasty_config,
    output:
        novoplasty_fasta=novoplasty_fasta,
    params:
        output_path = NOVOPLASTY_DIR(),
    message: "NOVOPlasty for sample: {wildcards.sample}"
    log: LOG_DIR.joinpath('{sample}', 'novoplasty.log')
    benchmark: BENCHMARK_DIR.joinpath('{sample}', 'novoplasty.stat')
    shell:
        """
        (
        cd {params.output_path}

        NOVOPlasty.pl -c {input.novoplasty_config}

        # remove +xxx
        seqkit replace -w0 \\
            -p "\+.+" -r "" \\
            -o {output.novoplasty_fasta} \\
            *{wildcards.sample}.fasta
        ) 2>{log}.err 1>{log}
        """

rule GetOrganelle:
    """
    Assemble mitochondrial genome using GetOrganelle.
    - https://github.com/Kinggerm/GetOrganelle

    Input:
    fq1, fq2: Paired clean FASTQ format files.
    novoplasty_contigs_new: The contig sequences generated by NOVOPlasty.

    Output:
    organelle_fasta_new: The improved version of organelle_fasta after the second assembly by GetOrganelle

    Params:
    output_path: Output directory.

    Note:
    This rule use 5G data as input.
    """
    input:
        fq1=FQ1,
        fq2=FQ2,
        seed=GETORGANELLE_SEED_FILE or [],
    output:
        organelle_fasta_new=organelle_fasta_new,
    params:
        output_path=ORGANELLE_DIR(),
        output_path_temp=ORGANELLE_DIR("organelle"),
        seed_arg=lambda wildcards, input: f'-s {input.seed}' if input.seed else '',
    message: "GetOrganelle for sample: {wildcards.sample}"
    log: LOG_DIR.joinpath('{sample}', 'get_organelle.log')
    benchmark: BENCHMARK_DIR.joinpath('{sample}', 'get_organelle.stat')
    shell:
        """
        (
        mkdir -p {params.output_path}
        cd {params.output_path}

        # get 5G data
        if [ ! -e {wildcards.sample}_1.5G.fq.gz ];then
            seqkit stats {input.fq1} > {wildcards.sample}.fq1.stats.txt
            reads_num_fq1=$(awk 'NR==2{{print $4}}' {wildcards.sample}.fq1.stats.txt | sed 's#,##g')
            echo "reads num of fq1: $reads_num_fq1"

            if [ $reads_num_fq1 -gt {READS_NUM_5G} ];then
                seqkit head -n {READS_NUM_5G} -w0 {input.fq1} -j4 -o {wildcards.sample}_1.5G.fq.gz
                seqkit head -n {READS_NUM_5G} -w0 {input.fq2} -j4 -o {wildcards.sample}_2.5G.fq.gz
            else
                ln -sf {input.fq1} {wildcards.sample}_1.5G.fq.gz
                ln -sf {input.fq2} {wildcards.sample}_2.5G.fq.gz
            fi
        fi

        # run GetOrganelle
        get_organelle_from_reads.py \\
            --continue \\
            -1 {wildcards.sample}_1.5G.fq.gz\\
            -2 {wildcards.sample}_2.5G.fq.gz \\
            -R 20 \\
            -k 21,33,45,55,65,75,85,95,105,111,127 \\
            -F {ORGANELLE_DB} \\
            -o {params.output_path_temp} \\
            --reduce-reads-for-coverage inf \\
            --max-reads inf {params.seed_arg}

        # replace '+', 'circular' characters
        seqkit replace -w0 \\
            -p ".*(circular).*" -r "{wildcards.sample} topology=circular" \\
            organelle/*fasta |
        seqkit replace -w0 \\
            -p "^scaffold.*" -r "{wildcards.sample} topology=linear" \\
            -o {output.organelle_fasta_new}
        ) 2>{log}.err 1>{log}
    """

# v0.03: MitoZ input: GetOrganelle result (default) or external FASTA (fasta_pattern).
# Reads are always used for the GetOrganelle result; for external FASTA only when reads_dir is set.
if FASTA_PATTERN:
    MITOZ_FASTA = MITOZ_ANNO_DIR(MITOZ_FASTA_NAME)
    MITOZ_READS = {'fq1': FQ1, 'fq2': FQ2} if config.get('reads_dir') else {}
    MITOZ_OUTPUTS = {'summary': MITOZ_ANNO_RESULT_DIR("summary.txt")}

    rule MitozInputFasta:
        """Copy the external FASTA ({fasta_pattern}) into the MitoZ directory."""
        input:
            fasta=FASTA_PATTERN,
        output:
            fasta=MITOZ_FASTA,
        shell:
            "cp -L {input.fasta} {output.fasta}"
else:
    MITOZ_FASTA = organelle_fasta_new
    MITOZ_READS = {'fq1': FQ1, 'fq2': FQ2}
    MITOZ_OUTPUTS = {
        'circos': MITOZ_ANNO_RESULT_DIR("circos.png"),
        'summary': MITOZ_ANNO_RESULT_DIR("summary.txt"),
        'genbank': MITOZ_ANNO_RESULT_DIR(f"{{sample}}_{ORGANELLE_DB}.get_organelle.fasta_mitoscaf.fa.gbf"),
    }

rule MitozAnnotate:
    """
    Annotate mitochondrial genome using MitoZ.
    - https://github.com/linzhi2013/MitoZ

    Input:
    fq1, fq2: Paired clean FASTQ format files.
    organelle_fasta_new: Path to the assembled mitochondrial genome in FASTA format generated by GetOrganelle.

    Outputs:
    circos: Path to the circular plot of the annotated mitochondrial genome.

    Params:
    outdir: Path to the directory where the output files should be saved.
    """
    input:
        **MITOZ_READS,
        organelle_fasta_new=MITOZ_FASTA,
    output:
        **MITOZ_OUTPUTS,
    params:
        outdir=MITOZ_ANNO_DIR(),
        fq_arg=lambda wildcards, input: f'--fq1 {input.fq1} --fq2 {input.fq2}' if MITOZ_READS else '',
    message: "MitozAnnotate for sample: {wildcards.sample}"
    log: LOG_DIR.joinpath('{sample}', 'mitoz_annotate.log')
    benchmark: BENCHMARK_DIR.joinpath('{sample}', 'mitoz_annotate.stat')
    shell:
        """
        (
        mkdir -p {params.outdir}
        cd {params.outdir}

        mitoz annotate \\
            --outprefix {wildcards.sample} \\
            --thread_number {THREAD_NUMBER} \\
            --fastafiles {input.organelle_fasta_new} {params.fq_arg} \\
            --species_name "{wildcards.sample}" \\
            --genetic_code {GENETIC_CODE} \\
            --clade {CLADE}
        ) 2>{log}.err 1>{log}
        """
