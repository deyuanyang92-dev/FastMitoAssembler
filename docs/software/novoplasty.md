# NOVOPlasty software research report

调研时间：2026-04-23 17:21:51 CST +0800
调研目标：为 FastMitoAssembler v002 的 NOVOPlasty 独立批量运行、MEANGS -> NOVOPlasty、MEANGS -> NOVOPlasty -> GetOrganelle 流程提供配置文件和 seed 管理依据。

## 1. 软件定位

NOVOPlasty 是短环状基因组 de novo assembler 和 heteroplasmy/variance caller。它不以大量命令行参数驱动，而是通过 per-sample `config.txt` 控制运行。FastMitoAssembler 的核心任务是为每个样本生成可复核配置文件、管理 seed、隔离输出目录，并收集标准化 FASTA。

## 2. 版本与官方来源

- 官方源码：<https://github.com/ndierckx/NOVOPlasty>
- 官方 release：`NOVOPlasty4.3.5`，2024-02-04。
- 官方脚本名：`NOVOPlasty4.3.5.pl`
- README 当前更新日志仍写 `version 4.3.3`，但 GitHub release 和脚本文件名指向 `4.3.5`。
- Bioconda 包：`novoplasty`
- FastMitoAssembler 当前 env：`FastMitoAssembler/FastMitoAssembler/smk/envs/novoplasty.yaml` 使用 `novoplasty`，未锁定精确版本。

版本判断：以 GitHub release `NOVOPlasty4.3.5` 和官方脚本名为准。

## 3. 本地 help 检查

当前环境检查：

```bash
command -v NOVOPlasty4.3.5.pl
command -v NOVOPlasty.pl
```

结果：未发现 NOVOPlasty 命令。本报告依据官方 README、release 和配置文件说明。

## 4. 安装方式

Bioconda：

```bash
conda install -c bioconda novoplasty
```

源码/脚本：

```bash
git clone https://github.com/ndierckx/NOVOPlasty.git
perl NOVOPlasty4.3.5.pl -c config.txt
```

FastMitoAssembler 建议：后续锁定 `novoplasty=4.3.5`，同时允许用户配置 `script_path` 指向本地 `NOVOPlasty4.3.5.pl`。

## 5. 核心命令

```bash
NOVOPlasty4.3.5.pl -c config.txt
```

或：

```bash
perl NOVOPlasty4.3.5.pl -c config.txt
```

## 6. 配置文件字段

NOVOPlasty 要求配置文件结构固定，并且每个参数必须在一行内，`=` 后有空格。

Project：

- `Project name`：项目/样本名，用于输出文件。
- `Type`：`chloro`、`mito`、`mito_plant`。
- `Genome Range`：预期大小范围，如 `12000-22000`。
- `K-mer`：默认 `33`；低覆盖或 seed 问题时可降到 `21-39`。
- `Max memory`：GB 数值，不带单位；可触发自动降采样。
- `Extended log`：是否输出详细日志。
- `Save assembled reads`：是否保存参与组装 reads。
- `Seed Input`：seed FASTA。
- `Extend seed directly`：只在 seed 来自同一样本且没有 mismatch 风险时使用。
- `Reference sequence`：可选参考。
- `Variance detection`：需要 reference。
- `Chloroplast sequence`：`mito_plant` 模式需要。

Dataset：

- `Read Length`
- `Insert size`
- `Platform`：`illumina` 或 `ion`。
- `Single/Paired`：README 说明目前只支持 paired-end。
- `Combined reads`
- `Forward reads`
- `Reverse reads`
- `Store Hash`

Optional：

- `Insert size auto`：默认 `yes`。
- `Use Quality Scores`：默认 `no`。
- `Reduce ambigious N's`
- `Output path`：批量运行必须显式设置，避免输出混在当前目录。

## 7. Seed 输入策略

官方 seed 说明：

- 可用来自目标 organelle genome 的单 read。
- 可用同种或近缘种 organelle sequence。
- 无近缘序列时可用较远物种完整 organelle sequence。
- 格式为标准 FASTA，第一行 `>Id_sequence`。

FastMitoAssembler 支持策略：

- `seed_mode=single`：所有样本共用一个 seed。
- `seed_mode=by-sample`：multi-FASTA 中 header 第一个 token 必须匹配 sample basename。
- `seed_missing=fail`：默认缺失报错，避免静默使用错误 seed。
- `mg-nov` 和 `mg-nov-get` 默认使用 MEANGS 输出作为 seed。

每个样本建议写出：

```text
result/{sample}/2.NOVOPlasty/{sample}.seed.fasta
result/{sample}/2.NOVOPlasty/config.txt
```

## 8. 输入格式

- Reads：Illumina FASTQ/FASTA，可未压缩，也可 gz/bz2 压缩。
- Library：官方说明 multiple libraries 尚不支持；FastMitoAssembler 第一阶段应按单 PE library 实现。
- Seed：标准 FASTA。
- Reference：可选 FASTA。

官方明确建议：不要 filter 或 quality trim reads，只去接头。这支持 FastMitoAssembler 的 fastp adapter-only 默认策略。

## 9. 输出文件结构

输出受 `Project name` 和 `Output path` 控制。批量运行时必须设置 `Output path`。

FastMitoAssembler 标准结构：

```text
result/{sample}/2.NOVOPlasty/
├── config.txt
├── {sample}.seed.fasta
├── {sample}.log 或 NOVOPlasty log
├── Contigs_*.fasta / Circularized_*.fasta / Project-name related FASTA
└── {sample}.novoplasty.fasta
```

具体原始 FASTA 名称可能随版本和结果类型变化。FastMitoAssembler 应保留原始输出，同时生成标准化：

```text
result/{sample}/2.NOVOPlasty/{sample}.novoplasty.fasta
```

summary 不能只靠文件名判断 topology，应解析 header/log；无法判断写 `topology=unknown`。

## 10. FastMitoAssembler 集成策略

- `fma novoplasty`：独立批量运行，必须有用户 seed。
- `fma mg-nov`：MEANGS -> NOVOPlasty。
- `fma mg-nov-get`：NOVOPlasty 输出作为 GetOrganelle seed 或候选输入。
- 每个样本保留 config 和 seed 文件，便于复核。
- 不把 NOVOPlasty 输出自动视为污染已排除结果；进入 summary 前记录长度、来源、拓扑和输出路径。

## 11. 风险与待验证

- Bioconda 包是否为 4.3.5 需要本地安装后确认。
- README 示例脚本名可能旧于 release，文档应提示以本地实际脚本为准。
- `Type=mito` 当前适合动物线粒体；植物线粒体需要 `mito_plant` 和 chloroplast sequence 支持。
- 输出 header/topology 需真实样本验证。

## 记录

- 调研日期：2026-04-23 Asia/Shanghai
- 调研时间：2026-04-23 17:21:51 CST +0800
- 软件版本：NOVOPlasty 4.3.5
- 版本依据：GitHub release `NOVOPlasty4.3.5` 和官方脚本名 `NOVOPlasty4.3.5.pl`
- 源码出处：<https://github.com/ndierckx/NOVOPlasty>
- 本地 help：未执行成功，当前环境未安装 NOVOPlasty 命令
