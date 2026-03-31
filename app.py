import os
import sqlite3
import re
import time
import fitz  
import ollama
from flask import Flask
from flask import render_template
from flask import request
from flask import redirect
from flask import session
from flask import flash
from flask import send_from_directory
from flask import jsonify
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Paragraph
from reportlab.platypus import Spacer
from reportlab.platypus import Table
from reportlab.platypus import TableStyle
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.shapes import Rect
from reportlab.graphics.shapes import String


app = Flask(__name__)
app.secret_key = "supersecretkey_vibeflow_2026"

# CONFIGURATIONS
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

AVAILABLE_MODELS = {
    "chatbot": "tinyllama",
    "resume": "phi3:mini"
}

# COMPANY RESUME TEMPLATES

company_templates = {
    "tcs": [
        "career objective",
        "education",
        "technical skills",
        "projects",
        "certifications"
    ],
    "infosys": [
        "career objective",
        "education",
        "technical skills",
        "projects",
        "internship"
    ],
    "microsoft": [
        "summary",
        "skills",
        "projects",
        "experience",
        "education"
    ],
    "apple": [
        "profile",
        "skills",
        "experience",
        "education"
    ],
    "google": [
        "summary",
        "education",
        "experience",
        "technical skills",
        "open source"
    ],
    "amazon": [
        "professional summary",
        "skills",
        "work experience",
        "education",
        "leadership"
    ],
    "meta": [
        "experience",
        "technical skills",
        "education",
        "projects",
        "impact"
    ],
    "netflix": [
        "core skills",
        "experience",
        "education",
        "innovation"
    ],
    "ibm": [
        "profile",
        "skills",
        "professional experience",
        "education",
        "certifications"
    ],
    "oracle": [
        "objective",
        "skills",
        "professional experience",
        "projects",
        "education"
    ],
    "adobe": [
        "summary",
        "skills",
        "experience",
        "projects",
        "education"
    ],
    "intel": [
        "technical skills",
        "experience",
        "education",
        "publications",
        "awards"
    ],
    "salesforce": [
        "skills",
        "professional experience",
        "cloud experience",
        "education",
        "certifications"
    ],
    "cisco": [
        "objective",
        "networking skills",
        "experience",
        "education",
        "certifications"
    ]
}

# SKILLS DATABASE 

skills_db = [
    "python",
    "java",
    "sql",
    "machine learning",
    "data analysis",
    "flask",
    "django",
    "react",
    "docker",
    "aws",
    "git",
    "linux",
    "cloud computing",
    "networking",
    "cybersecurity",
    "javascript",
    "c++",
    "php",
    "mysql"
]


# CORE LOGIC FUNCTIONS

def company_analyzer(text, company):
    """Analyze resume based on specific company standards."""
    text = text.lower()
    template = company_templates.get(company, [])

    matched = []
    missing = []

    for section in template:
        if section in text:
            matched.append(section)
        else:
            missing.append(section)

    total_sections = len(template)
    if total_sections > 0:
        score = (len(matched) / total_sections) * 100
    else:
        score = 0

    feedback = f"""
{company.upper()} Resume Compatibility Score: {round(score,2)}%

Matched Sections:
{', '.join(matched) if matched else 'None'}

Missing Sections:
{', '.join(missing) if missing else 'None'}

Suggestions:
Add the missing sections like {', '.join(missing[:2])} to better match {company.upper()} resume standards.
"""
    return feedback, round(score, 2)


def ats_analyzer(text):
    """General ATS Score calculation based on skills and contact info."""
    text = text.lower()
    clean_text = re.sub(r'[^\w\s]', '', text)

    # Skill matching
    matched = []
    missing = []
    for skill in skills_db:
        if skill in clean_text:
            matched.append(skill)
        else:
            missing.append(skill)

    # Calculate base keyword score (40%)
    keyword_score = (len(matched) / len(skills_db)) * 40

    # Contact Info check (20%)
    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    phone_pattern = r"\b\d{10}\b"
    
    email_score = 10 if re.search(email_pattern, text) else 0
    phone_score = 10 if re.search(phone_pattern, text) else 0

    # Section headers check (40%)
    section_score = 0
    important_sections = ["education", "experience", "skills"]
    for section in important_sections:
        if section in text:
            section_score += 13.33

    ats_score = keyword_score + email_score + phone_score + section_score
    if ats_score > 100:
        ats_score = 100

    feedback = f"""
Standard ATS Score: {round(ats_score,2)}%

Matched Skills:
{', '.join(matched) if matched else 'None'}

Missing Skills:
{', '.join(missing[:5])} (Top 5 Recommendations)

Suggestions:
Increase keyword density for your target role and ensure professional formatting.
"""
    return feedback, round(ats_score, 2)


def extract_skills(text):
    """Extract known skills from the resume text."""
    text = text.lower()
    found_skills = []
    for skill in skills_db:
        if skill in text:
            found_skills.append(skill)
    return found_skills


def extract_text_from_pdf(pdf_path):
    """Open PDF and return its text content."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def add_watermark(canvas, doc):
    """Add VIBE FLOW watermark to the generated PDF reports."""
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 70)
    canvas.setFillColorRGB(0.92, 0.92, 0.92)
    canvas.translate(300, 400)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, "VIBE FLOW")
    canvas.restoreState()

# DATABASE INITIALIZATION

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'user',
        score INTEGER,
        resume TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        filename TEXT,
        model TEXT,
        score INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ROUTES: 

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO users (email, password, role) VALUES (?, ?, ?)",
                (email, password, "user")
            )
            conn.commit()
            flash("Registration successful!")
            return redirect("/login")
        except:
            flash("Email already exists in our system.")
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # Static Admin Credentials Check
        if email == "site@gmail.com" and password == "admin8781":
            session["user"] = email
            session["role"] = "admin"
            return redirect("/admin")

        # Database User Check
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=?", (email,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user"] = user[1]
            session["role"] = user[3]
            return redirect("/dashboard")
        else:
            flash("Invalid Email or Password.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect("/login")

# ROUTES: MAIN APPLICATION

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")
    
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT filename, model, score, timestamp FROM history WHERE user_email=? ORDER BY timestamp DESC LIMIT 5", (session["user"],))
    history_records = c.fetchall()
    conn.close()

    return render_template("dashboard.html", models=AVAILABLE_MODELS, history=history_records)


@app.route("/upload", methods=["POST"])
def upload():
    if "user" not in session:
        return redirect("/login")

    file = request.files.get("resume")
    selected_option = request.form.get("model")

    if not file:
        flash("Please select a PDF file first.")
        return redirect("/dashboard")

    # Securely save the uploaded file
    filename = str(int(time.time())) + "_" + secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # Process PDF content
    text = extract_text_from_pdf(filepath)
    raw_text = text[:1500] # Limit for AI performance
    
    skills = extract_skills(text)

    # --- MAIN LOGIC SELECTOR ---
    
    # 1. Company Based Analysis
    if selected_option in company_templates:
        feedback, score = company_analyzer(text, selected_option)
    
    # 2. General ATS Logic
    elif selected_option == "ats":
        feedback, score = ats_analyzer(text)
    
    # 3. AI Based Analysis (Ollama)
    elif selected_option in AVAILABLE_MODELS:
        model_name = AVAILABLE_MODELS[selected_option]
        
        prompt = f"""
        You are an expert ATS (Applicant Tracking System) Analyzer.
        Analyze this resume text:
        {raw_text}

        Return ONLY the following details:
        ATS Score: [number between 0-100]
        Strengths: (list 5 short points)
        Missing Skills: (list 5 short points)
        Suggestions: (list 5 short points)
        
        Format the output clearly using bullet points for lists.
        """
        
        try:
            response = ollama.chat(
                model=model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            feedback = response["message"]["content"]
            
            # Extract score from AI response using Regex (handles brackets and asterisks)
            match = re.search(r'Score\s*[:=]?\s*[\*\[]*\s*(\d+)', feedback, re.IGNORECASE)
            score = int(match.group(1)) if match else 50
        except:
            feedback = "AI Error: Could not connect to Ollama server."
            score = 0
            
    else:
        feedback, score = "Error: Invalid selection", 0

    # Save Analysis result to user profile & history
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute(
        "UPDATE users SET score=?, resume=? WHERE email=?",
        (score, filename, session["user"])
    )
    c.execute(
        "INSERT INTO history (user_email, filename, model, score) VALUES (?, ?, ?, ?)",
        (session["user"], filename, selected_option, score)
    )
    
    # Fetch updated history to instantly show on UI
    c.execute("SELECT filename, model, score, timestamp FROM history WHERE user_email=? ORDER BY timestamp DESC LIMIT 5", (session["user"],))
    history_records = c.fetchall()
    conn.close()

    return render_template(
        "dashboard.html",
        result=feedback,
        score=score,
        skills=skills,
        models=AVAILABLE_MODELS,
        history=history_records
    )

# ROUTES: ADMIN PANEL

@app.route("/admin")
def admin():
    if "user" not in session or session.get("role") != "admin":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT id, email, score, resume FROM users WHERE role != 'admin'")
    users = c.fetchall()

    total_users = len(users)
    total_resumes = sum(1 for u in users if u[3])
    
    scores = []
    for u in users:
        if u[2] is not None:
            try:
                scores.append(float(u[2]))
            except:
                pass
                
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    conn.close()

    return render_template(
        "admin.html", 
        users=users, 
        total_users=total_users, 
        total_resumes=total_resumes, 
        avg_score=avg_score
    )


@app.route("/delete_user/<int:user_id>")
def delete_user(user_id):
    if "user" not in session or session.get("role") != "admin":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

    flash("User deleted successfully.")
    return redirect("/admin")

# ROUTES: UTILITIES (PDF, CHAT, LOADING)

@app.route("/download_report")
def download_report():
    score = request.args.get("score")
    feedback = request.args.get("feedback")

    score_val = float(score) if score else 0

    file_output = "ats_report.pdf"
    doc = SimpleDocTemplate(file_output, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title Styling
    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Title'], fontSize=28,
        textColor=colors.HexColor("#146588"), alignment=1
    )
    story.append(Paragraph("VIBE FLOW - AI REPORT", title_style))
    story.append(Spacer(1, 20))

    # Visual Score bar
    d = Drawing(400, 50)
    d.add(Rect(50, 10, 300, 15, fillColor=colors.HexColor("#eeeeee"), strokeColor=None))
    
    # Dynamic Color based on score
    if score_val < 40:
        bar_color = colors.HexColor("#e74c3c")
    elif score_val < 70:
        bar_color = colors.HexColor("#f1c40f")
    else:
        bar_color = colors.HexColor("#2ecc71")

    d.add(Rect(50, 10, (score_val/100)*300, 15, fillColor=bar_color, strokeColor=None))
    d.add(String(160, -10, f"ATS Match Score: {score}%", fontSize=12, fontName='Helvetica-Bold'))
    story.append(d)
    story.append(Spacer(1, 40))

    # Details Section
    story.append(Paragraph("<b>Detailed Feedback:</b>", styles['Heading2']))
    story.append(Spacer(1, 15))

    safe_feedback = feedback.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_feedback = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', safe_feedback)
    safe_feedback = safe_feedback.replace("\n", "<br/>")

    p_feedback = Paragraph(safe_feedback, styles['Normal'])
    
    table_data = [
        ["Category", "Information"],
        ["Analysis Score", f"{score}%"]
    ]

    fb_table = Table(table_data, colWidths=[120, 400])
    fb_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor("#146588")),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.white),
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))

    story.append(fb_table)
    story.append(Spacer(1, 25))
    
    story.append(Paragraph("<b>AI Analysis Feedback:</b>", styles['Heading3']))
    story.append(Spacer(1, 10))
    story.append(p_feedback)
    doc.build(story, onFirstPage=add_watermark, onLaterPages=add_watermark)

    return send_from_directory(".", file_output, as_attachment=True)


@app.route("/chat", methods=["POST"])
def chat():
    """Simple chatbot route for VibeFlow assistance."""
    user_msg = request.json.get("message")

    try:
        response = ollama.chat(
            model=AVAILABLE_MODELS.get("chatbot", "tinyllama"),
            messages=[
                {"role": "system", "content": "You are VibeFlow Assistant. Answer only resume-related questions concisely."},
                {"role": "user", "content": user_msg}
            ]
        )
        reply = response["message"]["content"]
    except:
        reply = "I'm sorry, my AI brain is currently resting. Please try again later."

    return jsonify({"reply": reply})


@app.route("/loading")
def loading():
    """Renders the loading animation page during analysis."""
    return render_template("loading.html")


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    """Admin only route to view raw uploaded resumes."""
    if "user" not in session or session.get("role") != "admin":
        return redirect("/login")
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# START SERVER

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)