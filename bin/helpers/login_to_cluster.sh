# source me
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=/dev/null
source "$repo_root/activate"
cluster_name=$(pcluster list-clusters | grep 'clusterName' | perl -pe 's/.*\: \"(.*)\"\,.*/$1/g;')
cluster_ip=$(pcluster describe-cluster -n $cluster_name | grep 'publicIpAddress' | perl -pe 's/.*\: \"(.*)\"\,.*/$1/g;')
ssh -i ~/.ssh/daylily2.pem ubuntu@$cluster_ip
