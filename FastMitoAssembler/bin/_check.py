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


def _run_probe(cmd, env_prefix=''):
    full_cmd = f'{env_prefix}{cmd} 2>&1'
    status, _ = util.getstatusoutput(full_cmd)
    return status == 0


def _probe_tool(tool, probe_cmd, cfg):
    cfg = cfg or {}
    conda_env = (cfg.get('conda_env') or '').strip()
    bin_dir = (cfg.get('bin_dir') or '').strip()

    if conda_env:
        ok = _run_probe(probe_cmd, f'conda run --no-capture-output -n {conda_env} ')
        if ok:
            return True, f'conda env: {conda_env}', None
        return False, None, f'conda env "{conda_env}" configured but tool not found — check the env name'

    if bin_dir:
        ok = _run_probe(probe_cmd, f'PATH="{bin_dir}:$PATH" ')
        if ok:
            return True, f'bin_dir: {bin_dir}', None
        return False, None, f'bin_dir "{bin_dir}" configured but tool not found — check the path'

    ok = _run_probe(probe_cmd)
    if ok:
        return True, 'in PATH', None
    return False, None, None


def load_tool_envs(project_tool_envs=None):
    merged = {}
    if GLOBAL_TOOL_ENVS_PATH.exists():
        merged = util.read_yaml(GLOBAL_TOOL_ENVS_PATH) or {}
    for tool, cfg in (project_tool_envs or {}).items():
        if cfg and isinstance(cfg, dict) and (cfg.get('conda_env') or cfg.get('bin_dir')):
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
    header = f"  {'Tool':<16} {'Status':<12} Details"
    click.echo(header)
    click.echo('  ' + '─' * 54)

    validated = {}
    all_ok = True
    for tool, probe_cmd in TOOL_PROBES:
        cfg = tool_envs.get(tool, {})
        ok, location, error = _probe_tool(tool, probe_cmd, cfg)
        if ok:
            status_txt = click.style('✓ found', fg='green')
            click.echo(f"  {tool:<16} {status_txt:<21} {location}")
            validated[tool] = cfg if cfg else {}
        else:
            status_txt = click.style('✗ missing', fg='red')
            all_ok = False
            if error:
                click.echo(f"  {tool:<16} {status_txt:<21} {error}")
            else:
                hint = f'set tool_envs.{tool}.conda_env or bin_dir in config.yaml'
                click.echo(f"  {tool:<16} {status_txt:<21} → {hint}")

    click.echo()

    if save:
        if not validated:
            click.secho('No tools validated — nothing to save.', fg='yellow')
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
    elif not all_ok:
        click.secho('Tip: run `fma check --save` after fixing missing tools to save configs globally.', fg='cyan')
