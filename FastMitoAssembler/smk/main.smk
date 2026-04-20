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
NOVOPLASTY_GENOME_MIN_SIZE = config.get('novoplasty_genome_min_size', 12000)
NOVOPLASTY_GENOME_MAX_SIZE = config.get('novoplasty_genome_max_size', 30000)
NOVOPLASTY_KMER_SIZE = config.get('novoplasty_kmer_size', 39)
NOVOPLASTY_MAX_MEM_GB = config.get('novoplasty_max_mem_gb', 10)
READ_LENGTH = int(config.get('read_length', 150))
INSERT_SIZE = config.get('insert_size', 300)
# MitozAnnotate configuration
MITOZ_CLADE = config.get('mitoz_clade', 'Annelida-segmented-worms')
GENETIC_CODE = config.get('genetic_code', 5)
MITOZ_THREAD_NUMBER = config.get('mitoz_thread_number', 20)
# MEANGS configuration
MEANGS_THREAD = config.get('meangs_thread', 4)
MEANGS_READS  = config.get('meangs_reads', 2000000)
MEANGS_DEEPIN = config.get('meangs_deepin', True)
MEANGS_CLADE  = config.get('meangs_clade', 'Annelida-segmented-worms')

# GetOrganelle configuration — blank config values are intentionally NOT
# forwarded so GetOrganelle applies its own -F-dependent defaults.
GETORGANELLE_ALL_DATA = bool(config.get('getorganelle_all_data', False))

def _go_flag(flag, key):
    v = config.get(key)
    if v in (None, '', []):
        return ''
    return f'{flag} {v}'

def _build_go_flags():
    parts = [
        _go_flag('-R', 'getorganelle_rounds'),
        _go_flag('-k', 'getorganelle_kmers'),
        _go_flag('-t', 'getorganelle_threads'),
        _go_flag('-w', 'getorganelle_word_size'),
        _go_flag('--max-extending-len', 'getorganelle_max_extending_len'),
    ]
    if GETORGANELLE_ALL_DATA:
        parts.append(_go_flag('--max-reads', 'getorganelle_max_reads') or '--max-reads inf')
        parts.append(_go_flag('--reduce-reads-for-coverage', 'getorganelle_reduce_reads_for_coverage') or '--reduce-reads-for-coverage inf')
    else:
        parts.append(_go_flag('--max-reads', 'getorganelle_max_reads'))
        parts.append(_go_flag('--reduce-reads-for-coverage', 'getorganelle_reduce_reads_for_coverage'))
    return ' '.join(p for p in parts if p)

GETORGANELLE_FLAGS = _build_go_flags()

# Optional fastp adapter-only trimming
FASTP_CFG = config.get('fastp') or {}
FASTP_ENABLED = bool(FASTP_CFG.get('enabled'))
FASTP_EXTRA = FASTP_CFG.get('extra_args') or ''

# Cleanup intermediate files after each step
CLEANUP = config.get('cleanup', False)
# ==============================================================

# ==============================================================
# Per-tool execution prefix (supports conda_env or bin_dir overrides)
_TOOL_ENVS = config.get('tool_envs', {})

def _shell_prefix(tool):
    cfg = _TOOL_ENVS.get(tool) or {}
    if not isinstance(cfg, dict):
        return ''
    conda_env = (cfg.get('conda_env') or '').strip()
    bin_dir = (cfg.get('bin_dir') or '').strip()
    if conda_env:
        return f'conda run --no-capture-output -n {conda_env} '
    if bin_dir:
        return f'PATH="{bin_dir}:$PATH" '
    return ''

def _tool_cmd(tool, default_cmd):
    """Return the shell command to invoke a tool.

    If the tool has a script_path configured (e.g. NOVOPlasty.pl), the command
    becomes 'perl /abs/path/to/script' instead of the default binary name.
    """
    cfg = _TOOL_ENVS.get(tool) or {}
    if not isinstance(cfg, dict):
        return default_cmd
    script_path = (cfg.get('script_path') or '').strip()
    if script_path:
        return f'perl {Path(script_path).expanduser().resolve()}'
    return default_cmd
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
MITOZ_ANNO_RESULT_DIR = partial(MITOZ_ANNO_DIR, f"{{sample}}.{ORGANELLE_DB}.get_organelle.fasta.result")

# Benchmark directory
BENCHMARK_DIR = Path(config.get("benchmark_dir", "benchmark")).resolve()

# input/output
FASTP_DIR = partial(SAMPLE_DIR, "0.fastp")
seed_fas = MEANGS_DIR("{sample}_deep_detected_mito.fas")
novoplasty_config = NOVOPLASTY_DIR("config.txt")
novoplasty_fasta = NOVOPLASTY_DIR("{sample}.novoplasty.fasta")
organelle_fasta_new = ORGANELLE_DIR(f"{ORGANELLE_DB}.get_organelle.fasta")
mm_report = partial(SAMPLE_DIR, "materials_and_methods.md")
# ==============================================================

# ==============================================================
# Read data
READS_DIR = Path(config.get("reads_dir", ".")).resolve()
FQ_PATH_PATTERN = config.get('fq_path_pattern', '{sample}/{sample}_1.clean.fq.gz')
RAW_FQ1 = READS_DIR.joinpath(FQ_PATH_PATTERN)
RAW_FQ2 = READS_DIR.joinpath(FQ_PATH_PATTERN.replace('1', '2'))

# When fastp is enabled, downstream rules consume its output instead of raw reads.
FASTP_FQ1 = FASTP_DIR("{sample}_1.adapter.fq.gz")
FASTP_FQ2 = FASTP_DIR("{sample}_2.adapter.fq.gz")
FQ1 = FASTP_FQ1 if FASTP_ENABLED else RAW_FQ1
FQ2 = FASTP_FQ2 if FASTP_ENABLED else RAW_FQ2

# Subsample before GetOrganelle (0 / null → no subsample, feed all reads through).
SUBSAMPLE_GB = config.get('subsample_gb', 5) or 0
SUBSAMPLE_READS = round(SUBSAMPLE_GB * 1e9 / 2 / READ_LENGTH) if SUBSAMPLE_GB else 0
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
        expand(mm_report(), sample=SAMPLES),
    run:
        print('ok')

if FASTP_ENABLED:
    rule fastp_adapter_trim:
        """
        Optional upstream adapter-only trim via fastp.

        `-Q` disables quality filtering and `-L` disables length filtering —
        adapter removal only, per NOVOPlasty / GetOrganelle author guidance
        against Phred quality trimming.
        Materialised only when `fastp.enabled: true` in config.yaml.
        """
        input:
            fq1=RAW_FQ1,
            fq2=RAW_FQ2,
        output:
            fq1=FASTP_FQ1,
            fq2=FASTP_FQ2,
        params:
            outdir=FASTP_DIR(),
            extra=FASTP_EXTRA,
            tool_prefix=_shell_prefix('fastp'),
        conda: "envs/fastp.yaml"
        message: "fastp (adapter-only) for sample: {wildcards.sample}"
        log: LOG_DIR.joinpath('{sample}', 'fastp.log')
        benchmark: BENCHMARK_DIR.joinpath('{sample}', 'fastp.stat')
        shell:
            """
            (
            mkdir -p {params.outdir}
            {params.tool_prefix}fastp --detect_adapter_for_pe -Q -L \\
                -i {input.fq1} -I {input.fq2} \\
                -o {output.fq1} -O {output.fq2} \\
                {params.extra} \\
                -j {log}.json -h {log}.html
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
        tool_prefix=_shell_prefix('meangs'),
        meangs_thread=MEANGS_THREAD,
        meangs_reads=MEANGS_READS,
        meangs_deepin=MEANGS_DEEPIN,
        meangs_clade=MEANGS_CLADE,
        deepin_flag='--deepin' if MEANGS_DEEPIN else '',
        insert_size=INSERT_SIZE,
        cleanup=CLEANUP,
    conda: "envs/meangs.yaml"
    message: "MEANGS for sample: {wildcards.sample}"
    log: LOG_DIR.joinpath('{sample}', 'meangs.log')
    benchmark: BENCHMARK_DIR.joinpath('{sample}', 'meangs.stat')
    shell:
        """
        (mkdir -p {params.outdir}
        cd {params.outdir}

        seed_input={params.seed_input}

        if [[ $seed_input =~ \.gb[kf]?$ ]];then
            {params.tool_prefix}genbank.py -f fasta $seed_input | seqkit head -n1 -w0 -o {output.seed_fas}
        elif [[ $seed_input =~ \.fa[sta]*$ ]];then
            seqkit head -n1 -w0 -o {output.seed_fas} $seed_input
        else
            {params.tool_prefix}meangs.py \\
                -1 {input.fq1} \\
                -2 {input.fq2} \\
                -o {wildcards.sample} \\
                -t {params.meangs_thread} \\
                -n {params.meangs_reads} \\
                -i {params.insert_size} \\
                --clade {params.meangs_clade} \\
                {params.deepin_flag}

            # locate MEANGS output: deepin → _deep_detected_mito.fas
            # non-deepin → _detected_mito.fas, or mito.fasta in some versions
            if [ "{params.meangs_deepin}" = "True" ]; then
                meangs_out={wildcards.sample}/{wildcards.sample}_deep_detected_mito.fas
            elif [ -f {wildcards.sample}/{wildcards.sample}_detected_mito.fas ]; then
                meangs_out={wildcards.sample}/{wildcards.sample}_detected_mito.fas
            else
                meangs_out={wildcards.sample}/mito.fasta
            fi
            seqkit head -n1 -w0 -o {output.seed_fas} $meangs_out

            if [ "{params.cleanup}" = "True" ]; then
                rm -rf {wildcards.sample}/
            fi
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
                genome_min_size=NOVOPLASTY_GENOME_MIN_SIZE,
                genome_max_size=NOVOPLASTY_GENOME_MAX_SIZE,
                kmer_size=NOVOPLASTY_KMER_SIZE,
                max_mem_gb=NOVOPLASTY_MAX_MEM_GB,
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
        output_path=NOVOPLASTY_DIR(),
        tool_prefix=_shell_prefix('novoplasty'),
        novoplasty_cmd=_tool_cmd('novoplasty', 'NOVOPlasty.pl'),
        cleanup=CLEANUP,
    conda: "envs/novoplasty.yaml"
    message: "NOVOPlasty for sample: {wildcards.sample}"
    log: LOG_DIR.joinpath('{sample}', 'novoplasty.log')
    benchmark: BENCHMARK_DIR.joinpath('{sample}', 'novoplasty.stat')
    shell:
        """
        (
        cd {params.output_path}

        {params.tool_prefix}{params.novoplasty_cmd} -c {input.novoplasty_config}

        # remove +xxx
        seqkit replace -w0 \\
            -p "\+.+" -r "" \\
            -o {output.novoplasty_fasta} \\
            *{wildcards.sample}.fasta

        if [ "{params.cleanup}" = "True" ]; then
            rm -f contigs_tmp_{wildcards.sample}.txt \
                  log_{wildcards.sample}.txt
        fi
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
        novoplasty_fasta=novoplasty_fasta,
    output:
        organelle_fasta_new=organelle_fasta_new,
    params:
        output_path=ORGANELLE_DIR(),
        output_path_temp=ORGANELLE_DIR("organelle"),
        tool_prefix=_shell_prefix('getorganelle'),
        go_flags=GETORGANELLE_FLAGS,
        subsample_reads=SUBSAMPLE_READS,
        cleanup=CLEANUP,
    conda: "envs/getorganelle.yaml"
    message: "GetOrganelle for sample: {wildcards.sample}"
    log: LOG_DIR.joinpath('{sample}', 'get_organelle.log')
    benchmark: BENCHMARK_DIR.joinpath('{sample}', 'get_organelle.stat')
    shell:
        """
        (
        mkdir -p {params.output_path}
        cd {params.output_path}

        # Optional subsample (config: subsample_gb; 0 disables).
        if [ {params.subsample_reads} -gt 0 ] && [ ! -e {wildcards.sample}_1.sub.fq.gz ]; then
            seqkit stats {input.fq1} > {wildcards.sample}.fq1.stats.txt
            reads_num_fq1=$(awk 'NR==2{{print $4}}' {wildcards.sample}.fq1.stats.txt | sed 's#,##g')
            echo "reads num of fq1: $reads_num_fq1"
            if [ $reads_num_fq1 -gt {params.subsample_reads} ]; then
                seqkit head -n {params.subsample_reads} -w0 {input.fq1} -j4 -o {wildcards.sample}_1.sub.fq.gz
                seqkit head -n {params.subsample_reads} -w0 {input.fq2} -j4 -o {wildcards.sample}_2.sub.fq.gz
            else
                ln -sf {input.fq1} {wildcards.sample}_1.sub.fq.gz
                ln -sf {input.fq2} {wildcards.sample}_2.sub.fq.gz
            fi
        fi

        if [ {params.subsample_reads} -gt 0 ]; then
            go_fq1={wildcards.sample}_1.sub.fq.gz
            go_fq2={wildcards.sample}_2.sub.fq.gz
        else
            go_fq1={input.fq1}
            go_fq2={input.fq2}
        fi

        # run GetOrganelle
        {params.tool_prefix}get_organelle_from_reads.py \\
            --continue \\
            -1 $go_fq1 \\
            -2 $go_fq2 \\
            -F {ORGANELLE_DB} \\
            -o {params.output_path_temp} \\
            -s {input.novoplasty_fasta} \\
            {params.go_flags}

        # replace '+', 'circular' characters
        seqkit replace -w0 \\
            -p ".*(circular).*" -r "{wildcards.sample} topology=circular" \\
            organelle/*fasta |
        seqkit replace -w0 \\
            -p "^scaffold.*" -r "{wildcards.sample} topology=linear" \\
            -o {output.organelle_fasta_new}

        if [ "{params.cleanup}" = "True" ]; then
            rm -rf organelle/filtered_spades/
            rm -f organelle/extended*.fq
            rm -f {wildcards.sample}_1.sub.fq.gz \
                  {wildcards.sample}_2.sub.fq.gz \
                  {wildcards.sample}.fq1.stats.txt
        fi
        ) 2>{log}.err 1>{log}
    """

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
        fq1=FQ1,
        fq2=FQ2,
        organelle_fasta_new=organelle_fasta_new,
    output:
        circos=MITOZ_ANNO_RESULT_DIR("circos.png"),
        summary=MITOZ_ANNO_RESULT_DIR("summary.txt"),
        genbank=MITOZ_ANNO_RESULT_DIR(f"{{sample}}_{ORGANELLE_DB}.get_organelle.fasta_mitoscaf.fa.gbf"),
    params:
        outdir=MITOZ_ANNO_DIR(),
        tool_prefix=_shell_prefix('mitoz'),
        cleanup=CLEANUP,
    conda: "envs/mitoz.yaml"
    message: "MitozAnnotate for sample: {wildcards.sample}"
    log: LOG_DIR.joinpath('{sample}', 'mitoz_annotate.log')
    benchmark: BENCHMARK_DIR.joinpath('{sample}', 'mitoz_annotate.stat')
    shell:
        """
        (
        mkdir -p {params.outdir}
        cd {params.outdir}

        {params.tool_prefix}mitoz annotate \\
            --outprefix {wildcards.sample} \\
            --thread_number {MITOZ_THREAD_NUMBER} \\
            --fastafiles {input.organelle_fasta_new} \\
            --fq1 {input.fq1} \\
            --fq2 {input.fq2} \\
            --species_name "{wildcards.sample}" \\
            --genetic_code {GENETIC_CODE} \\
            --clade {MITOZ_CLADE}

        if [ "{params.cleanup}" = "True" ]; then
            rm -f {params.outdir}/tmp_*
        fi
        ) 2>{log}.err 1>{log}
        """

rule GenerateReport:
    """
    Generate a bilingual (English + Chinese) Materials & Methods section
    for SCI papers, summarising tools, versions, and parameters used.
    Output: {RESULT_DIR}/{sample}/materials_and_methods.md
    """
    input:
        circos=MITOZ_ANNO_RESULT_DIR("circos.png"),
        summary=MITOZ_ANNO_RESULT_DIR("summary.txt"),
    output:
        report=mm_report(),
    message: "GenerateReport for sample: {wildcards.sample}"
    run:
        from FastMitoAssembler.report import generate_mm_report
        generate_mm_report(
            output_path=output.report,
            sample=wildcards.sample,
            cfg=config,
            tool_envs=_TOOL_ENVS,
        )
