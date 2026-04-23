rule SummaryMEANGS:
    input:
        fasta=seed_fas,
    output:
        fasta=SUMMARY_FASTA("meangs"),
    message: "Collect MEANGS summary for sample: {wildcards.sample}"
    run:
        from FastMitoAssembler.bin._summary import collect_fasta
        collect_fasta(
            input_path=input.fasta,
            output_path=output.fasta,
            sample=wildcards.sample,
            software='meangs',
            pipeline='meangs',
            locus='mt',
        )

rule SummaryNOVOPlasty:
    input:
        fasta=novoplasty_fasta,
    output:
        fasta=SUMMARY_FASTA("novoplasty"),
    message: "Collect NOVOPlasty summary for sample: {wildcards.sample}"
    run:
        from FastMitoAssembler.bin._summary import collect_fasta
        collect_fasta(
            input_path=input.fasta,
            output_path=output.fasta,
            sample=wildcards.sample,
            software='novoplasty',
            pipeline='novoplasty',
            locus='mt',
        )

rule SummaryGetOrganelle:
    input:
        fasta=organelle_fasta_new,
    output:
        fasta=SUMMARY_FASTA("getorganelle"),
    message: "Collect GetOrganelle summary for sample: {wildcards.sample}"
    run:
        from FastMitoAssembler.bin._summary import collect_fasta
        collect_fasta(
            input_path=input.fasta,
            output_path=output.fasta,
            sample=wildcards.sample,
            software='getorganelle',
            pipeline='getorganelle',
            locus='mt',
        )

rule SummaryMGNOV:
    input:
        fasta=novoplasty_fasta,
    output:
        fasta=SUMMARY_FASTA("mg-nov"),
    message: "Collect MEANGS-NOVOPlasty summary for sample: {wildcards.sample}"
    run:
        from FastMitoAssembler.bin._summary import collect_fasta
        collect_fasta(
            input_path=input.fasta,
            output_path=output.fasta,
            sample=wildcards.sample,
            software='novoplasty',
            pipeline='mg-nov',
            locus='mt',
        )

rule SummaryMGGET:
    input:
        fasta=organelle_fasta_new,
    output:
        fasta=SUMMARY_FASTA("mg-get"),
    message: "Collect MEANGS-GetOrganelle summary for sample: {wildcards.sample}"
    run:
        from FastMitoAssembler.bin._summary import collect_fasta
        collect_fasta(
            input_path=input.fasta,
            output_path=output.fasta,
            sample=wildcards.sample,
            software='getorganelle',
            pipeline='mg-get',
            locus='mt',
        )

rule SummaryMGNOVGET:
    input:
        fasta=organelle_fasta_new,
    output:
        fasta=SUMMARY_FASTA("mg-nov-get"),
    message: "Collect MEANGS-NOVOPlasty-GetOrganelle summary for sample: {wildcards.sample}"
    run:
        from FastMitoAssembler.bin._summary import collect_fasta
        collect_fasta(
            input_path=input.fasta,
            output_path=output.fasta,
            sample=wildcards.sample,
            software='getorganelle',
            pipeline='mg-nov-get',
            locus='mt',
        )

rule SummaryReport:
    input:
        expand(SUMMARY_FASTA("meangs"), sample=SAMPLES),
        expand(SUMMARY_FASTA("novoplasty"), sample=SAMPLES),
        expand(SUMMARY_FASTA("getorganelle"), sample=SAMPLES),
        expand(SUMMARY_FASTA("mg-nov"), sample=SAMPLES),
        expand(SUMMARY_FASTA("mg-get"), sample=SAMPLES),
        expand(SUMMARY_FASTA("mg-nov-get"), sample=SAMPLES),
    output:
        fasta=summary_all_fasta,
        report=summary_report_tsv,
    message: "Build combined summary FASTA and TSV"
    run:
        from FastMitoAssembler.bin._summary import combine_summary
        combine_summary(input, output.fasta, output.report)
