#!/usr/bin/env python
"""
Debug script to check panel gradesheet differences for:
result_type: 1, calc_type: legacy, grade2: 11, printtype: 1, edusession: 5, term: 1
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.db import connection
from panel.func import GradeAndGpaNonGradeTheory, GradeAndGpaNonGradePractical, get_percentage
from sms.models import (Student, StudentSession, SchoolGrade, SchoolTerm, 
                        GradeFullMarks, MarkObtained, Subject, EduSession,
                        SchoolBranch, ResultManagement, LiveResult)

def check_gradesheet(student_reg='11111481', term_id=1, session_id=5):
    """Check gradesheet calculation for a specific student."""
    
    # Get student
    student = Student.objects.get(reg_no=student_reg)
    term = SchoolTerm.objects.get(id=term_id)
    session = EduSession.objects.get(id=session_id)
    school = student.school
    
    # Get student's actual grade from StudentSession
    ss = StudentSession.objects.filter(
        student=student, session=session, status=True
    ).select_related('grade').first()
    
    if not ss:
        print(f"No StudentSession found for {student_reg} in session {session_id}")
        return
    
    grade = ss.grade
    
    print(f"Student: {student.name} ({student_reg})")
    print(f"Grade: {grade}, Term: {term}, Session: {session}")
    print(f"School: {school}")
    print("=" * 80)
    
    # Get marks
    marks = MarkObtained.objects.filter(
        student=student,
        session=session,
        school=school,
        grade=grade,
        term=term
    ).select_related('subject')
    
    print(f"Marks found: {marks.count()}")
    
    # Get full marks
    full_marks_qs = GradeFullMarks.objects.filter(
        session=session,
        school=school,
        grade=grade,
        term=term
    )
    full_marks_map = {fm.subject_id: fm for fm in full_marks_qs}
    
    # Get ResultManagement term_calculation
    try:
        result_mgmt = ResultManagement.objects.get(school_term=term)
        term_calculation = json.loads(result_mgmt.term_calculation)
        print(f"Term calculation: {term_calculation}")
    except ResultManagement.DoesNotExist:
        print("No ResultManagement found")
        return
    
    print("\n" + "=" * 80)
    print("SUBJECT-WISE DETAILS")
    print("=" * 80)
    
    for mark in marks:
        fm = full_marks_map.get(mark.subject_id)
        if not fm:
            continue
            
        th_fm = fm.th_fm
        pr_fm = fm.pr_fm
        th_pm = fm.th_pm if fm.th_pm > 0 else int(th_fm * 0.35) if th_fm > 0 else 0
        pr_pm = fm.pr_pm if fm.pr_pm > 0 else int(pr_fm * 0.40) if pr_fm > 0 else 0
        
        print(f"\n--- {mark.subject.subject} ---")
        print(f"  TH: FM={fm.th_fm}, PM={th_pm}, MO={mark.th_mo}")
        print(f"  PR: FM={fm.pr_fm}, PM={pr_pm}, MO={mark.pr_mo}")
        print(f"  Absent: {mark.is_absent}")
        
        if mark.is_absent:
            print("  Status: ABSENT")
            continue
        
        # Calculate percentages
        th_percent = (mark.th_mo * 100 / th_fm) if th_fm > 0 else 0
        pr_percent = (mark.pr_mo * 100 / pr_fm) if pr_fm > 0 else 0
        total_mo = mark.th_mo + mark.pr_mo
        total_fm = th_fm + pr_fm
        total_percent = (total_mo * 100 / total_fm) if total_fm > 0 else 0
        
        print(f"  TH: {mark.th_mo}/{th_fm} = {th_percent:.2f}%")
        print(f"  PR: {mark.pr_mo}/{pr_fm} = {pr_percent:.2f}%")
        print(f"  Total: {total_mo}/{total_fm} = {total_percent:.2f}%")
        
        # Check pass/fail
        th_pass = th_percent >= (th_pm * 100 / th_fm) if th_fm > 0 else True
        pr_pass = pr_percent >= (pr_pm * 100 / pr_fm) if pr_fm > 0 else True
        
        print(f"  TH Pass: {th_pass} (need {th_pm}/{th_fm} = {th_pm*100/th_fm:.1f}%)")
        print(f"  PR Pass: {pr_pass} (need {pr_pm}/{pr_fm} = {pr_pm*100/pr_fm:.1f}%)")
        
        # Use panel's non-graded calculation
        from panel.func import GradeAndGpaNonGradeTheory, GradeAndGpaNonGradePractical
        
        th_obj = GradeAndGpaNonGradeTheory(fm.th_fm, mark.th_mo, th_pm) if th_fm > 0 else None
        pr_obj = GradeAndGpaNonGradePractical(fm.pr_fm, mark.pr_mo, pr_pm) if pr_fm > 0 else None
        
        print(f"\n  TH Grade: {th_obj.th_grade}{th_obj.th_symbol if th_obj else '-'}")
        print(f"  TH Point: {th_obj.th_point if th_obj else 0}")
        print(f"  TH Fail: {th_obj.fail if th_obj else 0}")
        
        if pr_fm > 0:
            print(f"  PR Grade: {pr_obj.pr_grade}{pr_obj.pr_symbol if pr_obj else '-'}")
            print(f"  PR Point: {pr_obj.pr_point if pr_obj else 0}")
            print(f"  PR Fail: {pr_obj.fail if pr_obj else 0}")
        
        # Combined
        subject_failed = False
        if th_fm > 0 and th_obj and th_obj.fail:
            subject_failed = True
        if pr_fm > 0 and pr_obj and pr_obj.fail:
            subject_failed = True
            
        if subject_failed:
            final_grade = 'NG'
            final_gp = 0
        else:
            # Aggregate grade from total percentage
            from panel.func import get_grade_point
            _, _, gp = get_grade_point(total_percent)
            grade_letter, symbol, _ = get_grade_point(total_percent)
            final_grade = f"{grade_letter}{symbol}".strip()
            final_gp = gp
        
        print(f"\n  FINAL: Grade={final_grade}, GP={final_gp}")
        print(f"  Subject Failed: {subject_failed}")

def check_term_calculation(term_id=1):
    """Check term calculation weights."""
    try:
        term = SchoolTerm.objects.get(id=term_id)
        result_mgmt = ResultManagement.objects.get(school_term=term)
        calc = json.loads(result_mgmt.term_calculation)
        print(f"\nTerm Calculation for term {term_id}:")
        for k, v in calc.items():
            term_obj = SchoolTerm.objects.get(id=k)
            print(f"  Term {k} ({term_obj.term_name}): {v}%")
    except Exception as e:
        print(f"Error: {e}")

def check_live_result(school_id=1):
    """Check LiveResult configuration."""
    try:
        lr = LiveResult.objects.get(school_id=school_id)
        grade_list = json.loads(lr.grade_list)
        print(f"\nLiveResult:")
        print(f"  Term: {lr.term}")
        print(f"  Grade List: {grade_list}")
        print(f"  Status: {lr.status}")
        print(f"  Calculation Type: {lr.calculation_type}")
    except LiveResult.DoesNotExist:
        print("No LiveResult found")

if __name__ == "__main__":
    import json
    
    print("=" * 80)
    print("PANEL GRADESHEET DEBUG SCRIPT")
    print("=" * 80)
    
    # Check configurations
    check_live_result(1)
    check_term_calculation(1)
    
    # Check specific student - using correct grade from LiveResult
    check_gradesheet('11111481', 11, 1, 5)
    
    print("\n" + "=" * 80)
    print("DONE")
    print("=" * 80)