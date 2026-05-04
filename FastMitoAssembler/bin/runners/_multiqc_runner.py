"""
MultiQC Python Runner - 批量汇总报告生成

设计参考:
  - 官方文档: https://multiqc.info/
  - 参考实现: scripts/Summary_fastqc_using_fastqc_multiqc.py
  - 参考模式: FastMitoAssembler/bin/runners/_busco_runner.py

关键特性:
  - Popen 流式读取（避免缓冲区满导致子进程挂起）
  - 多目录输入支持
  - 强制覆盖选项
  - 错误诊断与提示
"""

import subprocess
import logging
import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# ==============================================================
# 全局变量
# ==============================================================

# MultiQC 错误模式
MULTIQC_ERROR_PATTERNS = {
    "no_results": [
        r"No analysis results found",
        r"Nothing to parse",
    ],
    "permission": [
        r"Permission denied",
        r"Cannot write to",
    ],
    "module_error": [
        r"Module.*error",
        r"Failed to parse",
    ],
}


# ==============================================================
# 辅助函数
# ==============================================================

def find_qc_directories(input_dir: Path) -> List[Path]:
    """Find directories containing QC results.

    Args:
        input_dir: Input directory path

    Returns:
        List of directories containing QC results
    """
    input_dir = Path(input_dir)
    qc_dirs = []

    # Look for common QC output directories
    qc_patterns = [
        "fastp", "fastqc", "busco", "spades",
        "multiqc_data", "qc", "quality",
    ]

    # Check direct subdirectories
    for subdir in input_dir.iterdir():
        if subdir.is_dir():
            # Check if directory name matches QC patterns
            if any(p in subdir.name.lower() for p in qc_patterns):
                qc_dirs.append(subdir)
            # Check for QC files in subdirectory
            for qc_file in ["fastp.json", "fastqc_data.txt", "short_summary.txt"]:
                if list(subdir.glob(f"**/{qc_file}")):
                    qc_dirs.append(subdir)

    # Also check the input directory itself
    for qc_file in ["fastp.json", "fastqc_data.txt", "short_summary.txt"]:
        if list(input_dir.glob(f"**/{qc_file}")):
            if input_dir not in qc_dirs:
                qc_dirs.append(input_dir)

    return qc_dirs


def diagnose_multiqc_error(log_content: str) -> Dict:
    """Diagnose MultiQC errors from log content."""
    errors = []
    hints = []

    for error_type, patterns in MULTIQC_ERROR_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, log_content, re.IGNORECASE):
                errors.append(error_type)
                if error_type == "no_results":
                    hints.append("未找到 QC 结果: 检查输入目录是否包含 fastp/fastqc/busco 等输出")
                elif error_type == "permission":
                    hints.append("权限问题: 检查输出目录写入权限")
                elif error_type == "module_error":
                    hints.append("模块解析错误: 检查 QC 文件格式是否正确")
                break

    return {"errors": errors, "hints": hints}


def parse_multiqc_report(report_file: Path) -> Dict:
    """Parse MultiQC report info."""
    if not report_file.exists():
        return {}

    result = {
        "report_path": str(report_file),
        "created": datetime.now().isoformat(),
    }

    # Check for data directory
    data_dir = report_file.parent / "multiqc_data"
    if data_dir.exists():
        result["data_dir"] = str(data_dir)

    return result


# ==============================================================
# MultiQC Runner 类
# ==============================================================

class MultiqcRunner:
    """MultiQC summary report runner."""

    def __init__(self, threads: int = 4, shell_prefix: str = ""):
        self.threads = threads
        self.shell_prefix = shell_prefix

    def build_command(
        self,
        input_dirs: List[Path],
        output_dir: Path,
        force: bool = False,
        **kwargs,
    ) -> List[str]:
        """Build MultiQC command."""
        cmd = ["multiqc"]

        # Input directories
        for d in input_dirs:
            cmd.append(str(d))

        # Output directory
        cmd.extend(["-o", str(output_dir)])

        # Force overwrite
        if force:
            cmd.append("-f")

        # Threads (MultiQC doesn't use threads directly, but for file parsing)
        # cmd.extend(["-t", str(self.threads)])

        # Extra arguments
        extra_args = kwargs.get("extra_args", "")
        if extra_args:
            cmd.extend(extra_args.split())

        return cmd

    def is_report_done(self, output_dir: Path) -> bool:
        """Check if MultiQC report exists."""
        report_file = output_dir / "multiqc_report.html"
        return report_file.exists()

    def run(
        self,
        input_dir: Path,
        output_dir: Path,
        force: bool = False,
        timeout: int = 3600,
        **kwargs,
    ) -> Dict:
        """Run MultiQC on all QC results."""
        result = {
            "input": str(input_dir),
            "output": str(output_dir),
            "status": "UNKNOWN",
        }

        # Check if already done
        if not force and self.is_report_done(output_dir):
            result["status"] = "SKIP"
            result["message"] = "Report already exists"
            return result

        # Find QC directories
        qc_dirs = find_qc_directories(input_dir)
        if not qc_dirs:
            result["status"] = "ERROR"
            result["message"] = "No QC results found in input directory"
            return result

        # Build command
        cmd = self.build_command(qc_dirs, output_dir, force, **kwargs)

        # Add shell prefix if needed
        if self.shell_prefix:
            cmd_str = self.shell_prefix + " ".join(cmd)
            cmd = ["bash", "-c", cmd_str]

        logging.info(f"[RUN] MultiQC: {' '.join(cmd[:5])}...")

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            stdout, _ = proc.communicate(timeout=timeout)

            # Check result
            if proc.returncode == 0 or self.is_report_done(output_dir):
                result["status"] = "OK"

                # Parse report info
                report_file = output_dir / "multiqc_report.html"
                if report_file.exists():
                    report_info = parse_multiqc_report(report_file)
                    result.update(report_info)
            else:
                result["status"] = "FAILED"
                result["returncode"] = proc.returncode

                # Diagnose error
                diagnosis = diagnose_multiqc_error(stdout)
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
        input_dirs: List[Path],
        output_dir: Path,
        force: bool = False,
        timeout: int = 3600,
        **kwargs,
    ) -> Dict:
        """Run MultiQC on multiple input directories (single report)."""
        # MultiQC inherently handles multiple directories in one run
        return self.run(input_dirs[0] if len(input_dirs) == 1 else input_dirs[0].parent,
                        output_dir, force, timeout, **kwargs)