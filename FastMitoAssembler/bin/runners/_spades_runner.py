"""
SPAdes Python Runner - 批量组装不依赖 Snakemake

设计参考:
  - 官方文档: https://github.com/ablab/spades
  - 参考实现: FastMitoAssembler/bin/runners/_meangs_runner.py
  - 参考脚本: my_shh/fastp_spades_buscov3.1.py

关键特性:
  - Popen 流式读取（避免缓冲区满导致子进程挂起）
  - Checkpoint 检测（自动续跑未完成任务）
  - 预设模式支持（default, isolate, meta, rna, plasmid, metaviral, shallow）
  - 断点续跑支持（--continue）
  - 自动清理中间文件
  - 错误诊断与提示
  - 预检查功能
  - ThreadPoolExecutor 并行执行
  - 信号处理（优雅关闭）

预设模式:
  default:    通用组装 --only-assembler --careful
  isolate:    细菌分离株 --isolate
  meta:       宏基因组 --meta
  rna:        转录组 --rna
  plasmid:    质粒 --plasmid
  metaviral:  病毒 --metaviral
  shallow:    低深度数据 -k 21,33,55 --careful

输出文件:
  {output_dir}/{sample}/
  ├── contigs.fasta        # Contigs 序列
  ├── scaffolds.fasta      # Scaffold 序列
  ├── transcripts.fasta    # 转录本 (仅 rna 模式)
  ├── plasmids.fasta       # 质粒 (仅 plasmid 模式)
  ├── viruses.fasta        # 病毒 (仅 metaviral 模式)
  ├── assembly_graph.fastg # 组装图
  ├── params.txt           # 参数记录
  └── spades.log           # 运行日志
"""

import subprocess
import logging
import os
import re
import shlex
import signal
import atexit
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed


# ==============================================================
# 全局变量与信号处理
# ==============================================================

_running_processes: Dict[str, subprocess.Popen] = {}
_processes_lock = None
_shutdown_requested = False


def _init_lock():
    """初始化线程锁"""
    global _processes_lock
    import threading
    _processes_lock = threading.Lock()


def _signal_handler(signum, frame):
    """信号处理器：终止所有子进程"""
    global _shutdown_requested
    _shutdown_requested = True
    logging.warning(f"[SIGNAL] 收到信号 {signum}，正在终止所有子进程...")
    if _processes_lock:
        with _processes_lock:
            for sample, proc in list(_running_processes.items()):
                if proc.poll() is None:
                    logging.warning(f"[SIGNAL] 终止 {sample} (PID: {proc.pid})")
                    proc.terminate()
    import time
    time.sleep(0.5)
    if _processes_lock:
        with _processes_lock:
            for sample, proc in list(_running_processes.items()):
                if proc.poll() is None:
                    logging.warning(f"[SIGNAL] 强制杀死 {sample}")
                    proc.kill()
    import sys
    sys.exit(128 + signum)


def _cleanup_on_exit():
    """退出时清理子进程"""
    if _processes_lock:
        with _processes_lock:
            for sample, proc in list(_running_processes.items()):
                if proc.poll() is None:
                    proc.terminate()


def _terminate_proc(proc: subprocess.Popen):
    """安全终止进程，避免僵尸进程"""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


# 注册信号处理器
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)
atexit.register(_cleanup_on_exit)


# ==============================================================
# 预设模式定义
# ==============================================================

SPADES_MODES = {
    "default": {
        "description": "General assembly with careful mode",
        "recommended_for": "general use, balanced quality and speed",
        "flags": "--only-assembler --careful",
        "output_files": ["contigs.fasta", "scaffolds.fasta"],
    },
    "isolate": {
        "description": "Isolate assembly for high-coverage bacterial samples",
        "recommended_for": "bacterial isolates with high coverage (>50x)",
        "flags": "--isolate --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta"],
    },
    "meta": {
        "description": "Metagenome assembly for complex communities",
        "recommended_for": "metagenomic samples, environmental samples",
        "flags": "--meta --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta"],
    },
    "rna": {
        "description": "RNA assembly for transcriptome data",
        "recommended_for": "RNA-seq data, transcriptome assembly",
        "flags": "--rna --only-assembler",
        "output_files": ["transcripts.fasta", "contigs.fasta"],
    },
    "plasmid": {
        "description": "Plasmid detection and assembly",
        "recommended_for": "plasmid extraction from bacterial samples",
        "flags": "--plasmid --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta", "plasmids.fasta"],
    },
    "metaviral": {
        "description": "Viral detection from metagenomic data",
        "recommended_for": "viral discovery from metagenomes",
        "flags": "--metaviral --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta", "viruses.fasta"],
    },
    "metaplasmid": {
        "description": "Plasmid detection from metagenomic data",
        "recommended_for": "plasmid discovery from metagenomes",
        "flags": "--metaplasmid --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta", "plasmids.fasta"],
    },
    "sc": {
        "description": "Single-cell MDA assembly",
        "recommended_for": "single-cell amplification data",
        "flags": "--sc --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta"],
    },
    "rnaviral": {
        "description": "RNA virus assembly",
        "recommended_for": "RNA virus detection",
        "flags": "--rnaviral --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta"],
    },
    "shallow": {
        "description": "Low-coverage/shallow sequencing assembly",
        "recommended_for": "low-coverage data (<20x), uses meta mode for robustness",
        "flags": "--meta -k 21,33,55 --only-assembler",
        "output_files": ["contigs.fasta", "scaffolds.fasta"],
    },
}

VALID_MODES = set(SPADES_MODES.keys())


# ==============================================================
# 错误诊断
# ==============================================================

SPADES_ERROR_PATTERNS = {
    "memory": {
        "patterns": [
            r"Killed",
            r"Out of memory",
            r"std::bad_alloc",
            r"cannot allocate memory",
            r"Memory allocation failed",
        ],
        "hint": "内存不足: 尝试增加 -m 参数，减少 K-mer 数量，或使用 --only-assembler",
    },
    "segmentation": {
        "patterns": [
            r"Segmentation fault",
            r"signal 11",
            r"SIGSEGV",
        ],
        "hint": "段错误: 尝试减少线程数 (-t)，更新 SPAdes 版本，或检查输入文件",
    },
    "kmer": {
        "patterns": [
            r"K-mer.*too (large|small)",
            r"Invalid k-mer",
            r"k-mer size.*not supported",
        ],
        "hint": "K-mer 问题: 检查 read 长度和覆盖度，调整 -k 参数",
    },
    "input": {
        "patterns": [
            r"Cannot open file",
            r"Invalid reads file",
            r"Error reading",
            r"No reads found",
            r"File not found",
            r"unsupported format",
        ],
        "hint": "输入文件问题: 检查文件路径、格式、权限，确保文件完整且非空",
    },
    "resume": {
        "patterns": [
            r"Cannot resume",
            r"No checkpoint found",
            r"Incorrect directory for resuming",
            r"Pipeline state.*corrupted",
        ],
        "hint": "续跑失败: 输出目录可能损坏，尝试删除后重新运行",
    },
    "disk": {
        "patterns": [
            r"No space left",
            r"Disk quota exceeded",
            r"write error",
        ],
        "hint": "磁盘空间不足: 清理磁盘空间或更换输出目录",
    },
    "thread": {
        "patterns": [
            r"Thread.*failed",
            r"pthread_create",
            r"Resource temporarily unavailable",
        ],
        "hint": "线程问题: 减少线程数 (-t) 或并行任务数",
    },
}


def diagnose_spades_error(log_content: str) -> Dict:
    """
    诊断 SPAdes 错误。

    Returns:
        {"errors": [error_types], "hints": [hints]}
    """
    errors = []
    hints = []

    for error_type, info in SPADES_ERROR_PATTERNS.items():
        for pattern in info["patterns"]:
            if re.search(pattern, log_content, re.IGNORECASE):
                if error_type not in errors:
                    errors.append(error_type)
                    hints.append(info["hint"])
                break

    return {"errors": errors, "hints": hints}


# ==============================================================
# 预检查功能
# ==============================================================

def preflight_check(
    fq1: Path,
    fq2: Optional[Path],
    output_dir: Path,
    threads: int,
    memory_gb: int,
) -> Dict:
    """
    运行前检查。

    Returns:
        {"ok": bool, "issues": [issues], "warnings": [warnings]}
    """
    issues = []
    warnings = []

    # 1. 输入文件检查
    for fq in [f for f in [fq1, fq2] if f is not None]:
        if not fq.exists():
            issues.append(f"输入文件不存在: {fq}")
        elif fq.stat().st_size == 0:
            issues.append(f"输入文件为空: {fq}")
        elif fq.stat().st_size < 100:
            warnings.append(f"输入文件过小 (<100 bytes): {fq}")

    # 2. 磁盘空间检查 (建议至少 10x 输入文件大小)
    try:
        input_size = sum(
            f.stat().st_size for f in [fq1, fq2] if f is not None and f.exists()
        )
        disk_free = shutil.disk_usage(output_dir.parent if output_dir.parent.exists() else ".").free
        required_space = input_size * 10
        if disk_free < required_space:
            warnings.append(
                f"磁盘空间可能不足: 建议 {required_space / 1e9:.1f}GB, 可用 {disk_free / 1e9:.1f}GB"
            )
    except Exception as e:
        warnings.append(f"无法检查磁盘空间: {e}")

    # 3. 内存检查
    try:
        import psutil
        mem = psutil.virtual_memory()
        if mem.available < memory_gb * 1024**3 * 0.5:
            warnings.append(
                f"可用内存可能不足: 需要 {memory_gb}GB, 可用 {mem.available / 1e9:.1f}GB"
            )
    except ImportError:
        pass

    # 4. SPAdes 可用性检查
    try:
        result = subprocess.run(
            ["spades.py", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            issues.append("SPAdes 未正确安装或不可用")
    except FileNotFoundError:
        issues.append("SPAdes 未找到: 请安装 SPAdes 或使用 --spades-path 指定路径")
    except subprocess.TimeoutExpired:
        warnings.append("SPAdes 版本检查超时")
    except Exception as e:
        warnings.append(f"无法检查 SPAdes: {e}")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


# ==============================================================
# SPAdes Runner 类
# ==============================================================

class SpadesRunner:
    """SPAdes 批量执行器"""

    def __init__(
        self,
        threads: int = 16,
        memory_gb: int = 32,
        shell_prefix: str = "",
        spades_path: str = "spades.py",
    ):
        self.threads = threads
        self.memory_gb = memory_gb
        self.shell_prefix = shell_prefix
        self.spades_path = spades_path

    def build_command(
        self,
        fq1: str,
        fq2: Optional[str],
        output_dir: Path,
        mode: str = "default",
        resume: bool = False,
        extra_args: str = "",
        **kwargs,
    ) -> List[str]:
        """
        构建 SPAdes 命令。

        Args:
            fq1: R1 文件路径
            fq2: R2 文件路径 (可选，单端数据为 None)
            output_dir: 输出目录
            mode: 组装模式
            resume: 是否续跑
            extra_args: 额外参数

        Returns:
            命令列表
        """
        cmd = [self.spades_path]

        if resume:
            cmd.extend(["--continue", "-o", str(output_dir)])
        else:
            # 输入文件
            if fq2:
                cmd.extend(["-1", fq1, "-2", fq2])
            else:
                cmd.extend(["-s", fq1])
            cmd.extend(["-o", str(output_dir)])

            # 模式参数
            if mode in SPADES_MODES:
                flags = SPADES_MODES[mode]["flags"]
                if flags:
                    cmd.extend(flags.split())
            else:
                # 未知模式，使用默认
                cmd.extend(SPADES_MODES["default"]["flags"].split())

        # 资源参数
        threads = kwargs.get("threads", self.threads)
        memory_gb = kwargs.get("memory_gb", self.memory_gb)
        cmd.extend(["-t", str(threads)])
        cmd.extend(["-m", str(memory_gb)])

        # 额外参数
        if extra_args:
            cmd.extend(shlex.split(extra_args))

        return cmd

    def is_sample_done(self, output_dir: Path, mode: str = "default") -> bool:
        """
        检测组装是否完成。

        根据模式检查不同的输出文件。
        """
        if not output_dir.exists():
            return False

        # 获取该模式的预期输出文件
        if mode in SPADES_MODES:
            expected_files = SPADES_MODES[mode]["output_files"]
        else:
            expected_files = ["contigs.fasta"]

        # 至少有一个预期文件存在且非空
        for f in expected_files:
            p = output_dir / f
            if p.exists() and p.stat().st_size > 0:
                return True

        return False

    def has_partial_state(self, output_dir: Path) -> bool:
        """
        检测是否有中断状态可续跑。

        检查条件:
          1. 输出目录存在
          2. 存在 pipeline_state/ 目录
          3. 存在 params.txt 或 spades.log
        """
        if not output_dir.exists():
            return False

        # 检查 pipeline_state 目录
        pipeline_state = output_dir / "pipeline_state"
        if pipeline_state.exists() and pipeline_state.is_dir():
            # 检查是否有状态文件
            if list(pipeline_state.glob("*.txt")):
                return True

        # 检查关键文件
        params_file = output_dir / "params.txt"
        spades_log = output_dir / "spades.log"

        return params_file.exists() or spades_log.exists()

    def get_resume_state(self, output_dir: Path) -> Dict:
        """
        获取续跑状态详情。

        Returns:
            {"can_resume": bool, "stage": str, "progress": str}
        """
        if not self.has_partial_state(output_dir):
            return {"can_resume": False, "stage": None, "progress": None}

        # 尝试从 spades.log 获取进度
        spades_log = output_dir / "spades.log"
        stage = "unknown"
        progress = None

        if spades_log.exists():
            try:
                content = spades_log.read_text(errors="ignore")
                # 查找最后阶段
                stage_patterns = [
                    (r"Running K(\d+)", "kmer"),
                    (r"corrector", "correction"),
                    (r"assembler", "assembly"),
                ]
                for pattern, name in stage_patterns:
                    matches = list(re.finditer(pattern, content, re.IGNORECASE))
                    if matches:
                        stage = name
            except Exception:
                pass

        return {"can_resume": True, "stage": stage, "progress": progress}

    def clean_intermediate(
        self,
        output_dir: Path,
        keep_patterns: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> List[Path]:
        """
        清理中间文件。

        删除:
          - tmp/
          - misc/
          - logs/
          - corrected/
          - K*/
          - .bin_reads/

        保留:
          - contigs.fasta
          - scaffolds.fasta
          - transcripts.fasta
          - plasmids.fasta
          - viruses.fasta
          - assembly_graph.fastg
          - params.txt
          - spades.log

        Returns:
            删除的文件/目录列表
        """
        if keep_patterns is None:
            keep_patterns = [
                "contigs.fasta", "scaffolds.fasta", "transcripts.fasta",
                "plasmids.fasta", "viruses.fasta",
                "assembly_graph.fastg", "assembly_graph_with_scaffolds.gfa",
                "params.txt", "spades.log", "spades.yaml",
                "input_dataset.yaml",
            ]

        # 要删除的目录模式
        delete_patterns = [
            "tmp", "misc", "logs", "corrected", ".bin_reads",
        ]

        deleted = []

        if not output_dir.exists():
            return deleted

        # 删除匹配的目录
        for pattern in delete_patterns:
            for p in output_dir.glob(pattern):
                if p.is_dir():
                    if not dry_run:
                        shutil.rmtree(p)
                    deleted.append(p)

        # 删除 K* 目录
        for p in output_dir.glob("K*"):
            if p.is_dir() and p.name.startswith("K") and p.name[1:].isdigit():
                if not dry_run:
                    shutil.rmtree(p)
                deleted.append(p)

        # 删除不在保留列表中的文件
        for p in output_dir.iterdir():
            if p.is_file() and p.name not in keep_patterns:
                if not dry_run:
                    p.unlink()
                deleted.append(p)

        return deleted

    def run_single(
        self,
        sample: str,
        fq1: Path,
        fq2: Optional[Path],
        output_dir: Path,
        mode: str = "default",
        force: bool = False,
        extra_args: str = "",
        timeout: int = 86400,  # 24 小时
        auto_clean: bool = True,
        keep_patterns: Optional[List[str]] = None,
        verbose: bool = False,
    ) -> Dict:
        """
        执行单个样本组装。

        Returns:
            {"sample": str, "status": str, "success": bool, ...}
        """
        global _shutdown_requested

        if _shutdown_requested:
            return {"sample": sample, "status": "SKIPPED", "success": False, "error": "Shutdown"}

        sample_dir = output_dir / sample
        sample_dir.mkdir(parents=True, exist_ok=True)

        # Checkpoint 检测
        if not force and self.is_sample_done(sample_dir, mode):
            logging.info(f"[SKIP] {sample} 已完成")
            return {"sample": sample, "status": "SKIP", "success": True}

        # 检测是否可以续跑
        resume = False
        if not force and self.has_partial_state(sample_dir):
            resume_state = self.get_resume_state(sample_dir)
            if resume_state["can_resume"]:
                logging.info(f"[RESUME] {sample} 检测到中断状态，尝试续跑")
                resume = True

        # 预检查
        if verbose and not resume:
            preflight = preflight_check(
                fq1, fq2, sample_dir,
                self.threads, self.memory_gb,
            )
            if preflight["issues"]:
                logging.warning(f"[PREFLIGHT] {sample} 问题: {preflight['issues']}")
            if preflight["warnings"]:
                logging.info(f"[PREFLIGHT] {sample} 警告: {preflight['warnings']}")

        # 构建命令
        cmd = self.build_command(
            str(fq1), str(fq2) if fq2 else None,
            sample_dir, mode, resume, extra_args,
            threads=self.threads,
            memory_gb=self.memory_gb,
        )

        log_file = sample_dir / "spades.log"

        logging.info(f"[RUN] {sample} mode={mode} resume={resume}")
        logging.debug(f"[CMD] {' '.join(cmd)}")

        # 执行
        proc = None
        try:
            with open(log_file, "a") as log_f:
                log_f.write(f"\n# Started at {datetime.now().isoformat()}\n")
                log_f.write(f"# Command: {' '.join(cmd)}\n\n")

                proc = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

                # 注册进程
                if _processes_lock:
                    with _processes_lock:
                        _running_processes[sample] = proc

                returncode = proc.wait(timeout=timeout)

                # 清理进程注册
                if _processes_lock:
                    with _processes_lock:
                        _running_processes.pop(sample, None)

                log_f.write(f"\n# Finished at {datetime.now().isoformat()}\n")
                log_f.write(f"# Return code: {returncode}\n")

            if returncode != 0:
                # 诊断错误
                log_content = log_file.read_text(errors="ignore")
                diagnosis = diagnose_spades_error(log_content)

                error_msg = f"返回码: {returncode}"
                if diagnosis["errors"]:
                    error_msg += f", 错误类型: {', '.join(diagnosis['errors'])}"

                logging.error(f"[FAILED] {sample} {error_msg}")
                if diagnosis["hints"]:
                    for hint in diagnosis["hints"]:
                        logging.error(f"[HINT] {sample} {hint}")

                return {
                    "sample": sample,
                    "status": "FAILED",
                    "success": False,
                    "returncode": returncode,
                    "error": error_msg,
                    "diagnosis": diagnosis,
                }

            # 清理中间文件
            if auto_clean:
                deleted = self.clean_intermediate(sample_dir, keep_patterns)
                if deleted and verbose:
                    logging.info(f"[CLEAN] {sample} 清理了 {len(deleted)} 个文件/目录")

            logging.info(f"[OK] {sample}")
            return {
                "sample": sample,
                "status": "OK",
                "success": True,
                "returncode": 0,
            }

        except subprocess.TimeoutExpired:
            if proc:
                _terminate_proc(proc)
            if _processes_lock:
                with _processes_lock:
                    _running_processes.pop(sample, None)

            logging.error(f"[TIMEOUT] {sample} 超时 (>{timeout}s)")
            return {
                "sample": sample,
                "status": "TIMEOUT",
                "success": False,
                "returncode": -1,
                "error": f"执行超时 (>{timeout}s)",
            }

        except Exception as e:
            if proc:
                _terminate_proc(proc)
            if _processes_lock:
                with _processes_lock:
                    _running_processes.pop(sample, None)

            logging.error(f"[ERROR] {sample} {e}")
            return {
                "sample": sample,
                "status": "ERROR",
                "success": False,
                "returncode": -1,
                "error": str(e),
            }

    def run_batch(
        self,
        samples: Dict[str, Tuple[Path, Optional[Path]]],
        output_dir: Path,
        mode: str = "default",
        parallel_jobs: int = 4,
        **kwargs,
    ) -> List[Dict]:
        """
        批量执行。

        Args:
            samples: {sample_name: (fq1, fq2)}
            output_dir: 输出目录
            mode: 组装模式
            parallel_jobs: 并行任务数

        Returns:
            结果列表
        """
        results = []

        with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
            futures = {}
            for sample, (fq1, fq2) in samples.items():
                future = executor.submit(
                    self.run_single,
                    sample, fq1, fq2, output_dir, mode,
                    **kwargs,
                )
                futures[future] = sample

            for future in as_completed(futures):
                sample = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logging.error(f"[ERROR] {sample}: {e}")
                    results.append({
                        "sample": sample,
                        "status": "ERROR",
                        "success": False,
                        "error": str(e),
                    })

        return results


# ==============================================================
# 辅助函数
# ==============================================================

def find_fastq_pairs(
    directory: Path,
    r1_suffix: str = "_1.fastq.gz",
    r2_suffix: str = "_2.fastq.gz",
    fastq_pos: str = "auto",
) -> Dict[str, Tuple[Path, Path]]:
    """
    查找双端 FASTQ 文件对。

    Returns:
        {sample_name: (fq1_path, fq2_path)}
    """
    samples = {}
    directory = Path(directory)

    # 后缀列表
    suffixes = [r1_suffix, r2_suffix]

    if fastq_pos == "flat":
        for fq1 in sorted(directory.glob(f"*{r1_suffix}")):
            sample = fq1.name[:-len(r1_suffix)]
            fq2 = directory / (sample + r2_suffix)
            if fq2.exists():
                samples[sample] = (fq1, fq2)

    elif fastq_pos == "subdir":
        for subdir in sorted(directory.iterdir()):
            if subdir.is_dir():
                for fq1 in subdir.glob(f"*{r1_suffix}"):
                    sample = subdir.name
                    fq2 = subdir / (sample + r2_suffix)
                    if not fq2.exists():
                        fq2 = subdir / fq1.name.replace(r1_suffix, r2_suffix)
                    if fq2.exists():
                        samples[sample] = (fq1, fq2)
                        break

    else:  # auto or recursive
        for fq1 in directory.rglob(f"*{r1_suffix}"):
            sample = fq1.parent.name
            fq2 = fq1.parent / fq1.name.replace(r1_suffix, r2_suffix)
            if fq2.exists():
                if sample in samples:
                    logging.warning(f"[WARN] 重名样本 '{sample}'")
                samples[sample] = (fq1, fq2)

    return samples


def write_status_file(output_dir: Path, results: List[Dict], mode: str):
    """写入状态文件"""
    status_file = output_dir / "spades_status.txt"

    with open(status_file, "w") as f:
        f.write(f"# Generated at {datetime.now().isoformat()}\n")
        f.write(f"# Mode: {mode}\n\n")

        for status in ["OK", "SKIP", "FAILED", "TIMEOUT", "ERROR"]:
            samples_with_status = [r["sample"] for r in results if r.get("status") == status]
            if samples_with_status:
                f.write(f"# {status}\n")
                for s in sorted(samples_with_status):
                    f.write(f"{s}\n")
                f.write("\n")


# 初始化锁
_init_lock()
