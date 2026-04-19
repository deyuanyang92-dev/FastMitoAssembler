import os
from FastMitoAssembler.bin._run import _detect_samples


def _make_reads(tmp_path, files):
    for f in files:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()


def test_detect_single_suffix(tmp_path):
    _make_reads(tmp_path, [
        'S1/S1_1.clean.fq.gz',
        'S2/S2_1.clean.fq.gz',
    ])
    samples = _detect_samples(str(tmp_path), '_1.clean.fq.gz,_2.clean.fq.gz')
    assert samples == ['S1', 'S2']


def test_detect_multiple_suffix_pairs(tmp_path):
    _make_reads(tmp_path, [
        'S1/S1_1.clean.fq.gz',
        'S2/S2_R1.fastq.gz',
    ])
    samples = _detect_samples(str(tmp_path), '_1.clean.fq.gz,_2.clean.fq.gz;_R1.fastq.gz,_R2.fastq.gz')
    assert 'S1' in samples
    assert 'S2' in samples


def test_detect_flat_layout(tmp_path):
    _make_reads(tmp_path, [
        'SampleA_1.clean.fq.gz',
        'SampleB_1.clean.fq.gz',
    ])
    samples = _detect_samples(str(tmp_path), '_1.clean.fq.gz,_2.clean.fq.gz')
    assert 'SampleA' in samples
    assert 'SampleB' in samples


def test_detect_deduplicates(tmp_path):
    _make_reads(tmp_path, ['S1/S1_1.clean.fq.gz'])
    samples = _detect_samples(str(tmp_path), '_1.clean.fq.gz,_2.clean.fq.gz;_1.clean.fq.gz,_2.clean.fq.gz')
    assert samples.count('S1') == 1


def test_detect_empty_when_no_match(tmp_path):
    _make_reads(tmp_path, ['S1/S1_R1.fastq.gz'])
    samples = _detect_samples(str(tmp_path), '_1.clean.fq.gz,_2.clean.fq.gz')
    assert samples == []
