import click

from FastMitoAssembler.bin._workflow import (
    _detect_samples,
    common_workflow_options,
    run_workflow,
)


@click.command(help=click.style('run the workflow', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
def run(**kwargs):
    run_workflow(kwargs)
