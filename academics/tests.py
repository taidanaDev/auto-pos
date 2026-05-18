from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import User
from .models import Course, Curriculum, CurriculumCourse, Department, Program, Student, StudentCourseRecord
from .grade_upload_services import (
    parse_grade_rows_from_text,
    save_grade_rows,
    validate_grade_preview_rows,
)
from .upload_services import (
    read_curriculum_file,
    split_requirement_codes,
    validate_curriculum_rows,
)


class CurriculumUploadServiceTests(SimpleTestCase):
    def test_read_curriculum_file_accepts_friendly_csv_headers(self):
        uploaded_file = SimpleUploadedFile(
            "curriculum.csv",
            (
                "Course Code,Course Title,Units,Year Level,Term,Display Order,"
                "Is Required,Prerequisites,Corequisites,Standing Requirement,Is Elective\n"
                "MATH401,Differential Calculus,3.0,1.0,First Semester,1.0,"
                "yes,,, ,no\n"
            ).encode(),
            content_type="text/csv",
        )

        df = read_curriculum_file(uploaded_file)
        rows, errors = validate_curriculum_rows(df)

        self.assertEqual(errors, [])
        self.assertEqual(rows[0]["course_code"], "MATH 401")
        self.assertEqual(rows[0]["units"], 3)
        self.assertEqual(rows[0]["year_level"], 1)
        self.assertEqual(rows[0]["term"], "first_sem")

    def test_validate_curriculum_rows_flags_invalid_boolean_values(self):
        uploaded_file = SimpleUploadedFile(
            "curriculum.csv",
            (
                "course_code,course_title,units,year_level,term,display_order,"
                "is_required,prerequisites,corequisites,standing_requirement,is_elective\n"
                "CpE 401,Computer Programming 1,1,1,first_sem,1,maybe,,,,no\n"
            ).encode(),
            content_type="text/csv",
        )

        df = read_curriculum_file(uploaded_file)
        rows, errors = validate_curriculum_rows(df)

        self.assertTrue(errors)
        self.assertIn("Is required", rows[0]["errors"][0])

    def test_split_requirement_codes_accepts_semicolons_commas_and_newlines(self):
        self.assertEqual(
            split_requirement_codes("MATH401; SCI 401,ENGG402\nCpE 401"),
            ["MATH 401", "SCI 401", "ENGG 402", "CPE 401"],
        )


class GradeUploadServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="24-00001@g.batstate-u.edu.ph",
            password="testpass123",
            first_name="Juan",
            last_name="Dela Cruz",
            role=User.Role.STUDENT,
        )
        department = Department.objects.create(
            department_code="CpE",
            department_name="Computer Engineering",
        )
        program = Program.objects.create(
            department=department,
            program_code="BSCpE",
            program_name="Bachelor of Science in Computer Engineering",
        )
        curriculum = Curriculum.objects.create(
            program=program,
            curriculum_code="BSCpE-2025",
            curriculum_name="BSCpE Curriculum",
            academic_year_label="2025-2026",
            total_units=180,
        )
        self.student = Student.objects.create(
            user=self.user,
            sr_code="24-00001",
            curriculum=curriculum,
            year_level=1,
            current_semester=1,
            section_code="1101",
        )
        self.course = Course.objects.create(
            course_code="CPE 401",
            course_title="Computer Programming 1",
            units=1,
        )
        self.other_course = Course.objects.create(
            course_code="MATH 401",
            course_title="Differential Calculus",
            units=3,
        )
        CurriculumCourse.objects.create(
            curriculum=curriculum,
            course=self.course,
            year_level=1,
            term=CurriculumCourse.Term.FIRST_SEM,
            display_order=1,
        )

    def test_parse_grade_rows_only_accepts_students_curriculum_courses(self):
        rows, errors = parse_grade_rows_from_text(
            "CpE401 Computer Programming 1 2.50\nMATH401 Differential Calculus 1.75",
            self.student,
        )

        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["course_code"], "CPE 401")
        self.assertEqual(rows[0]["grade_value"], "2.50")

    def test_validate_grade_preview_rows_rejects_invalid_increment(self):
        rows, errors = validate_grade_preview_rows(
            [
                {
                    "line_number": 1,
                    "course_code": "CpE401",
                    "grade_value": "2.30",
                    "remarks": "Edited",
                }
            ],
            self.student,
        )

        self.assertTrue(errors)
        self.assertIn("0.25 increments", rows[0]["errors"][0])

    def test_parser_does_not_treat_course_title_number_as_grade(self):
        rows, errors = parse_grade_rows_from_text(
            "CpE401 Computer Programming 1",
            self.student,
        )

        self.assertTrue(errors)
        self.assertEqual(rows[0]["grade_value"], "")
        self.assertIn("Grade is required.", rows[0]["errors"])

    def test_save_grade_rows_updates_existing_record_and_model_sets_status(self):
        StudentCourseRecord.objects.create(
            student=self.student,
            course=self.course,
            school_year="2025-2026",
            term=CurriculumCourse.Term.FIRST_SEM,
            grade_value=Decimal("5.00"),
            remarks="Old",
        )

        result = save_grade_rows(
            self.student,
            "2025-2026",
            [
                {
                    "course_code": "CPE 401",
                    "grade_value": "2.50",
                    "remarks": "Updated from upload",
                }
            ],
        )

        record = StudentCourseRecord.objects.get(
            student=self.student,
            course=self.course,
            school_year="2025-2026",
            term=CurriculumCourse.Term.FIRST_SEM,
        )
        self.assertEqual(result["saved_count"], 0)
        self.assertEqual(result["updated_count"], 1)
        self.assertEqual(record.grade_value, Decimal("2.50"))
        self.assertEqual(record.status, StudentCourseRecord.RecordStatus.PASSED)

    def test_input_grades_blocks_reinput_for_passed_course(self):
        StudentCourseRecord.objects.create(
            student=self.student,
            course=self.course,
            school_year="2025-2026",
            term=CurriculumCourse.Term.FIRST_SEM,
            grade_value=Decimal("2.00"),
            remarks="Passed",
        )

        self.client.login(email=self.user.email, password="testpass123")
        response = self.client.post(
            reverse("input_grades"),
            {
                "school_year": "2026-2027",
                f"grade_{self.course.id}": "1.00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            StudentCourseRecord.objects.filter(
                student=self.student,
                course=self.course,
            ).count(),
            1,
        )
        self.assertFalse(
            StudentCourseRecord.objects.filter(
                student=self.student,
                course=self.course,
                school_year="2026-2027",
            ).exists()
        )

    def test_input_grades_allows_reinput_for_failed_course(self):
        CurriculumCourse.objects.create(
            curriculum=self.student.curriculum,
            course=self.other_course,
            year_level=1,
            term=CurriculumCourse.Term.FIRST_SEM,
            display_order=2,
        )
        StudentCourseRecord.objects.create(
            student=self.student,
            course=self.other_course,
            school_year="2025-2026",
            term=CurriculumCourse.Term.FIRST_SEM,
            grade_value=Decimal("5.00"),
            remarks="Failed",
        )

        self.client.login(email=self.user.email, password="testpass123")
        response = self.client.post(
            reverse("input_grades"),
            {
                "school_year": "2026-2027",
                f"grade_{self.other_course.id}": "2.00",
            },
        )

        self.assertRedirects(response, reverse("my_course_records"))
        retake_record = StudentCourseRecord.objects.get(
            student=self.student,
            course=self.other_course,
            school_year="2026-2027",
        )
        self.assertEqual(retake_record.grade_value, Decimal("2.00"))
        self.assertEqual(
            retake_record.status,
            StudentCourseRecord.RecordStatus.PASSED,
        )
