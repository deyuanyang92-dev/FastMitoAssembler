"""
BLAST Runner - Python 后端 BLAST 执行

功能:
  - 在线 BLAST (Biopython qblast)
  - 本地 BLAST (blastn 命令)
  - 批量 BLAST 执行
  - 元数据获取 (NCBI E-utilities)

设计参考:
  - my_shh/blast2meta.py
"""

import logging
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class BlastRunner:
    """
    BLAST 执行器

    支持在线和本地 BLAST。
    """

    def __init__(
        self,
        mode: str = "remote",
        db: str = "nt",
        evalue: float = 1e-5,
        max_target_seqs: int = 10,
        threads: int = 4,
    ):
        """
        Args:
            mode: BLAST 模式 (remote/local)
            db: 数据库名称
            evalue: E-value 阈值
            max_target_seqs: 最大目标序列数
            threads: 线程数 (本地模式)
        """
        self.mode = mode
        self.db = db
        self.evalue = evalue
        self.max_target_seqs = max_target_seqs
        self.threads = threads

    def run_blast(
        self,
        query_fasta: Path,
        output_tsv: Path,
        **kwargs,
    ) -> Dict:
        """
        执行 BLAST 查询。

        Args:
            query_fasta: 查询 FASTA 文件
            output_tsv: 输出 TSV 文件

        Returns:
            执行结果
        """
        if self.mode == "remote":
            return self._run_remote_blast(query_fasta, output_tsv, **kwargs)
        else:
            return self._run_local_blast(query_fasta, output_tsv, **kwargs)

    def _run_remote_blast(
        self,
        query_fasta: Path,
        output_tsv: Path,
        **kwargs,
    ) -> Dict:
        """
        在线 BLAST (Biopython qblast)
        """
        try:
            from Bio.Blast import NCBIWWW, NCBIXML
        except ImportError:
            return {
                "success": False,
                "error": "Biopython not installed. Run: pip install biopython",
            }

        records = self._read_fasta_records(query_fasta)
        if not records:
            return {"success": False, "error": "No sequences in query FASTA"}

        db = kwargs.get("db", self.db)
        evalue = kwargs.get("evalue", self.evalue)
        max_target_seqs = kwargs.get("max_target_seqs", self.max_target_seqs)

        output_tsv = Path(output_tsv)
        output_tsv.parent.mkdir(parents=True, exist_ok=True)

        total_hits = 0
        with open(output_tsv, "w") as out:
            for i, (qid, qdesc, qseq) in enumerate(records):
                qlen = len(qseq)
                logging.info(f"[BLAST] Query {i+1}/{len(records)}: {qid}")

                success = False
                for attempt in range(1, 4):
                    try:
                        handle = NCBIWWW.qblast(
                            program="blastn",
                            database=db,
                            sequence=qseq,
                            expect=evalue,
                            hitlist_size=max_target_seqs,
                        )
                        blast_records = list(NCBIXML.parse(handle))
                        handle.close()

                        for br in blast_records:
                            for aln in br.alignments:
                                for hsp in aln.hsps:
                                    qcov = (hsp.query_end - hsp.query_start + 1) / max(1, qlen) * 100.0
                                    pid = (hsp.identities / max(1, hsp.align_length)) * 100.0
                                    subj_id = aln.accession or aln.hit_id
                                    title = aln.title or subj_id
                                    out.write("\t".join([
                                        qid, subj_id, title,
                                        f"{pid:.2f}", str(hsp.align_length),
                                        f"{qcov:.2f}", str(hsp.expect), str(hsp.score),
                                    ]) + "\n")
                                    total_hits += 1

                        success = True
                        break
                    except Exception as e:
                        logging.warning(f"[BLAST] Attempt {attempt} failed: {e}")
                        if attempt < 3:
                            time.sleep(5 * attempt)

                if not success:
                    logging.error(f"[BLAST] Failed after 3 attempts: {qid}")

                # NCBI 友好间隔
                time.sleep(2)

        return {
            "success": True,
            "output_file": str(output_tsv),
            "total_hits": total_hits,
        }

    def _run_local_blast(
        self,
        query_fasta: Path,
        output_tsv: Path,
        **kwargs,
    ) -> Dict:
        """
        本地 BLAST (blastn 命令)
        """
        blastn = shutil.which("blastn")
        if not blastn:
            return {
                "success": False,
                "error": "blastn not found in PATH",
            }

        db = kwargs.get("db", self.db)
        evalue = kwargs.get("evalue", self.evalue)
        max_target_seqs = kwargs.get("max_target_seqs", self.max_target_seqs)
        threads = kwargs.get("threads", self.threads)

        output_tsv = Path(output_tsv)
        output_tsv.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            blastn,
            "-query", str(query_fasta),
            "-db", db,
            "-outfmt", "6 qseqid sseqid stitle pident length qcovs evalue bitscore",
            "-out", str(output_tsv),
            "-evalue", str(evalue),
            "-max_target_seqs", str(max_target_seqs),
            "-num_threads", str(threads),
        ]

        logging.info(f"[BLAST] Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr[:500],
                    "returncode": result.returncode,
                }

            # 统计 hits
            hits = 0
            if output_tsv.exists():
                with open(output_tsv) as f:
                    hits = sum(1 for line in f if line.strip())

            return {
                "success": True,
                "output_file": str(output_tsv),
                "total_hits": hits,
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "BLAST timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_batch(
        self,
        fasta_files: List[Path],
        output_dir: Path,
        parallel_jobs: int = 1,
        **kwargs,
    ) -> List[Dict]:
        """
        批量执行 BLAST。

        Args:
            fasta_files: FASTA 文件列表
            output_dir: 输出目录
            parallel_jobs: 并行任务数 (仅本地模式有效)

        Returns:
            结果列表
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = []

        # 在线模式不支持并行 (NCBI 限制)
        if self.mode == "remote":
            for fasta in fasta_files:
                sample = fasta.stem.split(".")[0]
                output_tsv = output_dir / f"{sample}_blast.tsv"
                result = self.run_blast(fasta, output_tsv, **kwargs)
                result["sample"] = sample
                result["input_file"] = str(fasta)
                results.append(result)
        else:
            # 本地模式可以并行
            with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
                futures = {}
                for fasta in fasta_files:
                    sample = fasta.stem.split(".")[0]
                    output_tsv = output_dir / f"{sample}_blast.tsv"
                    future = executor.submit(
                        self.run_blast, fasta, output_tsv, **kwargs
                    )
                    futures[future] = sample

                for future in as_completed(futures):
                    sample = futures[future]
                    try:
                        result = future.result()
                        result["sample"] = sample
                        results.append(result)
                    except Exception as e:
                        results.append({
                            "sample": sample,
                            "success": False,
                            "error": str(e),
                        })

        return results

    def _read_fasta_records(self, fasta_path: Path) -> List[Tuple[str, str, str]]:
        """
        读取 FASTA 记录。

        Returns:
            [(id, description, sequence), ...]
        """
        records = []
        header_id = None
        header_desc = ""
        seq_parts = []

        with open(fasta_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith(">"):
                    if header_id is not None:
                        records.append((header_id, header_desc, "".join(seq_parts)))
                    parts = line[1:].split(None, 1)
                    header_id = parts[0]
                    header_desc = parts[1] if len(parts) > 1 else ""
                    seq_parts = []
                else:
                    seq_parts.append(line)

        if header_id is not None:
            records.append((header_id, header_desc, "".join(seq_parts)))

        return records


class MetadataFetcher:
    """
    NCBI 元数据获取器

    从 BLAST 结果获取序列元数据。
    """

    def __init__(self, email: str = "example@example.com"):
        """
        Args:
            email: NCBI 要求的 email
        """
        self.email = email

    def fetch_metadata(
        self,
        accessions: List[str],
        **kwargs,
    ) -> List[Dict]:
        """
        获取序列元数据。

        Args:
            accessions: 登录号列表

        Returns:
            元数据列表
        """
        try:
            from Bio import Entrez
        except ImportError:
            logging.error("Biopython not installed")
            return []

        Entrez.email = self.email

        results = []
        batch_size = 100

        for i in range(0, len(accessions), batch_size):
            batch = accessions[i:i + batch_size]
            try:
                handle = Entrez.efetch(
                    db="nucleotide",
                    id=",".join(batch),
                    rettype="gb",
                    retmode="text",
                )
                # 解析 GenBank 记录
                text = handle.read()
                handle.close()

                # 简单解析
                for record in self._parse_genbank_text(text):
                    results.append(record)

                # NCBI 友好间隔
                time.sleep(0.5)

            except Exception as e:
                logging.error(f"[METADATA] Failed to fetch batch: {e}")

        return results

    def _parse_genbank_text(self, text: str) -> List[Dict]:
        """
        解析 GenBank 文本。
        """
        records = []
        current = {}

        for line in text.split("\n"):
            if line.startswith("LOCUS"):
                if current:
                    records.append(current)
                current = {"accession": line.split()[1]}
            elif line.startswith("  ORGANISM"):
                current["organism"] = line.split("  ORGANISM")[1].strip()
            elif line.startswith("DEFINITION"):
                current["definition"] = line.split("DEFINITION")[1].strip()

        if current:
            records.append(current)

        return records

    def enrich_blast_results(
        self,
        blast_tsv: Path,
        output_tsv: Path,
        **kwargs,
    ) -> Dict:
        """
        为 BLAST 结果添加元数据。

        Args:
            blast_tsv: BLAST 结果 TSV
            output_tsv: 输出 TSV

        Returns:
            处理结果
        """
        # 读取 BLAST 结果
        accessions = set()
        blast_records = []

        with open(blast_tsv) as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    blast_records.append(parts)
                    accessions.add(parts[1])

        # 获取元数据
        metadata = self.fetch_metadata(list(accessions), **kwargs)
        metadata_map = {m.get("accession"): m for m in metadata}

        # 写入增强结果
        output_tsv = Path(output_tsv)
        output_tsv.parent.mkdir(parents=True, exist_ok=True)

        with open(output_tsv, "w") as out:
            # Header
            out.write("\t".join([
                "qseqid", "sseqid", "stitle", "pident", "length",
                "qcovs", "evalue", "bitscore", "organism", "definition",
            ]) + "\n")

            for parts in blast_records:
                acc = parts[1] if len(parts) > 1 else ""
                meta = metadata_map.get(acc, {})
                row = parts + [
                    meta.get("organism", ""),
                    meta.get("definition", ""),
                ]
                out.write("\t".join(row) + "\n")

        return {
            "success": True,
            "output_file": str(output_tsv),
            "total_records": len(blast_records),
            "metadata_fetched": len(metadata),
        }
