# MultiQC Snakemake Rules
#
# 汇总所有 QC 结果:
#   - fastp 质控报告
#   - BUSCO 评估结果
#   - SPAdes 组装统计

import os

# MultiQC 配置
MULTIQC_CFG = config.get('multiqc') or {}
MULTIQC_ENABLED = bool(MULTIQC_CFG.get('enabled', False))
MULTIQC_FORCE = MULTIQC_CFG.get('force', False)
MULTIQC_EXTRA = MULTIQC_CFG.get('extra_args', '')


# 目录和路径定义
MULTIQC_DIR = RESULT_DIR.joinpath('multiqc')
MULTIQC_REPORT = MULTIQC_DIR.joinpath('multiqc_report.html')
MULTIQC_DATA_DIR = MULTIQC_DIR.joinpath('multiqc_data')


if MULTIQC_ENABLED:
    rule multiqc:
        """
        MultiQC summary report for all QC results.

        Aggregates:
          - fastp quality control
          - BUSCO evaluation
          - SPAdes assembly stats
        """
        input:
            # Collect all QC outputs
            fastp_done=expand(FASTP_DIR.joinpath('fastp.json'), sample=SAMPLES) if FASTP_ENABLED else [],
            busco_done=expand(BUSCO_DIR.joinpath('.done'), sample=SAMPLES) if BUSCO_ENABLED else [],
            spades_done=expand(SPADES_DIR.joinpath('.done'), sample=SAMPLES) if SPADES_ENABLED else [],
        output:
            report=MULTIQC_REPORT,
            done=MULTIQC_DIR.joinpath('.done'),
        params:
            outdir=MULTIQC_DIR,
            tool_prefix=_shell_prefix('multiqc'),
            multiqc_cmd=_tool_cmd('multiqc', 'multiqc'),
            force=MULTIQC_FORCE,
            extra=MULTIQC_EXTRA,
        conda: "../envs/multiqc.yaml"
        message: "MultiQC summary report"
        log: LOG_DIR.joinpath('multiqc.log')
        benchmark: BENCHMARK_DIR.joinpath('multiqc.stat')
        shell:
            """
            (
            mkdir -p {params.outdir}

            # Build MultiQC command
            MULTIQC_CMD="{params.tool_prefix}{params.multiqc_cmd}"
            MULTIQC_CMD="$MULTIQC_CMD {RESULT_DIR}"
            MULTIQC_CMD="$MULTIQC_CMD -o {params.outdir}"

            # Force overwrite
            if [ "{params.force}" = "True" ]; then
                MULTIQC_CMD="$MULTIQC_CMD -f"
            fi

            # Extra arguments
            if [ -n "{params.extra}" ]; then
                MULTIQC_CMD="$MULTIQC_CMD {params.extra}"
            fi

            # Run MultiQC
            eval $MULTIQC_CMD
            ) 2>{log}.err 1>{log}

            # Mark completion
            touch {output.done}
            """

    rule multiqc_all:
        """Aggregate target for MultiQC report."""
        input: MULTIQC_DIR.joinpath('.done')
