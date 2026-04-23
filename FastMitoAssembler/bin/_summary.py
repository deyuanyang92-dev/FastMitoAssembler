import gzip
from pathlib import Path


SUMMARY_COLUMNS = [
    'sample',
    'software',
    'pipeline',
    'locus',
    'source_file',
    'record_id',
    'length',
    'gc_percent',
    'n_count',
    'topology',
    'status',
    'output_fasta',
    'notes',
]


def _open_text(path):
    path = Path(path)
    if path.suffix == '.gz':
        return gzip.open(path, 'rt')
    return path.open('r')


def parse_fasta(path):
    name = None
    desc = ''
    seq_parts = []
    with _open_text(path) as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith('>'):
                if name is not None:
                    yield name, desc, ''.join(seq_parts)
                desc = line[1:].strip()
                name = desc.split()[0] if desc else ''
                seq_parts = []
            else:
                seq_parts.append(line)
    if name is not None:
        yield name, desc, ''.join(seq_parts)


def _write_record(handle, header, seq, width=80):
    handle.write(f'>{header}\n')
    for i in range(0, len(seq), width):
        handle.write(seq[i:i + width] + '\n')


def infer_topology(record_id, description):
    text = f'{record_id} {description}'.lower()
    if 'circular' in text or ' topology=circular' in text or 'topology|circular' in text:
        return 'circular'
    if 'linear' in text or 'scaffold' in text or ' topology=linear' in text:
        return 'linear'
    return 'unknown'


def infer_locus(default_locus, software, pipeline):
    if default_locus:
        return default_locus
    text = f'{software} {pipeline}'.lower()
    if 'nr' in text:
        return 'nr'
    return 'unknown'


def sequence_stats(seq):
    seq = (seq or '').upper()
    length = len(seq)
    gc = seq.count('G') + seq.count('C')
    n_count = seq.count('N')
    gc_percent = round(gc * 100 / length, 4) if length else 0
    return length, gc_percent, n_count


def collect_fasta(input_path, output_path, sample, software, pipeline, locus='unknown', min_length=0):
    """Normalize one tool/pipeline FASTA into FastMitoAssembler summary format."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    if input_path.exists():
        for idx, (record_id, desc, seq) in enumerate(parse_fasta(input_path), start=1):
            length, gc_percent, n_count = sequence_stats(seq)
            if length < int(min_length or 0):
                continue
            topology = infer_topology(record_id, desc)
            out_locus = infer_locus(locus, software, pipeline)
            header = (
                f'{sample}|software={software}|pipeline={pipeline}|locus={out_locus}|'
                f'idx={idx}|topology={topology}|length={length}'
            )
            records.append((header, seq, {
                'sample': sample,
                'software': software,
                'pipeline': pipeline,
                'locus': out_locus,
                'source_file': str(input_path),
                'record_id': record_id,
                'length': str(length),
                'gc_percent': str(gc_percent),
                'n_count': str(n_count),
                'topology': topology,
                'status': 'ok',
                'output_fasta': str(output_path),
                'notes': '',
            }))

    with output_path.open('w') as out:
        for header, seq, _ in records:
            _write_record(out, header, seq)
    return [meta for _, _, meta in records]


def metadata_from_summary_fasta(path):
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        sample = path.name.split('.')[0] if path.name else ''
        pipeline = '.'.join(path.name.split('.')[1:-1]) if path.name.count('.') >= 2 else ''
        return [{
            'sample': sample,
            'software': '',
            'pipeline': pipeline,
            'locus': '',
            'source_file': '',
            'record_id': '',
            'length': '0',
            'gc_percent': '0',
            'n_count': '0',
            'topology': 'unknown',
            'status': 'empty',
            'output_fasta': str(path),
            'notes': 'summary FASTA is empty or missing',
        }]

    rows = []
    for record_id, desc, seq in parse_fasta(path):
        length, gc_percent, n_count = sequence_stats(seq)
        parts = record_id.split('|')
        sample = parts[0] if parts else ''
        kv = {}
        for part in parts[1:]:
            if '=' in part:
                k, v = part.split('=', 1)
                kv[k] = v
        rows.append({
            'sample': sample,
            'software': kv.get('software', ''),
            'pipeline': kv.get('pipeline', ''),
            'locus': kv.get('locus', ''),
            'source_file': str(path),
            'record_id': record_id,
            'length': str(length),
            'gc_percent': str(gc_percent),
            'n_count': str(n_count),
            'topology': kv.get('topology', infer_topology(record_id, desc)),
            'status': 'ok',
            'output_fasta': str(path),
            'notes': '',
        })
    return rows


def combine_summary(summary_fastas, all_fasta_path, report_path):
    all_fasta_path = Path(all_fasta_path)
    report_path = Path(report_path)
    all_fasta_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    with all_fasta_path.open('w') as all_out:
        for fasta in summary_fastas:
            fasta = Path(fasta)
            rows.extend(metadata_from_summary_fasta(fasta))
            if fasta.exists() and fasta.stat().st_size > 0:
                for record_id, desc, seq in parse_fasta(fasta):
                    _write_record(all_out, record_id, seq)

    with report_path.open('w') as report:
        report.write('\t'.join(SUMMARY_COLUMNS) + '\n')
        for row in rows:
            report.write('\t'.join(str(row.get(col, '')) for col in SUMMARY_COLUMNS) + '\n')
    return rows
