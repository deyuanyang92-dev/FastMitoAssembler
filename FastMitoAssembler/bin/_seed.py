import gzip
from pathlib import Path


class SeedError(ValueError):
    pass


def _open_text(path):
    path = Path(path)
    if path.suffix == '.gz':
        return gzip.open(path, 'rt')
    return path.open('r')


def _parse_fasta(path):
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


def _parse_genbank_origin(path):
    seq_parts = []
    in_origin = False
    with _open_text(path) as handle:
        for line in handle:
            if line.startswith('ORIGIN'):
                in_origin = True
                continue
            if in_origin:
                if line.startswith('//'):
                    break
                seq_parts.extend(ch for ch in line if ch.isalpha())
    seq = ''.join(seq_parts).upper()
    if seq:
        yield Path(path).stem, Path(path).stem, seq


def _records(path):
    lower = str(path).lower()
    if lower.endswith(('.gb', '.gbk', '.gbf', '.gb.gz', '.gbk.gz', '.gbf.gz')):
        yield from _parse_genbank_origin(path)
    else:
        yield from _parse_fasta(path)


def _write_fasta(path, record_id, seq, width=80):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as handle:
        handle.write(f'>{record_id}\n')
        for i in range(0, len(seq), width):
            handle.write(seq[i:i + width] + '\n')


def prepare_seed(input_path, output_path, sample, seed_mode='single', missing='fail'):
    """Write a sample-specific seed FASTA from a single or multi-record input."""
    if not input_path or str(input_path) == 'none':
        if missing == 'skip':
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).touch()
            return False
        raise SeedError(f'seed_input is required for sample {sample}')

    input_path = Path(input_path)
    if not input_path.exists():
        if missing == 'skip':
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).touch()
            return False
        raise SeedError(f'seed_input does not exist: {input_path}')

    selected = None
    for name, desc, seq in _records(input_path):
        if seed_mode == 'by-sample':
            if name == sample:
                selected = (name, desc, seq)
                break
        else:
            selected = (name, desc, seq)
            break

    if selected is None:
        if missing == 'skip':
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).touch()
            return False
        raise SeedError(f'No seed record found for sample {sample} in {input_path}')

    _, _, seq = selected
    if not seq:
        raise SeedError(f'Seed record for sample {sample} is empty in {input_path}')
    _write_fasta(output_path, f'{sample}|seed_source={input_path.name}', seq)
    return True
