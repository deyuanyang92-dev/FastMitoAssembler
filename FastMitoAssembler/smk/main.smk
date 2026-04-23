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
        expand(MITOZ_ANNO_RESULT_DIR("circos.png"), sample=SAMPLES),
        expand(MITOZ_ANNO_RESULT_DIR("summary.txt"), sample=SAMPLES),
        expand(MITOZ_ANNO_RESULT_DIR(f"{{sample}}_{ORGANELLE_DB}.get_organelle.fasta_mitoscaf.fa.gbf"), sample=SAMPLES),
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
        expand(MITOZ_ANNO_RESULT_DIR("circos.png"), sample=SAMPLES),
        expand(MITOZ_ANNO_RESULT_DIR("summary.txt"), sample=SAMPLES),
        expand(MITOZ_ANNO_RESULT_DIR(f"{{sample}}_{ORGANELLE_DB}.get_organelle.fasta_mitoscaf.fa.gbf"), sample=SAMPLES),


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
