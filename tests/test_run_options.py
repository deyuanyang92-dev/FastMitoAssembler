from unittest.mock import patch
from click.testing import CliRunner
from FastMitoAssembler.bin._run import run as run_cmd


def _make_runner():
    return CliRunner()


def _base_args():
    return [
        '--reads_dir', '/tmp/reads',
        '--samples', 'S1',
        '--dryrun',
    ]


def test_use_conda_true_by_default():
    runner = _make_runner()
    with patch('snakemake.snakemake') as mock_smk, \
         patch('os.path.isfile', return_value=True):
        runner.invoke(run_cmd, _base_args())
        call_kwargs = mock_smk.call_args[1]
        assert call_kwargs.get('use_conda') is True, \
            f"use_conda should default to True, got: {call_kwargs}"


def test_no_use_conda_flag_disables():
    runner = _make_runner()
    with patch('snakemake.snakemake') as mock_smk, \
         patch('os.path.isfile', return_value=True):
        runner.invoke(run_cmd, _base_args() + ['--no-use-conda'])
        call_kwargs = mock_smk.call_args[1]
        assert call_kwargs.get('use_conda') is False


def test_conda_prefix_passed_when_provided():
    runner = _make_runner()
    with patch('snakemake.snakemake') as mock_smk, \
         patch('os.path.isfile', return_value=True):
        runner.invoke(run_cmd, _base_args() + ['--conda-prefix', '/shared/envs'])
        call_kwargs = mock_smk.call_args[1]
        assert call_kwargs.get('conda_prefix') == '/shared/envs'


def test_conda_prefix_absent_when_not_provided():
    runner = _make_runner()
    with patch('snakemake.snakemake') as mock_smk, \
         patch('os.path.isfile', return_value=True):
        runner.invoke(run_cmd, _base_args())
        call_kwargs = mock_smk.call_args[1]
        assert 'conda_prefix' not in call_kwargs or call_kwargs['conda_prefix'] is None
