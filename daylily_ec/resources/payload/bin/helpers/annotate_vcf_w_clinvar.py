import vcf
import requests

# Define the ClinVar API endpoint and query parameters
clinvar_api_endpoint = "https://api.ncbi.nlm.nih.gov/clinvar/v1/variation"
clinvar_api_params = {"fields": "variation_id,rcv.accession,rcv.conditions.name,rcv.conditions.identifiers,rcv.conditions.medgen_uid,rcv.conditions.omim_id"}

# Load the VCF file using PyVCF
vcf_reader = vcf.Reader(open('input.vcf', 'r'))

# Add ClinVar annotations to each variant in the VCF file
for record in vcf_reader:
    # Get the chromosome, start position, and reference allele for the variant
    chrom = record.CHROM
    pos = record.POS
    ref = record.REF

    # Query the ClinVar API for annotations for the variant
    clinvar_api_url = f"{clinvar_api_endpoint}/{chrom}-{pos}-{ref}"
    response = requests.get(clinvar_api_url, params=clinvar_api_params)

    # Parse the ClinVar annotations from the API response
    annotations = []
    for rcv in response.json()['allele_annotations'][0]['clinical_significance']:
        accession = rcv['accession']
        condition_name = rcv['conditions'][0]['name']
        condition_identifiers = rcv['conditions'][0]['identifiers']
        medgen_uid = rcv['conditions'][0]['medgen_uid']
        omim_id = rcv['conditions'][0]['omim_id']
        annotation = f"CLNSIG={accession}|{condition_name}|{condition_identifiers}|{medgen_uid}|{omim_id}"
        annotations.append(annotation)

    # Add the ClinVar annotations to the INFO field of the variant
    if len(annotations) > 0:
        record.INFO['CLINVAR'] = ';'.join(annotations)

    # Write the annotated variant to a new VCF file
    vcf_writer.write_record(record)

# Close the VCF reader and writer
vcf_reader.close()
vcf_writer.close()
