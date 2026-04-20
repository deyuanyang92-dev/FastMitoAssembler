import os
import json

import yaml
import click
import snakemake

from FastMitoAssembler import MAIN_SMK, DEFAULT_CONFIG_FILE, DEFAULT_OPTION_FILE, VERSION, BANNER
from FastMitoAssembler.bin._run import run
from FastMitoAssembler.bin._other import prepare
from FastMitoAssembler.bin._init import init
from FastMitoAssembler.bin._check import check
from FastMitoAssembler.bin._config import config_cmd
from FastMitoAssembler.bin._setup import setup


CONTEXT_SETTINGS = dict(
    help_option_names=['-?', '-h', '--help'], max_content_width=800,)
BANNER = '\b\n'.join(BANNER.split('\n'))
HELP = f'''\n\n\b\n{BANNER}\n'''


__EPILOG__ = click.style('''
\n\b
Snakefile: {MAIN_SMK}
Configfile: {DEFAULT_CONFIG_FILE}
Optionfile: {DEFAULT_OPTION_FILE}

Contact: {author}<{author_email}>
''', fg='white').format(MAIN_SMK=MAIN_SMK, DEFAULT_CONFIG_FILE=DEFAULT_CONFIG_FILE, DEFAULT_OPTION_FILE=DEFAULT_OPTION_FILE, **VERSION)


@click.group(
    context_settings=CONTEXT_SETTINGS,
    name=VERSION['prog'],
    help=click.style(HELP, fg='cyan', italic=True),
    epilog=__EPILOG__,
)
@click.version_option(
    version=VERSION['version'],
    prog_name=VERSION['prog'],
    message=click.style('%(prog)s version %(version)s', bold=True, italic=True, fg='green'),
)
def cli():
    pass


def _tool_status_for_help():
    """Quick (file-only) tool status for the help epilog — no subprocess calls."""
    try:
        from FastMitoAssembler.bin._check import GLOBAL_TOOL_ENVS_PATH, TOOL_PROBES
        tools = [t for t, _ in TOOL_PROBES]
        if not GLOBAL_TOOL_ENVS_PATH.exists():
            return (
                '\n\b\n'
                '  ⚠  Tools not configured yet.\n'
                '     Quick setup:    fma setup\n'
                '     Install all:    fma prepare tools\n'
            )
        import yaml as _yaml
        cfg = _yaml.safe_load(GLOBAL_TOOL_ENVS_PATH.read_text()) or {}

        def _configured(t):
            c = cfg.get(t) or {}
            return bool(c.get('conda_env') or c.get('bin_dir') or c.get('script_path'))

        missing = [t for t in tools if not _configured(t)]
        if missing:
            return (
                '\n\b\n'
                f'  ⚠  Tools not yet configured: {", ".join(missing)}\n'
                '     Run: fma setup\n'
            )
        return '\n\b\n  ✓  All tools configured. Run `fma check` to verify.\n'
    except Exception:
        return ''


def main():
    cli.add_command(run)
    cli.add_command(prepare)
    cli.add_command(init)
    cli.add_command(check)
    cli.add_command(config_cmd)
    cli.add_command(setup)
    cli.epilog = __EPILOG__ + _tool_status_for_help()
    cli()


if __name__ == '__main__':
    main()
