# Codex 生信 Skills 筛选与 FastMitoAssembler 优化方案

日期：2026-04-23

## 1. 检索结论

本次检索的目标不是把 FastMitoAssembler 改成一个新的大脚本，而是借鉴已有 Codex/Agent 生信 skills 中适合本项目的设计经验，用来优化现有 Python CLI + Snakemake 流程整合方案。

### 1.1 官方 OpenAI curated skills

本机已安装的 Codex skills 只有系统内置项：

- `imagegen`
- `openai-docs`
- `plugin-creator`
- `skill-creator`
- `skill-installer`

通过官方 curated skills 列表核对后，当前没有专门面向生物信息学、Snakemake 生信流程、FASTQ/FASTA 处理或细胞器组装的官方 OpenAI skill。因此官方 skills 只能用于 skill 安装/创建规范，不能直接满足 FastMitoAssembler 的生信需求。

### 1.2 GPTomics/bioSkills

检索到的最完整生信 Agent/Codex skills 来源是：

- GitHub: `https://github.com/GPTomics/bioSkills`
- 本地调研副本：`/tmp/bioSkills_fma_research`

该仓库 README 显示包含 438 个 skills，覆盖 sequence-io、read-qc、genome-assembly、workflow-management、reporting 等类别。仓库内的 `bioskills-installer/SKILL.md` 写的是 425 个 skills，和 README 数量不完全一致，应以当前仓库实际文件为准。

`bioSkills` 支持 Codex CLI 安装，并支持按 category 选择安装。但 FastMitoAssembler 不应该安装或依赖全量 bioSkills，因为全量内容过大，且大部分与本项目无关。

## 2. 适合 FastMitoAssembler 的 Skills

### 2.1 核心采用

这些 skill 与本项目直接相关，建议作为方案设计和后续 Codex 开发时的参考。

| skill | 用途 | 在 FastMitoAssembler 中的对应位置 |
|---|---|---|
| `bio-workflow-management-snakemake-workflows` | Snakemake 规则、config、target、conda、HPC/profile 设计 | 拆分 `smk/main.smk`，新增 `smk/rules/*.smk` 和 target rules |
| `bio-read-qc-fastp-workflow` | fastp 的 adapter trimming、quality filtering、HTML/JSON report | 复用并扩展现有 `fastp_adapter_trim` 规则 |
| `bio-paired-end-fastq` | R1/R2 命名识别、配对检查、批量输入 | 优化 `_detect_samples`、`fq_path_pattern`、后续 sample sheet |
| `bio-batch-processing` | 批量处理多样本 FASTA/FASTQ | summary、seed 拆分、批量收集结果 |
| `bio-compressed-files` | `.gz/.bgz/.bz2` 序列文件读写 | Python summary 和 seed 解析需支持压缩 FASTA/FASTQ |
| `bio-format-conversion` | FASTA/FASTQ/GenBank 转换 | `seed_input` 支持 FASTA/GenBank，MitoZ 注释输入准备 |
| `bio-write-sequences` | 标准化写出 FASTA/GenBank | `result/summary/{sample}.{tool}.fasta` 标准写出 |
| `bio-reporting-automated-qc-reports` | MultiQC 聚合 fastp/FastQC/自定义指标 | 后续增加 `fma qc` 或 `summary_report.tsv` 聚合 |

### 2.2 可选采用

这些 skill 有价值，但不应放入 v1 核心依赖。

| skill | 是否采用 | 原因 |
|---|---|---|
| `bio-local-blast` | 可选 | 可用于组装结果污染筛查、候选 contig 来源验证，但依赖本地数据库，不应默认强制 |
| `bio-read-qc-contamination-screening` | 可选 | FastQ Screen 可筛查污染，但需要预建多物种 reference，适合作为高级 QC |
| `bio-genome-assembly-assembly-qc` | 部分参考 | QUAST 可在有 reference 时比较组装，BUSCO 不适合细胞器/nr 常规结果 |
| `bio-genome-assembly-contamination-detection` | 不作为核心 | CheckM/CheckM2/GUNC 主要面向微生物基因组/MAG，不适合默认评估线粒体、叶绿体或 nr |
| `bio-genome-assembly-short-read-assembly` | 概念参考 | 主要讲 SPAdes，GetOrganelle 内部用 SPAdes 思路，但 FastMitoAssembler 不应把 SPAdes 直接变成新主流程 |
| `bio-genome-assembly-metagenome-assembly` | 不作为核心 | 用户问题是浅层测序细胞器/nr 组装，不是 metagenome assembly |

### 2.3 不建议采用

以下类别与当前目标偏离较大，不纳入 FastMitoAssembler v1 设计：

- single-cell
- variant-calling
- RNA-seq/differential-expression
- clinical-databases
- proteomics/metabolomics
- ATAC-seq/ChIP-seq/Hi-C
- population-genetics
- genome-engineering

## 3. Skills 对现有方案的修正意见

### 3.1 不安装全量 bioSkills

推荐策略：

1. 当前阶段只作为调研和设计参考，不立即把第三方 skills 安装进项目。
2. 若后续需要安装，只做项目级安装，不做全局安装。
3. 若安装，只选 category：

```bash
cd /tmp/bioSkills_fma_research
./install-codex.sh --project /mnt/d/Codex/fastmito --categories "workflow-management,read-qc,sequence-io,genome-assembly,reporting,database-access" --dry-run
```

不建议安装全量，因为全量 skill 会引入大量与本流程无关的触发规则，降低后续对 FastMitoAssembler 的专注度。

### 3.2 更好的做法是创建项目专属 skill

后续可创建一个项目级 skill：

```text
.agents/skills/fastmitoassembler-bioflow/SKILL.md
```

它只记录 FastMitoAssembler 的架构、子命令、输入输出、外部工具约束和开发规范。第三方 bioSkills 只作为参考来源，不直接主导项目实现。

## 4. 优化后的总体架构

### 4.1 基本原则

FastMitoAssembler 的定位应保持为流程整合工具，而不是重新实现 MEANGS、NOVOPlasty、GetOrganelle、MitoZ 或 fastp。

Python 负责：

- CLI 子命令
- 配置合并和校验
- 样本发现
- seed 解析和拆分
- summary FASTA/TSV 标准化
- 调用 Snakemake target

Snakemake 负责：

- 每个外部工具的实际运行
- DAG 依赖
- per-rule conda/env
- log/benchmark
- dry-run/HPC/profile
- 单工具和串联流程组合

外部工具负责：

- MEANGS: 快速 seed/初步线粒体候选
- NOVOPlasty: seed-driven 细胞器组装
- GetOrganelle: 细胞器/nr 组装和补强
- MitoZ: 主要做 annotation，组装模式只作为可选 passthrough
- fastp: 可选预处理/QC，不默认过度过滤浅层数据

### 4.2 Snakemake 模块化

将当前单一 `smk/main.smk` 拆为：

```text
FastMitoAssembler/FastMitoAssembler/smk/main.smk
FastMitoAssembler/FastMitoAssembler/smk/rules/common.smk
FastMitoAssembler/FastMitoAssembler/smk/rules/preprocess.smk
FastMitoAssembler/FastMitoAssembler/smk/rules/meangs.smk
FastMitoAssembler/FastMitoAssembler/smk/rules/novoplasty.smk
FastMitoAssembler/FastMitoAssembler/smk/rules/getorganelle.smk
FastMitoAssembler/FastMitoAssembler/smk/rules/mitoz.smk
FastMitoAssembler/FastMitoAssembler/smk/rules/summary.smk
FastMitoAssembler/FastMitoAssembler/smk/rules/report.smk
```

职责：

- `common.smk`: `SAMPLES`、路径、FASTQ、tool prefix、通用 helper。
- `preprocess.smk`: fastp，默认关闭。
- `meangs.smk`: MEANGS 规则，独立 target。
- `novoplasty.smk`: seed 准备、NOVOPlasty config、NOVOPlasty run。
- `getorganelle.smk`: 支持独立运行、seed 运行、nr/anonym、subsample。
- `mitoz.smk`: annotate 默认，assembly 可选。
- `summary.smk`: 调用 Python summary helper。
- `report.smk`: 复用现有 `report.py` 生成 materials and methods。
- `main.smk`: 只 include 模块并定义最终 target。

这满足“每个软件独立 smk，更好组合”的要求，同时不为每个子命令重复造一套 rule。

### 4.3 CLI 子命令

保留：

```bash
fma run
fma init
fma check
fma config
fma setup
fma prepare
```

新增：

```bash
fma meangs
fma novoplasty
fma getorganelle
fma mitoz
fma mg-nov
fma mg-get
fma mg-nov-get
fma summary
```

建议后续增加但不放入第一批：

```bash
fma qc
fma report
```

所有新子命令都复用 `fma run` 的基础参数：

```bash
--reads_dir
--result_dir
--samples
--suffix_fq
--fq_path_pattern
--configfile
--optionfile
--cores
--dryrun
--use-conda / --no-use-conda
--conda-prefix
--keepgoing
--unlock
```

每个子命令只是选择不同 Snakemake target，不重复实现外部工具运行逻辑。

### 4.4 Snakemake target 映射

```text
fma run          -> all
fma meangs       -> meangs_all
fma novoplasty   -> novoplasty_all
fma getorganelle -> getorganelle_all
fma mitoz        -> mitoz_all
fma mg-nov       -> mg_nov_all
fma mg-get       -> mg_get_all
fma mg-nov-get   -> mg_nov_get_all
fma summary      -> summary_all
```

`fma run` 必须保持当前高成功率一键流程：

```text
fastp 可选 -> MEANGS -> NOVOPlasty -> GetOrganelle -> MitoZ annotate -> report
```

`fma run` 是保留的“资源足够时成功率高”的粗粒度流程。

## 5. 各工具流程设计

### 5.1 fastp

默认：

```yaml
fastp:
  enabled: false
  mode: adapter_only
  extra_args: ''
```

`adapter_only` 模式：

```bash
fastp --detect_adapter_for_pe -Q -L
```

原因：浅层细胞器组装中，过强 quality/length trimming 可能减少本来就少的细胞器 reads。默认只去 adapter，更稳妥。

高级模式可选：

```yaml
fastp:
  enabled: true
  mode: standard
  qualified_quality_phred: 20
  length_required: 36
  cut_right: true
  extra_args: ''
```

输出：

```text
result/{sample}/0.fastp/{sample}_1.adapter.fq.gz
result/{sample}/0.fastp/{sample}_2.adapter.fq.gz
logs/{sample}/fastp.log.html
logs/{sample}/fastp.log.json
```

下游 MEANGS、NOVOPlasty、GetOrganelle 自动使用 fastp 输出。

### 5.2 MEANGS

目标：

- 支持批量运行。
- 支持作为独立组装/检测工具。
- 支持作为 NOVOPlasty seed 来源。
- 保留现有 `--deepin` 成功率优势。

命令示例：

```bash
fma meangs \
  --reads_dir reads \
  --samples sample1 --samples sample2 \
  --fq_path_pattern "{sample}/{sample}_1.clean.fq.gz" \
  --cores 16
```

输出：

```text
result/{sample}/1.MEANGS/{sample}_deep_detected_mito.fas
result/summary/{sample}.meangs.fasta
```

### 5.3 NOVOPlasty

目标：

- 支持批量运行所有 FASTQ。
- 支持单一 seed 给所有样本。
- 支持 multi-FASTA seed，每个 `>` 的第一个 token 匹配 sample basename。
- 支持由 MEANGS 自动提供 seed 的串联流程。

新增 seed config：

```yaml
seed_input:
seed_mode: single       # single | by-sample
seed_missing: fail      # fail | skip
```

独立 NOVOPlasty：

```bash
fma novoplasty \
  --reads_dir reads \
  --samples sample1 \
  --seed_input seed.fa \
  --seed_mode single
```

multi-FASTA seed：

```text
>sample1
ATGC...
>sample2
ATGC...
```

命令：

```bash
fma novoplasty \
  --reads_dir reads \
  --seed_input seeds.by_sample.fa \
  --seed_mode by-sample
```

MEANGS + NOVOPlasty：

```bash
fma mg-nov --reads_dir reads --samples sample1 --cores 16
```

输出：

```text
result/{sample}/2.NOVOPlasty/config.txt
result/{sample}/2.NOVOPlasty/{sample}.novoplasty.fasta
result/summary/{sample}.novoplasty.fasta
result/summary/{sample}.mg-nov.fasta
```

### 5.4 GetOrganelle

目标：

- 支持独立批量运行。
- 支持从用户 seed、MEANGS seed、NOVOPlasty FASTA 或无 seed 运行。
- 支持 `-F` 数据库选择，包括 mt、plastome、nr 相关类型。
- 保留现有 `subsample_gb` 和 `getorganelle_all_data` 逻辑。

新增 config：

```yaml
getorganelle_seed_source: auto  # auto | none | user | meangs | novoplasty
getorganelle_f: animal_mt
genes:
```

独立运行：

```bash
fma getorganelle \
  --reads_dir reads \
  --samples sample1 \
  --organelle_database animal_mt
```

nr/anonym 类任务：

```bash
fma getorganelle \
  --reads_dir reads \
  --samples sample1 \
  --organelle_database anonym \
  --seed_input nr_seed.fa \
  --genes "18S,ITS,28S"
```

串联：

```bash
fma mg-get --reads_dir reads --samples sample1
fma mg-nov-get --reads_dir reads --samples sample1
```

输出：

```text
result/{sample}/3.GetOrganelle/{organelle_database}.get_organelle.fasta
result/summary/{sample}.getorganelle.fasta
result/summary/{sample}.mg-get.fasta
result/summary/{sample}.mg-nov-get.fasta
```

### 5.5 MitoZ

目标：

- 支持批量调用。
- 默认只做 annotate，不把 MitoZ assembly 作为主装配来源。
- 可选保留 MitoZ assembly passthrough，满足用户“本身支持批量组装”的要求。
- 允许用户指定外部 FASTA 或 summary FASTA 作为注释输入。

新增 config：

```yaml
mitoz_mode: annotate       # annotate | assemble
assembly_fasta:
mitoz_input_source: auto   # auto | assembly_fasta | summary | getorganelle | novoplasty
```

注释命令：

```bash
fma mitoz \
  --samples sample1 \
  --assembly_fasta result/summary/sample1.mg-nov-get.fasta
```

默认输入优先级：

```text
assembly_fasta
summary FASTA
GetOrganelle FASTA
NOVOPlasty FASTA
```

输出：

```text
result/{sample}/4.MitozAnnotate/
```

MitoZ annotation 结果记录到 report/summary TSV，但不作为组装 FASTA 的默认来源。

## 6. Summary FASTA 设计

这是用户原始需求中的核心功能：每个工具独立收集结果，串联流程收集最后一步结果，并供 MitoZ 注释使用。

### 6.1 输出文件

```text
result/summary/{sample}.meangs.fasta
result/summary/{sample}.novoplasty.fasta
result/summary/{sample}.getorganelle.fasta
result/summary/{sample}.mg-nov.fasta
result/summary/{sample}.mg-get.fasta
result/summary/{sample}.mg-nov-get.fasta
result/summary/summary_all.fasta
result/summary/summary_report.tsv
```

### 6.2 FASTA header

```text
>{sample}|software={software}|pipeline={pipeline}|locus={mt|pt|nr|unknown}|idx={n}|topology={circular|linear|unknown}|length={bp}
```

示例：

```text
>sample1|software=getorganelle|pipeline=mg-nov-get|locus=mt|idx=1|topology=circular|length=16531
```

### 6.3 TSV 字段

```text
sample
software
pipeline
locus
source_file
record_id
length
topology
status
output_fasta
notes
```

### 6.4 收集规则

- `fma meangs`: 收集 MEANGS 输出。
- `fma novoplasty`: 收集 NOVOPlasty 输出。
- `fma getorganelle`: 收集 GetOrganelle 输出。
- `fma mg-nov`: 收集 NOVOPlasty 输出。
- `fma mg-get`: 收集 GetOrganelle 输出。
- `fma mg-nov-get`: 收集 GetOrganelle 输出。
- `fma run`: 收集完整流程中最后有效组装输出，通常为 GetOrganelle。
- graph-only 或空 FASTA 不进入 final FASTA，但写入 `summary_report.tsv` 的 failed/empty 状态。

实现方式：

- 用 Python `Bio.SeqIO` 或轻量 FASTA parser 解析。
- 支持 `.fa/.fasta/.fas/.fna` 及 gzip 压缩。
- 不用 shell 拼接 FASTA。
- topology 从 header、GetOrganelle 文件名/内容、NOVOPlasty log 和已有标记中尽量解析；无法判断写 `unknown`。

## 7. 污染与低深度风险控制

用户原始问题中提到：浅层测序数据污染偏多时，直接一键 MEANGS -> NOVOPlasty -> GetOrganelle -> MitoZ 可能得到污染结果。因此优化方案加入分层 QC，但不把重型数据库工具作为默认依赖。

### 7.1 默认轻量 QC

默认加入 summary 级别检查：

- contig 数量
- 总长度
- 最长序列长度
- GC%
- N 数量
- topology
- 是否在预期 genome size 范围内
- 不同工具结果长度是否严重冲突
- MEANGS、NOVOPlasty、GetOrganelle 输出是否互相支持

### 7.2 fastp/MultiQC

fastp 输出 JSON/HTML，后续可用 MultiQC 聚合：

```text
logs/{sample}/fastp.log.json
logs/{sample}/fastp.log.html
result/qc/multiqc_report.html
```

### 7.3 可选污染筛查

后续 `fma qc` 可支持：

- `blastn` against user reference organelle database
- FastQ Screen against user configured contaminant genomes
- reference-guided QUAST if user提供 close reference

不建议默认使用 CheckM/CheckM2/GUNC，因为这些工具的主要对象是微生物基因组/MAG，不是细胞器或 nr 结果。

## 8. 代码改造路径

### Phase 0: 重新核对官方工具文档

在写代码前，重新核对每个工具当前官方文档和本地 `-h/--help` 输出，并更新：

```text
FastMitoAssembler/docs/research/meangs.md
FastMitoAssembler/docs/research/novoplasty.md
FastMitoAssembler/docs/research/getorganelle.md
FastMitoAssembler/docs/research/mitoz.md
FastMitoAssembler/docs/research/fastp.md
```

每个文档必须记录：

- 调研日期
- 软件版本
- 官方来源 URL
- 安装方式
- `--help` 或 `-h` 输出摘要
- 输入格式
- 输出格式
- 关键参数
- FastMitoAssembler 中采用/不采用的参数

### Phase 1: 无行为变化的 Snakemake 拆分

目标：先拆分文件，不改变 `fma run` 当前行为。

步骤：

1. 新建 `smk/rules/`。
2. 把当前 `main.smk` 拆到各工具 rule。
3. `main.smk` 只 include。
4. 跑 `fma run --dryrun` 对比当前 DAG。

### Phase 2: Python runner 共享化

新增：

```text
FastMitoAssembler/FastMitoAssembler/bin/_workflow.py
FastMitoAssembler/FastMitoAssembler/bin/_stages.py
```

`_workflow.py` 复用并抽出 `_run.py` 的：

- configfile 合并
- optionfile 合并
- sample auto-detect
- tool_envs 合并
- FASTQ 检查
- Snakemake 调用

`_stages.py` 定义各子命令，仅传入不同 target。

### Phase 3: seed 系统

新增：

```text
FastMitoAssembler/FastMitoAssembler/bin/_seed.py
```

支持：

- single seed
- by-sample multi-FASTA seed
- MEANGS seed
- NOVOPlasty seed
- seed 缺失 fail/skip

### Phase 4: summary 系统

新增：

```text
FastMitoAssembler/FastMitoAssembler/bin/_summary.py
FastMitoAssembler/FastMitoAssembler/smk/rules/summary.smk
```

实现：

- 每个工具独立 summary FASTA。
- 串联流程 summary FASTA。
- `summary_all.fasta`。
- `summary_report.tsv`。
- topology/length/status 标准化。

### Phase 5: 文档、示例、测试

更新：

- README 子命令示例。
- config template。
- 每个工具 research md。
- `docs/research/integration.md`。
- tests。

## 9. 测试清单

最小回归测试：

- `fma run --dryrun` 行为不变。
- 当前已有测试全部通过。

新增 dry-run 测试：

- `fma meangs --dryrun` 只触发 fastp 可选 + MEANGS + summary。
- `fma novoplasty --dryrun` 使用用户 seed，不隐式触发 MEANGS。
- `fma getorganelle --dryrun` 可无 seed 独立运行。
- `fma mitoz --dryrun` 可使用 `assembly_fasta`。
- `fma mg-nov --dryrun` 触发 MEANGS + NOVOPlasty + summary。
- `fma mg-get --dryrun` 触发 MEANGS + GetOrganelle + summary。
- `fma mg-nov-get --dryrun` 触发 MEANGS + NOVOPlasty + GetOrganelle + summary。
- `fma summary --dryrun` 只收集已有结果。

seed 测试：

- `seed_mode=single` 所有样本使用同一个 seed。
- `seed_mode=by-sample` 按 FASTA header 匹配 sample。
- by-sample 缺失 sample 时默认 fail。
- `seed_missing=skip` 时缺失样本写入 skipped 状态。

summary 测试：

- 空输出写 failed/empty TSV。
- circular header 识别为 circular。
- linear/scaffold header 识别为 linear。
- 无法判断写 unknown。
- 输出文件名符合 `{sample}.{software_or_pipeline}.fasta`。

fastp 测试：

- 默认关闭。
- 开启 adapter_only 后下游 FASTQ 指向 `0.fastp` 输出。
- HTML/JSON report 输出到 log 目录。

## 10. 当前最终建议

1. 不安装全量 bioSkills。
2. 只参考或项目级安装以下类别：`workflow-management`、`read-qc`、`sequence-io`、`genome-assembly`、`reporting`、`database-access`。
3. FastMitoAssembler 自己创建一个项目专属 skill 更合适，内容只围绕本项目。
4. 代码改造先做 Snakemake 模块拆分，再做 CLI 子命令，最后做 seed/summary。
5. `fma run` 保留为完整高成功率流程，不因子命令化而删除。
6. 每个外部工具单独 smk rule，但不要为每个子命令复制一套 rule。
7. summary 是本次改造的核心交付之一，必须优先实现。

## 11. 参考来源

- OpenAI skills: `https://github.com/openai/skills`
- GPTomics bioSkills: `https://github.com/GPTomics/bioSkills`
- Snakemake docs: `https://snakemake.readthedocs.io/`
- fastp: `https://github.com/OpenGene/fastp`
- GetOrganelle: `https://github.com/Kinggerm/GetOrganelle`
- NOVOPlasty: `https://github.com/ndierckx/NOVOPlasty`
- MitoZ: `https://github.com/linzhi2013/MitoZ`
- MEANGS: `https://github.com/YanCCscu/MEANGS`
