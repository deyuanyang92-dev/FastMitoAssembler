# BUSCO Snakemake Rules
#
# 评估模式:
#   - genome: 基因组评估
#   - transcriptome: 转录组评估
#   - proteins: 蛋白质评估

import os

# BUSCO 配置
BUSCO_CFG = config.get('busco') or {}
BUSCO_ENABLED = bool(BUSCO_CFG.get('enabled', False))
BUSCO_LINEAGE = BUSCO_CFG.get('lineage', 'metazoa_odb10')
BUSCO_MODE = BUSCO_CFG.get('mode', 'genome')
BUSCO_THREADS = BUSCO_CFG.get('threads', 12)
BUSCO_OFFLINE = BUSCO_CFG.get('offline', False)
BUSCO_DOWNLOAD_PATH = BUSCO_CFG.get('download_path', '')
BUSCO_EXTRA = BUSCO_CFG.get('extra_args', '')
BUSCO_FORCE = BUSCO_CFG.get('force', False)


# BUSCO 预设模式
BUSCO_MODE_PRESETS = {
    "genome": {
        "description": "Genome assembly evaluation",
        "flag": "-m genome",
    },
    "transcriptome": {
        "description": "Transcriptome assembly evaluation",
        "flag": "-m transcriptome",
    },
    "proteins": {
        "description": "Protein set evaluation",
        "flag": "-m proteins",
    },
}


def _busco_mode_flag(mode):
    """Get mode flag for BUSCO."""
    preset = BUSCO_MODE_PRESETS.get(mode, BUSCO_MODE_PRESETS["genome"])
    return preset["flag"]


# 目录和路径定义
BUSCO_DIR = RESULT_DIR.joinpath('{sample}', 'busco')
BUSCO_SUMMARY_GENERIC = BUSCO_DIR.joinpath('short_summary.txt')
BUSCO_SUMMARY_SPECIFIC = BUSCO_DIR.joinpath('short_summary.specific.{lineage}.{sample}.txt')


def _busco_input_fasta(wildcards):
    """Determine input FASTA for BUSCO evaluation."""
    # 优先使用 SPAdes contigs
    spades_contigs = RESULT_DIR.joinpath(wildcards.sample, 'spades', 'contigs.fasta')
    if spades_contigs.exists():
        return str(spades_contigs)

    # 其次使用 SPAdes scaffolds
    spades_scaffolds = RESULT_DIR.joinpath(wildcards.sample, 'spades', 'scaffolds.fasta')
    if spades_scaffolds.exists():
        return str(spades_scaffolds)

    # 默认返回 contigs 路径 (Snakemake 会检查是否存在)
    return str(spades_contigs)


if BUSCO_ENABLED:
    rule busco:
        """
        BUSCO evaluation for assembly quality assessment.

        Modes:
          - genome: Genome assembly
          - transcriptome: Transcriptome assembly
          - proteins: Protein set
        """
        input:
            fasta=_busco_input_fasta,
        output:
            summary=BUSCO_SUMMARY_GENERIC,
            done=BUSCO_DIR.joinpath('.done'),
        params:
            outdir=BUSCO_DIR,
            lineage=BUSCO_LINEAGE,
            mode=BUSCO_MODE,
            mode_flag=_busco_mode_flag(BUSCO_MODE),
            tool_prefix=_shell_prefix('busco'),
            busco_cmd=_tool_cmd('busco', 'busco'),
            threads=BUSCO_THREADS,
            offline=BUSCO_OFFLINE,
            download_path=BUSCO_DOWNLOAD_PATH,
            force=BUSCO_FORCE,
            extra=BUSCO_EXTRA,
        conda: "../envs/busco.yaml"
        message: "BUSCO ({params.mode}) for sample: {wildcards.sample}"
        log: LOG_DIR.joinpath('{sample}', 'busco.log')
        benchmark: BENCHMARK_DIR.joinpath('{sample}', 'busco.stat')
        threads: BUSCO_THREADS
        shell:
            """
            (
            mkdir -p {params.outdir}

            # Build BUSCO command
            BUSCO_CMD="{params.tool_prefix}{params.busco_cmd}"
            BUSCO_CMD="$BUSCO_CMD -i {input.fasta}"
            BUSCO_CMD="$BUSCO_CMD -o {wildcards.sample}"
            BUSCO_CMD="$BUSCO_CMD --out_path {params.outdir.parent}"
            BUSCO_CMD="$BUSCO_CMD -l {params.lineage}"
            BUSCO_CMD="$BUSCO_CMD {params.mode_flag}"
            BUSCO_CMD="$BUSCO_CMD -c {params.threads}"

            # Offline mode
            if [ "{params.offline}" = "True" ]; then
                BUSCO_CMD="$BUSCO_CMD --offline"
                if [ -n "{params.download_path}" ]; then
                    BUSCO_CMD="$BUSCO_CMD --download_path {params.download_path}"
                fi
            fi

            # Force overwrite
            if [ "{params.force}" = "True" ]; then
                BUSCO_CMD="$BUSCO_CMD --force"
            fi

            # Extra arguments
            if [ -n "{params.extra}" ]; then
                BUSCO_CMD="$BUSCO_CMD {params.extra}"
            fi

            # Run BUSCO
            eval $BUSCO_CMD
            ) 2>{log}.err 1>{log}

            # Mark completion
            touch {output.done}
            """

    rule busco_all:
        """Aggregate target for all BUSCO evaluations."""
        input: expand(BUSCO_DIR.joinpath('.done'), sample=SAMPLES)
