# NOVOPlasty 调研记录

调研日期：2026-04-23

## 版本与来源

- 官方代码：<https://github.com/ndierckx/NOVOPlasty>
- 论文：Dierckxsens, Mardulyn, Smits. 2016. Nucleic Acids Research. DOI: `10.1093/nar/gkw955`
- Bioconda：<https://anaconda.org/bioconda/novoplasty>
- 官方 GitHub 当前可见最新 release：`NOVOPlasty4.3.5`，2024-02-04
- Bioconda 当前可见最新版本：`4.3.5`
- FastMitoAssembler 当前环境约束：`FastMitoAssembler/smk/envs/novoplasty.yaml` 中写的是 `novoplasty`，未锁定精确版本

建议：FastMitoAssembler 后续应锁定 `novoplasty=4.3.5`，同时继续支持用户通过 `script_path` 指定 `NOVOPlasty4.3.5.pl` 或其他本地版本。

## 软件定位

NOVOPlasty 是短环状基因组 de novo assembler，也支持 heteroplasmy/variance calling。它依赖配置文件运行，核心集成点不是命令行参数，而是为每个样本生成稳定、可追踪的 `config.txt`。

官方说明强调：输入 reads 可以是未压缩或 gz/bz2 压缩的 Illumina FASTQ/FASTA；只支持单个 paired-end library，不支持 multiple libraries；不建议质量过滤或质量剪切，只建议去接头。

## 配置文件关键字段

当前 FastMitoAssembler 的 `NOVOPLASTY_CONFIG_TPL` 已覆盖主要字段：

- `Project name`：样本名，影响输出文件命名
- `Type`：当前写死为 `mito`
- `Genome Range`：如 `12000-22000`
- `K-mer`：默认应以 `33` 为基线；低覆盖或 seed 错误时可降到 `21-39`
- `Max memory`：GB 数值，不带单位，可触发自动降采样
- `Seed Input`：seed FASTA 路径
- `Extend seed directly`：仅当 seed 来自同一样本且没有 mismatch 风险时才建议启用
- `Forward reads` / `Reverse reads`：R1/R2 FASTQ
- `Insert size auto`：默认 `yes`
- `Use Quality Scores`：默认 `no`
- `Output path`：批量运行必须显式设置，避免结果混在当前目录

## seed 输入模式

FastMitoAssembler 需要支持三类：

1. 单一 seed：所有样本共用同一个 seed FASTA/GenBank。当前实现已可通过 `seed_input` 间接支持，但会只取第一条序列。
2. MEANGS seed：每个样本使用 `result/{sample}/1.MEANGS/{sample}_deep_detected_mito.fas`。
3. multi-FASTA by-sample seed：输入一个多序列 FASTA，header 的第一个 token 作为 sample 名，与 FASTQ sample 基础名匹配。

建议新增 `seed_mode`：

- `single`：默认，兼容现有行为；如果输入 multi-FASTA，默认取第一条并给出提示。
- `by-sample`：严格按 sample 匹配，缺失即报错，不自动降级。

## 典型命令

NOVOPlasty 官方运行方式：

```bash
NOVOPlasty.pl -c config.txt
```

FastMitoAssembler 批量调用建议：

```bash
fma novoplasty --reads_dir reads --seed_input seed.fa \
  --novoplasty_genome_min_size 12000 \
  --novoplasty_genome_max_size 22000 \
  --novoplasty_kmer_size 33 \
  --cores 8
```

MEANGS → NOVOPlasty：

```bash
fma mg-nov --reads_dir reads --meangs_reads 2000000 \
  --novoplasty_kmer_size 33 --cores 8
```

## 关键输出

NOVOPlasty 输出以 `Project name` 为前缀。当前 FastMitoAssembler 的 Snakemake 规则运行后会用：

```bash
seqkit replace -p "\+.+" -r "" -o {sample}.novoplasty.fasta *{sample}.fasta
```

这说明当前集成会把 NOVOPlasty header 中 `+...` 后缀去掉，并将标准化结果写到：

```text
result/{sample}/2.NOVOPlasty/{sample}.novoplasty.fasta
```

后续 summary 不应只依赖文件名判断成环，应解析 header 中的 circle/topology 信息；如果无法解析，标记 `topology=unknown`。

## FastMitoAssembler 集成建议

- `fma novoplasty` 需要可以单独运行；如果没有上游 MEANGS 结果，则必须要求 `--seed_input`。
- `fma mg-nov` 先跑 MEANGS，再为每个样本生成 NOVOPlasty `config.txt` 并运行。
- NOVOPlasty 配置文件应作为可复核产物保留，不应默认清理。
- 批量 by-sample seed 应将提取后的单样本 seed 写入样本目录，例如 `result/{sample}/2.NOVOPlasty/{sample}.seed.fasta`，再写入 config。
- 对污染数据，NOVOPlasty 输出需要进入 summary 和后续 MitoZ 前做长度范围、拓扑和来源记录，避免把污染 contig 当作最终结果。

## 风险与待核查

- 官方 README 中 `Type` 支持 `chloro/mito/mito_plant`，当前 FastMitoAssembler 写死 `mito`；如后续要支持植物线粒体，应确认是否需要暴露 `--novoplasty_type`。
- NOVOPlasty 最新 release 为 `4.3.5`，但 README 更新日志中仍有 `4.3.3` 字样；版本判断应以 release/conda 和实际脚本名为准。
- 输出 header 格式可能随版本变化，summary 的 topology 解析应宽松且保留 `unknown`。
