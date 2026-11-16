# HirePulse — Tech Career Discovery Platform

**HirePulse** is a modern full-stack career discovery and recruitment platform built with **Python (Flask)**, **SQLite**, and modern frontend technologies. Designed as part of the **ALTA Builder 30** challenge (Track A).

---

## ⚡ Key Features

- **Dynamic Discovery Feed**: 31+ enriched job listings across major tech hubs (Bangalore, Mumbai, Delhi NCR, Pune, Hyderabad, Remote).
- **Modern Job Cards**: Real corporate architecture cover photos, verified recruiter PFPs, and salary highlight badges.
- **Floating Scroll Dock**: Sticky top filter dock that slides in smoothly on scroll with quick city chips and search inputs.
- **Multi-City & Parameter Filtering**: Instant filtering by city, experience level, employment type, and work mode (*Remote, Hybrid, On-site*).
- **1-Click Quick Apply**: Immediate application submission with live UI state updates (*Applied* toggle).
- **Role-Based Authentication**:
  - **Job Seeker**: Search, filter, apply, and track submitted applications.
  - **Recruiter**: Post opportunities with validation and manage applicant pipelines.
  - **Admin**: Review, approve, or reject job submissions and monitor platform users.
- **Secure Password Hashing**: PBKDF2/SHA-256 via Werkzeug Security.
- **1-Click Demo Logins**: Instant credential autofill for fast testing and grading.

---

## 🛠️ Technology Stack

- **Backend**: Python 3, Flask, Werkzeug Security
- **Database**: SQLite3 (Relational with foreign keys and unique constraints)
- **Frontend**: HTML5, CSS3, Bootstrap 5, Bootstrap Icons
- **Design System**: Royal Blue (`#2457bd`) & Deep Navy (`#14243c`) with corporate photography

---

## 🚀 Getting Started

### 1. Clone & Navigate
```bash
git clone https://github.com/darshil2008/HirePulse.git
cd "Job-Portal"
```

### 2. Set Up Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
python3 app.py
```

### 5. Access the Platform
Open your browser and navigate to:
👉 **[http://127.0.0.1:5001](http://127.0.0.1:5001)**

---

## 🔑 Demo Accounts (1-Click Fill on `/login`)

| Role | Email | Password |
|---|---|---|
| **Admin** | `admin@hirepulse.com` | `admin123` |
| **Recruiter** | `recruiter@technova.com` | `recruiter123` |
| **Job Seeker** | `seeker@example.com` | `seeker123` |

---

## 📄 License
Open source under the [MIT License](LICENSE). Built for the ALTA Builder 30 Challenge.
