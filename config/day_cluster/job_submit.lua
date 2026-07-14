-- DAY-EC cluster-wide scheduling policy.
--
-- Memory remains available to applications, but it is deliberately not a
-- Slurm placement resource. Jobs must select capacity with a partition and
-- CPU/thread count. This server-side policy covers sbatch, salloc, srun job
-- allocations, job scripts, environment-derived requests, job updates, and
-- API clients that bypass the DAY-EC submission wrapper.

local function is_explicit(value, no_value)
    return value ~= nil and value ~= "" and value ~= no_value
end

local function reject_memory_request(job_desc)
    local per_node = job_desc.min_mem_per_node
    local per_cpu = job_desc.min_mem_per_cpu
    local per_tres = job_desc.mem_per_tres

    if is_explicit(per_node, slurm.NO_VAL64)
        or is_explicit(per_cpu, slurm.NO_VAL64)
        or is_explicit(per_tres, slurm.NO_VAL64) then
        slurm.log_user(
            "DAY-EC memory placement is disabled; remove --mem, --mem-per-cpu, " ..
            "--mem-per-gpu, and API memory fields. Select capacity with " ..
            "--partition and CPU/thread count."
        )
        return slurm.ERROR
    end
    return slurm.SUCCESS
end

function slurm_job_submit(job_desc, part_list, submit_uid)
    return reject_memory_request(job_desc)
end

function slurm_job_modify(job_desc, job_rec, part_list, modify_uid)
    return reject_memory_request(job_desc)
end

return slurm.SUCCESS
