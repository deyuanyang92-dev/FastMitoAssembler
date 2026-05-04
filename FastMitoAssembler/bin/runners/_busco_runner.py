"""
BUSCO Python Runner - 批量评估不依赖 Snakemake

设计参考:
  - 官方文档: https://busco.ezlab.org/
  - 参考实现: scripts/busco_batch.py
  - 参考模式: FastMitoAssembler/bin/runners/_spades_runner.py

关键特性:
  - Popen 流式读取（避免缓冲区满导致子进程挂起）
  - Checkpoint 检测（自动续跑未完成任务）
  - 多种评估模式（genome, transcriptome, proteins）
  - 离线模式支持
  - 错误诊断与提示
  - 并行执行
"""

import subprocess
import logging
import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed


# ==============================================================
# 全局变量
# ==============================================================

VALID_MODES = {"genome", "transcriptome", "proteins"}

# BUSCO 错误模式
BUSCO_ERROR_PATTERNS = {
    "lineage_not_found": [
        r"lineage.*not found",
        r"Cannot find lineage",
    ],
    "already_exists": [
        r"A run with the name.*already exists",
    ],
    "augustus_not_found": [
        r"Augustus not found",
        r"AUGUSTUS_CONFIG_PATH not set",
    ],
    "memory": [
        r"Out of memory",
        r"Killed",
    ],
    "input_error": [
        r"Cannot open file",
        r"Invalid FASTA",
    ],
}


# ==============================================================
# 辅助函数
# ==============================================================

def find_fasta_files(input_dir: Path, pattern: str = "*.fasta") -> Dict[str, Path]:
    """Find FASTA files in input directory.

    Args:
        input_dir: Input directory path
        pattern: Glob pattern for FASTA files

    Returns:
        Dict mapping sample names to FASTA file paths
    """
    input_dir = Path(input_dir)
    samples = {}

    # Look for FASTA files directly in input_dir
    for ext in [".fasta", ".fa", ".fna", ".faa", ".fna.gz", ".fasta.gz"]:
        for f in input_dir.glob(f"*{ext}"):
            sample = f.stem.replace(".fasta", "").replace(".fa", "").replace(".fna", "")
            samples[sample] = f

    # Look for FASTA files in subdirectories (SPAdes output structure)
    for subdir in input_dir.iterdir():
        if subdir.is_dir():
            for fasta_name in ["contigs.fasta", "scaffolds.fasta", "transcripts.fasta"]:
                f = subdir / fasta_name
                if f.exists():
                    samples[subdir.name] = f
                    break

    return samples


def write_busco_status(output_dir: Path, results: List[Dict], lineage: str, mode: str):
    """Write BUSCO status file."""
    status_file = output_dir / "busco_status.txt"
    with open(status_file, "w") as f:
        f.write(f"# BUSCO Status Report\n")
        f.write(f"# Generated: {datetime.now().isoformat()}\n")
        f.write(f"# Lineage: {lineage}\n")
        f.write(f"# Mode: {mode}\n\n")

        for r in results:
            sample = r.get("sample", "unknown")
            status = r.get("status", "UNKNOWN")
            complete = r.get("complete", "?")
            duplicated = r.get("duplicated", "?")
            fragmented = r.get("fragmented", "?")
            missing = r.get("missing", "?")
            f.write(f"{sample}\t{status}\t{complete}\t{duplicated}\t{fragmented}\t{missing}\n")


def diagnose_busco_error(log_content: str) -> Dict:
    """Diagnose BUSCO errors from log content."""
    errors = []
    hints = []

    for error_type, patterns in BUSCO_ERROR_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, log_content, re.IGNORECASE):
                errors.append(error_type)
                if error_type == "lineage_not_found":
                    hints.append("Lineage 数据库未找到: 检查 lineage 名称或使用 --offline 模式")
                elif error_type == "already_exists":
                    hints.append("运行目录已存在: 使用 --force 参数覆盖")
                elif error_type == "augustus_not_found":
                    hints.append("Augustus 未找到: 确保 BUSCO conda 环境正确安装")
                elif error_type == "memory":
                    hints.append("内存不足: 减少并行任务数或增加内存")
                elif error_type == "input_error":
                    hints.append("输入文件错误: 检查 FASTA 文件格式和路径")
                break

    return {"errors": errors, "hints": hints}


def parse_busco_summary(summary_file: Path) -> Dict:
    """Parse BUSCO short_summary.txt file."""
    if not summary_file.exists():
        return {}

    result = {}
    with open(summary_file) as f:
        for line in f:
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if "complete BUSCOs" in key:
                    result["complete"] = value.split()[0] if value else "0"
                elif "complete and single-copy" in key:
                    result["single_copy"] = value.split()[0] if value else "0"
                elif "complete and duplicated" in key:
                    result["duplicated"] = value.split()[0] if value else "0"
                elif "fragmented" in key:
                    result["fragmented"] = value.split()[0] if value else "0"
                elif "missing" in key:
                    result["missing"] = value.split()[0] if value else "0"
                elif "total BUSCO groups" in key:
                    result["total"] = value.split()[0] if value else "0"

    return result


# ==============================================================
# BUSCO Runner 类
# ==============================================================

class BuscoRunner:
    """BUSCO evaluation runner."""

    def __init__(self, threads: int = 12, shell_prefix: str = ""):
        self.threads = threads
        self.shell_prefix = shell_prefix

    def build_command(
        self,
        input_fasta: Path,
        output_dir: Path,
        lineage: str,
        mode: str = "genome",
        offline: bool = False,
        download_path: Optional[Path] = None,
        force: bool = False,
        **kwargs,
    ) -> List[str]:
        """Build BUSCO command."""
        cmd = ["busco"]

        # Input
        cmd.extend(["-i", str(input_fasta)])

        # Output
        cmd.extend(["-o", str(output_dir.name)])
        cmd.extend(["--out_path", str(output_dir.parent)])

        # Lineage
        cmd.extend(["-l", lineage])

        # Mode
        cmd.extend(["-m", mode])

        # Threads
        cmd.extend(["-c", str(self.threads)])

        # Offline mode
        if offline:
            cmd.append("--offline")
            if download_path:
                cmd.extend(["--download_path", str(download_path)])

        # Force overwrite
        if force:
            cmd.append("--force")

        # Extra arguments
        extra_args = kwargs.get("extra_args", "")
        if extra_args:
            cmd.extend(extra_args.split())

        return cmd

    def is_sample_done(self, output_dir: Path) -> bool:
        """Check if BUSCO run completed."""
        summary_file = output_dir / "short_summary.specific." + output_dir.name + ".txt"
        if summary_file.exists():
            return True
        # Also check generic summary
        for f in output_dir.glob("short_summary*.txt"):
            return True
        return False

    def run_single(
        self,
        sample: str,
        input_fasta: Path,
        output_dir: Path,
        lineage: str,
        mode: str = "genome",
        force: bool = False,
        offline: bool = False,
        download_path: Optional[Path] = None,
        timeout: int = 86400,
        **kwargs,
    ) -> Dict:
        """Run BUSCO on a single sample."""
        result = {
            "sample": sample,
            "input": str(input_fasta),
            "output": str(output_dir),
            "status": "UNKNOWN",
        }

        # Check if already done
        if not force and self.is_sample_done(output_dir):
            result["status"] = "SKIP"
            result["message"] = "Already completed"
            return result

        # Build command
        cmd = self.build_command(
            input_fasta,
            output_dir,
            lineage,
            mode,
            offline,
            download_path,
            force,
            **kwargs,
        )

        # Add shell prefix if needed
        if self.shell_prefix:
            cmd_str = self.shell_prefix + " ".join(cmd)
            cmd = ["bash", "-c", cmd_str]

        logging.info(f"[RUN] {sample}: {' '.join(cmd[:5])}...")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            stdout, _ = proc.communicate(timeout=timeout)

            # Check result
            if proc.returncode == 0 or self.is_sample_done(output_dir):
                result["status"] = "OK"

                # Parse summary
                summary_files = list(output_dir.glob("short_summary*.txt"))
                if summary_files:
                    busco_stats = parse_busco_summary(summary_files[0])
                    result.update(busco_stats)
            else:
                result["status"] = "FAILED"
                result["returncode"] = proc.returncode

                # Diagnose error
                diagnosis = diagnose_busco_error(stdout)
                if diagnosis["errors"]:
                    result["errors"] = diagnosis["errors"]
                    result["hints"] = diagnosis["hints"]

            result["log"] = stdout[-5000:] if len(stdout) > 5000 else stdout

        except subprocess.TimeoutExpired:
            proc.kill()
            result["status"] = "TIMEOUT"
            result["message"] = f"Timeout after {timeout}s"

        except Exception as e:
            result["status"] = "ERROR"
            result["message"] = str(e)

        return result

    def run_batch(
        self,
        samples: Dict[str, Path],
        output_dir: Path,
        lineage: str,
        mode: str = "genome",
        parallel_jobs: int = 3,
        force: bool = False,
        offline: bool = False,
        download_path: Optional[Path] = None,
        timeout: int = 86400,
        **kwargs,
    ) -> List[Dict]:
        """Run BUSCO on multiple samples in parallel."""
        results = []

        with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
            futures = {}
            for sample, fasta_path in samples.items():
                sample_output = output_dir / sample
                future = executor.submit(
                    self.run_single,
                    sample,
                    fasta_path,
                    sample_output,
                    lineage,
                    mode,
                    force,
                    offline,
                    download_path,
                    timeout,
                    **kwargs,
                )
                futures[future] = sample

            for future in as_completed(futures):
                sample = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    status = result.get("status", "UNKNOWN")
                    logging.info(f"[DONE] {sample}: {status}")
                except Exception as e:
                    results.append({
                        "sample": sample,
                        "status": "ERROR",
                        "message": str(e),
                    })

        return results
