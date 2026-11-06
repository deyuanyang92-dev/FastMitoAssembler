import os
import sys
import json
import tempfile
import subprocess

import click
import snakemake

from FastMitoAssembler import (
    MAIN_SMK,
    DEFAULT_CONFIG_FILE,
    DEFAULT_CONFIG,
    DEFAULT_OPTION_FILE,
    DEFAULT_OPTIONS,
    CITATION,
    util,
)

WORKFLOW_OPTIONS = [
    # custom configs
    click.option('-r', '--reads_dir', help='the root directory of reads'),
    click.option('-o', '--result_dir', help='the directory of result', default='result', show_default=True),
    click.option('-d', '--organelle_database', help='the database for GetOrganelle', default=DEFAULT_CONFIG['organelle_database'], show_default=True),
    click.option('-s', '--samples', help='the sample name', multiple=True),
    click.option('--fq_path_pattern', help='the path pattern of fastq file', default='{sample}/{sample}_1.clean.fq.gz', show_default=True),

    # optional configs
    click.option('--genetic_code', help='the genetic code table', type=int, default=DEFAULT_CONFIG['genetic_code'], show_default=True),
    click.option('--genome_min_size', help='the min size of genome', type=int, default=DEFAULT_CONFIG['genome_min_size'], show_default=True),
    click.option('--genome_max_size', help='the max size of genome', type=int, default=DEFAULT_CONFIG['genome_max_size'], show_default=True),
    click.option('--insert_size', help='the in', type=int, default=DEFAULT_CONFIG['insert_size'], show_default=True),
    click.option('--kmer_size', help='the K-mer size used in NOVOPlasty assembly', type=int, default=DEFAULT_CONFIG['kmer_size'], show_default=True),
    click.option('--read_length', help='the read length of Illumina short reads', type=int, default=DEFAULT_CONFIG['read_length'], show_default=True),
    click.option('--max_mem_gb', help='the limit of RAM usage for NOVOPlasty (unit: GB)', type=int, default=DEFAULT_CONFIG['max_mem_gb'], show_default=True),

    click.option('--seed_input', help='use a specific seed input, .fasta, or .gb'),
    click.option('--genes', help='the specific genes'),
    click.option('--fastp', help='remove adapters with fastp before all steps (no quality trimming)', is_flag=True),

    # snakefile, configfile and optionfile
    click.option('--snakefile', help='the main snakefile', default=MAIN_SMK, show_default=True),
    click.option('--configfile', help=f'the configfile for snakefile, template: {DEFAULT_CONFIG_FILE}'),
    click.option('--optionfile', help=f'the optionfile for snakefile, template: {DEFAULT_OPTION_FILE}'),

    ## snakemke options
    click.option('--cores', help='use at most N CPU cores/jobs in parallel', type=int, default=DEFAULT_OPTIONS['cores'], show_default=True),
    click.option('--dryrun', help='do not execute anything, and display what would bedone', is_flag=True),
]


def workflow_options(func):
    for option in reversed(WORKFLOW_OPTIONS):
        func = option(func)
    return func


def _run(kwargs, target=None, overrides=None):

    configs = {}
    arguments = (
        'reads_dir result_dir organelle_database samples '
        'genetic_code genome_min_size genome_max_size insert_size kmer_size '
        'read_length max_mem_gb seed_input genes fq_path_pattern fastp '
    ).strip().split()
    for key in arguments:
        configs[key] = kwargs[key]

    # higher priority
    if kwargs['configfile'] and os.path.isfile(kwargs['configfile']):
        click.secho('>>> reading config from file: {configfile}'.format(**kwargs), fg='green', err=True)
        data = util.read_yaml(kwargs['configfile'])
        for key, value in data.items():
            if value != '':
                configs[key] = value
    configs.update(overrides or {})
    click.secho('>>> Configs:\n' + json.dumps(configs, indent=2), fg='green', err=True)

    # MitoZ with external FASTA: reads are optional
    fasta_pattern = configs.get('fasta_pattern')
    if fasta_pattern:
        if not configs['samples']:
            click.secho(f'samples must supply!', err=True, fg='red')
            exit(1)
        for sample in configs['samples']:
            fasta = fasta_pattern.format(sample=sample)
            if not os.path.isfile(fasta):
                click.secho(f'fasta file not exists, please check: {fasta}', err=True, fg='red')
                exit(1)
    elif not (configs['reads_dir'] and configs['samples']):
        click.secho(f'reads_dir and samples must supply!', err=True, fg='red')
        exit(1)

    if configs['reads_dir']:
        for sample in configs['samples']:
            fq1 = os.path.join(configs['reads_dir'], configs['fq_path_pattern']).format(sample=sample)
            if not os.path.isfile(fq1):
                click.secho(f'reads file not exists, please check: {fq1}', err=True, fg='red')
                exit(1)

    if not all([isinstance(sample, str) for sample in configs['samples']]):
        click.secho('sample name must be a string, please check your input: {samples}'.format(**configs), fg='red')
        exit(1)

    options = {
        'cores': kwargs['cores'],
        'dryrun': kwargs['dryrun'],
        'printshellcmds': True,
    }
    if kwargs['optionfile'] and os.path.isfile(kwargs['optionfile']):
        click.secho('>>> reading options from file: {optionfile}'.format(**kwargs), fg='green', err=True)
        data = util.read_yaml(kwargs['optionfile'])
        for key, value in data.items():
            if value != '':
                options[key] = value

    click.secho('>>> Options:\n' + json.dumps(options, indent=2), fg='green', err=True)

    targets = [target] if target else None
    if hasattr(snakemake, 'snakemake'):
        # snakemake < 8
        ok = snakemake.snakemake(kwargs['snakefile'], config=configs, targets=targets, **options)
    else:
        # snakemake >= 8 removed the Python API, use the command line instead
        ok = _run_snakemake_cli(kwargs['snakefile'], configs, targets, options)

    if ok and not options.get('dryrun'):
        click.secho(f'\nIf you use FastMitoAssembler, please cite:\n{CITATION}', fg='cyan', err=True)
    if not ok:
        exit(1)


def _run_snakemake_cli(snakefile, configs, targets, options):
    with tempfile.NamedTemporaryFile('w', suffix='.yaml', delete=False) as out:
        json.dump(configs, out)  # JSON is valid YAML
    cmd = [sys.executable, '-m', 'snakemake', '-s', str(snakefile), '--configfile', out.name]
    for key, value in options.items():
        if value is True:
            cmd.append(f'--{key}')
        elif value not in (False, None):
            cmd += [f'--{key}', str(value)]
    cmd += targets or []
    click.secho('>>> run command: ' + ' '.join(cmd), fg='green', err=True)
    return subprocess.call(cmd) == 0


@click.command(help=click.style('run the whole workflow: MEANGS -> NOVOPlasty -> GetOrganelle -> MitoZ', fg='cyan', bold=True), no_args_is_help=True)
@workflow_options
def run(**kwargs):
    _run(kwargs)


@click.command(help=click.style('run MEANGS only', fg='cyan', bold=True), no_args_is_help=True)
@workflow_options
def meangs(**kwargs):
    _run(kwargs, 'meangs_all')


@click.command(name='mg-get', help=click.style('run MEANGS -> GetOrganelle', fg='cyan', bold=True), no_args_is_help=True)
@workflow_options
def mg_get(**kwargs):
    _run(kwargs, 'getorganelle_all', {'getorganelle_seed': 'meangs'})


@click.command(name='mg-nov-get', help=click.style('run MEANGS -> NOVOPlasty -> GetOrganelle', fg='cyan', bold=True), no_args_is_help=True)
@workflow_options
def mg_nov_get(**kwargs):
    _run(kwargs, 'getorganelle_all', {'getorganelle_seed': 'novoplasty'})


@click.command(help=click.style('run GetOrganelle in batch (no seed, or --seed_input)', fg='cyan', bold=True), no_args_is_help=True)
@workflow_options
def getorganelle(**kwargs):
    _run(kwargs, 'getorganelle_all', {'getorganelle_seed': 'none'})


@click.command(help=click.style('run MitoZ annotation in batch', fg='cyan', bold=True), no_args_is_help=True)
@workflow_options
@click.option('--fasta_pattern', help='annotate external FASTA files instead of GetOrganelle results, e.g. "/data/{sample}.fasta"; reads are optional')
def mitoz(fasta_pattern, **kwargs):
    _run(kwargs, 'mitoz_all', {'fasta_pattern': fasta_pattern} if fasta_pattern else None)
