"""
Shared configuration, paths, and helper functions for FastMitoAssembler.
"""
import os
import sys
from pathlib import Path
from functools import partial

# Use in development
FAST_MITO_AS_PATH = config.get("FAST_MITO_AS_PATH") or os.getenv('FAST_MITO_AS_PATH')
if FAST_MITO_AS_PATH:
    sys.path.insert(0, FAST_MITO_AS_PATH)
from FastMitoAssembler.config import NOVOPLASTY_CONFIG_TPL
from FastMitoAssembler.util import safe_open

# ==============================================================
# Configuration information
SAMPLES = config.get("samples")
ORGANELLE_DB = config.get("organelle_database", "animal_mt")
SEED_INPUT = config.get('seed_input')
SEED_INPUT = Path(SEED_INPUT).resolve() if SEED_INPUT else 'none'
SEED_MODE = config.get('seed_mode', 'single')
SEED_MISSING = config.get('seed_missing', 'fail')

# NOVOPlasty configuration
NOVOPLASTY_GENOME_MIN_SIZE = config.get('novoplasty_genome_min_size', 12000)
NOVOPLASTY_GENOME_MAX_SIZE = config.get('novoplasty_genome_max_size', 30000)
NOVOPLASTY_KMER_SIZE = config.get('novoplasty_kmer_size', 39)
NOVOPLASTY_MAX_MEM_GB = config.get('novoplasty_max_mem_gb', 10)
NOVOPLASTY_SEED_SOURCE = config.get('novoplasty_seed_source', 'auto')
READ_LENGTH = int(config.get('read_length', 150))
INSERT_SIZE = config.get('insert_size', 300)

# MitozAnnotate configuration
MITOZ_CLADE = config.get('mitoz_clade', 'Annelida-segmented-worms')
GENETIC_CODE = config.get('genetic_code', 5)
MITOZ_THREAD_NUMBER = config.get('mitoz_thread_number', 20)
MITOZ_INPUT_SOURCE = config.get('mitoz_input_source', 'auto')
ASSEMBLY_FASTA = config.get('assembly_fasta')

# MEANGS configuration
MEANGS_THREAD = config.get('meangs_thread', 4)
MEANGS_READS  = config.get('meangs_reads', 2000000)
MEANGS_DEEPIN = config.get('meangs_deepin', True)
_MEANGS_CLASS_MAP = {
    'Annelida-segmented-worms': 'A-worms',
    'Vertebrata': 'Chordata',
}
MEANGS_SPECIES_CLASS = config.get('meangs_species_class') or _MEANGS_CLASS_MAP.get(
    config.get('meangs_clade'), config.get('meangs_clade') or 'Arthropoda')
MEANGS_QUALITY = config.get('meangs_quality', 0.05)
MEANGS_SEQ_SCAF = config.get('meangs_seqscaf') or ''
MEANGS_KEEP_MIN_LEN = config.get('meangs_keepMinLen')

def _bool_flag(flag, key):
    return flag if bool(config.get(key, False)) else ''

def _value_flag(flag, value):
    if value in (None, '', []):
        return ''
    return f'{flag} {value}'

MEANGS_EXTRA_FLAGS = ' '.join(p for p in [
    _bool_flag('--clip', 'meangs_clip'),
    _bool_flag('--keepIntMed', 'meangs_keepIntMed'),
    _bool_flag('--skipassem', 'meangs_skipassem'),
    _bool_flag('--skipqc', 'meangs_skipqc'),
    _bool_flag('--skiphmm', 'meangs_skiphmm'),
    _bool_flag('--skipextend', 'meangs_skipextend'),
    _value_flag('-s', MEANGS_SEQ_SCAF),
    _value_flag('--keepMinLen', MEANGS_KEEP_MIN_LEN),
] if p)

# GetOrganelle configuration — blank config values are intentionally NOT
# forwarded so GetOrganelle applies its own -F-dependent defaults.
GETORGANELLE_ALL_DATA = bool(config.get('getorganelle_all_data', False))
GETORGANELLE_SEED_SOURCE = config.get('getorganelle_seed_source', 'auto')

def _go_flag(flag, key):
    v = config.get(key)
    if v in (None, '', []):
        return ''
    return f'{flag} {v}'

def _build_go_flags():
    parts = [
        _go_flag('-R', 'getorganelle_rounds'),
        _go_flag('-k', 'getorganelle_kmers'),
        _go_flag('-t', 'getorganelle_threads'),
        _go_flag('-w', 'getorganelle_word_size'),
        _go_flag('--max-extending-len', 'getorganelle_max_extending_len'),
    ]
    genes = config.get('genes')
    if genes not in (None, '', []):
        parts.append(f'--genes {genes}')
    if GETORGANELLE_ALL_DATA:
        parts.append(_go_flag('--max-reads', 'getorganelle_max_reads') or '--max-reads inf')
        parts.append(_go_flag('--reduce-reads-for-coverage', 'getorganelle_reduce_reads_for_coverage') or '--reduce-reads-for-coverage inf')
    else:
        parts.append(_go_flag('--max-reads', 'getorganelle_max_reads'))
        parts.append(_go_flag('--reduce-reads-for-coverage', 'getorganelle_reduce_reads_for_coverage'))
    return ' '.join(p for p in parts if p)

GETORGANELLE_FLAGS = _build_go_flags()

# Optional fastp adapter-only trimming
FASTP_CFG = config.get('fastp') or {}
FASTP_ENABLED = bool(FASTP_CFG.get('enabled'))
FASTP_MODE = FASTP_CFG.get('mode', 'adapter_only')
FASTP_EXTRA = FASTP_CFG.get('extra_args') or ''

# Cleanup intermediate files after each step
CLEANUP = config.get('cleanup', False)
# ==============================================================

# ==============================================================
# Per-tool execution prefix (supports conda_env or bin_dir overrides)
_TOOL_ENVS = config.get('tool_envs', {})

def _shell_prefix(tool):
    cfg = _TOOL_ENVS.get(tool) or {}
    if not isinstance(cfg, dict):
        return ''
    conda_env = (cfg.get('conda_env') or '').strip()
    bin_dir = (cfg.get('bin_dir') or '').strip()
    if conda_env:
        return f'conda run --no-capture-output -n {conda_env} '
    if bin_dir:
        return f'PATH="{bin_dir}:$PATH" '
    return ''

def _tool_cmd(tool, default_cmd):
    """Return the shell command to invoke a tool.

    Supports command overrides and script_path overrides while keeping the
    default packaged conda environments available when no override is set.
    """
    cfg = _TOOL_ENVS.get(tool) or {}
    if not isinstance(cfg, dict):
        return default_cmd
    command = (cfg.get('command') or '').strip()
    if command:
        return command
    script_path = (cfg.get('script_path') or '').strip()
    if script_path:
        interpreter = cfg.get('script_interpreter')
        if interpreter is None:
            interpreter = {
                'meangs': 'python',
                'novoplasty': 'perl',
            }.get(tool, '')
        if interpreter:
            return f'{interpreter} {Path(script_path).expanduser().resolve()}'
        return str(Path(script_path).expanduser().resolve())
    return default_cmd
# ==============================================================

# ==============================================================
# Log directory
LOG_DIR = Path(config.get("log_dir", "logs")).resolve()
# Output directory
RESULT_DIR = Path(config.get("result_dir", "result")).resolve()
SAMPLE_DIR = partial(os.path.join, RESULT_DIR, "{sample}")
SEED_DIR = partial(SAMPLE_DIR, "0.seed")
MEANGS_DIR = partial(SAMPLE_DIR, "1.MEANGS")
NOVOPLASTY_DIR = partial(SAMPLE_DIR, "2.NOVOPlasty")
ORGANELLE_DIR = partial(SAMPLE_DIR, "3.GetOrganelle")
MITOZ_ANNO_DIR = partial(SAMPLE_DIR, "4.MitozAnnotate")
MITOZ_ANNO_RESULT_DIR = partial(MITOZ_ANNO_DIR, f"{{sample}}.{ORGANELLE_DB}.get_organelle.fasta.result")

# Benchmark directory
BENCHMARK_DIR = Path(config.get("benchmark_dir", "benchmark")).resolve()

# input/output
FASTP_DIR = partial(SAMPLE_DIR, "0.fastp")
user_seed_fas = SEED_DIR("{sample}.seed.fasta")
seed_fas = MEANGS_DIR("{sample}_deep_detected_mito.fas")
novoplasty_config = NOVOPLASTY_DIR("config.txt")
novoplasty_fasta = NOVOPLASTY_DIR("{sample}.novoplasty.fasta")
organelle_fasta_new = ORGANELLE_DIR(f"{ORGANELLE_DB}.get_organelle.fasta")
mm_report = partial(SAMPLE_DIR, "materials_and_methods.md")

SUMMARY_DIR = Path(config.get("summary_dir", RESULT_DIR.joinpath("summary"))).resolve()

def SUMMARY_FASTA(pipeline):
    return os.path.join(SUMMARY_DIR, f"{{sample}}.{pipeline}.fasta")

summary_all_fasta = SUMMARY_DIR.joinpath("summary_all.fasta")
summary_report_tsv = SUMMARY_DIR.joinpath("summary_report.tsv")
# ==============================================================

# ==============================================================
# Read data
READS_DIR = Path(config.get("reads_dir", ".")).resolve()
FQ_PATH_PATTERN = config.get('fq_path_pattern', '{sample}/{sample}_1.clean.fq.gz')
FQ2_PATH_PATTERN = config.get('fq2_path_pattern') or FQ_PATH_PATTERN.replace('_1', '_2', 1).replace('R1', 'R2', 1)
SAMPLE_FASTQS = config.get('sample_fastqs') or {}

def RAW_FQ1(wildcards):
    sample_fastqs = SAMPLE_FASTQS.get(wildcards.sample) or {}
    return sample_fastqs.get('fq1') or str(READS_DIR.joinpath(FQ_PATH_PATTERN)).format(sample=wildcards.sample)

def RAW_FQ2(wildcards):
    sample_fastqs = SAMPLE_FASTQS.get(wildcards.sample) or {}
    return sample_fastqs.get('fq2') or str(READS_DIR.joinpath(FQ2_PATH_PATTERN)).format(sample=wildcards.sample)

# When fastp is enabled, downstream rules consume its output instead of raw reads.
FASTP_FQ1 = FASTP_DIR("{sample}_1.adapter.fq.gz")
FASTP_FQ2 = FASTP_DIR("{sample}_2.adapter.fq.gz")
FQ1 = FASTP_FQ1 if FASTP_ENABLED else RAW_FQ1
FQ2 = FASTP_FQ2 if FASTP_ENABLED else RAW_FQ2

# Subsample before GetOrganelle (0 / null -> no subsample, feed all reads through).
SUBSAMPLE_GB = config.get('subsample_gb', 5) or 0
SUBSAMPLE_READS = round(SUBSAMPLE_GB * 1e9 / 2 / READ_LENGTH) if SUBSAMPLE_GB else 0
# ==============================================================

def _novoplasty_seed_input(wildcards):
    source = NOVOPLASTY_SEED_SOURCE
    if source == 'user':
        return user_seed_fas
    return seed_fas

def _getorganelle_seed_input(wildcards):
    source = GETORGANELLE_SEED_SOURCE
    if source in (None, '', 'none'):
        return []
    if source == 'meangs':
        return seed_fas
    if source == 'user':
        return user_seed_fas
    # Backward-compatible default: full run and mg-nov-get use NOVOPlasty output.
    return novoplasty_fasta

def _mitoz_assembly_input(wildcards):
    if ASSEMBLY_FASTA:
        return str(Path(ASSEMBLY_FASTA).expanduser().resolve())
    if MITOZ_INPUT_SOURCE == 'novoplasty':
        return novoplasty_fasta
    return organelle_fasta_new
