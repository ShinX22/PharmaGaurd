SUPPORTED_RSIDS = {
    "rs3892097": "CYP2D6",
    "rs4244285": "CYP2C19",
    "rs1057910": "CYP2C9",
    "rs4149056": "SLCO1B1",
    "rs1142345": "TPMT",
    "rs3918290": "DPYD"
}

def validate_vcf_header(content):
    lines = content.split("\n")
    for line in lines[:50]:
        if line.startswith("##fileformat=VCFv4.2"):
            return True
    return False


def parse_vcf(file_stream):
    variants = []
    
    try:
        content = file_stream.read()
        
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        
        if not validate_vcf_header(content):
            raise ValueError("Invalid VCF format: missing ##fileformat=VCFv4.2 header")
        
        lines = content.split("\n")
        
        for line in lines:
            if not line.strip() or line.startswith("#"):
                continue
            
            columns = line.strip().split("\t")
            if len(columns) < 10:
                continue
            
            rsid = columns[2].strip()
            
            if rsid not in SUPPORTED_RSIDS:
                continue
            
            format_field = columns[8] if len(columns) > 8 else "GT"
            sample_data = columns[9] if len(columns) > 9 else "."
            
            format_indices = format_field.split(":")
            sample_values = sample_data.split(":")
            
            gt_index = format_indices.index("GT") if "GT" in format_indices else 0
            genotype = sample_values[gt_index] if gt_index < len(sample_values) else "./."
            
            if genotype in ["./.", "./.", ""]:
                continue
            
            variants.append({
                "rsid": rsid,
                "gene": SUPPORTED_RSIDS[rsid],
                "genotype": genotype
            })
    
    except ValueError:
        raise
    except Exception as e:
        return []
    
    return variants
