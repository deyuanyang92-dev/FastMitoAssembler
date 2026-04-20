"""fma setup — interactive wizard to configure all tool environments."""
import yaml
from pathlib import Path

import click

from FastMitoAssembler.bin._check import (
    GLOBAL_TOOL_ENVS_PATH,
    TOOL_PROBES,
    _probe_tool,
    _run_probe,
    _ST_FOUND,
    _ST_ERROR,
)

_TOOL_DISPLAY = {
    'meangs':       'MEANGS',
    'novoplasty':   'NOVOPlasty',
    'getorganelle': 'GetOrganelle',
    'mitoz':        'MitoZ',
}

_MAX_RETRIES = 3


def _load_global():
    if GLOBAL_TOOL_ENVS_PATH.exists():
        try:
            return yaml.safe_load(GLOBAL_TOOL_ENVS_PATH.read_text()) or {}
        except Exception:
            return {}
    return {}


def _save_global(updates):
    data = _load_global()
    data.update(updates)
    GLOBAL_TOOL_ENVS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GLOBAL_TOOL_ENVS_PATH, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def _current_status(tool, probe_cmd):
    """Return a one-line description of the current config for a tool."""
    data = _load_global()
    cfg = data.get(tool) or {}
    status, detail = _probe_tool(tool, probe_cmd, cfg)
    if status == _ST_FOUND:
        return click.style(f'✓ {detail}', fg='green')
    if status == _ST_ERROR:
        return click.style(f'✗ {detail}', fg='red')
    return click.style('⚡ not configured (bundled auto mode)', fg='yellow')


def _validate_conda_env(tool, probe_cmd, env_name):
    cfg = {'conda_env': env_name, 'bin_dir': '', 'script_path': ''}
    status, detail = _probe_tool(tool, probe_cmd, cfg)
    return status == _ST_FOUND, detail


def _validate_bin_dir(tool, probe_cmd, bin_dir):
    cfg = {'conda_env': '', 'bin_dir': bin_dir, 'script_path': ''}
    status, detail = _probe_tool(tool, probe_cmd, cfg)
    return status == _ST_FOUND, detail


def _validate_script_path(script_path):
    p = Path(script_path).expanduser().resolve()
    if p.is_file():
        return True, f'script: perl {p}'
    return False, f'file not found: {p}'


def _install_tool(tool):
    """Run fma prepare tools --tool <tool> in a subprocess."""
    import subprocess
    click.secho(f'  Installing {tool} via fma prepare tools...', fg='cyan')
    result = subprocess.run(
        ['fma', 'prepare', 'tools', '--tool', tool],
        text=True,
    )
    return result.returncode == 0


def _wizard_configure_tool(index, total, tool, probe_cmd):
    """Walk the user through configuring one tool.

    Returns a config dict, or None if the user chose to skip.
    """
    display = _TOOL_DISPLAY.get(tool, tool.upper())
    sep = '─' * 54

    click.echo(f'\n  {sep}')
    click.secho(f'  [{index}/{total}]  {display}', bold=True)
    click.echo(f'  Current status: {_current_status(tool, probe_cmd)}')
    click.echo()

    # Build menu
    options = [
        ('Conda environment', 'enter env name, e.g. my_{}_env'.format(tool)),
        ('Directory',         'enter bin dir, e.g. /opt/{}/bin'.format(tool)),
    ]
    if tool == 'novoplasty':
        options.append(('Perl script path', 'e.g. /opt/NOVOPlasty/NOVOPlasty.pl'))
    options.append(('Install now',     'run: fma prepare tools --tool {}'.format(tool)))
    options.append(('Skip',            'Snakemake will auto-install on first run'))

    for i, (label, hint) in enumerate(options, 1):
        click.echo(f'    {i}) {label:<22} ({hint})')

    skip_idx   = len(options)
    install_idx = skip_idx - 1

    for attempt in range(1, _MAX_RETRIES + 2):  # +2: one extra to show "giving up"
        try:
            raw = click.prompt(f'\n  Choice [1-{len(options)}]', default='1')
        except click.Abort:
            click.echo()
            return None

        try:
            choice = int(raw)
        except ValueError:
            click.secho('  Invalid input. Enter a number.', fg='red')
            continue

        if choice < 1 or choice > len(options):
            click.secho(f'  Please enter a number between 1 and {len(options)}.', fg='red')
            continue

        if choice == skip_idx:
            click.secho(f'  Skipped — {display} will be auto-installed on first run.', fg='yellow')
            return None

        if choice == install_idx:
            ok = _install_tool(tool)
            if ok:
                # After install, the named env is saved by fma prepare tools
                click.secho(f'  {display} installed.', fg='green')
                return None  # already saved by prepare tools
            else:
                click.secho('  Installation failed. Skipping.', fg='red')
                return None

        # --- conda env ---
        if choice == 1:
            env_name = click.prompt('  Conda env name').strip()
            if not env_name:
                continue
            click.secho('  Validating...', fg='cyan', nl=False)
            ok, detail = _validate_conda_env(tool, probe_cmd, env_name)
            if ok:
                click.secho(f' ✓ {detail}', fg='green')
                return {'conda_env': env_name, 'bin_dir': '', 'script_path': ''}
            click.secho(f' ✗ {detail}', fg='red')
            if attempt < _MAX_RETRIES:
                click.secho(f'  Try again ({attempt}/{_MAX_RETRIES})', fg='yellow')
            else:
                click.secho('  Too many failures — skipping.', fg='yellow')
                return None
            continue

        # --- bin dir ---
        if choice == 2:
            bin_dir = click.prompt('  Directory path').strip()
            if not bin_dir:
                continue
            click.secho('  Validating...', fg='cyan', nl=False)
            ok, detail = _validate_bin_dir(tool, probe_cmd, bin_dir)
            if ok:
                click.secho(f' ✓ {detail}', fg='green')
                return {'conda_env': '', 'bin_dir': bin_dir, 'script_path': ''}
            click.secho(f' ✗ {detail}', fg='red')
            if attempt < _MAX_RETRIES:
                click.secho(f'  Try again ({attempt}/{_MAX_RETRIES})', fg='yellow')
            else:
                click.secho('  Too many failures — skipping.', fg='yellow')
                return None
            continue

        # --- perl script path (novoplasty only) ---
        if choice == 3 and tool == 'novoplasty':
            script_path = click.prompt('  Path to NOVOPlasty.pl').strip()
            if not script_path:
                continue
            click.secho('  Validating...', fg='cyan', nl=False)
            ok, detail = _validate_script_path(script_path)
            if ok:
                abs_path = str(Path(script_path).expanduser().resolve())
                click.secho(f' ✓ {detail}', fg='green')
                click.secho(f'  Will be invoked as: perl {abs_path}', fg='cyan')
                return {'conda_env': '', 'bin_dir': '', 'script_path': abs_path}
            click.secho(f' ✗ {detail}', fg='red')
            if attempt < _MAX_RETRIES:
                click.secho(f'  Try again ({attempt}/{_MAX_RETRIES})', fg='yellow')
            else:
                click.secho('  Too many failures — skipping.', fg='yellow')
                return None
            continue

    return None


@click.command(
    name='setup',
    help=click.style(
        'interactive wizard to configure all bioinformatics tool environments',
        fg='cyan', bold=True,
    ),
)
def setup():
    """Walk through each tool (MEANGS, NOVOPlasty, GetOrganelle, MitoZ) one by one,
    validate the configuration, and save it globally so all future `fma run` calls
    use the correct environments automatically.
    """
    click.echo()
    click.secho('╔══════════════════════════════════════════════════════════╗', fg='cyan')
    click.secho('║       FastMitoAssembler — Tool Setup Wizard              ║', fg='cyan', bold=True)
    click.secho('╚══════════════════════════════════════════════════════════╝', fg='cyan')
    click.echo('  Configuring 4 tools. Press Ctrl+C at any time to cancel.')
    click.echo()
    click.secho(
        '  Tip: to install all tools automatically, run: fma prepare tools',
        fg='yellow',
    )

    results = {}
    for i, (tool, probe_cmd) in enumerate(TOOL_PROBES, 1):
        cfg = _wizard_configure_tool(i, len(TOOL_PROBES), tool, probe_cmd)
        if cfg is not None:
            results[tool] = cfg

    click.echo()
    if results:
        _save_global(results)
        click.secho('✓ Configuration saved to ' + str(GLOBAL_TOOL_ENVS_PATH), fg='green')
    else:
        click.secho('No changes saved.', fg='yellow')

    # Print summary
    click.echo()
    click.secho('  Summary:', bold=True)
    data = _load_global()
    for tool, probe_cmd in TOOL_PROBES:
        display = _TOOL_DISPLAY.get(tool, tool)
        cfg = data.get(tool) or {}
        status, detail = _probe_tool(tool, probe_cmd, cfg)
        if status == _ST_FOUND:
            icon = click.style('✓', fg='green')
            click.echo(f'  {icon} {display:<16} {detail}')
        else:
            icon = click.style('⚡', fg='yellow')
            click.echo(f'  {icon} {display:<16} auto (bundled)')

    click.echo()
    click.secho('Run `fma check` to verify all tools are reachable.', fg='cyan')
