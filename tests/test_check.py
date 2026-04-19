import yaml
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner

from FastMitoAssembler.bin._check import check, load_tool_envs, GLOBAL_TOOL_ENVS_PATH


def test_check_runs_and_shows_table():
    runner = CliRunner()
    with patch('FastMitoAssembler.bin._check._run_probe', return_value=False):
        result = runner.invoke(check, [])
    assert result.exit_code == 0
    assert 'meangs' in result.output
    assert 'novoplasty' in result.output
    assert 'getorganelle' in result.output
    assert 'mitoz' in result.output


def test_check_shows_found_when_probe_succeeds():
    runner = CliRunner()
    with patch('FastMitoAssembler.bin._check._run_probe', return_value=True):
        result = runner.invoke(check, [])
    assert 'found' in result.output


def test_check_save_writes_global_config(tmp_path):
    runner = CliRunner()
    fake_global = tmp_path / 'tool_envs.yaml'
    with patch('FastMitoAssembler.bin._check.GLOBAL_TOOL_ENVS_PATH', fake_global), \
         patch('FastMitoAssembler.bin._check._run_probe', return_value=True):
        result = runner.invoke(check, ['--save'])
    assert result.exit_code == 0
    assert fake_global.exists()
    assert 'Saved' in result.output


def test_check_save_merges_not_overwrites(tmp_path):
    fake_global = tmp_path / 'tool_envs.yaml'
    existing = {'meangs': {'conda_env': 'my_meangs', 'bin_dir': ''}}
    fake_global.write_text(yaml.dump(existing))

    runner = CliRunner()
    with patch('FastMitoAssembler.bin._check.GLOBAL_TOOL_ENVS_PATH', fake_global), \
         patch('FastMitoAssembler.bin._check._run_probe', return_value=True):
        runner.invoke(check, ['--save'])

    saved = yaml.safe_load(fake_global.read_text())
    # existing entry should be preserved
    assert saved.get('meangs', {}).get('conda_env') == 'my_meangs'


def test_load_tool_envs_merges_global_and_project(tmp_path):
    fake_global = tmp_path / 'tool_envs.yaml'
    fake_global.write_text(yaml.dump({'mitoz': {'conda_env': 'global_mitoz', 'bin_dir': ''}}))

    project_envs = {'meangs': {'conda_env': 'proj_meangs', 'bin_dir': ''}}

    with patch('FastMitoAssembler.bin._check.GLOBAL_TOOL_ENVS_PATH', fake_global):
        merged = load_tool_envs(project_envs)

    assert merged['mitoz']['conda_env'] == 'global_mitoz'
    assert merged['meangs']['conda_env'] == 'proj_meangs'


def test_load_tool_envs_project_overrides_global(tmp_path):
    fake_global = tmp_path / 'tool_envs.yaml'
    fake_global.write_text(yaml.dump({'mitoz': {'conda_env': 'global_mitoz', 'bin_dir': ''}}))

    project_envs = {'mitoz': {'conda_env': 'project_mitoz', 'bin_dir': ''}}

    with patch('FastMitoAssembler.bin._check.GLOBAL_TOOL_ENVS_PATH', fake_global):
        merged = load_tool_envs(project_envs)

    assert merged['mitoz']['conda_env'] == 'project_mitoz'


def test_check_configfile_not_found_still_works():
    runner = CliRunner()
    with patch('FastMitoAssembler.bin._check._run_probe', return_value=False):
        result = runner.invoke(check, ['--configfile', 'nonexistent.yaml'])
    assert result.exit_code == 0
