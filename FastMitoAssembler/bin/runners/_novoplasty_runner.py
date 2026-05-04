"""
NOVOPlasty Python Runner - 执行批量组装不依赖 Snakemake

设计参考: my_shh/get_batch.py
关键特性:
  - 多 kmer 顺序执行
  - 多 seed 尝试（复用 hash 表）
  - 自动选择最佳结果（优先 circularized）
  - Popen 流式读取
  - Checkpoint 检测
"""

import subprocess
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed


# 完成判据关键词
_SUCCESS_KEYWORDS = (
    "Final assembly saved",
    "Assembly completed",
    "Circular assembly",
    "succeeded",
)


def _log_has_success(log_file: Path) -> bool:
    """检查日志是否含成功关键词"""
    try:
        text = log_file.read_text(encoding="utf-8", errors="ignore")
        return any(kw in text for kw in _SUCCESS_KEYWORDS)
    except Exception:
        return False


def is_sample_done(output_dir: Path) -> bool:
    """
    判断样本是否已成功完成。

    完成判据：
      1. circularized.fasta 存在且非空（最佳）
      2. noncircularized.fasta 存在且非空（次佳）
      3. 日志含成功关键词
    """
    if not output_dir.exists():
        return False

    # 判据 1: circularized.fasta
    circular = output_dir / "circularized.fasta"
    if circular.exists() and circular.stat().st_size > 0:
        return True

    # 判据 2: noncircularized.fasta
    noncircular = output_dir / "noncircularized.fasta"
    if noncircular.exists() and noncircular.stat().st_size > 0:
        return True

    # 判据 3: 日志
    log_file = output_dir / "novoplasty.log"
    if log_file.exists() and _log_has_success(log_file):
        return True

    return False


def get_best_result(output_dir: Path) -> Optional[Path]:
    """
    获取最佳结果文件。

    优先级：
      1. circularized.fasta
      2. noncircularized.fasta
    """
    circular = output_dir / "circularized.fasta"
    if circular.exists() and circular.stat().st_size > 0:
        return circular

    noncircular = output_dir / "noncircularized.fasta"
    if noncircular.exists() and noncircular.stat().st_size > 0:
        return noncircular

    return None


class NovoplastyRunner:
    """
    NOVOPlasty Python 后端批量执行器

    特性：
      - 多 kmer 顺序执行
      - 多 seed 尝试
      - 自动选择最佳结果
    """

    # 默认 kmer 列表
    DEFAULT_KMERS = [33]

    def __init__(self, threads: int = 8, shell_prefix: str = ""):
        self.threads = threads
        self.shell_prefix = shell_prefix

    def build_config(
        self,
        sample: str,
        fq1: Path,
        fq2: Path,
        output_dir: Path,
        seed: Optional[Path] = None,
        kmer: int = 33,
        genome_min_size: int = 12000,
        genome_max_size: int = 22000,
        insert_size: int = 300,
        read_length: int = 150,
        max_mem_gb: int = 10,
        **kwargs,
    ) -> str:
        """
        构建 NOVOPlasty 配置文件内容。

        Args:
            sample: 样本名
            fq1: R1 文件路径
            fq2: R2 文件路径
            output_dir: 输出目录
            seed: seed 文件路径
            kmer: kmer 大小
            genome_min_size: 最小基因组大小
            genome_max_size: 最大基因组大小
            insert_size: 插入长度
            read_length: 读长
            max_mem_gb: 最大内存 (GB)

        Returns:
            配置文件内容
        """
        config = f"""Project:
-------------------------
Project name          : {sample}
Type                  : mito
Genome type           : circular
Read Length           : {read_length}
Insert size           : {insert_size}
K-mer                 : {kmer}

Data:
-------------------------
Input 1               : {fq1}
Input 2               : {fq2}

Output:
-------------------------
Output directory      : {output_dir}

Parameters:
-------------------------
Minimum genome size   : {genome_min_size}
Maximum genome size   : {genome_max_size}
Save k-mer hashes     : yes
Save best graphs      : yes
"""
        # 添加 seed（如果有）
        if seed and seed.exists():
            config += f"""
Seed:
-------------------------
Seed input            : {seed}
"""

        # 添加内存限制
        if max_mem_gb:
            config += f"""
Memory:
-------------------------
Max memory            : {max_mem_gb}
"""

        return config

    def build_command(
        self,
        config_file: Path,
        output_dir: Path,
        **kwargs,
    ) -> List[str]:
        """
        构建 NOVOPlasty 命令。

        Args:
            config_file: 配置文件路径
            output_dir: 输出目录

        Returns:
            命令参数列表
        """
        cmd = [
            "NOVOPlasty.pl",
            "-c", str(config_file),
        ]

        return cmd

    def run_single(
        self,
        sample: str,
        fq1: Path,
        fq2: Path,
        output_dir: Path,
        seed: Optional[Path] = None,
        kmers: Optional[List[int]] = None,
        num_seeds: int = 1,
        force: bool = False,
        **kwargs,
    ) -> Dict:
        """
        执行单个样本组装。

        Args:
            sample: 样本名
            fq1: R1 文件路径
            fq2: R2 文件路径
            output_dir: 输出目录
            seed: seed 文件路径
            kmers: kmer 列表
            num_seeds: seed 尝试次数
            force: 强制重跑

        Returns:
            执行结果
        """
        kmers = kmers or self.DEFAULT_KMERS
        output_dir = Path(output_dir)

        # Checkpoint 检测
        if not force and is_sample_done(output_dir):
            logging.info(f"[SKIP] {sample} 已完成，跳过")
            return {
                "sample": sample,
                "status": "SKIP",
                "success": True,
                "output_file": str(get_best_result(output_dir)),
            }

        logging.info(f"[RUN] {sample} 开始组装")

        # 多 kmer 尝试
        results = []
        for kmer in kmers:
            kmer_dir = output_dir / f"k{kmer}"
            kmer_dir.mkdir(parents=True, exist_ok=True)

            # 写入配置文件
            config_file = kmer_dir / "config.txt"
            config_content = self.build_config(
                sample=sample,
                fq1=fq1,
                fq2=fq2,
                output_dir=kmer_dir,
                seed=seed,
                kmer=kmer,
                **kwargs,
            )
            config_file.write_text(config_content)

            # 执行 NOVOPlasty
            cmd = self.build_command(config_file, kmer_dir, **kwargs)
            logging.info(f"[CMD] K={kmer}: {' '.join(cmd)}")

            result = self._execute_command(cmd, sample, kmer_dir)
            result["kmer"] = kmer
            results.append(result)

            # 如果成功且是 circularized，提前结束
            if result.get("success") and result.get("circularized"):
                logging.info(f"[OK] {sample} K={kmer} circularized，停止尝试")
                break

        # 选择最佳结果
        best = self._select_best_result(results, output_dir)

        return best

    def _execute_command(
        self,
        cmd: List[str],
        sample: str,
        work_dir: Path,
    ) -> Dict:
        """
        执行命令并捕获输出。
        """
        log_file = work_dir / "novoplasty.log"

        result = {
            "sample": sample,
            "success": False,
            "work_dir": str(work_dir),
        }

        try:
            if self.shell_prefix:
                full_cmd = f"{self.shell_prefix}{' '.join(cmd)}"
                proc = subprocess.Popen(
                    full_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=str(work_dir),
                )
            else:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=str(work_dir),
                )

            # 流式读取输出
            with open(log_file, "w") as log:
                for line in proc.stdout:
                    log.write(line)
                    logging.debug(f"  {line.rstrip()}")
            proc.stdout.close()
            returncode = proc.wait()

            result["returncode"] = returncode

            if returncode != 0:
                logging.error(f"[FAILED] {sample} (rc={returncode})")
                result["status"] = "FAILED"
                return result

            # 检查结果
            circular = work_dir / "circularized.fasta"
            noncircular = work_dir / "noncircularized.fasta"

            if circular.exists() and circular.stat().st_size > 0:
                logging.info(f"[OK] {sample} circularized")
                result["success"] = True
                result["status"] = "OK"
                result["circularized"] = True
                result["output_file"] = str(circular)
            elif noncircular.exists() and noncircular.stat().st_size > 0:
                logging.info(f"[OK] {sample} noncircularized")
                result["success"] = True
                result["status"] = "OK"
                result["circularized"] = False
                result["output_file"] = str(noncircular)
            else:
                logging.warning(f"[INCOMPLETE] {sample} 无结果文件")
                result["status"] = "INCOMPLETE"

        except Exception as e:
            logging.error(f"[ERROR] {sample}: {e}")
            result["error"] = str(e)
            result["status"] = "ERROR"

        return result

    def _select_best_result(
        self,
        results: List[Dict],
        output_dir: Path,
    ) -> Dict:
        """
        选择最佳结果。

        优先级：
          1. circularized
          2. noncircularized
          3. 最大 kmer
        """
        # 优先 circularized
        for r in results:
            if r.get("success") and r.get("circularized"):
                return r

        # 其次 noncircularized
        for r in results:
            if r.get("success"):
                return r

        # 都失败，返回最后一个
        if results:
            return results[-1]

        return {
            "sample": output_dir.name,
            "status": "FAILED",
            "success": False,
        }

    def run_batch(
        self,
        samples: Dict[str, Tuple[Path, Path]],
        output_root: Path,
        parallel_jobs: int = 1,
        seeds: Optional[Dict[str, Path]] = None,
        **kwargs,
    ) -> List[Dict]:
        """
        批量执行组装。

        Args:
            samples: {sample_name: (fq1_path, fq2_path)}
            output_root: 输出根目录
            parallel_jobs: 并行任务数
            seeds: {sample_name: seed_path}

        Returns:
            结果列表
        """
        seeds = seeds or {}
        results = []

        with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
            futures = {}
            for sample, (fq1, fq2) in samples.items():
                sample_dir = output_root / sample
                seed = seeds.get(sample)
                future = executor.submit(
                    self.run_single,
                    sample,
                    fq1,
                    fq2,
                    sample_dir,
                    seed=seed,
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
                        "error": str(e),
                    })

        return results


def parse_reads_dir(
    reads_dir: Path,
    r1_suffix: str = "_1.fastq.gz",
    r2_suffix: str = "_2.fastq.gz",
    fastq_pos: str = "recursive",
) -> Dict[str, Tuple[Path, Path]]:
    """
    解析 reads 目录。

    Args:
        reads_dir: reads 文件目录
        r1_suffix: R1 文件后缀
        r2_suffix: R2 文件后缀
        fastq_pos: 目录结构模式

    Returns:
        {sample_name: (fq1_path, fq2_path)}
    """
    samples = {}
    reads_dir = Path(reads_dir).resolve()

    if fastq_pos == "flat":
        for fq1 in reads_dir.glob(f"*{r1_suffix}"):
            sample = fq1.name[:-len(r1_suffix)]
            fq2 = reads_dir / f"{sample}{r2_suffix}"
            if fq2.exists():
                samples[sample] = (fq1, fq2)
    elif fastq_pos == "subdir":
        for subdir in sorted(reads_dir.iterdir()):
            if subdir.is_dir():
                for fq1 in subdir.glob(f"*{r1_suffix}"):
                    sample = subdir.name
                    fq2 = subdir / f"{fq1.name[:-len(r1_suffix)]}{r2_suffix}"
                    if fq2.exists():
                        samples[sample] = (fq1, fq2)
    else:
        for fq1 in reads_dir.glob(f"**/*{r1_suffix}"):
            sample = fq1.name[:-len(r1_suffix)]
            fq2 = fq1.parent / f"{sample}{r2_suffix}"
            if fq2.exists():
                samples[sample] = (fq1, fq2)

    return samples
