"""
Fastp Python Runner - 批量质控不依赖 Snakemake

设计参考:
  - 官方文档: https://github.com/OpenGene/fastp
  - 本地源码: FastMitoAssembler/smk/rules/preprocess.smk
  - 参考实现: FastMitoAssembler/bin/runners/_meangs_runner.py
  - 参考脚本: scripts/fastpv3.py (单端支持、自动结构检测、输出记录)

关键特性:
  - Popen 流式读取（避免缓冲区满导致子进程挂起）
  - Checkpoint 检测（自动续跑未完成任务）
  - 预设模式支持（adapter_only, shallow_data, transcriptome, full_qc）
  - 单端/双端数据支持（PE/SE/all_type）
  - 自动目录结构检测
  - 输出文件记录（finished/unfinished.txt）
  - ThreadPoolExecutor 并行执行
  - 信号处理（优雅关闭）

预设模式:
  adapter_only:   仅去接头（推荐 mitogenome 组装）
                  --detect_adapter_for_pe -Q -L
  shallow_data:   最大化保留 reads（低深度数据、古 DNA）
                  --detect_adapter_for_pe -Q -L --n_base_limit 10 --disable_low_complexity_filter
  transcriptome:  Poly-A/T 修剪 + 质量过滤（RNA-seq）
                  --detect_adapter_for_pe --trim_poly_x --cut_front --cut_tail ...
  full_qc:        标准 WGS 质控
                  --detect_adapter_for_pe --qualified_quality_phred 20 ...

输出文件:
  {output_dir}/{sample}/
  ├── {sample}_1.clean.fq.gz    # 输出 R1 (PE)
  ├── {sample}_2.clean.fq.gz    # 输出 R2 (PE)
  ├── {sample}.clean.fq.gz      # 输出 (SE)
  ├── fastp.json                # JSON 报告
  ├── fastp.html                # HTML 报告
  └── fastp.log                 # 运行日志

  {output_dir}/
  ├── finished_fastp.txt        # 成功样本列表
  ├── unfinished_fastp.txt      # 失败样本列表
  └── fastp_checked.txt         # 检测到的文件列表
"""

import subprocess
import logging
import os
import shlex
import signal
import atexit
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed


# 全局变量：跟踪正在运行的进程
_running_processes = {}
_shutdown_requested = False


def _signal_handler(signum, frame):
    """信号处理器：终止所有子进程"""
    global _shutdown_requested
    _shutdown_requested = True
    logging.warning(f"[SIGNAL] 收到信号 {signum}，正在终止所有子进程...")
    import time
    for sample, proc in list(_running_processes.items()):
        if proc.poll() is None:
            logging.warning(f"[SIGNAL] 终止 {sample} (PID: {proc.pid})")
            proc.terminate()
    time.sleep(0.5)
    for sample, proc in list(_running_processes.items()):
        if proc.poll() is None:
            logging.warning(f"[SIGNAL] 强制杀死 {sample}")
            proc.kill()
    import sys
    sys.exit(128 + signum)


def _cleanup_on_exit():
    """退出时清理子进程"""
    import time
    for sample, proc in list(_running_processes.items()):
        if proc.poll() is None:
            proc.terminate()
    time.sleep(0.5)
    for sample, proc in list(_running_processes.items()):
        if proc.poll() is None:
            proc.kill()


# 注册信号处理器
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)
atexit.register(_cleanup_on_exit)


# ==============================================================
# 预设模式定义
# ==============================================================

FASTP_PRESETS = {
    "default": {
        "description": "fastp default parameters - auto adapter detection + Q15 quality filter + 15bp length filter",
        "recommended_for": "general use, let fastp decide",
        "args": {},
        "cmd_flags": "",  # 空字符串，使用 fastp 全部默认值
    },

    "adapter_only": {
        "description": "Adapter trimming only - preserves all reads for assembly",
        "recommended_for": "mitogenome assembly (NOVOPlasty, GetOrganelle)",
        "args": {
            "detect_adapter_for_pe": True,
            "disable_quality_filtering": True,
            "disable_length_filtering": True,
        },
        "cmd_flags": "--detect_adapter_for_pe -Q -L",
    },

    "shallow_data": {
        "description": "Maximum read preservation for low-depth data",
        "recommended_for": "low-coverage sequencing, ancient DNA",
        # NOTE: 低复杂度过滤默认关闭，无需 disable_low_complexity_filter
        "args": {
            "detect_adapter_for_pe": True,
            "disable_quality_filtering": True,
            "disable_length_filtering": True,
            "n_base_limit": 10,
        },
        "cmd_flags": "--detect_adapter_for_pe -Q -L --n_base_limit 10",
    },

    "transcriptome": {
        "description": "Quality + poly-A/T trimming for RNA-seq",
        "recommended_for": "RNA-seq, transcriptome assembly",
        # NOTE: 低复杂度过滤默认关闭，无需 disable_low_complexity_filter
        "args": {
            "detect_adapter_for_pe": True,
            "trim_poly_x": True,
            "poly_x_min_len": 10,
            "cut_front": True,
            "cut_tail": True,
            "cut_window_size": 4,
            "cut_mean_quality": 20,
            "length_required": 30,
        },
        "cmd_flags": (
            "--detect_adapter_for_pe "
            "--trim_poly_x --poly_x_min_len 10 "
            "--cut_front --cut_tail "
            "--cut_window_size 4 --cut_mean_quality 20 "
            "--length_required 30"
        ),
    },

    "full_qc": {
        "description": "Standard WGS quality control",
        "recommended_for": "whole genome sequencing",
        "args": {
            "detect_adapter_for_pe": True,
            "qualified_quality_phred": 20,
            "unqualified_percent_limit": 20,
            "length_required": 50,
            "cut_window_size": 4,
            "cut_mean_quality": 20,
        },
        "cmd_flags": (
            "--detect_adapter_for_pe "
            "--qualified_quality_phred 20 "
            "--unqualified_percent_limit 20 "
            "--length_required 50 "
            "--cut_window_size 4 --cut_mean_quality 20"
        ),
    },
}

# 可用预设模式列表
PRESET_MODES = list(FASTP_PRESETS.keys())


# ==============================================================
# 辅助函数
# ==============================================================

def is_sample_done(output_dir: Path, sample: str) -> bool:
    """
    判断样本是否已成功完成。

    完成判据:
      1. {sample}_1.clean.fq.gz 存在且非空
      2. {sample}_2.clean.fq.gz 存在且非空
      3. fastp.json 存在（报告）
    """
    if not output_dir.exists():
        return False

    sample_dir = output_dir / sample

    fq1 = sample_dir / f"{sample}_1.clean.fq.gz"
    fq2 = sample_dir / f"{sample}_2.clean.fq.gz"
    json_report = sample_dir / "fastp.json"

    return (
        fq1.exists() and fq1.stat().st_size > 0
        and fq2.exists() and fq2.stat().st_size > 0
        and json_report.exists()
    )


def get_output_files(output_dir: Path, sample: str) -> Dict[str, Optional[Path]]:
    """
    获取已处理样本的输出文件路径。

    Returns:
        {
            "fq1": Path or None,
            "fq2": Path or None,
            "json": Path or None,
            "html": Path or None,
        }
    """
    sample_dir = output_dir / sample
    result = {"fq1": None, "fq2": None, "json": None, "html": None}

    fq1 = sample_dir / f"{sample}_1.clean.fq.gz"
    fq2 = sample_dir / f"{sample}_2.clean.fq.gz"
    json_report = sample_dir / "fastp.json"
    html_report = sample_dir / "fastp.html"

    if fq1.exists() and fq1.stat().st_size > 0:
        result["fq1"] = fq1
    if fq2.exists() and fq2.stat().st_size > 0:
        result["fq2"] = fq2
    if json_report.exists():
        result["json"] = json_report
    if html_report.exists():
        result["html"] = html_report

    return result


def parse_reads_dir(
    reads_dir: Path,
    r1_suffix: str = "_1.clean.fq.gz",
    r2_suffix: str = "_2.clean.fq.gz",
    fastq_pos: str = "subdir",
) -> Dict[str, Tuple[str, str]]:
    """
    解析 reads 目录，返回样本名到 FASTQ 路径的映射。

    Args:
        reads_dir: reads 目录
        r1_suffix: R1 文件后缀
        r2_suffix: R2 文件后缀
        fastq_pos: 文件位置模式 (subdir/flat/recursive)
            - subdir: 在一级子目录中查找（默认）
            - flat: 直接在 reads_dir 下查找
            - recursive: 递归查找

    Returns:
        {sample_name: (fq1_path, fq2_path)}
    """
    samples = {}
    reads_dir = Path(reads_dir)

    logging.debug(f"[DEBUG] parse_reads_dir: {reads_dir}")
    logging.debug(f"[DEBUG] r1_suffix: {r1_suffix}, r2_suffix: {r2_suffix}")
    logging.debug(f"[DEBUG] fastq_pos: {fastq_pos}")

    if fastq_pos == "flat":
        # 直接在 reads_dir 下查找
        for f in reads_dir.glob(f"*{r1_suffix}"):
            sample = f.name[:-len(r1_suffix)]
            fq2 = reads_dir / f.name.replace(r1_suffix, r2_suffix)
            if fq2.exists():
                samples[sample] = (str(f), str(fq2))
                logging.debug(f"[DEBUG] found sample (flat): {sample}")

    elif fastq_pos == "subdir":
        # 在一级子目录中查找
        for subdir in sorted(reads_dir.iterdir()):
            if subdir.is_dir():
                for f in subdir.glob(f"*{r1_suffix}"):
                    sample = subdir.name  # 使用子目录名作为样本名
                    fq2 = subdir / f.name.replace(r1_suffix, r2_suffix)
                    if fq2.exists():
                        samples[sample] = (str(f), str(fq2))
                        logging.debug(f"[DEBUG] found sample (subdir): {sample}")
                        break  # 每个子目录只取一对

    else:  # recursive
        # 递归查找
        for f in reads_dir.rglob(f"*{r1_suffix}"):
            sample = f.parent.name
            fq2 = f.parent / f.name.replace(r1_suffix, r2_suffix)
            if fq2.exists():
                samples[sample] = (str(f), str(fq2))
                logging.debug(f"[DEBUG] found sample (recursive): {sample}")

    logging.info(f"[PARSE] 找到 {len(samples)} 个样本")
    return samples


# ==============================================================
# FastpRunner 类
# ==============================================================

class FastpRunner:
    """
    Fastp 批量执行器。

    用法:
        runner = FastpRunner(threads=8, shell_prefix="conda run -n fastp ")
        results = runner.run_batch(samples, output_dir, mode="adapter_only")

    参数说明:
        threads: fastp 线程数 (-w)
        shell_prefix: shell 命令前缀（conda 环境或 PATH 设置）
    """

    def __init__(self, threads: int = 8, shell_prefix: str = ""):
        self.threads = threads
        self.shell_prefix = shell_prefix

    def build_command(
        self,
        fq1: str,
        fq2: str,
        output_fq1: str,
        output_fq2: str,
        json_report: str,
        html_report: str,
        mode: str = "adapter_only",
        extra_args: Optional[str] = None,
        **kwargs,
    ) -> List[str]:
        """
        构建 fastp 命令。

        Args:
            fq1, fq2: 输入 FASTQ 文件
            output_fq1, output_fq2: 输出 FASTQ 文件
            json_report, html_report: 报告路径
            mode: 预设模式 (adapter_only, shallow_data, transcriptome, full_qc)
            extra_args: 额外 fastp 参数（透传）
            **kwargs: 覆盖预设参数
        """
        cmd = ["fastp"]

        # 输入/输出
        cmd.extend(["-i", shlex.quote(fq1), "-I", shlex.quote(fq2)])
        cmd.extend(["-o", shlex.quote(output_fq1), "-O", shlex.quote(output_fq2)])
        cmd.extend(["-j", shlex.quote(json_report), "-h", shlex.quote(html_report)])

        # 线程数
        cmd.extend(["-w", str(self.threads)])

        # 应用预设模式
        if mode in FASTP_PRESETS:
            preset = FASTP_PRESETS[mode]
            cmd.extend(preset["cmd_flags"].split())

        # 应用参数覆盖
        self._apply_overrides(cmd, kwargs)

        # 额外参数（透传）
        if extra_args:
            cmd.extend(extra_args.split() if isinstance(extra_args, str) else extra_args)

        return cmd

    def _apply_overrides(self, cmd: List[str], kwargs: Dict):
        """应用参数覆盖到命令。"""
        # 接头控制
        if kwargs.get("disable_adapter_trimming"):
            cmd.append("--disable_adapter_trimming")
        if kwargs.get("adapter_sequence"):
            cmd.extend(["--adapter_sequence", kwargs["adapter_sequence"]])
        if kwargs.get("adapter_sequence_r2"):
            cmd.extend(["--adapter_sequence_r2", kwargs["adapter_sequence_r2"]])

        # 质量过滤
        if kwargs.get("disable_quality_filtering"):
            cmd.append("-Q")
        if kwargs.get("qualified_quality_phred"):
            cmd.extend(["--qualified_quality_phred", str(kwargs["qualified_quality_phred"])])
        if kwargs.get("unqualified_percent_limit"):
            cmd.extend(["--unqualified_percent_limit", str(kwargs["unqualified_percent_limit"])])
        if kwargs.get("n_base_limit") is not None:
            cmd.extend(["--n_base_limit", str(kwargs["n_base_limit"])])

        # 长度过滤
        if kwargs.get("disable_length_filtering"):
            cmd.append("-L")
        if kwargs.get("length_required"):
            cmd.extend(["--length_required", str(kwargs["length_required"])])

        # 滑动窗口修剪
        if kwargs.get("cut_front"):
            cmd.append("--cut_front")
        if kwargs.get("cut_tail"):
            cmd.append("--cut_tail")
        if kwargs.get("cut_window_size"):
            cmd.extend(["--cut_window_size", str(kwargs["cut_window_size"])])
        if kwargs.get("cut_mean_quality"):
            cmd.extend(["--cut_mean_quality", str(kwargs["cut_mean_quality"])])

        # PolyG/PolyX 修剪
        if kwargs.get("trim_poly_g"):
            cmd.append("--trim_poly_g")
        if kwargs.get("disable_trim_poly_g"):
            cmd.append("-G")
        if kwargs.get("trim_poly_x"):
            cmd.append("--trim_poly_x")
        if kwargs.get("poly_x_min_len"):
            cmd.extend(["--poly_x_min_len", str(kwargs["poly_x_min_len"])])

        # 低复杂度过滤
        if kwargs.get("disable_low_complexity_filter"):
            cmd.append("--disable_low_complexity_filter")
        if kwargs.get("complexity_threshold"):
            cmd.extend(["--complexity_threshold", str(kwargs["complexity_threshold"])])

    def run_single(
        self,
        sample: str,
        fq1: str,
        fq2: str,
        output_dir: Path,
        force: bool = False,
        mode: str = "adapter_only",
        **kwargs,
    ) -> Dict:
        """
        执行单个样本 fastp 处理。

        输出结构:
            {output_dir}/{sample}/
            ├── {sample}_1.clean.fq.gz
            ├── {sample}_2.clean.fq.gz
            ├── fastp.json
            ├── fastp.html
            └── fastp.log
        """
        output_dir = Path(output_dir)
        sample_dir = output_dir / sample
        sample_dir.mkdir(parents=True, exist_ok=True)

        # Checkpoint 检测
        if not force and is_sample_done(output_dir, sample):
            logging.info(f"[SKIP] {sample} 已完成，跳过")
            return {"sample": sample, "status": "SKIP", "success": True}

        # 输出路径
        out_fq1 = sample_dir / f"{sample}_1.clean.fq.gz"
        out_fq2 = sample_dir / f"{sample}_2.clean.fq.gz"
        json_report = sample_dir / "fastp.json"
        html_report = sample_dir / "fastp.html"
        log_file = sample_dir / "fastp.log"

        # 构建命令
        cmd = self.build_command(
            fq1, fq2,
            str(out_fq1), str(out_fq2),
            str(json_report), str(html_report),
            mode=mode,
            extra_args=kwargs.get("extra_args"),
            **kwargs,
        )

        # 检查是否已请求关闭
        if _shutdown_requested:
            return {"sample": sample, "status": "SKIPPED", "success": False, "error": "Shutdown requested"}

        # 添加 shell prefix
        if self.shell_prefix:
            cmd_str = self.shell_prefix + " ".join(cmd)
        else:
            cmd_str = " ".join(cmd)

        logging.info(f"[RUN] {sample}: {cmd_str}")

        # 执行命令 - Popen 流式读取
        proc = None
        try:
            with open(log_file, "w") as log_f:
                proc = subprocess.Popen(
                    cmd_str,
                    shell=True,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                )
                # 注册到全局跟踪
                _running_processes[sample] = proc
                returncode = proc.wait()

            # 从跟踪中移除
            _running_processes.pop(sample, None)

            if returncode != 0:
                logging.error(f"[FAILED] {sample} 返回码: {returncode}")
                logging.error(f"[DEBUG] {sample} 检查日志: {log_file}")
                return {"sample": sample, "status": "FAILED", "success": False, "returncode": returncode}

            # 验证输出文件
            output_files = get_output_files(output_dir, sample)
            if not output_files["fq1"] or not output_files["fq2"]:
                logging.error(f"[FAILED] {sample} 输出文件不存在")
                logging.error(f"[DEBUG] {sample} 检查目录: {sample_dir}")
                return {"sample": sample, "status": "FAILED", "success": False, "error": "Output missing"}

            logging.info(f"[OK] {sample} 完成")
            return {
                "sample": sample,
                "status": "OK",
                "success": True,
                "output_files": {k: str(v) for k, v in output_files.items() if v},
            }

        except KeyboardInterrupt:
            # 用户中断，终止子进程
            if proc and proc.poll() is None:
                logging.warning(f"[INTERRUPT] {sample} 终止子进程...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            _running_processes.pop(sample, None)
            return {"sample": sample, "status": "INTERRUPTED", "success": False, "error": "KeyboardInterrupt"}

        except Exception as e:
            # 异常时也清理进程
            if proc and proc.poll() is None:
                proc.terminate()
            _running_processes.pop(sample, None)
            logging.error(f"[ERROR] {sample}: {e}")
            logging.error(f"[DEBUG] {sample} 检查日志: {log_file}")
            return {"sample": sample, "status": "ERROR", "success": False, "error": str(e)}

    def run_batch(
        self,
        samples: Dict[str, Tuple[str, str]],
        output_dir: Path,
        parallel_jobs: int = 4,
        **kwargs,
    ) -> List[Dict]:
        """
        批量执行 fastp 处理。

        Args:
            samples: {sample_name: (fq1_path, fq2_path)}
            output_dir: 输出根目录
            parallel_jobs: 并行任务数
            **kwargs: 传递给 run_single 的参数

        Returns:
            结果列表
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logging.info(f"[BATCH] 开始批量 fastp 处理，共 {len(samples)} 个样本")
        logging.info(f"[BATCH] 并行任务数: {parallel_jobs}")
        logging.info(f"[BATCH] 模式: {kwargs.get('mode', 'adapter_only')}")
        logging.debug(f"[DEBUG] samples: {list(samples.keys())}")

        results = []
        with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
            futures = {}
            for sample, (fq1, fq2) in samples.items():
                future = executor.submit(
                    self.run_single,
                    sample=sample,
                    fq1=fq1,
                    fq2=fq2,
                    output_dir=output_dir,
                    **kwargs,
                )
                futures[future] = sample

            for future in as_completed(futures):
                sample = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logging.error(f"[ERROR] {sample}: future 异常 - {e}")
                    results.append({"sample": sample, "status": "ERROR", "success": False, "error": str(e)})

        # 汇总
        success = sum(1 for r in results if r.get("success"))
        failed = sum(1 for r in results if r.get("status") == "FAILED")
        skipped = sum(1 for r in results if r.get("status") == "SKIP")
        error = sum(1 for r in results if r.get("status") == "ERROR")

        logging.info(f"[BATCH] 完成: {success} OK, {failed} FAILED, {skipped} SKIP, {error} ERROR")

        # 写入完成/未完成样本列表（吸收自 fastpv3.py）
        self._write_status_files(results, output_dir)

        return results

    def _write_status_files(self, results: List[Dict], output_dir: Path):
        """
        写入完成/未完成样本列表文件。

        吸收自 fastpv3.py:
          - finished_fastp.txt: 成功样本
          - unfinished_fastp.txt: 失败样本
        """
        output_dir = Path(output_dir)

        finished = [r["sample"] for r in results if r.get("success")]
        unfinished = [r["sample"] for r in results if not r.get("success")]

        if finished:
            finished_file = output_dir / "finished_fastp.txt"
            with open(finished_file, "w") as f:
                for sample in finished:
                    f.write(f"{sample}\n")
            logging.info(f"[STATUS] 成功样本列表: {finished_file}")

        if unfinished:
            unfinished_file = output_dir / "unfinished_fastp.txt"
            with open(unfinished_file, "w") as f:
                for sample in unfinished:
                    f.write(f"{sample}\n")
            logging.info(f"[STATUS] 失败样本列表: {unfinished_file}")


# ==============================================================
# 新增功能：吸收自 fastpv3.py
# ==============================================================

def detect_fastq_structure(root_dir: Path, suffixes: List[str]) -> set:
    """
    自动检测 FASTQ 文件的目录结构。

    吸收自 fastpv3.py 的 detect_fastq_structure()。

    Args:
        root_dir: 根目录
        suffixes: FASTQ 文件后缀列表

    Returns:
        检测到的结构集合: {"flat", "subdir", "two-level or deeper"}
    """
    structures = set()
    root_dir = Path(root_dir)

    for f in root_dir.rglob("*"):
        if f.is_file() and any(f.name.endswith(suffix) for suffix in suffixes):
            rel_path = f.relative_to(root_dir)
            directory_part = rel_path.parent

            if str(directory_part) == ".":
                structures.add("flat")
            else:
                num_levels = len(directory_part.parts)
                if num_levels == 1:
                    structures.add("subdir")
                else:
                    structures.add("two-level or deeper")

    return structures


def parse_reads_dir_auto(
    reads_dir: Path,
    r1_suffix: str = "_1.fastq.gz",
    r2_suffix: str = "_2.fastq.gz",
) -> Tuple[Dict[str, Tuple[str, str]], str]:
    """
    自动检测目录结构并解析 FASTQ 文件。

    吸收自 fastpv3.py 的自动检测逻辑。

    Returns:
        (samples, detected_structure)
    """
    reads_dir = Path(reads_dir)

    # 自动检测结构
    structures = detect_fastq_structure(reads_dir, [r1_suffix, r2_suffix])
    logging.info(f"[AUTO] 检测到目录结构: {', '.join(structures)}")

    # 根据检测结果选择解析模式
    if "flat" in structures:
        fastq_pos = "flat"
    elif "subdir" in structures:
        fastq_pos = "subdir"
    else:
        fastq_pos = "recursive"

    samples = parse_reads_dir(reads_dir, r1_suffix, r2_suffix, fastq_pos)
    return samples, fastq_pos


def write_checked_file(
    output_dir: Path,
    pe_samples: Optional[Dict] = None,
    se_samples: Optional[Dict] = None,
):
    """
    写入检测到的文件列表。

    吸收自 fastpv3.py 的 fastp_checked.txt 功能。

    Args:
        output_dir: 输出目录
        pe_samples: 双端样本 {sample: (fq1, fq2)}
        se_samples: 单端样本 {sample: fq}
    """
    output_dir = Path(output_dir)
    checked_file = output_dir / "fastp_checked.txt"

    with open(checked_file, "w") as f:
        if pe_samples:
            f.write("################## PE ####################\n")
            for sample, (fq1, fq2) in sorted(pe_samples.items()):
                f.write(f"PE: {sample}\n")
                f.write(f"  R1: {fq1}\n")
                f.write(f"  R2: {fq2}\n")

        if se_samples:
            f.write("\n################## SE ####################\n")
            for sample, fq in sorted(se_samples.items()):
                f.write(f"SE: {sample}\n")
                f.write(f"  File: {fq}\n")

    logging.info(f"[CHECKED] 文件列表: {checked_file}")


# ==============================================================
# 单端数据支持（吸收自 fastpv3.py）
# ==============================================================

def parse_reads_dir_se(
    reads_dir: Path,
    se_suffix: str = ".fastq.gz",
    fastq_pos: str = "subdir",
) -> Dict[str, str]:
    """
    解析单端 FASTQ 文件。

    吸收自 fastpv3.py 的 find_SE_files()。

    Args:
        reads_dir: reads 目录
        se_suffix: 单端文件后缀
        fastq_pos: 文件位置模式

    Returns:
        {sample_name: fq_path}
    """
    samples = {}
    reads_dir = Path(reads_dir)

    if fastq_pos == "flat":
        for f in reads_dir.glob(f"*{se_suffix}"):
            sample = f.name[:-len(se_suffix)]
            samples[sample] = str(f)

    elif fastq_pos == "subdir":
        for subdir in sorted(reads_dir.iterdir()):
            if subdir.is_dir():
                for f in subdir.glob(f"*{se_suffix}"):
                    sample = subdir.name
                    samples[sample] = str(f)
                    break

    else:  # recursive
        for f in reads_dir.rglob(f"*{se_suffix}"):
            sample = f.parent.name
            samples[sample] = str(f)

    logging.info(f"[PARSE-SE] 找到 {len(samples)} 个单端样本")
    return samples


def is_sample_done_se(output_dir: Path, sample: str) -> bool:
    """检查单端样本是否已完成。"""
    sample_dir = output_dir / sample
    fq = sample_dir / f"{sample}.clean.fq.gz"
    json_report = sample_dir / "fastp.json"

    return fq.exists() and fq.stat().st_size > 0 and json_report.exists()
