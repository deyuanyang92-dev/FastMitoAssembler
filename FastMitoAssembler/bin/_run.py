import os
import json
import glob as glob_mod
from pathlib import Path

import click
import snakemake

from FastMitoAssembler import (
    MAIN_SMK,
    DEFAULT_CONFIG_FILE,
    DEFAULT_CONFIG,
    DEFAULT_OPTION_FILE,
    DEFAULT_OPTIONS,
    util,
)
from FastMitoAssembler.bin._check import load_tool_envs, TOOL_PROBES, _run_probe

def _detect_samples(reads_dir, suffix_fq):
    """Detect sample names from reads_dir using paired suffix patterns.

    suffix_fq format: 'R1_suffix,R2_suffix' pairs separated by ';'
    e.g. '_1.clean.fq.gz,_2.clean.fq.gz;_R1.fastq.gz,_R2.fastq.gz'
    Only the R1 suffix (first of each pair) is used for detection.
    """
    samples = []
    for pair in suffix_fq.split(';'):
        pair = pair.strip()
        if not pair:
            continue
        r1_suffix = pair.split(',')[0].strip()
        for path in sorted(glob_mod.glob(os.path.join(reads_dir, '**', f'*{r1_suffix}'), recursive=True)):
            name = os.path.basename(path)
            if name.endswith(r1_suffix):
                samples.append(name[:-len(r1_suffix)])
    return list(dict.fromkeys(samples))


@click.command(help=click.style('run the workflow', fg='cyan', bold=True), no_args_is_help=True)
# custom configs
@click.option('-r', '--reads_dir', help='the root directory of reads')
@click.option('-o', '--result_dir', help='the directory of result', default='result', show_default=True)
@click.option('-d', '--organelle_database', help='the database for GetOrganelle', default=DEFAULT_CONFIG['organelle_database'], show_default=True)
@click.option('-s', '--samples', help='the sample name', multiple=True)
@click.option('--fq_path_pattern', help='the path pattern of fastq file', default='{sample}/{sample}_1.clean.fq.gz', show_default=True)

# optional configs
@click.option('--genetic_code', help='the genetic code table', type=int, default=DEFAULT_CONFIG['genetic_code'], show_default=True)
@click.option('--genome_min_size', help='the min size of genome', type=int, default=DEFAULT_CONFIG['genome_min_size'], show_default=True)
@click.option('--genome_max_size', help='the max size of genome', type=int, default=DEFAULT_CONFIG['genome_max_size'], show_default=True)
@click.option('--insert_size', help='the in', type=int, default=DEFAULT_CONFIG['insert_size'], show_default=True)
@click.option('--kmer_size', help='the K-mer size used in NOVOPlasty assembly', type=int, default=DEFAULT_CONFIG['kmer_size'], show_default=True)
@click.option('--read_length', help='the read length of Illumina short reads', type=int, default=DEFAULT_CONFIG['read_length'], show_default=True)
@click.option('--max_mem_gb', help='the limit of RAM usage for NOVOPlasty (unit: GB)', type=int, default=DEFAULT_CONFIG['max_mem_gb'], show_default=True)

@click.option('--suffix_fq',
              help='paired fastq suffixes for auto-detecting samples (R1,R2 per pair; pairs separated by ";"). '
                   'Example: "_1.clean.fq.gz,_2.clean.fq.gz;_R1.fastq.gz,_R2.fastq.gz"',
              default='_1.clean.fq.gz,_2.clean.fq.gz',
              show_default=True)
@click.option('--seed_input', help='use a specific seed input, .fasta, or .gb')
@click.option('--genes', help='the specific genes')

# snakefile, configfile and optionfile
@click.option('--snakefile', help='the main snakefile', default=MAIN_SMK, show_default=True)
@click.option('--configfile', help=f'the configfile for snakefile, template: {DEFAULT_CONFIG_FILE}')
@click.option('--optionfile', help=f'the optionfile for snakefile, template: {DEFAULT_OPTION_FILE}')

## snakemke options
@click.option('--cores', help='use at most N CPU cores/jobs in parallel', type=int, default=DEFAULT_OPTIONS['cores'], show_default=True)
@click.option('--dryrun', help='do not execute anything, and display what would be done', is_flag=True)
@click.option('--use-conda/--no-use-conda', default=True, show_default=True,
              help='use conda environments for each rule')
@click.option('--conda-prefix', default=None,
              help='directory to store conda environments (shared across projects)')
@click.option('--keepgoing', is_flag=True,
              help='go on with independent jobs if a job fails')
@click.option('--unlock', is_flag=True,
              help='unlock the working directory if it is locked by a previous run')
def run(**kwargs):

    configs = {}
    arguments = (
        'reads_dir result_dir organelle_database samples '
        'genetic_code genome_min_size genome_max_size insert_size kmer_size '
        'read_length max_mem_gb seed_input genes fq_path_pattern '
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
    # merge global tool_envs with project-level overrides
    configs['tool_envs'] = load_tool_envs(configs.get('tool_envs', {}))

    if not configs['samples'] and configs['reads_dir']:
        detected = _detect_samples(configs['reads_dir'], kwargs['suffix_fq'])
        if detected:
            click.secho(f'>>> Auto-detected samples: {detected}', fg='cyan', err=True)
            configs['samples'] = detected

    click.secho('>>> Configs:\n' + json.dumps(configs, indent=2, default=str), fg='green', err=True)

    if not (configs['reads_dir'] and configs['samples']):
        click.secho(f'reads_dir and samples must supply!', err=True, fg='red')
        exit(1)

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
        'use_conda': kwargs['use_conda'],
        'keepgoing': kwargs['keepgoing'],
        'unlock': kwargs['unlock'],
    }
    if kwargs['conda_prefix']:
        options['conda_prefix'] = kwargs['conda_prefix']
    if kwargs['optionfile'] and os.path.isfile(kwargs['optionfile']):
        click.secho('>>> reading options from file: {optionfile}'.format(**kwargs), fg='green', err=True)
        data = util.read_yaml(kwargs['optionfile'])
        for key, value in data.items():
            if value != '':
                options[key] = value

    click.secho('>>> Options:\n' + json.dumps(options, indent=2), fg='green', err=True)

    # validate any configured bin_dir entries before starting the workflow
    probe_map = {tool: cmd for tool, cmd in TOOL_PROBES}
    for tool, cfg in (configs.get('tool_envs') or {}).items():
        if not isinstance(cfg, dict):
            continue
        bin_dir = (cfg.get('bin_dir') or '').strip()
        if bin_dir and tool in probe_map:
            ok = _run_probe(probe_map[tool], f'PATH="{bin_dir}:$PATH" ')
            if not ok:
                click.secho(
                    f'Error: bin_dir for {tool} does not work: {bin_dir}\n'
                    f'Please check the path or run `fma check` for diagnosis.',
                    fg='red', err=True)
                exit(1)

    snakemake.snakemake(kwargs['snakefile'], config=configs, **options)
