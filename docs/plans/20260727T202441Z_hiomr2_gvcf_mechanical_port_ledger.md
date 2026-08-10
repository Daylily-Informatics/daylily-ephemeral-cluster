# HIOMR2 gVCF Mechanical Kitchen-Sink Port — Multi-Agent Control Ledger

Controlling request: replace the over-adapted HIOMR2 kitchen-sink port with a
mechanical copy of the working HIOMR kitchen-sink rules.  Copy rule bodies
intact; change only HIOMR2 configuration/parameter keys, rule names (suffix
`_gvcf`), and the established HIOMR2 gVCF input/output naming contract.

Controlling ledger: this file

Related execution ledger:
`docs/plans/20260727T092600Z_jem_hg003_4_hiomr2_take4_ledger.md`

Source checkout (headnode only):
`/fsx/analysis_results/preval-hiomr2/jem-hg003-4-hiomr2-take4/daylily-omics-analysis`

## Non-negotiable contracts

- The final five-shard `*.g.vcf.gz` is the only small-variant input for every
  downstream HIOMR2 consumer.  No downstream rule may consume a shard, an
  SNV-VCF compatibility link, a re-called VCF, or an independently created
  reference callset.
- The five scoped shard gVCFs and indexes are declared `temp()` in the new
  rules.  They may be removed only after their final aggregate gVCF has been
  consumed successfully.
- Until this port is accepted, every DayOA dry-run and live attempt includes
  `--keep-temp`, even though the rule outputs are `temp()`.
- Preserve the HIOMR2 analysis-unit wildcard filename pattern.  The wildcard
  named `sample` resolves to the analysis-unit UID; it is not the short
  specimen label (for example, `HG003`).
- Use the DYEC interactive ubuntu login shell and named headnode tmux session;
  invoke workflow work through `dy-r`, never raw Snakemake.
- No source edit, controller relaunch, Slurm action, or commit/push occurs
  while the owner-directed stop is in effect.  The live rows below require a
  new explicit go-ahead.

## Multi-agent write isolation

This plan is intentionally parallel only for read-only inventory and review.
Exactly one agent may own a source-writing row at a time, and only after an
analysis-root write lock is held.  The orchestrator owns the ledger, merges
evidence, and is the only agent allowed to transition cross-row acceptance.

| Role | Permitted scope | Prohibited scope |
|---|---|---|
| Orchestrator | Ledger, parity decision, lock/release coordination, final acceptance | Concurrent source edits |
| Agent A — source porter | The copied HIOMR2 gVCF rule block only | Catalog/profile edits; headnode launch |
| Agent B — contract reviewer | Read-only HIOMR-to-HIOMR2 parity map and focused tests | Source writes; Slurm actions |
| Agent C — launch validator | Read-only plan review, then a single tmux `dy-r` attempt after Gate 4 | Source edits; job manipulation |

## Gate 0 — inventory freeze and current stop state

- Local coordinator repo at `2026-07-27T20:24:41Z`:
  `main...origin/main`, with numerous pre-existing untracked backups, ledgers,
  reports, and temporary artifacts.  They are not part of this port.
- The headnode source checkout has uncommitted port-test work.  Do not stage
  or discard it until Agent A has classified every difference against the
  source HIOMR rule bodies.
- Live evidence from the stopped test: SegDup job `207` failed because the
  current HIOMR2 wrapper read a CRAM without passing its declared reference to
  `samtools view`; the rule had diverged from the HIOMR body.  The two Mito
  jobs (`194`, `203`) completed naturally before a guarded cancellation could
  take effect.  No unrelated job was touched.
- The latest guard check reported a write lock owned by
  `codex-hiomr2-port-20260727`, but treated it as foreign to the present
  process.  Do not take it over silently; release or takeover needs explicit
  owner/approval handling before a future write or launch.
- Read-only source sweeps already establish that HIOMR derives its primary
  FASTA from `supporting_files.files.huref.fasta.name`, while HIOMR2 derives it
  from `sentdhiomr2.reference_fasta`.  No literal genomic FASTA is embedded in
  either rule file; the current `hg38_broad` path is a test-config override.

## Row ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Orchestrator | Freeze the current source, live-job, lock, and dirty-worktree baseline before replacement | SUCCESS | plan_amendment | Gate 0 | Orchestrator | Gate 0 notes above; current test jobs 194/203 completed, 197/198/199/207 failed, no unrelated job action |  | Baseline recorded; no implementation follows during the stop. |
| P-001 | DayOA source | Inventory the exact HIOMR kitchen-sink rule set, helper functions, targets, and consumer edges to be cloned | OPEN | feature_implementation | Gate 1 | Agent B | `workflow/rules/sent_hybrid_ilmn_ont_modular.refactored.smk`; current target area includes `produce_sentdhiomr_*` specialty targets |  |  |
| P-002 | DayOA source | Map each HIOMR source symbol to a HIOMR2 `_gvcf` symbol, allowing only config/parameter, rule-name, and path substitutions | OPEN | contract_test | Gate 1 | Agent B | Create a reviewed substitution table with every allowed delta and no unlisted behavioral delta |  |  |
| P-003 | DayOA source | Replace the bespoke HIOMR2 specialty wrappers with complete copies of the corresponding HIOMR rule bodies | OPEN | feature_implementation | Gate 1 | Agent A | Current divergent wrappers: `sentdhiomr2_mito_call`, `sentdhiomr2_segdup_gene`, and other specialty rules in `workflow/rules/sent_hybrid_ilmn_ont_modular2.smk` |  |  |
| P-004 | DayOA source | Name copied rules `*_gvcf` and apply the approved HIOMR2 config/parameter substitutions only | OPEN | feature_implementation | Gate 1 | Agent A | P-002 substitution table; `sentdhiomr2.reference_fasta` and existing analysis-unit helpers |  |  |
| P-005 | DayOA source | Make the final five-shard `*.g.vcf.gz` plus `.tbi` the sole downstream small-variant contract | OPEN | active_product_contract | Gate 3 | Agent A | Current port exposes `HIOMR2_FIVE_SHARD_GVCF`; remove all alternate downstream SNV/compatibility/reference paths from consumers |  |  |
| P-006 | DayOA source | Declare each five-shard gVCF and index `temp()` while retaining the final five-shard aggregate gVCF and index as non-temporary outputs | OPEN | config_or_startup_contract | Gate 2 | Agent A | `scoped_gvcf_shards` covers 1-22,X,Y,M; final aggregate is the durable handoff |  |  |
| P-007 | DayOA source | Preserve the HIOMR2 output naming pattern using analysis-unit UID, not the short sample/specimen label | OPEN | contract_test | Gate 1 | Agent B | Current wildcard evidence: `{sample}` resolves to the HG003/HG004 analysis-unit UID |  |  |
| P-008 | DayOA source | Remove independent gVCF recaller/reference/VCF-compatibility consumer paths from the kitchen-sink target unless a reviewed HIOMR body contains them | OPEN | removable_compatibility_debt | Gate 1 | Agent A | Current bespoke target includes `sentdhiomr2_inflection_vcf_compat`, CLI reference gVCF, and comparison additions |  |  |
| P-009 | DayOA tests | Add focused parity tests that fail on a rule-body difference outside the approved substitution map | OPEN | contract_test | Gate 1 | Agent B | Test must assert copied command bodies retain HIOMR behavior and confirm required `-T` for any CRAM decode is inherited/configured |  |  |
| P-010 | Command catalog | Reconcile the HIOMR2 kitchen-sink catalog target with the copied `_gvcf` rules and hg38 contract; preserve the separate test-only `hg38_broad` exception | OPEN | config_or_startup_contract | Gate 2 | Agent B | Existing catalog changes and `config/hiomr2_hg003_again_full_chrom_shards.yaml` |  |  |
| P-011 | Headnode staging | Classify all dirty/untracked headnode artifacts and stage only approved source/config/test files after source acceptance | OPEN | feature_implementation | Gate 4 | Orchestrator | Headnode checkout is dirty; do not use blanket `git add` |  |  |
| P-012 | Headnode dry run | Run the exact tmux `dy-r` command with `--rerun-triggers mtime -n --keep-temp`; prove final-gVCF-only consumers and no completed-work replay | BLOCKED | contract_test | Gate 4 | Agent C | Owner-directed stop; existing analysis-root write lock requires owner-safe release/takeover; no live action permitted | Stop instruction and locked-root ownership | Await explicit resume plus lock resolution. |
| P-013 | Headnode live proof | After P-012 review, run the identical command without `-n`, retaining `--keep-temp`, and observe submissions only through standard DayOA/Slurm handling | BLOCKED | feature_implementation | Gate 4 | Agent C | Requires P-012 SUCCESS and explicit resume | Stop instruction | Await explicit resume. |
| P-014 | Acceptance | Verify controller `RETURN CODE: 0`, final aggregate gVCF/tbi, all downstream outputs, source parity, and no shard cleanup while `--keep-temp` is active | BLOCKED | contract_test | Gate 5 | Orchestrator | Requires P-013 SUCCESS | Stop instruction | Await explicit resume and terminal controller evidence. |
| P-015 | Git | Commit and push only the approved, live-proven source/config/test changes from the headnode | BLOCKED | feature_implementation | Gate 5 | Orchestrator | User requires no commit before Slurm submission and proof | Stop instruction; P-014 incomplete | Await explicit resume and accepted live proof. |

## Exact future launch contract (not authorized while stopped)

Run in the persistent headnode tmux pane after `source dyoainit` and
`dy-a slurm hg38` (or the explicitly approved test-only `hg38_broad` setup):

```bash
dy-r <approved-hiomr2-gvcf-kitchensink-target> -j 200 -p -k -T 0 \
  --configfile config/hiomr2_hg003_again_full_chrom_shards.yaml \
  --config 'genome_build=hg38_broad' 'aligners=["sentmm2ont"]' \
  'dedupers=["na"]' 'snv_callers=["sentdhiomr2"]' 'sv_callers=[]' \
  'htd_callers=["smn12"]' use_fq_data_starting_hrs=0 \
  use_fq_data_up_to_hrs=25 --rerun-triggers mtime --rerun-incomplete --keep-temp -n
```

Only after the reviewed dry-run excludes already-complete work, use the same
command without `-n`.  The production catalog default remains `hg38`; the
`hg38_broad` setting above is solely the user-approved port-test exception.

## Final report (currently not terminal)

All rows terminal: no

Objective complete: no

Status counts:

- SUCCESS: 1
- OPEN: 10
- BLOCKED: 4
- IN_PROGRESS: 0
- ATTEMPTING_BUGFIX: 0
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0

Residual risks:

- The current HIOMR2 source is an over-adapted port and must not be accepted
  merely because individual wrappers can be patched.
- A write lock is present but is foreign to the present process; no silent
  takeover is permitted.
- No final rule set, dry run, live controller, or commit has been accepted
  under this revised mechanical-port contract.

## Amendment — 2026-07-27 HIOMR Kitchen-Sink specialty parity

The user resumed the reporting/test lane and clarified that HIOMR2 must carry
every HIOMR Kitchen-Sink specialty rule that the empirical HIOMR run executes.
In particular, HIOMR2 must add the independent Sniffles2 SV callset and the
ROH/UPD screen; neither may be represented by LongReadSV or omitted merely
because the initial HIOMR2 target did not list it.

The final merged five-shard gVCF (one gVCF plus one index per analysis unit)
remains the only small-variant downstream input.  The five shard gVCFs remain
preserved intermediates in this repair: do not modify the frozen caller,
shard-alias, or concat-rule bodies, and continue testing with `--keep-temp`.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| A-001 | DayOA source | Add HIOMR2-native downstream paths and a mechanical `sentdhiomr2_gvcf_sniffles2` copy of the HIOMR-family Sniffles2 rule | SUCCESS | feature_implementation | Gate 1 | Orchestrator | Headnode source adds `HIOMR2_SNIFFLES2_*`, `sentdhiomr2_gvcf_sniffles2`, analysis-unit output names, and matching `sniffles2_*` profile values; new Python helpers compile. | Missing ported specialty rule | Implemented; frozen gVCF caller, shard alias, and concat body were not edited. |
| A-002 | DayOA source | Add HIOMR2-native downstream paths and a mechanical `sentdhiomr2_gvcf_roh_upd_screen` copy consuming the merged final gVCF/index | SUCCESS | feature_implementation | Gate 1 | Orchestrator | Headnode source adds `sentdhiomr2_gvcf_roh_upd_screen` and `workflow/scripts/sentdhiomr2_gvcf_roh_upd_screen.py`; its only small-variant inputs are `HIOMR2_FIVE_SHARD_GVCF` and its `.tbi`. | Missing ported specialty rule | Implemented with biological VCF sample validation and analysis-unit UID artifacts. |
| A-003 | DayOA reporting | Produce and stage HIOMR2 MultiQC rows for merged gVCF, CNVscope, LongReadSV, SegDup, TIDDIT, Sniffles2, and ROH/UPD | SUCCESS | feature_implementation | Gate 1 | Orchestrator | New `sentdhiomr2_gvcf_variant_outputs_custom_data` plus `workflow/scripts/sentdhiomr2_gvcf_variant_outputs_mqc.py` stages all seven native TSVs into final MultiQC. | Missing mechanical reporting sibling | No independent/reference gVCF or compatibility-VCF row is accepted by the new report script. |
| A-004 | Headnode dry run | Run the authorized exact `dy-r` Kitchen-Sink plus analytical-package command with `--rerun-triggers mtime --rerun-incomplete --keep-temp -n` after A-001–A-003 | SUCCESS | contract_test | Gate 4 | Orchestrator | 2026-07-27 headnode tmux `jem_hg003_4_hiomr2_take4_20260727`, RnD, hg38_broad: `RETURN CODE: 0`; 264 planned jobs. It schedules `sentdhiomr2_gvcf_sniffles2` (2), `sentdhiomr2_gvcf_roh_upd_screen` (2), `sentdhiomr2_gvcf_variant_outputs_custom_data`, ExpansionHunter, native CNVscope/LongReadSV/SegDup/TIDDIT reporting, and no `sentdhiomr2_global_gvcf`, shard, or concat rule. |  | The two final merged gVCF/index pairs and all ten preserved shard gVCF/index pairs exist before launch; no live run submitted. |

## Commit receipt — 2026-07-27

The user explicitly authorized committing and pushing the current reviewed code
state before live workflow proof.  On the headnode as `ubuntu`, commit
`b4892cde` (`Port HIOMR2 Kitchen-Sink reporting`) was created and pushed to
`origin/codex/hiomr2-kitchensink-frozen-core`.

At the user's follow-up direction, annotated non-`v` release tag `13.0.60`
was created on the exact `b4892cde` commit (`git cat-file -t 13.0.60` returned
`tag`) and pushed to `origin`.  The preceding highest tag was `13.0.59`.

The commit contains only the eight reviewed source/config/test files: the
Slurm profile template, MultiQC configuration and rule, the HIOMR2 modular
rule, the two new HIOMR2 reporting scripts, and the existing LongTR rule/test
adjustment.  It deliberately excludes the generated profile `.hold` deletion,
analysis manifests, backup directory, staged workflow artifacts, and all
pipeline checkpoint files.  The staged whitespace check, both new-script
compilations, and the headnode dry-run were successful.  The analysis-root
write lock was released after the push.

## Live launch receipt — 2026-07-27

After the user explicitly directed the launch, the exact approved `dy-r`
Kitchen-Sink plus analytical-package command was sent in the persistent
`jem_hg003_4_hiomr2_take4_20260727` ubuntu tmux session without `-n`, retaining
`--rerun-triggers mtime --rerun-incomplete --keep-temp`. The controller accepted
both HG003 and HG004 analysis units, provisioned the required environments, and
submitted Slurm jobs. Initial read-only `squeue` evidence: jobs 208–225 were
`CF` (expected node configuration) and job 226 was pending for
`sentdhiomr2_gvcf_sniffles2`. No Slurm intervention was performed.

## Monitor evidence — 2026-07-27T23:28:12Z

The live controller remains active in `jem_hg003_4_hiomr2_take4_20260727` and
reported 25/264 steps (9%) complete at its latest completed-status line. Read-only
Slurm evidence shows broad active execution, including both HIOMR2 Sniffles2
jobs, both ROH/UPD jobs, SegDup, VEP, ExpansionHunter inputs, and related
Kitchen-Sink work. There is no node-loss evidence.

Observed non-spot failures (no intervention made):

- TIDDIT for both analysis units fails inside its current Conda environment:
  `pysam.index("-c", ...)` raises `OSError: No such file or directory: '-c'`.
- Peddy for both analysis units fails because the PED sample IDs are analysis-unit
  UIDs while the gVCF-derived VCF samples are `HG003` and `HG004`; Peddy exits
  `error: no samples from VCF found in ped`.
- The two analytical-package jobs fail safely because the target package roots
  for batch `this-time-go` already exist and the package rule refuses replacement.

Per the controller contract, do not overwrite existing package roots or perform
Slurm intervention. The controller continues with `-k`; source-backed repair is
not authorized by this monitor/status check.

## Amendment — HIOMR2 take5 repair and fresh proof

The user authorized a versioned repair and a fresh take5 proof run. The active
take4 controller remains untouched: it retains its already-loaded workflow plan
and existing package-root contract. Repair work will occur on a new feature
branch/worktree, then be released as a new annotated tag for the fresh clone.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| T5-000 | Gate 0 | Freeze take4 live evidence, source branch, and dirty generated-artifact boundary before repairs | SUCCESS | plan_amendment | Gate 0 | Orchestrator | Active controller 25/264 steps; branch/tag `b4892cde`/`13.0.60`; generated artifacts excluded from source commits; clean isolated `/tmp/hiomr2-take5-repair` worktree created on `codex/hiomr2-take5-repair` |  | Active take4 source is not edited while its controller is running. |
| T5-001 | DayOA source | Repair TIDDIT runtime failure with a new immutable environment contract and rule reference | ATTEMPTING_BUGFIX | feature_implementation | Gate 1 | Orchestrator | Added `workflow/envs/tiddit_v0.2.yaml` with `tiddit==3.9.7`, Python 3.11, and modern channel priority; template now references v0.2. Exact smoke test: `pysam 0.24.0 CSI_OPTIONS_OK` for the failing `-c/-m/-@` form. | Current TIDDIT/pysam ABI/API mismatch | Await source diff, focused checks, and fresh take5 dry run. |
| T5-002 | DayOA source | Repair Peddy by passing biological VCF sample IDs into its PED while preserving analysis-unit artifact names | ATTEMPTING_BUGFIX | feature_implementation | Gate 1 | Orchestrator | `peddy.smk` now resolves a strict `sentdhiomr2` VCF sample through `_hiomr2_sample_name`; PED individual ID becomes biological while path/family ID remain analysis-unit UID. | HIOMR2 output identity was incorrectly used as VCF sample identity | Await source diff, focused checks, and fresh take5 dry run. |
| T5-003 | Packaging contract | Preserve the explicit no-overwrite analytical package-root behavior | SUCCESS | legitimate_safety_handling | Gate 4 | Orchestrator | take4 logs reject pre-existing `this-time-go` roots; take5 is a new analysis root |  | No fallback overwrite; a fresh clone supplies isolated delivery roots. |
| T5-004 | Release | Commit reviewed repair plus active Kitchen-Sink source surface to a feature branch; cut and push next annotated non-v semver tag | OPEN | feature_implementation | Gate 5 | Orchestrator | Current release is `13.0.60` on `b4892cde` |  |  |
| T5-005 | Headnode clone | Create fresh `hiomrks-take5` analysis with the new explicit DayOA tag | OPEN | feature_implementation | Gate 4 | Orchestrator | User explicitly requested `day-clone -t <new-dayoa-ver> -d hiomrks-take5` |  |  |
| T5-006 | Fresh dry run | Stage the approved full-coverage HG003/HG004 ILMN + ONT [0,25] inputs and run HIOMR2 Kitchen-Sink plus analytical packaging at `-j 300 -p -T 0 -n`, without `-k` | OPEN | contract_test | Gate 4 | Orchestrator | User explicitly specified no `-k` |  |  |
| T5-007 | Fresh live proof | Run the identical take5 command without `-n` only after T5-006 RC 0 and plan review | OPEN | feature_implementation | Gate 4 | Orchestrator | User expressly authorized conditional live run |  |  |

## Take5 release and dry-run receipt — 2026-07-28T00:54Z

- Focused source checks passed on the headnode: `50 passed` across the HIOMR2
  core, alignment, Inflection contract/package, and ExpansionHunter suites.
  DAY-EC catalog mirror/validation checks also passed (`16 passed`).
- DayOA feature branch `codex/hiomr2-take5-repair` was pushed at `00528be6` and
  annotated tag `13.0.64` was created on that exact commit and pushed. The
  DYEC catalog update is separately pushed at
  `codex/hiomr2-take5-catalog` commit `17c26f58`; its `hiomr2` and analytical
  HIOMR2 kitchen-sink commands now use the take5 full-chromosome overlay,
  hg38, `-j 300 -p -T 0` without `-k`, `[0,25)`, `--keep-temp`, RnD-compatible
  specialty callers, and `this-time-go` for analytical packaging.
- In the required one-pane Ubuntu login-shell tmux session
  `hiomrks_take5_20260727`, `day-clone -t 13.0.64 -d hiomrks-take5` completed
  at `/fsx/analysis_results/preval-hiomr2/hiomrks-take5/daylily-omics-analysis`.
  A DYEC write visit and lock were recorded before staging. The active six
  manifests are a backed-up exact take4 input copy with only their
  analysis-unit namespace changed to `HIOMRKS-TAKE5`; the source input IDs and
  full ILMN plus three ONT inputs per sample were retained.
- `source dyoainit` and `dy-a slurm hg38` completed. The exact take5 `dy-r`
  dry-run returned `RETURN CODE: 0` and planned 292 jobs. It includes ten
  five-shard gVCFs (five per HG003/HG004), two final concats, two hard VCFs,
  ExpansionHunter, Sniffles2, ROH/UPD, SMN copy number, Ganon2, Peddy, VEP, and
  the analytical package. No `LongTR` or `sourmash` rule is planned.
- Take4 is still active and untouched. Read-only controller evidence reports
  `179 of 264 steps (68%) done` in `jem_hg003_4_hiomr2_take4_20260727`; at the
  snapshot there were no queued/running Slurm jobs matching take4/HIOMR2.
  Its retained controller may submit more work. The requested controller/job
  kill needs the separate, immediately-before-action confirmation required by
  the operating contract; do not submit take5 live until that confirmation.

## Take4 stop and take5 RnD live-retry receipt — 2026-07-28T01:53Z

- User supplied the required explicit second approval and confirmation token
  `1957c4a3d565593a`. DYEC took over the exact take4 kill lock, stopped only
  tmux controller `jem_hg003_4_hiomr2_take4_20260727`, and issued `scancel`
  for the 48 then-active jobs whose `WorkDir` was the take4 analysis root.
  A fresh process and queue read confirmed no remaining take4 controller
  process or active take4 job; the kill lock was released.
- The first approved take5 live attempt completed its two local setup steps,
  but its first Slurm submission was rejected before acceptance because the
  session inherited `DAY_PROJECT=preval-hiomr2`; that registry lookup is
  intentionally empty. No take5 Slurm job was accepted by that attempt.
- The supported DayOA submit input is `DAY_PROJECT`, which its Slurm helper
  turns into sbatch `--comment`. After a config-qualified `dy-r --unlock`
  returned RC 0 for the stale failed-controller lock, the persistent Ubuntu
  tmux session retried the identical live command with `DAY_PROJECT=RnD`.
- The retry is live. DYEC accepted `RnD` (cap `$500`, recorded spend `$0`,
  allowed freshness threshold `2160h`) and submitted job `442`; the first
  observed take5 jobs `434`–`442` are configuring with `Comment=RnD`.
  The controller reports 2/290 setup steps complete. No further Slurm action
  was performed.

## Take5 status evidence — 2026-07-28T03:39Z

- The live `hiomrks_take5_20260727` controller process tree remains present
  (`bin/day_run` and its `snakemake` child), at 61/290 steps (21%) on its
  latest controller line. Active work is limited to HG004 TIDDIT and site-mix
  contamination pileups; all observed take5 jobs carry the `RnD` Slurm comment.
- Kitchen-sink specialty work is partly successful: both Sniffles2 and
  LongReadSV calls, CNVscope, SMN copy number, mitochondrial calling,
  Ganon2 quick metagenomics, AlignStats, coverage, and multiple sex/relatedness
  prerequisites have completed for the shown analysis units.
- The final five-shard gVCF and Inflection package are not present. All five
  HG004 five-chromosome gVCF shard jobs failed (`474`, `475`, `477`, `482`,
  `489`, each `ExitCode=1:0`), so their concat, hard VCF, and dependent
  packaging work cannot complete.
- Source-backed failure: each failed shard invokes Sentieon DNAscope gVCF mode
  with an LR CRAM reheadered to `<analysis_unit>-lr` while the SR CRAM retains
  a different sample header. Sentieon rejects the two-sample invocation with
  `DNAscope: Only a single sample is allowed in GVCF emit mode`. No controller,
  Slurm, source, or output intervention was made during this read-only status
  check.

### Follow-up evidence — 2026-07-28T03:43Z

Accounting shows exactly five submitted five-chromosome shard gVCF jobs, all
for HG004 and all failed. No HG003 shard job has been submitted, and neither an
HG003 nor HG004 shard completion marker or gVCF output exists. Thus HG003 has
not succeeded; it has not reached the gVCF-shard execution stage.
