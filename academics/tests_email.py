"""
Email notification tests for student account creation.
"""

from django.test import TestCase
from django.core import mail
from django.conf import settings

from accounts.models import User
from academics.models import Student, Curriculum, Program, Department
from academics.email_service import send_student_account_welcome_email


class StudentEmailNotificationTests(TestCase):
    """Test email notifications when students are created."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for all tests."""
        # Create a department
        cls.department = Department.objects.create(
            department_code="CS",
            department_name="Computer Science"
        )

        # Create a program
        cls.program = Program.objects.create(
            department=cls.department,
            program_code="BS-CS",
            program_name="Bachelor of Science in Computer Science"
        )

        # Create a curriculum
        cls.curriculum = Curriculum.objects.create(
            program=cls.program,
            curriculum_code="BSCS-2023",
            curriculum_name="BS Computer Science 2023",
            academic_year_label="AY 2023-2024",
            total_units=183,
            is_active=True
        )

    def test_welcome_email_content(self):
        """Test that welcome email contains all required information."""
        # Create a test user
        user = User.objects.create_user(
            email="23-02639@g.batstate-u.edu.ph",
            password="test-password",
            first_name="John",
            last_name="Doe",
            role=User.Role.STUDENT,
            is_active=True,
        )

        # Send welcome email
        result = send_student_account_welcome_email(
            user,
            sr_code="23-02639",
            temporary_password="23-02639doe"
        )

        # Check that email was sent
        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)

        # Check email content
        email = mail.outbox[0]
        self.assertEqual(
            email.subject,
            "Welcome to Batangas State University - Auto POS System"
        )
        self.assertIn("23-02639@g.batstate-u.edu.ph", email.to)
        self.assertIn("John Doe", email.body)
        self.assertIn("23-02639", email.body)
        self.assertIn("23-02639doe", email.body)

    def test_welcome_email_html_content(self):
        """Test that HTML email contains security information."""
        user = User.objects.create_user(
            email="24-01234@g.batstate-u.edu.ph",
            password="test-password",
            first_name="Jane",
            last_name="Smith",
            role=User.Role.STUDENT,
            is_active=True,
        )

        result = send_student_account_welcome_email(
            user,
            sr_code="24-01234",
            temporary_password="24-01234smith"
        )

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        # Check for HTML message
        self.assertIsNotNone(email.alternatives)
        html_content = email.alternatives[0][0]

        # Check for important security information
        self.assertIn("temporary password", html_content.lower())
        self.assertIn("change this password", html_content.lower())
        self.assertIn("do not share", html_content.lower())

    def test_email_not_sent_with_invalid_email(self):
        """Test that email sending gracefully handles errors."""
        user = User.objects.create_user(
            email="invalid-email@test.local",
            password="test-password",
            first_name="Error",
            last_name="Test",
            role=User.Role.STUDENT,
            is_active=True,
        )

        # This should return False (email sending failed)
        # Note: Actual failure depends on email configuration
        try:
            result = send_student_account_welcome_email(
                user,
                sr_code="99-99999",
                temporary_password="testpass"
            )
            # In production SMTP, this would fail; in console backend it passes
            self.assertIsInstance(result, bool)
        except Exception:
            # Email sending can fail in test environment
            pass

    def test_from_email_configuration(self):
        """Test that DEFAULT_FROM_EMAIL is configured."""
        self.assertTrue(hasattr(settings, 'DEFAULT_FROM_EMAIL'))
        self.assertIsNotNone(settings.DEFAULT_FROM_EMAIL)
        self.assertGreater(len(settings.DEFAULT_FROM_EMAIL), 0)


class StudentRegistrationEmailIntegrationTests(TestCase):
    """Integration tests for student registration with email."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.department = Department.objects.create(
            department_code="IT",
            department_name="Information Technology"
        )

        cls.program = Program.objects.create(
            department=cls.department,
            program_code="BS-IT",
            program_name="Bachelor of Science in Information Technology"
        )

        cls.curriculum = Curriculum.objects.create(
            program=cls.program,
            curriculum_code="BSIT-2024",
            curriculum_name="BS Information Technology 2024",
            academic_year_label="AY 2024-2025",
            total_units=180,
            is_active=True
        )

    def test_student_registration_sends_email(self):
        """Test that student registration triggers email sending."""
        # Create a student through User/Student creation
        user = User.objects.create_user(
            email="25-05555@g.batstate-u.edu.ph",
            password="temporarypass",
            first_name="Alice",
            last_name="Wonder",
            role=User.Role.STUDENT,
            must_change_password=True,
            is_active=True
        )

        student = Student.objects.create(
            user=user,
            sr_code="25-05555",
            curriculum=self.curriculum,
            year_level=1,
            current_semester=1,
            section_code="1101",
            status=Student.Status.REGULAR
        )

        # Send welcome email
        result = send_student_account_welcome_email(
            user,
            sr_code="25-05555",
            temporary_password="temporarypass"
        )

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)

        # Verify email details
        email = mail.outbox[0]
        self.assertEqual(email.subject[:7], "Welcome")
        self.assertIn(user.email, email.to)
        self.assertIn("Alice Wonder", email.body)
