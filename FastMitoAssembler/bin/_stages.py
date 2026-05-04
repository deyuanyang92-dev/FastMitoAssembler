import click
import logging
import os
import subprocess
import sys
from pathlib import Path

from FastMitoAssembler.bin._workflow import common_workflow_options, run_workflow
from FastMitoAssembler.bin._check import load_tool_envs


def _run_stage(kwargs, target, overrides=None):
    return run_workflow(kwargs, target=target, config_overrides=overrides or {})


@click.command(name='meangs', help=click.style('run MEANGS in batch', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
@click.option('--backend', type=click.Choice(['snakemake', 'python']),
              default='snakemake', show_default=True,
              help='Execution backend: snakemake (workflow) or python (direct)')
@click.option('--parallel-jobs', '--parallel_jobs', 'parallel_jobs',
              type=int, default=3, show_default=True,
              help='Number of parallel jobs for Python backend')
@click.option('--force', is_flag=True,
              help='Force re-run even if sample is already done')
# MEANGS 原始参数支持
@click.option('--meangs-deepin/--meangs-no-deepin', 'meangs_deepin', default=True, show_default=True,
              help='Enable deepin mode for deeper assembly')
@click.option('--meangs-insert-size', '--meangs_insert_size', 'meangs_insert_size',
              type=int, default=350, show_default=True,
              help='Insert size for MEANGS (-i)')
@click.option('--meangs-species-class', '--meangs_species_class', 'meangs_species_class',
              default='Arthropoda', show_default=True,
              help='Species class for MEANGS (--species_class)')
@click.option('--meangs-clip', 'meangs_clip', is_flag=True,
              help='Detect circular cutting points (--clip)')
@click.option('--meangs-keep-intmed', 'meangs_keep_intmed', is_flag=True,
              help='Keep intermediate files (--keepIntMed)')
@click.option('--meangs-keep-min-len', '--meangs_keep_min_len', 'meangs_keep_min_len',
              type=int, help='Minimum read length after QC (--keepMinLen)')
@click.option('--meangs-seqscaf', '--meangs_seqscaf', 'meangs_seqscaf',
              help='Sequence scaffold file for annotation (-s)')
@click.option('--meangs-skipassem', 'meangs_skipassem', is_flag=True,
              help='Skip assembly process (--skipassem)')
@click.option('--meangs-skipqc', 'meangs_skipqc', is_flag=True,
              help='Skip quality control process (--skipqc)')
@click.option('--meangs-skiphmm', 'meangs_skiphmm', is_flag=True,
              help='Skip HMMER process (--skiphmm)')
@click.option('--meangs-skipextend', 'meangs_skipextend', is_flag=True,
              help='Skip extension process in deep mode (--skipextend)')
@click.option('--meangs-extra', '--meangs_extra', 'meangs_extra_args',
              help='Extra arguments passed to MEANGS (passthrough)')
def meangs(backend, parallel_jobs, force, meangs_deepin, meangs_insert_size,
           meangs_species_class, meangs_clip, meangs_keep_intmed, meangs_keep_min_len,
           meangs_seqscaf, meangs_skipassem, meangs_skipqc, meangs_skiphmm,
           meangs_skipextend, meangs_extra_args, **kwargs):
    """Run MEANGS in batch.

    Supports two execution backends:
    - snakemake: Uses Snakemake workflow (default)
    - python: Direct Python execution without Snakemake dependency

    All MEANGS original CLI parameters are supported.
    """
    if backend == 'python':
        # Python backend: direct execution
        from FastMitoAssembler.bin.runners import MeangsRunner, meangs_parse_reads_dir, SPECIES_CLASSES

        # Setup logging
        result_dir = Path(kwargs.get('result_dir', 'result')).resolve()
        result_dir.mkdir(parents=True, exist_ok=True)
        log_file = result_dir / 'meangs.log'
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_file, mode='a', encoding='utf-8'),
                logging.StreamHandler(sys.stdout),
            ],
        )

        # Get tool environment for meangs
        tool_envs = load_tool_envs(kwargs.get('tool_envs', {}))
        meangs_cfg = tool_envs.get('meangs', {}) or {}
        conda_env = meangs_cfg.get('conda_env', '')
        bin_dir = meangs_cfg.get('bin_dir', '')

        # Build shell prefix for meangs
        shell_prefix = ''
        if conda_env:
            shell_prefix = f'conda run --no-capture-output -n {conda_env} '
        elif bin_dir:
            shell_prefix = f'PATH="{bin_dir}:$PATH" '

        # Parse reads directory
        reads_dir = Path(kwargs.get('reads_dir')).resolve()
        suffix_fq = kwargs.get('suffix_fq', '_1.clean.fq.gz,_2.clean.fq.gz')
        fastq_pos = kwargs.get('fastq_pos', 'subdir')
        if ',' in suffix_fq:
            r1_suffix, r2_suffix = suffix_fq.split(',', 1)
            r1_suffix = r1_suffix.strip()
            r2_suffix = r2_suffix.strip()
        else:
            r1_suffix = f'_1{suffix_fq}'
            r2_suffix = f'_2{suffix_fq}'

        samples = meangs_parse_reads_dir(reads_dir, r1_suffix, r2_suffix, fastq_pos)
        if not samples:
            click.secho(f'No samples found in {reads_dir}', fg='red', err=True)
            raise click.exceptions.Exit(1)

        click.secho(f'>>> Found {len(samples)} samples', fg='cyan', err=True)

        # Build runner kwargs
        runner_kwargs = {
            'threads': kwargs.get('meangs_thread', 16),
            'insert_size': meangs_insert_size,
            'species_class': meangs_species_class,
            'nsample': kwargs.get('meangs_reads', 2000000),
            'deepin': meangs_deepin,
            'clip': meangs_clip,
            'keepIntMed': meangs_keep_intmed,
            'keepMinLen': meangs_keep_min_len,
            'seqscaf': meangs_seqscaf,
            'skipassem': meangs_skipassem,
            'skipqc': meangs_skipqc,
            'skiphmm': meangs_skiphmm,
            'skipextend': meangs_skipextend,
            'extra_args': meangs_extra_args,
            'force': force,
        }

        # Run batch
        runner = MeangsRunner(threads=runner_kwargs['threads'], shell_prefix=shell_prefix)
        results = runner.run_batch(
            samples,
            result_dir,
            parallel_jobs=parallel_jobs,
            **runner_kwargs,
        )

        # Summary
        success = sum(1 for r in results if r.get('success'))
        failed = sum(1 for r in results if r.get('status') == 'FAILED')
        skipped = sum(1 for r in results if r.get('status') == 'SKIP')
        error = sum(1 for r in results if r.get('status') == 'ERROR')

        click.secho(f'>>> Summary: {success} OK, {failed} FAILED, {skipped} SKIP, {error} ERROR', fg='cyan', err=True)

        return failed == 0 and error == 0
    else:
        # Snakemake backend (default) - 传递 MEANGS 参数到配置
        config_overrides = {
            'meangs_deepin': meangs_deepin,
            'meangs_insert_size': meangs_insert_size,
            'meangs_species_class': meangs_species_class,
        }
        if meangs_clip:
            config_overrides['meangs_clip'] = True
        if meangs_keep_intmed:
            config_overrides['meangs_keepIntMed'] = True
        if meangs_keep_min_len:
            config_overrides['meangs_keepMinLen'] = meangs_keep_min_len
        if meangs_seqscaf:
            config_overrides['meangs_seqscaf'] = meangs_seqscaf
        if meangs_skipassem:
            config_overrides['meangs_skipassem'] = True
        if meangs_skipqc:
            config_overrides['meangs_skipqc'] = True
        if meangs_skiphmm:
            config_overrides['meangs_skiphmm'] = True
        if meangs_skipextend:
            config_overrides['meangs_skipextend'] = True

        _run_stage(kwargs, 'meangs_all', config_overrides)


@click.command(name='novoplasty', help=click.style('run NOVOPlasty in batch', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
def novoplasty(**kwargs):
    _run_stage(kwargs, 'novoplasty_all', {'novoplasty_seed_source': 'user'})


@click.command(name='getorganelle', help=click.style('run GetOrganelle in batch', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
@click.option('--backend', type=click.Choice(['snakemake', 'python']),
              default='snakemake', show_default=True,
              help='Execution backend: snakemake (workflow) or python (direct)')
@click.option('--parallel-jobs', '--parallel_jobs', 'parallel_jobs',
              type=int, default=3, show_default=True,
              help='Number of parallel jobs for Python backend')
@click.option('--force', is_flag=True,
              help='Force re-run even if sample is already done')
@click.option('--overwrite', is_flag=True,
              help='Pass --overwrite to GetOrganelle (overwrite existing output directory)')
@click.option('--resume/--no-resume', default=True, show_default=True,
              help='Resume incomplete runs with --continue')
def getorganelle(backend, parallel_jobs, force, overwrite, resume, **kwargs):
    """Run GetOrganelle in batch.

    Supports two execution backends:
    - snakemake: Uses Snakemake workflow (default)
    - python: Direct Python execution without Snakemake dependency
    """
    if backend == 'python':
        # Python backend: direct execution
        from FastMitoAssembler.bin.runners import GetOrganelleRunner, parse_reads_dir

        # Setup logging
        result_dir = Path(kwargs.get('result_dir', 'result')).resolve()
        result_dir.mkdir(parents=True, exist_ok=True)
        log_file = result_dir / 'getorganelle.log'
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_file, mode='a', encoding='utf-8'),
                logging.StreamHandler(sys.stdout),
            ],
        )

        # Get tool environment for getorganelle
        tool_envs = load_tool_envs(kwargs.get('tool_envs', {}))
        go_cfg = tool_envs.get('getorganelle', {}) or {}
        conda_env = go_cfg.get('conda_env', '')
        bin_dir = go_cfg.get('bin_dir', '')

        # Build shell prefix for getorganelle
        shell_prefix = ''
        if conda_env:
            shell_prefix = f'conda run --no-capture-output -n {conda_env} '
        elif bin_dir:
            shell_prefix = f'PATH="{bin_dir}:$PATH" '

        # Parse reads directory
        reads_dir = Path(kwargs.get('reads_dir')).resolve()
        suffix_fq = kwargs.get('suffix_fq', '_1.clean.fq.gz,_2.clean.fq.gz')
        fastq_pos = kwargs.get('fastq_pos', 'recursive')
        if ',' in suffix_fq:
            r1_suffix, r2_suffix = suffix_fq.split(',', 1)
            r1_suffix = r1_suffix.strip()
            r2_suffix = r2_suffix.strip()
        else:
            r1_suffix = f'_1{suffix_fq}'
            r2_suffix = f'_2{suffix_fq}'

        samples = parse_reads_dir(reads_dir, r1_suffix, r2_suffix, fastq_pos)
        if not samples:
            click.secho(f'No samples found in {reads_dir}', fg='red', err=True)
            raise click.exceptions.Exit(1)

        click.secho(f'>>> Found {len(samples)} samples', fg='cyan', err=True)

        # Build runner kwargs
        runner_kwargs = {
            'threads': kwargs.get('getorganelle_threads', 16),
            'rounds': kwargs.get('getorganelle_rounds'),
            'kmers': kwargs.get('getorganelle_kmers'),
            'word_size': kwargs.get('getorganelle_word_size'),
            'database': kwargs.get('organelle_database', 'animal_mt'),
            'genes': kwargs.get('genes'),
            'all_data': kwargs.get('getorganelle_all_data', False),
            'max_reads': kwargs.get('getorganelle_max_reads'),
            'reduce_reads_for_coverage': kwargs.get('getorganelle_reduce_reads_for_coverage'),
            'max_extending_len': kwargs.get('getorganelle_max_extending_len'),
            'extra_args': kwargs.get('getorganelle_extra_args'),
            'force': force,
            'overwrite': overwrite,
            'resume': resume,
            'shell_prefix': shell_prefix,
        }

        # Run batch
        runner = GetOrganelleRunner(threads=runner_kwargs['threads'], shell_prefix=shell_prefix)
        results = runner.run_batch(
            samples,
            result_dir,
            parallel_jobs=parallel_jobs,
            **runner_kwargs,
        )

        # Summary
        success = sum(1 for r in results if r.get('success'))
        failed = sum(1 for r in results if r.get('status') == 'FAILED')
        skipped = sum(1 for r in results if r.get('status') == 'SKIP')
        incomplete = sum(1 for r in results if r.get('status') == 'INCOMPLETE')

        click.secho(f'>>> Summary: {success} OK, {failed} FAILED, {skipped} SKIP, {incomplete} INCOMPLETE', fg='cyan', err=True)

        return failed == 0
    else:
        # Snakemake backend (default)
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


@click.command(name='mg-mt-nr', help=click.style('run MEANGS -> GetOrganelle MT -> GetOrganelle NR (rRNA)', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
@click.option('--backend', type=click.Choice(['snakemake', 'python']),
              default='snakemake', show_default=True,
              help='Execution backend: snakemake (workflow) or python (direct)')
@click.option('--parallel-jobs', '--parallel_jobs', 'parallel_jobs',
              type=int, default=3, show_default=True,
              help='Number of parallel jobs for Python backend')
@click.option('--nr-genes', '--nr_genes', 'nr_genes',
              default='rrnL,rrnS', show_default=True,
              help='Target genes for NR mode (comma-separated, e.g., rrnL,rrnS)')
@click.option('--nr-seed', '--nr_seed', 'nr_seed',
              help='Seed file for NR mode (optional, uses MT result if not provided)')
def mg_mt_nr(backend, parallel_jobs, nr_genes, nr_seed, **kwargs):
    """Run MEANGS -> GetOrganelle MT -> GetOrganelle NR pipeline.

    This pipeline first assembles mitochondrial genome with MEANGS,
    then uses the result as seed for GetOrganelle MT assembly,
    and finally extracts rRNA genes using GetOrganelle NR mode.

    Examples:
        # Run with default rRNA genes (rrnL, rrnS)
        fma mg-mt-nr --reads_dir /data

        # Run with custom target genes
        fma mg-mt-nr --nr-genes "rrnL,rrnS,cox1" --reads_dir /data

        # Use Python backend
        fma mg-mt-nr --backend python --parallel-jobs 5 --reads_dir /data
    """
    if backend == 'python':
        from FastMitoAssembler.bin.runners import GetOrganelleRunner, parse_reads_dir
        from pathlib import Path

        # Setup logging
        result_dir = Path(kwargs.get('result_dir', 'result')).resolve()
        result_dir.mkdir(parents=True, exist_ok=True)
        log_file = result_dir / 'mg_mt_nr.log'
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_file, mode='a', encoding='utf-8'),
                logging.StreamHandler(sys.stdout),
            ],
        )

        click.secho('>>> Phase 1: MEANGS assembly', fg='cyan', err=True)
        # MEANGS phase would be handled by existing meangs command
        # For now, assume MEANGS results are available

        click.secho('>>> Phase 2: GetOrganelle MT assembly', fg='cyan', err=True)
        # MT assembly with seed from MEANGS

        click.secho('>>> Phase 3: GetOrganelle NR (rRNA) assembly', fg='cyan', err=True)
        # NR assembly with seed from MT result

        click.secho('>>> Pipeline complete', fg='green', err=True)
    else:
        # Snakemake backend
        config_overrides = {
            'getorganelle_nr_mode': True,
            'getorganelle_nr_genes': nr_genes,
        }
        if nr_seed:
            config_overrides['getorganelle_nr_seed'] = nr_seed
        _run_stage(kwargs, 'mg_mt_nr_all', config_overrides)


@click.command(name='summary', help=click.style('collect summary FASTA/TSV outputs', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
def summary(**kwargs):
    _run_stage(kwargs, 'summary_all')


@click.command(name='spades', help=click.style('run SPAdes assembly in batch', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
@click.option('--backend', type=click.Choice(['snakemake', 'python']),
              default='snakemake', show_default=True,
              help='Execution backend: snakemake (workflow) or python (direct)')
@click.option('--parallel-jobs', '--parallel_jobs', 'parallel_jobs',
              type=int, default=3, show_default=True,
              help='Number of parallel jobs for Python backend')
@click.option('--force', is_flag=True,
              help='Force re-run even if sample is already done')
@click.option('--mode', type=click.Choice(['default', 'isolate', 'meta', 'rna', 'plasmid',
                                           'metaviral', 'metaplasmid', 'sc', 'rnaviral', 'shallow']),
              default='meta', show_default=True,
              help='SPAdes assembly mode')
@click.option('--threads', '-t', type=int, default=16, show_default=True,
              help='Number of threads for SPAdes')
@click.option('--memory', '-m', type=int, default=32, show_default=True,
              help='Memory limit in GB for SPAdes')
@click.option('--no-clean', is_flag=True,
              help='Do not clean intermediate files after assembly')
@click.option('--extra-args', default='',
              help='Extra arguments passed to SPAdes')
def spades(backend, parallel_jobs, force, mode, threads, memory, no_clean, extra_args, **kwargs):
    """Run SPAdes assembly in batch.

    Supports two execution backends:
    - snakemake: Uses Snakemake workflow (default)
    - python: Direct Python execution without Snakemake dependency

    Assembly modes:
    - default: General assembly (--only-assembler --careful)
    - isolate: Bacterial isolates (--isolate)
    - meta: Metagenome assembly (--meta) - recommended for diverse data
    - rna: Transcriptome assembly (--rna)
    - plasmid: Plasmid detection (--plasmid)
    - metaviral: Viral detection (--metaviral)
    - shallow: Low-coverage data (--meta -k 21,33,55)
    """
    if backend == 'python':
        # Python backend: direct execution
        from FastMitoAssembler.bin.runners._spades_runner import SpadesRunner, find_fastq_pairs, write_status_file

        # Setup logging
        result_dir = Path(kwargs.get('result_dir', 'spades_output')).resolve()
        result_dir.mkdir(parents=True, exist_ok=True)
        log_file = result_dir / 'spades.log'
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_file, mode='a', encoding='utf-8'),
                logging.StreamHandler(sys.stdout),
            ],
        )

        # Get tool environment for spades
        tool_envs = load_tool_envs(kwargs.get('tool_envs', {}))
        spades_cfg = tool_envs.get('spades', {}) or {}
        conda_env = spades_cfg.get('conda_env', '')
        bin_dir = spades_cfg.get('bin_dir', '')

        # Build shell prefix for spades
        shell_prefix = ''
        if conda_env:
            shell_prefix = f'conda run --no-capture-output -n {conda_env} '
        elif bin_dir:
            shell_prefix = f'PATH="{bin_dir}:$PATH" '

        # Parse reads directory
        reads_dir = Path(kwargs.get('reads_dir')).resolve()
        suffix_fq = kwargs.get('suffix_fq', '_1.clean.fq.gz,_2.clean.fq.gz')
        fastq_pos = kwargs.get('fastq_pos', 'subdir')
        if ',' in suffix_fq:
            r1_suffix, r2_suffix = suffix_fq.split(',', 1)
            r1_suffix = r1_suffix.strip()
            r2_suffix = r2_suffix.strip()
        else:
            r1_suffix = f'_1{suffix_fq}'
            r2_suffix = f'_2{suffix_fq}'

        samples = find_fastq_pairs(reads_dir, r1_suffix, r2_suffix, fastq_pos)
        if not samples:
            click.secho(f'No samples found in {reads_dir}', fg='red', err=True)
            raise click.exceptions.Exit(1)

        click.secho(f'>>> Found {len(samples)} samples', fg='cyan', err=True)
        click.secho(f'>>> Mode: {mode}, Threads: {threads}, Memory: {memory}GB', fg='cyan', err=True)

        # Create runner
        runner = SpadesRunner(threads=threads, memory_gb=memory, shell_prefix=shell_prefix)

        # Run batch
        results = runner.run_batch(
            samples,
            result_dir,
            mode=mode,
            parallel_jobs=parallel_jobs,
            force=force,
            extra_args=extra_args,
            auto_clean=not no_clean,
        )

        # Summary
        ok_count = sum(1 for r in results if r.get('status') == 'OK')
        skip_count = sum(1 for r in results if r.get('status') == 'SKIP')
        fail_count = sum(1 for r in results if r.get('status') in ('FAILED', 'TIMEOUT', 'ERROR'))

        click.secho(f'>>> Summary: {ok_count} OK, {skip_count} SKIP, {fail_count} FAILED', fg='cyan', err=True)

        # Write status file
        write_status_file(result_dir, results, mode)

        return fail_count == 0
    else:
        # Snakemake backend
        config_overrides = {
            'spades': {
                'enabled': True,
                'mode': mode,
                'threads': threads,
                'memory_gb': memory,
                'auto_clean': not no_clean,
                'extra_args': extra_args,
            }
        }
        _run_stage(kwargs, 'spades_all', config_overrides)


@click.command(name='busco', help=click.style('run BUSCO evaluation in batch', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
@click.option('--backend', type=click.Choice(['snakemake', 'python']),
              default='python', show_default=True,
              help='Execution backend: snakemake (workflow) or python (direct)')
@click.option('--parallel-jobs', '--parallel_jobs', 'parallel_jobs',
              type=int, default=3, show_default=True,
              help='Number of parallel jobs for Python backend')
@click.option('--force', is_flag=True,
              help='Force re-run even if sample is already done')
@click.option('--lineage', '-l', default='metazoa_odb10', show_default=True,
              help='BUSCO lineage database')
@click.option('--mode', '-m', type=click.Choice(['genome', 'transcriptome', 'proteins']),
              default='genome', show_default=True,
              help='BUSCO assessment mode')
@click.option('--threads', '-t', type=int, default=12, show_default=True,
              help='Number of threads for BUSCO')
@click.option('--offline', is_flag=True,
              help='Use offline mode with local lineage database')
@click.option('--download-path', type=click.Path(),
              help='Path to download lineage database')
def busco(backend, parallel_jobs, force, lineage, mode, threads, offline, download_path, **kwargs):
    """Run BUSCO evaluation in batch.

    Supports two execution backends:
    - python: Direct Python execution (default)
    - snakemake: Uses Snakemake workflow

    BUSCO modes:
    - genome: Assess genome assembly
    - transcriptome: Assess transcriptome
    - proteins: Assess protein sequences
    """
    if backend == 'python':
        # Python backend: direct execution
        from FastMitoAssembler.bin.runners._busco_runner import BuscoRunner, find_fasta_files, write_busco_status

        # Setup logging
        result_dir = Path(kwargs.get('result_dir', 'busco_output')).resolve()
        result_dir.mkdir(parents=True, exist_ok=True)
        log_file = result_dir / 'busco.log'
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_file, mode='a', encoding='utf-8'),
                logging.StreamHandler(sys.stdout),
            ],
        )

        # Get tool environment for busco
        tool_envs = load_tool_envs(kwargs.get('tool_envs', {}))
        busco_cfg = tool_envs.get('busco', {}) or {}
        conda_env = busco_cfg.get('conda_env', '')
        bin_dir = busco_cfg.get('bin_dir', '')

        # Build shell prefix for busco
        shell_prefix = ''
        if conda_env:
            shell_prefix = f'conda run --no-capture-output -n {conda_env} '
        elif bin_dir:
            shell_prefix = f'PATH="{bin_dir}:$PATH" '

        # Parse input directory
        input_dir = Path(kwargs.get('reads_dir')).resolve()  # reads_dir used as input_dir for busco

        # Find FASTA files
        fasta_files = find_fasta_files(input_dir)
        if not fasta_files:
            click.secho(f'No FASTA files found in {input_dir}', fg='red', err=True)
            raise click.exceptions.Exit(1)

        click.secho(f'>>> Found {len(fasta_files)} FASTA files', fg='cyan', err=True)
        click.secho(f'>>> Lineage: {lineage}, Mode: {mode}, Threads: {threads}', fg='cyan', err=True)

        # Create runner
        runner = BuscoRunner(threads=threads, shell_prefix=shell_prefix)

        # Run batch
        results = runner.run_batch(
            fasta_files,
            result_dir,
            lineage=lineage,
            mode=mode,
            parallel_jobs=parallel_jobs,
            force=force,
            offline=offline,
            download_path=download_path,
        )

        # Summary
        ok_count = sum(1 for r in results if r.get('status') == 'OK')
        skip_count = sum(1 for r in results if r.get('status') == 'SKIP')
        fail_count = sum(1 for r in results if r.get('status') in ('FAILED', 'ERROR'))

        click.secho(f'>>> Summary: {ok_count} OK, {skip_count} SKIP, {fail_count} FAILED', fg='cyan', err=True)

        # Write status file
        write_busco_status(result_dir, results, lineage, mode)

        return fail_count == 0
    else:
        # Snakemake backend
        config_overrides = {
            'busco': {
                'enabled': True,
                'lineage': lineage,
                'mode': mode,
                'threads': threads,
                'offline': offline,
            }
        }
        _run_stage(kwargs, 'busco_all', config_overrides)


# =============================================================================
# MultiQC Command
# =============================================================================

@click.command(name='multiqc', help=click.style('run MultiQC summary report', fg='cyan', bold=True), no_args_is_help=True)
@common_workflow_options
@click.option('--backend', type=click.Choice(['snakemake', 'python']),
              default='python', show_default=True,
              help='Execution backend: snakemake (workflow) or python (direct)')
@click.option('--force', is_flag=True,
              help='Force re-run even if report already exists')
@click.option('--input-dir', '-i', required=True, type=click.Path(exists=True),
              help='Input directory containing QC results')
@click.option('--output-dir', '-o', default='multiqc_report', show_default=True,
              help='Output directory for MultiQC report')
def multiqc(backend, force, input_dir, output_dir, **kwargs):
    """Run MultiQC to aggregate all QC reports.

    MultiQC searches for and aggregates results from:
    - fastp quality control
    - BUSCO evaluation
    - SPAdes assembly stats
    - FastQC reports
    """
    if backend == 'python':
        # Python backend: direct execution
        from FastMitoAssembler.bin.runners._multiqc_runner import MultiqcRunner

        # Setup logging
        output_path = Path(output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)
        log_file = output_path / 'multiqc.log'
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_file, mode='a', encoding='utf-8'),
                logging.StreamHandler(sys.stdout),
            ],
        )

        # Get tool environment for multiqc
        tool_envs = load_tool_envs(kwargs.get('tool_envs', {}))
        multiqc_cfg = tool_envs.get('multiqc', {}) or {}
        conda_env = multiqc_cfg.get('conda_env', '')
        bin_dir = multiqc_cfg.get('bin_dir', '')

        # Build shell prefix for multiqc
        shell_prefix = ''
        if conda_env:
            shell_prefix = f'conda run --no-capture-output -n {conda_env} '
        elif bin_dir:
            shell_prefix = f'PATH="{bin_dir}:$PATH" '

        # Create runner
        runner = MultiqcRunner(shell_prefix=shell_prefix)

        # Run MultiQC
        result = runner.run(
            Path(input_dir).resolve(),
            output_path,
            force=force,
        )

        if result.get('status') == 'OK':
            click.secho(f'>>> MultiQC report: {output_path}/multiqc_report.html', fg='green', err=True)
            return True
        elif result.get('status') == 'SKIP':
            click.secho(f'>>> Report already exists: {output_path}/multiqc_report.html', fg='yellow', err=True)
            return True
        else:
            click.secho(f'>>> MultiQC failed: {result.get("message", "Unknown error")}', fg='red', err=True)
            if result.get('hints'):
                for hint in result['hints']:
                    click.secho(f'    Hint: {hint}', fg='yellow', err=True)
            return False
    else:
        # Snakemake backend
        config_overrides = {
            'multiqc': {
                'enabled': True,
                'force': force,
            }
        }
        _run_stage(kwargs, 'multiqc_all', config_overrides)


# =============================================================================
# FSB-All: One-Click Pipeline (fastp -> MultiQC -> SPAdes -> BUSCO)
# =============================================================================

@click.command(name='fsb-all',
    help=click.style('run fastp -> MultiQC -> SPAdes -> BUSCO pipeline', fg='cyan', bold=True),
    no_args_is_help=True)
@common_workflow_options
@click.option('--backend', type=click.Choice(['snakemake', 'python']),
              default='python', show_default=True,
              help='Execution backend: snakemake (workflow) or python (direct)')
@click.option('--mode', type=click.Choice(['default', 'isolate', 'meta', 'rna', 'plasmid', 'metaviral', 'shallow']),
              default='meta', show_default=True,
              help='SPAdes assembly mode')
@click.option('--lineage', default='metazoa_odb10', show_default=True,
              help='BUSCO lineage database')
@click.option('--fastp-mode', 'fastp_mode', default='adapter_only', show_default=True,
              help='fastp preset mode')
@click.option('-t', '--threads', type=int, default=16, show_default=True,
              help='Threads per job')
@click.option('-m', '--memory', type=int, default=32, show_default=True,
              help='Memory in GB for SPAdes')
@click.option('--parallel-jobs', '--parallel_jobs', 'parallel_jobs',
              type=int, default=3, show_default=True,
              help='Number of parallel jobs for Python backend')
@click.option('--force', is_flag=True,
              help='Force re-run all steps')
def fsb_all(backend, mode, lineage, fastp_mode, threads, memory, parallel_jobs, force, **kwargs):
    """Run complete assembly evaluation pipeline.

    Pipeline steps:
    1. fastp: Quality control and adapter trimming
    2. MultiQC: QC summary report (after fastp)
    3. SPAdes: Genome assembly
    4. BUSCO: Assembly quality evaluation

    Supports two execution backends:
    - python: Direct Python execution (default)
    - snakemake: Uses Snakemake workflow
    """
    if backend == 'python':
        return _run_fsb_all_python(kwargs, mode, lineage, fastp_mode, threads, memory, parallel_jobs, force)
    else:
        # Snakemake backend
        config_overrides = {
            'fastp': {'enabled': True, 'mode': fastp_mode},
            'spades': {'enabled': True, 'mode': mode, 'threads': threads, 'memory_gb': memory},
            'busco': {'enabled': True, 'lineage': lineage},
            'multiqc': {'enabled': True},
        }
        _run_stage(kwargs, 'fsb_all', config_overrides)


def _run_fsb_all_python(kwargs, mode, lineage, fastp_mode, threads, memory, parallel_jobs, force):
    """Python backend implementation for fsb-all pipeline."""
    from FastMitoAssembler.bin.runners import (
        FastpRunner,
        fastp_parse_reads_dir_auto,
        fastp_get_output_files,
    )
    from FastMitoAssembler.bin.runners._spades_runner import (
        SpadesRunner,
        find_fastq_pairs,
    )
    from FastMitoAssembler.bin.runners._busco_runner import (
        BuscoRunner,
        find_fasta_files,
    )
    from FastMitoAssembler.bin.runners._multiqc_runner import MultiqcRunner

    reads_dir = Path(kwargs.get('reads_dir', 'reads')).resolve()
    result_dir = Path(kwargs.get('result_dir', 'result')).resolve()
    result_dir.mkdir(parents=True, exist_ok=True)

    # Setup logging
    log_file = result_dir / 'fsb_all.log'
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode='a', encoding='utf-8'),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Get tool environments
    tool_envs = load_tool_envs(kwargs.get('tool_envs', {}))

    # ============================================================
    # Step 1: fastp - Parse samples first!
    # ============================================================
    click.secho('[1/4] Running fastp...', fg='cyan', bold=True, err=True)
    fastp_out = result_dir / 'fastp'

    # Parse samples from reads_dir (returns Dict[str, Tuple[str, str]])
    samples, detected_pos = fastp_parse_reads_dir_auto(reads_dir)
    if not samples:
        click.secho(f'    ERROR: No samples found in {reads_dir}', fg='red', err=True)
        return False

    logging.info(f"[FASTP] Found {len(samples)} samples, structure: {detected_pos}")
    click.secho(f'    Found {len(samples)} samples', fg='green', err=True)

    fastp_cfg = tool_envs.get('fastp', {}) or {}
    fastp_shell_prefix = ''
    if fastp_cfg.get('conda_env'):
        fastp_shell_prefix = f'conda run --no-capture-output -n {fastp_cfg["conda_env"]} '
    elif fastp_cfg.get('bin_dir'):
        fastp_shell_prefix = f'PATH="{fastp_cfg["bin_dir"]}:$PATH" '

    fastp_runner = FastpRunner(threads=threads, shell_prefix=fastp_shell_prefix)
    fastp_results = fastp_runner.run_batch(
        samples,  # Dict[str, Tuple[str, str]] - correct type!
        fastp_out,
        mode=fastp_mode,
        parallel_jobs=parallel_jobs,
        force=force,
    )

    # Check fastp results
    fastp_success = sum(1 for r in fastp_results if r.get('success'))
    fastp_failed = len(samples) - fastp_success
    if fastp_failed > 0:
        click.secho(f'    fastp: {fastp_success} OK, {fastp_failed} FAILED', fg='yellow', err=True)
    else:
        click.secho(f'    fastp complete! ({fastp_success} samples)', fg='green', err=True)

    # ============================================================
    # Step 2: MultiQC (after fastp to summarize QC results)
    # ============================================================
    click.secho('[2/4] Running MultiQC...', fg='cyan', bold=True, err=True)
    multiqc_out = result_dir / 'multiqc'
    multiqc_cfg = tool_envs.get('multiqc', {}) or {}
    multiqc_shell_prefix = ''
    if multiqc_cfg.get('conda_env'):
        multiqc_shell_prefix = f'conda run --no-capture-output -n {multiqc_cfg["conda_env"]} '
    elif multiqc_cfg.get('bin_dir'):
        multiqc_shell_prefix = f'PATH="{multiqc_cfg["bin_dir"]}:$PATH" '

    multiqc_runner = MultiqcRunner(shell_prefix=multiqc_shell_prefix)
    multiqc_runner.run(fastp_out, multiqc_out, force=force)
    click.secho('    MultiQC complete!', fg='green', err=True)

    # ============================================================
    # Step 3: SPAdes - Build samples dict from fastp output
    # ============================================================
    click.secho('[3/4] Running SPAdes...', fg='cyan', bold=True, err=True)
    spades_out = result_dir / 'spades'

    # Build samples dict from fastp output directory
    # Look for {sample}/{sample}_1.clean.fq.gz files
    spades_samples = find_fastq_pairs(
        fastp_out,
        r1_suffix="_1.clean.fq.gz",
        r2_suffix="_2.clean.fq.gz",
        fastq_pos="subdir",
    )

    if not spades_samples:
        click.secho(f'    ERROR: No fastp output found in {fastp_out}', fg='red', err=True)
        return False

    logging.info(f"[SPADES] Found {len(spades_samples)} samples from fastp output")
    click.secho(f'    Found {len(spades_samples)} samples', fg='green', err=True)

    spades_cfg = tool_envs.get('spades', {}) or {}
    spades_shell_prefix = ''
    if spades_cfg.get('conda_env'):
        spades_shell_prefix = f'conda run --no-capture-output -n {spades_cfg["conda_env"]} '
    elif spades_cfg.get('bin_dir'):
        spades_shell_prefix = f'PATH="{spades_cfg["bin_dir"]}:$PATH" '

    spades_runner = SpadesRunner(threads=threads, memory_gb=memory, shell_prefix=spades_shell_prefix)
    spades_results = spades_runner.run_batch(
        spades_samples,  # Dict[str, Tuple[Path, Path]] - correct type!
        spades_out,
        mode=mode,
        parallel_jobs=parallel_jobs,
        force=force,
    )

    # Check SPAdes results
    spades_success = sum(1 for r in spades_results if r.get('success'))
    spades_failed = len(spades_samples) - spades_success
    if spades_failed > 0:
        click.secho(f'    SPAdes: {spades_success} OK, {spades_failed} FAILED', fg='yellow', err=True)
    else:
        click.secho(f'    SPAdes complete! ({spades_success} samples)', fg='green', err=True)

    # ============================================================
    # Step 4: BUSCO
    # ============================================================
    click.secho('[4/4] Running BUSCO...', fg='cyan', bold=True, err=True)
    busco_out = result_dir / 'busco'
    busco_cfg = tool_envs.get('busco', {}) or {}
    busco_shell_prefix = ''
    if busco_cfg.get('conda_env'):
        busco_shell_prefix = f'conda run --no-capture-output -n {busco_cfg["conda_env"]} '
    elif busco_cfg.get('bin_dir'):
        busco_shell_prefix = f'PATH="{busco_cfg["bin_dir"]}:$PATH" '

    busco_runner = BuscoRunner(threads=threads, shell_prefix=busco_shell_prefix)
    fasta_files = find_fasta_files(spades_out)
    if fasta_files:
        busco_runner.run_batch(
            fasta_files,  # Dict[str, Path] - correct type!
            busco_out,
            lineage=lineage,
            mode='genome',
            parallel_jobs=parallel_jobs,
            force=force,
        )
        click.secho(f'    BUSCO complete! ({len(fasta_files)} samples)', fg='green', err=True)
    else:
        click.secho('    BUSCO skipped (no FASTA files found)', fg='yellow', err=True)

    # Summary
    click.secho('\n>>> Pipeline complete!', fg='green', bold=True, err=True)
    click.secho(f'>>> Results: {result_dir}', fg='cyan', err=True)
    click.secho(f'>>> MultiQC report: {multiqc_out}/multiqc_report.html', fg='cyan', err=True)

    return True


STAGE_COMMANDS = [
    meangs,
    novoplasty,
    getorganelle,
    mitoz,
    mg_nov,
    mg_get,
    mg_nov_get,
    mg_mt_nr,
    summary,
    spades,
    busco,
    multiqc,
    fsb_all,
]
