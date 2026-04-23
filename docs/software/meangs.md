# MEANGS software research report

调研时间：2026-04-23 17:21:51 CST +0800
调研目标：为 FastMitoAssembler v002 的 MEANGS 独立批量运行、MEANGS -> NOVOPlasty、MEANGS -> GetOrganelle、MEANGS -> NOVOPlasty -> GetOrganelle 流程提供实现依据。

## 1. 软件定位

MEANGS 是线粒体基因组 seed-free 组装工具，核心思路是从 NGS reads 中识别线粒体相关 reads，先组装候选 scaffolds，再用 HMM/注释筛选候选 mitogenome。它适合作为 FastMitoAssembler 的动物线粒体候选 seed/候选 contig 发现器。

FastMitoAssembler 中不要把 MEANGS 输出直接等同于最终无污染结果。浅层测序和污染偏多数据中，MEANGS 可能发现污染来源线粒体；summary 必须保留来源、长度、topology 和参数。

## 2. 版本与官方来源

- 官方源码：<https://github.com/YanCCscu/MEANGS>
- 官方入口脚本：`meangs.py`
- seed 转换脚本：`tools/scaffold2seed.py`
- 论文：Song, Yan, Li. 2022. Briefings in Bioinformatics. DOI: `10.1093/bib/bbab538`
- Conda 来源：`yccscucib::meangs`
- 官方源码 `meangs.py` 中版本号：`VERSION="1.3.1"`
- FastMitoAssembler 当前 env：`FastMitoAssembler/FastMitoAssembler/smk/envs/meangs.yaml` 使用 `meangs`，未锁定精确版本。

版本判断：本报告以官方源码 `meangs.py` 的 `1.3.1` 为准。旧调研中的 `1.2.1` 只能作为历史记录，不应覆盖 v1.3.1 的参数和行为。

## 3. 本地 help 检查

Codex 当前环境检查：

```bash
command -v meangs.py
```

结果：Codex 环境未发现 `meangs.py`。

用户本地环境实测记录：

- 记录时间：2026-04-23 20:06:17 CST +0800
- 环境提示符：`(meangs)`
- 执行命令：`meangs.py -h`
- help 显示入口：`meangs.py [-h] [-1 FQ1] [-2 FQ2] [-o OUTBASE] [-t THREADS] [-i INSERT] [-q QUALITY] [-n NSAMPLE] [-s SEQSCAF] ...`
- 已确认参数：`-1/--fq1`、`-2/--fq2`、`-o/--outBase`、`-t/--threads`、`-i/--insert`、`-q/--quality`、`-n/--nsample`、`-s/--seqscaf`、`--species_class`、`--deepin`、`--clip`、`--keepIntMed`、`--keepMinLen`、`--skipassem`、`--skipqc`、`--skiphmm`、`--skipextend`、`--silence`。
- `--species_class` 可选值：`A-worms`、`Arthropoda`、`Bryozoa`、`Chordata`、`Echinodermata`、`Mollusca`、`Nematoda`、`N-worms`、`Porifera-sponges`。
- `-n/--nsample` help 说明：默认 `0`，表示保留全部 reads；示例中 `-n 2000000 --deepin` 表示使用输入 FASTQ 的前 2,000,000 条 reads 参与 deepin 流程。
- help 示例确认 quick mode 和 deepin mode：
  - `meangs.py --silence -1 1.fq.gz -2 2.fq.gz -o OutBase -t 16 -i 350`
  - `meangs.py -1 R1.fastq.gz -2 R2.fastq.gz -o A3 -t 16 -n 2000000 -i 300 --deepin`

正式部署后仍建议补充记录：

```bash
meangs.py --version
```

若 `--version` 不可用，记录 conda 包版本或源码 commit/tag。

## 4. 安装方式

Conda：

```bash
conda install -c yccscucib meangs
```

源码：

```bash
git clone https://github.com/YanCCscu/MEANGS.git
cd MEANGS
cd tools/assembler_v1.0/src
make
cp assembler ../../
```

FastMitoAssembler 建议：在 `smk/envs/meangs.yaml` 后续锁定可复现版本，并允许用户通过 `tool_envs.meangs.bin_dir` 或独立路径指向本地安装。

## 5. 核心命令

paired-end quick mode：

```bash
meangs.py --silence -1 sample_R1.fq.gz -2 sample_R2.fq.gz -o SampleA -t 16 -i 350
```

paired-end deepin mode：

```bash
meangs.py -1 sample_R1.fastq.gz -2 sample_R2.fastq.gz -o SampleA -t 16 -n 2000000 -i 300 --deepin
```

single-end mode（v1.3.1 支持）：

```bash
meangs.py --silence -1 sample.fq.gz -o SampleA -t 16 -i 350
```

## 6. 主要参数

- `-1, --fq1`：输入 R1 FASTQ；v1.3.1 中也可作为 single-end 输入。
- `-2, --fq2`：输入 R2 FASTQ；paired-end 时使用。
- `-o, --outBase`：输出目录名和文件前缀。
- `-t, --threads`：分析线程数。
- `-i, --insert`：library insert length，默认 `350`。
- `-q, --quality`：低质量碱基阈值，默认 `0.05`。
- `-n, --nsample`：抽取 reads 数，默认 `0`。
- `-s, --seqscaf`：指定 FASTA，只做注释。
- `--species_class`：类群，默认 `Chordata`；可选 `A-worms`、`Arthropoda`、`Bryozoa`、`Chordata`、`Echinodermata`、`Mollusca`、`Nematoda`、`N-worms`、`Porifera-sponges`。
- `--deepin`：深度组装模式。
- `--clip`：检测成环剪切点。
- `--keepIntMed`：保留中间文件。
- `--keepMinLen`：QC 后保留 reads 的长度阈值，默认 `30`。
- `--skipassem`、`--skipqc`、`--skiphmm`、`--skipextend`：跳过对应阶段。
- `--silence`：标准输出写入日志。

关键兼容点：MEANGS 使用 `--species_class`，不是 MitoZ 的 `--clade`。

## 7. `-n/--nsample` 源码行为

源码函数 `QC_Convert(fq, seqtk, outBase, nsample=0, PQ=0.01)` 定义：

- `nsample == 0`：保留全部 reads。
- `nsample != 0`：执行 `head -{nsample*2}` 作用于 QC 转换后的 FASTA 流。

因为 FASTA 每条记录 2 行，所以 `head -{nsample*2}` 等价于每个输入 FASTQ 文件保留前 `nsample` 条 FASTA 记录。paired-end 模式中 R1 和 R2 分别执行一次，因此 `-n 2000000` 表示 R1 前 2,000,000 条记录和 R2 前 2,000,000 条记录各自参与初步流程。

FastMitoAssembler 配置建议：

- 默认可保留 `meangs_reads: 2000000` 作为速度/内存折中。
- 允许用户设为 `0` 使用全部 reads。
- 文档必须说明它不是随机抽样，而是取输入文件前部 records。

## 8. 输入格式

- FASTQ/FASTQ.GZ/FASTA：源码断言允许 `fq.gz`、`fastq.gz`、`fq`、`fastq`、`fas`、`fa`、`fasta`。
- paired-end：`-1` 和 `-2` 成对输入。
- single-end：只传 `-1`。
- 多 library：源码允许 `-1` 和 `-2` 用逗号分隔列表，但 FastMitoAssembler v002 第一阶段建议先支持单 PE library。

## 9. 输出目录结构

`-o SampleA` 时，MEANGS 会在当前工作目录下创建 `SampleA/`，并把 `args.outBase` 改成 `SampleA/SampleA` 作为文件前缀。

典型输出：

```text
SampleA/
├── SampleA_1.input.fas
├── SampleA_2.input.fas
├── SampleA_1_hmmout
├── SampleA_1_hmmout_tbl
├── SampleA_1_hmmout_tbl_sorted.gff
├── SampleA_2_hmmout
├── SampleA_2_hmmout_tbl
├── SampleA_2_hmmout_tbl_sorted.gff
├── SampleA_MatchReadNames
├── SampleA_matched_SampleA_1.input.fas
├── SampleA_matched_SampleA_2.input.fas
├── paired.fa
├── unpaired.fa
├── SampleA_scaffolds.fa
├── SampleA_detected_mito.fas
├── SampleA_deep_scaffolds.fa
├── SampleA_deep_detected_mito.fas
└── SampleA_SE_YYYY-MM-DD.log
```

实际文件会受 `--deepin`、`--skip*`、`--keepIntMed` 影响。若 `--keepIntMed` 未开启，部分中间 FASTA 会被删除。

## 10. `scaffold_seeds.fas` 格式与并行风险

deepin 模式中源码逻辑：

```python
mitoSeeds = 'scaffold_seeds.fas'
command = "python tools/scaffold2seed.py simple_final_file > scaffold_seeds.fas"
runASSEMBLY(..., SeedSeq=mitoSeeds, deepin=True)
```

关键结论：

- `scaffold_seeds.fas` 写在当前工作目录，不在 `SampleA/` 目录内。
- 批量并行运行多个样本时，如果共享同一个 CWD，会互相覆盖 `scaffold_seeds.fas`。
- FastMitoAssembler 必须为每个样本使用隔离工作目录，或者在 rule 中进入样本专属目录运行 MEANGS。

`tools/scaffold2seed.py` 行为：

- 输入：初筛 `*_detected_mito.fas`。
- 输出：标准 FASTA，写到 stdout。
- 默认最短片段长度：`150` bp。
- 正则：`[^ATGCatgc]`，任何非 ATGC 字符都会作为切分点。
- 如果序列没有 N/非 ATGC：输出原 header 和原序列。
- 如果序列含 N/非 ATGC：切分为多个片段，长度 >=150 的片段输出；header 变成 `{原title}_{片段起点}`。

## 11. FastMitoAssembler 集成策略

- `fma meangs`：独立批量运行，输出候选线粒体 FASTA。
- `fma mg-nov`：MEANGS deepin FASTA 作为 NOVOPlasty seed。
- `fma mg-get`：MEANGS FASTA 作为 GetOrganelle `-s` seed。
- `fma mg-nov-get`：MEANGS -> NOVOPlasty -> GetOrganelle。
- summary 优先收集 `SampleA_deep_detected_mito.fas`；无 deepin 时兼容 `SampleA_detected_mito.fas` 或 `mito.fasta`。
- summary header 中 `topology` 默认 `unknown`；只有 `--clip` 结果能可靠解析时才标记 circular。

## 12. 风险与待验证

- 本地安装后必须运行 `meangs.py -h` 验证 conda 包是否与官方源码 v1.3.1 一致。
- `scaffold_seeds.fas` CWD 覆盖风险必须通过 Snakemake per-sample workdir 避免。
- `-n` 不是随机抽样，输入 FASTQ 顺序可能影响结果。
- MEANGS 主要面向动物 mitogenome，不适合 nr 组装。
- 污染数据中 MEANGS 候选结果必须进入 QC/summary，不应自动作为最终结果。

## 记录

- 调研日期：2026-04-23 Asia/Shanghai
- 调研时间：2026-04-23 17:21:51 CST +0800
- 软件版本：MEANGS 1.3.1
- 版本依据：官方 `meangs.py` 源码 `VERSION="1.3.1"` 和 argparse 参数
- 源码出处：<https://github.com/YanCCscu/MEANGS>
- 本地 help：用户已提供 `meangs.py -h` 实测输出，记录时间 2026-04-23 20:06:17 CST +0800；Codex 当前环境未安装 `meangs.py`
