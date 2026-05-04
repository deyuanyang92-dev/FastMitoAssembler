"""
GetOrganelle Python Runner - 执行批量组装不依赖 Snakemake

设计参考: my_shh/get_batch.py (v6 优化版)
关键特性:
  - Popen 流式读取（避免缓冲区满导致子进程挂起）
  - Checkpoint 检测（自动续跑未完成任务）
  - --extra_args passthrough（支持任意额外参数）
  - ThreadPoolExecutor 并行执行
"""

import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed


# 完成判据关键词
_SUCCESS_KEYWORDS = (
    "Finished getting organelle",
    "Result status",
    "Writing output finished",
    "Total cost",
    "succeeded",
    "Organelle assembly finished",
)


def _log_has_success(log_file: Path) -> bool:
    """检查日志是否含成功关键词"""
    try:
        text = log_file.read_text(encoding="utf-8", errors="ignore")
        return any(kw in text for kw in _SUCCESS_KEYWORDS)
    except Exception:
        return False


def is_sample_done(run_out: Path) -> bool:
    """
    判断样本是否已成功完成。

    完成判据（按可靠性排序）：
      1. *.path_sequence.fasta 存在且非空（最可靠）
      2. *.fastg 存在且非空 + 日志含成功关键词（graph-only）
      3. 仅日志含成功关键词（兜底）
    """
    if not run_out.exists():
        return False

    # 判据 1: path_sequence.fasta
    for fa in run_out.glob("*.path_sequence.fasta"):
        if fa.stat().st_size > 0:
            return True

    log_file = run_out / "get_org.log.txt"

    # 判据 2: fastg + 日志
    for fg in run_out.glob("*.fastg"):
        if fg.stat().st_size > 0 and log_file.exists() and _log_has_success(log_file):
            return True

    # 判据 3: 仅日志
    if log_file.exists() and _log_has_success(log_file):
        return True

    return False


def is_sample_incomplete(run_out: Path) -> bool:
    """
    判断样本是否处于"已开始但未完成"状态（应使用 --continue 续跑）。
    """
    if not run_out.exists():
        return False
    return not is_sample_done(run_out)


def list_result_fastas(run_out: Path) -> List[Path]:
    """列出结果 fasta 文件"""
    return list(run_out.glob("*.path_sequence.fasta"))


class GetOrganelleRunner:
    """Python 后端批量执行 GetOrganelle

    支持模式:
      - mt: 线粒体基因组组装 (默认)
      - nr: NR/rRNA 基因组装 (使用 -F anonym)
    """

    # 预定义数据库模式
    DATABASE_MODES = {
        "mt": "animal_mt",       # 动物线粒体
        "cp": "plant_cp",        # 植物叶绿体
        "nr": "anonym",          # NR/rRNA 匿名模式
    }

    def __init__(self, threads: int = 16, shell_prefix: str = ""):
        self.threads = threads
        self.shell_prefix = shell_prefix

    def build_command(
        self,
        fq1: Path,
        fq2: Path,
        output_dir: Path,
        database: str = "animal_mt",
        mode: str = "mt",
        resume: bool = False,
        **kwargs,
    ) -> List[str]:
        """构建 GetOrganelle 命令

        Args:
            fq1: R1 文件路径
            fq2: R2 文件路径
            output_dir: 输出目录
            database: 数据库名称 (animal_mt, plant_cp, anonym)
            mode: 运行模式 (mt, cp, nr)
            resume: 是否续跑
            **kwargs: 其他参数
        """
        # 如果指定了 mode，自动选择数据库
        if mode in self.DATABASE_MODES and database == "animal_mt":
            database = self.DATABASE_MODES[mode]

        cmd = [
            "get_organelle_from_reads.py",
            "-1", str(fq1),
            "-2", str(fq2),
            "-o", str(output_dir),
            "-F", database,
            "-t", str(kwargs.get("threads", self.threads)),
        ]

        # NR 模式特殊参数
        if mode == "nr" or database == "anonym":
            # NR 模式需要 seed 和目标基因
            if kwargs.get("seed"):
                cmd.extend(["-s", str(kwargs["seed"])])
            if kwargs.get("target_genes"):
                cmd.extend(["--genes", str(kwargs["target_genes"])])
            elif kwargs.get("genes"):
                cmd.extend(["--genes", str(kwargs["genes"])])

            # NR 模式推荐参数
            if not kwargs.get("max_reads"):
                cmd.extend(["--max-reads", "inf"])
            if not kwargs.get("reduce_reads_for_coverage"):
                cmd.extend(["--reduce-reads-for-coverage", "inf"])
        else:
            # MT/CP 模式参数
            if kwargs.get("seed"):
                cmd.extend(["-s", str(kwargs["seed"])])
            if kwargs.get("genes"):
                cmd.extend(["--genes", str(kwargs["genes"])])

        # 基本参数
        if kwargs.get("rounds"):
            cmd.extend(["-R", str(kwargs["rounds"])])
        if kwargs.get("kmers"):
            cmd.extend(["-k", str(kwargs["kmers"])])
        if kwargs.get("word_size"):
            cmd.extend(["-w", str(kwargs["word_size"])])

        # 续跑
        if resume:
            cmd.append("--continue")

        # 强制重跑（覆盖已存在的目录）
        if kwargs.get("overwrite"):
            cmd.append("--overwrite")

        # --all-data 参数
        if kwargs.get("all_data"):
            if not kwargs.get("max_reads"):
                cmd.extend(["--max-reads", "inf"])
            if not kwargs.get("reduce_reads_for_coverage"):
                cmd.extend(["--reduce-reads-for-coverage", "inf"])

        # 其他可选参数
        if kwargs.get("max_reads"):
            cmd.extend(["--max-reads", str(kwargs["max_reads"])])
        if kwargs.get("reduce_reads_for_coverage"):
            cmd.extend(["--reduce-reads-for-coverage", str(kwargs["reduce_reads_for_coverage"])])
        if kwargs.get("max_extending_len"):
            cmd.extend(["--max-extending-len", str(kwargs["max_extending_len"])])
        if kwargs.get("expected_max_size"):
            cmd.extend(["--expected-max-size", str(kwargs["expected_max_size"])])
        if kwargs.get("expected_min_size"):
            cmd.extend(["--expected-min-size", str(kwargs["expected_min_size"])])
        if kwargs.get("memory_save"):
            cmd.append("--memory-save")

        # Passthrough extra args
        extra = kwargs.get("extra_args")
        if extra:
            cmd.extend(extra.split() if isinstance(extra, str) else extra)

        return cmd

    def run_single(
        self,
        sample: str,
        fq1: Path,
        fq2: Path,
        output_dir: Path,
        force: bool = False,
        **kwargs,
    ) -> Dict:
        """
        执行单个样本组装。

        关键特性：
        - Popen 流式读取（避免缓冲区满导致子进程挂起）
        - Checkpoint 检测（自动续跑未完成任务）
        """
        # 从 kwargs 中提取参数（避免重复传递）
        force = kwargs.pop("force", force)

        # Checkpoint 检测（在 mkdir 之前）
        if not force and is_sample_done(output_dir):
            logging.info(f"[SKIP] {sample} 已完成，跳过")
            return {"sample": sample, "status": "SKIP", "success": True}

        # 从 kwargs 中提取 resume 参数（避免重复传递）
        resume_enabled = kwargs.pop("resume", True)
        resume = resume_enabled and is_sample_incomplete(output_dir)
        if resume:
            logging.info(f"[RESUME] {sample} 检测到未完成运行，追加 --continue")
        else:
            logging.info(f"[RUN] {sample} 全新任务")

        # 构建命令
        cmd = self.build_command(fq1, fq2, output_dir, resume=resume, **kwargs)
        logging.info(f"[CMD] {' '.join(cmd)}")

        result = {
            "sample": sample,
            "command": " ".join(cmd),
            "success": False,
            "output_file": None,
        }

        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)

        # 获取 shell_prefix
        shell_prefix = kwargs.pop("shell_prefix", self.shell_prefix)

        try:
            # 构建完整命令（包含 shell_prefix）
            if shell_prefix:
                full_cmd = f"{shell_prefix}{' '.join(cmd)}"
                proc = subprocess.Popen(
                    full_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            else:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )

            for line in proc.stdout:
                logging.info(f"  {line.rstrip()}")
            proc.stdout.close()
            returncode = proc.wait()

            result["returncode"] = returncode

            if returncode != 0:
                logging.error(f"[FAILED] {sample} (rc={returncode})")
                result["status"] = "FAILED"
                return result

            # 以文件为准检查完成状态
            if is_sample_done(output_dir):
                logging.info(f"[OK] {sample} 完成")
                result["success"] = True
                result["status"] = "OK"

                # 查找输出文件
                for fa in output_dir.glob("*.path_sequence.fasta"):
                    if fa.stat().st_size > 0:
                        result["output_file"] = str(fa)
                        break
            else:
                # rc=0 但没有结果文件：incomplete graph
                logging.warning(
                    f"[INCOMPLETE] {sample} rc=0 但未找到 *.path_sequence.fasta"
                )
                result["status"] = "INCOMPLETE"

        except Exception as e:
            logging.error(f"[ERROR] {sample}: {e}")
            result["error"] = str(e)
            result["status"] = "ERROR"

        return result

    def run_batch(
        self,
        samples: Dict[str, Tuple[Path, Path]],
        output_root: Path,
        parallel_jobs: int = 3,
        **kwargs,
    ) -> List[Dict]:
        """
        批量执行组装。

        Args:
            samples: {sample_name: (fq1_path, fq2_path)}
            output_root: 输出根目录
            parallel_jobs: 并行任务数
        """
        results = []

        with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
            futures = {}
            for sample, (fq1, fq2) in samples.items():
                sample_dir = output_root / sample
                future = executor.submit(
                    self.run_single,
                    sample,
                    fq1,
                    fq2,
                    sample_dir,
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
                    results.append({"sample": sample, "status": "ERROR", "error": str(e)})

        return results


def parse_reads_dir(
    reads_dir: Path,
    r1_suffix: str = "_1.fastq.gz",
    r2_suffix: str = "_2.fastq.gz",
    fastq_pos: str = "recursive"
) -> Dict[str, Tuple[Path, Path]]:
    """
    解析 reads 目录，返回样本名和 reads 路径映射。

    Args:
        reads_dir: reads 文件目录
        r1_suffix: R1 文件后缀
        r2_suffix: R2 文件后缀
        fastq_pos: 目录结构模式 (flat/subdir/recursive)

    Returns:
        {sample_name: (fq1_path, fq2_path)}
    """
    samples = {}
    reads_dir = Path(reads_dir).resolve()

    if fastq_pos == "flat":
        # 文件直接在 reads_dir 下
        for fq1 in reads_dir.glob(f"*{r1_suffix}"):
            sample = fq1.name[:-len(r1_suffix)]
            fq2 = reads_dir / f"{sample}{r2_suffix}"
            if fq2.exists():
                samples[sample] = (fq1, fq2)
            else:
                logging.warning(f"[WARN] {sample} 缺少 R2 文件，跳过")
    elif fastq_pos == "subdir":
        # 每个样本一个子目录
        for subdir in sorted(reads_dir.iterdir()):
            if subdir.is_dir():
                for fq1 in subdir.glob(f"*{r1_suffix}"):
                    sample = subdir.name  # 使用目录名作为样本名
                    fq2 = subdir / f"{fq1.name[:-len(r1_suffix)]}{r2_suffix}"
                    if fq2.exists():
                        samples[sample] = (fq1, fq2)
                    else:
                        logging.warning(f"[WARN] {sample} 缺少 R2 文件，跳过")
    else:
        # recursive: 递归搜索
        for fq1 in reads_dir.glob(f"**/*{r1_suffix}"):
            sample = fq1.name[:-len(r1_suffix)]
            fq2 = fq1.parent / f"{sample}{r2_suffix}"
            if fq2.exists():
                samples[sample] = (fq1, fq2)
            else:
                logging.warning(f"[WARN] {sample} 缺少 R2 文件，跳过")
    return samples