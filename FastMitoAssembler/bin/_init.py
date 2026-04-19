import shutil

import click

from FastMitoAssembler import DEFAULT_CONFIG_FILE, DEFAULT_OPTION_FILE


def _copy_file(src, dest, force):
    if dest.exists() and not force:
        if not click.confirm(f'"{dest}" already exists, overwrite?'):
            click.secho(f'  skipped: {dest}', fg='yellow')
            return
    shutil.copy(src, dest)
    click.secho(f'  created: {dest}', fg='green')


@click.command(help=click.style('generate config files in current directory', fg='cyan', bold=True))
@click.option('-o', '--output', 'config_output',
              default='config.yaml',
              show_default=True,
              help='output filename for config.yaml')
@click.option('--options', 'gen_options', is_flag=True,
              help='also generate options.yaml')
@click.option('-f', '--force', is_flag=True,
              help='overwrite existing files without prompting')
def init(config_output, gen_options, force):
    from pathlib import Path
    dest = Path(config_output)
    _copy_file(DEFAULT_CONFIG_FILE, dest, force)
    if gen_options:
        _copy_file(DEFAULT_OPTION_FILE, Path('options.yaml'), force)
