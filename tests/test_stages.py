"""Tests for FastMitoAssembler.bin._stages – stage CLI commands."""

import pytest
import click
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, call

from FastMitoAssembler.bin._stages import (
    _run_stage,
    meangs,
    novoplasty,
    getorganelle,
    mitoz,
    mg_nov,
    mg_get,
    mg_nov_get,
    mg_mt_nr,
    summary,
    spades,
    busco,
    multiqc,
    fsb_all,
    STAGE_COMMANDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_runner():
    return CliRunner()


def _base_args():
    """Minimal CLI arguments accepted by common_workflow_options."""
    return [
        '--reads_dir', '/tmp/reads',
        '--samples', 'S1',
        '--dryrun',
    ]


# ===========================================================================
# 1. STAGE_COMMANDS list tests
# ===========================================================================


class TestStageCommandsList:
    """Tests for the STAGE_COMMANDS collection."""

    def test_has_exactly_thirteen_commands(self):
        assert len(STAGE_COMMANDS) == 13

    def test_all_elements_are_click_commands(self):
        for cmd in STAGE_COMMANDS:
            assert isinstance(cmd, click.Command), (
                f"{cmd!r} is not a click command"
            )


# ===========================================================================
# 2. Command name / identity tests
# ===========================================================================


class TestCommandNames:
    """Each stage command must have the correct click name."""

    @pytest.mark.parametrize("cmd,expected_name", [
        (meangs, 'meangs'),
        (novoplasty, 'novoplasty'),
        (getorganelle, 'getorganelle'),
        (mitoz, 'mitoz'),
        (mg_nov, 'mg-nov'),
        (mg_get, 'mg-get'),
        (mg_nov_get, 'mg-nov-get'),
        (summary, 'summary'),
        (spades, 'spades'),
        (busco, 'busco'),
        (multiqc, 'multiqc'),
        (fsb_all, 'fsb-all'),
    ])
    def test_command_name(self, cmd, expected_name):
        assert cmd.name == expected_name


# ===========================================================================
# 3. run_workflow dispatch tests – one per stage
# ===========================================================================


class TestMeangsStage:
    """meangs → target='meangs_all', overrides contain default MEANGS params."""

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_target_and_overrides(self, mock_rw):
        runner = _make_runner()
        runner.invoke(meangs, _base_args())
        mock_rw.assert_called_once()
        args, kwargs = mock_rw.call_args
        assert kwargs.get('target') == 'meangs_all'
        # MEANGS now passes default config values
        overrides = kwargs.get('config_overrides', {})
        assert 'meangs_deepin' in overrides
        assert 'meangs_insert_size' in overrides
        assert 'meangs_species_class' in overrides

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_exit_code_zero_on_success(self, mock_rw):
        mock_rw.return_value = True
        runner = _make_runner()
        result = runner.invoke(meangs, _base_args())
        assert result.exit_code == 0


class TestNovoplastyStage:
    """novoplasty → target='novoplasty_all', overrides={'novoplasty_seed_source': 'user'}."""

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_target_and_overrides(self, mock_rw):
        runner = _make_runner()
        runner.invoke(novoplasty, _base_args())
        mock_rw.assert_called_once()
        args, kwargs = mock_rw.call_args
        assert kwargs.get('target') == 'novoplasty_all'
        assert kwargs.get('config_overrides') == {'novoplasty_seed_source': 'user'}


class TestGetorganelleStage:
    """getorganelle → target='getorganelle_all', overrides={'getorganelle_seed_source': 'none'}."""

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_target_and_overrides(self, mock_rw):
        runner = _make_runner()
        runner.invoke(getorganelle, _base_args())
        mock_rw.assert_called_once()
        args, kwargs = mock_rw.call_args
        assert kwargs.get('target') == 'getorganelle_all'
        assert kwargs.get('config_overrides') == {'getorganelle_seed_source': 'none'}


class TestMitozStage:
    """mitoz → target='mitoz_all', overrides=None."""

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_target_and_overrides(self, mock_rw):
        runner = _make_runner()
        runner.invoke(mitoz, _base_args())
        mock_rw.assert_called_once()
        args, kwargs = mock_rw.call_args
        assert kwargs.get('target') == 'mitoz_all'
        assert kwargs.get('config_overrides') == {}


class TestMgNovStage:
    """mg_nov → target='mg_nov_all', overrides={'novoplasty_seed_source': 'meangs'}."""

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_target_and_overrides(self, mock_rw):
        runner = _make_runner()
        runner.invoke(mg_nov, _base_args())
        mock_rw.assert_called_once()
        args, kwargs = mock_rw.call_args
        assert kwargs.get('target') == 'mg_nov_all'
        assert kwargs.get('config_overrides') == {'novoplasty_seed_source': 'meangs'}


class TestMgGetStage:
    """mg_get → target='mg_get_all', overrides={'getorganelle_seed_source': 'meangs'}."""

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_target_and_overrides(self, mock_rw):
        runner = _make_runner()
        runner.invoke(mg_get, _base_args())
        mock_rw.assert_called_once()
        args, kwargs = mock_rw.call_args
        assert kwargs.get('target') == 'mg_get_all'
        assert kwargs.get('config_overrides') == {'getorganelle_seed_source': 'meangs'}


class TestMgNovGetStage:
    """mg_nov_get → target='mg_nov_get_all', overrides with two keys."""

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_target_and_overrides(self, mock_rw):
        runner = _make_runner()
        runner.invoke(mg_nov_get, _base_args())
        mock_rw.assert_called_once()
        args, kwargs = mock_rw.call_args
        assert kwargs.get('target') == 'mg_nov_get_all'
        expected_overrides = {
            'novoplasty_seed_source': 'meangs',
            'getorganelle_seed_source': 'novoplasty',
        }
        assert kwargs.get('config_overrides') == expected_overrides


class TestSummaryStage:
    """summary → target='summary_all', overrides=None."""

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_target_and_overrides(self, mock_rw):
        runner = _make_runner()
        runner.invoke(summary, _base_args())
        mock_rw.assert_called_once()
        args, kwargs = mock_rw.call_args
        assert kwargs.get('target') == 'summary_all'
        assert kwargs.get('config_overrides') == {}


# ===========================================================================
# 4. _run_stage direct tests
# ===========================================================================


class TestRunStageHelper:
    """Direct unit tests for _run_stage."""

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_passes_kwargs_through(self, mock_rw):
        kwargs = {'reads_dir': '/data', 'samples': ('S1',), 'cores': 4}
        _run_stage(kwargs, 'some_target')
        mock_rw.assert_called_once()
        args, call_kwargs = mock_rw.call_args
        # First positional arg should be the kwargs dict
        assert args[0] is kwargs

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_passes_target(self, mock_rw):
        _run_stage({}, 'my_target')
        _, call_kwargs = mock_rw.call_args
        assert call_kwargs['target'] == 'my_target'

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_overrides_default_to_empty_dict(self, mock_rw):
        _run_stage({}, 't')
        _, call_kwargs = mock_rw.call_args
        assert call_kwargs['config_overrides'] == {}

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_overrides_passed_through(self, mock_rw):
        overrides = {'key': 'value'}
        _run_stage({}, 't', overrides)
        _, call_kwargs = mock_rw.call_args
        assert call_kwargs['config_overrides'] is overrides

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_return_value_forwarded(self, mock_rw):
        mock_rw.return_value = True
        result = _run_stage({}, 't')
        assert result is True
        mock_rw.return_value = False
        result = _run_stage({}, 't')
        assert result is False


# ===========================================================================
# 5. CLI no-args help tests
# ===========================================================================


class TestNoArgsIsHelp:
    """Every stage command has no_args_is_help=True and exits with 0."""

    @pytest.mark.parametrize("cmd", STAGE_COMMANDS)
    def test_no_args_shows_help(self, cmd):
        runner = _make_runner()
        result = runner.invoke(cmd, [])
        # Click's no_args_is_help triggers a SystemExit(2) by default
        assert result.exit_code == 2
        assert 'Usage' in result.output


# ===========================================================================
# 6. kwargs forwarding from CLI to run_workflow
# ===========================================================================


class TestKwargsForwarding:
    """CLI options should flow through kwargs to run_workflow."""

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_dryrun_flag_forwarded(self, mock_rw):
        runner = _make_runner()
        runner.invoke(meangs, _base_args())
        args, kwargs = mock_rw.call_args
        assert args[0]['dryrun'] is True

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_reads_dir_forwarded(self, mock_rw):
        runner = _make_runner()
        runner.invoke(meangs, ['--reads_dir', '/data/fastq', '--samples', 'X', '--dryrun'])
        args, kwargs = mock_rw.call_args
        assert args[0]['reads_dir'] == '/data/fastq'

    @patch('FastMitoAssembler.bin._stages.run_workflow')
    def test_multiple_samples_forwarded(self, mock_rw):
        runner = _make_runner()
        runner.invoke(meangs, [
            '--reads_dir', '/data',
            '--samples', 'A',
            '--samples', 'B',
            '--dryrun',
        ])
        args, kwargs = mock_rw.call_args
        assert args[0]['samples'] == ('A', 'B')
