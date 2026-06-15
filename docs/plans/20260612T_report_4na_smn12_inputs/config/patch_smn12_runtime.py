from pathlib import Path
import yaml
path = Path('config/day_profiles/slurm/rule_config.yaml')
if not path.exists():
    raise SystemExit(f'Missing generated Slurm rule_config: {path}')
data = yaml.safe_load(path.read_text())
data['hg38_broad_samples_table'] = 'config/samples.tsv'
data['hg38_broad_units_table'] = 'config/units.tsv'
data['samples_table'] = 'config/samples.tsv'
data['units_table'] = 'config/units.tsv'
data['htd_callers'] = ['smn12', 'smaca', 'sma_finder', 'hapsma']
hapsma = data.setdefault('hapsma', {})
hapsma.update({
    'dev_exploratory': True,
    'ploidy': '1',
    'start': 'bam_single_remap',
    'smn_region': 'chr5:69949523-71054173',
    'min_smn_region_mean_coverage': 4,
    'calling_target_bed': '/fsx/references/runtime_assets/tool_specific_resources/hapsma/hg38_broad/SMN_region_38.smn_only.bed',
    'calling_target_region': 'chr5:69949523-71054173',
    'phaseset_region': 'chr5:69949523-71054173',
    'homopolymer_bed': '/fsx/references/runtime_assets/tool_specific_resources/hapsma/hg38_broad/hg38_broad_smn_100kb_pad_homopolymer_run3.bed',
    'clair3model': '/fsx/references/runtime_assets/tool_specific_resources/clair3/models/r1041_e82_400bps_sup_v500',
    'clair3_optional': '--haploid_sensitive --platform=ont --enable_long_indel',
    'minimap_index': '/fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.map-ont.mmi',
    'minimap_param': '-y -ax map-ont',
    'fastq_tags': 'RG,Mm,Ml,MM,ML',
    'min_read_length': 1000,
    'threads': 192,
    'mem_mb': 250000,
    'partition': 'i192hugenvme,i192nvme,i384nvme',
})
sentdhiomr = data.setdefault('sentdhiomr', {})
sentdhiomr['segdup_genes'] = 'SMN1'
sentdhiomr['segdup_threads'] = 192
sentdhiomr['segdup_mem_mb'] = 250000
path.write_text(yaml.safe_dump(data, sort_keys=False))
print('patched', path)
print('samples_table', data.get('samples_table'))
print('units_table', data.get('units_table'))
print('htd_callers', data['htd_callers'])
print('hapsma.minimap_index', hapsma['minimap_index'])
print('sentdhiomr.segdup_genes', sentdhiomr['segdup_genes'])
