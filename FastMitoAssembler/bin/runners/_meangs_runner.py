"""
MEANGS Python Runner - 批量组装不依赖 Snakemake

设计参考:
  - 官方仓库: https://github.com/YanCCscu/meangs
  - 本地源码: /media/deyuan/217ce44c-b5de-45ed-8720-deebdff85ece/ceshi/NEW_project/othertools/MEANGS/meangs.py
  - 参考脚本: /home/deyuan/Softs/jiaoben/MEANGS5.1.py

关键特性:
  - Popen 流式读取（避免缓冲区满导致子进程挂起）
  - Checkpoint 检测（自动续跑未完成任务）
  - 所有原始 MEANGS 参数支持
  - ThreadPoolExecutor 并行执行

⚠️ scaffold_seeds.fas 隔离问题:
  MEANGS deepin 模式会将 scaffold_seeds.fas 写入 CWD（硬编码）。
  本模块为每个样本创建独立工作目录，避免并行覆盖。
  详见: memory/project_meangs_scaffold_seeds_bug.md

MEANGS 工作流程:
  1. QC & Convert: seqtk 质控并转换为 FASTA
  2. HMM Search: nhmmer 搜索线粒体基因
  3. Reads Withdraw: 提取匹配的 reads
  4. Assembly: 组装 scaffolds
  5. HMM Annotation: 注释线粒体基因
  6. (Deepin) Extend: 使用 seed 延伸组装
  7. (Clip) Detect Circle: 检测环状切割点

输出文件:
  Quick 模式:
    - {sample}_scaffolds.fa         # 组装 scaffolds
    - {sample}_detected_mito.fas    # ★ 最终结果（HMM 筛选后）
    - {sample}_hmmout_tbl_sorted.gff # 基因注释

  Deepin 模式（额外）:
    - {sample}_deep_scaffolds.fa         # 延伸 scaffolds
    - {sample}_deep_detected_mito.fas    # ★ 最终结果
    - scaffold_seeds.fas                 # ⚠️ 写入 CWD，需隔离
    - mito_cliped.fas                    # (--clip) 环状切割点
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


# MEANGS 支持的物种类别
# 来源: MEANGS 源码第 29-31 行
# A-worms: Annelida 分节蠕虫
# N-worms: Nemertea 纽形动物
SPECIES_CLASSES = [
    "A-worms",        # Annelida (环节动物门)
    "Arthropoda",     # 节肢动物门
    "Bryozoa",        # 苔藓动物门
    "Chordata",       # 脊索动物门 (默认)
    "Echinodermata",  # 棘皮动物门
    "Mollusca",       # 软体动物门
    "Nematoda",       # 线虫动物门
    "N-worms",        # Nemertea (纽形动物门)
    "Porifera-sponges" # 海绵动物门
]


def is_sample_done(output_dir: Path, sample: str, deepin: bool = True) -> bool:
    """
    判断样本是否已成功完成。

    MEANGS 原始输出结构：
    {work_dir}/{sample}/
    ├── {sample}_scaffolds.fa             # Quick 组装 scaffolds
    ├── {sample}_detected_mito.fas        # ★ Quick 模式最终结果
    ├── {sample}_deep_scaffolds.fa        # Deepin 组装 scaffolds
    ├── {sample}_deep_detected_mito.fas   # ★ Deepin 模式最终结果
    ├── {sample}_hmmout_tbl_sorted.gff    # 基因注释
    └── ...

    完成判据：
      1. deep_detected_mito.fas 存在且非空（deepin 模式）
      2. detected_mito.fas 存在且非空（quick 模式）
    """
    if not output_dir.exists():
        return False

    # MEANGS 在 output_dir/{sample}/ 下创建 {sample}/ 子目录
    sample_dir = output_dir / sample / sample

    if deepin:
        result_file = sample_dir / f"{sample}_deep_detected_mito.fas"
    else:
        result_file = sample_dir / f"{sample}_detected_mito.fas"

    return result_file.exists() and result_file.stat().st_size > 0


def get_result_file(output_dir: Path, sample: str, deepin: bool = True) -> Optional[Path]:
    """
    获取 MEANGS 原始结果文件路径。

    不改变原始输出结构，只返回结果文件路径。
    """
    sample_dir = output_dir / sample / sample

    if deepin:
        result_file = sample_dir / f"{sample}_deep_detected_mito.fas"
    else:
        result_file = sample_dir / f"{sample}_detected_mito.fas"

    if result_file.exists() and result_file.stat().st_size > 0:
        return result_file
    return None


class MeangsRunner:
    """
    MEANGS 批量执行器

    参数说明（参考官方 README.md）:

    必需参数:
        -1, --fq1: R1 FASTQ 文件（支持 .fq.gz, .fastq.gz）
        -2, --fq2: R2 FASTQ 文件（可选，支持单端数据）
        -o, --outBase: 输出前缀

    组装参数:
        -t, --threads: 线程数（默认 1）
        -i, --insert: Insert size，文库插入长度（默认 350）
        -n, --nsample: 采样 reads 数（默认 0=全部）
                       ⚠️ 强烈推荐设置此参数以减少运行时间和内存
        -q, --quality: 低质量碱基阈值（默认 0.05）

    物种参数:
        --species_class: 物种类别（默认 Chordata）
            - A-worms: Annelida (环节动物)
            - Arthropoda: 节肢动物
            - Bryozoa: 苔藓动物
            - Chordata: 脊索动物 (默认)
            - Echinodermata: 棘皮动物
            - Mollusca: 软体动物
            - Nematoda: 线虫
            - N-worms: Nemertea (纽形动物)
            - Porifera-sponges: 海绵

    模式参数:
        --deepin: 启用深度组装模式
            Quick 模式: 快速组装，适合初步测试
            Deepin 模式: 使用 seed 延伸，获得更完整的结果

        --clip: 检测环状切割点
            输出 mito_cliped.fas 到上一级目录

    跳过步骤:
        --skipassem: 跳过组装（仅注释）
        --skipqc: 跳过质控
        --skiphmm: 跳过 HMM 搜索
        --skipextend: 跳过延伸（deepin 模式）

    其他参数:
        -s, --seqscaf: 指定 scaffold 文件用于注释
        --keepIntMed: 保留中间文件
        --keepMinLen: 质控后最小 read 长度（默认 30）
        --silence: 静默模式

    输出文件:
        Quick 模式:
            {sample}_scaffolds.fa          # 组装 scaffolds
            {sample}_detected_mito.fas     # ★ 最终结果
            {sample}_hmmout_tbl_sorted.gff # 基因注释

        Deepin 模式（额外）:
            {sample}_deep_scaffolds.fa     # 延伸 scaffolds
            {sample}_deep_detected_mito.fas # ★ 最终结果
            scaffold_seeds.fas             # ⚠️ 写入 CWD
            mito_cliped.fas                # (--clip)
    """

    def __init__(self, threads: int = 16, shell_prefix: str = ""):
        self.threads = threads
        self.shell_prefix = shell_prefix

    def build_command(
        self,
        fq1: str,
        fq2: str,
        sample: str,
        threads: Optional[int] = None,
        insert_size: int = 350,
        species_class: str = "Arthropoda",
        nsample: int = 2000000,
        deepin: bool = True,
        # 可选参数
        seqscaf: Optional[str] = None,
        clip: bool = False,
        keepIntMed: bool = False,
        keepMinLen: Optional[int] = None,
        skipassem: bool = False,
        skipqc: bool = False,
        skiphmm: bool = False,
        skipextend: bool = False,
        quality: float = 0.05,
    ) -> List[str]:
        """
        构建 MEANGS 命令

        注意: extra_args 不在此函数处理，而是在 run_single 中追加到命令字符串末尾，
        以保持用户提供的引号格式。

        参数详细说明:
            fq1: R1 FASTQ 文件路径
            fq2: R2 FASTQ 文件路径
            sample: 样本名（用作 -o 输出前缀）
            threads: 线程数（-t）
            insert_size: Insert size，文库插入长度（-i）
                - 对于 350bp 文库，使用 350
                - 对于 500bp 文库，使用 500
            species_class: 物种类别（--species_class）
                - 根据样本的物种选择正确的类别
                - 错误的类别可能导致 HMM 搜索失败
            nsample: 采样 reads 数（-n）
                - 默认 2000000（200万 reads）
                - 设置为 0 使用全部 reads
                - ⚠️ 强烈推荐设置以减少运行时间
            deepin: 是否启用深度组装模式
                - True: 使用 seed 延伸，获得更完整结果
                - False: 快速组装
            quality: 低质量碱基阈值（-q）
                - 默认 0.05
            clip: 是否检测环状切割点
                - 仅在 deepin 模式下有效
                - 输出 mito_cliped.fas
            keepIntMed: 是否保留中间文件
            keepMinLen: 质控后最小 read 长度
            skipassem: 跳过组装（仅注释）
            skipqc: 跳过质控
            skiphmm: 跳过 HMM 搜索
            skipextend: 跳过延伸（deepin 模式）
            seqscaf: 指定 scaffold 文件用于注释
        """
        # 使用 shlex.quote() 防止路径中的特殊字符导致注入
        cmd = ["meangs.py", "--silence"]
        cmd.extend(["-1", shlex.quote(fq1), "-2", shlex.quote(fq2)])
        cmd.extend(["-o", shlex.quote(sample)])
        cmd.extend(["-t", str(threads or self.threads)])
        cmd.extend(["-i", str(insert_size)])
        cmd.extend(["-n", str(nsample)])
        cmd.extend(["-q", str(quality)])
        cmd.extend(["--species_class", species_class])

        # 可选标志参数
        if deepin:
            cmd.append("--deepin")
        if clip:
            cmd.append("--clip")
        if keepIntMed:
            cmd.append("--keepIntMed")
        if skipassem:
            cmd.append("--skipassem")
        if skipqc:
            cmd.append("--skipqc")
        if skiphmm:
            cmd.append("--skiphmm")
        if skipextend:
            cmd.append("--skipextend")

        # 可选值参数
        if seqscaf:
            cmd.extend(["-s", shlex.quote(seqscaf)])
        if keepMinLen is not None:
            cmd.extend(["--keepMinLen", str(keepMinLen)])

        return cmd

    def run_single(
        self,
        sample: str,
        fq1: str,
        fq2: str,
        output_dir: Path,
        force: bool = False,
        deepin: bool = True,
        **kwargs,
    ) -> Dict:
        """
        执行单个样本组装。

        ⚠️ 关键：每个样本在独立工作目录中运行，避免 scaffold_seeds.fas 覆盖。

        MEANGS 原始输出结构（不改变）：
        {output_dir}/{sample}/{sample}/
        ├── {sample}_scaffolds.fa
        ├── {sample}_detected_mito.fas
        ├── {sample}_deep_scaffolds.fa
        ├── {sample}_deep_detected_mito.fas
        └── scaffold_seeds.fas  # 写入 work_dir，不是 sample_dir

        Debug 提示:
            - 检查 work_dir: {output_dir}/{sample}/
            - 检查 sample_dir: {output_dir}/{sample}/{sample}/
            - 检查日志: {output_dir}/{sample}/{sample}.log
            - 检查 scaffold_seeds.fas: {output_dir}/{sample}/scaffold_seeds.fas
        """
        output_dir = Path(output_dir)

        # ⚠️ 关键：每个样本在独立子目录中运行
        # MEANGS 会在 work_dir 下创建 {sample}/ 子目录
        # scaffold_seeds.fas 会写入 work_dir（不是 sample_dir）
        work_dir = output_dir / sample
        work_dir.mkdir(parents=True, exist_ok=True)

        # Debug: 记录工作目录
        logging.debug(f"[DEBUG] {sample} work_dir: {work_dir}")
        logging.debug(f"[DEBUG] {sample} expected sample_dir: {work_dir / sample}")

        # Checkpoint 检测
        if not force and is_sample_done(output_dir, sample, deepin):
            logging.info(f"[SKIP] {sample} 已完成，跳过")
            return {"sample": sample, "status": "SKIP", "success": True}

        # 构建命令
        cmd = self.build_command(fq1, fq2, sample, deepin=deepin, **kwargs)

        # 检查是否已请求关闭
        if _shutdown_requested:
            return {"sample": sample, "status": "SKIPPED", "success": False, "error": "Shutdown requested"}

        # 添加 shell prefix（conda 环境或 bin_dir）
        if self.shell_prefix:
            cmd_str = self.shell_prefix + " ".join(cmd)
        else:
            cmd_str = " ".join(cmd)

        # 追加额外参数（保持用户提供的格式）
        extra_args = kwargs.get("extra_args")
        if extra_args:
            cmd_str += " " + extra_args

        logging.info(f"[RUN] {sample}: {cmd_str}")

        # Debug: 记录完整命令和参数
        logging.debug(f"[DEBUG] {sample} full command: {cmd_str}")
        logging.debug(f"[DEBUG] {sample} cwd: {work_dir}")
        logging.debug(f"[DEBUG] {sample} deepin mode: {deepin}")
        logging.debug(f"[DEBUG] {sample} species_class: {kwargs.get('species_class', 'Arthropoda')}")

        # 执行命令 - 在 work_dir 目录下运行
        # MEANGS 会在当前目录下创建 {sample}/ 子目录
        log_file = work_dir / f"{sample}.log"
        proc = None
        try:
            with open(log_file, "w") as log_f:
                proc = subprocess.Popen(
                    cmd_str,
                    shell=True,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    cwd=str(work_dir),  # 关键：在独立目录运行，避免覆盖
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

            # 检查输出文件（MEANGS 原始输出）
            result_file = get_result_file(output_dir, sample, deepin)
            if not result_file:
                logging.error(f"[FAILED] {sample} 输出文件不存在")
                logging.error(f"[DEBUG] {sample} 检查目录: {work_dir / sample}")
                logging.error(f"[DEBUG] {sample} 检查日志: {log_file}")
                return {"sample": sample, "status": "FAILED", "success": False, "error": "Output not found"}

            # Debug: 记录结果文件
            logging.debug(f"[DEBUG] {sample} result_file: {result_file}")
            logging.debug(f"[DEBUG] {sample} result_file size: {result_file.stat().st_size} bytes")

            logging.info(f"[OK] {sample} 完成: {result_file}")
            return {
                "sample": sample,
                "status": "OK",
                "success": True,
                "result_file": str(result_file),
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
        parallel_jobs: int = 3,
        **kwargs,
    ) -> List[Dict]:
        """批量执行组装

        Args:
            samples: {sample_name: (fq1_path, fq2_path)}
            output_dir: 输出目录
            parallel_jobs: 并行任务数
            **kwargs: 传递给 run_single 的参数

        Returns:
            结果列表

        Debug 提示:
            - 每个样本在独立目录运行，避免 scaffold_seeds.fas 覆盖
            - 并行数建议: 3-5（取决于 CPU 和内存）
            - 检查总日志: {output_dir}/meangs_batch.log
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logging.info(f"[BATCH] 开始批量组装，共 {len(samples)} 个样本")
        logging.info(f"[BATCH] 并行任务数: {parallel_jobs}")
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

        return results


def parse_reads_dir(
    reads_dir: Path,
    r1_suffix: str = "_1.clean.fq.gz",
    r2_suffix: str = "_2.clean.fq.gz",
    fastq_pos: str = "subdir",
) -> Dict[str, Tuple[str, str]]:
    """解析 reads 目录，返回样本名到 FASTQ 路径的映射

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

    Debug 提示:
        - 如果找不到样本，检查 r1_suffix 和 r2_suffix 是否正确
        - 如果样本名不对，检查 fastq_pos 模式
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
        for subdir in reads_dir.iterdir():
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
