# FastMitoAssembler 设计方案专家评审

调研日期：2026-04-23

## 总体结论

当前设计方向是合理的，尤其是“保留粗暴高成功率一键流程，同时拆成可独立运行和可汇总复核的工具箱”。但方案还需要从“能跑通”升级到“能证明结果可信”。

核心优化方向：

- 不只收集 FASTA，还要建立候选序列质量证据。
- 增加污染识别和分类验证。
- 保留多工具、多流程候选结果，避免过早覆盖。
- 对每条候选序列记录工具版本、参数、来源路径和判断状态。

建议把 FastMitoAssembler 从一个 batch wrapper 进一步设计为面向浅层测序的可复核细胞器组装框架。

## 专家一：细胞器组装流程专家

### 点评

保留 `MEANGS -> NOVOPlasty -> GetOrganelle -> MitoZ` 是有价值的。MEANGS 适合动物线粒体 seed-free 初筛；NOVOPlasty 适合 seed-and-extend 快速闭环；GetOrganelle 适合 genome skimming 场景下的 reads 招募、de novo assembly、assembly graph 过滤和 disentangle。这个组合比单工具更稳。

但当前方案中“最后一个工具的 FASTA 就是结果”这个假设偏弱。GetOrganelle 官方文档和论文都强调 graph、`*.path_sequence.fasta`、多构型和成环状态的重要性。植物线粒体和 nr 区域尤其可能有多构型或非单一 circular contig。

### 优化建议

- GetOrganelle summary 默认只收集 `*.path_sequence.fasta`。
- graph-only 结果只进入 `INCOMPLETE`，不进入最终 FASTA。
- 所有结果必须附带 `length`、`coverage`、`topology`、`source_tool`、`source_path`、`status`。
- mt 与 nr 分开设计，不要把 nr 当作普通细胞器 genome 处理。
- nr 可以是 linear、多 copy 或多路径，不应强行按 mitochondrial circular genome 判断。
- 对 `embplant_mt` 增加警告：短读长很难可靠解析复杂重复，FASTA 只是候选结果，FASTG/GFA 必须保留用于人工复核。

## 专家二：浅层测序与污染控制专家

### 点评

浅层 genome skimming 最大风险不是“跑不出来”，而是“跑出来的是污染物”。尤其在目标 reads 少、污染 organelle reads 多时，MEANGS、NOVOPlasty 和 GetOrganelle 都可能组装出漂亮但错误的 circular contig。

因此 FastMitoAssembler 不能只判断工具是否运行成功，还必须判断结果是否像目标样本、目标类群和目标 genome。

### 优化建议

- summary TSV 增加 `best_blast_taxon`、`blast_identity`、`blast_coverage`、`top_hit_accession`。
- 每个候选 FASTA 自动做一次快速分类。可选方案包括 BLAST nt/自建线粒体库、MMseqs2 或 minimap2 到本地参考库。
- 对 MitoZ/MitoFinder 类注释输出，记录 PCG 数量、rRNA/tRNA 数量、缺失基因和异常 stop codon。
- 每个样本允许多个候选结果共存，不要过早覆盖。
- 新增一个“推荐结果选择”表，但不要自动删除非推荐候选。

候选结果建议同时保留：

```text
sample.meangs.fasta
sample.novoplasty.fasta
sample.getorganelle.fasta
sample.mg-nov-get.fasta
```

推荐结果可基于以下指标综合打分：

- 是否成环
- 是否在预期长度范围内
- 基因完整性
- 分类一致性
- coverage 连续性
- 多工具结果是否一致

建议新增 `fma validate` 或让 `fma summary` 自动生成 `summary_report.tsv`，字段至少包括：

```text
sample
pipeline
tool
locus
status
fasta_path
seq_count
length
topology
pcg_count
rrna_count
trna_count
coverage_mean
coverage_cv
blast_top_taxon
blast_identity
blast_coverage
warning
```

## 专家三：软件工程与可复现流程专家

### 点评

当前设计从功能上合理，但从软件架构上需要避免“又变成一个复杂的一键脚本”。FastMitoAssembler 应该保持 `fma run` 的易用性，同时将每个阶段拆成明确、可测、可复用的子命令。

### 优化建议

- `fma run` 保持旧的一键流程，但内部也应走同一套 stage、summary 和 validate 机制。
- 子命令不要复制大量 Click 参数，应抽象共享 runner，例如 `_build_run_config()` 和 `_run_snakemake_target()`。
- Snakemake 层使用明确 target，而不是在 shell 中写大量条件分支。
- 所有工具版本固定到环境文件，同时运行时检测实际版本并写入 report。
- summary/validate 不应依赖 shell grep，应尽量使用 Python FASTA parser 和 TSV writer。
- `seed_mode=single|by-sample` 很关键，建议再加 `--seed_missing fail|skip|fallback-single`，默认 `fail`。
- 批量数据中 silent fallback 很危险，尤其在污染数据中会导致错误 seed 被批量使用。

## 与现有工具和流程对比

| 工具/流程 | 核心思想 | 与 FastMitoAssembler 设计关系 | 启示 |
|---|---|---|---|
| GetOrganelle | baiting/iterative mapping，de novo assembly，graph filtering/disentangling，输出可能构型 | 应作为最重要的组装与 graph 复核核心 | 不要只看 FASTA；保留 graph、log、path_sequence |
| NOVOPlasty | seed-and-extend，从 seed 找目标 reads，快速组装 circular organelle | 适合与 MEANGS seed 组合，减少人工 seed 配置 | seed 质量决定结果；污染场景必须做分类验证 |
| MEANGS | 动物 mitogenome seed-free，自发现 seed，deepin 模式提高完整性 | 适合作为动物线粒体 seed 发现器 | 不适合 nr；输出应视为候选 seed 或候选 mt |
| MitoZ | animal mitogenome assembly、findMitoScaf、annotation、visualization | 更适合作为注释后端，而不是默认 assembly 来源 | “用 summary FASTA 给 MitoZ annotate”是正确方向 |
| MitoFinder | assemble/annotate mitochondrial contigs，也支持已有 assembly FASTA | 可作为未来替代或补充注释器 | 值得学习其 `assembly.fasta -> identify/annotate` 模式 |
| Fast-Plast / NOVOWrap | 面向 plastome 的自动 assemble、orient、validate、standardize | 如果未来支持叶绿体，应参考这些流程 | 叶绿体需要结构标准化、IR/LSC/SSC 方向处理 |
| MitoHiFi / Organelle_PBA | 长读长 organelle assembly，强调 read selection、NUMT/contamination、annotation/rotation | 当前不属于浅层 Illumina 主线，但设计理念值得借鉴 | 后续可加 long-read 模式，不应混入 v1 |

## 对当前方案的具体优化建议

1. 把 “summary FASTA” 升级成 “summary FASTA + summary TSV + validation TSV”。

2. `fma summary` 不只合并序列，还要判断：
   - 文件是否存在且非空
   - 序列长度是否在预期范围
   - header 是否含 topology
   - GetOrganelle 是否为 `path_sequence`
   - 是否有多个候选路径

3. `fma validate` 建议作为独立命令，后续可选：
   - `--blast_db`
   - `--min_len`
   - `--max_len`
   - `--expected_taxon`
   - `--require_circular`
   - `--min_pcg`

4. MitoZ 不应只作为最后一步固定执行。建议：
   - `fma mitoz annotate`
   - 输入来自 `summary/{sample}.{pipeline}.fasta`
   - 默认不调用 MitoZ assembly
   - MitoZ 自身 assembly 作为高级命令或单独模式

5. 对 nr 设计独立 locus 逻辑：
   - `locus=nr`
   - topology 默认 `linear|unknown`
   - 不要求 circular
   - 不交给 MitoZ 注释
   - summary 单独输出 `summary_nr.fasta`

6. 对完整链式流程保留，但标注为 high-recovery mode，而不是“标准科学流程”。

7. 对污染数据增加推荐组合：
   - 先 `fma meangs`
   - 再 `fma novoplasty`
   - 再 `fma getorganelle`
   - 最后 `fma summary + validate`
   - 只有 validate 通过后再 `fma mitoz`

## 建议修订后的流程

```text
reads
  |
  v
sample detection / optional adapter-only trimming
  |
  v
independent or chained assembly
  |-- MEANGS
  |-- NOVOPlasty
  |-- GetOrganelle
  `-- MEANGS -> NOVOPlasty -> GetOrganelle
  |
  v
candidate collection
  |
  v
summary FASTA + summary TSV
  |
  v
validation
  |-- topology
  |-- length
  |-- gene completeness
  |-- coverage
  `-- taxonomic check
  |
  v
selected candidate FASTA
  |
  v
MitoZ annotate
```

## 推荐的设计升级

FastMitoAssembler 的目标不应只是批量运行四个软件，而应是：

```text
批量运行 -> 候选结果收集 -> 质量验证 -> 推荐结果选择 -> 注释输出
```

这样可以避免“工具跑成功但结果错误”的问题，尤其适合浅层测序和污染较多的数据。

## 主要参考来源

- GetOrganelle GitHub：<https://github.com/Kinggerm/GetOrganelle>
- GetOrganelle paper：<https://genomebiology.biomedcentral.com/articles/10.1186/s13059-020-02154-5>
- NOVOPlasty GitHub：<https://github.com/ndierckx/NOVOPlasty>
- NOVOPlasty paper：<https://pmc.ncbi.nlm.nih.gov/articles/PMC5389512/>
- MEANGS GitHub：<https://github.com/YanCCscu/MEANGS>
- MEANGS paper：<https://academic.oup.com/bib/article/23/1/bbab538/6481918>
- MitoZ GitHub：<https://github.com/linzhi2013/MitoZ>
- MitoZ paper：<https://academic.oup.com/nar/article/47/11/e63/5377471>
- MitoFinder GitHub：<https://github.com/RemiAllio/MitoFinder>
- Fast-Plast GitHub：<https://github.com/mrmckain/Fast-Plast>
- MitoHiFi paper：<https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-023-05385-y>
- Organelle_PBA paper：<https://bmcgenomics.biomedcentral.com/articles/10.1186/s12864-016-3412-9>
