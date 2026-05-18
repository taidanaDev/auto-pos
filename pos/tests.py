from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase

from accounts.models import User
from academics.models import (
    Course,
    CourseRequirement,
    Curriculum,
    CurriculumCourse,
    Department,
    Program,
    Student,
    StudentCourseRecord,
)
from .models import POSPlanItem
from .pdf import get_evaluation_program_title, get_student_pdf_display_name
from .services import (
    build_complete_pos_display_items,
    generate_rearranged_pos_plan,
    get_original_graded_curriculum_items,
)


class POSPDFTemplateTests(SimpleTestCase):
    def test_evaluation_program_title_removes_bachelor_of_science_prefix(self):
        self.assertEqual(
            get_evaluation_program_title("Bachelor of Science in Computer Engineering"),
            "Computer Engineering",
        )

    def test_student_pdf_display_name_uses_lastname_firstname_format(self):
        student = SimpleNamespace(
            user=SimpleNamespace(first_name="Juan", last_name="Dela Cruz")
        )

        self.assertEqual(get_student_pdf_display_name(student), "DELA CRUZ, JUAN")

    def test_student_pdf_display_name_includes_middle_initial_when_available(self):
        student = SimpleNamespace(
            user=SimpleNamespace(
                first_name="Juan",
                middle_name="Santos",
                last_name="Dela Cruz",
            )
        )

        self.assertEqual(get_student_pdf_display_name(student), "DELA CRUZ, JUAN S.")

    def test_pdf_document_uses_dynamic_program_and_department_text(self):
        class StudentStub:
            sr_code = "22-12345"

            def full_name(self):
                return "Juan Dela Cruz"

        html = render_to_string(
            "pos/pdf/_pos_pdf_document.html",
            {
                "student": StudentStub(),
                "pos_plan": SimpleNamespace(created_at=datetime(2026, 5, 18)),
                "student_display_name": "DELA CRUZ, JUAN",
                "program_name": "Bachelor of Science in Industrial Engineering",
                "evaluation_program_title": "Industrial Engineering",
                "department_name": "Industrial Engineering",
                "academic_year": "2024-2025",
                "grouped_items": {
                    (1, "first_sem"): [
                        {
                            "course_code": "IE 101",
                            "course_title": "Introduction to Industrial Engineering",
                            "units": 3,
                            "requirement_text": "",
                            "grade": "",
                        }
                    ]
                },
            },
        )

        self.assertIn("College of Engineering - Department of Industrial Engineering", html)
        self.assertIn("INDUSTRIAL ENGINEERING", html)
        self.assertIn("EVALUATION", html)
        self.assertNotIn("BACHELOR OF SCIENCE IN", html)
        self.assertNotIn("Department of Electrical Engineering", html)
        self.assertNotIn("COMPUTER ENGINEERING", html)

    def test_pdf_document_keeps_signature_fields_blank(self):
        html = render_to_string(
            "pos/pdf/_pos_pdf_document.html",
            {
                "student": SimpleNamespace(
                    sr_code="22-12345",
                    full_name=lambda: "Juan Dela Cruz",
                ),
                "pos_plan": SimpleNamespace(created_at=datetime(2026, 5, 18)),
                "student_display_name": "DELA CRUZ, JUAN",
                "program_name": "Computer Engineering",
                "evaluation_program_title": "Computer Engineering",
                "department_name": "Computer Engineering",
                "academic_year": "2024-2025",
                "grouped_items": {},
            },
        )

        self.assertIn("Evaluated by:", html)
        self.assertIn("Checked and Reviewed:", html)
        self.assertIn("Approved by:", html)
        self.assertEqual(html.count("Date:"), 4)
        self.assertNotIn("Engr. ANTHONY HERNANDEZ", html)
        self.assertNotIn("Engr. MARK JOHN FEL T. RAYOS", html)
        self.assertNotIn("Engr. RICMART V. GARBIN", html)
        self.assertNotIn("Evaluator</div>", html)
        self.assertNotIn("Program Chair", html)
        self.assertNotIn("Department Chair", html)


class POSOriginalGradedDisplayTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="24-00003@g.batstate-u.edu.ph",
            password="testpass123",
            first_name="Ana",
            last_name="Reyes",
            role=User.Role.STUDENT,
        )
        department = Department.objects.create(
            department_code="CPE",
            department_name="Computer Engineering",
        )
        program = Program.objects.create(
            department=department,
            program_code="BSCPE",
            program_name="Bachelor of Science in Computer Engineering",
        )
        curriculum = Curriculum.objects.create(
            program=program,
            curriculum_code="BSCPE-2026",
            curriculum_name="BSCPE Curriculum",
            academic_year_label="2025-2026",
            total_units=12,
        )
        self.student = Student.objects.create(
            user=user,
            sr_code="24-00003",
            curriculum=curriculum,
            year_level=1,
            current_semester=1,
            section_code="1101",
        )

        self.passed_course = Course.objects.create(
            course_code="MATH 401",
            course_title="Differential Calculus",
            units=3,
        )
        self.failed_course = Course.objects.create(
            course_code="MATH 404",
            course_title="Differential Equations",
            units=3,
        )
        self.dependent_course = Course.objects.create(
            course_code="MATH 405",
            course_title="Advanced Engineering Mathematics",
            units=3,
        )

        CurriculumCourse.objects.create(
            curriculum=curriculum,
            course=self.passed_course,
            year_level=1,
            term=CurriculumCourse.Term.FIRST_SEM,
            display_order=1,
        )
        CurriculumCourse.objects.create(
            curriculum=curriculum,
            course=self.failed_course,
            year_level=1,
            term=CurriculumCourse.Term.SECOND_SEM,
            display_order=2,
        )
        CurriculumCourse.objects.create(
            curriculum=curriculum,
            course=self.dependent_course,
            year_level=1,
            term=CurriculumCourse.Term.SECOND_SEM,
            display_order=3,
        )

        CourseRequirement.objects.create(
            course=self.dependent_course,
            required_course=self.failed_course,
            requirement_type=CourseRequirement.RequirementType.PREREQUISITE,
        )

        StudentCourseRecord.objects.create(
            student=self.student,
            course=self.passed_course,
            school_year="2025-2026",
            term=CurriculumCourse.Term.FIRST_SEM,
            grade_value=Decimal("2.00"),
            remarks="Passed",
        )
        StudentCourseRecord.objects.create(
            student=self.student,
            course=self.failed_course,
            school_year="2025-2026",
            term=CurriculumCourse.Term.SECOND_SEM,
            grade_value=Decimal("5.00"),
            remarks="Failed",
        )

    def test_original_graded_courses_keep_curriculum_positions(self):
        original_items = get_original_graded_curriculum_items(self.student)

        self.assertEqual(
            [item["course"].course_code for item in original_items],
            ["MATH 401", "MATH 404"],
        )
        self.assertTrue(original_items[0]["is_completed"])
        self.assertTrue(original_items[1]["is_failed"])
        self.assertEqual(original_items[0]["curriculum_course"].year_level, 1)
        self.assertEqual(original_items[1]["curriculum_course"].term, CurriculumCourse.Term.SECOND_SEM)

    def test_generation_does_not_duplicate_passed_course_but_retakes_failed_course(self):
        pos_plan = generate_rearranged_pos_plan(self.student, generated_by=self.student.user)

        self.assertFalse(
            POSPlanItem.objects.filter(
                pos_plan=pos_plan,
                course=self.passed_course,
            ).exists()
        )

        retake_item = POSPlanItem.objects.get(
            pos_plan=pos_plan,
            course=self.failed_course,
        )
        self.assertEqual(retake_item.notes, "Retake failed course")
        self.assertTrue(
            POSPlanItem.objects.filter(
                pos_plan=pos_plan,
                course=self.dependent_course,
                planned_year_level=3,
                planned_term=CurriculumCourse.Term.SECOND_SEM,
            ).exists()
        )

    def test_complete_display_keeps_original_failed_attempt_and_retake(self):
        pos_plan = generate_rearranged_pos_plan(self.student, generated_by=self.student.user)
        grouped_items = build_complete_pos_display_items(self.student, pos_plan)

        failed_rows = [
            row
            for rows in grouped_items.values()
            for row in rows
            if row["course_code"] == "MATH 404"
        ]

        self.assertEqual(len(failed_rows), 2)
        self.assertEqual(failed_rows[0]["source"], "original")
        self.assertTrue(failed_rows[0]["is_failed"])
        self.assertEqual(failed_rows[0]["grade"], Decimal("5.00"))
        self.assertEqual(failed_rows[1]["source"], "rearranged")


class POSDifferentialEquationsScenarioTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="24-00004@g.batstate-u.edu.ph",
            password="testpass123",
            first_name="Ben",
            last_name="Santos",
            role=User.Role.STUDENT,
        )
        department = Department.objects.create(
            department_code="CPE",
            department_name="Computer Engineering",
        )
        program = Program.objects.create(
            department=department,
            program_code="BSCPE",
            program_name="Bachelor of Science in Computer Engineering",
        )
        curriculum = Curriculum.objects.create(
            program=program,
            curriculum_code="BSCPE-2027",
            curriculum_name="BSCPE Curriculum",
            academic_year_label="2026-2027",
            total_units=99,
        )
        self.student = Student.objects.create(
            user=user,
            sr_code="24-00004",
            curriculum=curriculum,
            year_level=2,
            current_semester=1,
            section_code="2101",
        )

        self.base = self.create_course("BASE 100", "Completed Base", 3, 1, "first_sem", 1)
        self.ee423 = self.create_course("EE 423", "Fundamentals of Electrical Engineering", 4, 2, "first_sem", 1)
        self.math404 = self.create_course("MATH 404", "Differential Equations", 3, 2, "first_sem", 2)
        self.engg414 = self.create_course("ENGG 414", "Numerical Methods", 3, 2, "second_sem", 1)
        self.create_course("FILL 2S", "Second Year Load", 22, 2, "second_sem", 2)
        self.cpe414 = self.create_course("CPE 414", "Feedback and Control Systems", 3, 3, "first_sem", 1)
        self.create_course("FILL 3F", "Third Year First Load", 19, 3, "first_sem", 2, prerequisite=self.base)
        self.cpe420 = self.create_course("CPE 420", "Digital Signal Processing", 4, 3, "second_sem", 1)
        self.create_course("FILL 3S", "Third Year Second Load", 16, 3, "second_sem", 2, prerequisite=self.base)
        self.create_course("FILL 4F", "Fourth Year First Load", 17, 4, "first_sem", 1, prerequisite=self.base)
        self.litr102 = self.create_course("Litr 102", "ASEAN Literature", 3, 4, "first_sem", 2)
        self.engg405 = self.create_course("ENGG 405", "Technopreneurship", 3, 4, "second_sem", 1)
        self.engg417 = self.create_course("ENGG 417", "On-the-Job Training", 4, 4, "second_sem", 2)
        prereq_for_cpe430 = self.create_course("CPE 422", "CpE Practice and Design 1", 1, 3, "second_sem", 3)
        self.cpe430 = self.create_course("CPE 430", "CpE Practice and Design 2", 2, 4, "second_sem", 3, prerequisite=prereq_for_cpe430)

        CourseRequirement.objects.create(
            course=self.engg414,
            required_course=self.math404,
            requirement_type=CourseRequirement.RequirementType.PREREQUISITE,
        )
        CourseRequirement.objects.create(
            course=self.cpe414,
            required_course=self.engg414,
            requirement_type=CourseRequirement.RequirementType.PREREQUISITE,
        )
        CourseRequirement.objects.create(
            course=self.cpe414,
            required_course=self.ee423,
            requirement_type=CourseRequirement.RequirementType.PREREQUISITE,
        )
        CourseRequirement.objects.create(
            course=self.cpe420,
            required_course=self.cpe414,
            requirement_type=CourseRequirement.RequirementType.PREREQUISITE,
        )

        for course in [self.base, self.ee423, prereq_for_cpe430]:
            StudentCourseRecord.objects.create(
                student=self.student,
                course=course,
                school_year="2025-2026",
                term=CurriculumCourse.Term.FIRST_SEM,
                grade_value=Decimal("2.00"),
                remarks="Passed",
            )

        StudentCourseRecord.objects.create(
            student=self.student,
            course=self.math404,
            school_year="2025-2026",
            term=CurriculumCourse.Term.FIRST_SEM,
            grade_value=Decimal("5.00"),
            remarks="Failed",
        )

    def create_course(self, code, title, units, year_level, term, display_order, prerequisite=None):
        course = Course.objects.create(
            course_code=code,
            course_title=title,
            units=units,
        )
        CurriculumCourse.objects.create(
            curriculum=self.student.curriculum,
            course=course,
            year_level=year_level,
            term=term,
            display_order=display_order,
        )
        if prerequisite:
            CourseRequirement.objects.create(
                course=course,
                required_course=prerequisite,
                requirement_type=CourseRequirement.RequirementType.PREREQUISITE,
            )
        return course

    def test_failed_differential_equations_cascades_like_expected_pos(self):
        pos_plan = generate_rearranged_pos_plan(self.student, generated_by=self.student.user)

        expected_slots = {
            "MATH 404": (3, CurriculumCourse.Term.FIRST_SEM),
            "ENGG 414": (3, CurriculumCourse.Term.SECOND_SEM),
            "CPE 414": (4, CurriculumCourse.Term.FIRST_SEM),
            "CPE 420": (4, CurriculumCourse.Term.SECOND_SEM),
            "Litr 102": (5, CurriculumCourse.Term.FIRST_SEM),
            "ENGG 417": (5, CurriculumCourse.Term.FIRST_SEM),
        }

        actual_slots = {
            item.course.course_code: (item.planned_year_level, item.planned_term)
            for item in POSPlanItem.objects.filter(pos_plan=pos_plan).select_related("course")
        }

        for course_code, expected_slot in expected_slots.items():
            self.assertEqual(actual_slots[course_code], expected_slot)
