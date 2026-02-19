import os
from flask import Flask, request, jsonify, render_template
from services.vcf_parser import parse_vcf
from services.phenotype_engine import determine_phenotype
from services.risk_engine import PRIMARY_GENE_MAP, evaluate_risk
from services.gemini_service import generate_explanation
from services.json_builder import build_response, build_multi_drug_response
from utils.validators import validate_file_extension, validate_file_size, validate_drugs

app = Flask(__name__)

app.json.sort_keys = False
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

SUPPORTED_DRUGS = [d.upper() for d in PRIMARY_GENE_MAP.keys()]
ALLOWED_EXTENSIONS = {'vcf'}
MAX_FILE_SIZE = 5 * 1024 * 1024

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST", "GET"])
def analyze():
    if request.method == "GET":
        return jsonify({
            "error": "Method not allowed. Use POST with multipart/form-data containing vcf_file, drug, and patient_id.",
            "error_code": "METHOD_NOT_ALLOWED"
        }), 405

    if request.method == "POST":
        if "vcf_file" not in request.files:
            return jsonify({
                "error": "VCF file is required",
                "error_code": "FILE_REQUIRED"
            }), 400
        
        vcf_file = request.files["vcf_file"]
        if vcf_file.filename == "":
            return jsonify({
                "error": "VCF file is required",
                "error_code": "FILE_REQUIRED"
            }), 400
        
        file_ext_error = validate_file_extension(vcf_file.filename, ALLOWED_EXTENSIONS)
        if file_ext_error:
            return jsonify({
                "error": file_ext_error,
                "error_code": "INVALID_FILE_EXTENSION"
            }), 400
        
        file_size_error = validate_file_size(vcf_file, MAX_FILE_SIZE)
        if file_size_error:
            return jsonify({
                "error": file_size_error,
                "error_code": "FILE_TOO_LARGE"
            }), 400
        
        drug = request.form.get("drug_input")
        patient_id = request.form.get("patient_id")

        if not drug or not drug.strip():
            return jsonify({
                "error": "Drug input is required",
                "error_code": "DRUG_REQUIRED"
            }), 400
        
        if not patient_id:
            return jsonify({
                "error": "Patient ID is required",
                "error_code": "PATIENT_ID_REQUIRED"
            }), 400
        
        drug_list = [d.strip().upper() for d in drug.split(",") if d.strip()]
        drug_list = [d for d in drug_list if d]
        
        invalid_drugs = [d for d in drug_list if d not in SUPPORTED_DRUGS]
        if invalid_drugs:
            return jsonify({
                "error": f"Unsupported drug: {invalid_drugs[0]}",
                "error_code": "UNSUPPORTED_DRUG"
            }), 400
        
        if not drug_list:
            return jsonify({
                "error": "Drug input is required",
                "error_code": "DRUG_REQUIRED"
            }), 400
        
        parsing_success = False
        try:
            vcf_file.seek(0)
            variants = parse_vcf(vcf_file.stream)
            parsing_success = True
        except Exception:
            variants = []
            return jsonify({
                "error": "Failed to parse VCF file. Please ensure the file is a valid VCF format.",
                "error_code": "VCF_PARSE_ERROR"
            }), 400

        drug_original_case = {d.upper(): d for d in PRIMARY_GENE_MAP.keys()}
        
        if len(drug_list) == 1:
            drug_original = drug_original_case.get(drug_list[0], drug_list[0])
            primary_gene = PRIMARY_GENE_MAP[drug_original]
            relevant = [v for v in variants if v.get("gene") == primary_gene]

            genotype = None
            phenotype = "Unknown"
            rsids = []
            
            if relevant:
                genotype = relevant[0].get("genotype")
                phenotype = determine_phenotype(genotype)
                rsids = [v.get("rsid") for v in relevant if v.get("rsid")]

            risk_label, severity, confidence = evaluate_risk(drug_original, phenotype)

            try:
                explanation = generate_explanation(primary_gene, phenotype, drug_original)
            except Exception as e:
                explanation = f"Analysis completed. Phenotype {phenotype} detected for {primary_gene} gene. Clinical interpretation should be confirmed with laboratory testing."

            response = build_response(
                patient_id, drug_original, primary_gene, phenotype,
                risk_label, severity, confidence,
                rsids, explanation, parsing_success
            )
        else:
            drug_results = []
            for drug_item in drug_list:
                drug_original = drug_original_case.get(drug_item, drug_item)
                primary_gene = PRIMARY_GENE_MAP[drug_original]
                relevant = [v for v in variants if v.get("gene") == primary_gene]

                genotype = None
                phenotype = "Unknown"
                rsids = []
                
                if relevant:
                    genotype = relevant[0].get("genotype")
                    phenotype = determine_phenotype(genotype)
                    rsids = [v.get("rsid") for v in relevant if v.get("rsid")]

                risk_label, severity, confidence = evaluate_risk(drug_original, phenotype)

                try:
                    explanation = generate_explanation(primary_gene, phenotype, drug_original)
                except Exception as e:
                    explanation = f"Analysis completed. Phenotype {phenotype} detected for {primary_gene} gene. Clinical interpretation should be confirmed with laboratory testing."

                drug_results.append({
                    "drug": drug_original,
                    "gene": primary_gene,
                    "phenotype": phenotype,
                    "risk_label": risk_label,
                    "severity": severity,
                    "confidence": confidence,
                    "rsids": rsids,
                    "explanation": explanation
                })

            response = build_multi_drug_response(patient_id, drug_results, parsing_success)

        return jsonify(response)


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        "error": "File too large. Maximum file size is 5MB.",
        "error_code": "FILE_TOO_LARGE"
    }), 413
