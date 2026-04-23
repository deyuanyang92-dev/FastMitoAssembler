# fastmito-v002 workflow flowchart

Date: 2026-04-23

This diagram summarizes the intended FastMitoAssembler v002 workflow integration. It is based on the current v002 design and the software research notes in `docs/software/`.

Renderable SVG companion:

```text
docs/design/fastmito-v002-flowchart.svg
```

## Mermaid

```mermaid
flowchart TD
    A[Input FASTQ batch<br/>paired-end by default] --> B{Optional fastp?}
    B -->|disabled by default| C[Raw / clean reads]
    B -->|adapter-only<br/>-Q -L| C0[fastp cleaned reads<br/>JSON + HTML report]
    C0 --> C

    C --> D{Subcommand / target}

    D -->|fma meangs<br/>meangs_all| M[MEANGS batch]
    D -->|fma novoplasty<br/>novoplasty_all| N[NOVOPlasty batch]
    D -->|fma getorganelle<br/>getorganelle_all| G[GetOrganelle batch]
    D -->|fma mitoz<br/>mitoz_all| Z[MitoZ annotate]
    D -->|fma mg-nov<br/>mg_nov_all| MN[MEANGS -> NOVOPlasty]
    D -->|fma mg-get<br/>mg_get_all| MG[MEANGS -> GetOrganelle]
    D -->|fma mg-nov-get<br/>mg_nov_get_all| MNG[MEANGS -> NOVOPlasty -> GetOrganelle]
    D -->|fma run<br/>all| FULL[Full chain]

    M --> MS[MEANGS candidate FASTA<br/>*_deep_detected_mito.fas]
    M --> MR[MEANGS report/QC<br/>source, length, topology=unknown]

    N --> NS{Seed source}
    NS -->|single seed| N1[one seed for all samples]
    NS -->|by-sample FASTA| N2[header first token matches sample]
    NS -->|MEANGS seed| N3[MEANGS candidate FASTA]
    N1 --> NO[NOVOPlasty config per sample]
    N2 --> NO
    N3 --> NO
    NO --> NF[NOVOPlasty FASTA<br/>{sample}.novoplasty.fasta]

    G --> GS{Seed / mode}
    GS -->|none| G0[GetOrganelle default database]
    GS -->|user seed| G1[user FASTA / genes]
    GS -->|MEANGS| G2[MEANGS candidate FASTA]
    GS -->|NOVOPlasty| G3[NOVOPlasty FASTA]
    G0 --> GO[GetOrganelle assembly]
    G1 --> GO
    G2 --> GO
    G3 --> GO
    GO --> GF[path_sequence.fasta<br/>graph/log retained]

    MN --> MNa[MEANGS]
    MNa --> MNb[NOVOPlasty config + run]
    MNb --> MNc[NOVOPlasty FASTA]

    MG --> MGa[MEANGS]
    MGa --> MGb[GetOrganelle -s MEANGS]
    MGb --> MGc[GetOrganelle path_sequence.fasta]

    MNG --> MNGa[MEANGS]
    MNGa --> MNGb[NOVOPlasty]
    MNGb --> MNGc[GetOrganelle -s NOVOPlasty]
    MNGc --> MNGd[GetOrganelle path_sequence.fasta]

    FULL --> F1[MEANGS]
    F1 --> F2[NOVOPlasty]
    F2 --> F3[GetOrganelle]
    F3 --> F4[MitoZ annotate]

    MS --> S[Summary collector]
    NF --> S
    GF --> S
    MNc --> S
    MGc --> S
    MNGd --> S
    F3 --> S

    S --> SF[summary FASTA<br/>{sample}.{software_or_pipeline}.fasta]
    S --> ST[summary_report.tsv<br/>length/topology/source/QC]
    SF --> Z
    Z --> ZA[MitoZ annotation outputs<br/>GBF, gene FASTA, summary.txt, plots]

    subgraph ExternalTools[External tools only - no algorithm reimplementation]
        M
        N
        G
        Z
    end
```

## Key Rules

- Python handles CLI, config merging, sample detection, seed parsing, summary collection, and Snakemake target dispatch.
- Snakemake runs external tools and composes the DAG.
- MitoZ defaults to `annotate`, not assembly.
- Chained workflows summarize the last assembler output:
  - `mg-nov`: NOVOPlasty
  - `mg-get`: GetOrganelle
  - `mg-nov-get`: GetOrganelle
  - `run`: GetOrganelle followed by MitoZ annotation
- MEANGS `scaffold_seeds.fas` is CWD-sensitive; batch execution must isolate per-sample working directories.
