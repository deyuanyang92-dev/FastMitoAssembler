rule PrepareUserSeed:
    """
    Normalize user-provided seed FASTA/GenBank into one sample-specific FASTA.
    """
    input:
        seed=str(SEED_INPUT),
    output:
        seed=user_seed_fas,
    params:
        seed_mode=SEED_MODE,
        seed_missing=SEED_MISSING,
    message: "Prepare user seed for sample: {wildcards.sample}"
    run:
        from FastMitoAssembler.bin._seed import prepare_seed
        prepare_seed(
            input_path=input.seed,
            output_path=output.seed,
            sample=wildcards.sample,
            seed_mode=params.seed_mode,
            missing=params.seed_missing,
        )

rule MEANGS:
    """
    Detect and retrieve the longest mitochondrial sequence using MEANGS.
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
        meangs_cmd=_tool_cmd('meangs', 'meangs.py'),
        meangs_thread=MEANGS_THREAD,
        meangs_reads=MEANGS_READS,
        meangs_deepin=MEANGS_DEEPIN,
        meangs_species_class=MEANGS_SPECIES_CLASS,
        meangs_quality=MEANGS_QUALITY,
        meangs_extra_flags=MEANGS_EXTRA_FLAGS,
        deepin_flag='--deepin' if MEANGS_DEEPIN else '',
        insert_size=INSERT_SIZE,
        cleanup=CLEANUP,
    conda: "../envs/meangs.yaml"
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
            {params.tool_prefix}{params.meangs_cmd} \
                --silence \
                -1 {input.fq1} \
                -2 {input.fq2} \
                -o {wildcards.sample} \
                -t {params.meangs_thread} \
                -n {params.meangs_reads} \
                -i {params.insert_size} \
                -q {params.meangs_quality} \
                --species_class {params.meangs_species_class} \
                {params.deepin_flag} \
                {params.meangs_extra_flags}

            if [ -f {wildcards.sample}/{wildcards.sample}_deep_detected_mito.fas ]; then
                meangs_out={wildcards.sample}/{wildcards.sample}_deep_detected_mito.fas
            elif [ -f {wildcards.sample}/{wildcards.sample}_detected_mito.fas ]; then
                meangs_out={wildcards.sample}/{wildcards.sample}_detected_mito.fas
            else
                echo "MEANGS output not found: expected {wildcards.sample}/{wildcards.sample}_deep_detected_mito.fas or {wildcards.sample}/{wildcards.sample}_detected_mito.fas" >&2
                exit 1
            fi
            echo "MEANGS seed source: $meangs_out"
            seqkit head -n1 -w0 -o {output.seed_fas} $meangs_out

            if [ "{params.cleanup}" = "True" ]; then
                rm -rf {wildcards.sample}/
            fi
        fi) 2>{log}.err 1>{log}
        """
