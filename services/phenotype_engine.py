def determine_phenotype(genotype):
    if genotype == "1/1":
        return "PM"
    elif genotype == "0/1":
        return "IM"
    elif genotype == "0/0":
        return "NM"
    return "Unknown"
