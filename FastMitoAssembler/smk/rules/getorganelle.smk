rule GetOrganelle:
    """
    Assemble organelle/nr targets using GetOrganelle.
    """
    input:
        fq1=FQ1,
        fq2=FQ2,
        seed=_getorganelle_seed_input,
    output:
        organelle_fasta_new=organelle_fasta_new,
    params:
        output_path=ORGANELLE_DIR(),
        output_path_temp=ORGANELLE_DIR("organelle"),
        tool_prefix=_shell_prefix('getorganelle'),
        go_flags=GETORGANELLE_FLAGS,
        seed_arg=lambda wildcards, input: f"-s {input.seed}" if input.seed else "",
        subsample_reads=SUBSAMPLE_READS,
        cleanup=CLEANUP,
    conda: "../envs/getorganelle.yaml"
    message: "GetOrganelle for sample: {wildcards.sample}"
    log: LOG_DIR.joinpath('{sample}', 'get_organelle.log')
    benchmark: BENCHMARK_DIR.joinpath('{sample}', 'get_organelle.stat')
    shell:
        """
        (
        mkdir -p {params.output_path}
        cd {params.output_path}

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

        {params.tool_prefix}get_organelle_from_reads.py \
            --continue \
            -1 $go_fq1 \
            -2 $go_fq2 \
            -F {ORGANELLE_DB} \
            -o {params.output_path_temp} \
            {params.seed_arg} \
            {params.go_flags}

        seqkit replace -w0 \
            -p ".*(circular).*" -r "{wildcards.sample} topology=circular" \
            organelle/*fasta |
        seqkit replace -w0 \
            -p "^scaffold.*" -r "{wildcards.sample} topology=linear" \
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
