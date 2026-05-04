# SPAdes Snakemake Rules
#
# 组装模式:
#   - default: 通用组装
#   - isolate: 细菌分离株
#   - meta: 宏基因组
#   - rna: 转录组
#   - plasmid: 质粒
#   - metaviral: 病毒
#   - shallow: 低深度数据

import os

# SPAdes 配置
SPADES_CFG = config.get('spades') or {}
SPADES_ENABLED = bool(SPADES_CFG.get('enabled', False))
SPADES_MODE = SPADES_CFG.get('mode', 'default')
SPADES_THREADS = SPADES_CFG.get('threads', 16)
SPADES_MEMORY = SPADES_CFG.get('memory_gb', 32)
SPADES_AUTO_CLEAN = SPADES_CFG.get('auto_clean', True)
SPADES_KEEP_PATTERNS = SPADES_CFG.get('keep_patterns', [
    "contigs.fasta", "scaffolds.fasta", "transcripts.fasta",
    "plasmids.fasta", "viruses.fasta",
    "assembly_graph.fastg", "params.txt", "spades.log",
])
SPADES_EXTRA = SPADES_CFG.get('extra_args', '')


# SPAdes 预设模式
SPADES_MODE_PRESETS = {
    "default": {
        "description": "General assembly with careful mode",
        "flags": "--only-assembler --careful",
        "output_files": ["contigs.fasta", "scaffolds.fasta"],
    },
    "isolate": {
        "description": "Isolate assembly for high-coverage bacterial samples",
        "flags": "--isolate --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta"],
    },
    "meta": {
        "description": "Metagenome assembly for complex communities",
        "flags": "--meta --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta"],
    },
    "rna": {
        "description": "RNA assembly for transcriptome data",
        "flags": "--rna --only-assembler",
        "output_files": ["transcripts.fasta", "contigs.fasta"],
    },
    "plasmid": {
        "description": "Plasmid detection and assembly",
        "flags": "--plasmid --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta", "plasmids.fasta"],
    },
    "metaviral": {
        "description": "Viral detection from metagenomic data",
        "flags": "--metaviral --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta", "viruses.fasta"],
    },
    "metaplasmid": {
        "description": "Plasmid detection from metagenomic data",
        "flags": "--metaplasmid --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta", "plasmids.fasta"],
    },
    "sc": {
        "description": "Single-cell MDA assembly",
        "flags": "--sc --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta"],
    },
    "rnaviral": {
        "description": "RNA virus assembly",
        "flags": "--rnaviral --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta"],
    },
    "shallow": {
        "description": "Low-coverage/shallow sequencing assembly",
        "flags": "--meta -k 21,33,55 --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta"],
    },
}


def _spades_mode_flags(mode):
    """获取模式参数"""
    preset = SPADES_MODE_PRESETS.get(mode, SPADES_MODE_PRESETS["default"])
    return preset["flags"]


def _spades_output_files(mode):
    """获取预期输出文件"""
    preset = SPADES_MODE_PRESETS.get(mode, SPADES_MODE_PRESETS["default"])
    return preset["output_files"]


# 目录和路径定义
SPADES_DIR = RESULT_DIR.joinpath('{sample}', 'spades')
SPADES_CONTIGS = SPADES_DIR.joinpath('contigs.fasta')
SPADES_SCAFFOLDS = SPADES_DIR.joinpath('scaffolds.fasta')
SPADES_TRANSCRIPTS = SPADES_DIR.joinpath('transcripts.fasta')


if SPADES_ENABLED:
    rule spades:
        """
        SPAdes assembly with preset modes.

        Modes:
          - default: General assembly
          - isolate: Bacterial isolates
          - meta: Metagenome
          - rna: Transcriptome
          - plasmid: Plasmid
          - metaviral: Viral
          - shallow: Low-coverage
        """
        input:
            fq1=FASTP_FQ1 if FASTP_ENABLED else RAW_FQ1,
            fq2=FASTP_FQ2 if FASTP_ENABLED else RAW_FQ2,
        output:
            contigs=SPADES_CONTIGS,
            scaffolds=SPADES_SCAFFOLDS,
            done=SPADES_DIR.joinpath('.done'),
        params:
            outdir=SPADES_DIR,
            mode=SPADES_MODE,
            mode_flags=_spades_mode_flags(SPADES_MODE),
            tool_prefix=_shell_prefix('spades'),
            spades_cmd=_tool_cmd('spades', 'spades.py'),
            threads=SPADES_THREADS,
            memory=SPADES_MEMORY,
            extra=SPADES_EXTRA,
        conda: "../envs/spades.yaml"
        message: "SPAdes ({params.mode}) for sample: {wildcards.sample}"
        log: LOG_DIR.joinpath('{sample}', 'spades.log')
        benchmark: BENCHMARK_DIR.joinpath('{sample}', 'spades.stat')
        threads: lambda wildcards: SPADES_THREADS
        resources:
            mem_mb=lambda wildcards: SPADES_MEMORY * 1024,
        shell:
            """
            (
            mkdir -p {params.outdir}
            {params.tool_prefix}{params.spades_cmd} {params.mode_flags} \
                -1 {input.fq1} -2 {input.fq2} \
                -o {params.outdir} \
                -t {params.threads} \
                -m {params.memory} \
                {params.extra} \
            ) 2>{log}.err 1>{log}

            # 标记完成
            touch {output.done}
            """

    rule spades_rna:
        """
        SPAdes RNA assembly (transcriptome).
        """
        input:
            fq1=FASTP_FQ1 if FASTP_ENABLED else RAW_FQ1,
            fq2=FASTP_FQ2 if FASTP_ENABLED else RAW_FQ2,
        output:
            transcripts=SPADES_TRANSCRIPTS,
            contigs=SPADES_CONTIGS,
            done=SPADES_DIR.joinpath('.done'),
        params:
            outdir=SPADES_DIR,
            tool_prefix=_shell_prefix('spades'),
            spades_cmd=_tool_cmd('spades', 'spades.py'),
            threads=SPADES_THREADS,
            memory=SPADES_MEMORY,
            extra=SPADES_EXTRA,
        conda: "../envs/spades.yaml"
        message: "SPAdes RNA for sample: {wildcards.sample}"
        log: LOG_DIR.joinpath('{sample}', 'spades.log')
        benchmark: BENCHMARK_DIR.joinpath('{sample}', 'spades.stat')
        threads: lambda wildcards: SPADES_THREADS
        resources:
            mem_mb=lambda wildcards: SPADES_MEMORY * 1024,
        shell:
            """
            (
            mkdir -p {params.outdir}
            {params.tool_prefix}{params.spades_cmd} --rna --only-assembler \
                -1 {input.fq1} -2 {input.fq2} \
                -o {params.outdir} \
                -t {params.threads} \
                -m {params.memory} \
                {params.extra} \
            ) 2>{log}.err 1>{log}

            touch {output.done}
            """

    rule spades_clean:
        """
        Clean SPAdes intermediate files.
        """
        input:
            done=SPADES_DIR.joinpath('.done'),
        params:
            outdir=SPADES_DIR,
            keep_patterns=" ".join(SPADES_KEEP_PATTERNS),
        run:
            import shutil
            outdir = params.outdir
            keep = set(params.keep_patterns.split())

            # 删除中间目录
            for pattern in ["tmp", "misc", "logs", "corrected", ".bin_reads"]:
                p = outdir.joinpath(pattern)
                if p.exists():
                    shutil.rmtree(p)

            # 删除 K* 目录
            for p in outdir.glob("K*"):
                if p.is_dir() and p.name.startswith("K") and p.name[1:].isdigit():
                    shutil.rmtree(p)

            # 删除不在保留列表中的文件
            for p in outdir.iterdir():
                if p.is_file() and p.name not in keep and p.name != ".done":
                    p.unlink()

    # Aggregate target for all samples
    rule spades_all:
        input: expand(SPADES_DIR.joinpath('.done'), sample=SAMPLES)
