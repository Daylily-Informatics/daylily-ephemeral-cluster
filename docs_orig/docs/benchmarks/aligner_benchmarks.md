# Comparison of BWA-mem2 ert and Sentieon BWA + Sorting

## Optimizations Applied


### jemalloc and numa!
  > Use them.
  > Enable Huge Pages.
  > Increase performance substantially.


### Pipe to Sort
  > Avoid hitting disk to minimize/eliminate expensive multi tmp file bam sort.
  
  
### Hardware
  > AWS EC2 r6* family 128vcp/1024GB memory instances. (choosing least expensive spot price from pool of 8 instance types meeting these criteria).
  

## Results
### [Sentieon BWA]() + Sort
  > extremely fast re-implementation of bwa.

  - command:
  ```bash
  
  ```

  30x genome, speed to map to `b37`:
    ![](../../docs/images/assets/b37_ert_aln.png)
  
  30x genome, speed to map to `hg38`:
    ![](../../docs/images/assets/b37_ert_aln.png)
  

### [BWA-mem2](https://github.com/bwa-mem2/bwa-mem2) + Sort
  > re-compiled using intel compiler tuned to the target EC2 instances to be run on.

  - command:
  ```bash
  
  ```
  
  30x genome, speed to map to `b37`:
    ![](../../docs/images/assets/b37_ert_aln.png)
  
  30x genome, speed to map to `hg38`:
    ![](../../docs/images/assets/b37_ert_aln.png)


### [BWA-mem2 ert](https://github.com/bwa-mem2/bwa-mem2/tree/ert) + Sort
  > fork of [bwa-mem2](https://github.com/bwa-mem2/bwa-mem2), adding an Enumerated Radix Tree for an additional speed increase.
  > re-compiled using intel compiler tuned to the target EC2 instances to be run on.

  - command:
  ```bash
  
  ```
  
  30x genome, speed to map to `b37`:
    ![](../../docs/images/assets/b37_ert_aln.png)
  
  30x genome, speed to map to `hg38`:
    ![](../../docs/images/assets/b37_ert_aln.png)
    
    
### HiSat2 (coming)
