"""
Tests for SpadesRunner
"""

import tempfile
from pathlib import Path
import pytest

from FastMitoAssembler.bin.runners._spades_runner import (
    SpadesRunner,
    SPADES_MODES,
    VALID_MODES,
    diagnose_spades_error,
    preflight_check,
)


class TestSpadesRunner:
    """SpadesRunner tests"""

    def test_init(self):
        """Test initialization"""
        runner = SpadesRunner(threads=16, memory_gb=64)
        assert runner.threads == 16
        assert runner.memory_gb == 64
        assert runner.shell_prefix == ""

    def test_init_with_prefix(self):
        """Test initialization with shell prefix"""
        runner = SpadesRunner(threads=16, shell_prefix="conda run -n spades ")
        assert runner.shell_prefix == "conda run -n spades "

    def test_valid_modes_exist(self):
        """Test all valid modes are defined"""
        expected_modes = {"default", "isolate", "meta", "rna", "plasmid",
                         "metaviral", "metaplasmid", "sc", "rnaviral", "shallow"}
        assert expected_modes.issubset(VALID_MODES)

    def test_modes_have_required_keys(self):
        """Test modes have required keys"""
        for mode, preset in SPADES_MODES.items():
            assert "description" in preset
            assert "flags" in preset
            assert "output_files" in preset
            assert preset["output_files"]  # non-empty

    def test_build_command_default(self, tmp_path):
        """Test building command with default mode"""
        runner = SpadesRunner()

        fq1 = tmp_path / "S1_1.fastq.gz"
        fq2 = tmp_path / "S1_2.fastq.gz"
        out_dir = tmp_path / "output"

        cmd = runner.build_command(str(fq1), str(fq2), out_dir, mode="default")

        cmd_str = " ".join(cmd)
        assert "spades.py" in cmd_str
        assert "-1" in cmd_str
        assert "-2" in cmd_str
        assert "-o" in cmd_str
        assert "--only-assembler" in cmd_str
        assert "--careful" in cmd_str
        assert "-t" in cmd_str
        assert "-m" in cmd_str

    def test_build_command_isolate(self, tmp_path):
        """Test building command with isolate mode"""
        runner = SpadesRunner()

        fq1 = tmp_path / "S1_1.fastq.gz"
        fq2 = tmp_path / "S1_2.fastq.gz"
        out_dir = tmp_path / "output"

        cmd = runner.build_command(str(fq1), str(fq2), out_dir, mode="isolate")

        cmd_str = " ".join(cmd)
        assert "--isolate" in cmd_str

    def test_build_command_meta(self, tmp_path):
        """Test building command with meta mode"""
        runner = SpadesRunner()

        fq1 = tmp_path / "S1_1.fastq.gz"
        fq2 = tmp_path / "S1_2.fastq.gz"
        out_dir = tmp_path / "output"

        cmd = runner.build_command(str(fq1), str(fq2), out_dir, mode="meta")

        cmd_str = " ".join(cmd)
        assert "--meta" in cmd_str

    def test_build_command_rna(self, tmp_path):
        """Test building command with rna mode"""
        runner = SpadesRunner()

        fq1 = tmp_path / "S1_1.fastq.gz"
        fq2 = tmp_path / "S1_2.fastq.gz"
        out_dir = tmp_path / "output"

        cmd = runner.build_command(str(fq1), str(fq2), out_dir, mode="rna")

        cmd_str = " ".join(cmd)
        assert "--rna" in cmd_str

    def test_build_command_shallow(self, tmp_path):
        """Test building command with shallow mode"""
        runner = SpadesRunner()

        fq1 = tmp_path / "S1_1.fastq.gz"
        fq2 = tmp_path / "S1_2.fastq.gz"
        out_dir = tmp_path / "output"

        cmd = runner.build_command(str(fq1), str(fq2), out_dir, mode="shallow")

        cmd_str = " ".join(cmd)
        assert "-k 21,33,55" in cmd_str
        assert "--meta" in cmd_str  # shallow mode uses meta for robustness

    def test_build_command_resume(self, tmp_path):
        """Test building command with resume"""
        runner = SpadesRunner()

        out_dir = tmp_path / "output"

        cmd = runner.build_command("", None, out_dir, mode="default", resume=True)

        cmd_str = " ".join(cmd)
        assert "--continue" in cmd_str
        assert "-o" in cmd_str
        # Resume mode should not have input files
        assert "-1" not in cmd_str
        assert "-2" not in cmd_str

    def test_build_command_extra_args(self, tmp_path):
        """Test passthrough of extra arguments"""
        runner = SpadesRunner()

        fq1 = tmp_path / "S1_1.fastq.gz"
        fq2 = tmp_path / "S1_2.fastq.gz"
        out_dir = tmp_path / "output"

        cmd = runner.build_command(
            str(fq1), str(fq2), out_dir,
            mode="default",
            extra_args="--disable-gpu-output",
        )

        cmd_str = " ".join(cmd)
        assert "--disable-gpu-output" in cmd_str

    def test_build_command_single_end(self, tmp_path):
        """Test building command with single-end data"""
        runner = SpadesRunner()

        fq1 = tmp_path / "S1.fastq.gz"
        out_dir = tmp_path / "output"

        cmd = runner.build_command(str(fq1), None, out_dir, mode="default")

        cmd_str = " ".join(cmd)
        assert "-s" in cmd_str
        assert "-1" not in cmd_str

    def test_is_sample_done_empty(self, tmp_path):
        """Test sample completion detection with empty directory"""
        runner = SpadesRunner()
        assert not runner.is_sample_done(tmp_path, "default")

    def test_is_sample_done_partial(self, tmp_path):
        """Test sample completion detection with partial files"""
        runner = SpadesRunner()

        # Only contigs.fasta exists
        (tmp_path / "contigs.fasta").write_text(">seq1\nACGT")

        assert runner.is_sample_done(tmp_path, "default")

    def test_is_sample_done_complete(self, tmp_path):
        """Test sample completion detection with all files"""
        runner = SpadesRunner()

        (tmp_path / "contigs.fasta").write_text(">seq1\nACGT")
        (tmp_path / "scaffolds.fasta").write_text(">seq1\nACGT")

        assert runner.is_sample_done(tmp_path, "default")

    def test_is_sample_done_rna_mode(self, tmp_path):
        """Test sample completion detection for rna mode"""
        runner = SpadesRunner()

        # rna mode checks for transcripts.fasta
        (tmp_path / "transcripts.fasta").write_text(">seq1\nACGT")

        assert runner.is_sample_done(tmp_path, "rna")

    def test_has_partial_state_empty(self, tmp_path):
        """Test partial state detection with empty directory"""
        runner = SpadesRunner()
        assert not runner.has_partial_state(tmp_path)

    def test_has_partial_state_with_params(self, tmp_path):
        """Test partial state detection with params.txt"""
        runner = SpadesRunner()

        (tmp_path / "params.txt").write_text("test")

        assert runner.has_partial_state(tmp_path)

    def test_has_partial_state_with_pipeline_state(self, tmp_path):
        """Test partial state detection with pipeline_state directory"""
        runner = SpadesRunner()

        pipeline_state = tmp_path / "pipeline_state"
        pipeline_state.mkdir()
        (pipeline_state / "stage1.txt").write_text("test")

        assert runner.has_partial_state(tmp_path)


class TestSpadesErrorDiagnosis:
    """SPAdes error diagnosis tests"""

    def test_diagnose_memory_error(self):
        """Test memory error diagnosis"""
        log = """
        Running SPAdes...
        Killed
        """
        result = diagnose_spades_error(log)
        assert "memory" in result["errors"]
        assert len(result["hints"]) > 0

    def test_diagnose_segmentation_fault(self):
        """Test segmentation fault diagnosis"""
        log = """
        Running SPAdes...
        Segmentation fault (core dumped)
        """
        result = diagnose_spades_error(log)
        assert "segmentation" in result["errors"]

    def test_diagnose_input_error(self):
        """Test input file error diagnosis"""
        log = """
        Error: Cannot open file /data/sample.fastq.gz
        """
        result = diagnose_spades_error(log)
        assert "input" in result["errors"]

    def test_diagnose_no_error(self):
        """Test no error found"""
        log = """
        Running SPAdes...
        Assembly completed successfully
        """
        result = diagnose_spades_error(log)
        assert len(result["errors"]) == 0

    def test_diagnose_multiple_errors(self):
        """Test multiple errors diagnosis"""
        log = """
        Error: Cannot open file
        Out of memory
        """
        result = diagnose_spades_error(log)
        assert "input" in result["errors"]
        assert "memory" in result["errors"]


class TestPreflightCheck:
    """Preflight check tests"""

    def test_preflight_missing_input(self, tmp_path):
        """Test preflight with missing input"""
        fq1 = tmp_path / "nonexistent_1.fastq.gz"
        fq2 = tmp_path / "nonexistent_2.fastq.gz"

        result = preflight_check(fq1, fq2, tmp_path, 16, 32)

        assert not result["ok"]
        assert len(result["issues"]) > 0

    def test_preflight_empty_input(self, tmp_path):
        """Test preflight with empty input"""
        fq1 = tmp_path / "S1_1.fastq.gz"
        fq2 = tmp_path / "S1_2.fastq.gz"
        fq1.touch()
        fq2.touch()

        result = preflight_check(fq1, fq2, tmp_path, 16, 32)

        assert not result["ok"]
        assert any("空" in issue for issue in result["issues"])

    def test_preflight_valid_input(self, tmp_path):
        """Test preflight with valid input"""
        fq1 = tmp_path / "S1_1.fastq.gz"
        fq2 = tmp_path / "S1_2.fastq.gz"
        fq1.write_bytes(b"test content" * 1000)
        fq2.write_bytes(b"test content" * 1000)

        result = preflight_check(fq1, fq2, tmp_path, 16, 32)

        # May have warnings but should pass basic checks
        assert len(result["issues"]) == 0 or "SPAdes" in " ".join(result["issues"])


class TestSpadesCleanIntermediate:
    """SPAdes intermediate file cleanup tests"""

    def test_clean_intermediate(self, tmp_path):
        """Test cleaning intermediate files"""
        runner = SpadesRunner()

        # Create intermediate directories
        (tmp_path / "tmp").mkdir()
        (tmp_path / "misc").mkdir()
        (tmp_path / "K21").mkdir()
        (tmp_path / "K33").mkdir()

        # Create output files
        (tmp_path / "contigs.fasta").write_text(">seq1\nACGT")
        (tmp_path / "scaffolds.fasta").write_text(">seq1\nACGT")
        (tmp_path / "params.txt").write_text("test")

        deleted = runner.clean_intermediate(tmp_path, dry_run=False)

        # Check intermediate directories are deleted
        assert not (tmp_path / "tmp").exists()
        assert not (tmp_path / "misc").exists()
        assert not (tmp_path / "K21").exists()
        assert not (tmp_path / "K33").exists()

        # Check output files are kept
        assert (tmp_path / "contigs.fasta").exists()
        assert (tmp_path / "scaffolds.fasta").exists()

    def test_clean_intermediate_dry_run(self, tmp_path):
        """Test dry run mode"""
        runner = SpadesRunner()

        (tmp_path / "tmp").mkdir()

        deleted = runner.clean_intermediate(tmp_path, dry_run=True)

        # Should report but not delete
        assert len(deleted) > 0
        assert (tmp_path / "tmp").exists()
