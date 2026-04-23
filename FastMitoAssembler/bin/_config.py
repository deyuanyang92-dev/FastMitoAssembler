"""fma config — manage per-tool environment settings globally."""
import yaml
from pathlib import Path

import click

from FastMitoAssembler import util
from FastMitoAssembler.bin._check import (
    GLOBAL_TOOL_ENVS_PATH,
    TOOL_PROBES,
    _probe_tool,
    _ST_FOUND,
    _ST_ERROR,
    script_invocation,
)

_TOOLS = [t for t, _ in TOOL_PROBES]
_PROBE_MAP = {t: cmd for t, cmd in TOOL_PROBES}


def _load_global():
    if GLOBAL_TOOL_ENVS_PATH.exists():
        return util.read_yaml(GLOBAL_TOOL_ENVS_PATH) or {}
    return {}


def _save_global(data):
    GLOBAL_TOOL_ENVS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GLOBAL_TOOL_ENVS_PATH, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


@click.group(
    name='config',
    help=click.style('manage per-tool environment configuration globally', fg='cyan', bold=True),
)
def config_cmd():
    pass


@config_cmd.command('set', help='set conda_env, bin_dir or script_path for a tool and save globally')
@click.argument('tool', type=click.Choice(_TOOLS))
@click.option('--conda-env', default='', metavar='ENV',
              help='name of an existing conda environment that contains the tool')
@click.option('--bin-dir', default='', metavar='DIR',
              help='directory that contains the tool binary (prepended to PATH)')
@click.option('--script-path', default='', metavar='PATH',
              help='full path to a tool script, e.g. meangs.py or NOVOPlasty.pl')
@click.option('--no-check', is_flag=True,
              help='skip validation before saving')
def config_set(tool, conda_env, bin_dir, script_path, no_check):
    if not conda_env and not bin_dir and not script_path:
        click.secho(
            'Provide at least one of --conda-env, --bin-dir, or --script-path.\n'
            'To remove a setting use: fma config reset ' + tool,
            fg='red',
        )
        raise SystemExit(1)

    cfg = {'conda_env': conda_env, 'bin_dir': bin_dir, 'script_path': script_path}

    if not no_check:
        click.secho(f'Validating {tool}...', fg='cyan')
        status, detail = _probe_tool(tool, _PROBE_MAP[tool], cfg)
        if status == _ST_ERROR:
            click.secho(f'Validation failed: {detail}', fg='red')
            click.secho('Use --no-check to save anyway.', fg='yellow')
            raise SystemExit(1)
        if status == _ST_FOUND:
            click.secho(f'  {tool}: {detail}', fg='green')

    data = _load_global()
    data[tool] = cfg
    _save_global(data)
    click.secho(f'Saved {tool} → {GLOBAL_TOOL_ENVS_PATH}', fg='green')


@config_cmd.command('reset', help='remove stored config for a tool (revert to bundled auto mode)')
@click.argument('tool', type=click.Choice(_TOOLS + ['all']))
def config_reset(tool):
    data = _load_global()
    if tool == 'all':
        removed = list(data.keys())
        data = {}
    else:
        removed = [tool] if tool in data else []
        data.pop(tool, None)

    if not removed:
        click.secho('Nothing to reset.', fg='yellow')
        return
    _save_global(data)
    for t in removed:
        click.secho(f'Reset {t} → bundled (auto-create on first run)', fg='green')


@config_cmd.command('show', help='show current global tool configuration')
def config_show():
    data = _load_global()
    click.secho(f'\nGlobal config: {GLOBAL_TOOL_ENVS_PATH}\n', bold=True)
    header = f"  {'Tool':<16} {'Type':<12} Value"
    click.echo(header)
    click.echo('  ' + '─' * 64)
    for tool in _TOOLS:
        cfg = data.get(tool) or {}
        if not isinstance(cfg, dict):
            cfg = {}
        conda_env   = cfg.get('conda_env')   or ''
        bin_dir     = cfg.get('bin_dir')     or ''
        script_path = cfg.get('script_path') or ''
        if conda_env:
            click.echo(f"  {tool:<16} {'conda_env':<12} {conda_env}")
        elif bin_dir:
            click.echo(f"  {tool:<16} {'bin_dir':<12} {bin_dir}")
        elif script_path:
            click.echo(f"  {tool:<16} {'script_path':<12} {script_invocation(tool, script_path)}")
        else:
            mode = click.style('⚡ bundled (auto)', fg='yellow')
            click.echo(f"  {tool:<16} {mode}")
    click.echo()
    click.secho(
        'Use `fma config set <tool> --conda-env <env>`, `--bin-dir <dir>`, or `--script-path <path>`.',
        fg='cyan',
    )
