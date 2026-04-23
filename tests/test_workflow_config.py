from unittest.mock import patch

from FastMitoAssembler.bin._workflow import _build_configs, _configure_direct_fastqs


def test_meangs_path_maps_to_tool_envs(tmp_path):
    script = tmp_path / 'meangs.py'
    script.write_text('#!/usr/bin/env python\n')
    with patch('FastMitoAssembler.bin._workflow.load_tool_envs', return_value={}):
        config = _build_configs({'meangs_path': str(script)})
    assert config['tool_envs']['meangs']['script_path'] == str(script)


def test_direct_fastqs_set_sample_fastqs(tmp_path):
    fq1 = tmp_path / 'S1_R1.fq.gz'
    fq2 = tmp_path / 'S1_R2.fq.gz'
    config = _configure_direct_fastqs({
        'reads_dir': None,
        'fq1': str(fq1),
        'fq2': str(fq2),
        'sample_name': 'S1',
    })
    assert config['samples'] == ['S1']
    assert config['reads_dir'] == str(tmp_path)
    assert config['sample_fastqs']['S1']['fq1'] == str(fq1.resolve())
    assert config['sample_fastqs']['S1']['fq2'] == str(fq2.resolve())
