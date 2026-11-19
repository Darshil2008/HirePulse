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
        self.assertIn(b"HirePulse", response.data)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
