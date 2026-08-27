# Candidate `lsmc-bio` Resource: Ganon2 Broad Blood/Oral Screen

Resource ID: `ganon2_blood_oral_ref_20260827_v1`

Status: candidate distribution resource; not published

Format version: `lsmc-bio.ganon2-resource/1.0`

## Purpose

This immutable Ganon 2.4.2 bundle is intended for high-quality short-read and
long-read, research-use screening of blood and oral-adjacent sequence. It is a
broad informational screen, not a clinical diagnostic, confirmatory assay, or
validated absence test. A positive taxonomic assignment remains a computational
screening result that may reflect homologous sequence, contamination, reference
misannotation, or an organism genuinely present in the specimen.

The candidate resource may be suitable for distribution by `lsmc-bio` after a
separate publication decision and release review. This document records the
technical and redistribution contract; it does not authorize uploading,
publishing, mirroring, or advertising the bundle outside LSMC.

## Immutable Bundle Contract

- Ganon: `2.4.2`.
- Filter type: HIBF.
- K-mer size: `27`.
- Window size: `51`.
- Maximum false-positive parameter: `0.001`.
- Every component in a bundle must use the same Ganon major/minor format and
  the same `k=27`, `w=51` pair. Mixing this bundle with incompatible prefixes
  is unsupported.
- The date-versioned resource ID is immutable. Source refreshes, taxonomy
  refreshes, component changes, or Ganon index-format changes require a new
  resource ID; an existing published object must never be overwritten.
- Snakemake input paths and mtimes remain the workflow dependency and rerun
  authority. The resource does not introduce a second hash-based dependency
  system for its large database objects.

## Components and Hierarchy

| Component | Classification hierarchy | Taxonomy | Contents |
|---|---:|---|---|
| `host_qc` | 1 | NCBI | LSMC GRCh38 no-alt analysis-set reference, PhiX174, UniVec Core, and explicit Illumina/ONT adapter sequences |
| `abfv_refseq_species1` | 2 | NCBI | One selected RefSeq assembly per archaeal, bacterial, fungal, and viral species |
| `broad_euk_refseq_species1` | 2 | NCBI | One selected RefSeq assembly per plant, protozoan, invertebrate, nonhuman mammalian, and other vertebrate species; Homo sapiens excluded |
| `genbank_species_gap_species1` | 2 | NCBI | One selected GenBank assembly only for species absent from the corresponding RefSeq organism groups; Homo sapiens excluded |
| `mgnify_human_oral_v1.0.1` | 3 | GTDB release 89 identifiers supplied by MGnify | Human Oral MGnify v1.0.1 representative genomes used only as an oral-rescue layer |

Hierarchy 1 is residual host/QC, hierarchy 2 is primary biological screening,
and hierarchy 3 is oral rescue for reads not assigned earlier. NCBI and GTDB
identities remain explicitly labeled and must not be merged into an invented
cross-taxonomy identifier.

The food and medically important parasite watchlists distributed beside this
document are validation and annotation lists. They do not create additional
classifiers and do not guarantee that every listed organism has an adequate,
unique, or current reference.

## Distribution Payload

A reviewed resource release should contain:

- the five `.hibf`, `.tax`, and `.info.tsv` component triplets;
- `bundle_components.tsv` with component order, hierarchy, taxonomy, label,
  relative prefix, and `27/51` compatibility fields;
- `build_context.tsv`, the `source_manifests/` accession and assembly-summary
  inventory, file-size inventory, build commands, Ganon version, source
  release/access dates, and build walltime;
- the food and parasite coverage watchlists and their validation results;
- this resource document and `lsmc_bio_resource_manifest.tsv`;
- source-specific attribution and redistribution review evidence current at
  the time of external publication.

Raw downloaded FASTAs are build intermediates and are intentionally excluded
from the resource payload. No human specimen reads, alignments, sample
identifiers, analysis outputs, credentials, or signed URLs belong in the
resource.

## Consumer Contract

The canonical internal object prefix is:

```text
s3://lsmc-dayoa-references-usw2/runtime_assets/tool_specific_resources/ganon2/ganon2_blood_oral_ref_20260827_v1/
```

The expected DYEC-mounted path is:

```text
/fsx/references/runtime_assets/tool_specific_resources/ganon2/ganon2_blood_oral_ref_20260827_v1/
```

An external `lsmc-bio` distribution should preserve the resource ID and
relative component prefixes. Consumers must use Ganon 2.4.2 or a separately
validated compatible version and must pass all five prefixes in the documented
hierarchy order. A consumer must fail clearly when a component, taxonomy file,
or compatibility field is missing; silent prefix discovery or fallback to a
different database is prohibited.

The first DayOA consumer implementation is release `16.0.11`. That release
identity records the integration contract; it does not by itself establish
that this candidate resource passed the pending SR/LR pilot or publication
gate.

## Update and Rebuild Policy

1. Pin the new source snapshots, taxonomies, Ganon version, `k/w`, and component
   selection rules before building.
2. Build in a fresh scratch allocation and stage to a new resource ID.
3. Validate component readability and compatibility, human exclusion outside
   `host_qc`, watchlist coverage, hierarchy labels, and a representative SR/LR
   classification.
4. Record source/accession manifests and measured build/runtime evidence.
5. Perform a fresh redistribution and attribution review. Upstream terms and
   individual submitted records can change independently of the index format.
6. Publish only under a separately approved release process. Never mutate an
   earlier version in place.

## Attribution and Redistribution Review

The combined bundle has no asserted single blanket data license. Before any
external distribution, `lsmc-bio` must retain an auditable review of every
source class:

- Ganon is distributed under the MIT license; retain its license and cite the
  Ganon project: <https://github.com/pirovc/ganon>.
- NCBI states that it places no restrictions on use or distribution of GenBank
  data, while warning that individual submitters may claim patent, copyright,
  or other rights: <https://www.ncbi.nlm.nih.gov/genbank/about/>.
- RefSeq is derived from public sequence data and is available through NCBI;
  preserve accession/source attribution and review the then-current NCBI terms:
  <https://www.ncbi.nlm.nih.gov/refseq/about/>.
- PhiX, UniVec, NCBI Taxonomy, RefSeq, and GenBank provenance must remain in the
  source manifest. The LSMC GRCh38 reference copy must be confirmed to derive
  from a redistributable public analysis-set source before external release.
- EMBL-EBI states that it adds no redistribution restriction beyond original
  data-owner rights and expects scientific attribution. Review the current
  terms at release time: <https://www.ebi.ac.uk/about/terms-of-use/>.
- Attribute MGnify and pin Human Oral catalogue `v1.0.1`; its documented
  catalogue is prokaryotic and biome-specific, not a general food, fungal,
  viral, plant, protozoan, or helminth database:
  <https://docs.mgnify.org/src/docs/mgnify-genomes.html>.

If any source or record cannot be cleared for the intended distribution, the
release must stop. Do not silently omit it, replace it, or infer a compatible
license.

## Known Limitations

- This is a breadth-oriented screen. `k=27`, `w=51` intentionally trades some
  sensitivity for smaller indexes and faster recurring queries; measured pilot
  results, not this design choice alone, characterize performance.
- One selected assembly per species limits strain diversity and may miss
  divergent or poorly assembled organisms. The GenBank gap layer improves
  species breadth but can include less-curated assemblies.
- K-mer/minimizer similarity is not proof of viability, pathogenicity,
  infection, causal relevance, or exact species identity.
- Low-complexity sequence, conserved regions, host homology, index false
  positives, taxonomic drift, contamination, and database contamination can
  create misleading assignments.
- No hit does not establish absence. Reads absent from the source CRAM, reads
  that cannot be materialized, and organisms missing from the bundle are not
  tested equivalently.
- The MGnify oral layer is prokaryotic oral enrichment only. Broad food,
  eukaryotic, fungal, viral, protozoan, and helminth coverage comes from the
  other components and remains reference-dependent.
- Results require independent confirmation before clinical, public-health,
  regulatory, or patient-management use.

## Publication Gate

An `lsmc-bio` publication requires a separate human authorization after the
resource build, export, object verification, compatibility validation, focused
SR/LR pilot, license/attribution review, and final payload inventory are all
terminal. Until then, describe this only as a candidate distribution resource.
