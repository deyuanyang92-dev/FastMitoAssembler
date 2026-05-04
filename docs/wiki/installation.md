# 安装与配置指南

## 系统要求

### 硬件要求

| 资源 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 4 核 | 16+ 核 |
| 内存 | 8 GB | 32+ GB |
| 磁盘 | 50 GB | 100+ GB SSD |

### 软件要求

| 软件 | 版本 | 说明 |
|------|------|------|
| Python | >= 3.9 | 推荐 3.12 |
| conda/mamba | 最新版 | mamba 更快 |
| Snakemake | 7.x | 可选 (Python 后端不需要) |

---

## 安装方式

### 方式一：完整安装 (推荐)

适合首次使用的用户。

```bash
# 1. 创建主环境
mamba create -n FastMitoAssembler -c conda-forge \
    python=3.12 "snakemake>=7,<8" click jinja2 pyyaml ete3

conda activate FastMitoAssembler

# 2. 安装 FastMitoAssembler
pip install git+https://github.com/deyuanyang92-dev/FastMitoAssembler.git

# 3. 安装工具环境 (约 20-40 分钟)
fma prepare tools

# 4. 准备数据库
fma prepare ncbitaxa                    # NCBI 分类库
fma prepare organelle -a animal_mt      # 动物线粒体数据库

# 5. 验证安装
fma check
```

### 方式二：使用已有工具

适合已有 MEANGS、NOVOPlasty、GetOrganelle、MitoZ 安装的用户。

```bash
# 1. 创建主环境
mamba create -n FastMitoAssembler -c conda-forge \
    python=3.12 "snakemake>=7,<8" click jinja2 pyyaml

conda activate FastMitoAssembler

# 2. 安装 FastMitoAssembler
pip install git+https://github.com/deyuanyang92-dev/FastMitoAssembler.git

# 3. 配置已有工具
# 方式 A: 自动检测
fma check --save

# 方式 B: 手动配置
fma config set meangs --conda-env my-meangs-env
fma config set novoplasty --conda-env my-novoplasty-env
fma config set getorganelle --conda-env my-getorganelle-env
fma config set mitoz --conda-env my-mitoz-env

# 4. 准备数据库
fma prepare ncbitaxa
fma prepare organelle -a animal_mt

# 5. 验证
fma check
```

### 方式三：从源码安装

适合开发者或需要修改源码的用户。

```bash
# 1. 克隆仓库
git clone https://github.com/deyuanyang92-dev/FastMitoAssembler.git
cd FastMitoAssembler

# 2. 创建环境
mamba create -n FastMitoAssembler -c conda-forge \
    python=3.12 "snakemake>=7,<8" click jinja2 pyyaml

conda activate FastMitoAssembler

# 3. 安装 (开发模式)
pip install -e .

# 4. 安装工具环境
fma prepare tools

# 5. 准备数据库
fma prepare ncbitaxa
fma prepare organelle -a animal_mt
```

---

## 工具环境配置

### 环境架构

FastMitoAssembler 使用**两层环境架构**：

```
FastMitoAssembler (主环境)        ← 流程调度器 (CLI + Snakemake)
├── FastMitoAssembler-meangs      ← MEANGS 工具
├── FastMitoAssembler-novoplasty  ← NOVOPlasty 工具
├── FastMitoAssembler-getorganelle← GetOrganelle 工具
└── FastMitoAssembler-mitoz       ← MitoZ 工具
```

### 配置方式

#### 1. conda 环境

```bash
fma config set meangs --conda-env my-meangs-env
```

生成的配置：
```yaml
meangs:
  conda_env: my-meangs-env
  bin_dir: ''
  script_path: ''
```

#### 2. 二进制目录

```bash
fma config set mitoz --bin-dir /opt/mitoz/bin
```

生成的配置：
```yaml
mitoz:
  conda_env: ''
  bin_dir: /opt/mitoz/bin
  script_path: ''
```

#### 3. 脚本路径

适合 Python/Perl 脚本工具：

```bash
fma config set meangs --script-path /path/to/meangs.py
fma config set novoplasty --script-path /path/to/NOVOPlasty.pl
```

#### 4. 项目级配置

在项目的 `config.yaml` 中覆盖全局配置：

```yaml
tool_envs:
  meangs:
    conda_env: project-specific-meangs
  mitoz:
    bin_dir: /project/tools/mitoz/bin
```

### 查看配置

```bash
# 显示全局配置
fma config show

# 输出示例：
# Tool configurations:
#   meangs:
#     conda_env: FastMitoAssembler-meangs
#   novoplasty:
#     conda_env: FastMitoAssembler-novoplasty
#   getorganelle:
#     conda_env: FastMitoAssembler-getorganelle
#   mitoz:
#     conda_env: FastMitoAssembler-mitoz
```

### 重置配置

```bash
# 重置单个工具
fma config reset meangs

# 重置所有工具
fma config reset all
```

---

## 数据库准备

### NCBI Taxonomy (MitoZ 需要)

```bash
# 自动下载
fma prepare ncbitaxa

# 使用本地文件
fma prepare ncbitaxa --taxdump_file /path/to/taxdump.tar.gz
```

下载位置：`~/.config/FastMitoAssembler/ncbi_taxa/`

### GetOrganelle 数据库

```bash
# 动物线粒体 (推荐)
fma prepare organelle -a animal_mt

# 植物线粒体
fma prepare organelle -a embplant_mt

# 植物叶绿体
fma prepare organelle -a embplant_pt

# 真菌线粒体
fma prepare organelle -a fungus_mt

# 所有数据库 (~10 GB)
fma prepare organelle -a all

# 列出已安装数据库
fma prepare organelle --list
```

可用数据库：
- `embplant_pt` - 植物叶绿体
- `embplant_mt` - 植物线粒体
- `embplant_nr` - 植物核糖体
- `fungus_mt` - 真菌线粒体
- `fungus_nr` - 真菌核糖体
- `animal_mt` - 动物线粒体
- `other_pt` - 其他质体

---

## 验证安装

### fma check

```bash
fma check
```

预期输出：
```
Tool              Status           Details
──────────────────────────────────────────────────────────────
meangs            ✓ found          conda env: FastMitoAssembler-meangs
novoplasty        ✓ found          conda env: FastMitoAssembler-novoplasty
getorganelle      ✓ found          conda env: FastMitoAssembler-getorganelle
mitoz             ✓ found          conda env: FastMitoAssembler-mitoz

Database          Status           Path
──────────────────────────────────────────────────────────────
ncbi_taxa         ✓ found          ~/.config/FastMitoAssembler/ncbi_taxa
animal_mt         ✓ found          ~/.config/FastMitoAssembler/animal_mt
```

### 测试运行

```bash
# 创建测试目录
mkdir -p test_fma && cd test_fma

# 初始化配置
fma init

# 编辑 config.yaml (使用测试数据)
# ...

# 干运行测试
fma run --configfile config.yaml --dryrun
```

---

## 更新

### 更新 FastMitoAssembler

```bash
conda activate FastMitoAssembler
pip install -U git+https://github.com/deyuanyang92-dev/FastMitoAssembler.git

# 如果 fma 命令找不到
pip install --force-reinstall --no-deps \
    git+https://github.com/deyuanyang92-dev/FastMitoAssembler.git
```

### 更新工具环境

```bash
# 重新创建所有工具环境
fma prepare tools --force

# 更新单个工具
fma prepare tools --tool mitoz --force
```

---

## 故障排除

### 问题 1: fma 命令找不到

**原因**: pip 安装后 entry point 未正确生成

**解决**:
```bash
pip install --force-reinstall --no-deps \
    git+https://github.com/deyuanyang92-dev/FastMitoAssembler.git
```

### 问题 2: 工具环境创建失败

**原因**: 网络问题或 conda 通道冲突

**解决**:
```bash
# 使用 mamba
mamba install -n FastMitoAssembler-meangs -c bioconda -c conda-forge meangs

# 或使用国内镜像
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/bioconda/
```

### 问题 3: MitoZ 环境安装缓慢

**原因**: MitoZ 依赖较多，包较大

**解决**:
```bash
# 单独安装，耐心等待
fma prepare tools --tool mitoz

# 或使用预构建环境
conda create -n FastMitoAssembler-mitoz -c bioconda -c conda-forge mitoz
```

### 问题 4: 数据库下载失败

**原因**: 网络问题

**解决**:
```bash
# 手动下载 taxdump
wget https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz
fma prepare ncbitaxa --taxdump_file taxdump.tar.gz

# 手动下载 GetOrganelle 数据库
# 参考: https://github.com/Kinggerm/GetOrganelle
```

### 问题 5: Snakemake 版本冲突

**原因**: Snakemake 8.x 与 7.x 不兼容

**解决**:
```bash
# 安装 Snakemake 7.x
mamba install -n FastMitoAssembler "snakemake>=7,<8" "pulp<2.8"
```

---

## 卸载

```bash
# 删除主环境
conda deactivate
conda env remove -n FastMitoAssembler

# 删除全局配置
rm -rf ~/.config/FastMitoAssembler

# 删除工具环境 (如果创建了)
conda env remove -n FastMitoAssembler-meangs
conda env remove -n FastMitoAssembler-novoplasty
conda env remove -n FastMitoAssembler-getorganelle
conda env remove -n FastMitoAssembler-mitoz
```

---

## 下一步

安装完成后，请参考：

- [快速开始](WIKI.md#快速开始) - 运行第一个流程
- [命令参考](WIKI.md#命令参考) - 了解所有命令
- [一键化流程](fsb-all-guide.md) - 使用 `fma fsb-all`