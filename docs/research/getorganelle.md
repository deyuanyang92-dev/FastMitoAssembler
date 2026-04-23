# GetOrganelle 调研记录

调研日期：2026-04-23

## 版本与来源

- 官方代码：<https://github.com/Kinggerm/GetOrganelle>
- 官方 Wiki：<https://github.com/Kinggerm/GetOrganelle/wiki>
- 论文：Jin et al. 2020. Genome Biology. DOI: `10.1186/s13059-020-02154-5`
- Bioconda：<https://anaconda.org/bioconda/getorganelle>
- 官方 GitHub 当前可见最新 release：`v1.7.7.1`，2024-04-03
- Bioconda 当前可见最新版本：`1.7.7.1`
- FastMitoAssembler 当前环境约束：`getorganelle=1.7.7.0`

建议：短期保持项目当前 `1.7.7.0` 以避免行为漂移；调研文档记录最新 `1.7.7.1`。后续升级应单独测试 `summary`、`path_sequence` 命名和参数默认值。

## 软件定位

GetOrganelle 是 genome skimming 数据的细胞器组装工具，核心脚本包括：

- `get_organelle_from_reads.py`：从 FASTQ reads 组装
- `get_organelle_from_assembly.py`：从 FASTG/GFA assembly graph 提取目标
- `get_organelle_config.py`：初始化数据库
- `summary_get_organelle_output.py`：官方 utility

官方建议使用去接头但不做质量过滤的原始 reads。`get_organelle_from_reads.py` 支持 Illumina paired-end 和 single-end FASTQ；FastMitoAssembler 当前以 paired-end 为主。

## 目标类型与数据库

`-F` 支持的常用类型：

- `embplant_pt`
- `other_pt`
- `embplant_mt`
- `embplant_nr`
- `animal_mt`
- `fungus_mt`
- `fungus_nr`
- `anonym`
- 也可用逗号组合多个类型，但计算量更高

数据库初始化：

```bash
get_organelle_config.py --add embplant_pt,embplant_mt
```

FastMitoAssembler 已有：

```bash
fma prepare organelle -a animal_mt
```

## 关键输入

- `-1`：R1 FASTQ
- `-2`：R2 FASTQ
- `-u`：single-end 或 unpaired reads
- `-o`：输出目录
- `-F`：目标类型
- `-s`：seed FASTA，用于招募初始目标 reads；不是 reference-guided assembly
- `--genes`：label database FASTA，用于 graph 过滤/识别
- `--genomes`：参考 genome database，需按官方帮助确认具体用途
- `--config-dir`：指定数据库目录；默认 `~/.GetOrganelle`，也可用 `GETORG_PATH`

## 关键参数

- `-R`：extension rounds；动物线粒体常用 `10`，植物线粒体常用更高轮次
- `-k`：SPAdes k-mer 列表；建议至少包含小 k-mer 和大 k-mer
- `-w`：word size，影响效率、内存和结果；失败时常需要调小
- `-t`：线程数
- `--max-reads`：最多使用 reads 数
- `--reduce-reads-for-coverage`：按目标覆盖度自动减少 reads，默认逻辑通常足够
- `--continue`：续跑
- `--overwrite`：覆盖已有输出
- `-P`：pre-grouping 参数，在植物线粒体等复杂场景中常见

当前 FastMitoAssembler 已实现部分 `getorganelle_*` 扁平参数透传，并支持 `getorganelle_all_data` 将 `--max-reads` 和 `--reduce-reads-for-coverage` 设为 `inf`。

## 典型命令

动物线粒体：

```bash
get_organelle_from_reads.py -1 sample_R1.fq.gz -2 sample_R2.fq.gz \
  -R 10 -k 21,45,65,85,105 -F animal_mt -o animal_mt_out
```

植物 nr：

```bash
get_organelle_from_reads.py -1 sample_R1.fq.gz -2 sample_R2.fq.gz \
  -o nr_output -R 10 -k 35,85,115 -F embplant_nr
```

真菌 nr：

```bash
get_organelle_from_reads.py -1 sample_R1.fq.gz -2 sample_R2.fq.gz \
  -R 10 -k 21,45,65,85,105 -F fungus_nr -o fungus_nr_out
```

FastMitoAssembler 批量建议：

```bash
fma getorganelle --reads_dir reads -F animal_mt \
  -R 10 -k 21,45,65,85,105 --cores 8
```

MEANGS → GetOrganelle：

```bash
fma mg-get --reads_dir reads -F animal_mt --cores 8
```

## 关键输出

官方 README/Wiki 将下列文件列为关键结果：

- `*.path_sequence.fasta`：最终路径序列，一个文件代表一种 genome structure
- `*.selected_graph.gfa`：organelle-only assembly graph
- `get_org.log.txt`：运行日志
- `extended_K*.assembly_graph.fastg`：raw assembly graph
- `*.fastg`、`*.gfa`、`.csv`：用于 Bandage 和人工复核

成环信息一般出现在 FASTA header 或文件名中；GetOrganelle 论文也说明 circular 序列会在 sequence name 中标记。FastMitoAssembler summary 应优先解析 header 中 `circular`，其次解析 `scaffold/linear`，否则 `unknown`。

## Temp_scripts 参考脚本

已克隆用户指定仓库到 `/tmp/Temp_scripts_fma_research`，commit：

```text
dc87bb3 Add blast2metadata v2.12 script
```

相关文件：

- `/tmp/Temp_scripts_fma_research/getorganelle/README.md`
- `/tmp/Temp_scripts_fma_research/getorganelle/batch_getorganelle.py`

该脚本提供了几个值得纳入 FastMitoAssembler 的规则：

- 默认只将非空 `*.path_sequence.fasta` 视为可汇总完整结果。
- rc=0 但无 `path_sequence` 时标记为 `INCOMPLETE`，不混入最终 FASTA。
- `--accept_graph_only` 只给高级用户显式接受 graph-only。
- `--iter_rounds` 时 summary 只取每个样本最高 `iter_N`。
- `--ref_gb` 可自动提取 seed 和 `--genes`。
- clean 默认只清理 `OK` 样本，`FAILED/INCOMPLETE` 保留中间文件用于排错。

## FastMitoAssembler 集成建议

- `fma getorganelle` 必须支持独立 batch；无上游 seed 时允许使用 GetOrganelle 默认数据库。
- `fma mg-get` 使用 MEANGS seed 作为 `-s`，绕过 NOVOPlasty。
- `fma mg-nov-get` 使用 NOVOPlasty 结果作为 `-s`，维持现有完整流程的前三步。
- `-F anonym` 时如果没有 `-s` 和 `--genes`，应直接报错。
- `summary` 默认只收集 `*.path_sequence.fasta`；graph-only 结果进入 report，不进入 final FASTA。
- 植物线粒体 `embplant_mt` 的 FASTA 结果在复杂重复场景下可能不可靠，应保留 FASTG/GFA 并在报告中提示人工复核。

## 风险与待核查

- FastMitoAssembler 当前锁定 `1.7.7.0`，最新是 `1.7.7.1`；升级前需跑 dry-run 和实际小样本测试。
- `--genes` 当前配置里已有字段但 Snakemake shell 未传入 GetOrganelle，需要实现。
- 当前 Snakemake 固定把 NOVOPlasty FASTA 作为 `-s`；独立 `fma getorganelle` 和 `mg-get` 需要条件输入。
