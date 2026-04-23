# MitoZ 调研记录

调研日期：2026-04-23

## 版本与来源

- 官方代码：<https://github.com/linzhi2013/MitoZ>
- 官方 Wiki：<https://github.com/linzhi2013/MitoZ/wiki>
- 论文：Meng et al. 2019. Nucleic Acids Research. DOI: `10.1093/nar/gkz173`
- Bioconda：<https://anaconda.org/bioconda/mitoz>
- 官方当前重点版本：`3.6`，2023-04-14 release
- Bioconda 当前可见最新版本：`3.6`
- FastMitoAssembler 当前环境约束：`mitoz>=3.6`

建议：FastMitoAssembler 后续应锁定 `mitoz=3.6`，因为官方 README 明确推荐升级到 3.6 以避开 3.5 的问题。若用户指定已有环境，则在 report 中记录实际 `mitoz --version`。

## 软件定位

MitoZ 是动物线粒体基因组 assembly、annotation、visualization 工具。它提供一键 `mitoz all`，也提供 `annotate`、`assemble`、`findmitoscaf`、`visualize` 等子命令。

FastMitoAssembler 当前最适合集成的是 `mitoz annotate`：把 MEANGS/NOVOPlasty/GetOrganelle 或 summary FASTA 作为外部候选线粒体 FASTA 输入，避免完全依赖 MitoZ 自身 assembly/findmitoscaf。

## 关键输入

`mitoz annotate` 当前 FastMitoAssembler 使用的核心参数：

- `--outprefix`
- `--thread_number`
- `--fastafiles`
- `--fq1`
- `--fq2`
- `--species_name`
- `--genetic_code`
- `--clade`

MitoZ tutorial 说明 MitoZ raw data 通常为 Illumina/BGISEQ WGS reads；`mitoz all` 会做过滤、组装、注释和可视化。FastMitoAssembler 不应默认走 `mitoz all`，因为本项目的目标是把其他 assembler 得到的候选 FASTA 交给 MitoZ 注释。

## 关键参数

- `--clade`：动物类群，必须与样本匹配
- `--genetic_code`：线粒体遗传密码表；节肢动物常用 `5`，脊椎动物常用 `2`
- `--thread_number`：线程数
- `--fastafiles`：输入待注释 FASTA
- `--fq1/--fq2`：可用于深度/可视化相关步骤
- `--species_name`：影响 GenBank 输出中的物种名

官方 2024-11-06 README 更新提醒：输入 raw data 过多可能导致非成环 mitogenome，较小数据量有时更容易得到 circular 结果。这支持 FastMitoAssembler 不应盲目把全部 reads 交给 MitoZ assembly，而应优先使用前序工具筛出的候选 FASTA 做 annotate。

## 典型命令

FastMitoAssembler 当前 Snakemake 使用模式：

```bash
mitoz annotate \
  --outprefix SampleA \
  --thread_number 20 \
  --fastafiles result/SampleA/3.GetOrganelle/animal_mt.get_organelle.fasta \
  --fq1 reads/SampleA/SampleA_1.clean.fq.gz \
  --fq2 reads/SampleA/SampleA_2.clean.fq.gz \
  --species_name "SampleA" \
  --genetic_code 5 \
  --clade Arthropoda
```

未来独立命令建议：

```bash
fma mitoz --assembly_fasta result/summary/SampleA.getorganelle.fasta \
  --reads_dir reads --clade Arthropoda --genetic_code 5 --cores 8
```

## 关键输出

当前 FastMitoAssembler 期望 MitoZ annotation 输出：

- `circos.png`
- `summary.txt`
- `*.gbf`

MitoZ tutorial 中 `mitoz all` 的组装结果还包括：

- `mt_assembly/{sample}.megahit.result/{sample}.megahit.mitogenome.fa`
- `overlap_information`
- `mt_annotation/.../*.gbf`
- `*.result/` 目录

MitoZ 组装阶段会从 candidate contigs 中筛选 mitogenome，并用 overlap 判断 circular。用户已指出 MitoZ 自身发现 `mtcontigs.fasta` 或候选线粒体 contig 的算法在某些情况下不好，因此 FastMitoAssembler 应把 MitoZ 定位为 annotation/visualization 后端，而不是唯一 assembly source。

## Temp_scripts 参考脚本

已克隆用户指定仓库到 `/tmp/Temp_scripts_fma_research`，commit：

```text
dc87bb3 Add blast2metadata v2.12 script
```

相关文件：

- `/tmp/Temp_scripts_fma_research/Mitoz-annotate/README.md`
- `/tmp/Temp_scripts_fma_research/Mitoz-annotate/batch_mitoz.py`

该脚本提供了几个值得纳入 FastMitoAssembler 的规则：

- 输入可为 FASTA 或 GenBank，FASTA header 可包含 `topology=linear|circular`。
- 多记录 FASTA 默认拆分为单条记录，避免 MitoZ 内部 ID 或 GenBank LOCUS 过长。
- MitoZ annotate 后可按目标基因如 `cox1` 重定向。
- 最终输出 `.gbf`、统计表、日志、失败列表和合并 GenBank。
- 调度可用 threads 或 Snakemake。

FastMitoAssembler v1 不必完整复制 GenBank 后处理流程，但应保留短 ID 和 header/topology 规范，避免 MitoZ 对复杂 header 处理不稳定。

## FastMitoAssembler 集成建议

- `fma mitoz` 默认只做 annotate，不调用 MitoZ assembly。
- 输入优先级：`--assembly_fasta` > summary FASTA > GetOrganelle 标准输出。
- 对于组合流程，MitoZ 注释输入使用最后一个有效 assembler 的 summary FASTA。
- MitoZ 输出目录保持 `result/{sample}/4.MitozAnnotate/`，同时将关键结果汇总到 `result/summary/mitoz/` 或 summary report。
- `topology` 应从输入 FASTA header 传递到 MitoZ 后处理，不应在 MitoZ 输出缺失时丢失。

## 风险与待核查

- MitoZ 主要面向动物 mitogenome，不适合作为 nr 注释工具。
- MitoZ 对 header 长度、特殊字符和多记录 FASTA 的兼容性需要在实现中防御；summary FASTA header 应可读但不过长。
- `mtcontigs.fasta` 或 MitoZ assembly 候选算法不作为 FastMitoAssembler 的默认可信来源。
- 用户若需要完整 MitoZ `all`，可作为高级模式另行支持，不纳入第一阶段核心实现。
