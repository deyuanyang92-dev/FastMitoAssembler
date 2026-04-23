# Repository Guidelines

## FastMitoAssembler v002 Project Goal

重构 FastMitoAssembler，让 MEANGS、NOVOPlasty、GetOrganelle、MitoZ 支持独立批量运行和组合流程。FastMitoAssembler 是流程整合项目，不重新实现这些外部软件的核心算法。

Python 负责 CLI、配置合并、样本识别、seed 解析、summary FASTA/TSV 和 Snakemake target 分发。Snakemake 负责 DAG、日志、conda 环境、dry-run、HPC/profile 以及外部工具执行。

## Current Progress

- [x] 调研 MEANGS 初稿
- [x] 调研 NOVOPlasty 初稿
- [x] 调研 GetOrganelle 初稿
- [x] 调研 MitoZ 初稿
- [x] 实现 Snakemake rules 模块化目录
- [x] 实现 Python 辅助模块雏形
- [ ] 按官方最新文档和本地 `-h`/`--help` 再复核所有工具
- [ ] 完成真实外部工具验证
- [ ] 若仍坚持字面 `modules/` 目录，再单独设计

当前实际模块化位置是 `FastMitoAssembler/smk/rules/` 和 `FastMitoAssembler/bin/_*.py`，不是独立的字面 `modules/` 目录。

## Mandatory Rules

- 修改 `.py` 文件后必须运行：`python -m black . && python -m flake8`。
- 如果当前环境缺少 `black` 或 `flake8`，必须明确记录为阻塞，不能伪造检查通过。
- 不要删除原有 `FastMitoAssembler/smk/` 目录下任何文件。
- 每完成一个独立模块后立即单独 `git commit`；如果当前操作者没有被授权提交，必须停下并提示用户提交。
- Python 版本要求：3.9+。
- 代码实现必须优先复用现有 FastMitoAssembler 框架、已有 Python 模块和已有 Snakemake 规则。

## Prohibited Actions

- 不破坏原有 `config.yaml` 兼容性；禁止随意删除、重命名或改变已有配置键语义。确需扩展时只追加新键，并保留旧键兼容。
- 不运行 `rm -rf` 类命令。
- 不删除或重写现有 `smk/` 主流程来替代模块化整合。
- 不把 MEANGS、NOVOPlasty、GetOrganelle、MitoZ、fastp、SPAdes 或 BLAST 的核心算法重新写进 FastMitoAssembler。
- 不把 MitoZ assembly 作为默认可信组装来源；MitoZ 默认应作为 annotation/visualization 后端。

## Project Structure & Module Organization

`FastMitoAssembler/` contains the Python package. CLI commands live in `FastMitoAssembler/bin/`, shared helpers in `config.py`, `util.py`, and `report.py`, and packaged workflow resources in `FastMitoAssembler/smk/`. Snakemake entrypoint is `FastMitoAssembler/smk/main.smk`; reusable rules are under `FastMitoAssembler/smk/rules/`; default workflow settings are in `config.yaml` and `options.yaml`; tool-specific conda environments are under `FastMitoAssembler/smk/envs/`. Tests are in `tests/` and mirror CLI or module behavior with files such as `test_check.py` and `test_run_options.py`. Documentation and planning assets are under `docs/`, while container recipes are in `docker/`.

## Build, Test, and Development Commands

Create the development environment with:

```bash
mamba env create -f environment.yml
conda activate FastMitoAssembler
pip install -e .
```

Run tests with `pytest`. Use focused runs while developing, for example `pytest tests/test_check.py`. Build source and wheel distributions with `bash build.sh`; it removes previous build artifacts, runs `python setup.py build sdist bdist_wheel`, then cleans temporary build directories. Use `fma --help`, `fma check`, and `fma run --configfile config.yaml --dryrun` to verify CLI behavior locally. After any Python edit, run `python -m black . && python -m flake8`; if either tool is unavailable, report that as a development-environment blocker.

## Coding Style & Naming Conventions

Use Python 3.9-compatible code. Follow the existing style: 4-space indentation, snake_case functions and variables, short module-level helpers, and Click command functions grouped under `FastMitoAssembler/bin/_*.py`. Keep command aliases and entry points synchronized with `setup.py`. Prefer `pathlib.Path` for filesystem paths where practical, and keep YAML keys stable because they are consumed by Snakemake and user config files. Do not change existing `config.yaml` key semantics without an explicit compatibility path.

## Testing Guidelines

The test suite uses `pytest`, `unittest.mock`, and `click.testing.CliRunner`. Name test files `test_*.py` and test functions `test_*`. Mock external tools, conda environments, filesystem probes, and Snakemake calls instead of requiring MEANGS, NOVOPlasty, GetOrganelle, or MitoZ in unit tests. Add regression tests for CLI flags, config parsing, generated reports, and sample detection whenever behavior changes.

## Commit & Pull Request Guidelines

Recent commits use short imperative subjects, often with prefixes such as `feat:` and `docs:`; keep subjects concise and scoped, for example `feat: add setup validation for tool_envs`. Pull requests should explain the user-facing change, list test commands run, mention affected CLI commands or config keys, and link related issues or design notes. Include screenshots only for generated reports or rendered documentation changes.

## Security & Configuration Tips

Do not commit local databases, read files, conda prefixes, or secrets. Global tool configuration belongs in `~/.config/FastMitoAssembler/tool_envs.yaml`; repository examples should use portable paths and safe defaults.
