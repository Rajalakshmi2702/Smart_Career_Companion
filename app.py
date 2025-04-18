import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Access your keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

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

# New: Import job market insights functions
from job_market import get_trending_jobs, get_in_demand_skills, get_salary_benchmarks

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = SECRET_KEY  # Loaded from environment

# Initialize extensions
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

# Resume Generation Routes
@app.route('/create_resume', methods=['GET', 'POST'])
@login_required
def create_resume():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        summary = request.form.get('summary', '')
        skills = request.form.get('skills', '')
        certifications = request.form.get('certifications', '')
        achievements = request.form.get('achievements', '')
        projects = request.form.get('projects', '')
        experience = request.form.get('experience', '')
        education = request.form.get('education', '')

        if not full_name or not email or not phone:
            flash("Missing required fields!", "danger")
            return render_template('resume_form.html')

        pdf_filename = f"{full_name.replace(' ', '_')}_resume.pdf"
        resume_directory = os.path.join(os.getcwd(), 'static', 'resumes')
        pdf_path = os.path.join(resume_directory, pdf_filename)
        os.makedirs(resume_directory, exist_ok=True)

        resume = Resume.query.filter_by(user_id=current_user.id).first()
        if resume:
            for attr, value in locals().items():
                if hasattr(resume, attr):
                    setattr(resume, attr, value)
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

        html = render_template('resume.html', **locals())
        try:
            HTML(string=html).write_pdf(pdf_path)
            flash("Resume generated successfully!", "success")
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f"Error generating PDF: {e}", "danger")
    return render_template('resume_form.html')

@app.route('/resume/download')
@login_required
def download_resume():
    resume = Resume.query.filter_by(user_id=current_user.id).first()
    if resume and resume.file_path:
        return send_file(resume.file_path, as_attachment=True)
    flash("No resume found. Please generate one first.", "warning")
    return redirect(url_for('dashboard'))

# Resume Scoring
@app.route('/resume/score', methods=['GET', 'POST'])
@login_required
def resume_score():
    score = None
    if request.method == 'POST':
        file = request.files.get('resume')
        if not file or not file.filename.lower().endswith('.pdf'):
            flash('Please upload a valid PDF.', 'danger')
            return redirect(request.url)
        try:
            reader = PdfReader(file)
            text = '\n'.join([p.extract_text() or '' for p in reader.pages])
            if not text.strip():
                flash('No text extracted.', 'danger')
                return redirect(request.url)
            score = get_resume_score(text)
        except Exception as e:
            flash(f"Error processing PDF: {e}", 'danger')
            return redirect(request.url)
    return render_template('resume_score.html', score=score)

def get_resume_score(resume_text):
    prompt = f"""
Analyze this resume and rate it on a scale of 1 to 100 (Score: X/100).
Provide bullet point recommendations.
Resume Content:
{resume_text}
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.7,"topP":0.95,"topK":40}}
    res = requests.post(url, headers={'Content-Type':'application/json'}, json=payload)
    if res.status_code == 200:
        data = res.json()
        txt = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text','')
        m = re.search(r"Score:\s*(\d+)", txt)
        return {'score': m.group(1) if m else 'N/A', 'feedback': txt}
    return {'score': 'Error', 'feedback': res.text}

# Job Market Insights
@app.route('/job-market')
@login_required
def job_market():
    country = request.args.get('country')
    domain = request.args.get('domain')
    jobs = get_trending_jobs(country, domain)
    skills = get_in_demand_skills()
    salary = get_salary_benchmarks()
    return render_template('job_market.html', jobs=jobs, skills=skills, salary=salary, selected_country=country, selected_domain=domain)

# Certificates & Badges
@app.route('/badges_certificates', methods=['GET','POST'])
@login_required
def badges_certificates():
    if request.method=='POST':
        file = request.files.get('certificate')
        if not file or file.filename=='':
            flash('No file selected.', 'danger')
            return redirect(request.url)
        filename = secure_filename(file.filename)
        dir_ = os.path.join(os.getcwd(),'static','certificates')
        os.makedirs(dir_, exist_ok=True)
        path = os.path.join(dir_,filename)
        file.save(path)
        cert = Certificate(user_id=current_user.id,file_name=filename,file_path=path)
        db.session.add(cert); db.session.commit()
        flash('Uploaded!', 'success')
        return redirect(url_for('badges_certificates'))
    certs = Certificate.query.filter_by(user_id=current_user.id).all()
    return render_template('badges_certificates.html', certificates=certs)

@app.route('/certificate/download/<int:certificate_id>')
@login_required
def download_certificate(certificate_id):
    cert = Certificate.query.filter_by(id=certificate_id, user_id=current_user.id).first()
    if cert:
        return send_file(cert.file_path, as_attachment=True)
    flash('Not found.', 'danger')
    return redirect(url_for('badges_certificates'))

@app.route('/certificate/<int:certificate_id>/qr')
@login_required
def certificate_qr(certificate_id):
    cert = Certificate.query.filter_by(id=certificate_id, user_id=current_user.id).first()
    if not cert or not cert.file_name.lower().endswith('.pdf'):
        flash('Invalid cert.', 'danger'); return redirect(url_for('badges_certificates'))
    try:
        doc = fitz.open(cert.file_path)
        img = Image.open(BytesIO(doc.load_page(0).get_pixmap().tobytes('png')))
        objs = decode(img)
        if not objs:
            flash('No QR.', 'danger'); return redirect(url_for('badges_certificates'))
        obj = objs[0]
        r = obj.rect; qr = img.crop((r.left,r.top,r.right,r.bottom))
        buf = BytesIO(); qr.save(buf,'PNG'); data = base64.b64encode(buf.getvalue()).decode('utf-8')
        return render_template('certificate_qr.html', qr_data=data)
    except Exception as e:
        flash(f'Error: {e}','danger'); return redirect(url_for('badges_certificates'))

@app.route('/certificate/delete/<int:certificate_id>', methods=['POST'])
@login_required
def delete_certificate(certificate_id):
    cert = Certificate.query.filter_by(id=certificate_id, user_id=current_user.id).first()
    if cert:
        if os.path.exists(cert.file_path): os.remove(cert.file_path)
        db.session.delete(cert); db.session.commit()
        flash('Deleted.', 'success')
    else:
        flash('Not found.', 'danger')
    return redirect(url_for('badges_certificates'))

@app.route('/certificate/verify_qr/<int:certificate_id>')
@login_required
def verify_certificate_qr(certificate_id):
    cert = Certificate.query.filter_by(id=certificate_id, user_id=current_user.id).first()
    if not cert or not cert.file_name.lower().endswith('.pdf'):
        flash('Invalid cert.', 'danger'); return redirect(url_for('badges_certificates'))
    try:
        doc = fitz.open(cert.file_path)
        img = Image.open(BytesIO(doc.load_page(0).get_pixmap().tobytes('png')))
        objs = decode(img)
        if not objs:
            flash('No QR.', 'danger'); return redirect(url_for('badges_certificates'))
        data = objs[0].data.decode('utf-8')
        return render_template('verify_qr.html', qr_data=data)
    except Exception as e:
        flash(f'Error: {e}','danger'); return redirect(url_for('badges_certificates'))

@app.route('/skill_verification')
@login_required
def skill_verification():
    certs = Certificate.query.filter_by(user_id=current_user.id).all()
    return render_template('skill_verification.html', certificates=certs)

# Skill Gap Analysis
@app.route('/skill-gap-analysis', methods=['GET','POST'])
@login_required
def skill_gap_analysis():
    if request.method=='POST':
        curr = request.form.get('current_skills')
        dom = request.form.get('target_domain')
        courses = get_course_recommendations(curr, dom)
        return render_template('skill_gap_results.html', courses=courses, current_skills=curr, target_domain=dom)
    return render_template('skill_gap_analysis.html')

def get_course_recommendations(skills, domain):
    mapping = {"web development":"web_development","data analytics":"data_science","machine learning":"data_science"}
    slug = mapping.get(domain.lower(), domain.lower().replace(' ','_') if domain else 'all')
    url = f"https://udemy-api2.p.rapidapi.com/v1/udemy/category/{slug}"
    headers = {"Content-Type":"application/json","x-rapidapi-host":"udemy-api2.p.rapidapi.com","x-rapidapi-key":RAPIDAPI_KEY}
    payload = {"page":1,"page_size":5,"sort":"popularity","locale":"en_US"}
    try:
        res = requests.post(url, headers=headers, json=payload)
        data = res.json().get('data',{}).get('courses',[]) if res.status_code==200 else []
        skills_list = [s.strip().lower() for s in (skills or '').split(',')]
        filtered = [c for c in data if any(sk in (c.get('title','')+c.get('headline','')).lower() for sk in skills_list)]
        return filtered or data
    except Exception as e:
        flash(f"Error: {e}", 'danger'); return []

# Job Recommendation
@app.route('/job-recommendation', methods=['GET','POST'])
@login_required
def job_recommendation():
    if request.method=='POST':
        prefs = request.form.get('preferences')
        skills = request.form.get('skills')
        exp = request.form.get('experience')
        jobs = get_job_recommendations(prefs, skills, exp)
        return render_template('job_results.html', jobs=jobs, preferences=prefs, skills=skills, experience=exp)
    return render_template('job_recommendation.html')

def get_job_recommendations(preferences, skills, experience):
    query = ' '.join(filter(None,[preferences, skills, experience]))
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
    params = {"query": query, "num_pages": "1", "page": "1"}
    try:
        res = requests.get(url, headers=headers, params=params)
        jobs = res.json().get('data', []) if res.status_code==200 else []
        return [{"job_title":j.get('job_title'),"employer_name":j.get('employer_name'),"location":j.get('location','Not specified'),"job_link":j.get('job_apply_link','#')} for j in jobs]
    except Exception as e:
        print(e); return []

# Career Main Page
@app.route('/career-main')
@login_required
def career_main():
    return render_template('career_main.html')

# Career Catalyst Chatbot
@app.route('/career-catalyst', methods=['GET','POST'])
@login_required
def career_catalyst():
    default_query = request.form.get('default_query','')
    user_query = request.form.get('user_query','')
    additional = request.form.get('additional_input','').strip()
    response_text = None

    # Build prompt logic...
    # (omitted for brevity, same as original but using GEMINI_API_KEY)
    prompt = default_query or user_query
    if prompt:
        response_text = get_career_catalyst_response(prompt)
    return render_template('career_catalyst.html', response=response_text, default_query=default_query, additional_input=additional)

def get_career_catalyst_response(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.7,"topP":0.95,"topK":40}}
    res = requests.post(url, headers={'Content-Type':'application/json'}, json=payload)
    if res.status_code==200:
        txt = res.json().get('candidates',[{}])[0].get('content',{}).get('parts',[{}])[0].get('text','')
        return clean_response(txt)
    return f"Error: {res.status_code}"

def clean_response(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return '<br><br>'.join(lines)

# Mock Interview
@app.route('/mock-interview', methods=['GET','POST'])
@login_required
def mock_interview():
    conversation = request.form.get('conversation','')
    user_answer = request.form.get('user_answer','')
    response_text = None
    if request.method=='POST':
        if user_answer.strip():
            conversation += "\nUser: " + user_answer.strip()
        elif not conversation.strip():
            conversation = "Interviewer: Let's begin our mock interview for a Software Engineer role.\nQuestion: Tell me about yourself."
        response_text = get_mock_interview_response(conversation)
        conversation += "\nInterviewer: " + response_text.strip()
    return render_template('mock_interview.html', interview_response=response_text, conversation=conversation)

def get_mock_interview_response(conversation):
    prompt = f"""
You are a professional interview coach. Here is the conversation so far:
{conversation}
Provide feedback on the last answer and ask the next question.
Format:
Question: ...\nFeedback: ...
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.7,"topP":0.95,"topK":40}}
    res = requests.post(url, headers={'Content-Type':'application/json'}, json=payload)
    if res.status_code==200:
        txt = res.json().get('candidates',[{}])[0].get('content',{}).get('parts',[{}])[0].get('text','')
        return remove_bullet_points(txt)
    return f"Error: {res.status_code}"

def remove_bullet_points(text):
    return "\n".join([re.sub(r'^\s*[\*\-]\s+', '', l) for l in text.splitlines()])

if __name__ == '__main__':
    app.run(debug=True)
