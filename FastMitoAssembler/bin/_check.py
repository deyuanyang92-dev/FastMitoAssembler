from pathlib import Path

import click

from FastMitoAssembler import util

GLOBAL_TOOL_ENVS_PATH = Path.home() / '.config' / 'FastMitoAssembler' / 'tool_envs.yaml'

TOOL_PROBES = [
    ('meangs',       'meangs.py --version'),
    ('novoplasty',   'NOVOPlasty.pl'),
    ('getorganelle', 'get_organelle_from_reads.py --version'),
    ('mitoz',        'mitoz --version'),
]

# Status constants
_ST_FOUND   = 'found'
_ST_BUNDLED = 'bundled'   # no explicit config; will be auto-built by Snakemake --use-conda
_ST_ERROR   = 'error'     # explicitly configured but not working


def _run_probe(cmd, env_prefix=''):
    full_cmd = f'{env_prefix}{cmd} 2>&1'
    status, _ = util.getstatusoutput(full_cmd)
    return status == 0


def _probe_tool(tool, probe_cmd, cfg):
    """Return (status, detail_message).

    status is one of _ST_FOUND / _ST_BUNDLED / _ST_ERROR.
    """
    cfg = cfg or {}
    conda_env  = (cfg.get('conda_env')  or '').strip()
    bin_dir    = (cfg.get('bin_dir')    or '').strip()
    script_path = (cfg.get('script_path') or '').strip()

    if conda_env:
        ok = _run_probe(probe_cmd, f'conda run --no-capture-output -n {conda_env} ')
        if ok:
            return _ST_FOUND, f'conda env: {conda_env}'
        return _ST_ERROR, f'conda env "{conda_env}" configured but tool not found — check the env name'

    if bin_dir:
        ok = _run_probe(probe_cmd, f'PATH="{bin_dir}:$PATH" ')
        if ok:
            return _ST_FOUND, f'bin_dir: {bin_dir}'
        return _ST_ERROR, f'bin_dir "{bin_dir}" configured but tool not found — check the path'

    if script_path:
        abs_path = Path(script_path).expanduser().resolve()
        if abs_path.is_file():
            return _ST_FOUND, f'script: perl {abs_path}'
        return _ST_ERROR, f'script_path "{script_path}" not found — check the path'

    # No explicit config — probe PATH; if missing, Snakemake will auto-build the bundled env
    ok = _run_probe(probe_cmd)
    if ok:
        return _ST_FOUND, 'in PATH'
    return _ST_BUNDLED, 'not in PATH — will be auto-built on first run (Snakemake --use-conda)'


def load_tool_envs(project_tool_envs=None):
    merged = {}
    if GLOBAL_TOOL_ENVS_PATH.exists():
        merged = util.read_yaml(GLOBAL_TOOL_ENVS_PATH) or {}
    for tool, cfg in (project_tool_envs or {}).items():
        if cfg and isinstance(cfg, dict) and (
            cfg.get('conda_env') or cfg.get('bin_dir') or cfg.get('script_path')
        ):
            merged[tool] = cfg
    return merged


@click.command(help=click.style('check tool availability and optionally save config globally', fg='cyan', bold=True))
@click.option('--configfile', default='config.yaml', show_default=True,
              help='project config.yaml to read tool_envs from')
@click.option('--save', is_flag=True,
              help=f'save validated tool configs to {GLOBAL_TOOL_ENVS_PATH}')
def check(configfile, save):
    project_cfg = {}
    if Path(configfile).exists():
        project_cfg = util.read_yaml(configfile) or {}
    tool_envs = load_tool_envs(project_cfg.get('tool_envs', {}))

    click.secho('\nChecking tool availability...\n', bold=True)
    header = f"  {'Tool':<16} {'Status':<14} Details"
    click.echo(header)
    click.echo('  ' + '─' * 62)

    validated = {}
    has_error = False
    for tool, probe_cmd in TOOL_PROBES:
        cfg = tool_envs.get(tool, {})
        status, detail = _probe_tool(tool, probe_cmd, cfg)
        if status == _ST_FOUND:
            status_txt = click.style('✓ found', fg='green')
            click.echo(f"  {tool:<16} {status_txt:<23} {detail}")
            validated[tool] = cfg if cfg else {}
        elif status == _ST_BUNDLED:
            status_txt = click.style('⚡ bundled', fg='yellow')
            click.echo(f"  {tool:<16} {status_txt:<23} {detail}")
        else:  # _ST_ERROR
            status_txt = click.style('✗ error', fg='red')
            has_error = True
            click.echo(f"  {tool:<16} {status_txt:<23} {detail}")

    click.echo()

    if has_error:
        click.secho(
            'Fix the errors above, then run `fma config set <tool> --conda-env <env>` '
            'or `fma config set <tool> --bin-dir <dir>` to save globally.',
            fg='red',
        )
    else:
        click.secho(
            '⚡ bundled tools are not yet installed.\n'
            '  Option A (recommended): run `fma prepare tools` to install them now into named conda envs.\n'
            '  Option B: run `fma run` — Snakemake will auto-create local envs on first use.\n'
            '  Option C: use your own installs — `fma config set <tool> --conda-env <env>`',
            fg='cyan',
        )

    if save:
        if not validated:
            click.secho('No explicitly-found tools to save.', fg='yellow')
            return
        existing = {}
        if GLOBAL_TOOL_ENVS_PATH.exists():
            existing = util.read_yaml(GLOBAL_TOOL_ENVS_PATH) or {}
        for tool, cfg in validated.items():
            if tool not in existing or not (existing[tool] or {}).get('conda_env') and not (existing[tool] or {}).get('bin_dir'):
                existing[tool] = cfg
        GLOBAL_TOOL_ENVS_PATH.parent.mkdir(parents=True, exist_ok=True)
        import yaml
        with open(GLOBAL_TOOL_ENVS_PATH, 'w') as f:
            yaml.dump(existing, f, default_flow_style=False, allow_unicode=True)
        click.secho(f'Saved to {GLOBAL_TOOL_ENVS_PATH}', fg='green')
