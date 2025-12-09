# Last 7 days node preemptions/terminations in Slurm logs
grep -Ei 'preempt|preemption|termination|node down' /var/log/slurmctld.log* | tail -n 500
