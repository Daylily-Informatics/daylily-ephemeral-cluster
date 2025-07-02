# Quickest Start
_this doc lays out the core steps necessary to install an ephemeral cluster, and assumes many pre-reqs exist_

> **If you encounter issues during install, please refer back to the detailed steps in the [README](README.md) and treat those as canonical.

## AWS Dashboard
### As an admin
#### Create `daylily-service` IAM user
- create a new IAM user named `daylily-service` & capture the console login url and p/w. 
- Assign the permission `AmazonQDeveloperAccess`. 
- Attach an inline policy named `daylily-service-cluster-policy` and use the json editor to then paste in [this json](config/aws/daylily-service-cluster-policy.json). Be sure to replace the <AWS_ACCOUNT_ID> instances with your aws account id.

#### As the `daylily-service` user
_on the laptop you'll create ephemeral clusters from_

- Using the console URL, login w/the saved p/w. Set new password.
- Save CLI credentials to `~/.aws/credentials` in a profile named `daylily-omics-analysis`.
- In the region you intend to run in, create a keypair with the name `<YOURPREFIX>-omics-analysis-<REGION>` of the type `ed25519`. Download `.pem` and move to `~/.ssh/`, fix permissions if necessary.

## DAYLILY CLI & Ephemeral Cluster Creation
_on the laptop you'll create ephemeral cluster, where you have saved the daylily-service user AWS cli credentials and have the appropriate `.pem`'s in `~/.ssh`._

### Create References S3 Bucket (if it does not already exist)
_One is needed per region you intend to run in._

```bash
export AWS_PROFILE=daylily-service
BUCKET_PREFIX=yocorp
REGION=us-west-2
./bin/create_daylily_omics_analysis_s3.sh  --disable-warn --region $REGION --profile $AWS_PROFILE --bucket-prefix $BUCKET_PREFIX --disable-dryrun
```

- This will take ~20min if you remain in `us-west-2`, longer if cross region.

> your reference bucket will be named **`yocorp-daylily-omics-analysis-us-west-2`**


#### Move the sentieon lic into place (only necessary if you are running sentieon, else skip)

```bash
sentieon_lic=Sentieon_YOCORP.lic
rclone copy $sentieon_lic yocorp_remote:yocorp-daylily-omics-analysis-us-west-2/data/cached_envs/
```

### Check Spot Market Pricing (optional, but suggested to get best pricing over time)

```bash
export AWS_PROFILE=daylily-service
REGION=us-west-2          
OUT_TSV=./init_daylily_cluster.tsv

./bin/check_current_spot_market_by_zones.py -o $OUT_TSV --profile $AWS_PROFILE   
```

- You can choose the region-availability-zone you wish to run in (be sure you already have a references bucket cloned into this region), and use the region-availability-zone in the create ephemeral cluster step.

### Create An Ephemeral Cluster
_this script will check and install a number of prerequsites and attempt to install_


#### Edit `config/daylily_ephemeral_cluster.yaml`

- The config file `config/daylily_ephemeral_cluster.yaml` is used to pull routine defaults that will be used to skip user prompts in the next step. Please check out the file and set anything you wish to tweak.

#### Run `daylily-create-ephemeral-cluster`

```bash
export AWS_PROFILE=daylily-service
REGION_AZ=us-west-2c

./bin/daylily-create-ephemeral-cluster --region-az $REGION_AZ --profile $AWS_PROFILE
```

You will be prompted for a variety of config settings. Some resources, if missing, will be created. Other resources if missing will trigger failures.  If all is well, you'll be left with a success message with a suggested command to start a remote test on the headnode.




