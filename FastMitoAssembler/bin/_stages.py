import click

from FastMitoAssembler.bin._workflow import common_workflow_options, run_workflow


def _run_stage(kwargs, target, overrides=None):
    return run_workflow(kwargs, target=target, config_overrides=overrides or {})


@click.command(name='meangs', help=click.style('run MEANGS only', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
def meangs(**kwargs):
    _run_stage(kwargs, 'meangs_all')


@click.command(name='novoplasty', help=click.style('run NOVOPlasty in batch', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
def novoplasty(**kwargs):
    _run_stage(kwargs, 'novoplasty_all', {'novoplasty_seed_source': 'user'})


@click.command(name='getorganelle', help=click.style('run GetOrganelle in batch', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
def getorganelle(**kwargs):
    _run_stage(kwargs, 'getorganelle_all', {'getorganelle_seed_source': 'none'})


@click.command(name='mitoz', help=click.style('run MitoZ annotation in batch', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
def mitoz(**kwargs):
    _run_stage(kwargs, 'mitoz_all')


@click.command(name='mg-nov', help=click.style('run MEANGS -> NOVOPlasty', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
def mg_nov(**kwargs):
    _run_stage(kwargs, 'mg_nov_all', {'novoplasty_seed_source': 'meangs'})


@click.command(name='mg-get', help=click.style('run MEANGS -> GetOrganelle', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
def mg_get(**kwargs):
    _run_stage(kwargs, 'mg_get_all', {'getorganelle_seed_source': 'meangs'})


@click.command(name='mg-nov-get', help=click.style('run MEANGS -> NOVOPlasty -> GetOrganelle', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
def mg_nov_get(**kwargs):
    _run_stage(
        kwargs,
        'mg_nov_get_all',
        {'novoplasty_seed_source': 'meangs', 'getorganelle_seed_source': 'novoplasty'},
    )


@click.command(name='summary', help=click.style('collect summary FASTA/TSV outputs', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
def summary(**kwargs):
    _run_stage(kwargs, 'summary_all')


STAGE_COMMANDS = [
    meangs,
    novoplasty,
    getorganelle,
    mitoz,
    mg_nov,
    mg_get,
    mg_nov_get,
    summary,
]
