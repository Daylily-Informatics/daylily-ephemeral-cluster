## Summary

- add `almalinux8` as a distinct supported operating-system value
- detect AlmaLinux 8 in ImageBuilder and preserve its release packages during kernel updates
- add schema, validator, configure, ImageBuilder, and integration-fixture coverage
- reject EFA-enabled AlmaLinux 8 configurations because the current EFA installer does not support AlmaLinux 8

## Scope

This supports customer-provided AlmaLinux 8 parent images. It does not claim that AWS ParallelCluster publishes an AlmaLinux image.

Closes #7482.

Companion cookbook PR: aws/aws-parallelcluster-cookbook#3222

## Tests

- 755 focused schema, validator, configure, and ImageBuilder tests passed
- AlmaLinux EFA validation covers x86_64, arm64, and EFA-disabled configurations
- changed ImageBuilder components and generic AlmaLinux fixtures passed diff and leak checks
