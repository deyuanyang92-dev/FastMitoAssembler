import re
import subprocess
from pathlib import Path

import jinja2

_MM_EN = """\
## Materials and Methods

### Mitochondrial Genome Assembly and Annotation

Paired-end Illumina reads (read length: {{ read_length }} bp, insert size: {{ insert_size }} bp) \
were assembled into a mitochondrial genome using the FastMitoAssembler pipeline [1], \
which chains four tools in sequence.

**Step 1 – Seed detection (MEANGS [2] v{{ meangs_ver }}):** Mitochondrial seed sequences \
were detected using MEANGS, sampling {{ meangs_reads }} reads per sample \
{{ '(deep assembly enabled)' if meangs_deepin else '(standard mode)' }}.

**Step 2 – Initial assembly (NOVOPlasty [3] v{{ novoplasty_ver }}):** De novo assembly of \
the mitochondrial genome was performed using NOVOPlasty with k-mer size {{ kmer_size }}, \
target genome size {{ genome_min_size }}–{{ genome_max_size }} bp, read length \
{{ read_length }} bp, insert size {{ insert_size }} bp, and {{ max_mem_gb }} GB memory limit.

**Step 3 – Extended assembly (GetOrganelle [4] v{{ getorganelle_ver }}):** The draft assembly \
was extended and refined using GetOrganelle with the `{{ organelle_database }}` reference database.

**Step 4 – Annotation (MitoZ [5] v{{ mitoz_ver }}):** The final mitochondrial genome was \
annotated using MitoZ with genetic code {{ genetic_code }} (clade: {{ clade }}).

### References

[1] FastMitoAssembler. https://github.com/deyuanyang92-dev/FastMitoAssembler
[2] MEANGS. https://github.com/YanCCscu/MEANGS
[3] Dierckxsens N, Mardulyn P, Smits G. (2017). NOVOPlasty: de novo assembly of organelle genomes from whole genome data. *Nucleic Acids Research*, 45(4), e18. https://doi.org/10.1093/nar/gkw955
[4] Jin JJ, Yu WB, Yang JB, Song Y, dePamphilis CW, Yi TS, Li DZ. (2020). GetOrganelle: a fast and versatile toolkit for accurate de novo assembly of organelle genomes. *Genome Biology*, 21, 241. https://doi.org/10.1186/s13059-020-02154-5
[5] Meng G, Li Y, Yang C, Liu S. (2019). MitoZ: a toolkit for animal mitochondrial genome assembly, annotation and visualization. *Nucleic Acids Research*, 47(11), e63. https://doi.org/10.1093/nar/gkz173
"""

_MM_ZH = """\
## 材料与方法

### 线粒体基因组组装与注释

使用FastMitoAssembler流程 [1] 对双端Illumina测序数据（读长：{{ read_length }} bp，\
插入片段大小：{{ insert_size }} bp）进行线粒体基因组组装，该流程依次调用四个工具。

**步骤一 – 种子序列检测（MEANGS [2] v{{ meangs_ver }}）：** 使用MEANGS检测线粒体种子序列，\
每个样本随机抽取 {{ meangs_reads }} 条reads\
{{ '（开启深度组装模式）' if meangs_deepin else '（标准模式）' }}。

**步骤二 – 初步组装（NOVOPlasty [3] v{{ novoplasty_ver }}）：** 以种子序列为基础，\
使用NOVOPlasty进行线粒体基因组初步组装，k-mer大小 {{ kmer_size }}，\
目标基因组大小 {{ genome_min_size }}–{{ genome_max_size }} bp，读长 {{ read_length }} bp，\
插入片段大小 {{ insert_size }} bp，内存限制 {{ max_mem_gb }} GB。

**步骤三 – 延伸组装（GetOrganelle [4] v{{ getorganelle_ver }}）：** 使用GetOrganelle \
结合 `{{ organelle_database }}` 参考数据库对初步组装结果进行延伸和精修。

**步骤四 – 注释（MitoZ [5] v{{ mitoz_ver }}）：** 使用MitoZ对线粒体基因组进行注释，\
遗传密码表 {{ genetic_code }}，分类群 `{{ clade }}`。

### 参考文献

[1] FastMitoAssembler. https://github.com/deyuanyang92-dev/FastMitoAssembler
[2] MEANGS. https://github.com/YanCCscu/MEANGS
[3] Dierckxsens N, Mardulyn P, Smits G. (2017). NOVOPlasty: de novo assembly of organelle genomes from whole genome data. *Nucleic Acids Research*, 45(4), e18. https://doi.org/10.1093/nar/gkw955
[4] Jin JJ等 (2020). GetOrganelle: a fast and versatile toolkit for accurate de novo assembly of organelle genomes. *Genome Biology*, 21, 241. https://doi.org/10.1186/s13059-020-02154-5
[5] Meng G, Li Y, Yang C, Liu S. (2019). MitoZ: a toolkit for animal mitochondrial genome assembly, annotation and visualization. *Nucleic Acids Research*, 47(11), e63. https://doi.org/10.1093/nar/gkz173
"""

# Version-detection commands for each tool (stdout+stderr combined)
_VERSION_CMDS = {
    'meangs':       'meangs.py --version 2>&1 || meangs.py -v 2>&1 || echo N/A',
    'novoplasty':   'NOVOPlasty.pl 2>&1 | head -5',
    'getorganelle': 'get_organelle_from_reads.py --version 2>&1',
    'mitoz':        'mitoz version 2>&1 || mitoz --version 2>&1 || echo N/A',
}


def _detect_version(tool, cmd, prefix=''):
    """Run a version-detection command and extract the first version-like string."""
    try:
        full_cmd = f'{prefix}{cmd}'
        result = subprocess.run(
            full_cmd, shell=True, capture_output=False,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=10,
        )
        out = result.stdout.strip()
        m = re.search(r'v?(\d+\.\d+[\d.]*)', out)
        return m.group(1) if m else 'N/A'
    except Exception:
        return 'N/A'


def _make_prefix(tool, tool_envs):
    cfg = (tool_envs or {}).get(tool) or {}
    if not isinstance(cfg, dict):
        return ''
    bin_dir = (cfg.get('bin_dir') or '').strip()
    return f'PATH="{bin_dir}:$PATH" ' if bin_dir else ''


def generate_mm_report(output_path, sample, cfg, tool_envs=None):
    """Generate a bilingual Materials & Methods markdown file.

    Parameters
    ----------
    output_path : str or Path
        Destination file path.
    sample : str
        Sample name (informational only).
    cfg : dict
        Snakemake config dict (passed through from the workflow).
    tool_envs : dict, optional
        Per-tool environment overrides (conda_env / bin_dir).
    """
    versions = {}
    for tool, cmd in _VERSION_CMDS.items():
        prefix = _make_prefix(tool, tool_envs)
        versions[tool] = _detect_version(tool, cmd, prefix)

    params = {
        'read_length':        cfg.get('read_length', 150),
        'insert_size':        cfg.get('insert_size', 300),
        'meangs_reads':       cfg.get('meangs_reads', 2000000),
        'meangs_deepin':      cfg.get('meangs_deepin', True),
        'kmer_size':          cfg.get('kmer_size', 33),
        'genome_min_size':    cfg.get('genome_min_size', 12000),
        'genome_max_size':    cfg.get('genome_max_size', 22000),
        'max_mem_gb':         cfg.get('max_mem_gb', 10),
        'organelle_database': cfg.get('organelle_database', 'animal_mt'),
        'genetic_code':       cfg.get('genetic_code', 5),
        'clade':              cfg.get('clade', 'Annelida-segmented-worms'),
        'meangs_ver':         versions['meangs'],
        'novoplasty_ver':     versions['novoplasty'],
        'getorganelle_ver':   versions['getorganelle'],
        'mitoz_ver':          versions['mitoz'],
    }

    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    en_text = env.from_string(_MM_EN).render(**params)
    zh_text = env.from_string(_MM_ZH).render(**params)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as fh:
        fh.write('# Materials and Methods / 材料与方法\n\n')
        fh.write('---\n\n')
        fh.write(en_text)
        fh.write('\n\n---\n\n')
        fh.write(zh_text)
        fh.write('\n')
