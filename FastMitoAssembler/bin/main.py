import os
import json

import yaml
import click
import snakemake

from FastMitoAssembler import MAIN_SMK, DEFAULT_CONFIG_FILE, DEFAULT_OPTION_FILE, VERSION, BANNER, CITATION
from FastMitoAssembler.bin._run import run, meangs, mg_get, mg_nov_get, getorganelle, mitoz
from FastMitoAssembler.bin._other import prepare


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

Citation: {CITATION}
''', fg='white').format(MAIN_SMK=MAIN_SMK, DEFAULT_CONFIG_FILE=DEFAULT_CONFIG_FILE, DEFAULT_OPTION_FILE=DEFAULT_OPTION_FILE, CITATION=CITATION, **VERSION)


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


def main():
    cli.add_command(run)
    cli.add_command(meangs)
    cli.add_command(mg_get)
    cli.add_command(mg_nov_get)
    cli.add_command(getorganelle)
    cli.add_command(mitoz)
    cli.add_command(prepare)
    cli()


if __name__ == '__main__':
    main()
