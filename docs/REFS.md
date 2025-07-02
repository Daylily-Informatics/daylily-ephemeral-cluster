# Refs to keep track of

- [GenMPI: Cluster Scalable Variant Calling for
Short/Long Reads Sequencing Data](https://www.biorxiv.org/content/10.1101/2022.04.01.486779v1.full.pdf?utm_source=chatgpt.com)
    - Published comparison on HG002 for GATK, deepvar, octopus, clair3, showing GATK stinks.

- [](https://bmcgenomics.biomedcentral.com/articles/10.1186/s12864-022-08365-3?utm_source=chatgpt.com)
  - >  Consistent with earlier observations, GATK-HC with the 2D CNN model performed reproducibly worse on SNPs than any other pipeline.
  - > Finally, software tools for bioinformatic analysis of NGS data are constantly improving. Besides accuracy, running time (which was not specifically evaluated in our analysis) may also present a serious problem when working with large genomic datasets. Multiple attempts have been made recently to achieve high scalability of the read alignment and variant calling software. These include, but are not limited to, development of a native Google Cloud Platform integration in the recent versions of GATK, faster reimplementation of the BWA MEM algorithm (BWA-MEM2, [33]), and many others. Constant development of novel methods and software tools suggests that large-scale stratified comparisons, like the one presented in our work, should be repeatedly conducted at least once in several years.
- [Benchmarking reveals superiority of deep learning variant callers on bacterial nanopore sequence data](https://elifesciences.org/reviewed-preprints/98300v1?utm_source=chatgpt.com)
  > 50% fewer errors per genome than traditional callers like GATK

- [dnascope](https://www.researchgate.net/publication/360819474_DNAscope_High_accuracy_small_variant_calling_using_machine_learning)
- [Performance analysis of conventional and AI-based variant callers using short and long reads](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-023-05596-3?utm_source=chatgpt.com)

- BEST PRACTICES -- worst of both worlds. They do not keep up with the field [here](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-021-04317-y#:~:text=,and%20hamper%20reproducibility%20over%20time) and also, are updated often to match the GATK releases, hurting reproducibility! [here]().
  - > Moreover, the Best Practices documentation itself is frequently updated with new versions of GATK, meaning command lines and recommended parameters “can become obsolete” over time
bmcbioinformatics.biomedcentral.com
. This is problematic for reproducibility – years later it may be elusive what exact pipeline was used, especially when researchers simply cite “GATK Best Practices” without detail. Even the GATK developers have acknowledged that many so-called Best Practices workflows in publications diverge from official recommendations, making reproducibility and standardization difficult
bmcbioinformatics.biomedcentral.com
.

