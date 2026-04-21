> Archived on 2026-03-08. These notes are preserved for historical reference and are not canonical operator guidance.

# Various Helpful Incantations

## AWS CLI 

### Show Instances Running For Cluster

```bash

region="us-west-2"
cluster_name="jem-calm-down-99"
aws ec2 describe-instances --region $region --filters "Name=tag:parallelcluster:cluster-name,Values=$cluster_name" --query "Reservations[*].Instances[*].[InstanceId,InstanceType,State.Name,Tags[?Key=='Name'].Value|[0],Tags[?Key=='parallelcluster:node-type'].Value|[0],PrivateIpAddress,PublicIpAddress,LaunchTime]" --output table

--------------------------------------------------------------------------------------------------------------------------------------
|                                                          DescribeInstances                                                         |
+---------------------+--------------+----------+-----------+-----------+-------------+-----------------+----------------------------+
|  i-0a9d1bd222295bbd0|  r5n.4xlarge |  running |  HeadNode |  HeadNode |  10.0.0.197 |  54.188.255.78  |  2024-08-20T00:45:05.000Z  |
+---------------------+--------------+----------+-----------+-----------+-------------+-----------------+----------------------------+
```

### Historic Resource JSON

```bash

aws cloudtrail lookup-events --region us-west-2 --lookup-attributes AttributeKey=EventName,AttributeValue=RunInstances --start-time $(date -u -d '2 days ago' '+%Y-%m-%dT%H:%M:%SZ') --end-time $(date -u '+%Y-%m-%dT%H:%M:%SZ') --output json > events.json

```


### Spot Instance Pricing

```bash



aws ec2 describe-spot-price-history \
    --instance-types m7i.metal-48xl r5.16xlarge r7i.48xlarge r6id.metal \
    --start-time 2024-08-22T00:00:00Z \
    --end-time 2024-08-23T00:00:00Z \
    --availability-zone us-west-2c \
    --filters "Name=product-description,Values=Linux/UNIX" \
    --output table \
    --region us-west-2
```


### For Terminated Instances

```bash

aws cloudtrail lookup-events     --region us-west-2     --lookup-attributes AttributeKey=EventName,AttributeValue=TerminateInstances     --start-time $(date -u -d '2 days ago' '+%Y-%m-%dT%H:%M:%SZ')     --end-time $(date -u '+%Y-%m-%dT%H:%M:%SZ')     --output json > termination_events.json

```
