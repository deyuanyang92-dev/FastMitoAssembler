import os
from click.testing import CliRunner
from FastMitoAssembler.bin._init import init


def test_init_creates_config(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(init, [])
        assert result.exit_code == 0
        assert os.path.isfile('config.yaml')
        assert 'created' in result.output


def test_init_with_options_flag(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(init, ['--options'])
        assert result.exit_code == 0
        assert os.path.isfile('config.yaml')
        assert os.path.isfile('options.yaml')


def test_init_custom_output_name(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(init, ['-o', 'myproject.yaml'])
        assert result.exit_code == 0
        assert os.path.isfile('myproject.yaml')


def test_init_force_overwrites(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(init, [])
        result = runner.invoke(init, ['--force'])
        assert result.exit_code == 0
        assert 'created' in result.output


def test_init_prompts_on_existing(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(init, [])
        result = runner.invoke(init, [], input='n\n')
        assert result.exit_code == 0
        assert 'skipped' in result.output
