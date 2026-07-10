## Summary

- add explicit AlmaLinux 8 providers for environment, platform, shared, and Slurm resources
- apply existing Enterprise Linux 8 package, Lustre, networking, and scheduler behavior to AlmaLinux 8
- explicitly skip EFA installation because the current EFA installer does not support AlmaLinux 8
- add generic ChefSpec, Kitchen, CloudWatch, and style coverage

## Scope

This supports customer-provided AlmaLinux 8 parent images. It does not claim that AWS ParallelCluster publishes an AlmaLinux image.

Tracks aws/aws-parallelcluster#7482.

Companion CLI PR: aws/aws-parallelcluster#7483

## Tests

- 1,975 edited-surface ChefSpec examples passed
- 19 CloudWatch Python tests passed
- EFA skip behavior passed focused ChefSpec coverage
- 66 changed Ruby files passed Cookstyle
- changed Ruby and Python files passed syntax checks
- an ImageBuilder build from an official AlmaLinux 8 x86_64 parent completed, and the resulting custom AMI passed the ImageBuilder boot/test phase
