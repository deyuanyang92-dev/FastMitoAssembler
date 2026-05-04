"""
Runner 模块 - Python 后端批量执行（无需 Snakemake）

支持的 Runner:
- FastpRunner: fastp 批量质控
- MeangsRunner: MEANGS 批量组装
- GetOrganelleRunner: GetOrganelle 批量组装（含 NR 模式）
- NovoplastyRunner: NOVOPlasty 批量组装（多 kmer/多 seed）
- MitozRunner: MitoZ 批量注释
- BlastRunner: BLAST 执行（在线/本地）
- MetadataFetcher: NCBI 元数据获取
- MultiqcRunner: MultiQC 汇总报告
- BuscoRunner: BUSCO 组装评估
"""

from ._fastp_runner import (
    FastpRunner,
    is_sample_done as fastp_is_sample_done,
    get_output_files as fastp_get_output_files,
    parse_reads_dir as fastp_parse_reads_dir,
    parse_reads_dir_se as fastp_parse_reads_dir_se,
    parse_reads_dir_auto as fastp_parse_reads_dir_auto,
    detect_fastq_structure as fastp_detect_structure,
    write_checked_file as fastp_write_checked_file,
    is_sample_done_se as fastp_is_sample_done_se,
    FASTP_PRESETS,
    PRESET_MODES,
)

from ._meangs_runner import (
    MeangsRunner,
    is_sample_done as meangs_is_sample_done,
    get_result_file as meangs_get_result_file,
    parse_reads_dir as meangs_parse_reads_dir,
    SPECIES_CLASSES,
)

from ._getorganelle_runner import (
    GetOrganelleRunner,
    is_sample_done,
    is_sample_incomplete,
    parse_reads_dir,
)

from ._novoplasty_runner import (
    NovoplastyRunner,
    is_sample_done as novoplasty_is_sample_done,
    get_best_result,
    parse_reads_dir as novoplasty_parse_reads_dir,
)

from ._mitoz_runner import (
    MitozRunner,
    is_sample_done as mitoz_is_sample_done,
    get_result_files,
    parse_fasta_dir,
)

from ._blast_runner import (
    BlastRunner,
    MetadataFetcher,
)

from ._multiqc_runner import (
    MultiqcRunner,
    find_qc_directories,
    diagnose_multiqc_error,
)

from ._busco_runner import (
    BuscoRunner,
    find_fasta_files,
    write_busco_status,
    diagnose_busco_error,
    parse_busco_summary,
)

__all__ = [
    # Fastp
    "FastpRunner",
    "fastp_is_sample_done",
    "fastp_get_output_files",
    "fastp_parse_reads_dir",
    "fastp_parse_reads_dir_se",
    "fastp_parse_reads_dir_auto",
    "fastp_detect_structure",
    "fastp_write_checked_file",
    "fastp_is_sample_done_se",
    "FASTP_PRESETS",
    "PRESET_MODES",
    # MEANGS
    "MeangsRunner",
    "meangs_is_sample_done",
    "meangs_get_result_file",
    "meangs_parse_reads_dir",
    "SPECIES_CLASSES",
    # GetOrganelle
    "GetOrganelleRunner",
    "is_sample_done",
    "is_sample_incomplete",
    "parse_reads_dir",
    # NOVOPlasty
    "NovoplastyRunner",
    "novoplasty_is_sample_done",
    "get_best_result",
    "novoplasty_parse_reads_dir",
    # MitoZ
    "MitozRunner",
    "mitoz_is_sample_done",
    "get_result_files",
    "parse_fasta_dir",
    # BLAST
    "BlastRunner",
    "MetadataFetcher",
    # MultiQC
    "MultiqcRunner",
    "find_qc_directories",
    "diagnose_multiqc_error",
    # BUSCO
    "BuscoRunner",
    "find_fasta_files",
    "write_busco_status",
    "diagnose_busco_error",
    "parse_busco_summary",
]
