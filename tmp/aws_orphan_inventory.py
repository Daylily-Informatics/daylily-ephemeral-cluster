#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from typing import Any

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError


def name_from_tags(tags: list[dict[str, str]] | None) -> str:
    for tag in tags or []:
        if tag.get("Key") == "Name":
            return tag.get("Value", "")
    return ""


def client(session: boto3.Session, service: str, region: str):
    return session.client(service, region_name=region)


def call(out: list[dict[str, Any]], region: str, service: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (ClientError, EndpointConnectionError) as exc:
        out.append(
            {
                "region": region,
                "service": service,
                "kind": "api_error",
                "severity": "info",
                "reason": str(exc),
            }
        )
        return None


def paginate(c, operation: str, **kwargs):
    paginator = c.get_paginator(operation)
    for page in paginator.paginate(**kwargs):
        yield page


def add(out, region, service, kind, identifier, severity, reason, **extra):
    item = {
        "region": region,
        "service": service,
        "kind": kind,
        "id": identifier,
        "severity": severity,
        "reason": reason,
    }
    item.update({k: v for k, v in extra.items() if v not in (None, "", [], {})})
    out.append(item)


def inventory_region(session: boto3.Session, region: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    now = dt.datetime.now(dt.timezone.utc)

    ec2 = client(session, "ec2", region)
    response = call(out, region, "ec2", ec2.describe_instances)
    if response:
        for reservation in response.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                state = inst.get("State", {}).get("Name")
                if state == "terminated":
                    continue
                iid = inst.get("InstanceId")
                name = name_from_tags(inst.get("Tags"))
                launch = inst.get("LaunchTime")
                age_days = (now - launch).days if launch else None
                sev = "high" if state == "running" else "medium"
                add(
                    out,
                    region,
                    "ec2",
                    f"instance:{state}",
                    iid,
                    sev,
                    f"EC2 instance is {state}; running instances incur compute cost and stopped instances keep attached EBS volumes.",
                    name=name,
                    instance_type=inst.get("InstanceType"),
                    launch_time=launch.isoformat() if launch else None,
                    age_days=age_days,
                    private_ip=inst.get("PrivateIpAddress"),
                    public_ip=inst.get("PublicIpAddress"),
                )

    response = call(out, region, "ec2", ec2.describe_volumes)
    if response:
        for vol in response.get("Volumes", []):
            status = vol.get("State")
            size = vol.get("Size")
            vid = vol.get("VolumeId")
            name = name_from_tags(vol.get("Tags"))
            if status == "available":
                sev = "high" if (size or 0) >= 100 else "medium"
                add(
                    out,
                    region,
                    "ec2",
                    "ebs_volume:unattached",
                    vid,
                    sev,
                    "EBS volume is unattached and still billed for storage.",
                    name=name,
                    size_gib=size,
                    volume_type=vol.get("VolumeType"),
                    create_time=vol.get("CreateTime").isoformat() if vol.get("CreateTime") else None,
                )
            elif status == "in-use" and name.lower().startswith(("deleted", "old", "unused")):
                add(
                    out,
                    region,
                    "ec2",
                    "ebs_volume:suspicious_name",
                    vid,
                    "low",
                    "Attached EBS volume name suggests stale/old resource; verify owner before action.",
                    name=name,
                    size_gib=size,
                    volume_type=vol.get("VolumeType"),
                )

    response = call(out, region, "ec2", ec2.describe_addresses)
    if response:
        for addr in response.get("Addresses", []):
            if not addr.get("AssociationId"):
                add(
                    out,
                    region,
                    "ec2",
                    "elastic_ip:unassociated",
                    addr.get("AllocationId") or addr.get("PublicIp"),
                    "medium",
                    "Elastic IP is allocated but not associated.",
                    public_ip=addr.get("PublicIp"),
                    domain=addr.get("Domain"),
                )

    response = call(out, region, "ec2", ec2.describe_nat_gateways)
    if response:
        for ngw in response.get("NatGateways", []):
            state = ngw.get("State")
            if state in {"available", "pending"}:
                add(
                    out,
                    region,
                    "ec2",
                    f"nat_gateway:{state}",
                    ngw.get("NatGatewayId"),
                    "high",
                    "NAT gateway is hourly billed plus data processing; verify it is still needed.",
                    vpc_id=ngw.get("VpcId"),
                    subnet_id=ngw.get("SubnetId"),
                    create_time=ngw.get("CreateTime").isoformat() if ngw.get("CreateTime") else None,
                )

    response = call(out, region, "ec2", ec2.describe_vpc_endpoints)
    if response:
        for ep in response.get("VpcEndpoints", []):
            service_name = ep.get("ServiceName", "")
            ep_type = ep.get("VpcEndpointType")
            state = ep.get("State")
            if ep_type == "Interface" and state == "available":
                add(
                    out,
                    region,
                    "ec2",
                    "vpc_endpoint:interface",
                    ep.get("VpcEndpointId"),
                    "medium",
                    "Interface VPC endpoint has hourly ENI cost; verify there is active traffic/use.",
                    service_name=service_name,
                    vpc_id=ep.get("VpcId"),
                    subnet_ids=ep.get("SubnetIds"),
                )

    response = call(out, region, "ec2", ec2.describe_snapshots, OwnerIds=["self"])
    if response:
        for snap in response.get("Snapshots", []):
            size = snap.get("VolumeSize") or 0
            start = snap.get("StartTime")
            age_days = (now - start).days if start else None
            if size >= 100 or (age_days is not None and age_days >= 30):
                add(
                    out,
                    region,
                    "ec2",
                    "snapshot:self",
                    snap.get("SnapshotId"),
                    "low",
                    "EBS snapshot storage may be stale; verify retention policy before deletion.",
                    size_gib=size,
                    start_time=start.isoformat() if start else None,
                    age_days=age_days,
                    description=snap.get("Description"),
                )

    for svc_name, operation, key in [
        ("elbv2", "describe_load_balancers", "LoadBalancers"),
        ("elb", "describe_load_balancers", "LoadBalancerDescriptions"),
    ]:
        c = client(session, svc_name, region)
        response = call(out, region, svc_name, getattr(c, operation))
        if response:
            for lb in response.get(key, []):
                ident = lb.get("LoadBalancerArn") or lb.get("LoadBalancerName")
                add(
                    out,
                    region,
                    svc_name,
                    "load_balancer",
                    ident,
                    "high",
                    "Load balancer has hourly cost; verify it has active targets/traffic.",
                    name=lb.get("LoadBalancerName"),
                    scheme=lb.get("Scheme"),
                    created_time=(
                        lb.get("CreatedTime").isoformat()
                        if hasattr(lb.get("CreatedTime"), "isoformat")
                        else None
                    ),
                )

    rds = client(session, "rds", region)
    response = call(out, region, "rds", rds.describe_db_instances)
    if response:
        for db in response.get("DBInstances", []):
            add(
                out,
                region,
                "rds",
                f"db_instance:{db.get('DBInstanceStatus')}",
                db.get("DBInstanceIdentifier"),
                "high",
                "RDS instance can incur compute/storage cost; verify owner and recent use.",
                engine=db.get("Engine"),
                db_class=db.get("DBInstanceClass"),
                allocated_storage_gib=db.get("AllocatedStorage"),
                multi_az=db.get("MultiAZ"),
            )
    response = call(out, region, "rds", rds.describe_db_clusters)
    if response:
        for cluster in response.get("DBClusters", []):
            add(
                out,
                region,
                "rds",
                f"db_cluster:{cluster.get('Status')}",
                cluster.get("DBClusterIdentifier"),
                "high",
                "RDS/Aurora cluster may incur storage/compute cost; verify owner and recent use.",
                engine=cluster.get("Engine"),
            )

    for svc, op, key, kind, ident_key, sev in [
        ("fsx", "describe_file_systems", "FileSystems", "filesystem", "FileSystemId", "high"),
        ("efs", "describe_file_systems", "FileSystems", "filesystem", "FileSystemId", "medium"),
        ("eks", "list_clusters", "clusters", "cluster", None, "high"),
        ("redshift", "describe_clusters", "Clusters", "cluster", "ClusterIdentifier", "high"),
        ("opensearch", "list_domain_names", "DomainNames", "domain", None, "high"),
        ("elasticache", "describe_cache_clusters", "CacheClusters", "cache_cluster", "CacheClusterId", "high"),
        ("sagemaker", "list_endpoints", "Endpoints", "endpoint", "EndpointName", "high"),
        ("sagemaker", "list_notebook_instances", "NotebookInstances", "notebook", "NotebookInstanceName", "medium"),
    ]:
        c = client(session, svc, region)
        response = call(out, region, svc, getattr(c, op))
        if not response:
            continue
        for item in response.get(key, []):
            if isinstance(item, str):
                ident = item
                extra = {}
            elif svc == "opensearch":
                ident = item.get("DomainName")
                extra = item
            else:
                ident = item.get(ident_key) if ident_key else str(item)
                extra = item
            add(
                out,
                region,
                svc,
                kind,
                ident,
                sev,
                f"{svc} {kind} exists and may incur recurring cost; verify it is still in use.",
                **extra,
            )

    ecs = client(session, "ecs", region)
    response = call(out, region, "ecs", ecs.list_clusters)
    if response:
        for arn in response.get("clusterArns", []):
            services = call(out, region, "ecs", ecs.list_services, cluster=arn)
            service_count = len((services or {}).get("serviceArns", []))
            add(
                out,
                region,
                "ecs",
                "cluster",
                arn,
                "medium" if service_count else "low",
                "ECS cluster exists; empty clusters are usually low cost but attached services/tasks can cost.",
                service_count=service_count,
            )

    logs = client(session, "logs", region)
    response = call(out, region, "logs", logs.describe_log_groups)
    if response:
        for group in response.get("logGroups", []):
            stored = group.get("storedBytes") or 0
            if stored >= 1024**3 and "retentionInDays" not in group:
                add(
                    out,
                    region,
                    "logs",
                    "log_group:no_retention_large",
                    group.get("logGroupName"),
                    "low",
                    "CloudWatch log group stores over 1 GiB and has no retention policy.",
                    stored_bytes=stored,
                )

    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--regions", nargs="+", required=True)
    args = parser.parse_args()
    session = boto3.Session(profile_name=args.profile)
    payload: dict[str, Any] = {
        "account": session.client("sts").get_caller_identity()["Account"],
        "profile": args.profile,
        "regions": {},
    }
    for region in args.regions:
        payload["regions"][region] = inventory_region(session, region)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
