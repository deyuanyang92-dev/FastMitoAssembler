# fastmito-v002 版本设计方案

日期：2026-04-23

## 1. 版本定位

`fastmito-v002` 是 FastMitoAssembler 在现有代码框架上的结构化升级版本，不是新项目，也不是重写版。

v002 的目标是把当前“一键链式流程”升级为“可拆分、可组合、可核查”的流程整合系统，同时保留现有完整流程的高成功率优势。

当前已有框架：

- Python CLI：`FastMitoAssembler/FastMitoAssembler/bin/main.py`
- 现有 runner：`FastMitoAssembler/FastMitoAssembler/bin/_run.py`
- 单一 Snakefile：`FastMitoAssembler/FastMitoAssembler/smk/main.smk`
- 默认配置：`FastMitoAssembler/FastMitoAssembler/smk/config.yaml`
- Snakemake options：`FastMitoAssembler/FastMitoAssembler/smk/options.yaml`
- tool envs：`FastMitoAssembler/FastMitoAssembler/smk/envs/*.yaml`
- NOVOPlasty config 模板：`FastMitoAssembler/FastMitoAssembler/config.py`
- materials and methods 报告：`FastMitoAssembler/FastMitoAssembler/report.py`
- 工具检查与配置：`_check.py`、`_setup.py`、`_config.py`、`_other.py`

v002 的核心原则：

1. 不重写外部工具算法。
2. 复用当前 `fma run`、tool envs、config、report、check/setup 等已有模块。
3. Python 负责 CLI、配置、样本、seed、summary 和 Snakemake target 调度。
4. Snakemake 负责 DAG、rule、conda、log、benchmark、dry-run 和外部工具运行。
5. 每个软件拆成独立 `.smk` 模块，但不为每个子命令复制一套 rule。
6. 保留完整链式流程：MEANGS -> NOVOPlasty -> GetOrganelle -> MitoZ。

## 2. v002 版本目标

### 2.1 必须实现

v002 必须覆盖用户原始需求：

- 批量调用 MEANGS。
- 批量调用 NOVOPlasty。
- NOVOPlasty 支持单 seed。
- NOVOPlasty 支持 multi-FASTA by-sample seed。
- 批量调用 GetOrganelle。
- 批量调用 MitoZ，默认用于 annotation。
- 支持 `MEANGS -> NOVOPlasty`。
- 支持 `MEANGS -> GetOrganelle`。
- 支持 `MEANGS -> NOVOPlasty -> GetOrganelle`。
- 保留 `MEANGS -> NOVOPlasty -> GetOrganelle -> MitoZ` 完整流程。
- 每个工具和每个组合流程生成 summary FASTA。
- summary FASTA 可作为 MitoZ annotation 输入。
- fastp 可选启用，默认不过度过滤。

### 2.2 v002 不做

v002 不做以下事情：

- 不把 SPAdes、BLAST、CheckM、FastQ Screen 变成默认主流程。
- 不做 RNA-seq、single-cell、variant calling 等无关流程。
- 不把 MitoZ assembly 作为默认组装入口。
- 不安装全量 GPTomics/bioSkills。
- 不让 Python 直接替代 Snakemake 运行所有步骤。
- 不删除现有 `fma run` 行为。

## 3. 参考 skills 的采用方式

v002 参考下列 skills 的设计思想，但不直接依赖全量 bioSkills：

| 参考 skill | v002 采用内容 |
|---|---|
| `bio-workflow-management-snakemake-workflows` | Snakemake rule 模块化、target 映射、config、conda/env、dry-run/HPC 兼容 |
| `bio-read-qc-fastp-workflow` | fastp adapter-only 默认策略、HTML/JSON report 输出 |
| `bio-paired-end-fastq` | paired FASTQ 命名识别、R1/R2 样本匹配 |
| `bio-batch-processing` | 多样本批量处理和 summary 汇总 |
| `bio-compressed-files` | summary/seed 支持 gzip FASTA/FASTQ |
| `bio-format-conversion` | FASTA/GenBank seed 输入兼容 |
| `bio-write-sequences` | 标准化写出 summary FASTA |
| `bio-reporting-automated-qc-reports` | 后续 MultiQC/QC report 可扩展点 |

项目专属 skill：

```text
.agents/skills/fastmitoassembler-bioflow/SKILL.md
```

该 skill 是 v002 后续设计和实现的主要约束文件。

## 4. v002 总体架构

### 4.1 Python 层

新增或改造模块：

```text
FastMitoAssembler/FastMitoAssembler/bin/_workflow.py
FastMitoAssembler/FastMitoAssembler/bin/_stages.py
FastMitoAssembler/FastMitoAssembler/bin/_seed.py
FastMitoAssembler/FastMitoAssembler/bin/_summary.py
```

保留并复用：

```text
FastMitoAssembler/FastMitoAssembler/bin/main.py
FastMitoAssembler/FastMitoAssembler/bin/_run.py
FastMitoAssembler/FastMitoAssembler/bin/_check.py
FastMitoAssembler/FastMitoAssembler/bin/_setup.py
FastMitoAssembler/FastMitoAssembler/bin/_config.py
FastMitoAssembler/FastMitoAssembler/bin/_other.py
FastMitoAssembler/FastMitoAssembler/config.py
FastMitoAssembler/FastMitoAssembler/report.py
FastMitoAssembler/FastMitoAssembler/util.py
```

职责划分：

| 模块 | 职责 |
|---|---|
| `_workflow.py` | 从 `_run.py` 抽出共享配置合并、样本检测、tool_envs 合并、FASTQ 检查、Snakemake 调用 |
| `_stages.py` | 定义 `fma meangs`、`fma novoplasty` 等子命令，并映射到 Snakemake target |
| `_seed.py` | 解析 single seed、by-sample multi-FASTA seed、GenBank seed；生成每样本标准 seed FASTA |
| `_summary.py` | 解析各工具输出，写出 summary FASTA 和 summary TSV |
| `_run.py` | 保留 `fma run`，内部改为调用 `_workflow.py`，保持用户体验不变 |
| `report.py` | 保留 materials and methods；v002 后续可接入 summary TSV 和实际工具版本 |

### 4.2 Snakemake 层

当前：

```text
smk/main.smk
```

v002 目标：

```text
smk/main.smk
smk/rules/common.smk
smk/rules/preprocess.smk
smk/rules/meangs.smk
smk/rules/novoplasty.smk
smk/rules/getorganelle.smk
smk/rules/mitoz.smk
smk/rules/summary.smk
smk/rules/report.smk
```

职责：

| 文件 | 职责 |
|---|---|
| `main.smk` | include rules，定义 target rules |
| `common.smk` | SAMPLES、路径、FASTQ、tool prefix、通用 helper |
| `preprocess.smk` | fastp |
| `meangs.smk` | MEANGS 批量运行和 seed 输出 |
| `novoplasty.smk` | seed 准备、NOVOPlasty config、NOVOPlasty run |
| `getorganelle.smk` | GetOrganelle 独立/seed/组合运行 |
| `mitoz.smk` | MitoZ annotation 默认路径，assembly 可选 |
| `summary.smk` | 调用 `_summary.py` 汇总结果 |
| `report.smk` | 调用 `report.py` 生成 materials and methods |

第一阶段拆分时必须保持 `fma run --dryrun` 的 DAG 行为不变。

## 5. CLI 设计

### 5.1 保留命令

```bash
fma run
fma init
fma check
fma config
fma setup
fma prepare
```

### 5.2 新增命令

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

### 5.3 target 映射

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

### 5.4 通用参数

所有新增子命令复用 `fma run` 的核心参数：

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

### 5.5 命令示例

MEANGS：

```bash
fma meangs \
  --reads_dir reads \
  --samples sample1 \
  --cores 8
```

NOVOPlasty 单 seed：

```bash
fma novoplasty \
  --reads_dir reads \
  --samples sample1 \
  --seed_input seed.fa \
  --seed_mode single \
  --cores 8
```

NOVOPlasty by-sample seed：

```bash
fma novoplasty \
  --reads_dir reads \
  --seed_input seeds.by_sample.fa \
  --seed_mode by-sample \
  --cores 8
```

MEANGS -> NOVOPlasty：

```bash
fma mg-nov \
  --reads_dir reads \
  --samples sample1 \
  --cores 8
```

MEANGS -> GetOrganelle：

```bash
fma mg-get \
  --reads_dir reads \
  --samples sample1 \
  --organelle_database animal_mt \
  --cores 8
```

MEANGS -> NOVOPlasty -> GetOrganelle：

```bash
fma mg-nov-get \
  --reads_dir reads \
  --samples sample1 \
  --organelle_database animal_mt \
  --cores 8
```

MitoZ annotation：

```bash
fma mitoz \
  --samples sample1 \
  --assembly_fasta result/summary/sample1.mg-nov-get.fasta \
  --cores 8
```

完整旧流程：

```bash
fma run \
  --reads_dir reads \
  --samples sample1 \
  --cores 16
```

## 6. 配置设计

### 6.1 保持兼容的现有配置

继续支持：

```yaml
reads_dir:
samples: []
result_dir: result
fq_path_pattern: '{sample}/{sample}_1.clean.fq.gz'
organelle_database: animal_mt
seed_input:
genes:
tool_envs:
```

继续支持现有 MEANGS、NOVOPlasty、GetOrganelle、MitoZ 参数。

### 6.2 v002 新增配置

```yaml
workflow_target: all

seed_mode: single          # single | by-sample
seed_missing: fail         # fail | skip
seed_output_dir: '{result_dir}/{sample}/0.seed'

summary:
  enabled: true
  output_dir: '{result_dir}/summary'
  include_failed: true
  min_length: 0

fastp:
  enabled: false
  mode: adapter_only       # adapter_only | standard | custom
  extra_args: ''

getorganelle_seed_source: auto  # auto | none | user | meangs | novoplasty
mitoz_mode: annotate            # annotate | assemble
mitoz_input_source: auto        # auto | assembly_fasta | summary | getorganelle | novoplasty
assembly_fasta:
```

### 6.3 backward compatibility

为了不破坏旧用户：

- 未提供 `seed_mode` 时默认 `single`。
- 未提供 `fastp.mode` 时默认 `adapter_only`。
- 未提供 `summary` 时仍启用 summary，但不影响旧流程最终 MitoZ report。
- `fma run` 默认 target 仍为 `all`。
- 旧 `seed_input` 仍有效。

## 7. FASTQ 与样本识别

v002 保留当前 `_detect_samples(reads_dir, suffix_fq)` 的思路，但增强校验：

当前支持：

```text
_1.clean.fq.gz,_2.clean.fq.gz
_R1.fastq.gz,_R2.fastq.gz
_R1_001.fastq.gz,_R2_001.fastq.gz
```

v002 要求：

- R1/R2 成对检查。
- 样本名去重。
- 缺失 R2 时明确报错。
- `fq_path_pattern` 仍优先。
- 后续可加 sample sheet，但不作为 v002 必须项。

## 8. seed 设计

### 8.1 seed 来源

v002 seed 来源包括：

```text
user seed
MEANGS output
NOVOPlasty output
none
```

### 8.2 seed 模式

single：

```yaml
seed_input: seed.fa
seed_mode: single
```

所有样本使用同一个 seed。

by-sample：

```yaml
seed_input: seeds.fa
seed_mode: by-sample
```

multi-FASTA：

```text
>sample1
ATGC...
>sample2
ATGC...
```

header 第一个 token 必须匹配 sample。

### 8.3 标准 seed 输出

每个样本生成标准 seed：

```text
result/{sample}/0.seed/{sample}.seed.fasta
```

NOVOPlasty config 和 GetOrganelle seed 参数只读取这个标准 seed 文件，避免在每个 rule 中重复解析 seed。

### 8.4 缺失行为

默认：

```yaml
seed_missing: fail
```

缺失 seed 直接失败。

可选：

```yaml
seed_missing: skip
```

对应样本写入 `summary_report.tsv` 的 skipped 状态，但不静默替代 seed。

## 9. 各工具流程

### 9.1 fastp

默认关闭。

开启后默认：

```bash
fastp --detect_adapter_for_pe -Q -L
```

输出：

```text
result/{sample}/0.fastp/{sample}_1.adapter.fq.gz
result/{sample}/0.fastp/{sample}_2.adapter.fq.gz
logs/{sample}/fastp.log
logs/{sample}/fastp.log.html
logs/{sample}/fastp.log.json
```

下游工具自动切换到 fastp 输出。

### 9.2 MEANGS

复用当前 `MEANGS` rule。

v002 输出标准化：

```text
result/{sample}/1.MEANGS/{sample}_deep_detected_mito.fas
result/summary/{sample}.meangs.fasta
```

MEANGS 独立运行和作为 seed 来源都必须支持。

### 9.3 NOVOPlasty

复用当前 `NOVOPLASTY_CONFIG_TPL`。

新增 seed 标准化输入：

```text
result/{sample}/0.seed/{sample}.seed.fasta
```

输出：

```text
result/{sample}/2.NOVOPlasty/config.txt
result/{sample}/2.NOVOPlasty/{sample}.novoplasty.fasta
result/summary/{sample}.novoplasty.fasta
result/summary/{sample}.mg-nov.fasta
```

### 9.4 GetOrganelle

v002 支持三种运行方式：

1. 无 seed 独立运行。
2. 用户 seed 运行。
3. MEANGS/NOVOPlasty seed 组合运行。

输出：

```text
result/{sample}/3.GetOrganelle/{organelle_database}.get_organelle.fasta
result/summary/{sample}.getorganelle.fasta
result/summary/{sample}.mg-get.fasta
result/summary/{sample}.mg-nov-get.fasta
```

nr 相关需求主要通过 GetOrganelle 的 `-F`/`genes`/seed 能力支持。

### 9.5 MitoZ

v002 默认：

```yaml
mitoz_mode: annotate
```

输入优先级：

```text
assembly_fasta
summary FASTA
GetOrganelle FASTA
NOVOPlasty FASTA
```

输出仍沿用当前 MitoZ result 目录：

```text
result/{sample}/4.MitozAnnotate/
```

MitoZ assembly 可作为可选 passthrough，但不作为默认可信组装路径。

## 10. Summary 设计

### 10.1 输出文件

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

### 10.2 FASTA header

```text
>{sample}|software={software}|pipeline={pipeline}|locus={mt|pt|nr|unknown}|idx={n}|topology={circular|linear|unknown}|length={bp}
```

### 10.3 TSV 字段

```text
sample
software
pipeline
locus
source_file
record_id
length
gc_percent
n_count
topology
status
output_fasta
notes
```

### 10.4 串联流程收集原则

```text
meangs       -> MEANGS output
novoplasty   -> NOVOPlasty output
getorganelle -> GetOrganelle output
mg-nov       -> NOVOPlasty output
mg-get       -> GetOrganelle output
mg-nov-get   -> GetOrganelle output
run          -> GetOrganelle output, then MitoZ annotation/report
```

空输出、缺失输出、graph-only 输出不进入 final FASTA，但必须进入 TSV 记录。

## 11. QC 与污染风险控制

v002 默认做轻量 summary QC，不默认做重型数据库污染筛查。

默认 QC 指标：

- contig 数量
- 总长度
- 最长序列长度
- GC%
- N count
- topology
- 是否落在预期 genome size 范围
- 多工具结果长度是否严重冲突

可选后续扩展：

- `fma qc`
- local BLAST against user database
- FastQ Screen
- MultiQC
- reference-guided QUAST

不默认使用 CheckM/CheckM2/GUNC。

## 12. v002 实施阶段

### v002.0 设计冻结

交付：

- `fastmito-v002.md`
- 更新 `communication—all.md`
- 明确不直接改代码

### v002.1 Snakemake 无行为拆分

交付：

- `smk/rules/*.smk`
- `main.smk` include 化
- `fma run --dryrun` 行为不变

### v002.2 Python workflow runner

交付：

- `_workflow.py`
- `_stages.py`
- `main.py` 注册新子命令
- `fma run` 继续可用

### v002.3 seed 系统

交付：

- `_seed.py`
- `seed_mode`
- `seed_missing`
- 每样本标准 seed FASTA
- NOVOPlasty seed 接入

### v002.4 summary 系统

交付：

- `_summary.py`
- `summary.smk`
- per-tool FASTA
- per-pipeline FASTA
- `summary_all.fasta`
- `summary_report.tsv`

### v002.5 GetOrganelle/MitoZ 输入增强

交付：

- GetOrganelle 独立运行
- GetOrganelle seed source
- `genes` 正确传递
- MitoZ 使用 `assembly_fasta` 或 summary FASTA

### v002.6 文档和测试

交付：

- README 示例
- config template 更新
- 每个子命令 dry-run 测试
- seed 测试
- summary 测试
- fastp 测试

## 13. 测试设计

### 13.1 回归测试

- `fma run --dryrun` 与当前完整流程一致。
- 已有 `fma check`、`fma setup`、`fma prepare` 不受影响。

### 13.2 子命令 dry-run

- `fma meangs --dryrun`
- `fma novoplasty --dryrun`
- `fma getorganelle --dryrun`
- `fma mitoz --dryrun`
- `fma mg-nov --dryrun`
- `fma mg-get --dryrun`
- `fma mg-nov-get --dryrun`
- `fma summary --dryrun`

### 13.3 seed 测试

- single seed。
- by-sample multi-FASTA。
- by-sample 缺失样本。
- GenBank seed 转 FASTA。
- gzip FASTA seed。

### 13.4 summary 测试

- MEANGS 输出收集。
- NOVOPlasty 输出收集。
- GetOrganelle 输出收集。
- circular/linear/unknown topology。
- 空输出状态。
- `summary_all.fasta` 聚合。

### 13.5 fastp 测试

- 默认关闭。
- 开启 adapter-only。
- 下游 FASTQ 指向 fastp 输出。
- HTML/JSON report 存在。

## 14. v002 最终验收标准

v002 完成时必须满足：

1. `fma run` 仍可执行完整链式流程。
2. 每个工具可以单独批量运行。
3. 组合流程可以通过子命令选择。
4. NOVOPlasty seed 管理不再需要手工逐样本写 config。
5. GetOrganelle 可以独立运行，也可以接收 MEANGS/NOVOPlasty seed。
6. MitoZ 默认使用外部组装 FASTA 注释。
7. 每个工具和每个组合流程都有 summary FASTA。
8. summary TSV 能记录失败、空结果和 topology。
9. fastp 可选启用，默认不过度过滤。
10. Snakemake rule 模块化，后续组合流程易扩展。

## 15. 文件清单

v002 设计相关文件：

```text
FastMitoAssembler/docs/design/fastmito-v002.md
FastMitoAssembler/docs/research/codex_bio_skills_selection_and_optimized_plan.md
.agents/skills/fastmitoassembler-bioflow/SKILL.md
communication—all.md
plan.txt
```

v002 后续实现预计涉及：

```text
FastMitoAssembler/FastMitoAssembler/bin/main.py
FastMitoAssembler/FastMitoAssembler/bin/_run.py
FastMitoAssembler/FastMitoAssembler/bin/_workflow.py
FastMitoAssembler/FastMitoAssembler/bin/_stages.py
FastMitoAssembler/FastMitoAssembler/bin/_seed.py
FastMitoAssembler/FastMitoAssembler/bin/_summary.py
FastMitoAssembler/FastMitoAssembler/smk/main.smk
FastMitoAssembler/FastMitoAssembler/smk/rules/*.smk
FastMitoAssembler/FastMitoAssembler/smk/config.yaml
FastMitoAssembler/FastMitoAssembler/report.py
```

## 16. 当前决策

`fastmito-v002` 采用“现有框架渐进式升级”方案。

第一步不是写新功能，而是做无行为变化的 Snakemake 拆分；这样可以最大限度保护当前已经能跑通的完整链式流程。后续再依次加入子命令、seed 系统、summary 系统和 MitoZ 输入增强。
