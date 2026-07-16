# Sentieon License Server us-west-2d Provisioning Ledger

Controlling request: provision a dedicated `t3.xlarge` Sentieon license-server
host in `us-west-2d`, assign an Elastic IP, prepare for Route 53 multivalue
round-robin, and return an exact FQDN request email for Sentieon.

Ledger path: `docs/plans/20260712T102020Z_sentieon_license_server_usw2d_ledger.md`

CloudFormation template:
`docs/plans/20260712T102020Z_sentieon_license_server_usw2d_cloudformation.yaml`

## Gate 0 Baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch/status: `jem-dev`; clean against `origin/jem-dev` before this ledger.
- AWS identity: account `108782052779`, profile `lsmc`, region `us-west-2`.
- Target AZ/VPC: `us-west-2d`, `vpc-06b01782f2abece1c`
  (`10.0.0.0/16`, `daylily-cs-us-west-twod`).
- Public subnet: `subnet-0e9acb65aba5a0330` (`10.0.0.0/24`), with an
  active Internet Gateway default route.
- Private compute subnet: `subnet-087a4872d0c34e642` (`10.0.1.0/24`).
- Public DNS owner: Route 53 zone `Z06611923OX2VPC09QNEJ` (`lsmc.bio`).
- Backend FQDN: `usw2d-01.sentieon.lsmc.bio`.
- Client service FQDN: `license.sentieon.lsmc.bio`.
- DNS design: public A records point to the EIP; an exact private
  `sentieon.lsmc.bio` split-horizon zone points the same names to the private
  address. Both service records are multivalue-ready.
- AMI: Canonical Ubuntu 22.04 LTS amd64
  `ami-0e1601cee784a69a2`, resolved from Canonical's public SSM path on
  2026-07-12. The root device is explicitly changed to encrypted `gp3`.
- Security boundary: no SSH ingress; TCP `8990` only from `10.0.0.0/16`; SSM
  management over outbound HTTPS; IMDSv2 required.
- Cost ownership assumption: shared platform service, tagged
  `CostCenter=platform` and `lsmc-cost-center=platform`.
- Installed-service boundary: the stack creates host readiness scaffolding but
  does not install Sentieon, a license file, or start `licsrvr`. Those require
  the vendor-issued FQDN-bound license.
- Elastic IP evidence: 15 allocations are already visible while the Service
  Quotas API reports 10. A new stack allocation may require an account quota
  increase; no existing address may be detached or reused by this task.
- Existing records/stacks: neither requested DNS name exists and CloudFormation
  stack `sentieon-license-usw2d-01` does not exist.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| GATE-001 | Inventory | Record repo, identity, VPC, subnet, DNS, AMI, quota, naming, and cost boundaries | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | Gate 0 baseline above |  | Current live AWS inventory recorded before mutation. |
| IAC-001 | CloudFormation | Define managed `t3.xlarge`, encrypted storage, SSM IAM, IMDSv2, SG, EIP, and outputs | SUCCESS | feature_implementation | Gate 2 | orchestrator | AWS `validate-template` passed; corrected template update reached `UPDATE_COMPLETE`; bootstrap rerun passed | Initial user-data stopped because Ubuntu lacked `/etc/motd.d`; fixed by creating it explicitly. CloudFormation drift reports only `/NetworkInterfaces/0/AssociatePublicIpAddress` because the separately managed EIP makes EC2 report a public association. | Template and live bootstrap agree. A reviewed attempt to change the declaration required instance replacement, so its unexecuted change set was deleted. The one documented EIP-association drift is operationally expected. |
| DNS-001 | Route 53 | Create backend and service public/private records with multivalue-ready service identity | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Public records resolve to `52.40.208.196`; private records resolve to `10.0.0.205`; both service records have `MultiValueAnswer=true`, identifier `usw2d-01` |  | Split-horizon backend and round-robin-ready client names are live. |
| DEPLOY-001 | EC2 | Deploy stack in `us-west-2d` with termination protection | SUCCESS | feature_implementation | Gate 2 | orchestrator | Stack `sentieon-license-usw2d-01` `UPDATE_COMPLETE`; termination protection `true`; instance `i-03c42907b08018d1a` is `t3.xlarge` in `us-west-2d` |  | Dedicated host is running and stack-managed. |
| EIP-001 | EC2 | Allocate and associate a new EIP without touching existing allocations | SUCCESS | feature_implementation | Gate 2 | orchestrator | `eipalloc-0c1ec16508fe480b3`, `52.40.208.196`, attached to `i-03c42907b08018d1a` |  | New EIP was allocated successfully; no existing allocation changed. |
| READY-001 | Validation | Verify instance state, AZ/type, EIP, DNS split horizon, SSM online, bootstrap marker, SG, and no active `licsrvr` | SUCCESS | contract_test | Gate 5 | orchestrator | EC2 status checks passed; SSM `Online` version `3.3.4793.0`; `cloud-init status --long` is `done` with no errors; marker present; hostname/FQDN correct; no TCP 8990 listener; Sentieon payload absent; encrypted 20 GiB `gp3` volume `vol-08a142d0b31d6421f` | Initial missing `/etc/motd.d` was repaired and the corrected cloud-init user module reran successfully. | Host infrastructure is ready but intentionally does not serve licenses until the vendor file and Sentieon 202503.03 are installed. |
| EMAIL-001 | Vendor handoff | Produce exact Sentieon email with backend FQDN, port, version, HA plan, and binding questions | SUCCESS | active_product_contract | Gate 5 | orchestrator | Email draft below |  | Exact vendor handoff is ready to send. |

## Acceptance Boundary

Infrastructure provisioning is complete only when every ledger row is terminal,
the stack is `CREATE_COMPLETE`, SSM is online, DNS is correct, and no Sentieon
daemon was started without the vendor-issued license. The license service itself
remains intentionally not operational until Sentieon returns that license.

## Deployment Receipt

- Stack: `sentieon-license-usw2d-01` (`UPDATE_COMPLETE`, termination protection
  enabled)
- Instance: `i-03c42907b08018d1a`, `t3.xlarge`, Ubuntu 22.04, `us-west-2d`
- Private address: `10.0.0.205`
- Elastic IP: `52.40.208.196` (`eipalloc-0c1ec16508fe480b3`)
- Backend FQDN: `usw2d-01.sentieon.lsmc.bio`
- Client endpoint: `license.sentieon.lsmc.bio:8990`
- Security group: `sg-004e7647782ff1cf9`; inbound TCP `8990` only from
  `10.0.0.0/16`; no SSH ingress
- IAM: only AWS-managed `AmazonSSMManagedInstanceCore`
- Storage: encrypted 20 GiB `gp3`, 3,000 IOPS, 125 MiB/s
- Runtime state: no Sentieon executable, license file, daemon, or TCP `8990`
  listener installed
- Expected CloudFormation drift: one property on the primary network interface,
  where the stack declares no auto-assigned address but EC2 reports a public
  association after the stack-owned EIP is attached

## Sentieon Email Draft

Subject: Cluster license request for us-west-2 server and Sentieon 202503.03

Hi,

Thank you for the deployment guidance. We have provisioned our first dedicated
Sentieon license server with the following stable identity:

- License-server FQDN: `usw2d-01.sentieon.lsmc.bio`
- Port: `8990`
- AWS region/AZ: `us-west-2` / `us-west-2d`
- Instance: dedicated `t3.xlarge`
- Elastic IP: `52.40.208.196`
- Planned client service name: `license.sentieon.lsmc.bio:8990`

Please issue a cluster license bound to
`usw2d-01.sentieon.lsmc.bio:8990` for Sentieon 202503.03, including PangenomeSV
and the Sentieon features currently available to us.

We plan to add license-server backends in this and other AWS regions and use
Route 53 multivalue DNS for distribution. Before we add those servers, could
you please confirm:

1. Whether each backend should receive a license bound to its individual FQDN.
2. Whether clients may connect through `license.sentieon.lsmc.bio:8990` while
   each server license is bound to its backend FQDN.
3. Whether algorithm/thread entitlements are pooled across parallel license
   servers or assigned independently to each server.
4. Your recommended backend count and entitlement sizing for up to 10,000
   concurrent jobs, including jobs using as many as 192 threads.

The server has outbound HTTPS connectivity for Sentieon validation. TCP 8990 is
restricted to our compute networks and will not be enabled as a service until
we receive the FQDN-bound license.

Thank you,
John Major

## Final Ledger State

- `SUCCESS`: 7
- `BLOCKED`: 0
- `FAIL`: 0
- Working statuses: 0
- All rows terminal: yes
- Infrastructure objective complete: yes
- License-service objective complete: intentionally pending the external
  vendor-issued license, outside this provisioning request
