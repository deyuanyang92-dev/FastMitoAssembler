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


def test_direct_single_sample_fastqs_are_forwarded():
    runner = _make_runner()
    args = [
        '--fq1', '/tmp/S1_R1.fq.gz',
        '--fq2', '/tmp/S1_R2.fq.gz',
        '--sample-name', 'S1',
        '--dryrun',
    ]
    with patch('snakemake.snakemake') as mock_smk, \
         patch('os.path.isfile', return_value=True):
        result = runner.invoke(run_cmd, args)
        assert result.exit_code == 0
        config = mock_smk.call_args[1]['config']
        assert config['samples'] == ['S1']
        assert config['sample_fastqs']['S1']['fq1'] == '/tmp/S1_R1.fq.gz'
        assert config['sample_fastqs']['S1']['fq2'] == '/tmp/S1_R2.fq.gz'


def test_direct_single_sample_requires_complete_trio():
    runner = _make_runner()
    result = runner.invoke(run_cmd, ['--fq1', '/tmp/S1_R1.fq.gz', '--dryrun'])
    assert result.exit_code != 0
    assert '--fq1, --fq2 and --sample_name' in result.output
