from collections import OrderedDict
from datetime import datetime


VALID_RISK_LABELS = {"Safe", "Adjust Dosage", "Toxic", "Ineffective", "Unknown"}
VALID_SEVERITY_LEVELS = {"none", "low", "moderate", "high", "critical"}
VALID_PHENOTYPES = {"PM", "IM", "NM", "RM", "UM", "URM", "Unknown"}


def validate_risk_label(value):
    if value in VALID_RISK_LABELS:
        return value
    return "Unknown"


def validate_severity(value):
    if value in VALID_SEVERITY_LEVELS:
        return value
    return "none"


def validate_phenotype(value):
    if value in VALID_PHENOTYPES:
        return value
    return "Unknown"


def build_multi_drug_response(patient_id, drug_results, parsing_success):
    drug_analyses = []
    overall_confidence = 0.0
    has_toxic = False
    has_adjust = False
    max_severity = 0
    severity_map = {"none": 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}
    
    for result in drug_results:
        phenotype = result.get("phenotype", "Unknown")
        phenotype = validate_phenotype(phenotype)
        
        confidence = float(result.get("confidence", 0.0)) if result.get("confidence") is not None else 0.0
        severity = validate_severity(result.get("severity", "none"))
        
        overall_confidence = max(overall_confidence, confidence)
        
        risk_label = validate_risk_label(result.get("risk_label", "Unknown"))
        if risk_label == "Toxic":
            has_toxic = True
        elif risk_label == "Adjust Dosage":
            has_adjust = True
        
        if severity in severity_map:
            max_severity = max(max_severity, severity_map[severity])
        
        drug_analyses.append(OrderedDict([
            ("drug", result.get("drug", "")),
            ("risk_assessment", OrderedDict([
                ("risk_label", risk_label),
                ("confidence_score", confidence),
                ("severity", severity)
            ])),
            ("pharmacogenomic_profile", OrderedDict([
                ("primary_gene", result.get("gene", "")),
                ("diplotype", determine_diplotype(phenotype)),
                ("phenotype", phenotype),
                ("detected_variants", [{"rsid": r} for r in result.get("rsids", [])])
            ])),
            ("clinical_recommendation", get_clinical_recommendation(phenotype, result.get("drug", ""))),
            ("llm_generated_explanation", OrderedDict([
                ("summary", result.get("explanation", ""))
            ]))
        ]))
    
    severity_labels = {0: "none", 1: "low", 2: "moderate", 3: "high", 4: "critical"}
    
    if has_toxic:
        overall_risk_label = "Toxic"
        overall_severity = "high"
    elif has_adjust:
        overall_risk_label = "Adjust Dosage"
        overall_severity = severity_labels.get(max_severity, "moderate")
    else:
        overall_risk_label = "Safe"
        overall_severity = severity_labels.get(max_severity, "low")
    
    overall_risk_label = validate_risk_label(overall_risk_label)
    overall_severity = validate_severity(overall_severity)
    overall_summary = generate_overall_summary(drug_results)
    
    return OrderedDict([
        ("patient_id", patient_id if patient_id else ""),
        ("drug", ", ".join([r.get("drug", "") for r in drug_results])),
        ("timestamp", datetime.utcnow().isoformat() + "Z"),
        ("risk_assessment", OrderedDict([
            ("risk_label", overall_risk_label),
            ("confidence_score", overall_confidence),
            ("severity", overall_severity)
        ])),
        ("pharmacogenomic_profile", OrderedDict([
            ("primary_gene", ""),
            ("diplotype", ""),
            ("phenotype", ""),
            ("detected_variants", [])
        ])),
        ("clinical_recommendation", OrderedDict([
            ("action", overall_risk_label),
            ("dose_adjustment", "See drug analyses"),
            ("monitoring", "See drug analyses")
        ])),
        ("llm_generated_explanation", OrderedDict([
            ("summary", overall_summary)
        ])),
        ("drug_analyses", drug_analyses),
        ("quality_metrics", OrderedDict([
            ("vcf_parsing_success", parsing_success)
        ]))
    ])


def determine_overall_risk(drug_results):
    has_toxic = False
    has_adjust = False
    max_severity = 0
    severity_map = {"none": 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}
    
    for result in drug_results:
        risk_label = validate_risk_label(result.get("risk_label", ""))
        sev = validate_severity(result.get("severity", "none"))
        
        if risk_label == "Toxic":
            has_toxic = True
        elif risk_label == "Adjust Dosage":
            has_adjust = True
        
        if sev in severity_map:
            max_severity = max(max_severity, severity_map[sev])
    
    severity_labels = {0: "none", 1: "low", 2: "moderate", 3: "high", 4: "critical"}
    
    if has_toxic:
        return {
            "overall_risk_label": "Toxic",
            "overall_severity": "high"
        }
    elif has_adjust:
        return {
            "overall_risk_label": "Adjust Dosage",
            "overall_severity": severity_labels.get(max_severity, "moderate")
        }
    else:
        return {
            "overall_risk_label": "Safe",
            "overall_severity": severity_labels.get(max_severity, "low")
        }


def generate_overall_summary(drug_results):
    toxic_drugs = []
    adjust_drugs = []
    safe_drugs = []
    
    for result in drug_results:
        drug = result.get("drug", "")
        risk = validate_risk_label(result.get("risk_label", ""))
        if risk == "Toxic":
            toxic_drugs.append(drug)
        elif risk == "Adjust Dosage":
            adjust_drugs.append(drug)
        else:
            safe_drugs.append(drug)
    
    parts = []
    if toxic_drugs:
        parts.append(f"Drugs with potential toxicity risk: {', '.join(toxic_drugs)}. Consider dose reduction or alternative therapy.")
    if adjust_drugs:
        parts.append(f"Dose adjustment recommended for: {', '.join(adjust_drugs)}.")
    if safe_drugs:
        parts.append(f"Standard dosing appropriate for: {', '.join(safe_drugs)}.")
    
    if not parts:
        return "Multi-drug analysis completed. Please refer to individual drug recommendations."
    
    return " ".join(parts)


def build_response(patient_id, drug, gene, phenotype,
                   risk_label, severity, confidence,
                   rsids, explanation, parsing_success):
    
    phenotype = validate_phenotype(phenotype if phenotype else "Unknown")
    risk_label = validate_risk_label(risk_label if risk_label else "Unknown")
    severity = validate_severity(severity if severity else "none")
    confidence = float(confidence) if confidence is not None else 0.0
    
    return OrderedDict([
        ("patient_id", patient_id if patient_id else ""),
        ("drug", drug if drug else ""),
        ("timestamp", datetime.utcnow().isoformat() + "Z"),
        ("risk_assessment", OrderedDict([
            ("risk_label", risk_label),
            ("confidence_score", confidence),
            ("severity", severity)
        ])),
        ("pharmacogenomic_profile", OrderedDict([
            ("primary_gene", gene if gene else ""),
            ("diplotype", determine_diplotype(phenotype)),
            ("phenotype", phenotype),
            ("detected_variants", [{"rsid": r} for r in rsids] if rsids else [])
        ])),
        ("clinical_recommendation", get_clinical_recommendation(phenotype, drug)),
        ("llm_generated_explanation", OrderedDict([
            ("summary", explanation if explanation else "No explanation available")
        ])),
        ("quality_metrics", OrderedDict([
            ("vcf_parsing_success", parsing_success)
        ]))
    ])


def determine_diplotype(phenotype):
    diplotype_map = {
        "PM": "*4/*4",
        "IM": "*1/*4",
        "NM": "*1/*1",
        "RM": "*1x2/*1",
        "UM": "*1xN/*1",
        "URM": "*1xN/*1"
    }
    return diplotype_map.get(phenotype, "*1/*1")


def get_clinical_recommendation(phenotype, drug):
    phenotype = validate_phenotype(phenotype)
    recommendations = {
        "PM": {
            "action": "Reduce dose or consider alternative therapy",
            "dose_adjustment": "Significant dose reduction recommended",
            "monitoring": "Frequent therapeutic drug monitoring required"
        },
        "IM": {
            "action": "Consider dose adjustment",
            "dose_adjustment": "Moderate dose reduction may be needed",
            "monitoring": "Regular clinical monitoring advised"
        },
        "NM": {
            "action": "Standard dosing",
            "dose_adjustment": "No dose adjustment required",
            "monitoring": "Standard monitoring per protocol"
        },
        "RM": {
            "action": "Standard dosing",
            "dose_adjustment": "Standard dose, may consider increase if needed",
            "monitoring": "Monitor for efficacy"
        },
        "UM": {
            "action": "Consider increased dose or alternative",
            "dose_adjustment": "May require higher than standard doses",
            "monitoring": "Monitor for therapeutic response"
        },
        "URM": {
            "action": "Consider increased dose or alternative",
            "dose_adjustment": "May require higher than standard doses",
            "monitoring": "Monitor for therapeutic response"
        },
        "Unknown": {
            "action": "Refer to clinical genetics",
            "dose_adjustment": "Use standard dosing with caution",
            "monitoring": "Close clinical monitoring recommended"
        }
    }
    
    return recommendations.get(phenotype, recommendations["Unknown"])
