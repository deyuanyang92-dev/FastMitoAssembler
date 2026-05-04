"""
FastMitoAssembler v002 workflow entry point.

This Snakefile intentionally keeps the legacy `all` target as the first rule
while loading tool-specific rules from reusable modules.
"""

include: "rules/common.smk"


rule all:
    """
    Legacy full workflow: MEANGS -> NOVOPlasty -> GetOrganelle -> MitoZ -> report.
    """
    message: "Congratulations, the pipeline process is complete!"
    input:
        expand(MITOZ_ANNO_RESULT_DIR("summary.txt"), sample=SAMPLES),
        expand(mm_report(), sample=SAMPLES),
    run:
        print('ok')


include: "rules/preprocess.smk"
include: "rules/meangs.smk"
include: "rules/novoplasty.smk"
include: "rules/getorganelle.smk"
include: "rules/mitoz.smk"
include: "rules/report.smk"
include: "rules/summary.smk"
include: "rules/spades.smk"
include: "rules/busco.smk"
include: "rules/multiqc.smk"


rule meangs_all:
    input:
        expand(seed_fas, sample=SAMPLES),


rule novoplasty_all:
    input:
        expand(novoplasty_fasta, sample=SAMPLES),


rule getorganelle_all:
    input:
        expand(organelle_fasta_new, sample=SAMPLES),


rule mitoz_all:
    input:
        expand(MITOZ_ANNO_RESULT_DIR("summary.txt"), sample=SAMPLES),


rule mg_nov_all:
    input:
        expand(novoplasty_fasta, sample=SAMPLES),


rule mg_get_all:
    input:
        expand(organelle_fasta_new, sample=SAMPLES),


rule mg_nov_get_all:
    input:
        expand(organelle_fasta_new, sample=SAMPLES),


rule summary_all:
    input:
        summary_all_fasta,
        summary_report_tsv,


rule fastp_all:
    """Aggregate target for all fastp runs."""
    input:
        expand(FASTP_FQ1, sample=SAMPLES) if FASTP_ENABLED else [],


rule spades_all:
    """Aggregate target for all SPAdes runs."""
    input:
        expand(SPADES_DIR.joinpath('.done'), sample=SAMPLES) if SPADES_ENABLED else [],


rule busco_all:
    """Aggregate target for all BUSCO evaluations."""
    input:
        expand(BUSCO_DIR.joinpath('.done'), sample=SAMPLES) if BUSCO_ENABLED else [],


rule multiqc_all:
    """Aggregate target for MultiQC report."""
    input:
        MULTIQC_DIR.joinpath('.done') if MULTIQC_ENABLED else [],


rule fsb_all:
    """
    Complete pipeline: fastp -> MultiQC -> SPAdes -> BUSCO.

    One-click assembly evaluation workflow.
    """
    message: "FSB pipeline complete: fastp -> MultiQC -> SPAdes -> BUSCO"
    input:
        # fastp outputs
        expand(FASTP_FQ1, sample=SAMPLES) if FASTP_ENABLED else [],
        # MultiQC report (after fastp)
        MULTIQC_DIR.joinpath('.done') if MULTIQC_ENABLED else [],
        # SPAdes outputs
        expand(SPADES_DIR.joinpath('.done'), sample=SAMPLES) if SPADES_ENABLED else [],
        # BUSCO outputs
        expand(BUSCO_DIR.joinpath('.done'), sample=SAMPLES) if BUSCO_ENABLED else [],
    run:
        print('FSB pipeline complete!')
