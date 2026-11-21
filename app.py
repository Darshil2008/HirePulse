
from flask import Flask, render_template, request, redirect, session, flash, jsonify, url_for
import sqlite3
import os
import secrets
import urllib.parse
import json
import ssl
from datetime import datetime
from functools import wraps
import requests
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "database.db")

def load_env():
    """Load environment variables from .env file if present."""
    env_file = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'").strip('"')
                    if k and k not in os.environ:
                        os.environ[k] = v

load_env()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "worklane_production_secret_key_982347981234")


def get_db():
    db_path = app.config.get("DATABASE", DB)
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db


def initialize_db():
    db = get_db()

    # Core Users Table
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)

    # Core Jobs Table
    db.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recruiter_id INTEGER,
            title TEXT,
            company TEXT,
            location TEXT,
            salary TEXT,
            description TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)

    # Core Applications Table
    db.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            user_id INTEGER,
            status TEXT DEFAULT 'Applied',
            UNIQUE(job_id, user_id)
        )
    """)

    # Safe column additions for users table
    existing_user_cols = [
        row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()
    ]
    user_new_cols = {
        "headline": "TEXT DEFAULT ''",
        "bio": "TEXT DEFAULT ''",
        "phone": "TEXT DEFAULT ''",
        "location": "TEXT DEFAULT ''",
        "skills": "TEXT DEFAULT ''",
        "experience_years": "INTEGER DEFAULT 0",
        "github_url": "TEXT DEFAULT ''",
        "linkedin_url": "TEXT DEFAULT ''",
        "portfolio_url": "TEXT DEFAULT ''",
        "resume_filename": "TEXT DEFAULT ''",
        "company_name": "TEXT DEFAULT ''",
        "company_website": "TEXT DEFAULT ''",
        "company_description": "TEXT DEFAULT ''",
        "is_verified": "INTEGER DEFAULT 0",
        "created_at": "TEXT DEFAULT ''",
        "auth_provider": "TEXT DEFAULT 'local'",
        "google_id": "TEXT DEFAULT ''",
        "avatar_url": "TEXT DEFAULT ''"
    }
    for col, defn in user_new_cols.items():
        if col not in existing_user_cols:
            db.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")

    # Safe column additions for jobs table
    existing_job_cols = [
        row["name"] for row in db.execute("PRAGMA table_info(jobs)").fetchall()
    ]
    job_new_cols = {
        "skills": "TEXT DEFAULT ''",
        "job_type": "TEXT DEFAULT 'Full-time'",
        "work_mode": "TEXT DEFAULT 'On-site'",
        "experience": "TEXT DEFAULT 'Fresher'",
        "views_count": "INTEGER DEFAULT 0",
        "department": "TEXT DEFAULT 'Engineering'",
        "is_featured": "INTEGER DEFAULT 0",
        "created_at": "TEXT DEFAULT ''"
    }
    for col, defn in job_new_cols.items():
        if col not in existing_job_cols:
            db.execute(f"ALTER TABLE jobs ADD COLUMN {col} {defn}")

    # Safe column additions for applications table
    existing_app_cols = [
        row["name"] for row in db.execute("PRAGMA table_info(applications)").fetchall()
    ]
    app_new_cols = {
        "cover_note": "TEXT DEFAULT ''",
        "resume_link": "TEXT DEFAULT ''",
        "recruiter_notes": "TEXT DEFAULT ''",
        "interview_date": "TEXT DEFAULT ''",
        "updated_at": "TEXT DEFAULT ''",
        "created_at": "TEXT DEFAULT ''"
    }
    for col, defn in app_new_cols.items():
        if col not in existing_app_cols:
            db.execute(f"ALTER TABLE applications ADD COLUMN {col} {defn}")

    # 4. Saved Jobs Table (Bookmarking)
    db.execute("""
        CREATE TABLE IF NOT EXISTS saved_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            job_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, job_id)
        )
    """)

    # 5. In-Platform Notifications Table
    db.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            message TEXT,
            link TEXT,
            is_read INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 6. Job Alerts Table
    db.execute("""
        CREATE TABLE IF NOT EXISTS job_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            criteria TEXT,
            frequency TEXT DEFAULT 'instant',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 7. Talent Network Table
    db.execute("""
        CREATE TABLE IF NOT EXISTS talent_network (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            skills TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 8. Job Reports Table (Trust & Safety)
    db.execute("""
        CREATE TABLE IF NOT EXISTS job_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            user_id INTEGER,
            reason TEXT,
            details TEXT,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migrate legacy admin emails to WorkLane
    db.execute("UPDATE users SET email='admin@worklane.com' WHERE email IN ('admin@hirepulse.com', 'admin@jobportal.com')")

    admin = db.execute(
        "SELECT id FROM users WHERE email=?",
        ("admin@worklane.com",)
    ).fetchone()

    if not admin:
        db.execute("""
            INSERT INTO users (name,email,password,role)
            VALUES (?,?,?,?)
        """, (
            "Admin User",
            "admin@worklane.com",
            generate_password_hash("admin123"),
            "admin"
        ))

    # Add demo recruiter and job seeker accounts if not present
    recruiter = db.execute(
        "SELECT id FROM users WHERE email=?",
        ("recruiter@technova.com",)
    ).fetchone()

    if not recruiter:
        db.execute("""
            INSERT INTO users (name,email,password,role,headline,company_name,company_website,is_verified)
            VALUES (?,?,?,?,?,?,?,1)
        """, (
            "Priya Sharma (TechNova HR)",
            "recruiter@technova.com",
            generate_password_hash("recruiter123"),
            "recruiter",
            "Lead Technical Talent Partner",
            "TechNova Solutions",
            "https://technova.example.com"
        ))
    else:
        db.execute("""
            UPDATE users SET 
                company_name='TechNova Solutions',
                company_website='https://technova.example.com',
                is_verified=1
            WHERE email='recruiter@technova.com' AND (company_name IS NULL OR company_name='')
        """)

    seeker = db.execute(
        "SELECT id FROM users WHERE email=?",
        ("seeker@example.com",)
    ).fetchone()

    if not seeker:
        db.execute("""
            INSERT INTO users (name,email,password,role,headline,bio,location,skills,experience_years,github_url,linkedin_url)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            "Darshil Gehlot",
            "seeker@example.com",
            generate_password_hash("seeker123"),
            "job_seeker",
            "Full Stack Python Developer & AI Engineer",
            "Building robust distributed backends, scalable RESTful APIs, and intelligent data workflows.",
            "Bangalore, India",
            "Python, Flask, JavaScript, React, PostgreSQL, Docker, Git, REST APIs",
            3,
            "https://github.com/darshil2008",
            "https://linkedin.com/in/darshilgehlot"
        ))
    else:
        db.execute("""
            UPDATE users SET 
                headline='Full Stack Python Developer & AI Engineer',
                bio='Building robust distributed backends, scalable RESTful APIs, and intelligent data workflows.',
                location='Bangalore, India',
                skills='Python, Flask, JavaScript, React, PostgreSQL, Docker, Git, REST APIs',
                experience_years=3,
                github_url='https://github.com/darshil2008',
                linkedin_url='https://linkedin.com/in/darshilgehlot'
            WHERE email='seeker@example.com' AND (skills IS NULL OR skills='')
        """)

    # Insert rich simulated jobs if the jobs table has fewer than 20 jobs
    count = db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    if count < 20:
        db.execute("DELETE FROM jobs WHERE recruiter_id IS NULL")
        
        demo_jobs = [
            # Bangalore Jobs
            ("Senior Python Developer", "TechNova Solutions", "Bangalore",
             "₹12-20 LPA", "Architect scalable microservices and REST APIs using Python, Flask, and PostgreSQL. Lead backend engineering sprints and mentor junior developers.",
             "Python, Flask, Django, PostgreSQL, Docker, Redis", "Full-time", "Hybrid", "3-5 years"),

            ("Full Stack Web Developer", "Infosys Limited", "Bangalore",
             "₹7-14 LPA", "Build customer-facing responsive web applications. Collaborate with UX designers to implement intuitive interfaces and robust REST backends.",
             "React, Node.js, Express, MongoDB, JavaScript, AWS", "Full-time", "Hybrid", "1-3 years"),

            ("Cloud & DevOps Architect", "CloudMatrix India", "Bangalore",
             "₹14-24 LPA", "Design and automate AWS/Azure cloud infrastructure. Oversee Kubernetes cluster orchestration, Terraform provisioning, and zero-downtime CI/CD deployments.",
             "AWS, Kubernetes, Docker, Terraform, CI/CD, Linux", "Full-time", "On-site", "3-5 years"),

            ("AI / Machine Learning Engineer", "NeuralWorks Labs", "Bangalore",
             "₹10-18 LPA", "Develop production-ready LLM pipelines, computer vision models, and predictive analytics services using PyTorch and HuggingFace.",
             "Python, PyTorch, TensorFlow, Scikit-learn, LangChain, FastAPI", "Full-time", "Hybrid", "2-4 years"),

            ("Rust Systems Engineer", "IronForge Systems", "Bangalore",
             "₹12-22 LPA", "Develop low-latency, memory-safe high-throughput networking libraries and distributed caching mechanisms.",
             "Rust, C++, WebAssembly, Linux, Git, Multithreading", "Full-time", "On-site", "2-4 years"),

            ("Junior Python Backend Intern", "ZetaByte Technologies", "Bangalore",
             "₹25k-35k/month", "Assist in creating RESTful endpoints, writing automated unit tests, and optimizing database queries for high-volume endpoints.",
             "Python, Flask, SQLite, Git, Postman", "Internship", "Hybrid", "Fresher"),

            # Mumbai Jobs
            ("Node.js Backend Developer", "ApiLayer Fintech", "Mumbai",
             "₹8-15 LPA", "Build secure banking and payment integration microservices. Ensure PCI-DSS compliance and sub-second latency.",
             "Node.js, Express, TypeScript, Redis, MongoDB, Kafka", "Full-time", "Hybrid", "2-4 years"),

            ("UI/UX Product Designer", "DesignHive Studio", "Mumbai",
             "₹6-11 LPA", "Create high-fidelity wireframes, user journeys, design systems, and clickable prototypes for mobile and web fintech platforms.",
             "Figma, Adobe XD, UI/UX, Design Systems, Prototyping", "Full-time", "On-site", "1-3 years"),

            ("Financial Data Analyst", "KFin Analytics", "Mumbai",
             "₹7-12 LPA", "Analyze equity and mutual fund market data. Prepare automated executive dashboards using Power BI and Python.",
             "Python, SQL, Excel, Power BI, Tableau, Financial Modelling", "Full-time", "On-site", "1-3 years"),

            ("React Native Mobile Engineer", "PayQuick India", "Mumbai",
             "₹9-16 LPA", "Build and optimize cross-platform mobile wallets with smooth animations and biometric authentication.",
             "React Native, JavaScript, Redux, iOS, Android, REST API", "Full-time", "Hybrid", "2-4 years"),

            # Delhi / NCR (Delhi, Gurgaon, Noida)
            ("Cybersecurity & SOC Analyst", "SecureStack Defense", "Gurgaon",
             "₹8-14 LPA", "Monitor network telemetry, analyze SIEM alerts, perform vulnerability scans, and respond to security incidents.",
             "SIEM, Network Security, Python, Linux, OWASP, Wireshark", "Full-time", "Hybrid", "1-3 years"),

            ("Senior Java Spring Boot Engineer", "CodeSphere Digital", "Gurgaon",
             "₹11-19 LPA", "Develop mission-critical enterprise services with Spring Boot, Kafka streaming, and MySQL database partitioning.",
             "Java, Spring Boot, Microservices, Kafka, MySQL, Hibernate", "Full-time", "On-site", "3-5 years"),

            ("PHP / Laravel Web Developer", "WebCrate Digital", "Noida",
             "₹4-8 LPA", "Maintain and enhance high-traffic digital e-commerce storefronts and custom ERP plugins using Laravel.",
             "PHP, Laravel, MySQL, JavaScript, HTML5, CSS3", "Full-time", "On-site", "0-2 years"),

            ("Frontend React Specialist", "InnoWave Media", "Delhi",
             "₹6-12 LPA", "Create fast, accessible, SEO-optimized web portals using React 18, Next.js, and modern Tailwind CSS.",
             "React, Next.js, TypeScript, Tailwind CSS, Redux", "Full-time", "Hybrid", "1-3 years"),

            # Hyderabad Jobs
            ("Big Data Engineer", "DataBridge Global", "Hyderabad",
             "₹10-18 LPA", "Build distributed ETL pipelines using PySpark and Snowflake. Process terabytes of unstructured event logs daily.",
             "Python, PySpark, Hadoop, Snowflake, SQL, Airflow", "Full-time", "On-site", "2-4 years"),

            ("Enterprise Software Engineer (Java)", "Tata Consultancy Services", "Hyderabad",
             "₹6-11 LPA", "Implement enterprise integration middleware and REST services for multinational banking clients.",
             "Java, Spring Boot, Oracle DB, REST, JUnit, Git", "Full-time", "Hybrid", "1-3 years"),

            ("Python Data Science Intern", "InsightCore Analytics", "Hyderabad",
             "₹20k-30k/month", "Perform exploratory data analysis, clean structured datasets, and build baseline classification models.",
             "Python, Pandas, NumPy, Scikit-learn, Matplotlib", "Internship", "On-site", "Fresher"),

            # Pune Jobs
            ("C++ Systems Programmer", "LogicLabs Automotive", "Pune",
             "₹7-13 LPA", "Develop embedded software and driver safety telemetry systems with strict real-time constraints.",
             "C++, STL, Linux, RTOS, Git, Multithreading", "Full-time", "On-site", "1-3 years"),

            ("DevOps CI/CD Engineer", "DeployKit Solutions", "Pune",
             "₹8-14 LPA", "Maintain GitLab CI/CD pipelines, Docker container registries, and Prometheus/Grafana monitoring alerts.",
             "Docker, Kubernetes, Jenkins, GitLab, Prometheus, Bash", "Full-time", "Hybrid", "2-4 years"),

            ("Angular Frontend Developer", "FormStack Technologies", "Pune",
             "₹6-10 LPA", "Build responsive corporate dashboards and analytics portals with Angular 16 and RxJS state management.",
             "Angular, TypeScript, RxJS, HTML5, Bootstrap, CSS", "Full-time", "Hybrid", "1-3 years"),

            # Chennai Jobs
            ("QA Automation Test Engineer", "TestPilot Labs", "Chennai",
             "₹5-9 LPA", "Design automated regression test suites for web and mobile platforms with Selenium WebDriver and PyTest.",
             "Selenium, Python, PyTest, Jenkins, Postman, JIRA", "Full-time", "On-site", "1-3 years"),

            ("Database Administrator (PostgreSQL)", "Apex Data Systems", "Chennai",
             "₹9-15 LPA", "Manage query optimization, indexing strategies, replication failover, and disaster recovery for PostgreSQL clusters.",
             "PostgreSQL, Linux, SQL Tuning, Backup/Recovery, Shell Scripting", "Full-time", "On-site", "3-5 years"),

            # Ahmedabad & Gujarat Jobs
            ("Python & Django Developer", "Vibrant Infotech", "Ahmedabad",
             "₹4.5-8.5 LPA", "Build business portals, inventory management systems, and third-party API integrations with Django.",
             "Python, Django, PostgreSQL, HTML, CSS, JavaScript", "Full-time", "On-site", "0-2 years"),

            ("Flutter Mobile App Developer", "AppForge Solutions", "Ahmedabad",
             "₹5-9 LPA", "Develop cross-platform iOS and Android mobile apps with clean BLoC state management and Firebase backends.",
             "Flutter, Dart, Firebase, REST APIs, Git", "Full-time", "On-site", "1-3 years"),

            # Kolkata Jobs
            ("Data Engineer (SQL / BI)", "EastBridge Consulting", "Kolkata",
             "₹5-9 LPA", "Design data marts, write complex SQL stored procedures, and automate weekly sales reporting.",
             "SQL, Power BI, Excel, ETL, Python", "Full-time", "Hybrid", "1-3 years"),

            ("Web Developer (MERN)", "BengalTech Labs", "Kolkata",
             "₹4-7.5 LPA", "Design interactive customer portals with modern React components and Express.js backend services.",
             "React, Node.js, Express, MongoDB, JavaScript", "Full-time", "On-site", "0-2 years"),

            # Jaipur Jobs
            ("Junior Software Associate", "PinkCity Software", "Jaipur",
             "₹3.5-6 LPA", "Participate in SDLC, write modular code, fix QA defects, and document API contracts.",
             "Java, Python, SQL, Git, HTML/CSS", "Full-time", "On-site", "Fresher"),

            # Remote / Work-From-Home Jobs
            ("Staff Python / FastAPI Architect", "GlobalSync Software", "Remote",
             "₹18-28 LPA", "Lead architecture of async event-driven systems. Manage distributed caching, message queues, and high-load traffic.",
             "Python, FastAPI, Celery, Redis, PostgreSQL, AWS", "Full-time", "Remote", "5+ years"),

            ("Senior React & Next.js Engineer", "PixelCraft Global", "Remote",
             "₹12-22 LPA", "Lead development of customer-facing SaaS dashboards with micro-frontends and server-side rendering.",
             "React, Next.js, TypeScript, GraphQL, Tailwind CSS", "Full-time", "Remote", "3-5 years"),

            ("Golang Microservices Engineer", "StreamOps Distributed", "Remote",
             "₹14-25 LPA", "Build high-throughput gRPC services, WebSocket message dispatchers, and distributed telemetry collectors.",
             "Go, gRPC, Docker, Kafka, PostgreSQL, Redis", "Full-time", "Remote", "3-5 years"),

            ("Machine Learning Research Intern", "CortexAI Labs", "Remote",
             "₹30k-45k/month", "Conduct experiments on LLM fine-tuning, RAG evaluation frameworks, and synthetic dataset generation.",
             "Python, PyTorch, HuggingFace, RAG, Jupyter, Git", "Internship", "Remote", "Fresher")
        ]

        for job in demo_jobs:
            db.execute("""
                INSERT INTO jobs
                (recruiter_id,title,company,location,salary,description,
                 skills,job_type,work_mode,experience,status)
                VALUES (NULL,?,?,?,?,?,?,?,?,?,'approved')
            """, job)

    # Ensure unassigned jobs are linked to demo recruiter so recruiter dashboard can manage all applicant pipelines
    rec_user = db.execute("SELECT id FROM users WHERE email='recruiter@technova.com'").fetchone()
    if rec_user:
        db.execute("UPDATE jobs SET recruiter_id=? WHERE recruiter_id IS NULL", (rec_user["id"],))

    db.commit()
    db.close()


initialize_db()


# Pool of high-resolution modern tech buildings & corporate campus photography
BUILDING_PHOTOS = [
    "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1497366216548-37526070297c?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1554469384-e58fac16e23a?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1486325212027-8081e485255e?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1577495508048-b635879837f1?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1486718448742-163732cd1544?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1479839672679-a46483c0e7c8?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1444723121867-7a241cacace9?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1498084393753-b411b2d26b34?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=600&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=600&auto=format&fit=crop&q=80"
]

# Verified recruiter & company profile pictures (PFPs)
COMPANY_PFPS = {
    "technova": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=160&auto=format&fit=crop&q=80",
    "infosys": "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=160&auto=format&fit=crop&q=80",
    "neuralworks": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=160&auto=format&fit=crop&q=80",
    "cloudmatrix": "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=160&auto=format&fit=crop&q=80",
    "securestack": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=160&auto=format&fit=crop&q=80",
    "apilayer": "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=160&auto=format&fit=crop&q=80",
    "designhive": "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=160&auto=format&fit=crop&q=80",
    "codesphere": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=160&auto=format&fit=crop&q=80",
    "ironforge": "https://images.unsplash.com/photo-1522075469751-3a6694fb2f61?w=160&auto=format&fit=crop&q=80",
    "databridge": "https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?w=160&auto=format&fit=crop&q=80",
    "appforge": "https://images.unsplash.com/photo-1501196354995-cbb51c65aaea?w=160&auto=format&fit=crop&q=80",
    "logiclabs": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=160&auto=format&fit=crop&q=80",
    "pixelcraft": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=160&auto=format&fit=crop&q=80",
    "webnest": "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=160&auto=format&fit=crop&q=80",
    "cortexai": "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=160&auto=format&fit=crop&q=80",
    "tata": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=160&auto=format&fit=crop&q=80",
    "kfin": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=160&auto=format&fit=crop&q=80",
    "payquick": "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=160&auto=format&fit=crop&q=80",
    "globalsync": "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=160&auto=format&fit=crop&q=80"
}

FALLBACK_PFPS = [
    "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=160&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=160&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=160&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=160&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=160&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=160&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=160&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=160&auto=format&fit=crop&q=80"
]

# Pool of realistic publication dates matching the Bloomberg editorial layout
JOB_DATES = [
    "Feb 20, 2026", "Dec 7, 2025", "Nov 28, 2025", "Nov 25, 2025",
    "Nov 23, 2025", "Nov 20, 2025", "Nov 17, 2025", "Nov 16, 2025",
    "Nov 7, 2025", "Nov 5, 2025", "Oct 29, 2025", "Oct 22, 2025",
    "Oct 15, 2025", "Oct 08, 2025", "Sep 30, 2025", "Sep 21, 2025"
]

def get_job_function(title, skills=""):
    """Categorizes a job into standard institutional engineering & tech functions."""
    combined = (str(title) + " " + str(skills)).lower()
    if any(k in combined for k in ["cloud", "devops", "aws", "kubernetes", "infrastructure", "sre", "architect"]):
        return "Cloud & DevOps"
    elif any(k in combined for k in ["machine learning", "ai", "data analyst", "data engineer", "data science", "big data", "quantitative", "neural"]):
        return "Data & Machine Learning"
    elif any(k in combined for k in ["security", "soc", "penetration", "cyber", "network", "firewall", "defense"]):
        return "Security & Systems"
    elif any(k in combined for k in ["designer", "ui/ux", "product manager", "mobile", "ios", "android", "design"]):
        return "Product & Design"
    else:
        return "Software Development/Engineering"


def compute_skill_match(job_skills_str, candidate_skills_str):
    """
    Computes a transparent, honest skill match percentage and breakdown.
    Returns: {
        'match_pct': int (0-100),
        'matching_skills': list of str,
        'missing_skills': list of str,
        'total_skills': list of str
    }
    """
    if not job_skills_str:
        return {'match_pct': 0, 'matching_skills': [], 'missing_skills': [], 'total_skills': []}
    
    job_skills = [s.strip() for s in job_skills_str.split(",") if s.strip()]
    if not candidate_skills_str:
        return {'match_pct': 0, 'matching_skills': [], 'missing_skills': job_skills, 'total_skills': job_skills}
    
    cand_skills = [s.strip().lower() for s in candidate_skills_str.split(",") if s.strip()]
    
    matching = []
    missing = []
    for js in job_skills:
        js_lower = js.lower()
        if any(js_lower == cs or js_lower in cs or cs in js_lower for cs in cand_skills):
            matching.append(js)
        else:
            missing.append(js)
            
    pct = round((len(matching) / max(len(job_skills), 1)) * 100) if job_skills else 0
    return {
        'match_pct': pct,
        'matching_skills': matching,
        'missing_skills': missing,
        'total_skills': job_skills
    }


def calculate_profile_strength(user_dict):
    """Calculates profile completeness percentage and provides actionable improvement tips."""
    if not user_dict:
        return {"percentage": 0, "tips": ["Complete your profile to unlock personalized matching"]}
    
    score = 0
    tips = []
    
    # 1. Basic details (20%)
    if user_dict.get("name") and user_dict.get("email"):
        score += 20
        
    # 2. Headline (15%)
    if user_dict.get("headline", "").strip():
        score += 15
    else:
        tips.append("Add a professional headline (e.g. 'Senior Backend Engineer')")
        
    # 3. Bio / Summary (15%)
    if user_dict.get("bio", "").strip():
        score += 15
    else:
        tips.append("Add a career summary or bio to stand out to employers")
        
    # 4. Skills (25%)
    skills = [s.strip() for s in user_dict.get("skills", "").split(",") if s.strip()]
    if len(skills) >= 4:
        score += 25
    elif len(skills) > 0:
        score += 15
        tips.append("Add at least 4 key skills to improve your match score")
    else:
        tips.append("Add your technical skills to see instant job match percentages")
        
    # 5. Location & Phone (10%)
    if user_dict.get("location", "").strip():
        score += 5
    else:
        tips.append("Add your preferred location")
        
    if user_dict.get("phone", "").strip():
        score += 5
    else:
        tips.append("Add a contact phone number")
        
    # 6. Links (GitHub / LinkedIn / Portfolio) (15%)
    has_links = any([user_dict.get("github_url"), user_dict.get("linkedin_url"), user_dict.get("portfolio_url")])
    if has_links:
        score += 15
    else:
        tips.append("Add your GitHub or LinkedIn profile link")
        
    return {
        "percentage": min(score, 100),
        "tips": tips if tips else ["Your profile is complete and optimized for recruiters!"]
    }


def create_notification(db, user_id, title, message, link=""):
    """Inserts an in-platform notification for a user."""
    try:
        db.execute("""
            INSERT INTO notifications (user_id, title, message, link, is_read)
            VALUES (?, ?, ?, ?, 0)
        """, (user_id, title, message, link))
        db.commit()
    except Exception as e:
        print("Notification creation error:", e)


@app.context_processor
def inject_global_data():
    """Provides global counts and brand helpers to all templates."""
    unread_count = 0
    saved_count = 0
    user_skills = ""
    is_verified = False
    
    if session.get("user_id"):
        try:
            db = get_db()
            unread_row = db.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0",
                (session["user_id"],)
            ).fetchone()
            if unread_row:
                unread_count = unread_row[0]
                
            if session.get("role") == "job_seeker":
                saved_row = db.execute(
                    "SELECT COUNT(*) FROM saved_jobs WHERE user_id=?",
                    (session["user_id"],)
                ).fetchone()
                if saved_row:
                    saved_count = saved_row[0]
                    
            u_row = db.execute(
                "SELECT skills, is_verified FROM users WHERE id=?",
                (session["user_id"],)
            ).fetchone()
            if u_row:
                user_skills = u_row["skills"] or ""
                is_verified = bool(u_row["is_verified"])
            db.close()
        except Exception:
            pass
            
    return {
        "unread_notifications_count": unread_count,
        "saved_jobs_count": saved_count,
        "current_user_skills": user_skills,
        "current_user_verified": is_verified,
        "platform_name": "WorkLane"
    }


def enrich_job_data(row, user_skills=None):
    """Enriches job records with realistic dates, job functions, building photos, recruiter/company PFPs, ratings, meta details, and transparent skill match."""
    j = dict(row)
    job_id = j.get("id", 1)

    # Realistic editorial date matching WorkLane careers style
    j["formatted_date"] = JOB_DATES[job_id % len(JOB_DATES)]
    
    # Categorized job function
    j["function"] = get_job_function(j.get("title", ""), j.get("skills", ""))
    
    # Transparent skill match computation
    j["match_score"] = compute_skill_match(j.get("skills", ""), user_skills)
    
    # Deterministic building photo
    b_idx = (job_id * 5) % len(BUILDING_PHOTOS)
    j["building_img"] = BUILDING_PHOTOS[b_idx]
    
    # Deterministic PFP based on company name
    comp_lower = j.get("company", "").lower()
    pfp_found = None
    for k, v in COMPANY_PFPS.items():
        if k in comp_lower:
            pfp_found = v
            break
    if not pfp_found:
        f_idx = (job_id * 7) % len(FALLBACK_PFPS)
        pfp_found = FALLBACK_PFPS[f_idx]
    j["pfp_img"] = pfp_found
    
    # Ratings & review stats
    ratings = ["4.2", "4.3", "4.5", "4.6", "4.4", "4.7", "4.1"]
    reviews = ["1.4k", "950", "2.1k", "1.1k", "820", "1.7k", "640"]
    times = ["Just now", "Today", "1d ago", "2d ago", "3d ago"]
    
    j["rating"] = ratings[job_id % len(ratings)]
    j["reviews"] = reviews[job_id % len(reviews)]
    j["posted_time"] = times[job_id % len(times)]
    
    return j


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first")
            return redirect("/login")
        return func(*args, **kwargs)
    return wrapper


def role_required(role):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if session.get("role") != role:
                flash("Access denied")
                return redirect("/")
            return func(*args, **kwargs)
        return wrapper
    return decorator


@app.route("/")
def index():
    search = request.args.get("search", "").strip()
    city = request.args.get("city", "").strip()
    location = request.args.get("location", "").strip()
    # Prioritize city if provided, else location
    selected_location = city if city else location

    experience = request.args.get("experience", "").strip()
    job_type = request.args.get("job_type", "").strip()
    work_mode = request.args.get("work_mode", "").strip()
    job_function = request.args.get("function", "").strip()

    db = get_db()

    # Retrieve user skills & saved jobs if logged in
    user_skills = ""
    saved_job_ids = set()
    applied_job_ids = set()
    if session.get("user_id"):
        user_row = db.execute("SELECT skills FROM users WHERE id=?", (session["user_id"],)).fetchone()
        if user_row:
            user_skills = user_row["skills"] or ""
        if session.get("role") == "job_seeker":
            saved_rows = db.execute("SELECT job_id FROM saved_jobs WHERE user_id=?", (session["user_id"],)).fetchall()
            saved_job_ids = {r["job_id"] for r in saved_rows}
            user_apps = db.execute("SELECT job_id FROM applications WHERE user_id=?", (session["user_id"],)).fetchall()
            applied_job_ids = {row["job_id"] for row in user_apps}

    # Retrieve ALL approved jobs to compute accurate global category counts
    all_raw = db.execute("SELECT * FROM jobs WHERE status='approved'").fetchall()
    all_jobs_enriched = [enrich_job_data(r, user_skills) for r in all_raw]

    # 1. Experience Counts
    exp_counts = {
        "Experienced Hires": sum(1 for j in all_jobs_enriched if any(e in j.get("experience", "") for e in ["2-4", "3-5", "5+"])),
        "Fresher": sum(1 for j in all_jobs_enriched if any(e in j.get("experience", "") for e in ["Fresher", "0-2"])),
        "1-3 years": sum(1 for j in all_jobs_enriched if "1-3" in j.get("experience", "")),
        "3-5 years": sum(1 for j in all_jobs_enriched if "3-5" in j.get("experience", "")),
        "5+ years": sum(1 for j in all_jobs_enriched if "5+" in j.get("experience", ""))
    }

    # 2. Location Counts
    locations_list = ["Bangalore", "Mumbai", "Gurgaon", "Delhi", "Noida", "Hyderabad", "Pune", "Chennai", "Remote"]
    loc_counts = {}
    for loc_name in locations_list:
        loc_counts[loc_name] = sum(1 for j in all_jobs_enriched if loc_name.lower() in j.get("location", "").lower())

    # 3. Job Function Counts
    functions_list = [
        "Software Development/Engineering",
        "Cloud & DevOps",
        "Data & Machine Learning",
        "Security & Systems",
        "Product & Design"
    ]
    func_counts = {}
    for fn in functions_list:
        func_counts[fn] = sum(1 for j in all_jobs_enriched if j.get("function") == fn)

    # 4. Work Mode Counts
    modes_list = ["Hybrid", "On-site", "Remote"]
    mode_counts = {}
    for m in modes_list:
        mode_counts[m] = sum(1 for j in all_jobs_enriched if m.lower() in j.get("work_mode", "").lower())

    # Build filtered job list
    query = """
        SELECT * FROM jobs
        WHERE status='approved'
        AND (title LIKE ? OR company LIKE ? OR skills LIKE ?)
    """
    params = [f"%{search}%"] * 3

    if selected_location:
        query += " AND location LIKE ?"
        params.append(f"%{selected_location}%")

    if experience:
        if experience == "Experienced Hires":
            query += " AND (experience LIKE '%2-4%' OR experience LIKE '%3-5%' OR experience LIKE '%5+%')"
        elif experience in ["Fresher", "Entry Level"]:
            query += " AND (experience LIKE '%Fresher%' OR experience LIKE '%0-2%')"
        else:
            query += " AND experience LIKE ?"
            params.append(f"%{experience}%")

    if job_type:
        query += " AND job_type=?"
        params.append(job_type)

    if work_mode:
        query += " AND work_mode=?"
        params.append(work_mode)

    query += " ORDER BY id DESC"

    jobs_raw = db.execute(query, params).fetchall()
    jobs = [enrich_job_data(r, user_skills) for r in jobs_raw]

    # In-memory filter for job function if specified
    if job_function:
        jobs = [j for j in jobs if j.get("function") == job_function]

    # Popular cities stats for backwards compatibility
    city_stats = [
        {"name": "Bangalore", "label": "Bangalore", "icon": "bi-buildings", "count": loc_counts.get("Bangalore", 0)},
        {"name": "Mumbai", "label": "Mumbai", "icon": "bi-cash-coin", "count": loc_counts.get("Mumbai", 0)},
        {"name": "Delhi", "label": "Delhi / NCR", "icon": "bi-bank", "count": loc_counts.get("Delhi", 0)},
        {"name": "Hyderabad", "label": "Hyderabad", "icon": "bi-cpu", "count": loc_counts.get("Hyderabad", 0)},
        {"name": "Pune", "label": "Pune", "icon": "bi-code-slash", "count": loc_counts.get("Pune", 0)},
        {"name": "Remote", "label": "Work From Home", "icon": "bi-house-check", "count": loc_counts.get("Remote", 0)},
    ]

    total_jobs_count = len(all_jobs_enriched)
    total_companies_count = len({j.get("company") for j in all_jobs_enriched})

    # Build active criteria list with one-click remove URLs
    current_args = request.args.to_dict()
    active_criteria = []

    def make_remove_url(key_to_remove):
        filtered_args = {k: v for k, v in current_args.items() if k != key_to_remove and k != "city"}
        if not filtered_args:
            return "/"
        from urllib.parse import urlencode
        return "/?" + urlencode(filtered_args)

    if search:
        active_criteria.append({"name": f"Search: {search}", "param": "search", "remove_url": make_remove_url("search")})
    if selected_location:
        active_criteria.append({"name": selected_location, "param": "location", "remove_url": make_remove_url("location")})
    if experience:
        active_criteria.append({"name": experience, "param": "experience", "remove_url": make_remove_url("experience")})
    if job_function:
        active_criteria.append({"name": job_function, "param": "function", "remove_url": make_remove_url("function")})
    if work_mode:
        active_criteria.append({"name": work_mode, "param": "work_mode", "remove_url": make_remove_url("work_mode")})
    if job_type:
        active_criteria.append({"name": job_type, "param": "job_type", "remove_url": make_remove_url("job_type")})

    db.close()

    return render_template(
        "index.html",
        jobs=jobs,
        search=search,
        location=selected_location,
        selected_city=city,
        experience=experience,
        job_type=job_type,
        work_mode=work_mode,
        job_function=job_function,
        city_stats=city_stats,
        exp_counts=exp_counts,
        loc_counts=loc_counts,
        func_counts=func_counts,
        mode_counts=mode_counts,
        active_criteria=active_criteria,
        applied_job_ids=applied_job_ids,
        saved_job_ids=saved_job_ids,
        total_jobs_count=total_jobs_count,
        total_companies_count=total_companies_count
    )


@app.route("/video-tour")
def video_tour():
    """Renders the official 2-minute video presentation and platform walkthrough."""
    return render_template("video_tour.html")


@app.route("/bookmark/<int:job_id>", methods=["POST"])
@login_required
@role_required("job_seeker")
def bookmark_job(job_id):
    db = get_db()
    existing = db.execute("SELECT id FROM saved_jobs WHERE user_id=? AND job_id=?", 
                          (session["user_id"], job_id)).fetchone()
    if existing:
        db.execute("DELETE FROM saved_jobs WHERE id=?", (existing["id"],))
        db.commit()
        saved = False
        message = "Job removed from saved collection"
    else:
        db.execute("INSERT INTO saved_jobs (user_id, job_id) VALUES (?, ?)", 
                   (session["user_id"], job_id))
        db.commit()
        saved = True
        message = "Job saved to your bookmarks"
    db.close()
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return {"success": True, "saved": saved, "message": message}
    flash(message)
    return redirect(request.referrer or "/")


@app.route("/get-alert", methods=["POST"])
def get_alert():
    email = request.form.get("email", "").strip().lower()
    criteria = request.form.get("criteria", "Current Search Criteria").strip()
    if email and "@" in email:
        db = get_db()
        db.execute("INSERT INTO job_alerts (email, criteria) VALUES (?, ?)", (email, criteria))
        db.commit()
        db.close()
        flash(f"Job alert configured for {email}. You will receive immediate notifications when matching roles open on WorkLane.")
    else:
        flash("Please provide a valid email address to configure job alerts.")
    return redirect(request.referrer or "/")


@app.route("/connect", methods=["POST"])
def connect_talent():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    skills = request.form.get("skills", "").strip()
    if email and "@" in email:
        db = get_db()
        db.execute("INSERT INTO talent_network (name, email, skills) VALUES (?, ?, ?)", (name, email, skills))
        db.commit()
        db.close()
        flash(f"Welcome to the WorkLane Talent Network{', ' + name if name else ''}! Our recruiting team will keep you connected with new opportunities.")
    else:
        flash("Please provide a valid email address to join our talent network.")
    return redirect(request.referrer or "/")


@app.route("/api/job/<int:job_id>")
def get_job_api(job_id):
    db = get_db()
    # Increment views count for job analytics
    db.execute("UPDATE jobs SET views_count = COALESCE(views_count, 0) + 1 WHERE id=?", (job_id,))
    db.commit()

    row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        db.close()
        return {"error": "Job not found"}, 404

    # Fetch user skills if logged in
    user_skills = ""
    if session.get("user_id"):
        u_row = db.execute("SELECT skills FROM users WHERE id=?", (session["user_id"],)).fetchone()
        if u_row:
            user_skills = u_row["skills"] or ""

    job = enrich_job_data(row, user_skills)

    # Similar jobs recommendation
    similar_rows = db.execute("""
        SELECT id, title, company, location, salary, job_type, experience
        FROM jobs
        WHERE status='approved' AND id != ?
        AND (location = ? OR title LIKE ? OR skills LIKE ?)
        LIMIT 3
    """, (job_id, job.get("location", ""), f"%{job['title'].split()[0]}%", f"%{job.get('skills', '').split(',')[0]}%")).fetchall()
    
    similar_jobs = [dict(sr) for sr in similar_rows]
    db.close()

    return {
        "id": job["id"],
        "title": job["title"],
        "company": job["company"],
        "location": job["location"],
        "salary": job["salary"],
        "description": job["description"],
        "skills": job["skills"],
        "job_type": job["job_type"],
        "work_mode": job["work_mode"],
        "experience": job["experience"],
        "formatted_date": job["formatted_date"],
        "function": job["function"],
        "views_count": job.get("views_count", 0),
        "match_score": job.get("match_score"),
        "similar_jobs": similar_jobs
    }


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip()

        if not name:
            flash("Name is required")
            return redirect("/register")

        if not email or "@" not in email:
            flash("A valid email address is required")
            return redirect("/register")

        if role not in ["job_seeker", "recruiter"]:
            flash("Invalid role")
            return redirect("/register")

        if len(password) < 8:
            flash("Password must contain at least 8 characters")
            return redirect("/register")

        db = get_db()

        try:
            db.execute("""
                INSERT INTO users (name,email,password,role)
                VALUES (?,?,?,?)
            """, (name, email, generate_password_hash(password), role))

            db.commit()
            
            # Send welcome notification
            new_user = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if new_user:
                create_notification(
                    db,
                    new_user["id"],
                    "Welcome to WorkLane!",
                    "Complete your profile and skills to start receiving matched job recommendations.",
                    "/profile"
                )

            flash("Account created successfully. Please sign in.")
            return redirect("/login")

        except sqlite3.IntegrityError:
            flash("Email already exists")

        finally:
            db.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required")
            return redirect("/login")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()
        db.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            return redirect("/dashboard")

        flash("Invalid email or password")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()
    user_id = session["user_id"]

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        headline = request.form.get("headline", "").strip()
        bio = request.form.get("bio", "").strip()
        phone = request.form.get("phone", "").strip()
        location = request.form.get("location", "").strip()
        skills = request.form.get("skills", "").strip()
        experience_years = int(request.form.get("experience_years", 0) or 0)
        github_url = request.form.get("github_url", "").strip()
        linkedin_url = request.form.get("linkedin_url", "").strip()
        portfolio_url = request.form.get("portfolio_url", "").strip()

        # Recruiter specific fields
        company_name = request.form.get("company_name", "").strip()
        company_website = request.form.get("company_website", "").strip()
        company_description = request.form.get("company_description", "").strip()

        db.execute("""
            UPDATE users SET
                name=?, headline=?, bio=?, phone=?, location=?, skills=?,
                experience_years=?, github_url=?, linkedin_url=?, portfolio_url=?,
                company_name=?, company_website=?, company_description=?
            WHERE id=?
        """, (
            name, headline, bio, phone, location, skills,
            experience_years, github_url, linkedin_url, portfolio_url,
            company_name, company_website, company_description,
            user_id
        ))
        db.commit()
        session["name"] = name
        flash("Your profile has been updated successfully!")
        db.close()
        return redirect("/profile")

    user_row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    db.close()

    user_dict = dict(user_row) if user_row else {}
    profile_strength = calculate_profile_strength(user_dict)

    return render_template("profile.html", user=user_dict, profile_strength=profile_strength)


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user_id = session["user_id"]
    role = session["role"]

    user_row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    user_dict = dict(user_row) if user_row else {}
    profile_strength = calculate_profile_strength(user_dict)

    if role == "recruiter":
        # When recruiter views their dashboard, unreviewed applications for their jobs transition to 'Under Review'
        unreviewed = db.execute("""
            SELECT applications.id, applications.user_id, applications.interview_date, jobs.title, jobs.company 
            FROM applications
            JOIN jobs ON applications.job_id=jobs.id
            WHERE jobs.recruiter_id=? AND applications.status='Applied'
        """, (user_id,)).fetchall()

        for u in unreviewed:
            target_status = "Interview" if u["interview_date"] else "Under Review"
            db.execute("UPDATE applications SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (target_status, u["id"]))
            create_notification(
                db,
                u["user_id"],
                f"Application {target_status}: {u['title']}",
                f"Your application for {u['title']} at {u['company']} is now {target_status} by the recruiting team.",
                "/dashboard"
            )
        if unreviewed:
            db.commit()

        # Recruiter jobs with applicant count
        jobs_raw = db.execute("""
            SELECT jobs.*, COUNT(applications.id) AS applicants_count
            FROM jobs
            LEFT JOIN applications ON jobs.id=applications.job_id
            WHERE jobs.recruiter_id=?
            GROUP BY jobs.id
            ORDER BY jobs.id DESC
        """, (user_id,)).fetchall()
        jobs = [dict(r) for r in jobs_raw]

        # Applications for this recruiter's jobs with applicant details
        apps_raw = db.execute("""
            SELECT applications.*, 
                   jobs.title, jobs.skills AS job_skills,
                   users.name AS applicant, users.email AS applicant_email,
                   users.headline AS applicant_headline, users.skills AS applicant_skills,
                   users.location AS applicant_location, users.experience_years AS applicant_exp,
                   users.github_url AS applicant_github, users.linkedin_url AS applicant_linkedin,
                   users.resume_filename AS applicant_resume
            FROM applications
            JOIN jobs ON applications.job_id=jobs.id
            JOIN users ON applications.user_id=users.id
            WHERE jobs.recruiter_id=?
            ORDER BY applications.id DESC
        """, (user_id,)).fetchall()

        applications = []
        for a in apps_raw:
            ad = dict(a)
            ad["match_score"] = compute_skill_match(ad.get("job_skills", ""), ad.get("applicant_skills", ""))
            applications.append(ad)

        pipeline = {
            "total": len(applications),
            "applied": sum(1 for a in applications if a["status"] == "Applied"),
            "under_review": sum(1 for a in applications if a["status"] == "Under Review"),
            "shortlisted": sum(1 for a in applications if a["status"] == "Shortlisted"),
            "interview": sum(1 for a in applications if a["status"] == "Interview"),
            "offered": sum(1 for a in applications if a["status"] == "Offered"),
            "hired": sum(1 for a in applications if a["status"] == "Offer Accepted"),
            "rejected": sum(1 for a in applications if a["status"] in ["Rejected", "Offer Declined"])
        }

        db.close()
        return render_template(
            "dashboard.html",
            jobs=jobs,
            applications=applications,
            pipeline=pipeline,
            user=user_dict,
            profile_strength=profile_strength
        )

    elif role == "job_seeker":
        # Seeker applications with full job metadata
        apps_raw = db.execute("""
            SELECT applications.*, jobs.title, jobs.company, jobs.location, jobs.salary, jobs.skills, jobs.status AS job_status
            FROM applications
            JOIN jobs ON applications.job_id=jobs.id
            WHERE applications.user_id=?
            ORDER BY applications.id DESC
        """, (user_id,)).fetchall()

        applications = []
        for a in apps_raw:
            ad = dict(a)
            ad["match_score"] = compute_skill_match(ad.get("skills", ""), user_dict.get("skills", ""))
            applications.append(ad)

        # Seeker saved jobs
        saved_raw = db.execute("""
            SELECT saved_jobs.id AS bookmark_id, saved_jobs.created_at AS saved_at, jobs.*
            FROM saved_jobs
            JOIN jobs ON saved_jobs.job_id=jobs.id
            WHERE saved_jobs.user_id=?
            ORDER BY saved_jobs.id DESC
        """, (user_id,)).fetchall()
        saved_jobs = [enrich_job_data(r, user_dict.get("skills", "")) for r in saved_raw]

        app_stats = {
            "total": len(applications),
            "active": sum(1 for a in applications if a["status"] in ["Applied", "Under Review", "Shortlisted", "Interview"]),
            "interviews": sum(1 for a in applications if a["status"] == "Interview"),
            "offers": sum(1 for a in applications if a["status"] == "Offered"),
            "saved": len(saved_jobs)
        }

        db.close()
        return render_template(
            "dashboard.html",
            applications=applications,
            saved_jobs=saved_jobs,
            app_stats=app_stats,
            user=user_dict,
            profile_strength=profile_strength
        )

    else:
        # Admin
        jobs = [dict(r) for r in db.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall()]
        users_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        jobs_count = len(jobs)
        reports_count = db.execute("SELECT COUNT(*) FROM job_reports WHERE status='pending'").fetchone()[0]
        db.close()
        return render_template(
            "dashboard.html",
            jobs=jobs,
            users_count=users_count,
            jobs_count=jobs_count,
            reports_count=reports_count,
            user=user_dict
        )


@app.route("/post-job", methods=["GET", "POST"])
@login_required
@role_required("recruiter")
def post_job():
    if request.method == "POST":
        db = get_db()

        title = request.form.get("title", "").strip()
        company = request.form.get("company", "").strip()
        location = request.form.get("location", "Remote").strip()
        salary = request.form.get("salary", "Competitive").strip()
        description = request.form.get("description", "").strip()
        skills = request.form.get("skills", "").strip()
        job_type = request.form.get("job_type", "Full-time").strip()
        work_mode = request.form.get("work_mode", "On-site").strip()
        experience = request.form.get("experience", "Fresher").strip()
        department = request.form.get("department", "Engineering").strip()

        if not title or not company:
            flash("Job title and company name are required.")
            db.close()
            return redirect("/post-job")

        # If recruiter is verified, automatically approve job
        u = db.execute("SELECT is_verified FROM users WHERE id=?", (session["user_id"],)).fetchone()
        initial_status = "approved" if (u and u["is_verified"]) else "pending"

        db.execute("""
            INSERT INTO jobs
            (recruiter_id,title,company,location,salary,description,
             skills,job_type,work_mode,experience,department,status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            session["user_id"],
            title,
            company,
            location,
            salary,
            description,
            skills,
            job_type,
            work_mode,
            experience,
            department,
            initial_status
        ))

        db.commit()
        db.close()

        if initial_status == "approved":
            flash("Job listing published immediately (Verified Recruiter)!")
        else:
            flash("Job submitted successfully! Awaiting Trust & Safety approval.")
        return redirect("/dashboard")

    return render_template("post_job.html")


@app.route("/edit-job/<int:job_id>", methods=["GET", "POST"])
@login_required
@role_required("recruiter")
def edit_job(job_id):
    db = get_db()
    job = db.execute("SELECT * FROM jobs WHERE id=? AND recruiter_id=?", 
                     (job_id, session["user_id"])).fetchone()
    if not job:
        flash("Job not found or access denied.")
        db.close()
        return redirect("/dashboard")

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        company = request.form.get("company", "").strip()
        location = request.form.get("location", "Remote").strip()
        salary = request.form.get("salary", "Competitive").strip()
        description = request.form.get("description", "").strip()
        skills = request.form.get("skills", "").strip()
        job_type = request.form.get("job_type", "Full-time").strip()
        work_mode = request.form.get("work_mode", "On-site").strip()
        experience = request.form.get("experience", "Fresher").strip()
        department = request.form.get("department", "Engineering").strip()

        if not title or not company:
            flash("Job title and company name are required.")
            db.close()
            return redirect(f"/edit-job/{job_id}")

        db.execute("""
            UPDATE jobs SET
                title=?, company=?, location=?, salary=?, description=?,
                skills=?, job_type=?, work_mode=?, experience=?, department=?
            WHERE id=? AND recruiter_id=?
        """, (title, company, location, salary, description,
              skills, job_type, work_mode, experience, department, job_id, session["user_id"]))
        db.commit()
        db.close()
        flash("Job listing updated successfully.")
        return redirect("/dashboard")

    db.close()
    return render_template("edit_job.html", job=dict(job))


@app.route("/job/status/<int:job_id>/<new_status>", methods=["POST"])
@login_required
@role_required("recruiter")
def change_job_status(job_id, new_status):
    if new_status not in ["approved", "paused", "closed"]:
        flash("Invalid job status.")
        return redirect("/dashboard")
    db = get_db()
    db.execute("""
        UPDATE jobs SET status=? WHERE id=? AND recruiter_id=?
    """, (new_status, job_id, session["user_id"]))
    db.commit()
    db.close()
    flash(f"Job status updated to {new_status.title()}.")
    return redirect("/dashboard")


@app.route("/delete-job/<int:job_id>", methods=["POST"])
@login_required
@role_required("recruiter")
def delete_job(job_id):
    db = get_db()

    db.execute("""
        DELETE FROM jobs
        WHERE id=? AND recruiter_id=?
    """, (job_id, session["user_id"]))

    db.commit()
    db.close()

    flash("Job listing deleted")
    return redirect("/dashboard")


@app.route("/apply/<int:job_id>", methods=["POST", "GET"])
@login_required
@role_required("job_seeker")
def apply(job_id):
    db = get_db()

    job = db.execute("""
        SELECT * FROM jobs
        WHERE id=? AND status='approved'
    """, (job_id,)).fetchone()

    if not job:
        flash("Job not available or no longer accepting applications.")
        db.close()
        return redirect(request.referrer or "/")

    cover_note = request.form.get("cover_note", "").strip() if request.method == "POST" else ""
    resume_link = request.form.get("resume_link", "").strip() if request.method == "POST" else ""

    # Check if user already applied
    existing = db.execute("SELECT id FROM applications WHERE job_id=? AND user_id=?", 
                          (job_id, session["user_id"])).fetchone()
    if existing:
        flash("You have already applied for this role.")
        db.close()
        return redirect(request.referrer or "/dashboard")

    # If no resume link provided, check user's github or portfolio
    user = db.execute("SELECT name, skills, github_url, linkedin_url FROM users WHERE id=?", 
                      (session["user_id"],)).fetchone()
    if not resume_link and user:
        resume_link = user["github_url"] or user["linkedin_url"] or ""

    try:
        db.execute("""
            INSERT INTO applications (job_id, user_id, status, cover_note, resume_link)
            VALUES (?, ?, 'Applied', ?, ?)
        """, (job_id, session["user_id"], cover_note, resume_link))
        db.commit()

        # Notify recruiter
        if job["recruiter_id"]:
            create_notification(
                db,
                job["recruiter_id"],
                f"New Application for {job['title']}",
                f"{session.get('name', 'A candidate')} has applied for {job['title']}.",
                "/dashboard"
            )

        # Notify candidate
        create_notification(
            db,
            session["user_id"],
            f"Application Submitted: {job['title']}",
            f"Your application for {job['title']} at {job['company']} was successfully received.",
            "/dashboard"
        )

        flash(f"Application for '{job['title']}' submitted successfully!")
    except Exception as e:
        flash(f"Error submitting application: {str(e)}")

    db.close()
    return redirect(request.referrer or "/dashboard")


@app.route("/application/withdraw/<int:app_id>", methods=["POST"])
@login_required
@role_required("job_seeker")
def withdraw_application(app_id):
    db = get_db()
    app_record = db.execute("SELECT * FROM applications WHERE id=? AND user_id=?", 
                            (app_id, session["user_id"])).fetchone()
    if not app_record:
        flash("Application not found or unauthorized.")
        db.close()
        return redirect("/dashboard")

    db.execute("DELETE FROM applications WHERE id=?", (app_id,))
    db.commit()
    db.close()
    flash("Application withdrawn successfully.")
    return redirect("/dashboard")


@app.route("/recruiter/application/update/<int:app_id>", methods=["POST"])
@login_required
@role_required("recruiter")
def update_application_status(app_id):
    db = get_db()
    app_record = db.execute("""
        SELECT applications.*, jobs.title, jobs.recruiter_id, jobs.company
        FROM applications
        JOIN jobs ON applications.job_id=jobs.id
        WHERE applications.id=? AND jobs.recruiter_id=?
    """, (app_id, session["user_id"])).fetchone()

    if not app_record:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            db.close()
            return jsonify({"success": False, "error": "Unauthorized or not found"}), 404
        flash("Unauthorized or application not found.")
        db.close()
        return redirect("/dashboard")

    data = request.get_json(silent=True) or request.form
    new_status = data.get("status", "").strip()
    recruiter_notes = data.get("recruiter_notes", app_record["recruiter_notes"] or "").strip()
    interview_date = data.get("interview_date", app_record["interview_date"] or "").strip()

    # Smart auto-advancement: if interview_date is provided and status is still Applied or Under Review, set to Interview
    if interview_date and (not new_status or new_status in ["Applied", "Under Review"]):
        new_status = "Interview"
    elif not new_status:
        new_status = app_record["status"]

    valid_statuses = ["Applied", "Under Review", "Shortlisted", "Interview", "Offered", "Offer Accepted", "Offer Declined", "Rejected"]
    if new_status not in valid_statuses:
        new_status = "Under Review"

    db.execute("""
        UPDATE applications SET
            status=?, recruiter_notes=?, interview_date=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (new_status, recruiter_notes, interview_date, app_id))
    db.commit()

    # Notify candidate of real status update
    create_notification(
        db,
        app_record["user_id"],
        f"Application Update: {app_record['title']}",
        f"Your application status for {app_record['title']} at {app_record['company']} has been updated to '{new_status}'.",
        "/dashboard"
    )

    db.close()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({"success": True, "status": new_status, "message": f"Candidate application updated to '{new_status}'."})

    flash(f"Candidate application updated to '{new_status}'.")
    return redirect("/dashboard")


@app.route("/application/respond-offer/<int:app_id>/<action>", methods=["POST"])
@login_required
@role_required("job_seeker")
def respond_offer(app_id, action):
    db = get_db()
    app_record = db.execute("""
        SELECT applications.*, jobs.title, jobs.company, jobs.recruiter_id
        FROM applications
        JOIN jobs ON applications.job_id=jobs.id
        WHERE applications.id=? AND applications.user_id=?
    """, (app_id, session["user_id"])).fetchone()

    if not app_record:
        flash("Application record not found.")
        db.close()
        return redirect("/dashboard")

    if action == "accept":
        new_status = "Offer Accepted"
        flash(f"🎉 Congratulations! You have accepted the formal offer for '{app_record['title']}' at {app_record['company']}!")
        
        # Notify recruiter
        if app_record["recruiter_id"]:
            create_notification(
                db,
                app_record["recruiter_id"],
                f"🎉 Offer Accepted: {app_record['title']}",
                f"{session.get('name', 'The candidate')} has officially accepted your offer for {app_record['title']}! Welcome your new hire.",
                "/dashboard"
            )
        # Notify candidate
        create_notification(
            db,
            session["user_id"],
            f"🎉 Offer Confirmed: {app_record['title']}",
            f"You have officially accepted the offer at {app_record['company']}. Onboarding details will be communicated soon.",
            "/dashboard"
        )
    elif action == "decline":
        new_status = "Offer Declined"
        flash(f"You have declined the offer for '{app_record['title']}'.")
        if app_record["recruiter_id"]:
            create_notification(
                db,
                app_record["recruiter_id"],
                f"Offer Declined: {app_record['title']}",
                f"{session.get('name', 'The candidate')} has declined the offer for {app_record['title']}.",
                "/dashboard"
            )
    else:
        new_status = app_record["status"]

    db.execute("UPDATE applications SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_status, app_id))
    db.commit()
    db.close()
    return redirect("/dashboard")


@app.route("/notifications")
@login_required
def notifications():
    db = get_db()
    items = db.execute("""
        SELECT * FROM notifications
        WHERE user_id=?
        ORDER BY id DESC
    """, (session["user_id"],)).fetchall()
    notifications_list = [dict(r) for r in items]
    db.close()
    return render_template("notifications.html", notifications=notifications_list)


@app.route("/notifications/read/<int:notif_id>", methods=["POST"])
@login_required
def read_notification(notif_id):
    db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", 
               (notif_id, session["user_id"]))
    db.commit()
    db.close()
    return redirect("/notifications")


@app.route("/notifications/read-all", methods=["POST"])
@login_required
def read_all_notifications():
    db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", 
               (session["user_id"],))
    db.commit()
    db.close()
    flash("All notifications marked as read.")
    return redirect("/notifications")


@app.route("/report-job/<int:job_id>", methods=["POST"])
@login_required
def report_job(job_id):
    reason = request.form.get("reason", "").strip()
    if not reason:
        reason = "Potential misleading information or policy violation"
    db = get_db()
    db.execute("""
        INSERT INTO job_reports (job_id, user_id, reason)
        VALUES (?, ?, ?)
    """, (job_id, session["user_id"], reason))
    db.commit()
    db.close()
    flash("Thank you for your report. WorkLane Trust & Safety will inspect this listing.")
    return redirect(request.referrer or "/")


@app.route("/admin")
@login_required
@role_required("admin")
def admin():
    db = get_db()

    jobs = db.execute("""
        SELECT jobs.*, users.name AS recruiter
        FROM jobs
        LEFT JOIN users ON jobs.recruiter_id=users.id
        ORDER BY jobs.id DESC
    """).fetchall()

    users = db.execute(
        "SELECT id, name, email, role, is_verified FROM users ORDER BY id DESC"
    ).fetchall()

    reports = db.execute("""
        SELECT job_reports.*, jobs.title AS job_title, jobs.company AS job_company, users.name AS reporter_name
        FROM job_reports
        JOIN jobs ON job_reports.job_id=jobs.id
        LEFT JOIN users ON job_reports.user_id=users.id
        WHERE job_reports.status='pending'
        ORDER BY job_reports.id DESC
    """).fetchall()

    db.close()
    return render_template("admin.html", jobs=jobs, users=users, reports=reports)


@app.route("/admin/verify-recruiter/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def toggle_verify_recruiter(user_id):
    db = get_db()
    user = db.execute("SELECT is_verified FROM users WHERE id=?", (user_id,)).fetchone()
    if user:
        new_val = 0 if user["is_verified"] else 1
        db.execute("UPDATE users SET is_verified=? WHERE id=?", (new_val, user_id))
        db.commit()
        status_text = "verified" if new_val else "unverified"
        flash(f"Recruiter verification badge updated to {status_text}.")
    db.close()
    return redirect("/admin")


@app.route("/admin/dismiss-report/<int:report_id>", methods=["POST"])
@login_required
@role_required("admin")
def dismiss_job_report(report_id):
    db = get_db()
    db.execute("UPDATE job_reports SET status='dismissed' WHERE id=?", (report_id,))
    db.commit()
    db.close()
    flash("Report dismissed.")
    return redirect("/admin")


@app.route("/approve/<int:job_id>/<action>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def approve(job_id, action):
    if action not in ["approved", "rejected"]:
        return redirect("/admin")

    db = get_db()
    db.execute(
        "UPDATE jobs SET status=? WHERE id=?",
        (action, job_id)
    )
    db.commit()
    db.close()

    flash(f"Job has been marked as {action}.")
    return redirect("/admin")


if __name__ == "__main__":
    app.run(debug=True, port=5001)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
