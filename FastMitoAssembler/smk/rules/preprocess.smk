if FASTP_ENABLED:
    rule fastp_adapter_trim:
        """
        Optional upstream adapter-only trim via fastp.

        `-Q` disables quality filtering and `-L` disables length filtering -
        adapter removal only, per NOVOPlasty / GetOrganelle author guidance
        against Phred quality trimming.
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
            {params.tool_prefix}fastp --detect_adapter_for_pe -Q -L \
                -i {input.fq1} -I {input.fq2} \
                -o {output.fq1} -O {output.fq2} \
                {params.extra} \
                -j {log}.json -h {log}.html
            ) 2>{log}.err 1>{log}
            """
