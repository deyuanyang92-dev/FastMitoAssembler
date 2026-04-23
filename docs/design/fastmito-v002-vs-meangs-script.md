# fastmito-v002 与 scripts/batch_meangs.py 功能对比

日期：2026-04-23

## 1. 更正说明

上一轮误把 Claude 目录中的 `Getorganelle_scripts/get_mt_nr_using_meangs_get_v0.01.py` 当成用户指定脚本进行比较。用户已更正，目标脚本是：

```text
/mnt/d/Claude/Fastmito/FastMitoAssembler/scripts/batch_meangs.py
```

本文件只对比该脚本与当前 `fastmito-v002`。

## 2. batch_meangs.py 的核心功能

脚本定位：MEANGS v1.3.1 批量运行包装器。

脚本解决的关键工程问题：

- 支持单样本：`--fq1 --fq2 --sample_name`。
- 支持批量样本：`--input_dir --suffix_fq --fastq_pos`。
- 支持两类 FASTQ 命名：
  - 单后缀：`.clean.fq.gz` -> `{sample}_1.clean.fq.gz` / `{sample}_2.clean.fq.gz`。
  - 双后缀：`.R1.clean.fastq.gz,.R2.clean.fastq.gz`。
- 支持两类目录布局：
  - `subdir`：每个样本一个子目录，子目录名作为 sample。
  - `flat`：所有 FASTQ 平铺在输入目录。
- 支持 `--meangs_path` 或 `--conda_meangs` 调用 MEANGS。
- 用 `ThreadPoolExecutor` 控制批量样本并行：`--max_parallel`。
- 每个样本使用独立临时 CWD：`out_dir/._work_{sample}`，规避 MEANGS `scaffold_seeds.fas` 并行竞态。
- 结果从临时目录移动到 `out_dir/{sample}/`。
- 已有 `{sample}_deep_detected_mito.fas` 时跳过，支持断点续跑。
- 支持 MEANGS v1.3.1 参数：
  - `--species_class`
  - `--deepin`
  - `--clip`
  - `--keepIntMed`
  - `--skipassem`
  - `--skipqc`
  - `--skiphmm`
  - `--skipextend`
  - `--seqscaf`
  - `--keepMinLen`
  - `-t/-i/-q/-n`
- 脚本末尾附带了一个 Snakemake 集成示例。

## 3. 当前 fastmito-v002 是否能实现这个脚本功能

结论：可以实现，而且更适合放在 v002 的 Python + Snakemake 架构中；但不能把这个功能完全等同为一个独立大脚本。

当前 v002 已经覆盖或刚修正：

- `fma meangs` 子命令可批量调用 MEANGS。
- MEANGS 规则按每个 sample 的独立结果目录运行，样本之间不会共享同一个 CWD。
- 支持通过 `tool_envs.meangs.conda_env` 或 `tool_envs.meangs.bin_dir` 调用 MEANGS，不需要在命令行硬编码 conda 环境。
- 自动识别样本时已吸收 `batch_meangs.py` 的 suffix 解析逻辑：
  - 单后缀自动转成 `_1{suffix}` / `_2{suffix}`。
  - 双后缀直接作为 R1/R2。
  - 支持 `recursive/subdir/flat` 三种检测模式。
- 自动识别时会把真实 R1/R2 路径传入 Snakemake，避免只识别 sample 后又套错 `fq_path_pattern`。
- 已把 MEANGS v1.3.1 调用从错误的 `--clade` 修正为 `--species_class`。
- 已新增 MEANGS 高级配置：
  - `meangs_quality`
  - `meangs_species_class`
  - `meangs_clip`
  - `meangs_keepIntMed`
  - `meangs_skipassem`
  - `meangs_skipqc`
  - `meangs_skiphmm`
  - `meangs_skipextend`
  - `meangs_seqscaf`
  - `meangs_keepMinLen`

仍未完全覆盖：

- `batch_meangs.py` 的单样本直跑模式 `--fq1 --fq2 --sample_name` 尚未做成单独 CLI；v002 目前通过 `--reads_dir --samples --fq_path_pattern` 表达。
- `--meangs_path` 命令行参数尚未直接暴露；v002 通过 `tool_envs.meangs.bin_dir` 配置工具路径。
- `--max_parallel` 没有同名参数；v002 用 Snakemake `--cores` 和每条 rule 的 `threads` 管理并行。
- `batch_meangs.py` 的断点判断是检查 deepin FASTA 是否存在；v002 依赖 Snakemake 的输出文件和 DAG 判断。
- `--clip` 产生的 `mito_cliped.fas` 尚未作为正式 summary 输入。
- `batch_meangs.py` 返回 `_expected_outputs()` 字典给嵌入式 Snakemake 示例；v002 使用正式 rule output，不需要这个字典接口。

## 4. 功能矩阵

| batch_meangs.py 功能 | fastmito-v002 状态 | 说明 |
|---|---|---|
| 单样本 `--fq1/--fq2` | 部分覆盖 | 可用 `--samples` + `fq_path_pattern`，但没有完全同名参数 |
| 批量 MEANGS | 已覆盖 | `fma meangs` |
| `subdir` 布局 | 已覆盖 | `--fastq_pos subdir` |
| `flat` 布局 | 已覆盖 | `--fastq_pos flat` |
| 递归扫描 | v002 扩展支持 | `--fastq_pos recursive`，适合混合项目目录 |
| 单后缀 `.clean.fq.gz` | 已覆盖 | 自动转 `_1/. _2` 风格 |
| 双后缀 `.R1,.R2` | 已覆盖 | 与脚本一致 |
| R2 存在性检查 | 已覆盖 | 自动检测和显式 sample 校验都检查 R1/R2 |
| `--conda_meangs` | 架构等价 | 用 `tool_envs.meangs.conda_env` |
| `--meangs_path` | 部分覆盖 | 用 `tool_envs.meangs.bin_dir`，尚未支持直接脚本路径 |
| MEANGS `--species_class` | 已修正 | 替代错误的 `--clade` |
| MEANGS `-q` | 已补充 | `meangs_quality` |
| `--deepin` | 已覆盖 | `meangs_deepin` |
| `--clip` | 部分覆盖 | 参数可传，summary 尚未收集 `mito_cliped.fas` |
| `--skipqc/--skiphmm/--skipextend` | 已补充 | 作为高级配置，不建议默认开启 |
| 每样本临时 CWD | 架构等价 | v002 每个 sample 有独立 `result/{sample}/1.MEANGS` |
| 已有结果跳过 | 已覆盖 | Snakemake output 机制 |
| `--max_parallel` | 架构等价 | Snakemake `--cores` |
| 失败样本列表 | 未覆盖 | 后续应在 summary/report 中加入 failed list |

## 5. 对 v002 的后续建议

优先级 P0：

1. 为 `fma meangs` 增加更贴近脚本的运行示例，包含 `subdir`、`flat`、单后缀、双后缀。
2. 在 summary 中记录 MEANGS 是否产生 deepin FASTA、detected FASTA、clip FASTA。
3. 增加 `tool_envs.meangs.script_path` 或命令行 `--meangs_path`，兼容直接指定 `meangs.py`。

优先级 P1：

1. 增加单样本快捷入口，例如：

```text
fma meangs --fq1 A.R1.fq.gz --fq2 A.R2.fq.gz --sample A
```

2. 生成 `meangs_failed.txt`，把失败样本从 Snakemake 日志中结构化汇总。
3. 如果启用 `meangs_clip`，把 `mito_cliped.fas` 纳入 per-sample summary。

优先级 P2：

1. 给 MEANGS 输出选择增加策略：
   - 优先 deepin。
   - 没有 deepin 则用 detected。
   - 多条 contig 时可选择最长或全部保留。
2. 在文档中明确 MEANGS v1.3.1 与旧版本参数差异，避免再次把 MitoZ 的 `--clade` 混用于 MEANGS。
