# GetOrganelle software research report

调研时间：2026-04-23 17:21:51 CST +0800
调研目标：为 FastMitoAssembler v002 的 GetOrganelle 独立批量运行、MEANGS -> GetOrganelle、MEANGS -> NOVOPlasty -> GetOrganelle，以及 nr 组装支持提供实现依据。

## 1. 软件定位

GetOrganelle 是 genome skimming 数据的细胞器和 nr 组装工具包。它通过 reads 招募、迭代延伸、SPAdes 组装、assembly graph slimming/disentangling 输出 organelle/nr 候选序列和 graph。它应是 FastMitoAssembler 中细胞器/nr 组装和 graph 复核的核心后端。

## 2. 版本与官方来源

- 官方源码：<https://github.com/Kinggerm/GetOrganelle>
- 官方 Wiki：<https://github.com/Kinggerm/GetOrganelle/wiki>
- 主要脚本：`get_organelle_from_reads.py`、`get_organelle_from_assembly.py`、`get_organelle_config.py`
- 官方 latest release：`GetOrganelle v1.7.7.1`
- FastMitoAssembler 当前 env：`FastMitoAssembler/FastMitoAssembler/smk/envs/getorganelle.yaml` 锁定 `getorganelle=1.7.7.0`

版本判断：官方最新是 `1.7.7.1`，项目当前环境仍为 `1.7.7.0`。报告和实现应同时记录“官方最新版本”和“项目锁定版本”。

## 3. 本地 help 检查

Codex 当前环境检查：

```bash
command -v get_organelle_from_reads.py
command -v get_organelle_from_assembly.py
```

结果：Codex 环境未发现 GetOrganelle 命令。

用户本地环境实测记录：

- 记录时间：2026-04-23 20:06:17 CST +0800
- 环境提示符：`(getorganelle)`
- 执行命令：`get_organelle_from_reads.py -h`
- help 显示版本：`GetOrganelle v1.7.7.1`
- help 明确 `-h` 是常用参数简略帮助，`--help` 是完整参数帮助。
- 已确认常用参数：`-1`、`-2`、`-u`、`-o`、`-s`、`-w`、`-R`、`-F`、`--max-reads`、`--fast`、`-k`、`-t`、`-P`、`-v/--version`、`-h`、`--help`。
- `-F` 支持目标：`embplant_pt`、`other_pt`、`embplant_mt`、`embplant_nr`、`animal_mt`、`fungus_mt`、`fungus_nr`、`anonym`，以及组合类型如 `embplant_pt,embplant_mt`。
- `--max-reads` help 确认默认值随 `-F` 变化：`embplant_pt/embplant_nr/fungus_mt/fungus_nr` 为 `1.5E7`，`embplant_mt/other_pt/anonym` 为 `7.5E7`，`animal_mt` 为 `3E8`。
- help 示例确认：
  - plant plastome：`-s cp_seed.fasta -R 15 -k 21,45,65,85,105 -F embplant_pt`
  - plant mitogenome：`-s mt_seed.fasta -R 30 -k 21,45,65,85,105 -F embplant_mt`

正式部署后仍建议补充记录：

```bash
get_organelle_from_reads.py --help
get_organelle_from_reads.py --version
```

## 4. 安装方式

Bioconda：

```bash
conda install -c bioconda getorganelle
```

数据库配置：

```bash
get_organelle_config.py --add embplant_pt,embplant_mt
```

数据库默认位置为 `~/.GetOrganelle`，可用 `--config-dir` 或环境变量 `GETORG_PATH` 指定。

## 5. 核心命令

animal mitogenome：

```bash
get_organelle_from_reads.py -1 sample_R1.fq.gz -2 sample_R2.fq.gz -o animal_mt_out -F animal_mt -R 10 -t 4
```

plant plastome：

```bash
get_organelle_from_reads.py -1 sample_R1.fq -2 sample_R2.fq -s cp_seed.fasta -o plastome_out -R 15 -k 21,45,65,85,105 -F embplant_pt
```

plant nr：

```bash
get_organelle_from_reads.py -1 sample_R1.fq -2 sample_R2.fq -o nr_out -R 10 -k 35,85,115 -F embplant_nr
```

from assembly graph：

```bash
get_organelle_from_assembly.py -g assembly_graph.fastg -o out_dir -F embplant_pt
```

## 6. 主要参数

输入输出：

- `-1`：forward paired-end reads。
- `-2`：reverse paired-end reads。
- `-u`：unpaired/single-end reads。
- `-o`：输出目录。
- `-s`：seed FASTA；GetOrganelle 的 seed 只用于识别 initial organelle reads，组装过程仍是 de novo。
- `-a`：anti-seed。
- `--config-dir`：数据库目录。
- `--prefix`：输出文件前缀。
- `--keep-temp`：保留中间文件。

目标和流程：

- `-F`：目标类型。
- `-R, --max-rounds`：最大延伸轮数。
- `-k`：SPAdes k-mer。
- `-t`：线程数。
- `--fast`：快速策略。
- `--memory-save`：节省内存策略。
- `--memory-unlimited`：高内存策略。

reads 使用量：

- `--max-reads`：每个文件使用 reads 上限。源码说明默认值随 `-F` 变化：`embplant_pt/embplant_nr/fungus_mt/fungus_nr` 为 `1.5E7`，`embplant_mt/other_pt/anonym` 为 `7.5E7`，`animal_mt` 为 `3E8`。
- `--reduce-reads-for-coverage`：按目标 coverage 软降采样，默认 `500`；设为 `inf` 可禁用。

自定义数据库：

- `--genes`：自定义 label database/genes FASTA。
- `--genomes` 或相关数据库配置：用于自定义参考场景。

## 7. `-F` 支持目标

源码支持：

- `embplant_pt`：embryophyta plant plastome。
- `other_pt`：non-embryophyta plastome。
- `embplant_mt`：plant mitogenome。
- `embplant_nr`：plant nuclear ribosomal RNA。
- `animal_mt`：animal mitogenome。
- `fungus_mt`：fungus mitogenome。
- `fungus_nr`：fungus nuclear ribosomal RNA。
- `anonym`：未知/自定义 organelle 类型，通常需要自定义 `-s` 和 `--genes`。

旧别名会自动重定向，例如 `plant_cp -> embplant_pt`，`plant_mt -> embplant_mt`，`plant_nr -> embplant_nr`。

## 8. 输入格式

- Reads：FASTQ、FASTQ.GZ、FASTQ.TAR.GZ，PE 或 SE。
- Seed：FASTA，可多个文件按 `-F` 对应。
- Assembly：`get_organelle_from_assembly.py` 支持 FASTG/GFA 类 assembly graph。
- 自定义 label database：GetOrganelle 兼容 FASTA/label database。

## 9. 输出文件结构

典型输出：

```text
out_dir/
├── get_org.log.txt
├── seed/
├── extended_1.fq / extended_2.fq
├── extended_K*.assembly_graph.fastg
├── extended_K*.assembly_graph.fastg.extend_*.fastg
├── extended_K*.assembly_graph.fastg.extend_*.csv
├── {type}.selected_graph.gfa
├── {type}.path_sequence.fasta
├── {type}.path_sequence.gfa
└── {type}*scaffolds*path_sequence.fasta
```

关键输出：

- `*.path_sequence.fasta`：summary 优先收集对象。
- `*.selected_graph.gfa`：保留供 graph 复核。
- `get_org.log.txt`：必须保留。
- `*scaffolds*path_sequence.fasta`：通常表示未完整 circular，但仍可进入候选 summary，并标记 incomplete/unknown。

## 10. FastMitoAssembler 集成策略

- `fma getorganelle`：独立批量运行，无 seed 时使用 GetOrganelle 默认数据库。
- `fma mg-get`：MEANGS 输出作为 `-s` seed，跳过 NOVOPlasty。
- `fma mg-nov-get`：NOVOPlasty 输出作为 `-s` seed 或候选输入。
- nr 支持通过 `-F embplant_nr`、`-F fungus_nr` 或 `-F anonym` + `-s`/`--genes` 实现。
- FastMitoAssembler config 中空值不应强行传参，应该让 GetOrganelle 根据 `-F` 使用默认值。
- summary 优先收集 `*.path_sequence.fasta`，同时在 TSV 记录 graph/log 路径和 topology。

## 11. 风险与待验证

- 项目 env `1.7.7.0` 与官方最新 `1.7.7.1` 需要明确是否升级。
- plant mitogenome 可能多构型，不应只看 FASTA；graph 必须保留。
- `--genes` 需要确认 Snakemake rule 已正确透传。
- `animal_mt` 默认 `--max-reads 3E8` 可能消耗较大，FastMitoAssembler 应让用户明确配置。

## 记录

- 调研日期：2026-04-23 Asia/Shanghai
- 调研时间：2026-04-23 17:21:51 CST +0800
- 软件版本：GetOrganelle 1.7.7.1；FastMitoAssembler 当前 env 为 1.7.7.0
- 版本依据：GitHub release latest 和 `get_organelle_from_reads.py` help 源码
- 源码出处：<https://github.com/Kinggerm/GetOrganelle>
- 官方 Wiki：<https://github.com/Kinggerm/GetOrganelle/wiki>
- 本地 help：用户已提供 `get_organelle_from_reads.py -h` 实测输出，记录时间 2026-04-23 20:06:17 CST +0800；Codex 当前环境未安装 GetOrganelle 命令
