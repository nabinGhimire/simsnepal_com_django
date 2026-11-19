"""
Exam app shared functions for result calculation and grade ledger generation.
Centralized logic for cross-validation and easy updates.
"""
import json


def get_percentage(obtained, full):
    """Calculate percentage."""
    if full == 0:
        return 0
    return obtained * 100 / full


def get_grade_point(percent):
    """Convert percentage to grade, symbol, and grade point."""
    if percent < 0 or percent > 100:
        return ["SOMETHING WRONG", " ", 0.0]
    elif 90 <= percent <= 100:
        return ["A", "+", 4.0]
    elif 80 <= percent < 90:
        return ["A", " ", 3.6]
    elif 70 <= percent < 80:
        return ["B", "+", 3.2]
    elif 60 <= percent < 70:
        return ["B", " ", 2.8]
    elif 50 <= percent < 60:
        return ["C", "+", 2.4]
    elif 40 <= percent < 50:
        return ["C", " ", 2.0]
    elif 35 <= percent < 40:
        return ["D", " ", 1.6]
    elif 0 <= percent < 35:
        return ["NG", " ", 0]


def get_grade_point_exam(percent):
    """Exam-specific grade point (different scale)."""
    if percent < 0 or percent > 100:
        return ["ERROR", " ", 0.0]
    elif percent >= 90:
        return ["A", "+", 4.0]
    elif percent >= 80:
        return ["A", " ", 3.6]
    elif percent >= 70:
        return ["B", "+", 3.2]
    elif percent >= 60:
        return ["B", " ", 2.8]
    elif percent >= 50:
        return ["C", "+", 2.4]
    elif percent >= 40:
        return ["C", " ", 2.0]
    elif percent >= 35:
        return ["D", " ", 1.6]
    else:
        return ["NG", " ", 0]


def get_grade_point_from_point(point):
    """Convert grade point back to grade letter, symbol, and point."""
    if point >= 4.0:
        return ["A", "+", 4.0]
    elif point >= 3.6:
        return ["A", " ", 3.6]
    elif point >= 3.2:
        return ["B", "+", 3.2]
    elif point >= 2.8:
        return ["B", " ", 2.8]
    elif point >= 2.4:
        return ["C", "+", 2.4]
    elif point >= 2.0:
        return ["C", " ", 2.0]
    elif point >= 1.6:
        return ["D", " ", 1.6]
    else:
        return ["NG", " ", 0]


class GradeAndGpa:
    """Legacy grading system (grading_type=0)."""
    def __init__(self, fm_th, fm_pr, mo_th, mo_pr, priority, result_type=None):
        self.fm_th = fm_th
        self.fm_pr = fm_pr
        self.mo_th = mo_th
        self.mo_pr = mo_pr

        self.total_fm = 0
        self.total_mo = 0

        self.th_symbol = ' '
        self.pr_symbol = ' '

        self.th_grade = ' '
        self.th_point = 0

        self.pr_grade = ' '
        self.pr_point = 0

        self.fail = 0
        self.final_fail = 0
        self.total_symbol = ' '
        self.th_fail = False
        self.pr_fail = False

        if fm_th > 0:
            if fm_pr > 0:
                # Both theory and practical marks
                self.total_fm = fm_th + fm_pr
                self.total_mo = mo_th + mo_pr

                th_percent = get_percentage(mo_th, fm_th)
                pr_percent = get_percentage(mo_pr, fm_pr)

                self.th_grade, self.th_symbol, self.th_point = get_grade_point(th_percent)
                self.pr_grade, self.pr_symbol, self.pr_point = get_grade_point(pr_percent)

                if priority:
                    if self.th_point < 1.6:
                        self.th_fail = True
                        self.fail += 1
                    if self.pr_point < 1.6:
                        self.pr_fail = True
                        self.fail += 1
            else:
                # Only theory marks
                self.total_fm = fm_th
                self.total_mo = mo_th

                th_percent = get_percentage(mo_th, fm_th)
                self.th_grade, self.th_symbol, self.th_point = get_grade_point(th_percent)
                self.pr_grade = ' '
                self.pr_point = 0

                if priority:
                    if self.th_point < 1.6:
                        self.th_fail = True
                        self.fail += 1
        else:
            if fm_pr > 0:
                # Only Practical Marks
                self.total_fm = fm_pr
                self.total_mo = mo_pr

                pr_percent = get_percentage(mo_pr, fm_pr)
                self.pr_grade, self.pr_symbol, self.pr_point = get_grade_point(pr_percent)
                self.th_grade = ' '
                self.th_point = 0

                if priority:
                    if self.pr_point < 1.6:
                        self.pr_fail = True
                        self.fail += 1

        if self.total_fm <= 0:
            self.percent = 0
        else:
            self.percent = (self.total_mo / self.total_fm) * 100

        # Check if either TH or PR is NG (below passing marks)
        th_is_ng = fm_th > 0 and self.th_point < 1.6
        pr_is_ng = fm_pr > 0 and self.pr_point < 1.6

        if th_is_ng or pr_is_ng:
            self.total_grade = "NG"
            self.total_symbol = ""
            self.total_point = 0
            self.fail += 1
        else:
            self.total_grade, self.total_symbol, self.total_point = get_grade_point(self.percent)

        if priority:
            if self.total_point < 1.6:
                self.final_fail += 1


class GradeAndGpaNew:
    """New Grading System (grading_type=2)."""
    def __init__(self, fm_th, fm_pr, mo_th, mo_pr, priority, result_type=None):
        self.fm_th = fm_th
        self.fm_pr = fm_pr
        self.mo_th = mo_th
        self.mo_pr = mo_pr

        self.total_fm = 0
        self.total_mo = 0

        self.th_symbol = ' '
        self.pr_symbol = ' '

        self.th_grade = ' '
        self.th_point = 0

        self.pr_grade = ' '
        self.pr_point = 0

        self.fail = 0
        self.final_fail = 0
        self.total_symbol = ' '
        self.th_fail = False
        self.pr_fail = False

        if fm_th > 0:
            if fm_pr > 0:
                self.total_fm = fm_th + fm_pr
                self.total_mo = mo_th + mo_pr

                th_percent = get_percentage(mo_th, fm_th)
                pr_percent = get_percentage(mo_pr, fm_pr)

                self.th_grade, self.th_symbol, self.th_point = get_grade_point(th_percent)
                self.pr_grade, self.pr_symbol, self.pr_point = get_grade_point(pr_percent)

                if priority:
                    if self.th_point < 1.6:
                        self.th_fail = True
                        self.fail += 1
                    if self.pr_point < 1.6:
                        self.pr_fail = True
                        self.fail += 1
            else:
                self.total_fm = fm_th
                self.total_mo = mo_th

                th_percent = get_percentage(mo_th, fm_th)
                self.th_grade, self.th_symbol, self.th_point = get_grade_point(th_percent)
                self.pr_grade = ' '
                self.pr_point = 0

                if priority and self.th_point < 1.6:
                    self.th_fail = True
                    self.fail += 1

        elif fm_pr > 0:
            self.total_fm = fm_pr
            self.total_mo = mo_pr

            pr_percent = get_percentage(mo_pr, fm_pr)
            self.pr_grade, self.pr_symbol, self.pr_point = get_grade_point(pr_percent)
            self.th_grade = ' '
            self.th_point = 0

            if priority and self.pr_point < 1.6:
                self.pr_fail = True
                self.fail += 1

        if self.total_fm > 0:
            self.percent = (self.total_mo / self.total_fm) * 100
        else:
            self.percent = 0

        th_is_ng = fm_th > 0 and self.th_point < 1.6
        pr_is_ng = fm_pr > 0 and self.pr_point < 1.6

        if th_is_ng or pr_is_ng:
            self.total_grade = "NG"
            self.total_symbol = ""
            self.total_point = 0
            self.fail += 1
        else:
            self.total_grade, self.total_symbol, self.total_point = get_grade_point(self.percent)

        if priority and self.total_point < 1.6:
            self.final_fail += 1

        if result_type == 2:
            if self.th_fail or self.pr_fail:
                self.fail += 1
                self.final_fail += 1
                self.total_grade = "NG"
                self.total_symbol = ""
                self.total_point = 0
                if self.th_fail:
                    self.th_grade = "NG"
                    self.th_symbol = ""
                    self.th_point = 0
                if self.pr_fail:
                    self.pr_grade = "NG"
                    self.pr_symbol = ""
                    self.pr_point = 0


class GradeAndGpaNonGradeTheory:
    """Non-Grade System theory component (grading_type=1)."""
    def __init__(self, fm_th, mo_th, pm_marks=None):
        self.fm_th = fm_th
        self.mo_th = mo_th

        self.total_fm = 0
        self.total_mo = 0

        self.th_symbol = ' '
        self.pr_symbol = ' '

        self.th_grade = ' '
        self.th_point = 0

        self.pr_grade = ' '
        self.pr_point = 0

        self.fail = 0
        self.final_fail = 0
        self.total_symbol = ' '

        if fm_th > 0:
            th_percent = get_percentage(mo_th, fm_th)
            self.th_grade, self.th_symbol, self.th_point = get_grade_point(th_percent)
            self.pr_grade = ' '
            self.pr_point = 0

            pass_percent = pm_marks * 100 / fm_th if pm_marks and fm_th > 0 else 35
            if th_percent < pass_percent:
                self.fail += 1
                self.th_grade = "NG"
                self.th_symbol = " "
                self.th_point = 0

        if self.fm_th <= 0:
            self.percent = 0
        else:
            self.percent = (self.mo_th / self.fm_th) * 100

        self.total_grade, self.total_symbol, self.total_point = get_grade_point(self.percent)

        if self.fail > 0:
            self.final_fail += 1
            self.total_grade = "NG"
            self.total_symbol = " "
            self.total_point = 0


class GradeAndGpaNonGradePractical:
    """Non-Grade System practical component (grading_type=1)."""
    def __init__(self, fm_pr, mo_pr, pm_marks=None):
        self.fm_pr = fm_pr
        self.mo_pr = mo_pr

        self.total_fm = 0
        self.total_mo = 0

        self.th_symbol = ' '
        self.pr_symbol = ' '

        self.th_grade = ' '
        self.th_point = 0

        self.pr_grade = ' '
        self.pr_point = 0

        self.fail = 0
        self.final_fail = 0
        self.total_symbol = ' '

        if fm_pr > 0:
            pr_percent = get_percentage(mo_pr, fm_pr)
            self.pr_grade, self.pr_symbol, self.pr_point = get_grade_point(pr_percent)
            self.th_grade = ' '
            self.th_point = 0

            pass_percent = pm_marks * 100 / fm_pr if pm_marks and fm_pr > 0 else 40
            if pr_percent < pass_percent:
                self.fail += 1
                self.pr_grade = "NG"
                self.pr_symbol = " "
                self.pr_point = 0

        if self.fm_pr <= 0:
            self.percent = 0
        else:
            self.percent = (self.mo_pr / self.fm_pr) * 100

        self.total_grade, self.total_symbol, self.total_point = get_grade_point(self.percent)

        if self.fail > 0:
            self.final_fail += 1
            self.total_grade = "NG"
            self.total_symbol = " "
            self.total_point = 0


def remarks(gpa, failed_subjects=0, absent_subjects=0, is_final_term=False, subject_performance=None):
    """Generate contextual remarks based on GPA and subject performance."""
    if is_final_term:
        if failed_subjects == 0:
            base_remark = "Congratulations! Promoted to the next class."
        elif failed_subjects <= 2:
            base_remark = "Insufficient to promote. Provision for re-exam."
        else:
            base_remark = "Failed! Insufficient to promote."

        if absent_subjects > 0:
            base_remark += f" Absent in {absent_subjects} subject(s)."

        return base_remark

    if gpa == '-' or gpa == 0:
        return "Needs significant improvement. Please focus on all subjects."

    if gpa >= 3.6:
        overall = "Excellent"
    elif gpa >= 3.2:
        overall = "Very Good"
    elif gpa >= 2.8:
        overall = "Good"
    elif gpa >= 2.4:
        overall = "Satisfactory"
    elif gpa >= 2.0:
        overall = "Average"
    elif gpa >= 1.6:
        overall = "Below Average"
    else:
        overall = "Needs Improvement"

    feedback_parts = [f"Overall: {overall} (GPA: {gpa:.2f})."]

    if subject_performance:
        weak_subjects = []
        strong_subjects = []
        for sub in subject_performance:
            if sub.get('gradepoint', 0) < 1.6:
                weak_subjects.append(sub.get('subject_name', 'Subject'))
            elif sub.get('gradepoint', 0) >= 3.6:
                strong_subjects.append(sub.get('subject_name', 'Subject'))

        if weak_subjects:
            feedback_parts.append(f"Needs work in: {', '.join(weak_subjects)}.")
        if strong_subjects:
            feedback_parts.append(f"Strong in: {', '.join(strong_subjects)}.")

    return ' '.join(feedback_parts)


def calculate_rank(school, session, grade, term, section=None, regno=None, rank_by="total", config=None):
    """Calculate rank for students. Skips failed students."""
    from sms.models import StudentSession, Subject, MarkObtained, GradeFullMarks
    from exam.models import ResultManagement

    # Handle school being either SchoolBranch object or integer ID
    school_id = school.id if hasattr(school, 'id') else school
    
    # Handle grade being either SchoolGrade object or integer ID
    grade_id = grade.id if hasattr(grade, 'id') else grade
    
    # Handle term being either SchoolTerm object or integer ID
    term_id = term.id if hasattr(term, 'id') else term

    students_qs = StudentSession.objects.filter(session=session, grade=grade_id, status=True)
    if section:
        students_qs = students_qs.filter(section=section)

    students = list(students_qs.select_related('student'))
    if not students:
        return {}

    subjects = Subject.objects.filter(branch_id=school_id, grade_id=grade_id, status=True)
    subject_ids = list(subjects.values_list('id', flat=True))

    marks_qs = MarkObtained.objects.filter(
        school_id=school_id,
        session_id=session.id if hasattr(session, 'id') else session,
        grade_id=grade_id,
        term_id=term_id,
        subject_id__in=subject_ids,
        student_id__in=[s.student_id for s in students],
    ).values('student_id', 'subject_id', 'th_mo', 'pr_mo')

    marks_map = {}
    for m in marks_qs:
        marks_map[(m['student_id'], m['subject_id'])] = (m.get('th_mo', 0) or 0, m.get('pr_mo', 0) or 0)

    fm_qs = GradeFullMarks.objects.filter(
        school_id=school_id,
        session_id=session.id if hasattr(session, 'id') else session,
        grade_id=grade_id,
        term_id=term_id,
        subject_id__in=subject_ids,
    ).values('subject_id', 'th_fm', 'pr_fm')

    fm_map = {}
    for fm in fm_qs:
        fm_map[(fm['subject_id'])] = (fm.get('th_fm', 0) or 0, fm.get('pr_fm', 0) or 0)

    # Get pass logic config from config dict
    th_pass_type = config.get('th_pass_type', 'percentage')
    th_pass_value = float(config.get('th_pass_value', 35.0))
    pr_pass_type = config.get('pr_pass_type', 'percentage')
    pr_pass_value = float(config.get('pr_pass_value', 35.0))

    student_scores = {}
    failed_regnos = set()
    
    for student in students:
        total_mo = 0
        total_fm = 0
        has_failed = False
        
        for subject in subjects:
            th_mo, pr_mo = marks_map.get((student.student_id, subject.id), (0, 0))
            th_fm, pr_fm = fm_map.get(subject.id, (0, 0))
            total_mo += th_mo + pr_mo
            total_fm += th_fm + pr_fm
            
            # Check if student failed this subject using configurable pass logic
            # Theory check
            if th_fm > 0:
                if th_pass_type == 'percentage':
                    th_percent = (th_mo / th_fm * 100) if th_fm > 0 else 0
                    if th_percent < th_pass_value:
                        has_failed = True
                elif th_pass_type == 'gpa':
                    if th_mo > 0:
                        th_percent = (th_mo / th_fm * 100) if th_fm > 0 else 0
                        _, _, th_gpa = get_grade_point(th_percent)
                        if th_gpa < th_pass_value:
                            has_failed = True
                elif th_pass_type == 'marks':
                    if th_mo < th_pass_value:
                        has_failed = True
            
            # Practical check
            if pr_fm > 0:
                if pr_pass_type == 'percentage':
                    pr_percent = (pr_mo / pr_fm * 100) if pr_fm > 0 else 0
                    if pr_percent < pr_pass_value:
                        has_failed = True
                elif pr_pass_type == 'gpa':
                    if pr_mo > 0:
                        pr_percent = (pr_mo / pr_fm * 100) if pr_fm > 0 else 0
                        _, _, pr_gpa = get_grade_point(pr_percent)
                        if pr_gpa < pr_pass_value:
                            has_failed = True
                elif pr_pass_type == 'marks':
                    if pr_mo < pr_pass_value:
                        has_failed = True

        if has_failed:
            failed_regnos.add(student.student.reg_no)
            continue  # Skip failed students from ranking

        if rank_by == "total":
            score = total_mo
        elif rank_by == "th":
            score = sum(marks_map.get((student.student_id, s.id), (0, 0))[0] for s in subjects)
        else:
            score = total_mo

        if total_fm > 0:
            score = score / total_fm * 100

        student_scores[student.student.reg_no] = score

    sorted_regnos = sorted(student_scores.keys(), key=lambda r: student_scores[r], reverse=True)
    ranks = {}
    for rank, reg_no in enumerate(sorted_regnos, 1):
        ranks[reg_no] = rank

    return ranks


def _parse_weighted_term_config(weight_config, target_term_id, include_current=False):
    """Parse weighted term configuration."""
    if not weight_config:
        return {}

    if isinstance(weight_config, str):
        try:
            import json
            weight_config = json.loads(weight_config)
        except Exception:
            return {}

    if not isinstance(weight_config, dict):
        return {}

    global_plan = weight_config.get("plan", "direct")
    target_fm_th = float(weight_config.get("target_fm_th", 100))
    target_fm_pr = float(weight_config.get("target_fm_pr", 100))

    sources_block = {}
    if "sources" in weight_config:
        sources_block = weight_config["sources"]
    elif "weights" in weight_config:
        weights_block = weight_config.get("weights", {})
        target_block = weights_block.get(str(target_term_id)) or weights_block.get(target_term_id, {})
        sources_block = target_block.get("sources", target_block)
    else:
        sources_block = weight_config

    normalized = {}

    def _as_float(val):
        try:
            return float(val)
        except Exception:
            return 0.0

    for term_key, value in sources_block.items():
        try:
            term_id = int(term_key)
        except Exception:
            continue

        if term_id == target_term_id and not include_current:
            continue

        th_from_th = th_from_pr = pr_from_th = pr_from_pr = 0.0

        if isinstance(value, (int, float)):
            th_from_th = pr_from_pr = float(value)
        elif isinstance(value, dict):
            th_block = value.get("th", {})
            pr_block = value.get("pr", {})

            if isinstance(th_block, dict):
                th_from_th = _as_float(th_block.get("th", 0))
                th_from_pr = _as_float(th_block.get("pr", 0))
            else:
                th_from_th = _as_float(value.get("th", 0))
                th_from_pr = _as_float(value.get("pr", 0))

            if isinstance(pr_block, dict):
                pr_from_th = _as_float(pr_block.get("th", 0))
                pr_from_pr = _as_float(pr_block.get("pr", 0))
            else:
                pr_from_th = _as_float(value.get("th", 0))
                pr_from_pr = _as_float(value.get("pr", 0))

        if th_from_th > 0 or th_from_pr > 0 or pr_from_th > 0 or pr_from_pr > 0:
            normalized[str(term_id)] = {
                "th_from_th": th_from_th / 100.0,
                "th_from_pr": th_from_pr / 100.0,
                "pr_from_th": pr_from_th / 100.0,
                "pr_from_pr": pr_from_pr / 100.0,
                "plan": global_plan,
                "th_target_fm": target_fm_th,
                "pr_target_fm": target_fm_pr,
            }

    return normalized


def calculate_student_result(school, session, grade, term, student_session, config):
    """
    Calculate result for a single student using the configured grading system.
    This is the core calculation function used by all print views.
    
    Args:
        school: SchoolBranch instance
        session: EduSession instance
        grade: SchoolGrade instance
        term: SchoolTerm instance
        student_session: StudentSession instance
        config: dict with grading_type, ledger_type, calculation_type, assessment_source
    
    Returns:
        dict with calculated results
    """
    from sms.models import Subject, MarkObtained
    from exam.models import GradeFullMarks, ResultManagement

    subjects = Subject.objects.filter(
        branch=school, grade=grade, status=True
    ).order_by('id')

    grading_type = config.get('grading_type', 0)
    ledger_type = config.get('ledger_type', 1)
    calculation_type = config.get('calculation_type', 'legacy')

    term_weights = {}
    if calculation_type == 'weighted':
        try:
            rm = ResultManagement.objects.get(school=school, year=session, school_term=term)
            term_weights = json.loads(rm.term_calculation)
        except (ResultManagement.DoesNotExist, json.JSONDecodeError):
            term_weights = {}

    mo_dict = {}
    total_th_mo = 0
    total_pr_mo = 0
    total_th_fm = 0
    total_pr_fm = 0
    cgpa_sum = 0
    subject_count = 0
    fail_count = 0

    for subject in subjects:
        subject_count += 1
        mo_dict[subject.id] = {
            'subject_name': subject.subject,
            'subject_id': subject.id,
        }

        try:
            marks = MarkObtained.objects.get(
                student=student_session.student,
                session=session,
                grade=grade,
                term=term,
                subject=subject
            )
            th_mo = marks.th_mo or 0
            pr_mo = marks.pr_mo or 0
        except MarkObtained.DoesNotExist:
            th_mo = 0
            pr_mo = 0

        try:
            gfm = GradeFullMarks.objects.get(
                session=session, school=school, grade=grade, term=term, subject=subject
            )
            th_fm = gfm.th_fm or 0
            pr_fm = gfm.pr_fm or 0
            th_pm = gfm.th_pm or 0
            pr_pm = gfm.pr_pm or 0
        except GradeFullMarks.DoesNotExist:
            th_fm = pr_fm = th_pm = pr_pm = 0

        mo_dict[subject.id]['th_fm'] = th_fm
        mo_dict[subject.id]['pr_fm'] = pr_fm
        mo_dict[subject.id]['th_pm'] = th_pm
        mo_dict[subject.id]['pr_pm'] = pr_pm
        mo_dict[subject.id]['th_mo'] = th_mo
        mo_dict[subject.id]['pr_mo'] = pr_mo

        if calculation_type == 'weighted' and term_weights:
            weighted_th_mo = 0
            weighted_pr_mo = 0
            weighted_th_fm = 0
            weighted_pr_fm = 0

            for src_term_id, weight in term_weights.items():
                try:
                    src_term = int(src_term_id)
                    w = int(weight) / 100.0
                    if src_term == term.id:
                        weighted_th_mo += th_mo
                        weighted_pr_mo += pr_mo
                        weighted_th_fm += th_fm
                        weighted_pr_fm += pr_fm
                    else:
                        src_marks = MarkObtained.objects.get(
                            student=student_session.student,
                            session=session,
                            grade=grade,
                            term_id=src_term,
                            subject=subject
                        )
                        src_gfm = GradeFullMarks.objects.get(
                            session=session, school=school, grade=grade, term_id=src_term, subject=subject
                        )
                        weighted_th_mo += (src_marks.th_mo or 0) * w
                        weighted_pr_mo += (src_marks.pr_mo or 0) * w
                        weighted_th_fm += (src_gfm.th_fm or 0) * w
                        weighted_pr_fm += (src_gfm.pr_fm or 0) * w
                except (MarkObtained.DoesNotExist, GradeFullMarks.DoesNotExist, ValueError):
                    continue

            th_mo = round(weighted_th_mo)
            pr_mo = round(weighted_pr_mo)
            th_fm = round(weighted_th_fm)
            pr_fm = round(weighted_pr_fm)
            mo_dict[subject.id]['th_mo'] = th_mo
            mo_dict[subject.id]['pr_mo'] = pr_mo
            mo_dict[subject.id]['th_fm'] = th_fm
            mo_dict[subject.id]['pr_fm'] = pr_fm

        total_th_mo += th_mo
        total_pr_mo += pr_mo
        total_th_fm += th_fm
        total_pr_fm += pr_fm

        priority = getattr(subject, 'heavy_weight', True)
        if grading_type == 2:
            g_obj = GradeAndGpaNew(th_fm, pr_fm, th_mo, pr_mo, priority, result_type=2)
        elif grading_type == 1:
            if th_fm > 0 and pr_fm > 0:
                th_obj = GradeAndGpaNonGradeTheory(th_fm, th_mo, th_pm)
                pr_obj = GradeAndGpaNonGradePractical(pr_fm, pr_mo, pr_pm)
            elif th_fm > 0:
                th_obj = GradeAndGpaNonGradeTheory(th_fm, th_mo, th_pm)
                pr_obj = None
            elif pr_fm > 0:
                th_obj = None
                pr_obj = GradeAndGpaNonGradePractical(pr_fm, pr_mo, pr_pm)
            else:
                th_obj = pr_obj = None
        else:
            g_obj = GradeAndGpa(th_fm, pr_fm, th_mo, pr_mo, priority)

        if grading_type == 1:
            if th_obj:
                mo_dict[subject.id]['th_grade'] = th_obj.th_grade
                mo_dict[subject.id]['th_symbol'] = th_obj.th_symbol
                mo_dict[subject.id]['th_point'] = th_obj.th_point
                mo_dict[subject.id]['th_fail'] = th_obj.fail > 0
                cgpa_sum += th_obj.th_point
            if pr_obj:
                mo_dict[subject.id]['pr_grade'] = pr_obj.pr_grade
                mo_dict[subject.id]['pr_symbol'] = pr_obj.pr_symbol
                mo_dict[subject.id]['pr_point'] = pr_obj.pr_point
                mo_dict[subject.id]['pr_fail'] = pr_obj.fail > 0
                cgpa_sum += pr_obj.pr_point
            if th_obj and pr_obj:
                mo_dict[subject.id]['total_grade'] = th_obj.total_grade
                mo_dict[subject.id]['total_symbol'] = th_obj.total_symbol
                mo_dict[subject.id]['total_point'] = th_obj.total_point
            elif th_obj:
                mo_dict[subject.id]['total_grade'] = th_obj.total_grade
                mo_dict[subject.id]['total_symbol'] = th_obj.total_symbol
                mo_dict[subject.id]['total_point'] = th_obj.total_point
            elif pr_obj:
                mo_dict[subject.id]['total_grade'] = pr_obj.total_grade
                mo_dict[subject.id]['total_symbol'] = pr_obj.total_symbol
                mo_dict[subject.id]['total_point'] = pr_obj.total_point
            if th_obj and th_obj.fail > 0:
                fail_count += 1
            if pr_obj and pr_obj.fail > 0:
                fail_count += 1
        else:
            mo_dict[subject.id]['th_grade'] = g_obj.th_grade
            mo_dict[subject.id]['th_symbol'] = g_obj.th_symbol
            mo_dict[subject.id]['th_point'] = g_obj.th_point
            mo_dict[subject.id]['pr_grade'] = g_obj.pr_grade
            mo_dict[subject.id]['pr_symbol'] = g_obj.pr_symbol
            mo_dict[subject.id]['pr_point'] = g_obj.pr_point
            mo_dict[subject.id]['th_fail'] = g_obj.th_fail
            mo_dict[subject.id]['pr_fail'] = g_obj.pr_fail
            mo_dict[subject.id]['total_grade'] = g_obj.total_grade
            mo_dict[subject.id]['total_symbol'] = g_obj.total_symbol
            mo_dict[subject.id]['total_point'] = g_obj.total_point
            cgpa_sum += g_obj.total_point
            if g_obj.th_fail:
                fail_count += 1
            if g_obj.pr_fail:
                fail_count += 1

        mo_dict[subject.id]['gradepoint'] = g_obj.total_point if grading_type != 1 else mo_dict[subject.id].get('total_point', 0)

    cgpa = round(cgpa_sum / subject_count, 2) if subject_count > 0 else 0

    if cgpa > 0:
        overall_grade, overall_symbol, overall_point = get_grade_point_from_point(cgpa)
    else:
        overall_grade, overall_symbol, overall_point = "NG", "", 0

    remarks_text = remarks(cgpa)

    total_mo = total_th_mo + total_pr_mo
    total_fm = total_th_fm + total_pr_fm
    percentage = round((total_mo / total_fm * 100), 2) if total_fm > 0 else 0

    return {
        'mo_dict': mo_dict,
        'total_th_mo': total_th_mo,
        'total_pr_mo': total_pr_mo,
        'total_mo': total_mo,
        'total_fm': total_fm,
        'total_th_fm': total_th_fm,
        'total_pr_fm': total_pr_fm,
        'percentage': percentage,
        'cgpa': cgpa,
        'overall_grade': overall_grade,
        'overall_symbol': overall_symbol,
        'overall_point': overall_point,
        'fail_count': fail_count,
        'remarks': remarks_text,
        'subjects': subjects,
    }


def build_grade_ledger_context(**kwargs):
    """
    Build complete grade ledger context for template rendering.
    Supports Legacy (0), Non-Grade System (1), New Grading System (2).
    
    Returns:
        dict with all context variables needed for grade ledger templates
    """
    no_of_terms = kwargs.get('no_of_terms', 0)
    term_list = kwargs.get('term_list', [])
    term_calculation = kwargs.get('term_calculation', {})
    pass_fail_filter = kwargs.get('pass_fail_filter', 0)
    students = kwargs.get('students', [])
    grade_subjects = kwargs.get('grade_subjects', [])
    this_term = kwargs.get('this_term')
    this_grade = kwargs.get('this_grade')
    school = kwargs.get('school')
    subjects = kwargs.get('subjects', [])
    this_section = kwargs.get('this_section')
    slogan = kwargs.get('slogan', " ")
    logo = kwargs.get('logo', "")
    term_acronym = kwargs.get('term_acronym', {})
    this_session = kwargs.get('this_session')
    grading_type = kwargs.get('grading_type', 0)

    if isinstance(term_calculation, str):
        try:
            term_calculation = json.loads(term_calculation)
        except (json.JSONDecodeError, TypeError):
            term_calculation = {}

    if not this_session:
        try:
            year = this_term.year if hasattr(this_term, 'year') else this_term.term.year
            from sms.models import EduSession
            this_session = EduSession.objects.get(year=year)
        except Exception:
            this_session = None

    try:
        from exam.models import SchoolTerminology
        terminology = SchoolTerminology.objects.get(school=school)
    except Exception:
        terminology = None

    config = {'grading_type': grading_type, 'ledger_type': 1, 'calculation_type': 'legacy'}

    from exam.models import SchoolTerm

    student_data = []
    for student in students:
        student_terms = {}
        total_fm = 0
        total_mo = 0
        cgpa_sum = 0
        cgpa_count = 0
        any_fail = False

        for t_id in term_list:
            try:
                term = SchoolTerm.objects.get(id=t_id)
                result = calculate_student_result(school, this_session, this_grade, term, student, config)
                student_terms[t_id] = {
                    'term': term,
                    'term_name': term.term_name,
                    'term_short': term.name_in_short,
                    **result,
                }
                total_fm += result['total_fm']
                total_mo += result['total_mo']
                cgpa_sum += result['cgpa']
                cgpa_count += 1
                if result['fail_count'] > 0:
                    any_fail = True
            except Exception:
                continue

        avg_cgpa = round(cgpa_sum / cgpa_count, 2) if cgpa_count > 0 else 0
        percentage = round((total_mo / total_fm * 100), 2) if total_fm > 0 else 0
        
        if avg_cgpa >= 4.0:
            overall_grade, overall_symbol = "A", "+"
        elif avg_cgpa >= 3.6:
            overall_grade, overall_symbol = "A", " "
        elif avg_cgpa >= 3.2:
            overall_grade, overall_symbol = "B", "+"
        elif avg_cgpa >= 2.8:
            overall_grade, overall_symbol = "B", " "
        elif avg_cgpa >= 2.4:
            overall_grade, overall_symbol = "C", "+"
        elif avg_cgpa >= 2.0:
            overall_grade, overall_symbol = "C", " "
        elif avg_cgpa >= 1.6:
            overall_grade, overall_symbol = "D", " "
        else:
            overall_grade, overall_symbol = "NG", ""

        student_data.append({
            'student': student,
            'terms': student_terms,
            'totals': {
                'total_fm': total_fm,
                'total_mo': total_mo,
                'percentage': percentage,
                'cgpa': avg_cgpa,
                'overall_grade': overall_grade,
                'overall_symbol': overall_symbol,
                'any_fail': any_fail,
            },
        })

    if pass_fail_filter == 1:
        student_data = [s for s in student_data if not s['totals']['any_fail']]
    elif pass_fail_filter == 2:
        student_data = [s for s in student_data if s['totals']['any_fail']]

    return {
        'school': school,
        'term': this_term,
        'grade': this_grade,
        'section': this_section,
        'subjects': subjects,
        'term_list': term_list,
        'term_acronym': term_acronym,
        'no_of_terms': no_of_terms,
        'student_data': student_data,
        'config': config,
        'data_filter': pass_fail_filter,
        'grading_type': grading_type,
        'slogan': slogan,
        'logo': logo,
        'terminology': terminology,
    }


def get_grade_config(school, session, grade):
    """Get GradeResultConfig for a grade/session, or return defaults."""
    from exam.models import GradeResultConfig, LiveResult, SchoolResultType
    gc = GradeResultConfig.objects.filter(
        school=school, year=session, grade=grade
    ).first()
    if gc:
        return {
            'grading_type': gc.grading_type,
            'ledger_type': gc.ledger_type,
            'calculation_type': gc.calculation_type,
            'assessment_source': gc.assessment_source,
        }
    lr = LiveResult.objects.filter(school=school).first()
    sr = SchoolResultType.objects.filter(school=school, session=session).first()
    return {
        'grading_type': getattr(lr, 'calculation_type', 0) if lr else 0,
        'ledger_type': 1,
        'calculation_type': 'legacy',
        'assessment_source': 'exam',
    }