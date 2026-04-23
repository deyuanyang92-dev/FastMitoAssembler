rule NOVOPlasty_config:
    """
    Generate the configuration file for NOVOPlasty.
    """
    input:
        fq1=FQ1,
        fq2=FQ2,
        seed_fas=_novoplasty_seed_input,
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
    conda: "../envs/novoplasty.yaml"
    message: "NOVOPlasty for sample: {wildcards.sample}"
    log: LOG_DIR.joinpath('{sample}', 'novoplasty.log')
    benchmark: BENCHMARK_DIR.joinpath('{sample}', 'novoplasty.stat')
    shell:
        """
        (
        cd {params.output_path}

        {params.tool_prefix}{params.novoplasty_cmd} -c {input.novoplasty_config}

        seqkit replace -w0 \
            -p "\+.+" -r "" \
            -o {output.novoplasty_fasta} \
            *{wildcards.sample}.fasta

        if [ "{params.cleanup}" = "True" ]; then
            rm -f contigs_tmp_{wildcards.sample}.txt \
                  log_{wildcards.sample}.txt
        fi
        ) 2>{log}.err 1>{log}
        """
