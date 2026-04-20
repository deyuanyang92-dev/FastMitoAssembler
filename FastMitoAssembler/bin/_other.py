
import click

from FastMitoAssembler import util, BASE_DIR

ORGANELLE_DB_LIST = ['all', 'embplant_pt', 'embplant_mt', 'embplant_nr', 'fungus_mt', 'fungus_nr', 'animal_mt', 'other_pt']
GETORGANELLE_ENV_NAME = 'FastMitoAssembler-getorganelle'
GETORGANELLE_ENV_YAML = BASE_DIR / 'smk' / 'envs' / 'getorganelle.yaml'

NCBI_TAXDUMP = 'https://ftp.ncbi.nih.gov/pub/taxonomy/taxdump.tar.gz'

# Named conda environments for each tool (created by `fma prepare tools`)
TOOL_ENVS = {
    'meangs':       ('FastMitoAssembler-meangs',       'meangs.yaml'),
    'novoplasty':   ('FastMitoAssembler-novoplasty',   'novoplasty.yaml'),
    'getorganelle': ('FastMitoAssembler-getorganelle', 'getorganelle.yaml'),
    'mitoz':        ('FastMitoAssembler-mitoz',        'mitoz.yaml'),
}

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


def _conda_env_exists(env_name):
    status, _ = util.getstatusoutput(f'conda env list 2>/dev/null | grep -q "^{env_name} "')
    return status == 0


@prepare.command('tools', help='create dedicated conda environments for all bioinformatics tools')
@click.option('--force', is_flag=True, help='remove and recreate an environment if it already exists')
@click.option('--save/--no-save', default=True, show_default=True,
              help='save created env names to global config (~/.config/FastMitoAssembler/tool_envs.yaml)')
@click.option('--tool', 'selected',
              type=click.Choice(list(TOOL_ENVS.keys())),
              multiple=True,
              help='install only specific tools (default: all)')
def prepare_tools(force, save, selected):
    """Create named conda environments for MEANGS, NOVOPlasty, GetOrganelle and MitoZ.

    Each tool is installed into its own isolated environment so upgrading one
    tool never breaks the others.  After creation the env names are saved
    globally so every subsequent `fma run` uses them automatically.
    """
    from FastMitoAssembler.bin._check import GLOBAL_TOOL_ENVS_PATH
    import yaml as _yaml

    tools_to_build = list(selected) if selected else list(TOOL_ENVS.keys())

    click.secho('\nInstalling tool environments...\n', bold=True)

    created = {}
    for tool in tools_to_build:
        env_name, yaml_name = TOOL_ENVS[tool]
        env_yaml = BASE_DIR / 'smk' / 'envs' / yaml_name

        if _conda_env_exists(env_name) and not force:
            click.secho(f'  {tool:<16} ✓ already exists  ({env_name})', fg='green')
            created[tool] = env_name
            continue

        if force and _conda_env_exists(env_name):
            click.secho(f'  {tool:<16} removing old env...', fg='yellow')
            util.getstatusoutput(f'conda env remove -n {env_name} -y')

        click.secho(f'  {tool:<16} creating {env_name} ...', fg='cyan')
        # prefer mamba for speed, fall back to conda
        for installer in ('mamba', 'conda'):
            st, _ = util.getstatusoutput(f'which {installer}')
            if st == 0:
                break
        status, output = util.getstatusoutput(
            f'{installer} env create -n {env_name} -f {env_yaml} 2>&1'
        )
        if status == 0:
            click.secho(f'  {tool:<16} ✓ done  ({env_name})', fg='green')
            created[tool] = env_name
        else:
            click.secho(f'  {tool:<16} ✗ failed\n{output}', fg='red')

    click.echo()

    if save and created:
        existing = {}
        if GLOBAL_TOOL_ENVS_PATH.exists():
            existing = util.read_yaml(GLOBAL_TOOL_ENVS_PATH) or {}
        for tool, env_name in created.items():
            existing[tool] = {'conda_env': env_name, 'bin_dir': ''}
        GLOBAL_TOOL_ENVS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(GLOBAL_TOOL_ENVS_PATH, 'w') as f:
            _yaml.dump(existing, f, default_flow_style=False, allow_unicode=True)
        click.secho(f'Tool configs saved to {GLOBAL_TOOL_ENVS_PATH}', fg='green')
        click.secho(
            'All future `fma run` calls will use these environments automatically.',
            fg='cyan',
        )
    elif not created:
        click.secho('No environments were created.', fg='yellow')
