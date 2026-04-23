rule GenerateReport:
    """
    Generate a bilingual (English + Chinese) Materials & Methods section.
    """
    input:
        circos=MITOZ_ANNO_RESULT_DIR("circos.png"),
        summary=MITOZ_ANNO_RESULT_DIR("summary.txt"),
    output:
        report=mm_report(),
    message: "GenerateReport for sample: {wildcards.sample}"
    run:
        from FastMitoAssembler.report import generate_mm_report
        generate_mm_report(
            output_path=output.report,
            sample=wildcards.sample,
            cfg=config,
            tool_envs=_TOOL_ENVS,
        )
