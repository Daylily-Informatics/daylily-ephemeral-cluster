set -euo pipefail
echo '=== sinfo summary ==='
sinfo -o '%P|%a|%D|%t|%C|%m|%G|%N'
echo '=== nodes ==='
sinfo -Nel || true
echo '=== queue ==='
squeue -o '%i|%P|%C|%t|%M|%D|%R|%j'
echo '=== fairshare/account summary ==='
sacctmgr show assoc format=Account,User,Partition,GrpTRES,GrpJobs,GrpSubmit,MaxTRES,MaxJobs,MaxSubmit -Pn 2>/dev/null | head -n 80 || true