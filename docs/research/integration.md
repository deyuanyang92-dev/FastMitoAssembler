# FastMitoAssembler 集成调研记录

调研日期：2026-04-23

## 当前项目状态

当前代码已有完整链式 Snakemake 流程：

```text
MEANGS -> NOVOPlasty -> GetOrganelle -> MitoZ annotate -> Materials & Methods report
```

主要入口仍是 `fma run`，注册于 `FastMitoAssembler/FastMitoAssembler/bin/main.py`。核心 Snakemake 文件是 `FastMitoAssembler/FastMitoAssembler/smk/main.smk`。

当前已存在能力：

- 自动识别样本：`--suffix_fq` 支持多个 R1/R2 后缀模式。
- 工具环境隔离：MEANGS、NOVOPlasty、GetOrganelle、MitoZ 各有独立 conda env YAML。
- `seed_input`：可把单个 FASTA/GenBank 转成 MEANGS seed 输出。
- NOVOPlasty config 自动生成。
- GetOrganelle 部分参数扁平透传。
- MitoZ 使用 `annotate --fastafiles` 注释 GetOrganelle 结果。
- `materials_and_methods.md` 会检测工具版本并写入报告。

当前缺口：

- 没有独立 `fma meangs/novoplasty/getorganelle/mitoz` 子命令。
- 没有组合命令 `mg-nov`、`mg-get`、`mg-nov-get`。
- Snakemake 默认 `rule all` 固定跑到 MitoZ，缺少按阶段 target 分发。
- GetOrganelle 当前固定以 NOVOPlasty FASTA 为 `-s`，不支持独立或 MEANGS seed。
- `genes` 配置存在但未传入 GetOrganelle。
- 没有统一 summary FASTA 和 summary report。
- multi-FASTA by-sample seed 尚未实现。

## 版本策略

建议第一阶段锁定版本：

- MEANGS：`1.2.1`
- NOVOPlasty：`4.3.5`
- GetOrganelle：暂保留项目当前 `1.7.7.0`，另记录最新 `1.7.7.1`
- MitoZ：`3.6`

环境文件建议后续改为精确版本，避免不同机器解析到不同版本：

```yaml
meangs=1.2.1
novoplasty=4.3.5
getorganelle=1.7.7.0
mitoz=3.6
```

如果用户使用 `fma config set` 指向外部环境，则实际版本以运行时检测为准。

## 子命令设计

保留现有：

```bash
fma run
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
fma clean
```

阶段映射：

- `run`：`meangs,novoplasty,getorganelle,mitoz`
- `meangs`：`meangs`
- `novoplasty`：`novoplasty`，需要已有 seed 或用户 seed；默认不隐式跑 MEANGS
- `getorganelle`：`getorganelle`，无 seed 时用 GetOrganelle 默认数据库
- `mitoz`：`mitoz`，输入来自 `--assembly_fasta` 或 summary/GetOrganelle 结果
- `mg-nov`：`meangs,novoplasty`
- `mg-get`：`meangs,getorganelle`
- `mg-nov-get`：`meangs,novoplasty,getorganelle`

## seed 与参考输入规则

统一参数：

```bash
--seed_input PATH
--seed_mode single|by-sample
--genes PATH
--ref_gb PATH
```

规则：

- `single` 为默认，保持旧行为。
- `by-sample` 时，FASTA header 第一个 token 必须等于 sample 名。
- by-sample 缺失样本直接报错，不能自动取第一条。
- `--ref_gb` 可在 GetOrganelle 中派生 seed FASTA 和 `--genes`，参考 Temp_scripts 的 `batch_getorganelle.py`。
- `-F anonym` 必须同时有 seed 和 label，否则报错。

## summary FASTA 规范

输出目录：

```text
result/summary/
```

单样本单工具：

```text
result/summary/{sample}.{tool}.fasta
```

组合流程：

```text
result/summary/{sample}.{pipeline}.fasta
```

全局合并：

```text
result/summary/summary_all.fasta
result/summary/summary_report.tsv
```

FASTA header：

```text
>{sample}|tool={tool}|pipeline={pipeline}|locus={mt|nr|unknown}|idx={n}|topology={circular|linear|unknown}
```

默认收集规则：

- MEANGS：收集 `{sample}_deep_detected_mito.fas` 或兼容 non-deepin 输出。
- NOVOPlasty：收集 `{sample}.novoplasty.fasta`。
- GetOrganelle：默认只收集非空 `*.path_sequence.fasta` 派生的标准输出。
- MitoZ：不作为 assembly summary 来源；MitoZ 的输出进入 annotation report。
- 组合流程：只汇总最后一个有效 assembler 的结果。

## 污染与失败处理

污染或浅层数据下，不应把“命令退出码为 0”当作“结果可信”。

建议 report 至少记录：

- sample
- pipeline
- tool
- input FASTQ
- output FASTA
- sequence count
- sequence length
- topology
- status：`OK|INCOMPLETE|FAILED|SKIPPED`
- reason

判定规则：

- GetOrganelle 无 `path_sequence.fasta`：`INCOMPLETE`。
- graph-only 结果默认不进 final summary。
- NOVOPlasty 输出为空或长度不在期望范围：`INCOMPLETE`。
- MEANGS 无目标 FASTA：`FAILED`。
- MitoZ annotate 失败不删除输入 FASTA，保留日志。

## clean 规则

默认保留可复核产物：

- MEANGS：标准 seed FASTA 和日志
- NOVOPlasty：`config.txt`、标准 FASTA、log
- GetOrganelle：`*.path_sequence.fasta`、`*.fastg`、`*.gfa`、`*.selected_graph.gfa`、`get_org.log.txt`
- MitoZ：`*.gbf`、`*.sqn`、`summary.txt`、`circos.png`
- 所有 `materials_and_methods.md`

默认只清理 `OK` 样本的大型中间文件。`INCOMPLETE` 和 `FAILED` 样本保留中间文件，便于排错。

## 第一阶段实现边界

先实现：

- 子命令化阶段控制
- seed single/by-sample
- GetOrganelle 独立与组合输入
- summary FASTA/report
- MitoZ annotate 使用外部 FASTA

暂缓：

- 完整复制 Temp_scripts 的 GenBank metadata 后处理
- MitoZ `all`/assembly 高级模式
- 多 library 输入
- single-end 输入
- 图形化人工 Bandage 交互
