"""
MitoZ Python Runner - 执行批量注释不依赖 Snakemake

设计参考: my_shh/get_batch.py
关键特性:
  - GenBank 文件提取
  - 基因重定向
  - Popen 流式读取
  - Checkpoint 检测
"""

import subprocess
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed


# 完成判据关键词
_SUCCESS_KEYWORDS = (
    "Annotation completed",
    "All done",
    "succeeded",
    "Finished",
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
      1. summary.txt 存在
      2. *.gb 文件存在
      3. 日志含成功关键词
    """
    if not output_dir.exists():
        return False

    # 判据 1: summary.txt
    summary = output_dir / "summary.txt"
    if summary.exists() and summary.stat().st_size > 0:
        return True

    # 判据 2: GenBank 文件
    for gb in output_dir.glob("*.gb"):
        if gb.stat().st_size > 0:
            return True

    # 判据 3: 日志
    log_file = output_dir / "mitoz.log"
    if log_file.exists() and _log_has_success(log_file):
        return True

    return False


def get_result_files(output_dir: Path) -> Dict[str, Path]:
    """
    获取结果文件。

    Returns:
        {"gb": genbank_path, "fasta": fasta_path, "summary": summary_path}
    """
    results = {}

    # GenBank 文件
    for gb in output_dir.glob("*.gb"):
        if gb.stat().st_size > 0:
            results["gb"] = gb
            break

    # FASTA 文件
    for fa in output_dir.glob("*.fas"):
        if fa.stat().st_size > 0:
            results["fasta"] = fa
            break

    # Summary
    summary = output_dir / "summary.txt"
    if summary.exists():
        results["summary"] = summary

    return results


class MitozRunner:
    """
    MitoZ Python 后端批量执行器

    特性：
      - 自动注释线粒体基因组
      - 基因重定向支持
      - GenBank 文件提取
    """

    # 默认 clade
    DEFAULT_CLADE = "Arthropoda"

    def __init__(self, threads: int = 20, shell_prefix: str = ""):
        self.threads = threads
        self.shell_prefix = shell_prefix

    def build_command(
        self,
        fasta: Path,
        output_dir: Path,
        clade: str = "Arthropoda",
        genetic_code: int = 5,
        **kwargs,
    ) -> List[str]:
        """
        构建 MitoZ 命令。

        Args:
            fasta: 输入 FASTA 文件
            output_dir: 输出目录
            clade: 物种 clade
            genetic_code: 遗传密码表

        Returns:
            命令参数列表
        """
        cmd = [
            "MitoZ",
            "all",
            "--fasta", str(fasta),
            "--out_dir", str(output_dir),
            "--clade", clade,
            "--genetic_code", str(genetic_code),
            "--thread_number", str(kwargs.get("threads", self.threads)),
        ]

        # 可选参数
        if kwargs.get("start_gene"):
            cmd.extend(["--start_gene", kwargs["start_gene"]])

        return cmd

    def run_single(
        self,
        sample: str,
        fasta: Path,
        output_dir: Path,
        clade: str = "Arthropoda",
        genetic_code: int = 5,
        force: bool = False,
        **kwargs,
    ) -> Dict:
        """
        执行单个样本注释。

        Args:
            sample: 样本名
            fasta: 输入 FASTA 文件
            output_dir: 输出目录
            clade: 物种 clade
            genetic_code: 遗传密码表
            force: 强制重跑

        Returns:
            执行结果
        """
        output_dir = Path(output_dir)

        # Checkpoint 检测
        if not force and is_sample_done(output_dir):
            logging.info(f"[SKIP] {sample} 已完成，跳过")
            results = get_result_files(output_dir)
            return {
                "sample": sample,
                "status": "SKIP",
                "success": True,
                "results": {k: str(v) for k, v in results.items()},
            }

        logging.info(f"[RUN] {sample} 开始注释")

        # 构建命令
        cmd = self.build_command(
            fasta=fasta,
            output_dir=output_dir,
            clade=clade,
            genetic_code=genetic_code,
            **kwargs,
        )
        logging.info(f"[CMD] {' '.join(cmd)}")

        result = {
            "sample": sample,
            "success": False,
            "input_file": str(fasta),
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
                )
            else:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )

            log_file = output_dir / "mitoz.log"
            output_dir.mkdir(parents=True, exist_ok=True)

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
            if is_sample_done(output_dir):
                logging.info(f"[OK] {sample} 注释完成")
                result["success"] = True
                result["status"] = "OK"
                results = get_result_files(output_dir)
                result["results"] = {k: str(v) for k, v in results.items()}
            else:
                logging.warning(f"[INCOMPLETE] {sample} 无结果文件")
                result["status"] = "INCOMPLETE"

        except Exception as e:
            logging.error(f"[ERROR] {sample}: {e}")
            result["error"] = str(e)
            result["status"] = "ERROR"

        return result

    def run_batch(
        self,
        samples: Dict[str, Path],
        output_root: Path,
        parallel_jobs: int = 1,
        clade: str = "Arthropoda",
        **kwargs,
    ) -> List[Dict]:
        """
        批量执行注释。

        Args:
            samples: {sample_name: fasta_path}
            output_root: 输出根目录
            parallel_jobs: 并行任务数
            clade: 物种 clade

        Returns:
            结果列表
        """
        results = []

        with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
            futures = {}
            for sample, fasta in samples.items():
                sample_dir = output_root / sample
                future = executor.submit(
                    self.run_single,
                    sample,
                    fasta,
                    sample_dir,
                    clade=clade,
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

    def extract_genes(
        self,
        gbk_file: Path,
        output_dir: Path,
        **kwargs,
    ) -> Dict:
        """
        从 GenBank 文件提取基因序列。

        Args:
            gbk_file: GenBank 文件路径
            output_dir: 输出目录

        Returns:
            提取结果
        """
        try:
            from Bio import SeqIO
        except ImportError:
            return {
                "success": False,
                "error": "Biopython not installed",
            }

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        genes = {}
        try:
            for record in SeqIO.parse(gbk_file, "genbank"):
                for feature in record.features:
                    if feature.type == "gene":
                        gene_name = feature.qualifiers.get("gene", ["unknown"])[0]
                        gene_seq = feature.extract(record.seq)
                        genes[gene_name] = str(gene_seq)

            # 写入基因文件
            genes_fasta = output_dir / "genes.fasta"
            with open(genes_fasta, "w") as f:
                for name, seq in genes.items():
                    f.write(f">{name}\n{seq}\n")

            return {
                "success": True,
                "output_file": str(genes_fasta),
                "genes": list(genes.keys()),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def reorient(
        self,
        gbk_file: Path,
        output_file: Path,
        start_gene: str = "cox1",
        **kwargs,
    ) -> Dict:
        """
        重定向 GenBank 文件（以指定基因起始）。

        Args:
            gbk_file: GenBank 文件路径
            output_file: 输出文件路径
            start_gene: 起始基因名

        Returns:
            重定向结果
        """
        try:
            from Bio import SeqIO
        except ImportError:
            return {
                "success": False,
                "error": "Biopython not installed",
            }

        try:
            records = list(SeqIO.parse(gbk_file, "genbank"))
            if not records:
                return {"success": False, "error": "No records in GenBank file"}

            record = records[0]

            # 找到起始基因位置
            start_pos = None
            for feature in record.features:
                if feature.type == "gene":
                    gene_name = feature.qualifiers.get("gene", [""])[0]
                    if gene_name.lower() == start_gene.lower():
                        start_pos = feature.location.start
                        break

            if start_pos is None:
                return {
                    "success": False,
                    "error": f"Gene '{start_gene}' not found",
                }

            # 重定向序列
            new_seq = record.seq[start_pos:] + record.seq[:start_pos]

            # 创建新记录
            new_record = record[:]
            new_record.seq = new_seq

            # 写入输出
            SeqIO.write(new_record, output_file, "genbank")

            return {
                "success": True,
                "output_file": str(output_file),
                "start_gene": start_gene,
                "start_position": int(start_pos),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}


def parse_fasta_dir(
    fasta_dir: Path,
    pattern: str = "*.fasta",
) -> Dict[str, Path]:
    """
    解析 FASTA 目录。

    Args:
        fasta_dir: FASTA 文件目录
        pattern: 文件匹配模式

    Returns:
        {sample_name: fasta_path}
    """
    samples = {}
    fasta_dir = Path(fasta_dir).resolve()

    for fasta in fasta_dir.glob(pattern):
        # 从文件名提取样本名
        sample = fasta.stem.split(".")[0]
        samples[sample] = fasta

    return samples