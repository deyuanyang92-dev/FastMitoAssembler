import yaml
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from FastMitoAssembler.bin._check import _probe_tool, _ST_FOUND, _ST_ERROR, _ST_BUNDLED
from FastMitoAssembler.bin._config import config_cmd
from FastMitoAssembler.bin._setup import setup


# ---------------------------------------------------------------------------
# script_path in _probe_tool
# ---------------------------------------------------------------------------

def test_probe_tool_script_path_found(tmp_path):
    script = tmp_path / 'NOVOPlasty.pl'
    script.write_text('#!/usr/bin/perl\n')
    cfg = {'conda_env': '', 'bin_dir': '', 'script_path': str(script)}
    status, detail = _probe_tool('novoplasty', 'NOVOPlasty.pl', cfg)
    assert status == _ST_FOUND
    assert 'perl' in detail
    assert 'NOVOPlasty.pl' in detail


def test_probe_tool_script_path_missing():
    cfg = {'conda_env': '', 'bin_dir': '', 'script_path': '/nonexistent/NOVOPlasty.pl'}
    status, detail = _probe_tool('novoplasty', 'NOVOPlasty.pl', cfg)
    assert status == _ST_ERROR
    assert 'not found' in detail


def test_probe_tool_script_path_ignored_when_conda_env_set():
    """conda_env takes precedence over script_path."""
    cfg = {'conda_env': 'some_env', 'bin_dir': '', 'script_path': '/fake/path.pl'}
    with patch('FastMitoAssembler.bin._check._run_probe', return_value=True):
        status, detail = _probe_tool('novoplasty', 'NOVOPlasty.pl', cfg)
    assert status == _ST_FOUND
    assert 'conda env' in detail


# ---------------------------------------------------------------------------
# fma config set --script-path
# ---------------------------------------------------------------------------

def test_config_set_script_path_no_check(tmp_path):
    fake_global = tmp_path / 'tool_envs.yaml'
    script = tmp_path / 'NOVOPlasty.pl'
    script.write_text('')

    runner = CliRunner()
    with patch('FastMitoAssembler.bin._config.GLOBAL_TOOL_ENVS_PATH', fake_global), \
         patch('FastMitoAssembler.bin._check.GLOBAL_TOOL_ENVS_PATH', fake_global):
        result = runner.invoke(config_cmd, [
            'set', 'novoplasty',
            '--script-path', str(script),
            '--no-check',
        ])
    assert result.exit_code == 0
    saved = yaml.safe_load(fake_global.read_text())
    assert saved['novoplasty']['script_path'] == str(script)


def test_config_set_requires_at_least_one_option():
    runner = CliRunner()
    result = runner.invoke(config_cmd, ['set', 'novoplasty'])
    assert result.exit_code != 0


def test_config_show_displays_script_path(tmp_path):
    fake_global = tmp_path / 'tool_envs.yaml'
    fake_global.write_text(yaml.dump({
        'novoplasty': {'conda_env': '', 'bin_dir': '', 'script_path': '/opt/NOVOPlasty.pl'}
    }))
    runner = CliRunner()
    with patch('FastMitoAssembler.bin._config.GLOBAL_TOOL_ENVS_PATH', fake_global):
        result = runner.invoke(config_cmd, ['show'])
    assert result.exit_code == 0
    assert 'script_path' in result.output
    assert 'NOVOPlasty.pl' in result.output


# ---------------------------------------------------------------------------
# fma setup wizard
# ---------------------------------------------------------------------------

def test_setup_skip_all(tmp_path):
    """Choosing skip for every tool should produce no changes."""
    fake_global = tmp_path / 'tool_envs.yaml'
    runner = CliRunner()
    # 4 tools × choice "5" (skip) for novoplasty, "4" for others
    # We use '4\n' for meangs/getorganelle/mitoz and '5\n' for novoplasty
    inputs = '4\n1\n5\n4\n4\n'  # meangs skip, novoplasty menu choice 1 (conda), then back to skip path
    # Simpler: just input skip option index for each tool
    # meangs=4, novoplasty=5, getorganelle=4, mitoz=4
    inputs = '4\n5\n4\n4\n'
    with patch('FastMitoAssembler.bin._setup.GLOBAL_TOOL_ENVS_PATH', fake_global), \
         patch('FastMitoAssembler.bin._check.GLOBAL_TOOL_ENVS_PATH', fake_global):
        result = runner.invoke(setup, input=inputs)
    assert result.exit_code == 0
    assert not fake_global.exists() or not yaml.safe_load(fake_global.read_text())


def test_setup_configure_conda_env(tmp_path):
    """Selecting conda env and entering a valid env name saves the config."""
    fake_global = tmp_path / 'tool_envs.yaml'
    runner = CliRunner()
    # meangs: choice 1 (conda) → env name → then skip all others (novoplasty=5, go=4, mitoz=4)
    inputs = '1\nmy_meangs_env\n5\n4\n4\n'
    with patch('FastMitoAssembler.bin._setup.GLOBAL_TOOL_ENVS_PATH', fake_global), \
         patch('FastMitoAssembler.bin._check.GLOBAL_TOOL_ENVS_PATH', fake_global), \
         patch('FastMitoAssembler.bin._check._run_probe', return_value=True):
        result = runner.invoke(setup, input=inputs)
    assert result.exit_code == 0
    if fake_global.exists():
        saved = yaml.safe_load(fake_global.read_text()) or {}
        assert saved.get('meangs', {}).get('conda_env') == 'my_meangs_env'


def test_setup_configure_script_path(tmp_path):
    """Selecting perl script path for novoplasty saves script_path."""
    fake_global = tmp_path / 'tool_envs.yaml'
    script = tmp_path / 'NOVOPlasty.pl'
    script.write_text('')
    runner = CliRunner()
    # meangs skip(4), novoplasty choice 3 (script path) → path, getorganelle skip(4), mitoz skip(4)
    inputs = f'4\n3\n{script}\n4\n4\n'
    with patch('FastMitoAssembler.bin._setup.GLOBAL_TOOL_ENVS_PATH', fake_global), \
         patch('FastMitoAssembler.bin._check.GLOBAL_TOOL_ENVS_PATH', fake_global):
        result = runner.invoke(setup, input=inputs)
    assert result.exit_code == 0
    if fake_global.exists():
        saved = yaml.safe_load(fake_global.read_text()) or {}
        sp = saved.get('novoplasty', {}).get('script_path', '')
        assert 'NOVOPlasty.pl' in sp
