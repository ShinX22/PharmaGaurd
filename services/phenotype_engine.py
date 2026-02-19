def determine_phenotype(genotype):
    if not genotype or genotype in ["./.", "./.", ""]:
        return "Unknown"
    if genotype == "1/1":
        return "PM"
    elif genotype == "0/1":
        return "IM"
    elif genotype == "0/0":
        return "NM"
    elif genotype == "1/2" or genotype == "2/1":
        return "UM"
    elif genotype == "1x2/1" or genotype == "1/1x2":
        return "RM"
    return "Unknown"
