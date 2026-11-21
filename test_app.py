import unittest
import os
import tempfile
import sqlite3
from werkzeug.security import generate_password_hash

# Set testing environment before importing app
os.environ["FLASK_ENV"] = "testing"
from app import app, initialize_db


class HirePulseTestCase(unittest.TestCase):
    def setUp(self):
        # Create a temporary database for each test to isolate data
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        app.config["TESTING"] = True
        app.config["DATABASE"] = self.db_path
        app.config["WTF_CSRF_ENABLED"] = False

        self.client = app.test_client()

        with app.app_context():
            initialize_db()

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    # 1. Main Flow: Home page renders correctly
    def test_01_home_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"WorkLane" in response.data or b"HirePulse" in response.data)

    # 2. Input Validation: Short password (< 8 chars) rejected
    def test_02_register_validation_short_password(self):
        response = self.client.post("/register", data={
            "name": "Test Seeker",
            "email": "seeker@example.com",
            "password": "short",
            "role": "job_seeker"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Password must contain at least 8 characters", response.data)

    # 3. Input Validation: Invalid/empty email rejected
    def test_03_register_validation_invalid_email(self):
        response = self.client.post("/register", data={
            "name": "Test Seeker",
            "email": "not-an-email",
            "password": "securepassword123",
            "role": "job_seeker"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"A valid email address is required", response.data)

    # 4. Main Flow: Successful registration & login flow
    def test_04_register_and_login_success(self):
        # Register
        reg_resp = self.client.post("/register", data={
            "name": "Darshil Gehlot",
            "email": "darshil@test.com",
            "password": "mypassword123",
            "role": "job_seeker"
        }, follow_redirects=True)
        self.assertEqual(reg_resp.status_code, 200)
        self.assertIn(b"Account created successfully", reg_resp.data)

        # Login
        login_resp = self.client.post("/login", data={
            "email": "darshil@test.com",
            "password": "mypassword123"
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)
        self.assertIn(b"Dashboard", login_resp.data)

    # 5. Auth Security: Incorrect password fails
    def test_05_login_invalid_password(self):
        # Create user
        self.client.post("/register", data={
            "name": "User One",
            "email": "user1@test.com",
            "password": "correctpassword",
            "role": "job_seeker"
        })

        # Try wrong password
        response = self.client.post("/login", data={
            "email": "user1@test.com",
            "password": "wrongpassword"
        }, follow_redirects=True)
        self.assertIn(b"Invalid email or password", response.data)

    # 6. Protected Route: Unauthenticated access blocked
    def test_06_dashboard_requires_login(self):
        response = self.client.get("/dashboard")
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    # 7. Role-Based Access: Recruiter can post job, Job Seeker cannot
    def test_07_role_based_job_posting(self):
        # Register recruiter
        self.client.post("/register", data={
            "name": "Tech Corp",
            "email": "recruiter@tech.com",
            "password": "password1234",
            "role": "recruiter"
        })
        self.client.post("/login", data={
            "email": "recruiter@tech.com",
            "password": "password1234"
        })

        post_resp = self.client.post("/post-job", data={
            "title": "Junior AI Engineer",
            "company": "Tech Corp",
            "location": "Bengaluru",
            "salary": "\u20b912 - 18 LPA",
            "description": "Work with LLMs and Python agents",
            "skills": "Python, PyTorch",
            "job_type": "Full-time",
            "work_mode": "Hybrid",
            "experience": "Fresher"
        }, follow_redirects=True)
        self.assertEqual(post_resp.status_code, 200)
        self.assertIn(b"Job submitted successfully", post_resp.data)
        self.assertIn(b"Junior AI Engineer", post_resp.data)

    # 8. Portal Explorer Elements: Criteria, Load More, Corporate Footer
    def test_08_portal_explorer_elements(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Criteria", response.data)
        self.assertIn(b"GET ALERT", response.data)
        self.assertIn(b"CONNECT WITH US", response.data)
        self.assertIn(b"LOAD MORE", response.data)
        self.assertIn(b"the global business and technology information and career network", response.data)
        self.assertIn(b"VALUES", response.data)
        self.assertIn(b"CAREERS", response.data)
        self.assertIn(b"PRESS", response.data)
        self.assertIn(b"REGIONS", response.data)

    # 9. Filter Functionality (Location, Experience, Function)
    def test_09_bloomberg_filters_and_criteria(self):
        # Filter by Bangalore
        resp = self.client.get("/?location=Bangalore")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Bangalore", resp.data)
        # Check active criteria pill
        self.assertIn(b"\xe2\x9c\x95", resp.data)  # ✕ symbol
        self.assertIn(b"Clear", resp.data)

    # 10. API Job Details Endpoint
    def test_10_api_job_details(self):
        response = self.client.get("/api/job/1")
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn("title", json_data)
        self.assertIn("formatted_date", json_data)
        self.assertIn("function", json_data)

    # 11. Get Alert & Connect Endpoints
    def test_11_alert_and_connect_actions(self):
        alert_resp = self.client.post("/get-alert", data={
            "email": "subscriber@domain.com",
            "criteria": "Bangalore Engineering"
        }, follow_redirects=True)
        self.assertEqual(alert_resp.status_code, 200)
        self.assertIn(b"Job alert configured for subscriber@domain.com", alert_resp.data)

        connect_resp = self.client.post("/connect", data={
            "name": "Darshil Gehlot",
            "email": "darshil@domain.com"
        }, follow_redirects=True)
        self.assertEqual(connect_resp.status_code, 200)
        self.assertIn(b"Talent Network", connect_resp.data)

    # 12. Intelligent Job Discovery: Skill match computation
    def test_12_skill_matching_logic(self):
        from app import compute_skill_match
        result = compute_skill_match("Python, Flask, PostgreSQL, Docker", "Python, Flask, React")
        self.assertEqual(result["match_pct"], 50)
        self.assertIn("Python", result["matching_skills"])
        self.assertIn("Flask", result["matching_skills"])
        self.assertIn("Docker", result["missing_skills"])

    # 13. Profile Strength Calculator
    def test_13_profile_strength_calculation(self):
        from app import calculate_profile_strength
        user_basic = {"name": "Test User", "email": "test@example.com"}
        basic_score = calculate_profile_strength(user_basic)
        self.assertLess(basic_score["percentage"], 50)
        self.assertTrue(len(basic_score["tips"]) > 0)

        user_complete = {
            "name": "Darshil Gehlot",
            "email": "darshil@example.com",
            "headline": "Lead AI Engineer",
            "bio": "Building scalable machine learning systems.",
            "skills": "Python, PyTorch, Docker, Kubernetes, AWS",
            "location": "Bangalore",
            "phone": "+91 9876543210",
            "github_url": "https://github.com/darshil2008"
        }
        complete_score = calculate_profile_strength(user_complete)
        self.assertGreaterEqual(complete_score["percentage"], 90)

    # 14. Bookmarking Jobs (Save / Unsave)
    def test_14_bookmark_toggle(self):
        # Login as seeker
        self.client.post("/login", data={"email": "seeker@example.com", "password": "seeker123"})
        # Bookmark job 1
        resp = self.client.post("/bookmark/1", headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["saved"])

        # Un-bookmark job 1
        resp2 = self.client.post("/bookmark/1", headers={"X-Requested-With": "XMLHttpRequest"})
        data2 = resp2.get_json()
        self.assertFalse(data2["saved"])

    # 15. Application Tracking System: Stage Progression
    def test_15_ats_stage_progression(self):
        # 1. Seeker applies to job
        self.client.post("/login", data={"email": "seeker@example.com", "password": "seeker123"})
        apply_resp = self.client.post("/apply/1", data={
            "cover_note": "Excited to apply for this backend role.",
            "resume_link": "https://github.com/darshil2008"
        }, follow_redirects=True)
        self.assertEqual(apply_resp.status_code, 200)

        # 2. Recruiter logs in and updates stage
        self.client.get("/logout")
        self.client.post("/login", data={"email": "recruiter@technova.com", "password": "recruiter123"})

        # Get application ID from DB
        with app.app_context():
            from app import get_db
            db = get_db()
            app_record = db.execute("SELECT id FROM applications WHERE job_id=1").fetchone()
            app_id = app_record["id"]
            # Ensure job 1 is assigned to recruiter for test
            db.execute("UPDATE jobs SET recruiter_id=(SELECT id FROM users WHERE email='recruiter@technova.com') WHERE id=1")
            db.commit()

        update_resp = self.client.post(f"/recruiter/application/update/{app_id}", data={
            "status": "Interview",
            "interview_date": "2026-12-01 14:00",
            "recruiter_notes": "Great technical portfolio."
        }, follow_redirects=True)
        self.assertEqual(update_resp.status_code, 200)

        # Verify status in database
        with app.app_context():
            db = get_db()
            updated = db.execute("SELECT status, interview_date FROM applications WHERE id=?", (app_id,)).fetchone()
            self.assertEqual(updated["status"], "Interview")
            self.assertEqual(updated["interview_date"], "2026-12-01 14:00")

    # 16. In-Platform Notifications
    def test_16_notifications(self):
        self.client.post("/login", data={"email": "seeker@example.com", "password": "seeker123"})
        notif_resp = self.client.get("/notifications")
        self.assertEqual(notif_resp.status_code, 200)
        self.assertIn(b"Notifications", notif_resp.data)

    # 17. Trust & Safety: Job Reporting & Admin Verification
    def test_17_trust_and_safety(self):
        # Seeker reports job 1
        self.client.post("/login", data={"email": "seeker@example.com", "password": "seeker123"})
        report_resp = self.client.post("/report-job/1", data={
            "reason": "Suspicious contact information"
        }, follow_redirects=True)
        self.assertEqual(report_resp.status_code, 200)
        self.assertIn(b"Trust", report_resp.data)

        # Admin logs in and checks reports
        self.client.get("/logout")
        self.client.post("/login", data={"email": "admin@worklane.com", "password": "admin123"})
        admin_resp = self.client.get("/admin")
        self.assertEqual(admin_resp.status_code, 200)
        self.assertIn(b"Suspicious contact information", admin_resp.data)

    # 18. Candidate Profile Update & Strength Recalculation
    def test_18_profile_update(self):
        self.client.post("/login", data={"email": "seeker@example.com", "password": "seeker123"})
        post_resp = self.client.post("/profile", data={
            "name": "Darshil Gehlot",
            "headline": "Lead AI & Distributed Systems Architect",
            "bio": "Building resilient event-driven architectures and LLM workflows.",
            "phone": "+91 9876543210",
            "location": "Bangalore, India",
            "skills": "Python, Flask, PyTorch, Docker, Kubernetes, AWS",
            "experience_years": 4,
            "github_url": "https://github.com/darshil2008",
            "linkedin_url": "https://linkedin.com/in/darshilgehlot",
            "portfolio_url": "https://darshil.dev"
        }, follow_redirects=True)
        self.assertEqual(post_resp.status_code, 200)
        self.assertIn(b"Your profile has been updated successfully!", post_resp.data)
        self.assertIn(b"Lead AI", post_resp.data)

    # 19. Recruiter Edit Job and Status Lifecycle (Live -> Paused -> Approved)
    def test_19_recruiter_job_management(self):
        self.client.post("/login", data={"email": "recruiter@technova.com", "password": "recruiter123"})
        
        # Post new role
        self.client.post("/post-job", data={
            "title": "Senior Cloud SRE",
            "company": "TechNova Solutions",
            "location": "Bangalore",
            "salary": "₹18-28 LPA",
            "description": "Maintain 99.99% availability across multi-cloud environments.",
            "skills": "AWS, Kubernetes, Terraform, Prometheus",
            "job_type": "Full-time",
            "work_mode": "Hybrid",
            "experience": "3-5 years",
            "department": "Infrastructure"
        })

        with app.app_context():
            from app import get_db
            db = get_db()
            job = db.execute("SELECT id FROM jobs WHERE title='Senior Cloud SRE'").fetchone()
            job_id = job["id"]

        # Edit job
        edit_resp = self.client.post(f"/edit-job/{job_id}", data={
            "title": "Principal Cloud SRE & Architect",
            "company": "TechNova Solutions",
            "location": "Remote",
            "salary": "₹25-35 LPA",
            "description": "Lead cloud reliability engineering practice.",
            "skills": "AWS, Kubernetes, Terraform, Go",
            "job_type": "Full-time",
            "work_mode": "Remote",
            "experience": "5+ years",
            "department": "Infrastructure"
        }, follow_redirects=True)
        self.assertEqual(edit_resp.status_code, 200)
        self.assertIn(b"Principal Cloud SRE", edit_resp.data)

        # Pause job
        pause_resp = self.client.post(f"/job/status/{job_id}/paused", follow_redirects=True)
        self.assertEqual(pause_resp.status_code, 200)
        self.assertIn(b"Paused", pause_resp.data)

    # 20. Application Withdrawal Flow
    def test_20_application_withdrawal(self):
        self.client.post("/login", data={"email": "seeker@example.com", "password": "seeker123"})
        self.client.post("/apply/2", follow_redirects=True)

        with app.app_context():
            from app import get_db
            db = get_db()
            app_rec = db.execute("SELECT id FROM applications WHERE job_id=2").fetchone()
            app_id = app_rec["id"]

        # Withdraw application
        with_resp = self.client.post(f"/application/withdraw/{app_id}", follow_redirects=True)
        self.assertEqual(with_resp.status_code, 200)
        self.assertIn(b"Application withdrawn successfully", with_resp.data)

    # 21. Formal Job Offer and Candidate Acceptance Flow
    def test_21_job_offer_flow_and_acceptance(self):
        # 1. Recruiter logs in and extends offer for job 3
        self.client.post("/login", data={"email": "seeker@example.com", "password": "seeker123"})
        self.client.post("/apply/3", data={"cover_note": "Ready to join"}, follow_redirects=True)
        self.client.get("/logout")

        with app.app_context():
            from app import get_db
            db = get_db()
            app_rec = db.execute("SELECT id FROM applications WHERE job_id=3").fetchone()
            app_id = app_rec["id"]
            db.execute("UPDATE jobs SET recruiter_id=(SELECT id FROM users WHERE email='recruiter@technova.com') WHERE id=3")
            db.commit()

        # Recruiter extends formal offer
        self.client.post("/login", data={"email": "recruiter@technova.com", "password": "recruiter123"})
        offer_resp = self.client.post(f"/recruiter/application/update/{app_id}", data={
            "status": "Offered",
            "recruiter_notes": "We are thrilled to offer you this role at 25 LPA!"
        }, follow_redirects=True)
        self.assertEqual(offer_resp.status_code, 200)

        # 2. Candidate logs in and views offer card on dashboard
        self.client.get("/logout")
        self.client.post("/login", data={"email": "seeker@example.com", "password": "seeker123"})
        dash_resp = self.client.get("/dashboard")
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn(b"Official Employment Offer Extended!", dash_resp.data)

        # 3. Candidate accepts offer
        accept_resp = self.client.post(f"/application/respond-offer/{app_id}/accept", follow_redirects=True)
        self.assertEqual(accept_resp.status_code, 200)
        self.assertIn(b"Offer Formally Accepted", accept_resp.data)

        # Verify DB status is 'Offer Accepted'
        with app.app_context():
            db = get_db()
            final_app = db.execute("SELECT status FROM applications WHERE id=?", (app_id,)).fetchone()
            self.assertEqual(final_app["status"], "Offer Accepted")

    # 22. Authentication & Session Lifecycle Verification
    def test_22_session_and_auth_lifecycle(self):
        # 1. Register new user
        reg_resp = self.client.post("/register", data={
            "name": "Lifecycle Engineer",
            "email": "lifecycle@test.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "role": "job_seeker"
        }, follow_redirects=True)
        self.assertEqual(reg_resp.status_code, 200)

        # 2. Login
        login_resp = self.client.post("/login", data={
            "email": "lifecycle@test.com",
            "password": "Password123!"
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)
        self.assertIn(b"Lifecycle Engineer", login_resp.data)

        # 3. Access protected dashboard
        dash_resp = self.client.get("/dashboard")
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn(b"WORKSPACE", dash_resp.data)

        # 4. Logout
        logout_resp = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(logout_resp.status_code, 200)

        # 5. Verify protected dashboard now redirects to login
        unauth_dash = self.client.get("/dashboard", follow_redirects=False)
        self.assertEqual(unauth_dash.status_code, 302)
        self.assertIn("/login", unauth_dash.location)


if __name__ == "__main__":
    unittest.main(verbosity=2)
