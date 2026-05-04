# 一键化流程 (fsb-all) 使用指南

## 概述

`fma fsb-all` 是一个一键化命令，用于运行完整的组装评估流程：

```
fastp (质控) → MultiQC (汇总) → SPAdes (组装) → BUSCO (评估)
```

该命令同时支持 **Python** 和 **Snakemake** 两种后端。

---

## 快速开始

### Python 后端 (推荐)

```bash
fma fsb-all --backend python \
    -r /path/to/reads \
    -o /path/to/result \
    --mode meta \
    -t 16 -m 32
```

### Snakemake 后端

```bash
fma fsb-all --backend snakemake \
    -r /path/to/reads \
    -o /path/to/result \
    --mode meta
```

---

## 参数详解

### 必需参数

| 参数 | 说明 |
|------|------|
| `-r, --reads-dir` | 输入 FASTQ 文件目录 |
| `-o, --result-dir` | 输出目录 |

### 后端选择

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--backend` | `python` | 后端类型: `python` 或 `snakemake` |

### 工具参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--mode` | `meta` | SPAdes 组装模式 |
| `--fastp-mode` | `adapter_only` | fastp 质控模式 |
| `--lineage` | `metazoa_odb10` | BUSCO lineage 数据集 |

### 资源参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-t, --threads` | `16` | 每个任务使用的线程数 |
| `-m, --memory` | `32` | 内存限制 (GB) |
| `--parallel-jobs` | `3` | Python 后端并行任务数 |

### 其他参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--force` | `False` | 强制重跑已完成的样本 |

---

## SPAdes 组装模式

| 模式 | 说明 | 参数 | 适用场景 |
|------|------|------|----------|
| `default` | 通用组装 | `--only-assembler --careful` | 标准 WGS 数据 |
| `isolate` | 细菌分离株 | `--isolate` | 高覆盖度细菌 |
| `meta` | 宏基因组 | `--meta` | 复杂微生物群落 |
| `rna` | 转录组 | `--rna` | RNA-seq 数据 |
| `plasmid` | 质粒 | `--plasmid` | 质粒检测 |
| `metaviral` | 病毒 | `--metaviral` | 宏基因组病毒 |
| `metaplasmid` | 宏质粒 | `--metaplasmid` | 宏基因组质粒 |
| `sc` | 单细胞 | `--sc` | 单细胞 MDA 数据 |
| `rnaviral` | RNA 病毒 | `--rnaviral` | RNA 病毒组装 |
| `shallow` | 低深度 | `--meta -k 21,33,55` | 低覆盖度数据 |

---

## fastp 质控模式

| 模式 | 说明 | 关键参数 |
|------|------|----------|
| `adapter_only` | 仅去接头 | `--detect_adapter_for_pe -Q -L` |
| `shallow_data` | 最大化保留 | `--n_base_limit 10 --disable_low_complexity_filter` |
| `transcriptome` | RNA-seq | `--trim_poly_x --cut_front --cut_tail` |
| `full_qc` | 标准 WGS | `--qualified_quality_phred 20` |

### fastp 模式详解

**adapter_only** (推荐线粒体组装):
- 仅去除接头序列
- 保留所有质量过滤
- 适合后续 MEANGS/GetOrganelle 组装

**shallow_data** (低深度数据):
- 最大化保留 reads
- 允许更多 N 碱基
- 禁用低复杂度过滤
- 适合古 DNA 或低覆盖度样本

**transcriptome** (RNA-seq):
- Poly-A/T 尾修剪
- 质量修剪
- 适合转录组数据

**full_qc** (标准 WGS):
- 完整质量控制
- 质量过滤
- 长度过滤
- 适合标准全基因组测序

---

## BUSCO Lineage 选择

### 常用 Lineage

| Lineage | 说明 | 物种示例 |
|---------|------|----------|
| `metazoa_odb10` | 后生动物 | 动物 |
| `insecta_odb10` | 昆虫 | 果蝇、蜜蜂 |
| `vertebrata_odb10` | 脊椎动物 | 人、小鼠 |
| `actinopterygii_odb10` | 辐鳍鱼 | 斑马鱼 |
| `aves_odb10` | 鸟类 | 鸡、鸽子 |
| `mammalia_odb10` | 哺乳动物 | 人、小鼠 |
| `fungi_odb10` | 真菌 | 酵母 |
| `bacteria_odb10` | 细菌 | 大肠杆菌 |

### 如何选择

1. **确定分类层级**: 越具体的 lineage 评估越准确
2. **检查可用性**: 访问 [BUSCO 网站](https://busco.ezlab.org/) 查看可用 lineage
3. **下载离线数据** (可选):
   ```bash
   busco --download_path /path/to/busco_data --download insecta_odb10
   ```

---

## 输出结构

```
result/
├── fastp/                         # fastp 质控结果
│   ├── sample1/
│   │   ├── sample1_1.clean.fq.gz  # R1 输出
│   │   ├── sample1_2.clean.fq.gz  # R2 输出
│   │   ├── fastp.json             # JSON 报告
│   │   ├── fastp.html             # HTML 报告
│   │   └── fastp.log              # 运行日志
│   ├── sample2/
│   │   └── ...
│   ├── finished_fastp.txt         # 成功样本列表
│   └── unfinished_fastp.txt       # 失败样本列表
│
├── multiqc/                       # MultiQC 汇总报告
│   ├── multiqc_report.html        # HTML 报告
│   └── multiqc_data/              # 数据目录
│
├── spades/                        # SPAdes 组装结果
│   ├── sample1/
│   │   ├── contigs.fasta          # Contigs 序列
│   │   ├── scaffolds.fasta        # Scaffold 序列
│   │   ├── assembly_graph.fastg   # 组装图
│   │   ├── params.txt             # 参数记录
│   │   └── spades.log             # 运行日志
│   ├── sample2/
│   │   └── ...
│   └── spades_status.txt          # 状态汇总
│
├── busco/                         # BUSCO 评估结果
│   ├── sample1/
│   │   ├── short_summary.txt      # 摘要报告
│   │   ├── busco.log              # 运行日志
│   │   └── run_sample1/           # 详细结果
│   │       ├── busco_summary.txt
│   │       ├── full_table.tsv
│   │       └── missing_busco_list.tsv
│   ├── sample2/
│   │   └── ...
│   └── busco_status.txt           # 状态汇总
│
└── fsb_all.log                    # 流程总日志
```

---

## 使用示例

### 示例 1: 宏基因组组装

```bash
fma fsb-all --backend python \
    -r /data/metagenome_reads \
    -o /results/metagenome \
    --mode meta \
    --lineage bacteria_odb10 \
    -t 32 -m 64 \
    --parallel-jobs 4
```

### 示例 2: 转录组组装

```bash
fma fsb-all --backend python \
    -r /data/rnaseq_reads \
    -o /results/transcriptome \
    --mode rna \
    --fastp-mode transcriptome \
    --lineage metazoa_odb10 \
    -t 16 -m 32
```

### 示例 3: 低深度数据

```bash
fma fsb-all --backend python \
    -r /data/low_coverage_reads \
    -o /results/shallow \
    --mode shallow \
    --fastp-mode shallow_data \
    --lineage insecta_odb10 \
    -t 8 -m 16
```

### 示例 4: Snakemake 后端

```bash
fma fsb-all --backend snakemake \
    -r /data/reads \
    -o /results/snakemake \
    --mode meta \
    --lineage metazoa_odb10 \
    --cores 48
```

---

## 断点续跑

`fma fsb-all` 支持自动断点续跑：

1. **自动检测**: 每个工具会检查输出目录中已完成的样本
2. **跳过已完成**: 已成功完成的样本会自动跳过
3. **续跑中断**: 中断的任务会从中断点继续

### 强制重跑

```bash
fma fsb-all --backend python \
    -r /data/reads \
    -o /results \
    --force  # 强制重跑所有样本
```

---

## 常见问题

### Q: 如何选择 SPAdes 模式？

**A**:
- 不确定 → `default` 或 `meta`
- 宏基因组 → `meta`
- 细菌分离株 → `isolate`
- RNA-seq → `rna`
- 低深度 → `shallow`

### Q: 如何选择 BUSCO lineage？

**A**:
- 动物 → `metazoa_odb10`
- 昆虫 → `insecta_odb10`
- 脊椎动物 → `vertebrata_odb10`
- 细菌 → `bacteria_odb10`
- 真菌 → `fungi_odb10`

### Q: Python vs Snakemake 后端？

**A**:
- **Python**: 轻量级，无需 Snakemake，适合简单批量处理
- **Snakemake**: 依赖管理更完善，适合复杂流程和 HPC 集群

### Q: 内存不足怎么办？

**A**: 减少并行任务数和线程数：
```bash
fma fsb-all --backend python \
    -r /data/reads -o /results \
    -t 8 -m 16 \
    --parallel-jobs 1  # 串行执行
```

### Q: 如何查看进度？

**A**: 查看日志文件：
```bash
tail -f result/fsb_all.log
```

或查看状态文件：
```bash
cat result/fastp/finished_fastp.txt
cat result/spades/spades_status.txt
```

---

## 性能优化

### 1. 调整并行任务数

```bash
# 高性能服务器
--parallel-jobs 6 -t 16 -m 32

# 普通服务器
--parallel-jobs 3 -t 8 -m 16

# 低配置机器
--parallel-jobs 1 -t 4 -m 8
```

### 2. 使用更快的存储

将输出目录放在 SSD 或高速存储上：
```bash
fma fsb-all -r /data/reads -o /ssd/results ...
```

### 3. 预先准备环境

确保所有工具环境已配置：
```bash
fma check --save
```

---

## 下一步

完成 `fsb-all` 后，可以：

1. **查看 MultiQC 报告**: `open result/multiqc/multiqc_report.html`
2. **检查 BUSCO 结果**: `cat result/busco/sample1/short_summary.txt`
3. **运行线粒体组装**: 使用 SPAdes contigs 作为 MEANGS 种子
