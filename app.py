from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from services.vcf_parser import parse_vcf
from services.phenotype_engine import determine_phenotype
from services.risk_engine import PRIMARY_GENE_MAP, evaluate_risk
from services.gemini_service import generate_explanation
from services.json_builder import build_response, build_multi_drug_response
from utils.validators import validate_file_extension, validate_file_size
from models import init_db, get_db, User, Scan
from config import Config
from bson import ObjectId
from datetime import datetime
import math

app = Flask(__name__)
app.config.from_object(Config)

init_db(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

app.json.sort_keys = False
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

SUPPORTED_DRUGS = [d.upper() for d in PRIMARY_GENE_MAP.keys()]
ALLOWED_EXTENSIONS = {'vcf'}
MAX_FILE_SIZE = 5 * 1024 * 1024

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)

def save_scan(user_id, data):
    try:
        patient_id = data.get('patient_id', '')
        drug = data.get('drug', '')
        
        if isinstance(drug, list):
            drug = ', '.join(drug)
        
        scan_id = Scan.create(user_id, patient_id, drug, data)
        return scan_id
    except Exception as e:
        print(f"Error saving scan: {e}")
        return None

@app.route("/")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template("landing.html")

@app.route("/demo")
def demo():
    # High-fidelity sample data for public demo
    sample_data = {
        "patient_id": "DEMO-PATIENT-01",
        "drug": "WARFARIN",
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "parsing_status": "success",
        "pharmacogenomic_profile": {
            "primary_gene": "CYP2C9",
            "phenotype": "Poor Metabolizer",
            "diplotype": "*3/*3",
            "detected_variants": [
                {"rsid": "rs1057910", "genotype": "C/C", "gene": "CYP2C9"}
            ]
        },
        "risk_assessment": {
            "risk_label": "TOXIC",
            "severity": "high",
            "confidence_score": 0.98
        },
        "clinical_recommendation": {
            "action": "Significant Dose Reduction Required",
            "dose_adjustment": "Reduce starting dose by 50-75%",
            "monitoring": "Daily INR monitoring until stable"
        },
        "llm_generated_explanation": {
            "summary": "This patient is a CYP2C9 Poor Metabolizer (*3/*3), which significantly impairs the metabolism of S-warfarin. This leads to higher plasma concentrations and a vastly increased risk of bleeding. Clinical guidelines (CPIC) strongly recommend a major reduction in the initial warfarin dose and frequent monitoring to prevent over-anticoagulation."
        }
    }
    return render_template("results.html", saved_report=sample_data, from_history=False)

@app.route("/analyze-page")
@login_required
def analyze_page():
    return render_template("analyze.html")

@app.route("/do-analysis", methods=["POST"])
@login_required
def do_analysis():
    """Handle web form submission and render results"""
    if "vcf_file" not in request.files:
        return render_template("analyze.html", error="VCF file is required")
    
    vcf_file = request.files["vcf_file"]
    if vcf_file.filename == "":
        return render_template("analyze.html", error="VCF file is required")
    
    file_ext_error = validate_file_extension(vcf_file.filename, ALLOWED_EXTENSIONS)
    if file_ext_error:
        return render_template("analyze.html", error=file_ext_error)
    
    file_size_error = validate_file_size(vcf_file, MAX_FILE_SIZE)
    if file_size_error:
        return render_template("analyze.html", error=file_size_error)
    
    drug = request.form.get("drug_input")
    patient_id = request.form.get("patient_id")
    
    if not drug or not drug.strip():
        return render_template("analyze.html", error="Drug input is required")
    if not patient_id:
        return render_template("analyze.html", error="Patient ID is required")
    
    drug_list = [d.strip().upper() for d in drug.split(",") if d.strip()]
    drug_list = [d for d in drug_list if d]
    
    invalid_drugs = [d for d in drug_list if d not in SUPPORTED_DRUGS]
    if invalid_drugs:
        return render_template("analyze.html", error=f"Unsupported drug: {invalid_drugs[0]}")
    
    if not drug_list:
        return render_template("analyze.html", error="Drug input is required")
    
    parsing_success = False
    try:
        vcf_file.seek(0)
        variants = parse_vcf(vcf_file.stream)
        parsing_success = True
    except ValueError as e:
        return render_template("analyze.html", error=str(e))
    except Exception:
        return render_template("analyze.html", error="Failed to parse VCF file. Please ensure the file is a valid VCF format.")
    
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
        
        if not relevant:
            explanation = "No actionable pharmacogenomic variants detected."
        else:
            try:
                explanation = generate_explanation(primary_gene, phenotype, drug_original)
            except Exception:
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
            
            if not relevant:
                explanation = "No actionable pharmacogenomic variants detected."
            else:
                try:
                    explanation = generate_explanation(primary_gene, phenotype, drug_original)
                except Exception:
                    explanation = f"Analysis completed. Phenotype {phenotype} detected for {primary_gene} gene. Clinical interpretation should be confirmed with laboratory testing."
            
            drug_results.append({
                "drug": drug_original,
                "gene": primary_gene,
                "phenotype": phenotype,
                "risk_label": risk_label,
                "severity": severity,
                "confidence": confidence,
                "rsids": rsids,
                "explanation": explanation,
                "has_relevant_variant": bool(relevant)
            })
        
        response = build_multi_drug_response(patient_id, drug_results, parsing_success)
    
    save_scan(current_user.id, response)
    return render_template("results.html", saved_report=response)

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == "POST":
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password:
            return render_template("login.html", error="Email and password are required")
        
        user = User.get_by_email(email)
        
        if user and user.check_password(password):
            User.update_last_login(user.id)
            login_user(user)
            return redirect(url_for('dashboard'))
        
        return render_template("login.html", error="Invalid email or password")
    
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == "POST":
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'clinician')
        
        if not name or not email or not password:
            return render_template("register.html", error="All fields are required")
        
        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match")
        
        if len(password) < 6:
            return render_template("register.html", error="Password must be at least 6 characters")
        
        if role not in ['clinician', 'researcher']:
            role = 'clinician'
        
        existing_user = User.get_by_email(email)
        if existing_user:
            return render_template("register.html", error="Email already registered")
        
        try:
            user = User.create(email, password, name, role)
            login_user(user)
            return redirect(url_for('dashboard'))
        except Exception as e:
            return render_template("register.html", error="Registration failed. Please try again.")
    
    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/dashboard")
@login_required
def dashboard():
    recent_scans = Scan.get_by_user(current_user.id, limit=5)
    total_scans = Scan.count_by_user(current_user.id)
    return render_template("dashboard.html", scans=recent_scans, total_scans=total_scans, user=current_user)

@app.route("/history")
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    patient_filter = request.args.get('patient_id', '')
    risk_filter = request.args.get('risk', '')
    drug_filter = request.args.get('drug', '')
    
    total_scans = Scan.count_by_user(current_user.id)
    total_pages = math.ceil(total_scans / per_page) if total_scans > 0 else 1
    skip = (page - 1) * per_page
    
    scans = Scan.search(current_user.id, patient_filter, risk_filter, drug_filter)
    
    if patient_filter or risk_filter or drug_filter:
        total_scans = len(scans)
        total_pages = math.ceil(total_scans / per_page) if total_scans > 0 else 1
        scans = scans[skip:skip + per_page]
    
    return render_template("history.html", scans=scans, total_scans=total_scans,
                           page=page, total_pages=total_pages,
                           patient_filter=patient_filter, risk_filter=risk_filter, drug_filter=drug_filter)

@app.route("/scan/<scan_id>")
@login_required
def view_scan(scan_id):
    scan = Scan.get_by_id(scan_id, current_user.id)
    if not scan:
        flash('Scan not found', 'error')
        return redirect(url_for('history'))
    return render_template("results.html", saved_report=scan['result_json'], from_history=True)

@app.route("/analyze", methods=["POST", "GET"])
@login_required
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
        except ValueError as e:
            variants = []
            return jsonify({
                "error": str(e),
                "error_code": "INVALID_VCF_FORMAT"
            }), 400
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

            if not relevant:
                explanation = "No actionable pharmacogenomic variants detected."
            else:
                try:
                    explanation = generate_explanation(primary_gene, phenotype, drug_original)
                except Exception:
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

                if not relevant:
                    explanation = "No actionable pharmacogenomic variants detected."
                else:
                    try:
                        explanation = generate_explanation(primary_gene, phenotype, drug_original)
                    except Exception:
                        explanation = f"Analysis completed. Phenotype {phenotype} detected for {primary_gene} gene. Clinical interpretation should be confirmed with laboratory testing."

                drug_results.append({
                    "drug": drug_original,
                    "gene": primary_gene,
                    "phenotype": phenotype,
                    "risk_label": risk_label,
                    "severity": severity,
                    "confidence": confidence,
                    "rsids": rsids,
                    "explanation": explanation,
                    "has_relevant_variant": bool(relevant)
                })

            response = build_multi_drug_response(patient_id, drug_results, parsing_success)

        save_scan(current_user.id, response)
        return jsonify(response)


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        "error": "File too large. Maximum file size is 5MB.",
        "error_code": "FILE_TOO_LARGE"
    })

if __name__ == "__main__":
    app.run(debug=True)
