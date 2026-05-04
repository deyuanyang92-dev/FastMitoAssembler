# FastMitoAssembler Wiki

## 目录

1. [项目概述](#项目概述)
2. [安装指南](#安装指南)
3. [快速开始](#快速开始)
4. [命令参考](#命令参考)
5. [双后端架构](#双后端架构)
6. [一键化流程](#一键化流程)
7. [配置参考](#配置参考)
8. [输出说明](#输出说明)
9. [常见问题](#常见问题)
10. [更新日志](#更新日志)

---

## 项目概述

### 什么是 FastMitoAssembler？

FastMitoAssembler (`fma`) 是一个用于线粒体基因组组装和注释的自动化流程。它串联多个组装工具，自动传播种子序列，并生成标准化的输出结果。

### 核心特性

- **双后端架构**: 所有工具同时支持 Snakemake 和 Python 后端
- **一键化流程**: `fma fsb-all` 一键运行 fastp → MultiQC → SPAdes → BUSCO
- **自动种子检测**: MEANGS 无参种子检测，无需手动提供种子
- **隔离环境**: 每个工具独立 conda 环境，避免依赖冲突
- **断点续跑**: 自动检测已完成样本，支持续跑
- **双语报告**: 自动生成中英文 Materials & Methods

### 支持的生物

| 类群 | 数据库 | 遗传密码 |
|------|--------|----------|
| 动物 (默认) | `animal_mt` | 5 (无脊椎) / 2 (脊椎) |
| 真菌 | `fungus_mt` | 4 |
| 植物 | `embplant_mt` | 1 |
| 叶绿体 | `embplant_pt` | 11 |

### 流程架构

```
原始数据 (FASTQ)
      │
      ▼
┌─────────────┐
│   fastp     │  质控与接头去除
└─────────────┘
      │
      ▼
┌─────────────┐
│   MEANGS    │  种子序列检测
└─────────────┘
      │
      ├──────────────────────┐
      ▼                      ▼
┌─────────────┐      ┌─────────────┐
│ NOVOPlasty  │      │ GetOrganelle│
└─────────────┘      └─────────────┘
      │                      │
      └──────────┬───────────┘
                 ▼
          ┌─────────────┐
          │    MitoZ    │  基因注释
          └─────────────┘
                 │
                 ▼
          ┌─────────────┐
          │   Summary   │  结果汇总
          └─────────────┘
```

---

## 安装指南

### 系统要求

- Python >= 3.9
- conda / mamba (推荐)
- ~20 GB 磁盘空间 (含数据库)

### 快速安装

```bash
# 1. 创建环境
mamba create -n FastMitoAssembler -c conda-forge \
    python=3.12 "snakemake>=7,<8" click jinja2 pyyaml

conda activate FastMitoAssembler

# 2. 安装 FastMitoAssembler
pip install git+https://github.com/deyuanyang92-dev/FastMitoAssembler.git

# 3. 安装工具环境
fma prepare tools

# 4. 准备数据库
fma prepare ncbitaxa
fma prepare organelle -a animal_mt

# 5. 验证安装
fma check
```

### 使用已有工具

如果你已经安装了 MEANGS、NOVOPlasty、GetOrganelle、MitoZ：

```bash
# 自动检测
fma check --save

# 或手动配置
fma config set meangs --conda-env my-meangs-env
fma config set novoplasty --conda-env my-novoplasty-env
fma config set getorganelle --conda-env my-getorganelle-env
fma config set mitoz --conda-env my-mitoz-env
```

---

## 快速开始

### 示例：3 个环节动物样本

```bash
# 1. 初始化项目
mkdir my_project && cd my_project
fma init

# 2. 编辑 config.yaml
cat > config.yaml << 'EOF'
reads_dir: /path/to/reads
samples: [POL1, POL10, POL11]
result_dir: result
organelle_database: animal_mt
genetic_code: 5
mitoz_clade: Annelida-segmented-worms
EOF

# 3. 运行流程
fma run --configfile config.yaml --cores 48 --no-use-conda
```

### 一键化流程 (fastp → SPAdes → BUSCO)

```bash
# Python 后端 (无需 Snakemake)
fma fsb-all --backend python \
    -r /path/to/reads \
    -o /path/to/result \
    --mode meta \
    -t 16 -m 32

# Snakemake 后端
fma fsb-all --backend snakemake \
    -r /path/to/reads \
    -o /path/to/result \
    --mode meta
```

---

## 命令参考

### 主命令

| 命令 | 说明 | 后端支持 |
|------|------|----------|
| `fma run` | 完整流程 | Snakemake |
| `fma fsb-all` | fastp → MultiQC → SPAdes → BUSCO | Python + Snakemake |
| `fma meangs` | MEANGS 种子检测 | Python + Snakemake |
| `fma novoplasty` | NOVOPlasty 组装 | Python + Snakemake |
| `fma getorganelle` | GetOrganelle 组装 | Python + Snakemake |
| `fma mitoz` | MitoZ 注释 | Python + Snakemake |
| `fma spades` | SPAdes 组装 | Python + Snakemake |
| `fma busco` | BUSCO 评估 | Python + Snakemake |
| `fma multiqc` | MultiQC 汇总 | Python + Snakemake |

### 链式命令

| 命令 | 流程 | 后端支持 |
|------|------|----------|
| `fma mg-nov` | MEANGS → NOVOPlasty | Python + Snakemake |
| `fma mg-get` | MEANGS → GetOrganelle | Python + Snakemake |
| `fma mg-nov-get` | MEANGS → NOVOPlasty → GetOrganelle | Python + Snakemake |

### 配置命令

| 命令 | 说明 |
|------|------|
| `fma init` | 创建 config.yaml |
| `fma check` | 检查工具状态 |
| `fma config show` | 显示工具配置 |
| `fma config set <tool>` | 设置工具路径 |
| `fma prepare tools` | 安装工具环境 |
| `fma prepare ncbitaxa` | 下载 NCBI 分类数据库 |
| `fma prepare organelle` | 下载 GetOrganelle 数据库 |

---

## 双后端架构

### 概述

所有工具同时支持 **Snakemake** 和 **Python** 两种后端：

| 后端 | 优点 | 缺点 |
|------|------|------|
| **Snakemake** | 自动依赖管理、断点续跑、HPC 支持 | 需要安装 Snakemake |
| **Python** | 轻量级、无需 Snakemake、直接执行 | 需手动管理依赖顺序 |

### 使用方式

```bash
# Snakemake 后端 (默认)
fma meangs --reads_dir /data -o result

# Python 后端
fma meangs --backend python --reads_dir /data -o result --parallel-jobs 5
```

### Python Runner 特性

- **Popen 流式读取**: 避免缓冲区满导致子进程挂起
- **Checkpoint 检测**: 自动续跑未完成任务
- **ThreadPoolExecutor**: 并行批量执行
- **信号处理**: 支持 Ctrl+C 优雅终止
- **状态文件**: 记录成功/失败样本列表

---

## 一键化流程

### fma fsb-all

一键运行 `fastp → MultiQC → SPAdes → BUSCO` 完整流程。

```bash
fma fsb-all --backend python \
    -r /path/to/reads \
    -o /path/to/result \
    --mode meta \
    --lineage metazoa_odb10 \
    -t 16 -m 32 \
    --parallel-jobs 3
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--backend` | `python` | 后端: `python` 或 `snakemake` |
| `-r, --reads-dir` | 必需 | 输入 FASTQ 目录 |
| `-o, --result-dir` | `result` | 输出目录 |
| `--mode` | `meta` | SPAdes 模式 |
| `--fastp-mode` | `adapter_only` | fastp 模式 |
| `--lineage` | `metazoa_odb10` | BUSCO lineage |
| `-t, --threads` | `16` | 每个任务线程数 |
| `-m, --memory` | `32` | 内存限制 (GB) |
| `--parallel-jobs` | `3` | 并行任务数 |
| `--force` | `False` | 强制重跑 |

### SPAdes 模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `default` | 通用组装 | 标准 WGS |
| `isolate` | 细菌分离株 | 高覆盖度细菌 |
| `meta` | 宏基因组 | 复杂微生物群落 |
| `rna` | 转录组 | RNA-seq |
| `plasmid` | 质粒 | 质粒检测 |
| `metaviral` | 病毒 | 宏基因组病毒 |
| `shallow` | 低深度 | 低覆盖度数据 |

### fastp 模式

| 模式 | 说明 | 参数 |
|------|------|------|
| `adapter_only` | 仅去接头 | `--detect_adapter_for_pe -Q -L` |
| `shallow_data` | 最大化保留 | `--n_base_limit 10 --disable_low_complexity_filter` |
| `transcriptome` | RNA-seq | `--trim_poly_x --cut_front --cut_tail` |
| `full_qc` | 标准 WGS | `--qualified_quality_phred 20` |

### 输出结构

```
result/
├── fastp/                    # fastp 质控结果
│   ├── sample1/
│   │   ├── sample1_1.clean.fq.gz
│   │   ├── sample1_2.clean.fq.gz
│   │   ├── fastp.json
│   │   └── fastp.html
│   └── finished_fastp.txt
├── multiqc/                  # MultiQC 汇总报告
│   └── multiqc_report.html
├── spades/                   # SPAdes 组装结果
│   ├── sample1/
│   │   ├── contigs.fasta
│   │   ├── scaffolds.fasta
│   │   └── spades.log
│   └── spades_status.txt
├── busco/                    # BUSCO 评估结果
│   ├── sample1/
│   │   ├── short_summary.txt
│   │   └── busco.log
│   └── busco_status.txt
└── fsb_all.log               # 流程日志
```

---

## 配置参考

### config.yaml 完整示例

```yaml
# 输入输出
reads_dir: /path/to/reads
samples: [sample1, sample2, sample3]
result_dir: result

# 样本检测
fq_path_pattern: '{sample}/{sample}_1.clean.fq.gz'
fastq_pos: recursive  # recursive / subdir / flat

# 数据库
organelle_database: animal_mt
genetic_code: 5

# MEANGS
meangs_thread: 16
meangs_reads: 2000000
meangs_deepin: true
meangs_species_class: Arthropoda

# NOVOPlasty
novoplasty_genome_min_size: 12000
novoplasty_genome_max_size: 22000
novoplasty_kmer_size: 33
novoplasty_max_mem_gb: 10

# GetOrganelle
getorganelle_threads: 16
getorganelle_rounds: 15
subsample_gb: 5

# MitoZ
mitoz_clade: Arthropoda
mitoz_thread_number: 16

# fastp (可选)
fastp:
  enabled: true
  mode: adapter_only
  extra_args: ''

# SPAdes (可选)
spades:
  enabled: true
  mode: meta
  threads: 16
  memory_gb: 32

# BUSCO (可选)
busco:
  enabled: true
  lineage: metazoa_odb10
  mode: genome
  threads: 12

# 工具环境 (可选)
tool_envs:
  meangs:
    conda_env: FastMitoAssembler-meangs
  novoplasty:
    conda_env: FastMitoAssembler-novoplasty
```

### 样本检测模式

**recursive** (默认): 递归搜索所有子目录
```
reads/
  sample1/
    sample1_1.clean.fq.gz
    sample1_2.clean.fq.gz
  subdir/
    sample2/
      sample2_1.clean.fq.gz
```

**subdir**: 仅一级子目录
```
reads/
  sample1/
    sample1_1.fq.gz
  sample2/
    sample2_1.fq.gz
```

**flat**: 所有文件在根目录
```
reads/
  sample1_1.fq.gz
  sample1_2.fq.gz
  sample2_1.fq.gz
```

---

## 输出说明

### 目录结构

```
result/
├── sample1/
│   ├── 1.MEANGS/
│   │   └── animal_mt.meangs.fasta
│   ├── 2.NOVOPlasty/
│   │   └── sample1.novoplasty.fasta
│   ├── 3.GetOrganelle/
│   │   └── animal_mt.get_organelle.fasta
│   └── 4.MitozAnnotate/
│       └── sample1.result/
│           ├── summary.txt
│           ├── cds/
│           ├── genes/
│           └── circos.png
├── summary/
│   ├── summary_all.fasta
│   └── summary_report.tsv
├── logs/
│   └── sample1/
│       ├── meangs.log
│       ├── novoplasty.log
│       └── getorganelle.log
└── Materials_and_Methods.txt
```

### summary_report.tsv 列说明

| 列名 | 说明 |
|------|------|
| sample | 样本名 |
| software | 组装工具 |
| pipeline | 流程模式 |
| locus | 基因组类型 (mt/nr) |
| length | 序列长度 (bp) |
| gc_percent | GC 含量 (%) |
| topology | 拓扑结构 (circular/linear) |
| status | 状态 (ok/empty) |

---

## 常见问题

### Q: 如何选择后端？

**A**:
- 简单批量处理 → Python 后端 (`--backend python`)
- 复杂依赖管理 → Snakemake 后端 (`--backend snakemake`)
- HPC 集群 → Snakemake 后端

### Q: 样本检测失败？

**A**: 检查以下设置：
1. `reads_dir` 路径是否正确
2. `fq_path_pattern` 是否匹配文件名
3. `fastq_pos` 是否匹配目录结构

### Q: 如何续跑中断的任务？

**A**: 直接重新运行相同命令，已完成样本会自动跳过：
```bash
fma fsb-all --backend python -r /data -o result
```

### Q: MEANGS 没有产生种子？

**A**: 可能原因：
- 样本无线粒体信号
- `meangs_reads` 设置过低
- 物种类型不匹配 (`meangs_species_class`)

### Q: 如何使用已有种子？

**A**:
```bash
fma novoplasty --seed_input seed.fasta --seed_mode single
fma getorganelle --seed_input seeds.fasta --seed_mode by-sample
```

### Q: BUSCO lineage 如何选择？

**A**: 常用 lineage：
- `metazoa_odb10` - 后生动物
- `insecta_odb10` - 昆虫
- `vertebrata_odb10` - 脊椎动物
- `fungi_odb10` - 真菌
- `bacteria_odb10` - 细菌

---

## 更新日志

### v0.0.2b0 (2026-05)

**新功能**:
- 双后端架构：所有工具支持 Python + Snakemake
- 一键化流程：`fma fsb-all` (fastp → MultiQC → SPAdes → BUSCO)
- 新增命令：`fma spades`, `fma busco`, `fma multiqc`
- Python Runner：断点续跑、并行执行、信号处理

**修复**:
- MEANGS scaffold_seeds.fas 并行覆盖问题
- spades.smk 变量引用错误
- fsb-all Python 后端类型不匹配

**改进**:
- 自动目录结构检测
- 状态文件记录 (finished/unfinished.txt)
- 错误诊断与提示

### v0.0.1 (2025-12)

- 初始版本
- MEANGS、NOVOPlasty、GetOrganelle、MitoZ 支持
- Snakemake 流程框架
