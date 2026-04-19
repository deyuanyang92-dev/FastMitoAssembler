
import click

from FastMitoAssembler import util, BASE_DIR

ORGANELLE_DB_LIST = ['all', 'embplant_pt', 'embplant_mt', 'embplant_nr', 'fungus_mt', 'fungus_nr', 'animal_mt', 'other_pt']
GETORGANELLE_ENV_NAME = 'FastMitoAssembler-getorganelle'
GETORGANELLE_ENV_YAML = BASE_DIR / 'smk' / 'envs' / 'getorganelle.yaml'

NCBI_TAXDUMP = 'https://ftp.ncbi.nih.gov/pub/taxonomy/taxdump.tar.gz'

@click.group(help=click.style('prepare database', fg='cyan', bold=True))
def prepare():
    pass


@prepare.command(help='prepare ete3.NCBITaxa')
@click.option('--taxdump_file', help=f'the taxdump file of NCBI, you can mamually download it from: {NCBI_TAXDUMP}')
def ncbitaxa(**kwargs):
    import ete3
    print('preparing ete3.NCBITaxa ...')
    ete3.NCBITaxa(taxdump_file=kwargs['taxdump_file'])
    print('ete3.NCBITaxa is ok!')


def _get_organelle_runner():
    """Return a shell prefix to run get_organelle_config.py.

    Tries current PATH first. If not found, auto-creates a dedicated conda
    env from the bundled getorganelle.yaml so the user never has to do it manually.
    """
    status, _ = util.getstatusoutput('get_organelle_config.py --version')
    if status == 0:
        return ''

    # Not in current PATH — check if the auto-created env already exists
    status, _ = util.getstatusoutput(
        f'conda run -n {GETORGANELLE_ENV_NAME} get_organelle_config.py --version')
    if status == 0:
        return f'conda run -n {GETORGANELLE_ENV_NAME} '

    # Create the env automatically from the bundled yaml
    click.secho(
        f'GetOrganelle not found. Creating conda environment "{GETORGANELLE_ENV_NAME}" automatically...',
        fg='yellow', err=True)
    status, output = util.getstatusoutput(
        f'conda env create -n {GETORGANELLE_ENV_NAME} -f {GETORGANELLE_ENV_YAML}')
    if status != 0:
        click.secho(f'Failed to create environment:\n{output}', fg='red', err=True)
        raise click.Abort()

    click.secho(f'Environment "{GETORGANELLE_ENV_NAME}" created.', fg='green', err=True)
    return f'conda run -n {GETORGANELLE_ENV_NAME} '


@prepare.command(help='prepare database for GetOrganelle', no_args_is_help=True)
@click.option('-a', '--add',
              help='add database for organelle type(s)',
              type=click.Choice(ORGANELLE_DB_LIST),
              show_choices=True,
              default=['animal_mt'],
              show_default=True,
              multiple=True,
)
@click.option('--list', help='list configured databases checking and exit', is_flag=True)
def organelle(**kwargs):
    runner = _get_organelle_runner()

    status, output = util.getstatusoutput(f'{runner}get_organelle_config.py --list')
    configured_dbs = set([db.split()[0] for db in output.strip().split('\n') if db])
    if configured_dbs:
        click.secho(f'configured databases:\n{output}', fg='cyan')
    else:
        click.secho(f'no configured databases', fg='yellow')

    if not kwargs['list']:
        databases = ORGANELLE_DB_LIST[1:] if 'all' in kwargs['add'] else kwargs['add']
        for database in databases:
            if database in configured_dbs:
                if not click.confirm(f'"{database}" alreay configured, overwrite it?'):
                    continue
            click.secho(f'preparing database for GetOrganelle: {database}', fg='green')
            status, output = util.getstatusoutput(
                f'{runner}get_organelle_config.py --add {database}')
            click.secho(output)
