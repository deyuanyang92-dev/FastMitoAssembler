from pathlib import Path
from unittest.mock import patch

from FastMitoAssembler.report import generate_mm_report, _detect_version, _make_prefix


# ---------------------------------------------------------------------------
# _make_prefix
# ---------------------------------------------------------------------------

def test_make_prefix_bin_dir():
    tool_envs = {'mitoz': {'bin_dir': '/opt/mitoz/bin', 'conda_env': ''}}
    assert _make_prefix('mitoz', tool_envs) == 'PATH="/opt/mitoz/bin:$PATH" '


def test_make_prefix_no_bin_dir():
    tool_envs = {'mitoz': {'bin_dir': '', 'conda_env': 'my_env'}}
    assert _make_prefix('mitoz', tool_envs) == ''


def test_make_prefix_missing_tool():
    assert _make_prefix('novoplasty', {}) == ''


# ---------------------------------------------------------------------------
# _detect_version
# ---------------------------------------------------------------------------

def test_detect_version_extracts_number():
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.stdout = 'GetOrganelle v1.7.7.0\n'
        ver = _detect_version('getorganelle', 'get_organelle_from_reads.py --version')
    assert ver == '1.7.7.0'


def test_detect_version_returns_na_on_failure():
    with patch('subprocess.run', side_effect=Exception('not found')):
        ver = _detect_version('mitoz', 'mitoz version')
    assert ver == 'N/A'


def test_detect_version_returns_na_when_no_version_string():
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.stdout = 'some output with no version\n'
        ver = _detect_version('meangs', 'meangs.py --version')
    assert ver == 'N/A'


# ---------------------------------------------------------------------------
# generate_mm_report
# ---------------------------------------------------------------------------

_SAMPLE_CONFIG = {
    'read_length': 150,
    'insert_size': 300,
    'meangs_reads': 2000000,
    'meangs_deepin': True,
    'kmer_size': 33,
    'genome_min_size': 12000,
    'genome_max_size': 22000,
    'max_mem_gb': 10,
    'organelle_database': 'animal_mt',
    'genetic_code': 5,
    'clade': 'Annelida-segmented-worms',
}


def test_generate_mm_report_creates_file(tmp_path):
    out = tmp_path / 'sample1' / 'materials_and_methods.md'
    with patch('FastMitoAssembler.report._detect_version', return_value='1.0.0'):
        generate_mm_report(out, 'sample1', _SAMPLE_CONFIG)
    assert out.exists()


def test_generate_mm_report_contains_english_and_chinese(tmp_path):
    out = tmp_path / 'mm.md'
    with patch('FastMitoAssembler.report._detect_version', return_value='N/A'):
        generate_mm_report(out, 'sample1', _SAMPLE_CONFIG)
    text = out.read_text(encoding='utf-8')
    assert 'Materials and Methods' in text
    assert '材料与方法' in text


def test_generate_mm_report_contains_key_params(tmp_path):
    out = tmp_path / 'mm.md'
    with patch('FastMitoAssembler.report._detect_version', return_value='N/A'):
        generate_mm_report(out, 'sample1', _SAMPLE_CONFIG)
    text = out.read_text(encoding='utf-8')
    assert 'animal_mt' in text
    assert 'Annelida-segmented-worms' in text
    assert '150' in text
    assert '33' in text


def test_generate_mm_report_deep_assembly_flag(tmp_path):
    out = tmp_path / 'mm.md'
    cfg = {**_SAMPLE_CONFIG, 'meangs_deepin': True}
    with patch('FastMitoAssembler.report._detect_version', return_value='N/A'):
        generate_mm_report(out, 'sample1', cfg)
    text = out.read_text(encoding='utf-8')
    assert 'deep assembly enabled' in text
    assert '深度组装' in text


def test_generate_mm_report_standard_mode_flag(tmp_path):
    out = tmp_path / 'mm.md'
    cfg = {**_SAMPLE_CONFIG, 'meangs_deepin': False}
    with patch('FastMitoAssembler.report._detect_version', return_value='N/A'):
        generate_mm_report(out, 'sample1', cfg)
    text = out.read_text(encoding='utf-8')
    assert 'standard mode' in text
    assert '标准模式' in text


def test_generate_mm_report_contains_citations(tmp_path):
    out = tmp_path / 'mm.md'
    with patch('FastMitoAssembler.report._detect_version', return_value='N/A'):
        generate_mm_report(out, 'sample1', _SAMPLE_CONFIG)
    text = out.read_text(encoding='utf-8')
    assert 'NOVOPlasty' in text
    assert 'GetOrganelle' in text
    assert 'MitoZ' in text
    assert 'MEANGS' in text
    assert 'doi.org' in text


def test_generate_mm_report_creates_parent_dirs(tmp_path):
    out = tmp_path / 'deep' / 'nested' / 'dir' / 'mm.md'
    with patch('FastMitoAssembler.report._detect_version', return_value='N/A'):
        generate_mm_report(out, 'sample1', _SAMPLE_CONFIG)
    assert out.exists()
