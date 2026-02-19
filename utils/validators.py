import os


def validate_file_extension(filename, allowed_extensions):
    if not filename:
        return "No file provided"
    
    filename = filename.strip()
    ext = os.path.splitext(filename)[1].lower()
    
    valid_extensions = {'.vcf', 'vcf'}
    if ext not in valid_extensions:
        return f"Invalid file extension '{ext}'. Only .vcf files are allowed."
    
    return None


def validate_file_size(file_obj, max_size_bytes):
    file_obj.seek(0, 2)
    size = file_obj.tell()
    file_obj.seek(0)
    
    if size > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        return f"File too large ({size / (1024 * 1024):.2f}MB). Maximum allowed size is {max_mb:.0f}MB."
    
    return None


def validate_drugs(drug_input, supported_drugs):
    if not drug_input:
        return {"valid": False, "error": "Drug selection is required", "error_code": "DRUG_REQUIRED"}
    
    drug_list = [d.strip() for d in drug_input.split(",")]
    invalid_drugs = [d for d in drug_list if d not in supported_drugs]
    
    if invalid_drugs:
        return {
            "valid": False,
            "error": f"Unsupported drug(s): {', '.join(invalid_drugs)}. Supported drugs: {', '.join(supported_drugs)}",
            "error_code": "UNSUPPORTED_DRUG"
        }
    
    return {"valid": True, "drugs": drug_list}


VALID_SEVERITY_LEVELS = {"none", "low", "moderate", "high", "critical"}
VALID_RISK_LABELS = {"Safe", "Toxic", "Adjust Dosage", "Unknown"}
VALID_PHENOTYPES = {"PM", "IM", "NM", "RM", "UM", "Unknown"}


def validate_response_schema(data):
    errors = []
    
    if not data.get("patient_id"):
        errors.append("Missing required field: patient_id")
    
    if not data.get("drug"):
        errors.append("Missing required field: drug")
    
    risk_assessment = data.get("risk_assessment", {})
    if risk_assessment.get("severity") and risk_assessment["severity"] not in VALID_SEVERITY_LEVELS:
        errors.append(f"Invalid severity value: {risk_assessment.get('severity')}")
    
    if risk_assessment.get("risk_label") and risk_assessment["risk_label"] not in VALID_RISK_LABELS:
        errors.append(f"Invalid risk_label value: {risk_assessment.get('risk_label')}")
    
    pgx_profile = data.get("pharmacogenomic_profile", {})
    if pgx_profile.get("phenotype") and pgx_profile["phenotype"] not in VALID_PHENOTYPES:
        errors.append(f"Invalid phenotype value: {pgx_profile.get('phenotype')}")
    
    return errors
