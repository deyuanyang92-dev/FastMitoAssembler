"""
Tests for FastpRunner
"""

import tempfile
from pathlib import Path
import pytest

from FastMitoAssembler.bin.runners._fastp_runner import (
    FastpRunner,
    is_sample_done,
    is_sample_done_se,
    get_output_files,
    parse_reads_dir,
    parse_reads_dir_se,
    parse_reads_dir_auto,
    detect_fastq_structure,
    write_checked_file,
    FASTP_PRESETS,
    PRESET_MODES,
)


class TestFastpRunner:
    """FastpRunner tests"""

    def test_init(self):
        """Test initialization"""
        runner = FastpRunner(threads=8)
        assert runner.threads == 8
        assert runner.shell_prefix == ""

    def test_init_with_prefix(self):
        """Test initialization with shell prefix"""
        runner = FastpRunner(threads=8, shell_prefix="conda run -n fastp ")
        assert runner.shell_prefix == "conda run -n fastp "

    def test_preset_modes_exist(self):
        """Test all preset modes are defined"""
        assert "default" in FASTP_PRESETS
        assert "adapter_only" in FASTP_PRESETS
        assert "shallow_data" in FASTP_PRESETS
        assert "transcriptome" in FASTP_PRESETS
        assert "full_qc" in FASTP_PRESETS
        assert len(PRESET_MODES) == 5

    def test_preset_modes_have_required_keys(self):
        """Test preset modes have required keys"""
        for mode, preset in FASTP_PRESETS.items():
            assert "description" in preset
            assert "cmd_flags" in preset
            # default mode has empty flags (uses fastp defaults)
            if mode != "default":
                assert preset["cmd_flags"]  # non-empty for non-default modes

    def test_build_command_adapter_only(self, tmp_path):
        """Test building command with adapter_only mode"""
        runner = FastpRunner()

        fq1 = tmp_path / "S1_1.fq.gz"
        fq2 = tmp_path / "S1_2.fq.gz"
        out1 = tmp_path / "out_1.fq.gz"
        out2 = tmp_path / "out_2.fq.gz"
        json_r = tmp_path / "fastp.json"
        html_r = tmp_path / "fastp.html"

        cmd = runner.build_command(
            str(fq1), str(fq2),
            str(out1), str(out2),
            str(json_r), str(html_r),
            mode="adapter_only",
        )

        cmd_str = " ".join(cmd)
        assert "fastp" in cmd_str
        assert "-i" in cmd_str
        assert "-I" in cmd_str
        assert "-o" in cmd_str
        assert "-O" in cmd_str
        assert "-j" in cmd_str
        assert "-h" in cmd_str
        assert "--detect_adapter_for_pe" in cmd_str
        assert "-Q" in cmd_str
        assert "-L" in cmd_str

    def test_build_command_transcriptome(self, tmp_path):
        """Test building command with transcriptome mode"""
        runner = FastpRunner()

        fq1 = tmp_path / "S1_1.fq.gz"
        fq2 = tmp_path / "S1_2.fq.gz"
        out1 = tmp_path / "out_1.fq.gz"
        out2 = tmp_path / "out_2.fq.gz"
        json_r = tmp_path / "fastp.json"
        html_r = tmp_path / "fastp.html"

        cmd = runner.build_command(
            str(fq1), str(fq2),
            str(out1), str(out2),
            str(json_r), str(html_r),
            mode="transcriptome",
        )

        cmd_str = " ".join(cmd)
        assert "--trim_poly_x" in cmd_str
        assert "--cut_front" in cmd_str
        assert "--cut_tail" in cmd_str
        assert "--length_required" in cmd_str

    def test_build_command_shallow_data(self, tmp_path):
        """Test building command with shallow_data mode"""
        runner = FastpRunner()

        fq1 = tmp_path / "S1_1.fq.gz"
        fq2 = tmp_path / "S1_2.fq.gz"
        out1 = tmp_path / "out_1.fq.gz"
        out2 = tmp_path / "out_2.fq.gz"
        json_r = tmp_path / "fastp.json"
        html_r = tmp_path / "fastp.html"

        cmd = runner.build_command(
            str(fq1), str(fq2),
            str(out1), str(out2),
            str(json_r), str(html_r),
            mode="shallow_data",
        )

        cmd_str = " ".join(cmd)
        assert "--n_base_limit" in cmd_str
        # BUG-01 修复: --disable_low_complexity_filter 是无效参数，已移除
        # 低复杂度过滤默认关闭，无需显式禁用
        assert "-Q" in cmd_str  # 禁用质量过滤
        assert "-L" in cmd_str  # 禁用长度过滤

    def test_build_command_full_qc(self, tmp_path):
        """Test building command with full_qc mode"""
        runner = FastpRunner()

        fq1 = tmp_path / "S1_1.fq.gz"
        fq2 = tmp_path / "S1_2.fq.gz"
        out1 = tmp_path / "out_1.fq.gz"
        out2 = tmp_path / "out_2.fq.gz"
        json_r = tmp_path / "fastp.json"
        html_r = tmp_path / "fastp.html"

        cmd = runner.build_command(
            str(fq1), str(fq2),
            str(out1), str(out2),
            str(json_r), str(html_r),
            mode="full_qc",
        )

        cmd_str = " ".join(cmd)
        assert "--qualified_quality_phred" in cmd_str
        assert "--unqualified_percent_limit" in cmd_str

    def test_build_command_custom_adapter(self, tmp_path):
        """Test building command with custom adapter sequences"""
        runner = FastpRunner()

        fq1 = tmp_path / "S1_1.fq.gz"
        fq2 = tmp_path / "S1_2.fq.gz"
        out1 = tmp_path / "out_1.fq.gz"
        out2 = tmp_path / "out_2.fq.gz"
        json_r = tmp_path / "fastp.json"
        html_r = tmp_path / "fastp.html"

        cmd = runner.build_command(
            str(fq1), str(fq2),
            str(out1), str(out2),
            str(json_r), str(html_r),
            mode="adapter_only",
            adapter_sequence="AGATCGGAAGAGC",
            adapter_sequence_r2="AGATCGGAAGAGC",
        )

        cmd_str = " ".join(cmd)
        assert "--adapter_sequence" in cmd_str
        assert "AGATCGGAAGAGC" in cmd_str

    def test_build_command_extra_args(self, tmp_path):
        """Test passthrough of extra arguments"""
        runner = FastpRunner()

        fq1 = tmp_path / "S1_1.fq.gz"
        fq2 = tmp_path / "S1_2.fq.gz"
        out1 = tmp_path / "out_1.fq.gz"
        out2 = tmp_path / "out_2.fq.gz"
        json_r = tmp_path / "fastp.json"
        html_r = tmp_path / "fastp.html"

        cmd = runner.build_command(
            str(fq1), str(fq2),
            str(out1), str(out2),
            str(json_r), str(html_r),
            mode="adapter_only",
            extra_args="--dont_eval_duplication",
        )

        cmd_str = " ".join(cmd)
        assert "--dont_eval_duplication" in cmd_str

    def test_build_command_n_base_limit_override(self, tmp_path):
        """Test n_base_limit override"""
        runner = FastpRunner()

        fq1 = tmp_path / "S1_1.fq.gz"
        fq2 = tmp_path / "S1_2.fq.gz"
        out1 = tmp_path / "out_1.fq.gz"
        out2 = tmp_path / "out_2.fq.gz"
        json_r = tmp_path / "fastp.json"
        html_r = tmp_path / "fastp.html"

        cmd = runner.build_command(
            str(fq1), str(fq2),
            str(out1), str(out2),
            str(json_r), str(html_r),
            mode="adapter_only",
            n_base_limit=20,
        )

        cmd_str = " ".join(cmd)
        assert "--n_base_limit" in cmd_str
        assert "20" in cmd_str

    def test_is_sample_done_empty(self, tmp_path):
        """Test sample completion detection with empty directory"""
        assert not is_sample_done(tmp_path, "S1")

    def test_is_sample_done_partial(self, tmp_path):
        """Test sample completion detection with partial files"""
        sample_dir = tmp_path / "S1"
        sample_dir.mkdir()

        # Only fq1 exists
        (sample_dir / "S1_1.clean.fq.gz").write_bytes(b"test")

        assert not is_sample_done(tmp_path, "S1")

    def test_is_sample_done_complete(self, tmp_path):
        """Test sample completion detection with all files"""
        sample_dir = tmp_path / "S1"
        sample_dir.mkdir()

        # Create all output files
        (sample_dir / "S1_1.clean.fq.gz").write_bytes(b"test")
        (sample_dir / "S1_2.clean.fq.gz").write_bytes(b"test")
        (sample_dir / "fastp.json").write_text("{}")

        assert is_sample_done(tmp_path, "S1")

    def test_get_output_files_empty(self, tmp_path):
        """Test getting output files from empty directory"""
        sample_dir = tmp_path / "S1"
        sample_dir.mkdir()

        files = get_output_files(tmp_path, "S1")

        assert files["fq1"] is None
        assert files["fq2"] is None
        assert files["json"] is None
        assert files["html"] is None

    def test_get_output_files_complete(self, tmp_path):
        """Test getting output files from complete directory"""
        sample_dir = tmp_path / "S1"
        sample_dir.mkdir()

        (sample_dir / "S1_1.clean.fq.gz").write_bytes(b"test")
        (sample_dir / "S1_2.clean.fq.gz").write_bytes(b"test")
        (sample_dir / "fastp.json").write_text("{}")
        (sample_dir / "fastp.html").write_text("<html></html>")

        files = get_output_files(tmp_path, "S1")

        assert files["fq1"] is not None
        assert files["fq2"] is not None
        assert files["json"] is not None
        assert files["html"] is not None

    def test_parse_reads_dir_flat(self, tmp_path):
        """Test parsing flat directory structure"""
        (tmp_path / "S1_1.fq.gz").touch()
        (tmp_path / "S1_2.fq.gz").touch()
        (tmp_path / "S2_1.fq.gz").touch()
        # S2 missing R2

        samples = parse_reads_dir(
            tmp_path,
            r1_suffix="_1.fq.gz",
            r2_suffix="_2.fq.gz",
            fastq_pos="flat",
        )

        assert "S1" in samples
        assert "S2" not in samples  # Missing R2

    def test_parse_reads_dir_subdir(self, tmp_path):
        """Test parsing subdirectory structure"""
        s1_dir = tmp_path / "S1"
        s1_dir.mkdir()
        (s1_dir / "reads_1.fq.gz").touch()
        (s1_dir / "reads_2.fq.gz").touch()

        s2_dir = tmp_path / "S2"
        s2_dir.mkdir()
        (s2_dir / "reads_1.fq.gz").touch()
        # S2 missing R2

        samples = parse_reads_dir(
            tmp_path,
            r1_suffix="_1.fq.gz",
            r2_suffix="_2.fq.gz",
            fastq_pos="subdir",
        )

        assert "S1" in samples
        assert "S2" not in samples  # Missing R2

    def test_parse_reads_dir_recursive(self, tmp_path):
        """Test parsing recursive directory structure"""
        nested = tmp_path / "project" / "batch1" / "S1"
        nested.mkdir(parents=True)
        (nested / "data_1.fq.gz").touch()
        (nested / "data_2.fq.gz").touch()

        samples = parse_reads_dir(
            tmp_path,
            r1_suffix="_1.fq.gz",
            r2_suffix="_2.fq.gz",
            fastq_pos="recursive",
        )

        assert "S1" in samples


class TestFastpNewFeatures:
    """测试从 fastpv3.py 吸收的新功能"""

    def test_detect_fastq_structure_flat(self, tmp_path):
        """测试 flat 结构检测"""
        (tmp_path / "S1_1.fq.gz").touch()
        (tmp_path / "S2_1.fq.gz").touch()

        structures = detect_fastq_structure(tmp_path, ["_1.fq.gz", "_2.fq.gz"])

        assert "flat" in structures

    def test_detect_fastq_structure_subdir(self, tmp_path):
        """测试 subdir 结构检测"""
        s1_dir = tmp_path / "S1"
        s1_dir.mkdir()
        (s1_dir / "reads_1.fq.gz").touch()

        structures = detect_fastq_structure(tmp_path, ["_1.fq.gz"])

        assert "subdir" in structures

    def test_detect_fastq_structure_deep(self, tmp_path):
        """测试深层结构检测"""
        nested = tmp_path / "project" / "batch1" / "S1"
        nested.mkdir(parents=True)
        (nested / "data_1.fq.gz").touch()

        structures = detect_fastq_structure(tmp_path, ["_1.fq.gz"])

        assert "two-level or deeper" in structures

    def test_parse_reads_dir_auto(self, tmp_path):
        """测试自动检测解析"""
        s1_dir = tmp_path / "S1"
        s1_dir.mkdir()
        (s1_dir / "reads_1.fq.gz").touch()
        (s1_dir / "reads_2.fq.gz").touch()

        samples, structure = parse_reads_dir_auto(
            tmp_path,
            r1_suffix="_1.fq.gz",
            r2_suffix="_2.fq.gz",
        )

        assert "S1" in samples
        assert structure == "subdir"

    def test_parse_reads_dir_se_flat(self, tmp_path):
        """测试单端数据解析 - flat"""
        (tmp_path / "S1.fastq.gz").touch()
        (tmp_path / "S2.fastq.gz").touch()

        samples = parse_reads_dir_se(
            tmp_path,
            se_suffix=".fastq.gz",
            fastq_pos="flat",
        )

        assert "S1" in samples
        assert "S2" in samples

    def test_parse_reads_dir_se_subdir(self, tmp_path):
        """测试单端数据解析 - subdir"""
        s1_dir = tmp_path / "S1"
        s1_dir.mkdir()
        (s1_dir / "reads.fastq.gz").touch()

        samples = parse_reads_dir_se(
            tmp_path,
            se_suffix=".fastq.gz",
            fastq_pos="subdir",
        )

        assert "S1" in samples

    def test_is_sample_done_se(self, tmp_path):
        """测试单端样本完成检测"""
        sample_dir = tmp_path / "S1"
        sample_dir.mkdir()

        # 空目录
        assert not is_sample_done_se(tmp_path, "S1")

        # 完整文件
        (sample_dir / "S1.clean.fq.gz").write_bytes(b"test")
        (sample_dir / "fastp.json").write_text("{}")

        assert is_sample_done_se(tmp_path, "S1")

    def test_write_checked_file(self, tmp_path):
        """测试写入检测文件列表"""
        pe_samples = {"S1": ("/data/S1_1.fq.gz", "/data/S1_2.fq.gz")}
        se_samples = {"S2": "/data/S2.fastq.gz"}

        write_checked_file(tmp_path, pe_samples, se_samples)

        checked_file = tmp_path / "fastp_checked.txt"
        assert checked_file.exists()

        content = checked_file.read_text()
        assert "PE" in content
        assert "SE" in content
        assert "S1" in content
        assert "S2" in content