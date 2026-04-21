# Comparison of Duplicate Marking Tools: Sentieon, Doppelmark, Sambamba

## Optimizations Applied

### jemalloc and numa!
  > Use them.
  > Enable Huge Pages.

  
### Hardware
  > AWS EC2 r6* family 128vcp/1024GB memory instances. (choosing least expensive spot price from pool of 8 instance types meeting these criteria).
  

## Results
### [Sentieon MarkDuplicates]() 
  > extremely fast re-implementation of bwa.

  - command:
  ```bash
  
  ```

  30x genome, speed to mark duplicate for `b37` aligned BAM:
    ![](../../docs/images/assets/b37_sent_mkd.png)
  
  30x genome, speed to mark duplicates for `hg38` aligned BAM:
    ![](../../docs/images/assets/hg38_sent_mkd.png)
  

### [Doppelmark](https://github.com/grailbio/doppelmark)
  > re-compiled using intel compiler tuned to the target EC2 instances to be run on.

  - command:
  ```bash
  
  ```
  
  30x genome, speed to mark duplicates for `b37` aligned BAM:
    ![](../../docs/images/assets/b37_dppl_mkd.png)
  
  30x genome, speed to mark duplicates for `hg38` aligned BAM:
    ![](../../docs/images/assets/hg38_dppl_mkd.png)
    

### [Sambamba](https://github.com/biod/sambamba)

  - command:
  ```bash
  
  ```
  
  30x genome, speed to mark duplicates for `b37` aligned BAM:
    ![](../../docs/images/assets/b37_smb_mkd.png)
  
  30x genome, speed to mark duplicates for `hg38` aligned BAM:
    ![](../../docs/images/assets/hg38_smb_mkd.png)
    
    
 ### [BioBamBam2](https://gitlab.com/german.tischler/biobambam2)
  > re-compiled using intel compiler tuned to the target EC2 instances to be run on.

  - command:
  ```bash
  
  ```
  
  30x genome, speed to mark duplicates for `b37` aligned BAM:
    ![](../../docs/images/assets/b37_bbb2_mkd.png)
  
  30x genome, speed to mark duplicates for `hg38` aligned BAM:
    ![](../../docs/images/assets/hg38_bbb2_mkd.png)
    
  
  ### Others Tools Tested, But Too Slow To Consider Further
    - gatk
    - samtools
