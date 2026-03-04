#source me
conda activate DAY-EC && cluster_name=$(conda activate DAY-EC && pcluster list-clusters | grep 'clusterName' | perl -pe 's/.*\: \"(.*)\"\,.*/$1/g;') && cluster_ip=$(pcluster describe-cluster -n $cluster_name | grep 'publicIpAddress' | perl -pe 's/.*\: \"(.*)\"\,.*/$1/g;') &&ssh -i ~/.ssh/daylily2.pem ubuntu@$cluster_ip
