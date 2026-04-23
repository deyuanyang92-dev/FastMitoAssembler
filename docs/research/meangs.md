# MEANGS 调研记录

调研日期：2026-04-23

## 版本与来源

- 官方代码：<https://github.com/YanCCscu/MEANGS>
- 论文：Song, Yan, Li. 2022. Briefings in Bioinformatics. DOI: `10.1093/bib/bbab538`
- Conda 来源：`yccscucib::meangs`
- 官方 GitHub 当前可见最新 release：`v1.2.1`，2023-04-04
- Anaconda `yccscucib` 当前可见版本：`1.2.1`，2023-03-31
- FastMitoAssembler 当前环境约束：`FastMitoAssembler/smk/envs/meangs.yaml` 中写的是 `meangs`，未锁定精确版本

建议：FastMitoAssembler 后续应锁定 `meangs=1.2.1`，并在运行报告中记录实际 `meangs.py --version` 输出。若本地包无法提供稳定版本输出，则记录 conda 包版本。

## 软件定位

MEANGS 是动物线粒体基因组的 seed-free de novo 组装工具，从 paired-end NGS 数据中自动发现 seed 并延伸 contig。官方说明强调 MEANGS v1.0 只支持 paired-end 数据；当前项目也应继续按 PE FASTQ 作为 MEANGS 输入。

## 关键输入

- `-1/--fq1`：R1 FASTQ，可为 gz 压缩文件
- `-2/--fq2`：R2 FASTQ，可为 gz 压缩文件
- `-o/--outBase`：输出前缀，同时影响输出目录和文件命名
- `-i/--insert`：文库 insert size
- `-n/--nsample`：抽取 reads 数。官方建议用该参数降低运行时间和内存消耗
- `-s/--seqscaf`：指定 FASTA 序列，仅用于注释

## 关键参数

- `-t/--threads`：线程数
- `--deepin`：深度组装模式，适合提高完整性，但耗时更多
- `--clip`：检测线粒体成环剪切点
- `--species_class`：官方支持的类群值包括 `A-worms`、`Arthropoda`、`Bryozoa`、`Chordata`、`Echinodermata`、`Mollusca`、`Nematoda`、`N-worms`、`Porifera-sponges`
- `--silence`：将标准输出重定向到程序日志

注意：当前 FastMitoAssembler 配置使用 `meangs_clade` 并传给 `--clade`，但官方 README 中参数名是 `--species_class`。需要在实现前用实际安装版本确认 `meangs.py -h`，确定 yccscucib 版本是否新增了 `--clade` 别名；否则这是潜在兼容风险。

## 典型命令

快速模式：

```bash
meangs.py --silence -1 sample_1.fq.gz -2 sample_2.fq.gz \
  -o SampleA -t 16 -i 350
```

深度模式：

```bash
meangs.py -1 sample_R1.fastq.gz -2 sample_R2.fastq.gz \
  -o SampleA -t 16 -n 2000000 -i 300 --deepin
```

FastMitoAssembler 批量调用建议：

```bash
fma meangs --reads_dir reads --suffix_fq '_1.clean.fq.gz,_2.clean.fq.gz' \
  --meangs_thread 4 --meangs_reads 2000000 --meangs_deepin \
  --meangs_clade Arthropoda --cores 8
```

## 关键输出

官方 README 说明所有输出存放在 `-o` 指定目录下：

- `{prefix}_deep_detected_mito.fas`：deepin 模式下最终组装线粒体序列
- `{prefix}_hmmout_tbl_sorted.gff`：自动注释得到的蛋白编码基因结果
- `mito_cliped.fas`：启用 `--clip` 且剪切成功时可能输出到上一级目录
- 非 deepin 模式在不同版本中可能出现 `{prefix}_detected_mito.fas` 或 `mito.fasta`

当前 FastMitoAssembler 已在 Snakemake 中兼容：

- deepin：`{sample}/{sample}_deep_detected_mito.fas`
- non-deepin：优先 `{sample}/{sample}_detected_mito.fas`，否则 `mito.fasta`

## FastMitoAssembler 集成建议

- `fma meangs` 作为独立批量命令时，目标输出应为 `result/{sample}/1.MEANGS/{sample}_deep_detected_mito.fas`。
- 若用户提供 `seed_input`，当前 Snakemake 会跳过 MEANGS 组装并用 `seqkit head -n1` 取第一条 FASTA 作为 seed。后续应增加 `seed_mode`，支持 multi-FASTA 按 sample 匹配。
- summary FASTA 应记录 `tool=meangs`、`pipeline=meangs`、`topology=unknown|circular|linear`。MEANGS 未启用或未成功 `--clip` 时不应强行标记 circular。
- MEANGS 输出是候选线粒体序列，不应直接等同于最终高置信成环基因组。进入 NOVOPlasty 或 GetOrganelle 前应保留来源和长度信息。

## 风险与待核查

- 官方 README 的类群参数与当前项目使用的 `--clade` 不一致，需要实际命令帮助确认。
- MEANGS 主要面向动物 mitogenome，不适合作为 nr 组装工具。
- 浅层数据污染较高时，MEANGS seed-free 发现可能选中污染来源线粒体；summary 报告中应保留长度、拓扑和来源工具，方便人工复核。
