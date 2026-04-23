# FastMitoAssembler v002 beta release note

Version: `0.0.2b0`

Tag: `v002-beta`

Date: 2026-04-23

## Purpose

This beta packages the v002 modular workflow work for controlled testing. It is
not marked as a production release.

## Main changes

- Added independent stage commands:
  `fma meangs`, `fma novoplasty`, `fma getorganelle`, `fma mitoz`, and
  `fma summary`.
- Added chain commands:
  `fma mg-nov`, `fma mg-get`, and `fma mg-nov-get`.
- Split the Snakemake workflow into reusable rule modules under
  `FastMitoAssembler/smk/rules/`.
- Added shared Python workflow helpers for config merging, sample detection,
  target dispatch, seed handling, and summary collection.
- Added optional fastp configuration with adapter-only defaults.
- Added v002 design documents, software research notes, and a workflow
  flowchart.
- Updated package version metadata to `0.0.2b0`.

## Testing focus

- Confirm `fma --help` lists all v002 commands.
- Run dry-runs for independent and chain commands.
- Validate seed behavior for `single` and `by-sample` modes.
- Validate summary FASTA and `summary_report.tsv` on controlled examples.
- Run real MEANGS, NOVOPlasty, GetOrganelle, and MitoZ tests before using the
  beta as a production workflow.

## Install

```bash
pip install -U \
    git+https://github.com/deyuanyang92-dev/FastMitoAssembler.git@v002-beta
```

See `docs/INSTALL-v002.md` for the full installation and dry-run guide.
