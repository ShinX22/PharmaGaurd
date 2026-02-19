import os
import google.genai
from config import GEMINI_API_KEY

_client = None

def _get_client():
    global _client
    if _client is None and GEMINI_API_KEY:
        try:
            _client = google.genai.Client(api_key=GEMINI_API_KEY)
        except Exception:
            _client = False
    return _client if _client else None


def generate_explanation(gene, phenotype, drug):
    if not gene or not drug:
        return "Gene or drug information missing. Please verify input data."
    
    if not GEMINI_API_KEY:
        return get_fallback_explanation(gene, phenotype, drug)
    
    client = _get_client()
    if not client:
        return get_fallback_explanation(gene, phenotype, drug)
    
    try:
        phenotype_desc = get_phenotype_description(phenotype)
        
        prompt = f"""
You are a clinical pharmacogenomics expert. Provide a concise clinical explanation.

Gene: {gene}
Drug: {drug}
Phenotype: {phenotype} ({phenotype_desc})

Provide a 2-3 sentence clinical explanation suitable for healthcare professionals.
Do NOT speculate beyond the provided phenotype information.
"""
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        
        if response and response.text:
            return response.text.strip()
        else:
            return get_fallback_explanation(gene, phenotype, drug)
            
    except Exception as e:
        return get_fallback_explanation(gene, phenotype, drug)


def get_phenotype_description(phenotype):
    descriptions = {
        "PM": "Poor Metabolizer - minimal enzyme activity",
        "IM": "Intermediate Metabolizer - reduced enzyme activity",
        "NM": "Normal Metabolizer - typical enzyme activity",
        "RM": "Rapid Metabolizer - increased enzyme activity",
        "UM": "Ultra-rapid Metabolizer - very high enzyme activity",
        "Unknown": "Phenotype not determined"
    }
    return descriptions.get(phenotype, "Unknown phenotype")


def get_fallback_explanation(gene, phenotype, drug):
    phenotype_desc = get_phenotype_description(phenotype)
    
    explanations = {
        "PM": f"Patient with {gene} Poor Metabolizer ({phenotype_desc}) phenotype may experience elevated drug levels when treated with {drug}, potentially increasing toxicity risk. Dose reduction and close monitoring are recommended per CPIC guidelines.",
        
        "IM": f"Patient with {gene} Intermediate Metabolizer ({phenotype_desc}) phenotype may have reduced clearance of {drug}. Standard dosing with clinical monitoring is advised.",
        
        "NM": f"Patient with {gene} Normal Metabolizer ({phenotype_desc}) phenotype is expected to respond normally to {drug} at standard doses.",
        
        "RM": f"Patient with {gene} Rapid Metabolizer ({phenotype_desc}) phenotype may have accelerated clearance of {drug}. Consider standard dosing with monitoring.",
        
        "UM": f"Patient with {gene} Ultra-rapid Metabolizer ({phenotype_desc}) phenotype may have subtherapeutic response to {drug} at standard doses. Dose increase may be required.",
        
        "Unknown": f"Unable to determine {gene} metabolizer status for {drug}. Clinical judgment and therapeutic drug monitoring are recommended."
    }
    
    return explanations.get(phenotype, explanations["Unknown"])
