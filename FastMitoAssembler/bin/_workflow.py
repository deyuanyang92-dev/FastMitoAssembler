import glob as glob_mod
import json
import os
from pathlib import Path

import click
import snakemake

from FastMitoAssembler import (
    MAIN_SMK,
    DEFAULT_CONFIG,
    DEFAULT_OPTIONS,
    util,
)
from FastMitoAssembler.bin._check import load_tool_envs, TOOL_PROBES, _run_probe


CONFIG_ARGUMENTS = (
    'reads_dir result_dir organelle_database samples fq1 fq2 sample_name '
    'genetic_code novoplasty_genome_min_size novoplasty_genome_max_size insert_size novoplasty_kmer_size '
    'read_length novoplasty_max_mem_gb seed_input seed_mode seed_missing genes fq_path_pattern fq2_path_pattern fastq_pos '
    'assembly_fasta mitoz_input_source getorganelle_seed_source novoplasty_seed_source '
    'meangs_path '
).strip().split()


def _parse_suffix_pair(pair):
    pair = (pair or '').strip()
    if not pair:
        return None
    if ',' in pair:
        r1_suffix, r2_suffix = pair.split(',', 1)
        return r1_suffix.strip(), r2_suffix.strip()
    return f'_1{pair}', f'_2{pair}'


def _iter_suffix_pairs(suffix_fq):
    for pair in (suffix_fq or '').split(';'):
        parsed = _parse_suffix_pair(pair)
        if parsed:
            yield parsed


def _detect_fastq_pairs(reads_dir, suffix_fq, fastq_pos='recursive'):
    """Detect paired FASTQ files using batch_meangs.py-compatible suffix rules."""
    pairs = {}
    reads_dir = os.path.abspath(reads_dir)
    for r1_suffix, r2_suffix in _iter_suffix_pairs(suffix_fq):
        if fastq_pos == 'flat':
            pattern = os.path.join(reads_dir, f'*{r1_suffix}')
            paths = sorted(glob_mod.glob(pattern))
            sample_from_path = lambda p: os.path.basename(p)[:-len(r1_suffix)]
        elif fastq_pos == 'subdir':
            paths = []
            for subdir in sorted(os.listdir(reads_dir)):
                dir_path = os.path.join(reads_dir, subdir)
                if os.path.isdir(dir_path):
                    paths.extend(sorted(glob_mod.glob(os.path.join(dir_path, f'*{r1_suffix}'))))
            sample_from_path = lambda p: Path(p).parent.name
        else:
            pattern = os.path.join(reads_dir, '**', f'*{r1_suffix}')
            paths = sorted(glob_mod.glob(pattern, recursive=True))
            sample_from_path = lambda p: os.path.basename(p)[:-len(r1_suffix)]

        for fq1 in paths:
            fq2 = fq1[:-len(r1_suffix)] + r2_suffix
            if os.path.isfile(fq2):
                sample = sample_from_path(fq1)
                pairs.setdefault(sample, {'fq1': os.path.abspath(fq1), 'fq2': os.path.abspath(fq2)})
    return pairs


def _detect_samples(reads_dir, suffix_fq, fastq_pos='recursive'):
    """Detect sample names from reads_dir using paired suffix patterns."""
    samples = []
    for r1_suffix, _ in _iter_suffix_pairs(suffix_fq):
        for path in sorted(glob_mod.glob(os.path.join(reads_dir, '**', f'*{r1_suffix}'), recursive=True)):
            name = os.path.basename(path)
            if name.endswith(r1_suffix):
                samples.append(name[:-len(r1_suffix)])
    return list(dict.fromkeys(samples))


def _build_configs(kwargs, overrides=None):
    configs = {}
    for key in CONFIG_ARGUMENTS:
        if key in kwargs:
            configs[key] = kwargs[key]

    if kwargs.get('configfile') and os.path.isfile(kwargs['configfile']):
        click.secho('>>> reading config from file: {configfile}'.format(**kwargs), fg='green', err=True)
        data = util.read_yaml(kwargs['configfile'])
        for key, value in data.items():
            if value != '':
                configs[key] = value

    for key, value in (overrides or {}).items():
        if value is not None:
            configs[key] = value

    configs['tool_envs'] = load_tool_envs(configs.get('tool_envs', {}))
    _apply_tool_aliases(configs)
    return configs


def _normalise_samples(samples):
    if samples in (None, ''):
        return []
    if isinstance(samples, str):
        return [samples] if samples else []
    return [sample for sample in samples if sample]


def _apply_tool_aliases(configs):
    """Map compatibility shortcuts onto the canonical tool_envs structure."""
    meangs_path = configs.get('meangs_path')
    if not meangs_path:
        return configs
    tool_envs = dict(configs.get('tool_envs') or {})
    meangs_cfg = dict(tool_envs.get('meangs') or {})
    meangs_cfg['script_path'] = meangs_path
    tool_envs['meangs'] = meangs_cfg
    configs['tool_envs'] = tool_envs
    return configs


def _configure_direct_fastqs(configs):
    """Support single-sample CLI mode: --fq1 --fq2 --sample_name."""
    fq1 = configs.get('fq1')
    fq2 = configs.get('fq2')
    sample_name = configs.get('sample_name')
    if not any([fq1, fq2, sample_name]):
        configs['samples'] = _normalise_samples(configs.get('samples'))
        return configs
    if not all([fq1, fq2, sample_name]):
        click.secho(
            '--fq1, --fq2 and --sample_name must be supplied together.',
            err=True,
            fg='red',
        )
        raise click.exceptions.Exit(1)

    sample_name = str(sample_name)
    existing_samples = _normalise_samples(configs.get('samples'))
    if existing_samples and existing_samples != [sample_name]:
        click.secho(
            f'--sample_name conflicts with --samples/config samples: {existing_samples}',
            err=True,
            fg='red',
        )
        raise click.exceptions.Exit(1)

    fq1_path = str(Path(fq1).expanduser().resolve())
    fq2_path = str(Path(fq2).expanduser().resolve())
    configs['samples'] = [sample_name]
    configs['sample_fastqs'] = {
        sample_name: {
            'fq1': fq1_path,
            'fq2': fq2_path,
        }
    }
    if not configs.get('reads_dir'):
        configs['reads_dir'] = str(Path(fq1_path).parent)
    return configs


def _auto_detect_samples(configs, kwargs):
    if not configs.get('samples') and configs.get('reads_dir'):
        sample_fastqs = _detect_fastq_pairs(
            configs['reads_dir'],
            configs.get('suffix_fq') or kwargs.get('suffix_fq') or '',
            configs.get('fastq_pos') or kwargs.get('fastq_pos') or 'recursive',
        )
        detected = list(sample_fastqs.keys())
        if not detected:
            detected = _detect_samples(
                configs['reads_dir'],
                configs.get('suffix_fq') or kwargs.get('suffix_fq') or '',
                configs.get('fastq_pos') or kwargs.get('fastq_pos') or 'recursive',
            )
        if detected:
            click.secho(f'>>> Auto-detected samples: {detected}', fg='cyan', err=True)
            configs['samples'] = detected
            if sample_fastqs:
                configs['sample_fastqs'] = sample_fastqs
    return configs


def _validate_inputs(configs):
    configs['samples'] = _normalise_samples(configs.get('samples'))
    if not configs.get('samples'):
        click.secho('samples must supply, or use auto-detection/direct FASTQ options.', err=True, fg='red')
        raise click.exceptions.Exit(1)
    if not configs.get('reads_dir') and not configs.get('sample_fastqs'):
        click.secho('reads_dir must supply unless direct FASTQ paths are provided.', err=True, fg='red')
        raise click.exceptions.Exit(1)

    for sample in configs['samples']:
        fastqs = (configs.get('sample_fastqs') or {}).get(sample)
        if fastqs:
            fq1 = fastqs.get('fq1')
            fq2 = fastqs.get('fq2')
        else:
            fq1_pattern = configs['fq_path_pattern']
            fq2_pattern = configs.get('fq2_path_pattern') or fq1_pattern.replace('_1', '_2', 1).replace('R1', 'R2', 1)
            fq1 = os.path.join(configs['reads_dir'], fq1_pattern).format(sample=sample)
            fq2 = os.path.join(configs['reads_dir'], fq2_pattern).format(sample=sample)
        for fq in (fq1, fq2):
            if not os.path.isfile(fq):
                click.secho(f'reads file not exists, please check: {fq}', err=True, fg='red')
                raise click.exceptions.Exit(1)

    if not all([isinstance(sample, str) for sample in configs['samples']]):
        click.secho('sample name must be a string, please check your input: {samples}'.format(**configs), fg='red')
        raise click.exceptions.Exit(1)


def _build_options(kwargs, target=None):
    options = {
        'cores': kwargs['cores'],
        'dryrun': kwargs['dryrun'],
        'printshellcmds': True,
        'use_conda': kwargs['use_conda'],
        'keepgoing': kwargs['keepgoing'],
        'unlock': kwargs['unlock'],
    }
    if target:
        options['targets'] = [target]
    if kwargs.get('conda_prefix'):
        options['conda_prefix'] = kwargs['conda_prefix']
    if kwargs.get('optionfile') and os.path.isfile(kwargs['optionfile']):
        click.secho('>>> reading options from file: {optionfile}'.format(**kwargs), fg='green', err=True)
        data = util.read_yaml(kwargs['optionfile'])
        for key, value in data.items():
            if value != '':
                options[key] = value
    return options


def _validate_tool_envs(configs):
    probe_map = {tool: cmd for tool, cmd in TOOL_PROBES}
    for tool, cfg in (configs.get('tool_envs') or {}).items():
        if not isinstance(cfg, dict):
            continue
        script_path = (cfg.get('script_path') or '').strip()
        if script_path and not Path(script_path).expanduser().is_file():
            click.secho(
                f'Error: script_path for {tool} does not exist: {script_path}\n'
                f'Please check the path or run `fma check` for diagnosis.',
                fg='red',
                err=True,
            )
            raise click.exceptions.Exit(1)
        bin_dir = (cfg.get('bin_dir') or '').strip()
        if bin_dir and tool in probe_map:
            ok = _run_probe(probe_map[tool], f'PATH="{bin_dir}:$PATH" ')
            if not ok:
                click.secho(
                    f'Error: bin_dir for {tool} does not work: {bin_dir}\n'
                    f'Please check the path or run `fma check` for diagnosis.',
                    fg='red', err=True)
                raise click.exceptions.Exit(1)


def run_workflow(kwargs, target=None, config_overrides=None):
    configs = _build_configs(kwargs, config_overrides)
    configs = _configure_direct_fastqs(configs)
    configs = _auto_detect_samples(configs, kwargs)
    configs['samples'] = _normalise_samples(configs.get('samples'))

    click.secho('>>> Configs:\n' + json.dumps(configs, indent=2, default=str), fg='green', err=True)
    _validate_inputs(configs)

    options = _build_options(kwargs, target)
    click.secho('>>> Options:\n' + json.dumps(options, indent=2), fg='green', err=True)

    _validate_tool_envs(configs)
    return snakemake.snakemake(kwargs.get('snakefile') or MAIN_SMK, config=configs, **options)


def common_workflow_options(func):
    options = [
        click.option('-r', '--reads_dir', help='the root directory of reads'),
        click.option('-o', '--result_dir', help='the directory of result', default='result', show_default=True),
        click.option('-d', '--organelle_database', help='the database for GetOrganelle', default=DEFAULT_CONFIG['organelle_database'], show_default=True),
        click.option('-s', '--samples', help='the sample name', multiple=True),
        click.option('--fq1', help='direct single-sample R1 FASTQ path'),
        click.option('--fq2', help='direct single-sample R2 FASTQ path'),
        click.option('--sample_name', '--sample-name', help='sample name used with --fq1/--fq2'),
        click.option('--fq_path_pattern', help='the path pattern of fastq file', default='{sample}/{sample}_1.clean.fq.gz', show_default=True),
        click.option('--fq2_path_pattern', help='optional explicit R2 path pattern; defaults to deriving R2 from fq_path_pattern'),
        click.option('--meangs_path', '--meangs-path', help='direct path to meangs.py; maps to tool_envs.meangs.script_path'),
        click.option('--genetic_code', help='the genetic code table', type=int, default=DEFAULT_CONFIG['genetic_code'], show_default=True),
        click.option('--novoplasty_genome_min_size', help='NOVOPlasty: min expected genome size (bp)', type=int, default=DEFAULT_CONFIG['novoplasty_genome_min_size'], show_default=True),
        click.option('--novoplasty_genome_max_size', help='NOVOPlasty: max expected genome size (bp)', type=int, default=DEFAULT_CONFIG['novoplasty_genome_max_size'], show_default=True),
        click.option('--insert_size', help='the insert size', type=int, default=DEFAULT_CONFIG['insert_size'], show_default=True),
        click.option('--novoplasty_kmer_size', help='NOVOPlasty: K-mer size for assembly', type=int, default=DEFAULT_CONFIG['novoplasty_kmer_size'], show_default=True),
        click.option('--read_length', help='the read length of Illumina short reads', type=int, default=DEFAULT_CONFIG['read_length'], show_default=True),
        click.option('--novoplasty_max_mem_gb', help='NOVOPlasty: RAM limit (GB)', type=int, default=DEFAULT_CONFIG['novoplasty_max_mem_gb'], show_default=True),
        click.option('--suffix_fq',
                     help='paired fastq suffixes for auto-detecting samples (R1,R2 per pair; pairs separated by ";").',
                     default='_1.clean.fq.gz,_2.clean.fq.gz',
                     show_default=True),
        click.option('--fastq_pos', default='recursive', show_default=True,
                     type=click.Choice(['recursive', 'subdir', 'flat']),
                     help='FASTQ layout used by auto-detection'),
        click.option('--seed_input', help='use a specific seed input, .fasta, or .gb'),
        click.option('--seed_mode', '--seed-mode', default='single', show_default=True,
                     type=click.Choice(['single', 'by-sample']),
                     help='seed interpretation mode'),
        click.option('--seed_missing', '--seed-missing', default='fail', show_default=True,
                     type=click.Choice(['fail', 'skip']),
                     help='behavior when a sample-specific seed is missing'),
        click.option('--genes', help='specific genes forwarded to GetOrganelle when applicable'),
        click.option('--assembly_fasta', '--assembly-fasta', help='external assembly FASTA for MitoZ annotation'),
        click.option('--mitoz_input_source', '--mitoz-input-source', default='auto', show_default=True,
                     type=click.Choice(['auto', 'assembly_fasta', 'summary', 'getorganelle', 'novoplasty']),
                     help='MitoZ annotation input source'),
        click.option('--getorganelle_seed_source', '--getorganelle-seed-source', default='auto', show_default=True,
                     type=click.Choice(['auto', 'none', 'user', 'meangs', 'novoplasty']),
                     help='GetOrganelle seed source'),
        click.option('--novoplasty_seed_source', '--novoplasty-seed-source', default='auto', show_default=True,
                     type=click.Choice(['auto', 'user', 'meangs']),
                     help='NOVOPlasty seed source'),
        click.option('--snakefile', help='the main snakefile', default=MAIN_SMK, show_default=True),
        click.option('--configfile', help='the configfile for snakefile'),
        click.option('--optionfile', help='the optionfile for snakefile'),
        click.option('--cores', help='use at most N CPU cores/jobs in parallel', type=int, default=DEFAULT_OPTIONS['cores'], show_default=True),
        click.option('--dryrun', help='do not execute anything, and display what would be done', is_flag=True),
        click.option('--use-conda/--no-use-conda', default=True, show_default=True,
                     help='use conda environments for each rule'),
        click.option('--conda-prefix', default=None,
                     help='directory to store conda environments (shared across projects)'),
        click.option('--keepgoing', is_flag=True,
                     help='go on with independent jobs if a job fails'),
        click.option('--unlock', is_flag=True,
                     help='unlock the working directory if it is locked by a previous run'),
    ]
    for option in reversed(options):
        func = option(func)
    return func
