# MitoZ software research report

调研时间：2026-04-23 17:21:51 CST +0800
调研目标：为 FastMitoAssembler v002 的 MitoZ 批量注释、summary FASTA 注释输入和可选 assembly passthrough 提供实现依据。

## 1. 软件定位

MitoZ 是动物线粒体基因组 assembly、annotation 和 visualization 工具，提供 `all`、`annotate`、`assemble`、`findmitoscaf`、`visualize` 等子命令。FastMitoAssembler 中 MitoZ 应默认作为 annotation/visualization 后端，而不是默认可信组装来源。

用户已指出 MitoZ 自身寻找 `mtcontigs.fasta` 或候选线粒体 contig 的算法在一些情况下容易失败；因此 FastMitoAssembler 的核心路径应使用 MEANGS/NOVOPlasty/GetOrganelle 的候选 FASTA，再交给 MitoZ annotate。

## 2. 版本与官方来源

- 官方源码：<https://github.com/linzhi2013/MitoZ>
- 官方 Wiki：<https://github.com/linzhi2013/MitoZ/wiki>
- 官方 Tutorial：<https://github.com/linzhi2013/MitoZ/wiki/Tutorial>
- 官方 release：`MitoZ 3.6`，2023-04-14。
- 官方 README 推荐升级到 3.6，因为 3.5 存在 known bugs。
- FastMitoAssembler 当前 env：`FastMitoAssembler/FastMitoAssembler/smk/envs/mitoz.yaml` 使用 `mitoz>=3.6`。

版本判断：以官方 release 和 README 推荐版本 `3.6` 为准。

## 3. 本地 help 检查

Codex 当前环境检查：

```bash
command -v mitoz
```

结果：Codex 环境未发现 `mitoz` 命令。

用户本地环境实测记录：

- 记录时间：2026-04-23 20:06:17 CST +0800
- 环境提示符：`(mitoz3.6)`
- 执行命令：`mitoz -h`
- help 显示版本：`MitoZ 3.6`
- 顶层子命令：`filter`、`assemble`、`findmitoscaf`、`annotate`、`visualize`、`all`。
- 执行命令：`mitoz annotate -h`
- `mitoz annotate` 必需参数：`--outprefix`、`--fastafiles`。
- `mitoz annotate` 常用参数：`--workdir`、`--thread_number`、`--fq1`、`--fq2`、`--profiles_dir`、`--species_name`、`--template_sbt`、`--genetic_code`、`--clade`。
- `mitoz annotate --clade` 可选值：`Chordata`、`Arthropoda`、`Echinodermata`、`Annelida-segmented-worms`、`Bryozoa`、`Mollusca`、`Nematoda`、`Nemertea-ribbon-worms`、`Porifera-sponges`。
- `--fastafiles` help 明确要求：sequence id 长度应 `<=13` 字符；每条序列 header 应包含 `topology=linear` 或 `topology=circular`，否则默认按 `topology=linear` 处理。

正式部署后仍建议补充记录：

```bash
mitoz all -h
mitoz assemble -h
mitoz findmitoscaf -h
mitoz visualize -h
```

## 4. 安装方式

官方支持 Docker、Singularity/Apptainer、conda-pack、conda、source code。FastMitoAssembler 推荐独立 conda 或用户已有环境：

```bash
conda install -c bioconda mitoz=3.6
```

运行前建议使用官方 test dataset 验证，尤其是 WSL 环境中 `cmsearch`/tRNA 注释问题。

## 5. 子命令定位

- `mitoz all`：从 raw FASTQ 一键过滤、组装、注释、可视化。
- `mitoz assemble`：组装阶段。
- `mitoz findmitoscaf`：从组装结果筛选候选线粒体 scaffold。
- `mitoz annotate`：对给定 FASTA 注释。
- `mitoz visualize`：可视化注释结果。

FastMitoAssembler 默认只使用 `mitoz annotate`。`all`/assembly 只能作为高级 passthrough，不能作为默认可信组装来源。

## 6. 核心命令

官方 `all` 示例：

```bash
mitoz all \
  --outprefix DM01 \
  --thread_number 16 \
  --clade Chordata \
  --genetic_code 2 \
  --species_name "Homo sapiens" \
  --fq1 DM01_1.fastq.gz \
  --fq2 DM01_2.fastq.gz \
  --fastq_read_length 151 \
  --data_size_for_mt_assembly 3,0 \
  --assembler megahit \
  --kmers_megahit 59 79 99 \
  --memory 50 \
  --requiring_taxa Chordata
```

FastMitoAssembler 推荐 annotate：

```bash
mitoz annotate \
  --thread_number 16 \
  --outprefix SampleA \
  --fastafiles SampleA.summary.fasta \
  --fq1 SampleA_R1.clean.fq.gz \
  --fq2 SampleA_R2.clean.fq.gz \
  --species_name "SampleA" \
  --genetic_code 5 \
  --clade Arthropoda
```

## 7. 主要参数

- `--outprefix`：输出前缀。
- `--thread_number`：线程数。
- `--clade`：动物类群，MitoZ 自身参数，不同于 MEANGS `--species_class`。
- `--genetic_code`：线粒体遗传密码。
- `--species_name`：GenBank/annotation 中的物种名。
- `--fq1` / `--fq2`：FASTQ。
- `--fastafiles`：待注释 FASTA；FastMitoAssembler 的核心输入。
- `--fastq_read_length`：reads 长度。
- `--data_size_for_mt_assembly`：assembly 使用数据量，`all` 模式相关。
- `--assembler`：如 `megahit`。
- `--kmers_megahit`：MEGAHIT k-mer。
- `--memory`：内存。
- `--requiring_taxa`：目标分类过滤。

## 8. 输入格式

- `mitoz all`：raw FASTQ，paired-end 或 single-end；SE 不适合 `--assembler spades`。
- `mitoz annotate`：FASTA，通过 `--fastafiles` 输入；可附带 FASTQ。
- FastMitoAssembler summary FASTA 用于 MitoZ annotate 时必须生成 MitoZ 兼容 header：sequence id 长度 `<=13` 字符，并显式携带 `topology=circular` 或 `topology=linear`。
- FastMitoAssembler 内部 summary 可记录 `topology=unknown`；但交给 MitoZ 前必须转换为 `topology=linear` 或 `topology=circular`，否则 MitoZ 会按 linear 处理。

## 9. 输出文件结构

官方 `all` 输出通常包括：

```text
workdir/
├── clean_data/
├── mt_assembly/
├── mt_annotation/
├── {outprefix}.result/
└── mitoz.log
```

annotation 关键输出：

- `.gbf`：GenBank annotation。
- `.cds.fasta`
- `.cds_translation.fasta`
- `.gene.fasta`
- `.rrna.fasta`
- `.trna.fasta`
- `summary.txt`：包含长度、Circularity、相关物种、基因坐标等。
- visualization 文件，例如 circos 图。

## 10. 官方使用警告

官方 README 2024-11-06 提醒：使用过多 raw data，例如 12 Gbp，可能导致非成环 mitogenome；较小数据量，例如 0.3 Gbp，有时能得到 circular mitogenome，并且计算更快。

这支持 FastMitoAssembler 的设计：不要默认把全部 reads 交给 MitoZ assembly；优先使用上游 assembler 的候选 FASTA 做 annotate。

## 11. FastMitoAssembler 集成策略

- `fma mitoz` 默认调用 `mitoz annotate`。
- 输入优先级：用户 `assembly_fasta` > summary FASTA > GetOrganelle FASTA > NOVOPlasty FASTA。
- 多记录 FASTA 如造成 MitoZ header/LOCUS 问题，应拆成单记录逐条注释；每条记录进入 MitoZ 前都必须使用短 ID 和显式 topology。
- MitoZ 输出进入 annotation report，不作为 assembly summary FASTA 默认来源。
- `summary.txt` 中 `Circularity`、基因数量、PCG/rRNA/tRNA 完整性应进入 summary TSV。
- MitoZ 不用于 nr 注释。

## 12. 风险与待验证

- 本地安装后必须运行 `mitoz annotate -h` 确认 3.6 参数。
- WSL 环境可能需要重新编译 `cmsearch` 才能正常 tRNA annotation。
- `--fastafiles` 对多记录 FASTA 的兼容性必须真实测试。
- `mtcontigs.fasta` 和 MitoZ assembly 候选算法不能作为 FastMitoAssembler 默认可信来源。

## 记录

- 调研日期：2026-04-23 Asia/Shanghai
- 调研时间：2026-04-23 17:21:51 CST +0800
- 软件版本：MitoZ 3.6
- 版本依据：GitHub release、README 3.6 推荐和 Wiki Tutorial
- 源码出处：<https://github.com/linzhi2013/MitoZ>
- 官方 Tutorial：<https://github.com/linzhi2013/MitoZ/wiki/Tutorial>
- 本地 help：用户已提供 `mitoz -h` 和 `mitoz annotate -h` 实测输出，记录时间 2026-04-23 20:06:17 CST +0800；Codex 当前环境未安装 `mitoz`
