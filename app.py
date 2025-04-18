import os
import json
import re
import requests
import google.generativeai as palm  # For Gemini API
import qrcode
import base64
from io import BytesIO
from flask import Flask, render_template, redirect, url_for, request, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from PyPDF2 import PdfReader  # For PDF text extraction
from weasyprint import HTML  # For PDF generation
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF for handling PDFs
from pyzbar.pyzbar import decode  # for decoding QR codes
from PIL import Image  # to convert bytes to an image
from io import BytesIO  # to handle byte streams



# NEW: Import job market insights functions
from job_market import get_trending_jobs, get_in_demand_skills, get_salary_benchmarks


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'supersecretkey'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
migrate = Migrate(app, db)

# -----------------------#
#      Models            #
# -----------------------#

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    skills = db.Column(db.Text, nullable=True)
    password = db.Column(db.String(256), nullable=False)

class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    skills = db.Column(db.Text, nullable=True)
    certifications = db.Column(db.Text, nullable=True)
    achievements = db.Column(db.Text, nullable=True)
    projects = db.Column(db.Text, nullable=True)
    experience = db.Column(db.Text, nullable=True)
    education = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(200), nullable=True)

# New model to hold certificates and badges uploads
class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_name = db.Column(db.String(150), nullable=False)
    file_path = db.Column(db.String(200), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# -----------------------#
#        Routes          #
# -----------------------#

@app.route('/')
def home():
    return render_template('index.html', user=current_user)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        user = User(name=name, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        flash("Signup Successful! Please login.", "success")
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash("Login Successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials, try again.", "danger")
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for('home'))

# ---------- Existing Resume Routes ---------- #

@app.route("/generate_resume", methods=["POST"])
@login_required
def generate_resume():
    full_name = request.form["full_name"]
    email = request.form["email"]
    phone = request.form["phone"]
    summary = request.form["summary"]
    skills = request.form["skills"]
    certifications = request.form["certifications"]
    achievements = request.form["achievements"]
    projects = request.form["projects"]
    experience = request.form["experience"]
    education = request.form["education"]

    pdf_filename = f"{full_name.replace(' ', '_')}_resume.pdf"
    pdf_path = os.path.join("static/resumes", pdf_filename)

    resume = Resume.query.filter_by(user_id=current_user.id).first()
    if resume:
        resume.full_name = full_name
        resume.email = email
        resume.phone = phone
        resume.summary = summary
        resume.skills = skills
        resume.certifications = certifications
        resume.achievements = achievements
        resume.projects = projects
        resume.experience = experience
        resume.education = education
        resume.file_path = pdf_path
    else:
        resume = Resume(
            user_id=current_user.id,
            full_name=full_name,
            email=email,
            phone=phone,
            summary=summary,
            skills=skills,
            certifications=certifications,
            achievements=achievements,
            projects=projects,
            experience=experience,
            education=education,
            file_path=pdf_path
        )
        db.session.add(resume)

    db.session.commit()
    
    resume_html = render_template("resume.html",
                                  full_name=full_name,
                                  email=email,
                                  phone=phone,
                                  summary=summary,
                                  skills=skills,
                                  certifications=certifications,
                                  achievements=achievements,
                                  projects=projects,
                                  experience=experience,
                                  education=education)

    try:
        HTML(string=resume_html).write_pdf(pdf_path)
    except Exception as e:
        flash(f"Error generating PDF: {str(e)}", "danger")
        return redirect(url_for("dashboard"))

    flash("Resume generated successfully!", "success")
    return redirect(url_for("dashboard"))

@app.route('/create_resume', methods=['GET', 'POST'])
@login_required
def create_resume():
    if request.method == 'POST':
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        summary = request.form.get("summary", "")
        skills = request.form.get("skills", "")
        certifications = request.form.get("certifications", "")
        achievements = request.form.get("achievements", "")
        projects = request.form.get("projects", "")
        experience = request.form.get("experience", "")
        education = request.form.get("education", "")

        if not full_name or not email or not phone:
            flash("Missing required fields!", "danger")
            return render_template("resume_form.html")

        pdf_filename = f"{full_name.replace(' ', '_')}_resume.pdf"
        resume_directory = os.path.join(os.getcwd(), "static", "resumes")
        pdf_path = os.path.join(resume_directory, pdf_filename)

        if not os.path.exists(resume_directory):
            os.makedirs(resume_directory)

        resume = Resume.query.filter_by(user_id=current_user.id).first()
        if resume:
            resume.full_name = full_name
            resume.email = email
            resume.phone = phone
            resume.summary = summary
            resume.skills = skills
            resume.certifications = certifications
            resume.achievements = achievements
            resume.projects = projects
            resume.experience = experience
            resume.education = education
            resume.file_path = pdf_path
        else:
            resume = Resume(
                user_id=current_user.id,
                full_name=full_name,
                email=email,
                phone=phone,
                summary=summary,
                skills=skills,
                certifications=certifications,
                achievements=achievements,
                projects=projects,
                experience=experience,
                education=education,
                file_path=pdf_path
            )
            db.session.add(resume)

        db.session.commit()

        resume_html = render_template("resume.html",
                                      full_name=full_name,
                                      email=email,
                                      phone=phone,
                                      summary=summary,
                                      skills=skills,
                                      certifications=certifications,
                                      achievements=achievements,
                                      projects=projects,
                                      experience=experience,
                                      education=education)
        
        try:
            HTML(string=resume_html).write_pdf(pdf_path)
        except Exception as e:
            flash(f"Error generating PDF: {str(e)}", "danger")
            return render_template("resume_form.html")

        flash("Resume generated successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("resume_form.html")

@app.route("/resume/download")
@login_required
def download_resume():
    resume = Resume.query.filter_by(user_id=current_user.id).first()
    if resume and resume.file_path:
        return send_file(resume.file_path, as_attachment=True)
    flash("No resume found. Please generate one first.", "warning")
    return redirect(url_for("dashboard"))

# ---------- Resume Score Route ---------- #

@app.route('/resume/score', methods=['GET', 'POST'])
@login_required
def resume_score():
    score = None
    if request.method == 'POST':
        if 'resume' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['resume']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        if file and file.filename.lower().endswith('.pdf'):
            try:
                pdf_reader = PdfReader(file)
                resume_text = ""
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        resume_text += text + "\n"
                if not resume_text.strip():
                    flash("No text could be extracted from the PDF.", "danger")
                    return redirect(request.url)
                score = get_resume_score(resume_text)
            except Exception as e:
                flash(f"Error processing PDF: {str(e)}", "danger")
                return redirect(request.url)
        else:
            flash('Uploaded file is not a PDF', 'danger')
            return redirect(request.url)
    return render_template("resume_score.html", score=score)

def get_resume_score(resume_text):
    prompt_str = f"""Analyze this resume and rate it on a scale of 1 to 100 (Score: X/100).
Then provide recommended changes as bullet points, each on a new line.
Resume Content:
{resume_text}"""
    api_key = "AIzaSyBRJslEP2gkoG8KEd05nlFdTS-JAUkEdyU"  # Replace with your valid API key
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": prompt_str}]}],
        "generationConfig": {"temperature": 0.7, "topP": 0.95, "topK": 40},
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=payload)

    print("API Response:", response.text)

    if response.status_code == 200:
        try:
            data = response.json()
            if "candidates" in data and len(data["candidates"]) > 0 and "content" in data["candidates"][0]:
                response_text = data["candidates"][0]["content"]["parts"][0]["text"]
                match = re.search(r"Score:\s*(\d+)\s*/\s*100", response_text)
                try:
                    score = match.group(1)
                except IndexError:
                    score = "N/A"
                feedback = response_text
                return {"score": score, "feedback": feedback}
            else:
                return {"score": "N/A", "feedback": "No score generated in the response."}
        except json.JSONDecodeError:
            return {"score": "N/A", "feedback": "Error decoding JSON response."}
    else:
        return {"score": f"Error: {response.status_code}", "feedback": response.text}

# ---------- New: Job Market Insights Route ---------- #
@app.route('/job-market')
@login_required
def job_market():
    # Read filter values from GET parameters for country and domain
    country = request.args.get('country')
    domain = request.args.get('domain')
    jobs = get_trending_jobs(country, domain)
    skills = get_in_demand_skills()  # Optionally, pass filters here if desired
    salary = get_salary_benchmarks()
    return render_template('job_market.html', 
                           jobs=jobs, 
                           skills=skills, 
                           salary=salary,
                           selected_country=country,
                           selected_domain=domain)

# ---------- New: Badges & Certificates, Skill Verification ---------- #

@app.route('/badges_certificates', methods=['GET', 'POST'])
@login_required
def badges_certificates():
    if request.method == 'POST':
        if 'certificate' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['certificate']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            cert_directory = os.path.join(os.getcwd(), "static", "certificates")
            if not os.path.exists(cert_directory):
                os.makedirs(cert_directory)
            file_path = os.path.join(cert_directory, filename)
            file.save(file_path)
            new_cert = Certificate(user_id=current_user.id, file_name=filename, file_path=file_path)
            db.session.add(new_cert)
            db.session.commit()
            flash("Certificate/Badge uploaded successfully.", "success")
            return redirect(url_for('badges_certificates'))
    certificates = Certificate.query.filter_by(user_id=current_user.id).all()
    return render_template('badges_certificates.html', certificates=certificates)

@app.route('/certificate/download/<int:certificate_id>')
@login_required
def download_certificate(certificate_id):
    cert = Certificate.query.filter_by(id=certificate_id, user_id=current_user.id).first()
    if cert:
        return send_file(cert.file_path, as_attachment=True)
    flash("Certificate not found.", "danger")
    return redirect(url_for('badges_certificates'))

@app.route('/certificate/<int:certificate_id>/qr')
@login_required
def certificate_qr(certificate_id):
    cert = Certificate.query.filter_by(id=certificate_id, user_id=current_user.id).first()
    if not cert:
        flash("Certificate not found.", "danger")
        return redirect(url_for('badges_certificates'))
    if not cert.file_name.lower().endswith('.pdf'):
        flash("QR code extraction is available only for PDF certificates.", "danger")
        return redirect(url_for('badges_certificates'))
    try:
        # Open the PDF using PyMuPDF and convert the first page to an image
        doc = fitz.open(cert.file_path)
        page = doc.load_page(0)
        pix = page.get_pixmap()
        image_data = pix.tobytes("png")
        
        # Convert image bytes to a PIL Image
        image = Image.open(BytesIO(image_data))
        
        # Use pyzbar to decode QR codes in the image
        decoded_objects = decode(image)
        if not decoded_objects:
            flash("No QR code found in the certificate.", "danger")
            return redirect(url_for('badges_certificates'))
        
        # Assume the first detected QR code is the one to use
        obj = decoded_objects[0]
        left = obj.rect.left
        top = obj.rect.top
        right = left + obj.rect.width
        bottom = top + obj.rect.height
        
        # Crop the image to the QR code area
        qr_image = image.crop((left, top, right, bottom))
        buf = BytesIO()
        qr_image.save(buf, format="PNG")
        buf.seek(0)
        
        # Encode the QR code image to base64 so it can be embedded in the template
        import base64
        img_data = base64.b64encode(buf.getvalue()).decode('utf-8')
        
        return render_template('certificate_qr.html', qr_data=img_data)
    except Exception as e:
        flash("Error extracting QR code: " + str(e), "danger")
        return redirect(url_for('badges_certificates'))

@app.route('/verify_certificate/<int:certificate_id>')
def verify_certificate(certificate_id):
    cert = Certificate.query.filter_by(id=certificate_id).first()
    if not cert:
        return "<h1>Certificate not found or invalid.</h1>"
    return render_template('verify_certificate.html', certificate=cert)

@app.route('/certificate/delete/<int:certificate_id>', methods=['POST'])
@login_required
def delete_certificate(certificate_id):
    cert = Certificate.query.filter_by(id=certificate_id, user_id=current_user.id).first()
    if not cert:
        flash("Certificate not found.", "danger")
        return redirect(url_for('badges_certificates'))
    if os.path.exists(cert.file_path):
        os.remove(cert.file_path)
    db.session.delete(cert)
    db.session.commit()
    flash("Certificate deleted successfully.", "success")
    return redirect(url_for('badges_certificates'))

@app.route('/certificate/verify_qr/<int:certificate_id>')
@login_required
def verify_certificate_qr(certificate_id):
    cert = Certificate.query.filter_by(id=certificate_id, user_id=current_user.id).first()
    if not cert:
        flash("Certificate not found.", "danger")
        return redirect(url_for('badges_certificates'))
    if not cert.file_name.lower().endswith('.pdf'):
        flash("QR code verification is available only for PDF certificates.", "danger")
        return redirect(url_for('badges_certificates'))
    try:
        # Open the PDF using PyMuPDF and load the first page
        doc = fitz.open(cert.file_path)
        page = doc.load_page(0)
        pix = page.get_pixmap()
        image_data = pix.tobytes("png")
        
        # Convert image bytes to a PIL Image
        image = Image.open(BytesIO(image_data))
        decoded_objects = decode(image)
        if not decoded_objects:
            flash("No QR code found in the certificate.", "danger")
            return redirect(url_for('badges_certificates'))
        qr_data = decoded_objects[0].data.decode('utf-8')
        # Instead of redirecting, render a verification page with buttons for link and sharing
        return render_template('verify_qr.html', qr_data=qr_data)
    except Exception as e:
        flash("Error during QR code verification: " + str(e), "danger")
        return redirect(url_for('badges_certificates'))

@app.route('/skill_verification')
@login_required
def skill_verification():
    certificates = Certificate.query.filter_by(user_id=current_user.id).all()
    return render_template('skill_verification.html', certificates=certificates)





# ---------- Skill Gap Analysis Feature ---------- #
@app.route('/skill-gap-analysis', methods=['GET', 'POST'])
@login_required
def skill_gap_analysis():
    if request.method == 'POST':
        # Get user inputs from the form.
        current_skills = request.form.get('current_skills')
        target_domain = request.form.get('target_domain')
        
        # Get course recommendations based on skills and target domain.
        recommendations = get_course_recommendations(current_skills, target_domain)
        
        # Pass recommendations as "courses" and other data to the template.
        return render_template('skill_gap_results.html', courses=recommendations, current_skills=current_skills, target_domain=target_domain)
    
    # For GET requests, render the analysis form.
    return render_template('skill_gap_analysis.html')


def get_course_recommendations(skills, domain):
    """
    Query the Udemy API via RapidAPI and return a list of course recommendations.
    Uses a mapping to convert the target domain to a valid Udemy category slug.
    Filters the courses based on the provided current skills.
    """
    # Mapping of user-entered domains to Udemy category slugs.
    domain_mapping = {
    "web development": "web_development",
    "data analytics": "data_science",
    "data analysis": "data_science",
    "machine learning": "data_science"  # or the correct slug if different
}

    
    # Convert the target domain into a category slug.
    domain_lower = domain.lower() if domain else ""
    category_slug = domain_mapping.get(domain_lower, domain_lower.replace(" ", "_") if domain_lower else "all")
    
    url = f"https://udemy-api2.p.rapidapi.com/v1/udemy/category/{category_slug}"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "udemy-api2.p.rapidapi.com",
        "x-rapidapi-key": "cc4555b44bmsh12bb570027fd569p17d9cajsn35c983318890"  # Replace with your actual RapidAPI Key if needed.
    }
    
    payload = {
        "page": 1,
        "page_size": 5,
        "ratings": "",
        "instructional_level": [],
        "lang": [],
        "price": [],
        "duration": [],
        "subtitles_lang": [],
        "sort": "popularity",
        "features": [],
        "locale": "en_US",
        "extract_pricing": True
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            # Courses are contained in the "courses" field within "data".
            courses = data.get("data", {}).get("courses", [])
            
            # Prepare a list of skills (converted to lowercase) for filtering.
            skills_list = [skill.strip().lower() for skill in skills.split(",")] if skills else []
            filtered_courses = []
            for course in courses:
                title = course.get("title", "").lower()
                headline = course.get("headline", "").lower()
                
                # Check if any of the skills appear in the title or headline.
                skill_match = any(skill in title or skill in headline for skill in skills_list) if skills_list else True
                
                if skill_match:
                    filtered_courses.append(course)
            
            # If no courses match the skills filter, return the unfiltered courses.
            return filtered_courses if filtered_courses else courses
        else:
            flash("Error fetching course recommendations. Please try again later.", "danger")
            return []
    except Exception as e:
        flash(f"An error occurred: {str(e)}", "danger")
        return []


#------------JOB RECOMMENDATION -----------------------#

@app.route('/job-recommendation', methods=['GET', 'POST'])
@login_required
def job_recommendation():
    if request.method == 'POST':
        preferences = request.form.get('preferences')
        skills = request.form.get('skills')
        experience = request.form.get('experience')

        jobs = get_job_recommendations(preferences, skills, experience)

        return render_template('job_results.html', jobs=jobs,
                               preferences=preferences, skills=skills,
                               experience=experience)

    return render_template('job_recommendation.html')


def get_job_recommendations(preferences, skills, experience):
    url = "https://jsearch.p.rapidapi.com/search"

    query = preferences or ""
    if skills:
        query += f" {skills}"
    if experience:
        query += f" {experience}"

    querystring = {
        "query": query,
        "num_pages": "1",
        "page": "1"
    }

    headers = {
        "X-RapidAPI-Key": "71c46cc8femsh18850742b7ce6a5p1f8112jsnb6ed11380ff0",  # Replace with your actual key
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)
        if response.status_code == 200:
            data = response.json()
            jobs = data.get("data", [])

            mapped_jobs = []
            for job in jobs:
                mapped_jobs.append({
                    "job_title": job.get("job_title"),
                    "employer_name": job.get("employer_name"),
                    "location": job.get("location") or "Not specified",
                    "job_link": job.get("job_apply_link") or "#"
                })

            return mapped_jobs
        else:
            print("API Error:", response.status_code, response.text)
            return []
    except Exception as e:
        print("Exception occurred:", str(e))
        return []

# ---------- New: Career Main Page ----------
@app.route('/career-main')
@login_required
def career_main():
    return render_template('career_main.html')

# ---------- Modified: Career Catalyst Feature (Chatbot) ----------
@app.route('/career-catalyst', methods=['GET', 'POST'])
@login_required
def career_catalyst():
    response_text = None
    # Retrieve both the main query and additional details if provided.
    default_query = request.form.get('default_query', '')
    user_query = request.form.get('user_query', '')
    additional_input = request.form.get('additional_input', '').strip()

    # Check if a default query was chosen from the dropdown.
    if default_query:
        # For options that require additional details, if not provided, ask the user.
        if default_query in ["Information on workshops", "Virtual meets", "The latest industry updates", "Booming opportunities"]:
            if not additional_input:
                response_text = f"Please provide additional details. For example, for '{default_query}', mention the domain or area you are interested in."
                return render_template('career_catalyst.html', response=response_text, default_query=default_query)
            # Build a custom prompt for each case.
            if default_query == "Information on workshops":
                prompt = f"""You are Career Catalyst, a seasoned career advisor who provides expert guidance and detailed information on workshops.
                List out the realtime current ongoing or going to be conducted workshops and virual workshops along with the details.
The user is interested in workshops related to the domain: {additional_input}.
Provide a detailed and actionable response with upcoming workshops, relevant details, and suggestions."""
            elif default_query == "Virtual meets":
                prompt = f"""You are Career Catalyst, a seasoned career advisor who provides expert guidance and detailed information on virtual meets.
Search and tell about current realtime ongoing or upcoming virutal meets and give me details about it.
                The user is interested in virtual meets in the domain: {additional_input}.
Provide a detailed response with upcoming virtual meet opportunities and relevant information."""
            elif default_query == "The latest industry updates":
                prompt = f"""You are Career Catalyst, a seasoned career advisor who provides the latest industry updates.
The user is interested in updates in the domain: {additional_input}.
Provide a detailed and actionable response with the most current industry trends and news."""
            elif default_query == "Booming opportunities":
                prompt = f"""You are Career Catalyst, a seasoned career advisor who identifies booming opportunities.
The user is interested in booming opportunities in the domain: {additional_input}.
Provide a detailed response with specific booming opportunities and actionable insights."""
        # For options that don't require additional details, use a simple prompt.
        elif default_query == "General career advice":
            prompt = f"""You are Career Catalyst, a seasoned career advisor who provides general career advice.
Provide a detailed and actionable response based on the query: {default_query}."""
        
        else:
            prompt = user_query  # fallback if something unexpected happens.
    # If no default query was chosen, then use the free text user query.
    elif user_query:
        prompt = f"""You are Career Catalyst, a seasoned career advisor who provides expert guidance on career choices, workshops, virtual meets, industry updates, booming opportunities, and mock interview practice.
Based on the following query, provide a detailed and actionable response:
{user_query}"""
    else:
        prompt = ""  # nothing to do if neither is provided

    if prompt:
        response_text = get_career_catalyst_response(prompt)
    return render_template('career_catalyst.html', response=response_text, default_query=default_query, additional_input=additional_input)

def get_career_catalyst_response(prompt):
    api_key = "AIzaSyBRJslEP2gkoG8KEd05nlFdTS-JAUkEdyU"  # Replace with your valid API key
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "topP": 0.95, "topK": 40},
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        try:
            data = response.json()
            if "candidates" in data and len(data["candidates"]) > 0 and "content" in data["candidates"][0]:
                response_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return clean_response(response_text)
            else:
                return "No response generated."
        except Exception as e:
            return f"Error decoding response: {str(e)}"
    else:
        return f"Error: {response.status_code} - {response.text}"
def clean_response(text):
    import re

    # Remove bold and emphasis markers
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*+(.*?)\*+', r'\1', text)

    # Split and clean each line
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Add <br><br> for spacing in HTML
    return "<br><br>".join(lines)


# ---------- New: Mock Interview Chat System ----------
@app.route('/mock-interview', methods=['GET', 'POST'])
@login_required
def mock_interview():
    conversation = request.form.get('conversation', '')
    user_answer = request.form.get('user_answer', '')
    interview_response = None

    if request.method == 'POST':
        # If this is not the initial call, append the user's answer.
        if user_answer.strip():
            conversation += "\nUser: " + user_answer.strip()
        else:
            # For an initial empty conversation, start with the first question.
            if not conversation.strip():
                conversation = "Interviewer: Let's begin our mock interview for a Software Engineer role.\nQuestion: Tell me about yourself."

        # Get Gemini's feedback and next question based on the current conversation.
        interview_response = get_mock_interview_response(conversation)
        # Append Gemini's response to the conversation for continuity.
        conversation += "\nInterviewer: " + interview_response.strip()

    return render_template('mock_interview.html',
                           interview_response=interview_response,
                           conversation=conversation)

def get_mock_interview_response(conversation):
    gemini_prompt = f"""You are a professional interview coach conducting a mock interview session in a chat format. Here is the conversation so far:
{conversation}

If the last message was the user's answer, please provide detailed, actionable feedback on that answer, and then ask the next interview question. If this is the first interaction, simply ask the first question.
Format your response in the following structure:

Question: <next interview question>
Feedback: <feedback on the user's previous answer (if any)>

Only include the parts that are relevant.
"""
    api_key = "AIzaSyBRJslEP2gkoG8KEd05nlFdTS-JAUkEdyU"  # Replace with your valid API key
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": gemini_prompt}]}],
        "generationConfig": {"temperature": 0.7, "topP": 0.95, "topK": 40},
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        try:
            data = response.json()
            if ("candidates" in data and len(data["candidates"]) > 0 
                and "content" in data["candidates"][0]):
                response_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return remove_bullet_points(response_text)
            else:
                return "No response generated."
        except Exception as e:
            return f"Error decoding response: {str(e)}"
    else:
        return f"Error: {response.status_code} - {response.text}"

def remove_bullet_points(text):
    """
    Remove common bullet markers (like '*' or '-') from the start of each line.
    """
    lines = text.splitlines()
    cleaned_lines = [re.sub(r'^\s*[\*\-]\s+', '', line) for line in lines]
    return "\n".join(cleaned_lines)

if __name__ == '__main__':
    app.run(debug=True)