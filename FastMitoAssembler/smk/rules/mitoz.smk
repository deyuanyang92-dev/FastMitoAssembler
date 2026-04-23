rule MitozAnnotate:
    """
    Annotate mitochondrial genome using MitoZ.
    """
    input:
        fq1=FQ1,
        fq2=FQ2,
        assembly_fasta=_mitoz_assembly_input,
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

        {params.tool_prefix}mitoz annotate \
            --outprefix {wildcards.sample} \
            --thread_number {MITOZ_THREAD_NUMBER} \
            --fastafiles {input.assembly_fasta} \
            --fq1 {input.fq1} \
            --fq2 {input.fq2} \
            --species_name "{wildcards.sample}" \
            --genetic_code {GENETIC_CODE} \
            --clade {MITOZ_CLADE}

        if [ "{params.cleanup}" = "True" ]; then
            rm -f {params.outdir}/tmp_*
        fi
        ) 2>{log}.err 1>{log}
        """
