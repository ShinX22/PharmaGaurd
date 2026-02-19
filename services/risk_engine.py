PRIMARY_GENE_MAP = {
    "Codeine": "CYP2D6",
    "Clopidogrel": "CYP2C19",
    "Warfarin": "CYP2C9",
    "Simvastatin": "SLCO1B1",
    "Azathioprine": "TPMT",
    "Fluorouracil": "DPYD"
}

def evaluate_risk(drug, phenotype):
    if phenotype == "PM":
        return "Toxic", "high", 0.92
    elif phenotype == "IM":
        return "Adjust Dosage", "moderate", 0.75
    elif phenotype == "NM":
        return "Safe", "low", 0.60
    return "Unknown", "none", 0.0
