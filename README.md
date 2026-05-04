# FastMitoAssembler

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Snakemake](https://img.shields.io/badge/Snakemake-7.x-green.svg)](https://snakemake.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 线粒体基因组组装与注释的一站式解决方案

**FastMitoAssembler** (`fma`) 是一个自动化流程，用于从 Illumina 短读长数据组装和注释线粒体基因组。它串联多个组装工具，自动传播种子序列，并生成标准化的输出结果和双语 Materials & Methods 报告。

## ✨ 核心特性

- 🔄 **双后端架构** - 所有工具同时支持 Snakemake 和 Python 后端
- 🚀 **一键化流程** - `fma fsb-all` 一键运行 fastp → MultiQC → SPAdes → BUSCO
- 🎯 **自动种子检测** - MEANGS 无参种子检测，无需手动提供种子
- 🔧 **隔离环境** - 每个工具独立 conda 环境，避免依赖冲突
- 📊 **断点续跑** - 自动检测已完成样本，支持续跑
- 📝 **双语报告** - 自动生成中英文 Materials & Methods

## 📦 安装

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
# 自动检测并保存
fma check --save

# 或手动配置
fma config set meangs --conda-env my-meangs-env
fma config set novoplasty --conda-env my-novoplasty-env
```

## 🚀 快速开始

### 示例：线粒体基因组组装

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

# 3. 运行完整流程
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
    -o /path/to/result
```

## 📖 命令参考

### 主要命令

| 命令 | 说明 | 后端支持 |
|------|------|----------|
| `fma run` | 完整线粒体组装流程 | Snakemake |
| `fma fsb-all` | fastp → MultiQC → SPAdes → BUSCO | Python + Snakemake |
| `fma meangs` | MEANGS 种子检测 | Python + Snakemake |
| `fma novoplasty` | NOVOPlasty 组装 | Python + Snakemake |
| `fma getorganelle` | GetOrganelle 组装 | Python + Snakemake |
| `fma mitoz` | MitoZ 注释 | Python + Snakemake |
| `fma spades` | SPAdes 组装 | Python + Snakemake |
| `fma busco` | BUSCO 评估 | Python + Snakemake |
| `fma multiqc` | MultiQC 汇总 | Python + Snakemake |

### 链式命令

| 命令 | 流程 |
|------|------|
| `fma mg-nov` | MEANGS → NOVOPlasty |
| `fma mg-get` | MEANGS → GetOrganelle |
| `fma mg-nov-get` | MEANGS → NOVOPlasty → GetOrganelle |

### 配置命令

```bash
fma init                    # 创建 config.yaml
fma check                   # 检查工具状态
fma check --save            # 检查并保存配置
fma config show             # 显示工具配置
fma config set <tool>       # 设置工具路径
fma prepare tools           # 安装工具环境
fma prepare ncbitaxa        # 下载 NCBI 分类数据库
fma prepare organelle -a animal_mt  # 下载 GetOrganelle 数据库
```

## 🏗️ 流程架构

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

## 📁 输出结构

```
result/
├── sample1/
│   ├── 1.MEANGS/
│   │   └── animal_mt.meangs.fasta      # MEANGS 组装结果
│   ├── 2.NOVOPlasty/
│   │   └── sample1.novoplasty.fasta    # NOVOPlasty 组装结果
│   ├── 3.GetOrganelle/
│   │   └── animal_mt.get_organelle.fasta  # GetOrganelle 组装结果
│   └── 4.MitozAnnotate/
│       └── sample1.result/
│           ├── summary.txt              # 基因注释摘要
│           ├── cds/                     # 编码序列
│           ├── genes/                   # 基因注释
│           └── circos.png               # 环状基因组图
├── summary/
│   ├── summary_all.fasta                # 所有组装序列
│   └── summary_report.tsv               # 汇总表格
└── Materials_and_Methods.txt            # 双语 M&M 报告
```

## 📚 文档

- [Wiki](docs/WIKI.md) - 完整使用指南
- [User Manual](docs/manual.md) - 详细参数说明
- [INSTALL-v002](docs/INSTALL-v002.md) - 安装指南
- [Flowchart](docs/design/fastmito-v002-flowchart.svg) - 流程图

## 🔧 支持的生物

| 类群 | 数据库 | 遗传密码 |
|------|--------|----------|
| 动物 (默认) | `animal_mt` | 5 (无脊椎) / 2 (脊椎) |
| 真菌 | `fungus_mt` | 4 |
| 植物 | `embplant_mt` | 1 |
| 叶绿体 | `embplant_pt` | 11 |

## 🛠️ 使用的工具

- [MEANGS](https://github.com/YanCCscu/meangs) - 无参种子检测
- [NOVOPlasty](https://github.com/Edith1715/NOVOplasty) - 组装工具
- [GetOrganelle](https://github.com/Kinggerm/GetOrganelle) - 细胞器组装
- [SPAdes](https://github.com/ablab/spades) - 基因组组装
- [MitoZ](https://github.com/linzhi2013/MitoZ) - 线粒体注释
- [fastp](https://github.com/OpenGene/fastp) - 质量控制
- [BUSCO](https://busco.ezlab.org/) - 组装评估
- [MultiQC](https://multiqc.info/) - 报告汇总

## 📝 引用

如果你在研究中使用了 FastMitoAssembler，请引用以下文章：

**MEANGS**:
> Yan, C., et al. (2022). MEANGS: A reference-free mitochondrial genome assembly tool for high-throughput sequencing data. *Molecular Ecology Resources*.

**NOVOPlasty**:
> Dierckxsens, N., et al. (2017). NOVOPlasty: de novo assembly of organelle genomes from whole genome data. *Nucleic Acids Research*.

**GetOrganelle**:
> Jin, J.J., et al. (2020). GetOrganelle: a fast and versatile toolkit for accurate de novo assembly of organelle genomes. *Genome Biology*.

**MitoZ**:
> Meng, G., et al. (2019). MitoZ: a toolkit for animal mitochondrial genome assembly, annotation and visualization. *Nucleic Acids Research*.

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 👥 贡献者

- **Original idea:** Deyuan Yang
- **Original code:** Bioinformatics engineers at Novogene (诺禾元生物科技)
- **Maintenance & updates:** Managed by Deyuan Yang using [Claude Code](https://claude.ai/code)

## 🐛 问题反馈

如有问题或建议，请在 [GitHub Issues](https://github.com/deyuanyang92-dev/FastMitoAssembler/issues) 提交。
