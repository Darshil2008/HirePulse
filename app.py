
from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "database.db")


def get_db():
    db_path = app.config.get("DATABASE", DB)
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db


def initialize_db():
    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)

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

    db.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            user_id INTEGER,
            status TEXT DEFAULT 'Applied',
            UNIQUE(job_id, user_id)
        )
    """)

    # Add new columns safely to an existing database
    existing_columns = [
        row["name"] for row in db.execute("PRAGMA table_info(jobs)").fetchall()
    ]

    new_columns = {
        "skills": "TEXT DEFAULT ''",
        "job_type": "TEXT DEFAULT 'Full-time'",
        "work_mode": "TEXT DEFAULT 'On-site'",
        "experience": "TEXT DEFAULT 'Fresher'"
    }

    for column, definition in new_columns.items():
        if column not in existing_columns:
            db.execute(f"ALTER TABLE jobs ADD COLUMN {column} {definition}")

    # Check for admin user (migrate legacy jobportal email to hirepulse if present)
    db.execute("UPDATE users SET email='admin@hirepulse.com' WHERE email='admin@jobportal.com'")

    admin = db.execute(
        "SELECT id FROM users WHERE email=?",
        ("admin@hirepulse.com",)
    ).fetchone()

    if not admin:
        db.execute("""
            INSERT INTO users (name,email,password,role)
            VALUES (?,?,?,?)
        """, (
            "Admin User",
            "admin@hirepulse.com",
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
            INSERT INTO users (name,email,password,role)
            VALUES (?,?,?,?)
        """, (
            "Priya Sharma (TechNova HR)",
            "recruiter@technova.com",
            generate_password_hash("recruiter123"),
            "recruiter"
        ))

    seeker = db.execute(
        "SELECT id FROM users WHERE email=?",
        ("seeker@example.com",)
    ).fetchone()

    if not seeker:
        db.execute("""
            INSERT INTO users (name,email,password,role)
            VALUES (?,?,?,?)
        """, (
            "Darshil Gehlot",
            "seeker@example.com",
            generate_password_hash("seeker123"),
            "job_seeker"
        ))

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


def enrich_job_data(row):
    """Enriches job records with realistic dates, job functions, building photos, recruiter/company PFPs, ratings, and meta details."""
    j = dict(row)
    job_id = j.get("id", 1)

    # Realistic editorial date matching Bloomberg careers style
    j["formatted_date"] = JOB_DATES[job_id % len(JOB_DATES)]
    
    # Categorized job function
    j["function"] = get_job_function(j.get("title", ""), j.get("skills", ""))
    
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

    # Retrieve ALL approved jobs to compute accurate global category counts
    all_raw = db.execute("SELECT * FROM jobs WHERE status='approved'").fetchall()
    all_jobs_enriched = [enrich_job_data(r) for r in all_raw]

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
    jobs = [enrich_job_data(r) for r in jobs_raw]

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

    # Track applied jobs for logged in job seeker
    applied_job_ids = set()
    if session.get("user_id") and session.get("role") == "job_seeker":
        user_apps = db.execute(
            "SELECT job_id FROM applications WHERE user_id=?",
            (session["user_id"],)
        ).fetchall()
        applied_job_ids = {row["job_id"] for row in user_apps}

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
        total_jobs_count=total_jobs_count,
        total_companies_count=total_companies_count
    )


@app.route("/get-alert", methods=["POST"])
def get_alert():
    email = request.form.get("email", "").strip().lower()
    criteria = request.form.get("criteria", "Current Search Criteria").strip()
    if email and "@" in email:
        flash(f"Job alert configured for {email}. You will receive immediate notifications when matching roles open.")
    else:
        flash("Please provide a valid email address to configure job alerts.")
    return redirect(request.referrer or "/")


@app.route("/connect", methods=["POST"])
def connect_talent():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    if email and "@" in email:
        flash(f"Welcome to the HirePulse Talent Network{', ' + name if name else ''}! Our recruiting team will keep you connected with new opportunities.")
    else:
        flash("Please provide a valid email address to join our talent network.")
    return redirect(request.referrer or "/")


@app.route("/api/job/<int:job_id>")
def get_job_api(job_id):
    db = get_db()
    row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    db.close()
    if not row:
        return {"error": "Job not found"}, 404
    job = enrich_job_data(row)
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
        "function": job["function"]
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
            flash("Account created successfully")
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


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()

    if session["role"] == "recruiter":
        jobs = db.execute(
            "SELECT * FROM jobs WHERE recruiter_id=?",
            (session["user_id"],)
        ).fetchall()

        applications = db.execute("""
            SELECT applications.*, jobs.title, users.name AS applicant
            FROM applications
            JOIN jobs ON applications.job_id=jobs.id
            JOIN users ON applications.user_id=users.id
            WHERE jobs.recruiter_id=?
        """, (session["user_id"],)).fetchall()

    elif session["role"] == "job_seeker":
        jobs = []
        applications = db.execute("""
            SELECT applications.*, jobs.title, jobs.company
            FROM applications
            JOIN jobs ON applications.job_id=jobs.id
            WHERE applications.user_id=?
        """, (session["user_id"],)).fetchall()

    else:
        jobs = db.execute(
            "SELECT * FROM jobs ORDER BY id DESC"
        ).fetchall()
        applications = []

    db.close()

    return render_template(
        "dashboard.html",
        jobs=jobs,
        applications=applications
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

        if not title or not company:
            flash("Job title and company name are required.")
            return redirect("/post-job")

        db.execute("""
            INSERT INTO jobs
            (recruiter_id,title,company,location,salary,description,
             skills,job_type,work_mode,experience)
            VALUES (?,?,?,?,?,?,?,?,?,?)
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
            experience
        ))

        db.commit()
        db.close()

        flash("Job submitted successfully! Awaiting admin approval.")
        return redirect("/dashboard")

    return render_template("post_job.html")


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

    flash("Job deleted")
    return redirect("/dashboard")


@app.route("/apply/<int:job_id>", methods=["POST", "GET"])
@login_required
@role_required("job_seeker")
def apply(job_id):
    db = get_db()

    job = db.execute("""
        SELECT id FROM jobs
        WHERE id=? AND status='approved'
    """, (job_id,)).fetchone()

    if not job:
        flash("Job not available")
    else:
        try:
            db.execute("""
                INSERT INTO applications (job_id,user_id)
                VALUES (?,?)
            """, (job_id, session["user_id"]))

            db.commit()
            flash("Application submitted successfully")

        except sqlite3.IntegrityError:
            flash("You have already applied")

    db.close()
    return redirect("/")


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
        "SELECT id,name,email,role FROM users"
    ).fetchall()

    db.close()

    return render_template("admin.html", jobs=jobs, users=users)


@app.route("/approve/<int:job_id>/<action>")
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

    return redirect("/admin")


if __name__ == "__main__":
    app.run(debug=True, port=5001)
