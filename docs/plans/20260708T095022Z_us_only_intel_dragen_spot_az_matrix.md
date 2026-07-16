# US-Only Intel/DRAGEN Spot AZ Matrix - 20260708T095022Z

Read-only AWS screen using profile `lsmc`.

## Scope

- Intel template: `config/day_cluster/prod_cluster_nested_spot_mem_scratch_intel_avx512_expanded.yaml` (64 unique instance types)
- DRAGEN template: `config/day_cluster/prod_cluster_dragen_pcluster_image_rhel8.yaml` (1 unique instance types)
- DRAGEN template: `config/day_cluster/prod_cluster_dragen_native_ami_rhel8.yaml` (1 unique instance types)
- DRAGEN template: `config/day_cluster/prod_cluster_dragen_pcluster_image_rhel8_nofsx.yaml` (1 unique instance types)
- DRAGEN template: `config/day_cluster/prod_cluster_dragen_native_ami_rhel8_nofsx.yaml` (1 unique instance types)
- Union: 65 unique instance types
- Regions: us-east-1, us-east-2, us-west-1, us-west-2
- AZs: us-east-1a, us-east-1b, us-east-1c, us-east-1d, us-east-1e, us-east-1f, us-east-2a, us-east-2b, us-east-2c, us-west-1a, us-west-1b, us-west-2a, us-west-2b, us-west-2c, us-west-2d

## Method

- Spot presence means `ec2:DescribeSpotPriceHistory` returned at least one `Linux/UNIX` row for that exact instance type and AZ with `MaxResults=1`.
- `Y` means current/latest Spot price history is visible. `OFFERED_NO_SPOT` means EC2 reports the instance type offering in that AZ but Spot price history returned no row. `NOT_OFFERED` means neither an instance-type offering nor Spot price history was visible for that AZ.
- This mirrors the renderer failure mode: no Spot price-history row for a template instance type in the selected AZ can block render.

## Output files

- Long CSV: `docs/plans/20260708T095022Z_us_only_intel_dragen_spot_az_matrix_long.csv`
- Status matrix CSV: `docs/plans/20260708T095022Z_us_only_intel_dragen_spot_az_matrix_status_matrix.csv`
- Price matrix CSV: `docs/plans/20260708T095022Z_us_only_intel_dragen_spot_az_matrix_price_matrix.csv`
- Metadata JSON: `docs/plans/20260708T095022Z_us_only_intel_dragen_spot_az_matrix_metadata.json`

## Full-Coverage AZs

- `intel`: us-east-1a, us-east-1b, us-east-1d, us-west-2a, us-west-2b, us-west-2c
- `dragen`: us-east-1a, us-east-1b, us-east-1c, us-east-1d, us-west-2b, us-west-2c
- `all`: us-east-1a, us-east-1b, us-east-1d, us-west-2b, us-west-2c

## intel AZ coverage

| Region | AZ | Present | Missing | Coverage | Missing instance types |
|---|---:|---:|---:|---:|---|
| us-east-1 | us-east-1a | 64 | 0 | 100.0% | none |
| us-east-1 | us-east-1b | 64 | 0 | 100.0% | none |
| us-east-1 | us-east-1c | 61 | 3 | 95.3% | m8idb.96xlarge, r8idb.96xlarge, r8idn.96xlarge |
| us-east-1 | us-east-1d | 64 | 0 | 100.0% | none |
| us-east-1 | us-east-1e | 0 | 64 | 0.0% | c6i.32xlarge, c6i.metal, c6in.32xlarge, c6in.metal, c7i.48xlarge, c7i.metal-48xl, c8i.32xlarge, c8i.48xlarge, c8i.metal-48xl, c8id.96xlarge, c8id.metal-96xl, i4i.2xlarge, i4i.32xlarge, i4i.metal, i7i.2xlarge, i7i.48xl... |
| us-east-1 | us-east-1f | 60 | 4 | 93.8% | m8idb.96xlarge, m8idn.96xlarge, r8idb.96xlarge, r8idn.96xlarge |
| us-east-2 | us-east-2a | 62 | 2 | 96.9% | m8idb.96xlarge, m8idn.96xlarge |
| us-east-2 | us-east-2b | 62 | 2 | 96.9% | m8idb.96xlarge, m8idn.96xlarge |
| us-east-2 | us-east-2c | 62 | 2 | 96.9% | m8idb.96xlarge, m8idn.96xlarge |
| us-west-1 | us-west-1a | 47 | 17 | 73.4% | c8id.96xlarge, c8id.metal-96xl, m8id.96xlarge, m8id.metal-96xl, m8idb.96xlarge, m8idn.96xlarge, r6id.2xlarge, r6id.32xlarge, r6id.metal, r8id.96xlarge, r8id.metal-96xl, r8idb.96xlarge, r8idn.96xlarge, x8i.2xlarge, x8i... |
| us-west-1 | us-west-1b | 47 | 17 | 73.4% | c8id.96xlarge, c8id.metal-96xl, m8id.96xlarge, m8id.metal-96xl, m8idb.96xlarge, m8idn.96xlarge, r6id.2xlarge, r6id.32xlarge, r6id.metal, r8id.96xlarge, r8id.metal-96xl, r8idb.96xlarge, r8idn.96xlarge, x8i.2xlarge, x8i... |
| us-west-2 | us-west-2a | 64 | 0 | 100.0% | none |
| us-west-2 | us-west-2b | 64 | 0 | 100.0% | none |
| us-west-2 | us-west-2c | 64 | 0 | 100.0% | none |
| us-west-2 | us-west-2d | 55 | 9 | 85.9% | c6in.32xlarge, c6in.metal, r5n.2xlarge, r8idb.96xlarge, r8idn.96xlarge, x2idn.32xlarge, x2idn.metal, x2iedn.32xlarge, x2iedn.metal |

## dragen AZ coverage

| Region | AZ | Present | Missing | Coverage | Missing instance types |
|---|---:|---:|---:|---:|---|
| us-east-1 | us-east-1a | 1 | 0 | 100.0% | none |
| us-east-1 | us-east-1b | 1 | 0 | 100.0% | none |
| us-east-1 | us-east-1c | 1 | 0 | 100.0% | none |
| us-east-1 | us-east-1d | 1 | 0 | 100.0% | none |
| us-east-1 | us-east-1e | 0 | 1 | 0.0% | f2.6xlarge |
| us-east-1 | us-east-1f | 0 | 1 | 0.0% | f2.6xlarge |
| us-east-2 | us-east-2a | 0 | 1 | 0.0% | f2.6xlarge |
| us-east-2 | us-east-2b | 0 | 1 | 0.0% | f2.6xlarge |
| us-east-2 | us-east-2c | 0 | 1 | 0.0% | f2.6xlarge |
| us-west-1 | us-west-1a | 0 | 1 | 0.0% | f2.6xlarge |
| us-west-1 | us-west-1b | 0 | 1 | 0.0% | f2.6xlarge |
| us-west-2 | us-west-2a | 0 | 1 | 0.0% | f2.6xlarge |
| us-west-2 | us-west-2b | 1 | 0 | 100.0% | none |
| us-west-2 | us-west-2c | 1 | 0 | 100.0% | none |
| us-west-2 | us-west-2d | 0 | 1 | 0.0% | f2.6xlarge |

## Instance-Type Gaps

### intel instance-type gaps by region

| Instance type | Templates | Full regions | Partial/missing regions |
|---|---|---|---|
| c6i.32xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| c6i.metal | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| c6in.32xlarge | intel | us-east-2, us-west-1 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-2: present us-west-2a,us-west-2b,us-west-2c; missing us-west-2d |
| c6in.metal | intel | us-east-2, us-west-1 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-2: present us-west-2a,us-west-2b,us-west-2c; missing us-west-2d |
| c7i.48xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| c7i.metal-48xl | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| c8i.32xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| c8i.48xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| c8i.metal-48xl | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| c8id.96xlarge | intel | us-east-2, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-1: missing all 2 AZs |
| c8id.metal-96xl | intel | us-east-2, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-1: missing all 2 AZs |
| i4i.2xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| i4i.32xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| i4i.metal | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| i7i.2xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| i7i.48xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| i7i.metal-48xl | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| i7ie.2xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| i7ie.48xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| i7ie.metal-48xl | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| m6i.32xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| m6i.metal | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| m6id.32xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| m6id.metal | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| m6idn.32xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| m6idn.metal | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| m6in.32xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| m6in.metal | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| m7i.48xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| m7i.metal-48xl | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| m8i.32xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| m8i.48xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| m8i.metal-48xl | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| m8id.96xlarge | intel | us-east-2, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-1: missing all 2 AZs |
| m8id.metal-96xl | intel | us-east-2, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-1: missing all 2 AZs |
| m8idb.96xlarge | intel | us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1d; missing us-east-1c,us-east-1e,us-east-1f<br>us-east-2: missing all 3 AZs<br>us-west-1: missing all 2 AZs |
| m8idn.96xlarge | intel | us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d; missing us-east-1e,us-east-1f<br>us-east-2: missing all 3 AZs<br>us-west-1: missing all 2 AZs |
| r5.2xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| r5n.2xlarge | intel | us-east-2, us-west-1 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-2: present us-west-2a,us-west-2b,us-west-2c; missing us-west-2d |
| r6i.2xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| r6i.32xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| r6i.metal | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| r6id.2xlarge | intel | us-east-2, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-1: missing all 2 AZs |
| r6id.32xlarge | intel | us-east-2, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-1: missing all 2 AZs |
| r6id.metal | intel | us-east-2, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-1: missing all 2 AZs |
| r7i.2xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| r7i.48xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| r7i.metal-48xl | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| r8i.2xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| r8i.32xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| r8i.48xlarge | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| r8i.metal-48xl | intel | us-east-2, us-west-1, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e |
| r8id.96xlarge | intel | us-east-2, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-1: missing all 2 AZs |
| r8id.metal-96xl | intel | us-east-2, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-1: missing all 2 AZs |
| r8idb.96xlarge | intel | us-east-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1d; missing us-east-1c,us-east-1e,us-east-1f<br>us-west-1: missing all 2 AZs<br>us-west-2: present us-west-2a,us-west-2b,us-west-2c; missing us-west-2d |
| r8idn.96xlarge | intel | us-east-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1d; missing us-east-1c,us-east-1e,us-east-1f<br>us-west-1: missing all 2 AZs<br>us-west-2: present us-west-2a,us-west-2b,us-west-2c; missing us-west-2d |
| x2idn.32xlarge | intel | us-east-2, us-west-1 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-2: present us-west-2a,us-west-2b,us-west-2c; missing us-west-2d |
| x2idn.metal | intel | us-east-2, us-west-1 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-2: present us-west-2a,us-west-2b,us-west-2c; missing us-west-2d |
| x2iedn.32xlarge | intel | us-east-2, us-west-1 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-2: present us-west-2a,us-west-2b,us-west-2c; missing us-west-2d |
| x2iedn.metal | intel | us-east-2, us-west-1 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-2: present us-west-2a,us-west-2b,us-west-2c; missing us-west-2d |
| x8i.2xlarge | intel | us-east-2, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-1: missing all 2 AZs |
| x8i.32xlarge | intel | us-east-2, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-1: missing all 2 AZs |
| x8i.48xlarge | intel | us-east-2, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-1: missing all 2 AZs |
| x8i.metal-48xl | intel | us-east-2, us-west-2 | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1f; missing us-east-1e<br>us-west-1: missing all 2 AZs |

### dragen instance-type gaps by region

| Instance type | Templates | Full regions | Partial/missing regions |
|---|---|---|---|
| f2.6xlarge | dragen_native_ami_rhel8;dragen_native_ami_rhel8_nofsx;dragen_pcluster_image_rhel8;dragen_pcluster_image_rhel8_nofsx | none | us-east-1: present us-east-1a,us-east-1b,us-east-1c,us-east-1d; missing us-east-1e,us-east-1f<br>us-east-2: missing all 3 AZs<br>us-west-1: missing all 2 AZs<br>us-west-2: present us-west-2b,us-west-2c; missing us-west-2a,us-west-2d |

