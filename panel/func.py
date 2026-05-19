from sms.models import *
from .views import *
#
#
# def detailResult(school, term, grade, student, printtype=0):
#     printtype = int(printtype)
#     this_session = EduSession.objects.get(id=2)
#     grade_subjects = Subject.objects.filter(grade=grade, branch=school, status=True)
#     fm_pm = GradeFullMarks.objects.filter(
#         session=this_session, school=school, grade=grade, term=term
#     )
#     marks_obtained = MarkObtained.objects.filter(
#         student=student, session=this_session, grade=grade, term=term
#     )
#
#     # print(marks_obtained)
#
#     mo_th = 0
#     mo_pr = 0
#     total = 0
#     gp = 0
#
#     sub_count = 1
#     total = dict()
#     credithour = 0
#     totalm = 0
#     totaltm = 0
#     totalpm = 0
#     totaltmo = 0
#     totalpmo = 0
#     position = 0
#     fail = 0
#
#     subcount = 0
#     cgpa = 0
#     mo_dict = dict()
#     for subject in grade_subjects:
#         for mo in marks_obtained:
#             if subject.id == mo.subject:
#
#                 this_subject = Subject.objects.get(id=int(mo.subject))
#                 mo_dict[subject.id] = dict()
#
#                 gfm = GradeFullMarks.objects.get(subject=this_subject, term=term)
#
#                 totaltm += gfm.th_fm
#                 totalpm += gfm.pr_fm
#                 totaltmo += mo.th_mo
#                 totalpmo += mo.pr_mo
#
#                 th_fail = False
#                 pr_fail = False
#
#                 if mo.th_mo > 0:
#                     mth = mo.th_mo
#
#                     mthg = grading(mth * 100 / gfm.th_fm)[0]
#                     mthgp = grading(mth * 100 / gfm.th_fm)[1]
#                 elif gfm.th_fm == 0:
#                     mth = 0
#                     mthg = ""
#                     mthgp = 0
#                 else:
#                     mth = 0
#                     mthg = "N"
#                     fail += 1
#                     mthgp = 0
#                     th_fail = True
#
#                 if mo.pr_mo > 0:
#                     mpr = mo.pr_mo
#                     mprg = grading(mpr * 100 / gfm.pr_fm)[0]
#                     mprgp = grading(mpr * 100 / gfm.pr_fm)[1]
#                 elif gfm.pr_fm == 0:
#                     mpr = 0
#                     mprg = ""
#                     mprgp = 0
#                     # mpr = ''
#                 else:
#                     mpr = 0
#                     mprg = "N"
#                     fail += 1
#                     mprgp = 0
#                     pr_fail = True
#
#                 totfm = gfm.th_fm + gfm.pr_fm
#                 totmo = mo.th_mo + mo.pr_mo
#                 if gfm.pr_fm != 0 and gfm.th_fm != 0:
#                     totmogp = (mthgp + mprgp) / 2
#
#                 else:
#                     totmogp = mthgp + mprgp
#
#                 cgpa += totmogp
#
#                 if totmo > 0:
#                     totmop = totmo * 100 / totfm
#                     mo_dict[subject.id]["total_mo"] = grading(totmop)[0]
#                 else:
#                     mo_dict[subject.id]["total_mo"] = "N"
#                 # print('Print Type: ', printtype)
#                 if printtype == 1:  # GRADE
#                     mo_dict[subject.id]["theory_mo"] = mthg
#                     mo_dict[subject.id]["th_fail"] = th_fail
#                     mo_dict[subject.id]["prac_mo"] = mprg
#                     mo_dict[subject.id]["pr_fail"] = pr_fail
#                     mo_dict[subject.id]["gradepoint"] = totmo
#                 else:
#                     mo_dict[subject.id]["theory_mo"] = mth
#                     mo_dict[subject.id]["th_fail"] = th_fail
#                     mo_dict[subject.id]["prac_mo"] = mpr
#                     mo_dict[subject.id]["pr_fail"] = pr_fail
#                     mo_dict[subject.id]["gradepoint"] = totmo
#
#                 sub_count += 1
#
#     # totaltm += gfm.th_fm
#     # totalpm += gfm.pr_fm
#     totalm = totaltm + totalpm
#     totalmo = totaltmo + totalpmo
#     # print('TOTAL MO', totalmo)
#     if totalmo > 0:
#         totalpercent = totalmo * 100 / totalm
#         totaltmog = grading(totaltmo * 100 / totalm)[0]
#     else:
#         totalpercent = 0
#         totaltmog = 0
#     # print('TOTAL PERCENT', totalpercent)
#
#     if totalpmo > 0:
#         totalpmog = totalpmo * 100 / totalpm
#         total["og_pr"] = grading(totalpmog)[0]
#     else:
#         totalpmog = ""
#         total["og_pr"] = totalpmog
#
#     total["credithour"] = credithour
#     total["og_th"] = totaltmog
#     total["tog"] = grading(totalpercent)[0]
#     totalgpa = grading(totalpercent)[1]
#
#     sr = {}
#
#     if printtype == 1:  # grade
#         sr["mo_th"] = totaltmog
#         if totalpmog == "":
#             sr["mo_pr"] = ""
#         else:
#             sr["mo_pr"] = grading(totalpmog)[0]
#
#         sr["total"] = totaltmog
#         sr["gp"] = totalgpa
#         sr["subjects"] = mo_dict
#     else:
#         sr["mo_th"] = totaltmo
#         sr["mo_pr"] = totalpmo
#         sr["total"] = totalmo
#         sr["gp"] = totalgpa
#         sr["subjects"] = mo_dict
#
#     return sr
#
#
# def detailResult2078old(school, term, grade, student, printtype=0):
#     printtype = int(printtype)
#     this_session = EduSession.objects.get(id=2)
#     grade_subjects = Subject.objects.filter(
#         grade=grade, branch=school, status=True
#     ).order_by("id")
#     fm_pm = GradeFullMarks.objects.filter(
#         session=this_session, school=school, grade=grade, term=term
#     )
#     marks_obtained = MarkObtained.objects.filter(
#         student=student, session=this_session, grade=grade, term=term
#     )
#
#     # print(marks_obtained)
#
#     mo_th = 0
#     mo_pr = 0
#     total = 0
#     gp = 0
#
#     sub_count = 0
#     total = dict()
#     credithour = 0
#     totalm = 0
#     totaltm = 0
#     totalpm = 0
#     totaltmo = 0
#     totalpmo = 0
#     position = 0
#     fail = 0
#     gp16count = 0
#     subcount = 0
#     cgpa = 0
#     th_fail = pr_fail = 0
#     mo_dict = dict()
#     for subject in grade_subjects:
#         sub_count += 1
#         for mo in marks_obtained:
#             if subject.id == mo.subject:
#
#                 this_subject = Subject.objects.get(id=int(mo.subject))
#                 mo_dict[subject.id] = dict()
#
#                 gfm = GradeFullMarks.objects.get(subject=this_subject, term=term)
#
#                 # totaltm += gfm.th_fm
#                 # totalpm += gfm.pr_fm
#                 # totaltmo += mo.th_mo
#                 # totalpmo += mo.pr_mo
#
#                 # th_fail = False
#                 # pr_fail = False
#
#                 # if mo.th_mo > 0:
#                 #     mth = mo.th_mo
#
#                 #     mthg = grading(mth * 100 / gfm.th_fm)[0]
#                 #     mthgp = grading(mth * 100 / gfm.th_fm)[1]
#                 # elif gfm.th_fm == 0:
#                 #     mth = 0
#                 #     mthg = ""
#                 #     mthgp = 0
#                 # else:
#                 #     mth = 0
#                 #     mthg = "N"
#                 #     fail += 1
#                 #     mthgp = 0
#                 #     th_fail = True
#
#                 # if mo.pr_mo > 0:
#                 #     mpr = mo.pr_mo
#                 #     mprg = grading(mpr * 100 / gfm.pr_fm)[0]
#                 #     mprgp = grading(mpr * 100 / gfm.pr_fm)[1]
#                 # elif gfm.pr_fm == 0:
#                 #     mpr = 0
#                 #     mprg = ""
#                 #     mprgp = 0
#                 #     # mpr = ''
#                 # else:
#                 #     mpr = 0
#                 #     mprg = "N"
#                 #     fail += 1
#                 #     mprgp = 0
#                 #     pr_fail = True
#
#                 # total_fm = gfm.th_fm + gfm.pr_fm
#                 # total_mo = mo.th_mo + mo.pr_mo
#
#                 # # if gfm.pr_fm != 0 and gfm.th_fm !=0:
#                 # #     totmogp = (mthgp + mprgp)/2
#
#                 # # else:
#                 # #     totmogp = (mthgp + mprgp)
#
#                 # if total_mo > 0:
#                 #     totmop = total_mo * 100 / total_fm
#                 #     try:
#                 #         mo_dict[sub_count]["total_mo"] = grading(totmop)[0]
#                 #     except:
#                 #         print(
#                 #             "%s - %s at line: %s"
#                 #             % (
#                 #                 sys.exc_info()[0],
#                 #                 sys.exc_info()[1],
#                 #                 sys.exc_info()[2].tb_lineno,
#                 #             )
#                 #         )
#
#                 #     totmogp = grading(totmop)[1]
#                 #     totalmog = grading(totmop)[0]
#                 #     if subject.heavy_weight:
#                 #         if int(totmogp) < 1.6:
#                 #             print("TOTMOGP: ", totmogp)
#                 #             gp16count += 1
#                 # else:
#                 #     try:
#                 #         mo_dict[sub_count]["total_mo"] = "N"
#                 #     except:
#                 #         print(
#                 #             "%s - %s at line: %s"
#                 #             % (
#                 #                 sys.exc_info()[0],
#                 #                 sys.exc_info()[1],
#                 #                 sys.exc_info()[2].tb_lineno,
#                 #             )
#                 #         )
#                 #     totmogp = 0
#
#                 # cgpa += totmogp
#
#                 # # if totmo > 0:
#                 # #     totmop = totmo*100/totfm
#                 # #     mo_dict[subject.id]['total_mo'] = grading(totmop)[0]
#                 # # else:
#                 # #     mo_dict[subject.id]['total_mo'] = 'N'
#                 # # print('Print Type: ', printtype)
#
#                 # # cgpa += totmogp
#
#                 # mthg = grading(mth)[0]
#                 # if gfm.pr_fm > 0:
#                 #     mprg = grading(mpr)[0]
#                 # else:
#                 #     mprg = ""
#                 #  ==========================================
#                 # New Code
#
#                 subject_marks_obtained = mo
#
#                 if gfm.th_fm > 0:
#                     if gfm.pr_fm > 0:
#                         # Both Theory and practical Marks
#                         mth = subject_marks_obtained.th_mo * 100 / gfm.th_fm
#                         mpr = subject_marks_obtained.pr_mo * 100 / gfm.pr_fm
#                     else:
#                         # Only theory Marks
#                         mth = subject_marks_obtained.th_mo * 100 / gfm.th_fm
#                         mpr = 0
#                 # elif gfm.pr_fm > 0:
#                 #     # Only Practical Marks
#                 #     mpr = subject_marks_obtained.th_mo * 100 / gfm.pr_fm
#                 #     mth = 0
#
#                 total_fm = gfm.th_fm + gfm.pr_fm
#                 total_mo = subject_marks_obtained.th_mo + subject_marks_obtained.pr_mo
#
#                 if total_mo > 0:
#                     totmop = total_mo * 100 / total_fm
#                     mo_dict[subject.id]["total_mo"] = grading(totmop)[0]
#                     totmogp = grading(totmop)[1]
#                     totalmog = grading(totmop)[0]
#                     if subject.heavy_weight:
#                         if int(totmogp) < 1.6:
#                             print("TOTMOGP: ", totmogp)
#                             gp16count += 1
#                 else:
#                     mo_dict[subject.id]["total_mo"] = "N"
#                     totmogp = 0
#                     gp16count += 1
#
#                 cgpa += totmogp
#
#                 mthg = grading(mth)[0]
#                 if gfm.pr_fm > 0:
#                     mprg = grading(mpr)[0]
#                 else:
#                     mprg = ""
#
#                 # New Code Ends
#                 # =================================
#
#                 if printtype == 1:  # GRADE
#                     mo_dict[subject.id]["theory_mo"] = mthg
#                     mo_dict[subject.id]["th_fail"] = th_fail
#                     mo_dict[subject.id]["prac_mo"] = mprg
#                     mo_dict[subject.id]["pr_fail"] = pr_fail
#                     mo_dict[subject.id]["gradepoint"] = totmogp
#                 else:
#                     mo_dict[subject.id]["theory_mo"] = mth
#                     mo_dict[subject.id]["th_fail"] = th_fail
#                     mo_dict[subject.id]["prac_mo"] = mpr
#                     mo_dict[subject.id]["pr_fail"] = pr_fail
#                     mo_dict[subject.id]["gradepoint"] = totmogp
#
#     try:
#         cgpa = round(cgpa / sub_count, 2)
#     except ZeroDivisionError as error:
#         cgpa = "Value is 0"
#
#     # eeeeeeeeeeeeeeeeeeeeeeee
#
#     totaltm += gfm.th_fm
#     totalpm += gfm.pr_fm
#     totalm = totaltm + totalpm
#     totalmo = totaltmo + totalpmo
#     # print('TOTAL MO', totalmo)
#     if totalmo > 0:
#         totalpercent = totalmo * 100 / totalm
#         totaltmog = grading(totaltmo * 100 / totalm)[0]
#     else:
#         totalpercent = 0
#         totaltmog = 0
#     # print('TOTAL PERCENT', totalpercent)
#
#     if totalpmo > 0:
#         totalpmog = totalpmo * 100 / totalpm
#         total["og_pr"] = grading(totalpmog)[0]
#     else:
#         totalpmog = ""
#         total["og_pr"] = totalpmog
#
#     total["credithour"] = credithour
#     total["og_th"] = totaltmog
#     total["tog"] = grading(totalpercent)[0]
#     totalgpa = grading(totalpercent)[1]
#
#     #  eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
#
#     sr = {}
#     totalgpa = cgpa
#     totaltmog = gpFromGPA(cgpa)
#     totalmo = totalmog
#
#     if printtype == 1:  # grade
#         sr["mo_th"] = totaltmog
#         if totalpmog == "":
#             sr["mo_pr"] = ""
#         else:
#             sr["mo_pr"] = grading(totalpmog)[0]
#
#         sr["total"] = totaltmog
#         sr["gp"] = totalgpa
#         sr["subjects"] = mo_dict
#     else:
#         sr["mo_th"] = totaltmo
#         sr["mo_pr"] = totalpmo
#         sr["total"] = totalmo
#         sr["gp"] = totalgpa
#         sr["subjects"] = mo_dict
#
#     return sr
#
#
# def grading(percent):
#     if percent > 100:
#         return ("SOMETHING WRONG", 4.0, "SOMETHING WRONG")
#     if 90 <= percent <= 100:
#         return ("A+", 4.0, "Excellent")
#     elif 80 <= percent < 90:
#         return ("A", 3.6, "Very Nice")
#         # return(result)
#     elif 70 <= percent < 80:
#         return ("B+", 3.2, "Nice")
#         # return(result)
#     elif 60 <= percent < 70:
#         return ("B", 2.8, "Good")
#         # return(result)
#     elif 50 <= percent < 60:
#         return ("C+", 2.4, "Study More")
#         # return(result)
#     elif 40 <= percent < 50:
#         return ("C", 2.0, "Pay Attention")
#         # return(result)
#     elif 30 <= percent < 40:
#         return ("D+", 1.6, "Labour Hard")
#     elif 20 <= percent < 40:
#         return ("D", 1.2, "Labour Hard")
#         # return(result)
#     elif percent >= 1 and percent < 20:
#         return ("E", 0.8, "Labour Hardrder")
#         # return(result)
#     elif percent == 0:
#         return ("N", 0, "Try Next Time")
#         # return(result)
#
#
# def remarks(percent):
#     if percent > 4:
#         return ("SOMETHING WRONG", 4.0)
#     if percent == 4:
#         return "Excellent"
#     elif 3.6 <= percent < 4:
#         return "Very Nice"
#         # return(result)
#     elif 3.2 <= percent < 3.6:
#         return "Nice"
#         # return(result)
#     elif 2.8 <= percent < 3.2:
#         return "Good"
#         # return(result)
#     elif 2.4 <= percent < 2.8:
#         return "Study More"
#         # return(result)
#     elif 2.0 <= percent < 2.40:
#         return "Pay Attention"
#         # return(result)
#     elif 1.6 <= percent < 2.0:
#         return "Labour Hard"
#     elif 1.2 <= percent < 1.6:
#         return "Labour Hard"
#         # return(result)
#     elif percent >= 0.1 and percent < 1.2:
#         return "Labour Hardrder"
#         # return(result)
#     elif percent == 0:
#         return "Try Next Time"
#         # return(result)
#
#
# def gpFromGPA(gpa):
#     if gpa > 4:
#         return ("SOMETHING WRONG", 4.0)
#     if gpa == 4:
#         return "A+"
#     elif 3.6 <= gpa < 4:
#         return "A"
#         # return(result)
#     elif 3.2 <= gpa < 3.6:
#         return "B+"
#         # return(result)
#     elif 2.8 <= gpa < 3.2:
#         return "B"
#         # return(result)
#     elif 2.4 <= gpa < 2.8:
#         return "C+"
#         # return(result)
#     elif 2.0 <= gpa < 2.40:
#         return "C"
#         # return(result)
#     elif 1.6 <= gpa < 2.0:
#         return "D+"
#     elif 1.2 <= gpa < 1.6:
#         return "D"
#         # return(result)
#     elif gpa >= 0.1 and gpa < 1.2:
#         return "E"
#         # return(result)
#     elif gpa == 0:
#         return "N"
#         # return(result)
#
#
# @login_required
# def printGradesheetByGrade(request, grade):
#     user = request.user
#     try:
#         branchuser = BranchUser.objects.get(user=user)
#     except BranchUser.DoesNotExist:
#         return HttpResponse(
#             'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
#         )
#
#     # this_term = V2TerminalExams.objects.get(school=school, branch=branch, value=term)
#     grade = int(grade)
#     resultstatus = LiveResult.objects.get(school=branchuser.school.id)
#
#     count = SchoolGrade.objects.filter(id=grade).count()
#     if count == 1:
#         reqGrade = SchoolGrade.objects.get(id=grade)
#         if reqGrade.school.id == branchuser.school.id:
#             print("YES", reqGrade, reqGrade.id)
#             students = Student.objects.filter(grade=grade)
#
#             resultstatus = LiveResult.objects.get(school=branchuser.school.id)
#             gradelist = json.loads(resultstatus.gradelist)
#             term = resultstatus.term
#             this_term = SchoolTerm.objects.get(id=term)
#             print(this_term)
#
#             as_dict = dict()
#
#             total_std = Student.objects.filter(
#                 school=branchuser.school.id, grade=reqGrade, status=1
#             ).count()
#
#             grade_subjects = Subject.objects.filter(
#                 grade=reqGrade.id, branch=branchuser.school.id, status=True
#             )
#             # Subject.objects.filter(grade=reqGrade.id, status=1)
#
#             for subject in grade_subjects:
#                 print(reqGrade.id, subject)
#
#             for student in students:
#                 if int(student.reg_no) >= 11110350:
#                     break
#                 as_dict[student.reg_no] = dict()
#                 as_dict[student.reg_no]["std_name"] = student.name
#                 as_dict[student.reg_no]["grade"] = student.grade
#                 as_dict[student.reg_no]["section"] = student.section
#                 as_dict[student.reg_no]["mo_dict"] = dict()
#                 grade_subjects = Subject.objects.filter(
#                     grade=student.grade, branch=student.school, status=True
#                 )
#                 total_std = Student.objects.filter(
#                     school=student.school, grade=student.grade, status=1
#                 ).count()
#
#                 marks_obtained = MarkObtained.objects.filter(
#                     student=student.reg_no,
#                     session=this_session,
#                     grade=student.grade.id,
#                     term=term,
#                 )
#                 sub_count = 1
#                 total = dict()
#                 credithour = 0
#                 totalm = 0
#                 totaltm = 0
#                 totalpm = 0
#                 totaltmo = 0
#                 totalpmo = 0
#                 position = 0
#                 fail = 0
#                 totalstudent = Student.objects.filter(
#                     grade=student.grade, section=student.section
#                 ).count()
#                 # for calculating rank
#
#                 req_rank = calculaterank(
#                     school=student.school.id,
#                     session=this_session,
#                     grade=int(student.grade.id),
#                     term=term,
#                     section=student.section,
#                     regno=student.reg_no,
#                 )
#
#                 # print(req_rank)
#
#                 ## rank calculation ends
#
#                 # print(mod)
#                 subcount = 0
#                 cgpa = 0
#                 for subject in grade_subjects:
#                     for mo in marks_obtained:
#                         if subject.id == mo.subject:
#                             subcount += 1
#                             as_dict[student.reg_no]["mo_dict"][sub_count] = dict()
#                             this_subject = Subject.objects.get(id=int(mo.subject))
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "subject_name"
#                             ] = this_subject
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "theory_fm"
#                             ] = 4
#
#                             credithour += 4
#
#                             gfm = GradeFullMarks.objects.get(
#                                 subject=this_subject, term=this_term
#                             )
#
#                             totaltm += gfm.th_fm
#                             totalpm += gfm.pr_fm
#                             totaltmo += mo.th_mo
#                             totalpmo += mo.pr_mo
#
#                             if mo.th_mo > 0:
#                                 mth = mo.th_mo * 100 / gfm.th_fm
#                                 mthg = grading(mth)[0]
#                                 mthgp = grading(mth)[1]
#                             elif gfm.th_fm == 0:
#                                 mthg = ""
#                                 mthgp = 0
#                             else:
#                                 mthg = "N"
#                                 fail += 1
#                                 mthgp = 0
#
#                             if mo.pr_mo > 0:
#                                 mpr = mo.pr_mo * 100 / gfm.pr_fm
#                                 mprg = grading(mpr)[0]
#                                 mprgp = grading(mpr)[1]
#                             elif gfm.pr_fm == 0:
#                                 mprg = ""
#                                 mprgp = 0
#                             else:
#                                 mprg = "N"
#                                 fail += 1
#                                 mprgp = 0
#
#                             totfm = gfm.th_fm + gfm.pr_fm
#                             totmo = mo.th_mo + mo.pr_mo
#                             if gfm.pr_fm != 0 and gfm.th_fm != 0:
#                                 totmogp = (mthgp + mprgp) / 2
#                                 totmogp = grading(
#                                     (mo.th_mo + mo.pr_mo)
#                                     * 100
#                                     / (gfm.th_fm + gfm.pr_fm)
#                                 )[1]
#
#                             else:
#                                 totmogp = mthgp + mprgp
#
#                             cgpa += totmogp
#
#                             if totmo > 0:
#                                 totmop = totmo * 100 / totfm
#                                 as_dict[student.reg_no]["mo_dict"][sub_count][
#                                     "total_mo"
#                                 ] = grading(totmop)[0]
#                             else:
#                                 as_dict[student.reg_no]["mo_dict"][sub_count][
#                                     "total_mo"
#                                 ] = "N"
#
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "theory_mo"
#                             ] = mthg
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "prac_mo"
#                             ] = mprg
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "gradepoint"
#                             ] = totmogp
#
#                             sub_count += 1
#
#                 # cgpa = grading(totmo*100/totfm)[1]
#                 if cgpa > 0:
#                     cgpa = round(cgpa / subcount, 2)
#                 else:
#                     cgpa = 0
#
#                 as_dict[student.reg_no]["cgpa"] = cgpa
#                 as_dict[student.reg_no]["remarks"] = remarks(cgpa)
#
#                 totaltm += gfm.th_fm
#                 totalpm += gfm.pr_fm
#                 totalm = totaltm + totalpm
#                 totalmo = totaltmo + totalpmo
#                 totalg = totalmo * 100 / totalm
#
#                 totaltmog = totaltmo * 100 / totaltm
#
#                 if totalpmo > 0:
#                     totalpmog = totalpmo * 100 / totalpm
#                     total["og_pr"] = grading(totalpmog)[0]
#                 else:
#                     totalpmog = ""
#                     total["og_pr"] = totalpmog
#
#                 total["credithour"] = credithour
#                 total["og_th"] = grading(totaltmog)[0]
#                 total["tog"] = grading(totalg)[0]
#                 totalgpa = grading(totalg)[1]
#                 # as_dict[student.reg_no]['mo_dict'] = dict()
#                 as_dict[student.reg_no]["additional_td"] = 12 - grade_subjects.count()
#
#                 req_rank = calculaterank(
#                     school=student.school.id,
#                     session=this_session,
#                     grade=int(student.grade.id),
#                     term=term,
#                     section=student.section,
#                     regno=student.reg_no,
#                 )
#                 totalstudent = Student.objects.filter(
#                     grade=student.grade, section=student.section
#                 ).count()
#
#                 as_dict[student.reg_no]["rank"] = req_rank
#                 as_dict[student.reg_no]["totalstudent"] = totalstudent
#                 # #as_dict[student.reg_no][''] =
#                 # print(student, student.reg_no)
#
#                 # # as_dict[student.reg_no]['mo_dict']['name'] = 'Test'
#
#                 # # print(grade_subjects)
#
#                 # marks_obtained = MarkObtained.objects.filter(student=student.reg_no, session=1, grade=93, term=31)
#
#                 # for marks in marks_obtained:
#                 #     print(marks)
#                 # sub_count = 1
#                 # total = dict()
#                 # credithour = 0
#                 # totalm = 0
#                 # totaltm = 0
#                 # totalpm = 0
#                 # totaltmo = 0
#                 # totalpmo = 0
#                 # position = 0
#                 # fail = 0
#                 # totalstudent = Student.objects.filter(grade=student.grade , section=student.section).count()
#                 # # # for calculating rank
#
#                 # # req_rank = calculaterank(school=student.school.id, session=this_session, grade= int(student.grade.id), term=term, section=student.section, regno=student.reg_no)
#
#                 # # # print(req_rank)
#
#                 # # ## rank calculation ends
#
#                 # # # print(mod)
#                 # subcount = 0
#                 # cgpa = 0
#                 # for subject in grade_subjects:
#                 #     print(subject, subcount)
#                 #     for mo in marks_obtained:
#                 #         if subject.id == mo.subject:
#                 #             subcount+=1
#                 #             print(subcount)
#                 #             as_dict[student.reg_no]['mo_dict'][sub_count] = dict()
#                 #             this_subject = Subject.objects.get(id=int(mo.subject))
#                 #             as_dict[student.reg_no]['mo_dict'][sub_count]['subject_name'] = this_subject
#                 #             as_dict[student.reg_no]['mo_dict'][sub_count]['theory_fm'] = 4
#
#                 #             credithour += 4
#
#                 #             gfm = GradeFullMarks.objects.get(subject=this_subject, term=this_term)
#
#                 #             totaltm += gfm.th_fm
#                 #             totalpm += gfm.pr_fm
#                 #             totaltmo += mo.th_mo
#                 #             totalpmo += mo.pr_mo
#
#                 #             if mo.th_mo > 0:
#                 #                 mth = mo.th_mo*100/gfm.th_fm
#                 #                 mthg = grading(mth)[0]
#                 #                 mthgp = grading(mth)[1]
#                 #             elif gfm.th_fm == 0:
#                 #                 mthg = ''
#                 #                 mthgp = 0
#                 #             else:
#                 #                 mthg = 'N'
#                 #                 fail +=1
#                 #                 mthgp = 0
#
#                 #             if mo.pr_mo > 0:
#                 #                 mpr = mo.pr_mo*100/gfm.pr_fm
#                 #                 mprg = grading(mpr)[0]
#                 #                 mprgp = grading(mpr)[1]
#                 #             elif gfm.pr_fm == 0:
#                 #                 mprg = ''
#                 #                 mprgp = 0
#                 #             else:
#                 #                 mprg = 'N'
#                 #                 fail +=1
#                 #                 mprgp = 0
#
#                 #             totfm = gfm.th_fm + gfm.pr_fm
#                 #             totmo = mo.th_mo + mo.pr_mo
#                 #             if gfm.pr_fm != 0 and gfm.th_fm !=0:
#                 #                 totmogp = round((mthgp + mprgp)/2, 2)
#                 #                 totmogp = grading((mo.th_mo+mo.pr_mo)*100/(gfm.th_fm+gfm.pr_fm))[1]
#
#                 #             else:
#                 #                 totmogp = (mthgp + mprgp)
#
#                 #             cgpa += totmogp
#
#                 #             if totmo > 0:
#                 #                 totmop = totmo*100/totfm
#                 #                 as_dict[student.reg_no]['mo_dict'][sub_count]['total_mo'] = totmo #grading(totmop)[0]
#                 #             else:
#                 #                  as_dict[student.reg_no]['mo_dict'][sub_count]['total_mo'] = 'N'
#
#                 #             as_dict[student.reg_no]['mo_dict'][sub_count]['theory_mo'] = mthg
#                 #             as_dict[student.reg_no]['mo_dict'][sub_count]['prac_mo'] = mprg
#                 #             as_dict[student.reg_no]['mo_dict'][sub_count]['gradepoint'] = totmogp
#
#                 #             # cgpa = grading(totmo*100/totfm)[1]
#                 #             cgpa = round(cgpa/subcount, 2)
#
#                 #             totaltm += gfm.th_fm
#                 #             totalpm += gfm.pr_fm
#                 #             totalm = totaltm + totalpm
#                 #             totalmo = totaltmo + totalpmo
#                 #             totalg = totalmo*100/totalm
#
#                 #             totaltmog = totaltmo*100/totaltm
#
#                 #             if totalpmo > 0:
#                 #                 totalpmog = totalpmo*100/totalpm
#                 #                 total['og_pr'] = grading(totalpmog)[0]
#                 #             else:
#                 #                 totalpmog = ''
#                 #                 total['og_pr'] = totalpmog
#
#                 #             total['credithour'] = credithour
#                 #             total['og_th'] = grading(totaltmog)[0]
#                 #             total['tog'] = grading(totalg)[0]
#                 #             totalgpa = grading(totalg)[1]
#                 #             # total[''] =
#
#                 #             as_dict[student.reg_no]['mo_dict'][sub_count]['gpa'] = totalgpa
#
#                 #             sub_count +=1
#                 #             # as_dict[student.reg_no]['mo_dict'][sub_count]['gpa'] = totalgpa
#
#                 # ###### as_dict[student.reg_no]['cgpa'] = cgpa
#
#                 # # context = {'year': this_year, 'term':this_term, 'student': student, 'mo_dict': mo_dict, 'total': total, 'totalgpa': totalgpa, 'totalstudent': totalstudent, 'fail': fail, 'position': position, 'req_rank': req_rank, 'cgpa':cgpa }
#
#                 #     # print('one', mo_dict)
#             context = {"year": "2076", "this_term": this_term, "as_dict": as_dict}
#             return render(request, "panel/result3.html", context)
#         else:
#             print("NO")
#
#     return HttpResponse("Hi")
#     # regno = request.POST.get('regno')
#     # code =  request.POST.get('scode')
#
#     # if Student.objects.filter(reg_no=regno).count() == 1:
#     #     student= Student.objects.get(reg_no=int(regno))
#     #     if student.pin_code != int(code):
#     #         context = { 'message': 'Sorry the security code of the student did not match.'}
#     #         return render(request, 'panel/resultform.html',context)
#     #     else:
#     #         resultstatus = LiveResult.objects.get(school=student.school)
#     #         gradelist = json.loads(resultstatus.gradelist)
#     #         term = resultstatus.term
#     #         this_term = SchoolTerm.objects.get(id=term)
#     #         if student.grade.id not in gradelist:
#     #             message = 'Sorry the result of Grade '+student.grade.grade_name+' has not been published yet. For more information please contact on School.'
#     #             context = { 'message': message}
#     #             return render(request, 'panel/resultform.html',context)
#     # else:
#     #     context = { 'message': 'Sorry student with the registration number could not be found.'}
#     #     return render(request, 'panel/resultform.html',context)
#
#     # # sc
#     # mo_dict = dict()
#     # grade_subjects = Subject.objects.filter(grade=student.grade, branch=student.school, status=True)
#     # total_std = Student.objects.filter(school=student.school, grade=student.grade, status=1).count()
#
#     # marks_obtained = MarkObtained.objects.filter(student=student.reg_no, session=this_session, grade=student.grade.id, term=term)
#     # sub_count = 1
#     # total = dict()
#     # credithour = 0
#     # totalm = 0
#     # totaltm = 0
#     # totalpm = 0
#     # totaltmo = 0
#     # totalpmo = 0
#     # position = 0
#     # fail = 0
#     # totalstudent = Student.objects.filter(grade=student.grade , section=student.section).count()
#     # # for calculating rank
#
#     # req_rank = calculaterank(school=student.school.id, session=this_session, grade= int(student.grade.id), term=term, section=student.section, regno=student.reg_no)
#
#     # # print(req_rank)
#
#     # ## rank calculation ends
#
#     # # print(mod)
#     # subcount = 0
#     # cgpa = 0
#     # for subject in grade_subjects:
#     #     for mo in marks_obtained:
#     #         if subject.id == mo.subject:
#     #             subcount+=1
#     #             print(subcount)
#     #             mo_dict[sub_count] = dict()
#     #             this_subject = Subject.objects.get(id=int(mo.subject))
#     #             mo_dict[sub_count]['subject_name'] = this_subject
#     #             mo_dict[sub_count]['theory_fm'] = 4
#
#     #             credithour += 4
#
#     #             gfm = GradeFullMarks.objects.get(subject=this_subject, term=this_term)
#
#     #             totaltm += gfm.th_fm
#     #             totalpm += gfm.pr_fm
#     #             totaltmo += mo.th_mo
#     #             totalpmo += mo.pr_mo
#
#     #             if mo.th_mo > 0:
#     #                 mth = mo.th_mo*100/gfm.th_fm
#     #                 mthg = grading(mth)[0]
#     #                 mthgp = grading(mth)[1]
#     #             elif gfm.th_fm == 0:
#     #                 mthg = ''
#     #                 mthgp = 0
#     #             else:
#     #                 mthg = 'N'
#     #                 fail +=1
#     #                 mthgp = 0
#
#     #             if mo.pr_mo > 0:
#     #                 mpr = mo.pr_mo*100/gfm.pr_fm
#     #                 mprg = grading(mpr)[0]
#     #                 mprgp = grading(mpr)[1]
#     #             elif gfm.pr_fm == 0:
#     #                 mprg = ''
#     #                 mprgp = 0
#     #             else:
#     #                 mprg = 'N'
#     #                 fail +=1
#     #                 mprgp = 0
#
#     #             totfm = gfm.th_fm + gfm.pr_fm
#     #             totmo = mo.th_mo + mo.pr_mo
#     #             if gfm.pr_fm != 0 and gfm.th_fm !=0:
#     #                 totmogp = round((mthgp + mprgp)/2, 2)
#     #                 totmogp = grading((mo.th_mo+mo.pr_mo)*100/(gfm.th_fm+gfm.pr_fm))[1]
#
#     #             else:
#     #                 totmogp = (mthgp + mprgp)
#
#     #             cgpa += totmogp
#
#     #             if totmo > 0:
#     #                 totmop = totmo*100/totfm
#     #                 mo_dict[sub_count]['total_mo'] = grading(totmop)[0]
#     #             else:
#     #                 mo_dict[sub_count]['total_mo'] = 'N'
#
#     #             mo_dict[sub_count]['theory_mo'] = mthg
#     #             mo_dict[sub_count]['prac_mo'] = mprg
#     #             mo_dict[sub_count]['gradepoint'] = totmogp
#
#     #             sub_count +=1
#
#     # # cgpa = grading(totmo*100/totfm)[1]
#     # cgpa = round(cgpa/subcount, 2)
#
#     # totaltm += gfm.th_fm
#     # totalpm += gfm.pr_fm
#     # totalm = totaltm + totalpm
#     # totalmo = totaltmo + totalpmo
#     # totalg = totalmo*100/totalm
#
#     # totaltmog = totaltmo*100/totaltm
#
#     # if totalpmo > 0:
#     #     totalpmog = totalpmo*100/totalpm
#     #     total['og_pr'] = grading(totalpmog)[0]
#     # else:
#     #     totalpmog = ''
#     #     total['og_pr'] = totalpmog
#
#     # total['credithour'] = credithour
#     # total['og_th'] = grading(totaltmog)[0]
#     # total['tog'] = grading(totalg)[0]
#     # totalgpa = grading(totalg)[1]
#     # # total[''] =
#
#     # context = {'year': this_year, 'term':this_term, 'student': student, 'mo_dict': mo_dict, 'total': total, 'totalgpa': totalgpa, 'totalstudent': totalstudent, 'fail': fail, 'position': position, 'req_rank': req_rank, 'cgpa':cgpa }
#     # return render(request, 'panel/result3.html', context)
#
#     # # return HttpResponse('Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.')
#
#
# def calculaterank(school, session, grade, term, section=None, regno=None):
#     print("calculating rank")
#     if section:
#         student_ko_list = Student.objects.filter(
#             school=school, grade=grade, section=section, status=True
#         )
#     else:
#         student_ko_list = Student.objects.filter(
#             school=school, grade=grade, status=True
#         )
#     std_list = dict()
#     gfm = GradeFullMarks.objects.filter(
#         school=school, session=this_session, grade=grade, term=term
#     )
#     gsubjects = Subject.objects.filter(branch=school, grade=grade, status=True)
#     glist = []
#     for items in gsubjects:
#         glist.append(items.id)
#     # print(gsubjects, glist)
#     for stdl in student_ko_list:
#         # print(stdl)
#         totm = 0
#         fail = 0
#         students_marks = MarkObtained.objects.filter(
#             school=school,
#             session=this_session,
#             grade=grade,
#             term=term,
#             student=stdl.reg_no,
#         )
#         if students_marks.count() == 0:
#             fail += 100
#         for marks in students_marks:
#             for gs in gfm:
#                 if gs.subject.id == marks.subject and gs.subject.id in glist:
#
#                     total_marks_obtained = marks.th_mo + marks.pr_mo
#                     total_full_marks = gs.th_fm + gs.pr_fm
#
#                     tmop = total_marks_obtained * 100 / total_full_marks
#
#                     totmogp = grading(tmop)[1]
#                     t_subject = Subject.objects.get(id=gs.subject.id)
#
#                     # if t_subject.heavy_weight:
#                     #     if int(totmogp) < 1.6:
#                     #         fail += 1
#                     if tmop > 0:
#                         if gs.subject.heavy_weight:
#                             if totmogp <= 1.6:
#                                 fail += 1
#                     else:
#                         fail += 1
#
#                     totm += total_marks_obtained
#
#                     # Commented on May 15 2021
#
#                     # if gs.th_fm > 0 and gs.pr_fm > 0:
#                     #     if gs.th_pm <= marks.th_mo and gs.pr_pm <= marks.pr_mo:
#                     #         totm += marks.th_mo + marks.pr_mo
#                     #         # print('Pass ', gs.subject, gs.th_pm, marks.th_mo, 'Practical', gs.pr_pm, marks.pr_mo)
#                     #     else:
#                     #         totm += marks.th_mo + marks.pr_mo
#                     #         fail += 1
#                     #         # print('Fail ', gs.subject, gs.th_pm, marks.th_mo, 'Practical', gs.pr_pm, marks.pr_mo)
#                     # elif gs.th_fm > 0 and gs.pr_fm == 0:
#                     #     if gs.th_pm <= marks.th_mo:
#                     #         # print('Pass ', gs.subject, gs.th_pm, marks.th_mo, 'Practical', gs.pr_pm, marks.pr_mo)
#                     #         totm += marks.th_mo
#                     #     else:
#                     #         totm += marks.th_mo
#                     #         fail += 1
#
#                     # Commented lines end
#
#                     # print('Fail ', gs.subject, gs.th_pm, marks.th_mo, 'Practical', gs.pr_pm, marks.pr_mo)
#             # print(stdl.reg_no, totm)
#
#         if fail == 0:
#             std_list[stdl.reg_no] = totm
#             # print(stdl.reg_no, ' pass')
#         else:
#             print(stdl.reg_no, " fail")
#
#         # print(totm)
#
#     # print(std_list)
#     # rank_no = 1
#     # for key, value in sorted(mydict.iteritems(), key=lambda (k,v): (v,k)):
#     # print "%s: %s" % (key, value)
#
#     # for key, value in sorted(std_list.iteritems(), key=lambda (k,v): (v,k)):
#     # print "%s: %s" % (key, value)
#     # sorted_d = [(k,v) for k,v in std_list.items()]
#
#     sorted_d = sorted(std_list.items(), key=lambda x: x[1], reverse=True)
#     # print(sorted_d)
#     # print("Rank Calculation Done")
#     # # print(sorted_d)
#     # print(type(sorted_d))
#     # for key, value in sorted_d.items():
#     #     print(key, value)
#     # print('Shorted D')
#     # print(sorted_d)
#
#     high_mark = 0
#     stat_rank = 0
#     sorted_rank = []
#     std_dict = dict()
#     for calc in sorted_d:
#         if calc[1] == high_mark:
#             high_mark = calc[1]
#             reg_no = calc[0]
#             # print(calc[0],calc[1], stat_rank)
#             # sorted_rank.append((calc[0],calc[1], stat_rank))
#             std_dict[reg_no] = stat_rank
#         else:
#             stat_rank += 1
#             high_mark = calc[1]
#             reg_no = calc[0]
#             # print(calc[0],calc[1], stat_rank)
#             # sorted_rank.append((calc[0],calc[1], stat_rank))
#             std_dict[reg_no] = stat_rank
#
#     print(std_dict)
#
#     if regno:
#         if regno in std_dict:
#             # print(regno)
#             # print(std_dict[regno])
#             return std_dict[regno]
#         else:
#             return "-"
#     else:
#         return std_dict
#
#
# def printGradesheetTestPercent(request, grade):
#     user = request.user
#     try:
#         branchuser = BranchUser.objects.get(user=user)
#     except BranchUser.DoesNotExist:
#         return HttpResponse(
#             'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
#         )
#
#     # this_term = V2TerminalExams.objects.get(school=school, branch=branch, value=term)
#     grade = int(grade)
#     resultstatus = LiveResult.objects.get(school=branchuser.school.id)
#
#     count = SchoolGrade.objects.filter(id=grade).count()
#     if count == 1:
#         reqGrade = SchoolGrade.objects.get(id=grade)
#         if reqGrade.school.id == branchuser.school.id:
#             print("YES", reqGrade, reqGrade.id)
#             students = Student.objects.filter(grade=grade)
#
#             resultstatus = LiveResult.objects.get(school=branchuser.school.id)
#             gradelist = json.loads(resultstatus.gradelist)
#             term = resultstatus.term
#             this_term = SchoolTerm.objects.get(id=term)
#             print("Term", this_term.id, this_term.term_name)
#
#             try:
#                 thepost = ResultManagement.objects.get(school_term=int(this_term.id))
#             except ResultManagement.DoesNotExist:
#                 thepost = None
#
#                 return HttpResponse(
#                     "Sorry Result Management not found for the required term"
#                 )
#
#             mark_ratio = json.loads(thepost.term_calculation)
#             print(mark_ratio)
#             req_term_count = 1
#             req_terms = []
#
#             # for key, value in mark_ratio.items():
#             #     req_terms[req_term_count] = key
#             #     req_term_count += 1
#
#             as_dict = dict()
#
#             total_std = Student.objects.filter(
#                 school=branchuser.school.id, grade=reqGrade, status=1
#             ).count()
#
#             grade_subjects = Subject.objects.filter(
#                 grade=reqGrade.id, branch=branchuser.school.id, status=True
#             )
#             # Subject.objects.filter(grade=reqGrade.id, status=1)
#
#             # for subject in grade_subjects:
#             #     print (reqGrade.id, subject)
#
#             for student in students:
#                 if int(student.reg_no) >= 11110348:
#                     break
#                 as_dict[student.reg_no] = dict()
#                 as_dict[student.reg_no]["std_name"] = student.name
#                 as_dict[student.reg_no]["grade"] = student.grade
#                 as_dict[student.reg_no]["section"] = student.section
#                 as_dict[student.reg_no]["mo_dict"] = dict()
#                 as_dict[student.reg_no]["mo_dict2"] = dict()
#                 grade_subjects = Subject.objects.filter(
#                     grade=student.grade, branch=student.school, status=True
#                 )
#
#                 # ResultManagement.objects.ge
#                 et_sub_count = 0
#                 for subject in grade_subjects:
#                     # subcount+=1
#                     as_dict[student.reg_no]["mo_dict"][subject.id] = dict()
#                     as_dict[student.reg_no]["mo_dict2"][subject.id] = dict()
#                     as_dict[student.reg_no]["mo_dict2"][subject.id]["finalgrade"] = 0
#                     as_dict[student.reg_no]["mo_dict2"][subject.id]["gradepoint"] = 0
#
#                 for key, value in mark_ratio.items():
#                     exam_term = SchoolTerm.objects.get(school=student.school, id=key)
#                     print(exam_term)
#                     print("-------")
#
#                     et_sub_count += 1
#                     tot_grade_point = 0
#
#                     et_marks_obtained = MarkObtained.objects.filter(
#                         student=student.reg_no,
#                         session=this_session,
#                         grade=student.grade.id,
#                         term=exam_term.id,
#                     )
#                     print(et_marks_obtained)
#                     for et_items in et_marks_obtained:
#                         print(et_items.subject, et_items.th_mo, et_items.pr_mo)
#                         as_dict[student.reg_no]["mo_dict"][et_items.subject][
#                             et_sub_count
#                         ] = dict()
#                         this_subject = Subject.objects.get(id=int(et_items.subject))
#                         # as_dict[student.reg_no]['mo_dict'][et_items.subject][et_sub_count]['subject_name'] = this_subject.subject
#                         as_dict[student.reg_no]["mo_dict"][et_items.subject][
#                             et_sub_count
#                         ]["th_mo"] = et_items.th_mo
#                         as_dict[student.reg_no]["mo_dict"][et_items.subject][
#                             et_sub_count
#                         ]["pr_mo"] = et_items.pr_mo
#
#                         as_dict[student.reg_no]["mo_dict2"][et_items.subject][
#                             "finalgrade"
#                         ] += (et_items.th_mo + et_items.pr_mo)
#
#                         as_dict[student.reg_no]["mo_dict2"][et_items.subject][
#                             "subject_name"
#                         ] = this_subject.subject
#                         as_dict[student.reg_no]["mo_dict2"][et_items.subject][
#                             "gradepoint"
#                         ] += (et_items.th_mo + et_items.pr_mo)
#                     print("-------")
#
#                     print(as_dict)
#
#                 marks_obtained = MarkObtained.objects.filter(
#                     student=student.reg_no,
#                     session=this_session,
#                     grade=student.grade.id,
#                     term=term,
#                 )
#                 sub_count = 1
#                 total = dict()
#                 credithour = 0
#                 totalm = 0
#                 totaltm = 0
#                 totalpm = 0
#                 totaltmo = 0
#                 totalpmo = 0
#                 position = 0
#                 fail = 0
#                 totalstudent = Student.objects.filter(
#                     grade=student.grade, section=student.section
#                 ).count()
#                 # for calculating rank
#
#                 # req_rank = calculaterank(school=student.school.id, session=this_session, grade= int(student.grade.id), term=term, section=student.section, regno=student.reg_no)
#                 # print('00000000000000000000')
#                 # print(req_rank)
#
#                 ## rank calculation ends
#
#                 # print(mod)
#                 subcount = 0
#                 cgpa = 0
#                 for subject in grade_subjects:
#                     for mo in marks_obtained:
#                         if subject.id == mo.subject:
#                             subcount += 1
#                             as_dict[student.reg_no]["mo_dict"][sub_count] = dict()
#                             this_subject = Subject.objects.get(id=int(mo.subject))
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "subject_name"
#                             ] = this_subject
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "theory_fm"
#                             ] = 4
#
#                             credithour += 4
#
#                             gfm = GradeFullMarks.objects.get(
#                                 subject=this_subject, term=this_term
#                             )
#
#                             totaltm += gfm.th_fm
#                             totalpm += gfm.pr_fm
#                             totaltmo += mo.th_mo
#                             totalpmo += mo.pr_mo
#
#                             if mo.th_mo > 0:
#                                 mth = mo.th_mo * 100 / gfm.th_fm
#                                 mthg = grading(mth)[0]
#                                 mthgp = grading(mth)[1]
#                             elif gfm.th_fm == 0:
#                                 mthg = ""
#                                 mthgp = 0
#                             else:
#                                 mthg = "N"
#                                 fail += 1
#                                 mthgp = 0
#
#                             if mo.pr_mo > 0:
#                                 mpr = mo.pr_mo * 100 / gfm.pr_fm
#                                 mprg = grading(mpr)[0]
#                                 mprgp = grading(mpr)[1]
#                             elif gfm.pr_fm == 0:
#                                 mprg = ""
#                                 mprgp = 0
#                             else:
#                                 mprg = "N"
#                                 fail += 1
#                                 mprgp = 0
#
#                             totfm = gfm.th_fm + gfm.pr_fm
#                             totmo = mo.th_mo + mo.pr_mo
#                             if gfm.pr_fm != 0 and gfm.th_fm != 0:
#                                 totmogp = (mthgp + mprgp) / 2
#                                 totmogp = grading(
#                                     (mo.th_mo + mo.pr_mo)
#                                     * 100
#                                     / (gfm.th_fm + gfm.pr_fm)
#                                 )[1]
#
#                             else:
#                                 totmogp = mthgp + mprgp
#
#                             cgpa += totmogp
#
#                             if totmo > 0:
#                                 totmop = totmo * 100 / totfm
#                                 as_dict[student.reg_no]["mo_dict"][sub_count][
#                                     "total_mo"
#                                 ] = grading(totmop)[0]
#                             else:
#                                 as_dict[student.reg_no]["mo_dict"][sub_count][
#                                     "total_mo"
#                                 ] = "N"
#
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "theory_mo"
#                             ] = mthg
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "prac_mo"
#                             ] = mprg
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "gradepoint"
#                             ] = totmogp
#
#                             sub_count += 1
#
#                 # cgpa = grading(totmo*100/totfm)[1]
#                 if cgpa > 0:
#                     cgpa = round(cgpa / subcount, 2)
#                 else:
#                     cgpa = 0
#
#                 as_dict[student.reg_no]["cgpa"] = cgpa
#                 as_dict[student.reg_no]["remarks"] = remarks(cgpa)
#
#                 totaltm += gfm.th_fm
#                 totalpm += gfm.pr_fm
#                 totalm = totaltm + totalpm
#                 totalmo = totaltmo + totalpmo
#                 totalg = totalmo * 100 / totalm
#
#                 totaltmog = totaltmo * 100 / totaltm
#
#                 if totalpmo > 0:
#                     totalpmog = totalpmo * 100 / totalpm
#                     total["og_pr"] = grading(totalpmog)[0]
#                 else:
#                     totalpmog = ""
#                     total["og_pr"] = totalpmog
#
#                 total["credithour"] = credithour
#                 total["og_th"] = grading(totaltmog)[0]
#                 total["tog"] = grading(totalg)[0]
#                 totalgpa = grading(totalg)[1]
#
#                 # as_dict[student.reg_no]['mo_dict'] = dict()
#                 as_dict[student.reg_no]["additional_td"] = 12 - grade_subjects.count()
#
#                 # req_rank = calculaterank(school=student.school.id, session=this_session, grade= int(student.grade.id), term=term, section=student.section, regno=student.reg_no)
#                 req_rank = 1
#                 totalstudent = Student.objects.filter(
#                     grade=student.grade, section=student.section
#                 ).count()
#
#                 as_dict[student.reg_no]["rank"] = req_rank
#                 as_dict[student.reg_no]["totalstudent"] = totalstudent
#
#             context = {
#                 "year": "2076",
#                 "this_term": this_term.term_name,
#                 "as_dict": as_dict,
#                 "req_terms": req_terms,
#             }
#             return render(request, "panel/result2_percent.html", context)
#         else:
#             print("NO")
#
#     return HttpResponse("Hi")
#
#
# def printGradesheetTest(request, grade):
#     user = request.user
#     try:
#         branchuser = BranchUser.objects.get(user=user)
#     except BranchUser.DoesNotExist:
#         return HttpResponse(
#             'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
#         )
#
#     # this_term = V2TerminalExams.objects.get(school=school, branch=branch, value=term)
#     grade = int(grade)
#     resultstatus = LiveResult.objects.get(school=branchuser.school.id)
#
#     count = SchoolGrade.objects.filter(id=grade).count()
#     if count == 1:
#         reqGrade = SchoolGrade.objects.get(id=grade)
#         if reqGrade.school.id == branchuser.school.id:
#             print("YES", reqGrade, reqGrade.id)
#             students = Student.objects.filter(grade=grade)
#
#             resultstatus = LiveResult.objects.get(school=branchuser.school.id)
#             gradelist = json.loads(resultstatus.gradelist)
#             term = resultstatus.term
#             this_term = SchoolTerm.objects.get(id=term)
#             print("Term", this_term.id, this_term.term_name)
#
#             try:
#                 thepost = ResultManagement.objects.get(school_term=int(this_term.id))
#             except ResultManagement.DoesNotExist:
#                 thepost = None
#
#                 return HttpResponse(
#                     "Sorry Result Management not found for the required term"
#                 )
#
#             mark_ratio = json.loads(thepost.term_calculation)
#             print(mark_ratio)
#             req_term_count = 1
#             req_terms = []
#
#             # for key, value in mark_ratio.items():
#             #     req_terms[req_term_count] = key
#             #     req_term_count += 1
#
#             as_dict = dict()
#
#             total_std = Student.objects.filter(
#                 school=branchuser.school.id, grade=reqGrade, status=1
#             ).count()
#
#             grade_subjects = Subject.objects.filter(
#                 grade=reqGrade.id, branch=branchuser.school.id, status=True
#             )
#             grade_subjects_count = grade_subjects.count()
#             # Subject.objects.filter(grade=reqGrade.id, status=1)
#
#             # for subject in grade_subjects:
#             #     print (reqGrade.id, subject)
#
#             for student in students:
#                 if int(student.reg_no) >= 11110348:
#                     break
#                 as_dict[student.reg_no] = dict()
#                 as_dict[student.reg_no]["std_name"] = student.name
#                 as_dict[student.reg_no]["grade"] = student.grade
#                 as_dict[student.reg_no]["section"] = student.section
#                 as_dict[student.reg_no]["mo_dict"] = dict()
#                 as_dict[student.reg_no]["mo_dict2"] = dict()
#                 grade_subjects = Subject.objects.filter(
#                     grade=student.grade, branch=student.school, status=True
#                 )
#
#                 # ResultManagement.objects.ge
#                 et_sub_count = 0
#                 for subject in grade_subjects:
#                     # subcount+=1
#                     as_dict[student.reg_no]["mo_dict"][subject.id] = dict()
#                     as_dict[student.reg_no]["mo_dict2"][subject.id] = dict()
#                     as_dict[student.reg_no]["mo_dict2"][subject.id]["finalgrade"] = 0
#                     as_dict[student.reg_no]["mo_dict2"][subject.id]["gradepoint"] = 0
#
#                 for key, value in mark_ratio.items():
#                     exam_term = SchoolTerm.objects.get(school=student.school, id=key)
#                     print(exam_term)
#                     print("-------")
#
#                     et_sub_count += 1
#                     tot_grade_point = 0
#
#                     et_marks_obtained = MarkObtained.objects.filter(
#                         student=student.reg_no,
#                         session=this_session,
#                         grade=student.grade.id,
#                         term=exam_term.id,
#                     )
#                     print(et_marks_obtained)
#                     for et_items in et_marks_obtained:
#                         print(et_items.subject, et_items.th_mo, et_items.pr_mo)
#                         as_dict[student.reg_no]["mo_dict"][et_items.subject][
#                             et_sub_count
#                         ] = dict()
#                         this_subject = Subject.objects.get(id=int(et_items.subject))
#                         # as_dict[student.reg_no]['mo_dict'][et_items.subject][et_sub_count]['subject_name'] = this_subject.subject
#                         as_dict[student.reg_no]["mo_dict"][et_items.subject][
#                             et_sub_count
#                         ]["th_mo"] = et_items.th_mo
#                         as_dict[student.reg_no]["mo_dict"][et_items.subject][
#                             et_sub_count
#                         ]["pr_mo"] = et_items.pr_mo
#
#                         gfm = GradeFullMarks.objects.get(
#                             subject=et_items.subject, term=exam_term.id
#                         )
#
#                         print(gfm)
#
#                         as_dict[student.reg_no]["mo_dict2"][et_items.subject][
#                             "subject_name"
#                         ] = this_subject.subject
#                         as_dict[student.reg_no]["mo_dict2"][et_items.subject][
#                             "finalgrade"
#                         ] += (et_items.th_mo + et_items.pr_mo)
#                         as_dict[student.reg_no]["mo_dict2"][et_items.subject][
#                             "gradepoint"
#                         ] += (et_items.th_mo + et_items.pr_mo)
#                     print("-------")
#
#                     print(as_dict)
#
#                 marks_obtained = MarkObtained.objects.filter(
#                     student=student.reg_no,
#                     session=this_session,
#                     grade=student.grade.id,
#                     term=term,
#                 )
#                 sub_count = 1
#                 total = dict()
#                 credithour = 0
#                 totalm = 0
#                 totaltm = 0
#                 totalpm = 0
#                 totaltmo = 0
#                 totalpmo = 0
#                 position = 0
#                 fail = 0
#                 totalstudent = Student.objects.filter(
#                     grade=student.grade, section=student.section
#                 ).count()
#                 # for calculating rank
#
#                 # req_rank = calculaterank(school=student.school.id, session=this_session, grade= int(student.grade.id), term=term, section=student.section, regno=student.reg_no)
#                 # print('00000000000000000000')
#                 # print(req_rank)
#
#                 ## rank calculation ends
#
#                 # print(mod)
#                 subcount = 0
#                 cgpa = 0
#                 for subject in grade_subjects:
#                     for mo in marks_obtained:
#                         if subject.id == mo.subject:
#                             subcount += 1
#                             as_dict[student.reg_no]["mo_dict"][sub_count] = dict()
#                             this_subject = Subject.objects.get(id=int(mo.subject))
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "subject_name"
#                             ] = this_subject
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "theory_fm"
#                             ] = 4
#
#                             credithour += 4
#
#                             gfm = GradeFullMarks.objects.get(
#                                 subject=this_subject, term=this_term
#                             )
#
#                             totaltm += gfm.th_fm
#                             totalpm += gfm.pr_fm
#                             totaltmo += mo.th_mo
#                             totalpmo += mo.pr_mo
#
#                             if mo.th_mo > 0:
#                                 mth = mo.th_mo * 100 / gfm.th_fm
#                                 mthg = grading(mth)[0]
#                                 mthgp = grading(mth)[1]
#                             elif gfm.th_fm == 0:
#                                 mthg = ""
#                                 mthgp = 0
#                             else:
#                                 mthg = "N"
#                                 fail += 1
#                                 mthgp = 0
#
#                             if mo.pr_mo > 0:
#                                 mpr = mo.pr_mo * 100 / gfm.pr_fm
#                                 mprg = grading(mpr)[0]
#                                 mprgp = grading(mpr)[1]
#                             elif gfm.pr_fm == 0:
#                                 mprg = ""
#                                 mprgp = 0
#                             else:
#                                 mprg = "N"
#                                 fail += 1
#                                 mprgp = 0
#
#                             totfm = gfm.th_fm + gfm.pr_fm
#                             totmo = mo.th_mo + mo.pr_mo
#                             if gfm.pr_fm != 0 and gfm.th_fm != 0:
#                                 totmogp = (mthgp + mprgp) / 2
#                                 totmogp = grading(
#                                     (mo.th_mo + mo.pr_mo)
#                                     * 100
#                                     / (gfm.th_fm + gfm.pr_fm)
#                                 )[1]
#
#                             else:
#                                 totmogp = mthgp + mprgp
#
#                             cgpa += totmogp
#
#                             if totmo > 0:
#                                 totmop = totmo * 100 / totfm
#                                 as_dict[student.reg_no]["mo_dict"][sub_count][
#                                     "total_mo"
#                                 ] = grading(totmop)[0]
#                             else:
#                                 as_dict[student.reg_no]["mo_dict"][sub_count][
#                                     "total_mo"
#                                 ] = "N"
#
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "theory_mo"
#                             ] = mthg
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "prac_mo"
#                             ] = mprg
#                             as_dict[student.reg_no]["mo_dict"][sub_count][
#                                 "gradepoint"
#                             ] = totmogp
#
#                             sub_count += 1
#
#                 # cgpa = grading(totmo*100/totfm)[1]
#                 if cgpa > 0:
#                     cgpa = round(cgpa / subcount, 2)
#                 else:
#                     cgpa = 0
#
#                 as_dict[student.reg_no]["cgpa"] = cgpa
#                 as_dict[student.reg_no]["remarks"] = remarks(cgpa)
#
#                 totaltm += gfm.th_fm
#                 totalpm += gfm.pr_fm
#                 totalm = totaltm + totalpm
#                 totalmo = totaltmo + totalpmo
#                 totalg = totalmo * 100 / totalm
#
#                 totaltmog = totaltmo * 100 / totaltm
#
#                 if totalpmo > 0:
#                     totalpmog = totalpmo * 100 / totalpm
#                     total["og_pr"] = grading(totalpmog)[0]
#                 else:
#                     totalpmog = ""
#                     total["og_pr"] = totalpmog
#
#                 total["credithour"] = credithour
#                 total["og_th"] = grading(totaltmog)[0]
#                 total["tog"] = grading(totalg)[0]
#                 totalgpa = grading(totalg)[1]
#
#                 # as_dict[student.reg_no]['mo_dict'] = dict()
#                 as_dict[student.reg_no]["additional_td"] = 12 - grade_subjects.count()
#
#                 # req_rank = calculaterank(school=student.school.id, session=this_session, grade= int(student.grade.id), term=term, section=student.section, regno=student.reg_no)
#                 req_rank = 1
#                 totalstudent = Student.objects.filter(
#                     grade=student.grade, section=student.section
#                 ).count()
#
#                 as_dict[student.reg_no]["rank"] = req_rank
#                 as_dict[student.reg_no]["totalstudent"] = totalstudent
#
#             context = {
#                 "year": "2076",
#                 "this_term": this_term.term_name,
#                 "as_dict": as_dict,
#                 "req_terms": req_terms,
#             }
#             return render(request, "panel/result2.html", context)
#         else:
#             print("NO")
#
#     return HttpResponse("Hi")
#
#
def samataFinalRemarks(count):
    if count == 0:
        message = "Congratulations! Promoted to the next class."
        return message
    elif count <= 2:
        message = "Insufficient to promote. Provision for re-exam."
        return message
    elif count >= 3:
        message = "Failed! Insufficient to promote."
        return message




def detailResult2078(school, term, grade, student_reg_no, printtype=0, edusession=None, grading_type=2):
    printtype = int(printtype)
    grading_type = int(grading_type)
    
    if edusession:
        try: req_session = EduSession.objects.get(id=edusession)
        except: req_session = EduSession.objects.filter(status=True).last()
    else:
        req_session = EduSession.objects.filter(status=True).last()

    form_student = Student.objects.get(reg_no=student_reg_no)
    try:
        student = StudentSession.objects.get(session=req_session, student=form_student, status=True)
    except StudentSession.DoesNotExist:
        # If no session student found, create a dummy one for logic to proceed
        # Or find the student in any session
        student = StudentSession.objects.filter(student=form_student).last()
        if not student:
            # Fallback if student has no sessions at all
            return {"subjects": {}, "mo_th": 0, "mo_pr": 0, "total": 0, "gp": 0, "remarks": ""}

    print("STUDENT", student)
    this_term = SchoolTerm.objects.get(id=term)
    this_session = req_session

    target_grade = student.grade
    grade_subjects = Subject.objects.filter(
        grade=target_grade, branch=target_grade.school, status=True
    ).order_by("id")
    total_std = StudentSession.objects.filter(
        session=edusession, grade=grade, status=1
    ).count()

    # marks_obtained = MarkObtained.objects.filter(student=student.reg_no, session=this_session,
    # grade=student.grade.id, term=term)

    total = dict()
    credithour = 0
    totalm = 0
    totaltm = 0
    totalpm = 0
    totaltmo = 0
    totalpmo = 0
    totalmo = 0
    position = 0
    fail = 0
    totalgpa = totalpmog = 0
    totalstudent = StudentSession.objects.filter(
        grade=grade, section=student.section
    ).count()
    # for calculating rank

    # req_rank = calculaterank(school=student.school.id, session=this_session, grade=int(student.grade.id), term=term,
    #                         section=student.section, regno=student.reg_no)
    req_rank = ""
    # print(req_rank)

    ## rank calculation ends

    # print(mod)
    sub_count = 0
    cgpa = 0
    gp16count = 0
    mo_dict = {}
    th_subject_count = pr_subject_count = 0
    th_gp_total = pr_gp_total = 0
    for subject in grade_subjects:
        sub_count += 1
        mo_dict[subject.id] = {}
        try:
            subject_marks_obtained = MarkObtained.objects.get(
                student=student.student.reg_no,
                session=this_session,
                grade=student.grade.id,
                term=term,
                subject=subject.id,
            )
        except:
            subject_marks_obtained = MarkObtained()
            subject_marks_obtained.th_mo = 0
            subject_marks_obtained.pr_mo = 0

        try:
            gfm = GradeFullMarks.objects.get(subject=subject.id, term=this_term)
        except:
            gfm = GradeFullMarks
            gfm.th_fm = 0
            gfm.pr_fm = 0
            gfm.th_pm = 0
            gfm.pr_pm = 0

        mo_dict[subject.id]["subject_name"] = subject.subject

        total_fm = gfm.th_fm + gfm.pr_fm
        total_mo = subject_marks_obtained.th_mo + subject_marks_obtained.pr_mo

        # Use appropriate GradeAndGpa class based on grading_type
        if grading_type == 2:
            g_obj = GradeAndGpaNew(gfm.th_fm, gfm.pr_fm, subject_marks_obtained.th_mo, subject_marks_obtained.pr_mo, subject.heavy_weight, result_type=2)
        else:
            g_obj = GradeAndGpa(gfm.th_fm, gfm.pr_fm, subject_marks_obtained.th_mo, subject_marks_obtained.pr_mo, subject.heavy_weight)

        mo_dict[subject.id]["total_mo"], mo_dict[subject.id]["total_mo_s"] = g_obj.total_grade, g_obj.total_symbol
        totmogp = g_obj.total_point
        totalmog = g_obj.total_grade
        totalmog_s = g_obj.total_symbol
        
        if subject.heavy_weight and totmogp <= 1.6:
            gp16count += 1

        cgpa += totmogp

        if gfm.th_fm > 0:
            mo_dict[subject.id]["theory_mo"] = g_obj.th_grade
            mo_dict[subject.id]["theory_mo_s"] = g_obj.th_symbol
            th_gp_total += g_obj.th_point
        else:
            mo_dict[subject.id]["theory_mo"] = ""
            mo_dict[subject.id]["theory_mo_s"] = ""

        if gfm.pr_fm > 0:
            mo_dict[subject.id]["prac_mo"] = g_obj.pr_grade
            mo_dict[subject.id]["prac_mo_s"] = g_obj.pr_symbol
            pr_gp_total += g_obj.pr_point
        else:
            mo_dict[subject.id]["prac_mo"] = ""
            mo_dict[subject.id]["prac_mo_s"] = ""

        mo_dict[subject.id]["theory_raw"] = subject_marks_obtained.th_mo # Raw Mark
        mo_dict[subject.id]["prac_raw"] = subject_marks_obtained.pr_mo   # Raw Mark
        mo_dict[subject.id]["gradepoint"] = totmogp
        mo_dict[subject.id]["th_fail"] = g_obj.th_fail
        mo_dict[subject.id]["pr_fail"] = g_obj.pr_fail

        totaltmo += subject_marks_obtained.th_mo
        totalpmo += subject_marks_obtained.pr_mo
        totalmo += total_mo

    try:
        cgpa = round(cgpa / sub_count, 2)
    except ZeroDivisionError as error:
        cgpa = "Value is 0"

    # the_remarks = samataFinalRemarks(gp16count)
    the_remarks = remarks(cgpa)

    # print(the_remarks)

    th_grade_final = th_gp_total  # grading(totalpmog)[0]
    pr_grade_final = pr_gp_total  # grading(totalpmog)[0]

    sr = {}
    totalgpa = cgpa
    totaltmog = gpFromGPA(cgpa)
    totaltmog_l, totaltmog_s = split_gpa_grade(totaltmog)

    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    print("PRINTING MODICT: ", student.student.reg_no)
    print(mo_dict)
    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

    if printtype == 1:  # grade
        th_gpa_grade = gpFromGPA(th_gp_total/sub_count)
        sr["mo_th_l"], sr["mo_th_s"] = split_gpa_grade(th_gpa_grade)
        if totalpmog == "":
            sr["mo_pr_l"] = " "
            sr["mo_pr_s"] = ""
        else:
            sr["mo_pr_l"] = pr_grade_final
            sr["mo_pr_s"] = "" # Assuming pr_grade_final is already a letter or handled

        sr["total_l"] = totaltmog_l
        sr["total_s"] = totaltmog_s
        sr["mo_th"] = totaltmo
        sr["mo_pr"] = totalpmo
        sr["total"] = totalmo
        sr["gp"] = totalgpa
        sr["subjects"] = mo_dict
        sr["remarks"] = the_remarks
    else:
        sr["mo_th"] = totaltmo
        sr["mo_pr"] = totalpmo
        sr["total"] = totalmo
        sr["gp"] = totalgpa
        sr["subjects"] = mo_dict
        sr["remarks"] = the_remarks

    return sr

def summarizedResult(school, term, grade, student):
    this_session = EduSession.objects.get(id=3)
    grade_subjects = Subject.objects.filter(grade=grade, branch=school, status=True)
    marks_obtained = MarkObtained.objects.filter(student=student, session=this_session, grade=grade, term=term)

    # print(marks_obtained)

    mo_th = 0
    mo_pr = 0
    total = 0
    gp = 0

    sub_count = 1
    total = dict()
    credithour = 0
    totalm = 0
    totaltm = 0
    totalpm = 0
    totaltmo = 0
    totalpmo = 0
    position = 0
    fail = 0

    subcount = 0
    cgpa = 0
    mo_dict = dict()
    for subject in grade_subjects:
        for mo in marks_obtained:
            if subject.id == mo.subject:
                subcount += 1
                mo_dict[sub_count] = dict()
                this_subject = Subject.objects.get(id=int(mo.subject))
                mo_dict[sub_count]['subject_name'] = this_subject
                mo_dict[sub_count]['theory_fm'] = 4

                credithour += 4

                gfm = GradeFullMarks.objects.get(subject=this_subject)

                totaltm += gfm.th_fm
                totalpm += gfm.pr_fm
                totaltmo += mo.th_mo
                totalpmo += mo.pr_mo

                if mo.th_mo > 0:
                    mth = mo.th_mo * 100 / gfm.th_fm
                    mthg = grading(mth)[0]
                    mthgp = grading(mth)[1]
                elif gfm.th_fm == 0:
                    mthg = ''
                    mthgp = 0
                else:
                    mthg = 'N'
                    fail += 1
                    mthgp = 0

                if mo.pr_mo > 0:
                    mpr = mo.pr_mo * 100 / gfm.pr_fm
                    mprg = grading(mpr)[0]
                    mprgp = grading(mpr)[1]
                elif gfm.pr_fm == 0:
                    mprg = ''
                    mprgp = 0
                else:
                    mprg = 'N'
                    fail += 1
                    mprgp = 0

                totfm = gfm.th_fm + gfm.pr_fm
                totmo = mo.th_mo + mo.pr_mo
                if gfm.pr_fm != 0 and gfm.th_fm != 0:
                    totmogp = (mthgp + mprgp) / 2

                else:
                    totmogp = (mthgp + mprgp)

                cgpa += totmogp

                if totmo > 0:
                    totmop = totmo * 100 / totfm
                    mo_dict[sub_count]['total_mo'] = grading(totmop)[0]
                else:
                    mo_dict[sub_count]['total_mo'] = 'N'

                mo_dict[sub_count]['theory_mo'] = mthg
                mo_dict[sub_count]['prac_mo'] = mprg
                mo_dict[sub_count]['gradepoint'] = totmogp

                sub_count += 1

    cgpa = round(cgpa / subcount, 2)

    totaltm += gfm.th_fm
    totalpm += gfm.pr_fm
    totalm = totaltm + totalpm
    totalmo = totaltmo + totalpmo
    totalg = totalmo * 100 / totalm

    totaltmog = totaltmo * 100 / totaltm

    if totalpmo > 0:
        totalpmog = totalpmo * 100 / totalpm
        total['og_pr'] = grading(totalpmog)[0]
    else:
        totalpmog = ''
        total['og_pr'] = totalpmog

    total['credithour'] = credithour
    total['og_th'] = grading(totaltmog)[0]
    total['tog'] = grading(totalg)[0]
    totalgpa = grading(totalg)[1]

    sr = {}
    sr['mo_th'] = totaltmo
    sr['mo_pr'] = totalpmo
    sr['total'] = totalmo
    sr['gp'] = totalgpa

    return (sr)


def detailResult(school, term, grade, student, edusession, printtype=0):
    printtype = int(printtype)
    this_session = EduSession.objects.get(id=edusession)
    grade_subjects = Subject.objects.filter(grade=grade, branch=school, status=True)
    fm_pm = GradeFullMarks.objects.filter(session=this_session, school=school, grade=grade, term=term)
    marks_obtained = MarkObtained.objects.filter(student=student, session=this_session, grade=grade, term=term)
    print("FM PM")
    print(fm_pm)
    print(marks_obtained)

    mo_th = 0
    mo_pr = 0
    total = 0
    gp = 0

    sub_count = 1
    total = dict()
    credithour = 0
    totalm = 0
    totaltm = 0
    totalpm = 0
    totaltmo = 0
    totalpmo = 0
    position = 0
    fail = 0

    subcount = 0
    cgpa = 0
    mo_dict = dict()
    for subject in grade_subjects:
        for mo in marks_obtained:
            if subject.id == mo.subject:

                this_subject = Subject.objects.get(id=int(mo.subject))
                mo_dict[subject.id] = dict()

                gfm = GradeFullMarks.objects.get(session=this_session, subject=this_subject, term=term)

                totaltm += gfm.th_fm
                totalpm += gfm.pr_fm
                totaltmo += mo.th_mo
                totalpmo += mo.pr_mo

                th_fail = False
                pr_fail = False

                if mo.th_mo > 0:
                    mth = mo.th_mo

                    mthg = grading(mth * 100 / gfm.th_fm)[0]
                    mthgp = grading(mth * 100 / gfm.th_fm)[1]
                elif gfm.th_fm == 0:
                    mth = 0
                    mthg = ''
                    mthgp = 0
                else:
                    mth = 0
                    mthg = 'N'
                    fail += 1
                    mthgp = 0
                    th_fail = True

                if mo.pr_mo > 0:
                    mpr = mo.pr_mo
                    mprg = grading(mpr * 100 / gfm.pr_fm)[0]
                    mprgp = grading(mpr * 100 / gfm.pr_fm)[1]
                elif gfm.pr_fm == 0:
                    mpr = 0
                    mprg = ''
                    mprgp = 0
                    # mpr = ''
                else:
                    mpr = 0
                    mprg = 'N'
                    fail += 1
                    mprgp = 0
                    pr_fail = True

                totfm = gfm.th_fm + gfm.pr_fm
                totmo = mo.th_mo + mo.pr_mo
                if gfm.pr_fm != 0 and gfm.th_fm != 0:
                    totmogp = (mthgp + mprgp) / 2

                else:
                    totmogp = (mthgp + mprgp)

                cgpa += totmogp

                if totmo > 0:
                    totmop = totmo * 100 / totfm
                    mo_dict[subject.id]['total_mo'] = grading(totmop)[0]
                else:
                    mo_dict[subject.id]['total_mo'] = 'N'
                # print('Print Type: ', printtype)
                if printtype == 1:  # GRADE
                    mo_dict[subject.id]['theory_mo'] = mthg
                    mo_dict[subject.id]['th_fail'] = th_fail
                    mo_dict[subject.id]['prac_mo'] = mprg
                    mo_dict[subject.id]['pr_fail'] = pr_fail
                    mo_dict[subject.id]['gradepoint'] = totmo
                else:
                    mo_dict[subject.id]['theory_mo'] = mth
                    mo_dict[subject.id]['th_fail'] = th_fail
                    mo_dict[subject.id]['prac_mo'] = mpr
                    mo_dict[subject.id]['pr_fail'] = pr_fail
                    mo_dict[subject.id]['gradepoint'] = totmo

                sub_count += 1

    # totaltm += gfm.th_fm
    # totalpm += gfm.pr_fm
    totalm = totaltm + totalpm
    totalmo = totaltmo + totalpmo
    # print('TOTAL MO', totalmo)
    if totalmo > 0:
        totalpercent = totalmo * 100 / totalm
        totaltmog = grading(totaltmo * 100 / totalm)[0]
    else:
        totalpercent = 0
        totaltmog = 0
    # print('TOTAL PERCENT', totalpercent)

    if totalpmo > 0:
        totalpmog = totalpmo * 100 / totalpm
        total['og_pr'] = grading(totalpmog)[0]
    else:
        totalpmog = ''
        total['og_pr'] = totalpmog

    total['credithour'] = credithour
    total['og_th'] = totaltmog
    total['tog'] = grading(totalpercent)[0]
    totalgpa = grading(totalpercent)[1]

    sr = {}

    if printtype == 1:  # grade
        sr['mo_th'] = totaltmog
        if totalpmog == '':
            sr['mo_pr'] = ''
        else:
            sr['mo_pr'] = grading(totalpmog)[0]

        sr['total'] = totaltmog
        sr['gp'] = totalgpa
        sr['subjects'] = mo_dict
    else:   # Percent
        sr['mo_th'] = totaltmo
        sr['mo_pr'] = totalpmo
        sr['total'] = totalmo
        sr['gp'] = totalgpa
        sr['subjects'] = mo_dict

    return sr


def grading(percent):
    res = get_grade_point_exam(percent)
    grade_l = res[0]
    grade_s = res[1]
    point = res[2]
    
    # Map points to legacy remarks
    remark = "Try Next Time"
    if point >= 4.0: remark = "Excellent"
    elif point >= 3.6: remark = "Very Nice"
    elif point >= 3.2: remark = "Nice"
    elif point >= 2.8: remark = "Good"
    elif point >= 2.4: remark = "Study More"
    elif point >= 2.0: remark = "Pay Attention"
    elif point >= 1.6: remark = "Labour Hard"
    
    return (grade_l, grade_s, point, remark)


def split_gpa_grade(gpa_grade_str):
    if not gpa_grade_str:
        return "-", ""
    if len(gpa_grade_str) > 1 and gpa_grade_str[1] in ["+", "-"]:
        return gpa_grade_str[0], gpa_grade_str[1:]
    return gpa_grade_str, ""

def gpFromGPA(gpa):
    gpa = round(_as_float(gpa), 2)
    if gpa >= 4.0:
        return "A+"
    elif gpa >= 3.6:
        return "A"
    elif gpa >= 3.2:
        return "B+"
    elif gpa >= 2.8:
        return "B"
    elif gpa >= 2.4:
        return "C+"
    elif gpa >= 2.0:
        return "C"
    elif gpa >= 1.6:
        return "D"
    # elif gpa >= 1.2:
    #     return "D"
    # elif gpa >= 0.1:
    #     return "E"
    else:
        return "NG"


def remarks(percent):
    if percent > 4:
        return ("SOMETHING WRONG", 4.0)
    if percent == 4:
        return ("Excellent")
    elif 3.6 <= percent < 4:
        return ("Very Nice")
        # return(result)
    elif 3.2 <= percent < 3.6:
        return ("Nice")
        # return(result)
    elif 2.8 <= percent < 3.2:
        return ("Good")
        # return(result)
    elif 2.4 <= percent < 2.8:
        return ("Study More")
        # return(result)
    elif 2.0 <= percent < 2.40:
        return ("Pay Attention")
        # return(result)
    elif 1.6 <= percent < 2.0:
        return ("Labour Hard")
    elif 1.2 <= percent < 1.6:
        return ("Labour Hard")
        # return(result)
    elif percent >= 0.1 and percent < 1.2:
        return ("Labour Harder")
        # return(result)
    elif percent == 0:
        return ("Try Next Time")
        # return(result)


def calculate_rank(school, session, grade, term, section=None, regno=None, rank_by="total"):
    print('calculating rank')
    # this_session = EduSession.objects.get(id=session)
    if section:
        # student_ko_list = Student.objects.filter(school=school, grade=grade, section=section, status=True)
        student_ko_list = StudentSession.objects.filter(grade=grade, section=section, session=session, status=True)
    else:
        # student_ko_list = Student.objects.filter(school=school, grade=grade, status=True)
        student_ko_list = StudentSession.objects.filter(grade=grade, session=session, status=True)
    std_list = dict()
    gfm = GradeFullMarks.objects.filter(school=school, session=session, grade=grade, term=term)
    gsubjects = Subject.objects.filter(branch=school, grade=grade, status=True)
    glist = []
    for items in gsubjects:
        glist.append(items.id)
    # print(gsubjects, glist)
    for stdl in student_ko_list:
        # print(stdl)
        totm = 0
        fail= 0
        students_marks = MarkObtained.objects.filter(school=school, session=session, grade=grade, term=term, student=stdl.student.reg_no)
        #print("Students Marks", students_marks)
        #print("gsubjects", gsubjects)
        for marks in students_marks:
            for gs in gfm:
                if(gs.subject.id == marks.subject.id): # and gs.subject.id in glist):
         #           print("OOOOOOO", gs.subject.id, marks.subject.id)
                    if gs.th_fm > 0 and gs.pr_fm > 0:
          #              print(gs)
                        if gs.th_pm <= marks.th_mo and gs.pr_pm <= marks.pr_mo:
                            totm += marks.th_mo + marks.pr_mo
                            # print('Pass ', gs.subject, gs.th_pm, marks.th_mo, 'Practical', gs.pr_pm, marks.pr_mo)
           #                 print("STUDENT PASS")
                        else:
            #                print("STUDENT FAILED")
                            totm += marks.th_mo + marks.pr_mo
                            fail += 1
                            # print('Fail ', gs.subject, gs.th_pm, marks.th_mo, 'Practical', gs.pr_pm, marks.pr_mo)
                    elif gs.th_fm > 0 and gs.pr_fm == 0:
                        if gs.th_pm <= marks.th_mo:
                            # print('Pass ', gs.subject, gs.th_pm, marks.th_mo, 'Practical', gs.pr_pm, marks.pr_mo)
                            totm += marks.th_mo
                        else:
                            totm += marks.th_mo
                            fail +=1
                            # print('Fail ', gs.subject, gs.th_pm, marks.th_mo, 'Practical', gs.pr_pm, marks.pr_mo)
            # print(stdl.reg_no, totm)

        std_list[stdl.student.reg_no] = totm
        if fail != 0:
            print(stdl.student.reg_no, ' fail')

        # print(totm)

    # print(std_list)
    # rank_no = 1
    # for key, value in sorted(mydict.iteritems(), key=lambda (k,v): (v,k)):
    # print "%s: %s" % (key, value)

    # for key, value in sorted(std_list.iteritems(), key=lambda (k,v): (v,k)):
    # print "%s: %s" % (key, value)
    # sorted_d = [(k,v) for k,v in std_list.items()]

    # Sort based on rank_by
    if rank_by == "gpa":
        # Note: GPA calculation is complex and depends on many factors.
        # For simplicity in this function, we'll continue using total marks
        # but the view functions have the more precise GPA ranking.
        sorted_d = sorted(std_list.items(), key=lambda x: x[1], reverse=True)
    else:
        sorted_d = sorted(std_list.items(), key=lambda x: x[1], reverse=True)

    high_mark = -1
    stat_rank = 0
    std_dict = dict()
    for calc in sorted_d:
        current_val = round(_as_float(calc[1]), 2)
        if current_val == high_mark:
            std_dict[calc[0]] = stat_rank
        else:
            stat_rank += 1
            high_mark = current_val
            std_dict[calc[0]] = stat_rank

    print(std_dict)

    if regno:
        if regno in std_dict:
            # print(regno)
            # print(std_dict[regno])
            return std_dict[regno]
        else:
            return '-'
    else:
        return std_dict


def gradingbygov(percent):
    if percent > 100:
        return ("SOMETHING WRONG", 4.0)
    elif 90 <= percent <= 100:
        return ("A+", 4.0, "Outstanding")
    elif 80 <= percent < 90:
        return ("A", 3.6, "Excellent")
        # return(result)
    elif 70 <= percent < 80:
        return ("B+", 3.2, "Very good")
        # return(result)
    elif 60 <= percent < 70:
        return ("B", 2.8, "Good")
        # return(result)
    elif 50 <= percent < 60:
        return ("C+", 2.4, "Satisfactory")
        # return(result)
    elif 40 <= percent < 50:
        return ("C", 2.0, "Acceptable")
        # return(result)
    elif 35 <= percent < 40:
        return ("D", 1.6, "Basic")
    else:
        return ("NG", 0, "Not graded")


# class GradeAndGpa:
#     def __init__(self, fm_th, fm_pr, mo_th, mo_pr, priority):
#         self.fm_th = fm_th
#         self.fm_pr = fm_pr
#         # self.pm_th = pm_th
#         # self.pm_pr = pm_pr
#         self.mo_th = mo_th
#         self.mo_pr = mo_pr

#         if fm_th > 0:
#             if fm_pr > 0:
#                 # Both theory and practical marks
#                 self.total_fm = fm_th + fm_pr
#                 self.total_mo = mo_th + mo_pr

#                 th_percent = get_percentage(mo_th, fm_th)
#                 pr_percent = get_percentage(mo_pr, fm_pr)

#                 self.th_grade, self.th_point = get_grade_point(th_percent)
#                 self.pr_grade, self.pr_point = get_grade_point(pr_percent)
#             else:
#                 # Only theory marks
#                 self.total_fm = fm_th
#                 self.total_mo = mo_th

#                 th_percent = get_percentage(mo_th, fm_th)
#                 self.th_grade, self.th_point = get_grade_point(th_percent)
#                 self.pr_grade = ' '
#                 self.pr_point = 0
#         else:
#             if fm_pr > 0:
#                 # Only Practical Marks
#                 self.total_fm = fm_pr
#                 self.total_mo = mo_pr

#                 pr_percent = get_percentage(mo_pr, fm_pr)
#                 self.pr_grade, self.pr_point = get_grade_point(pr_percent)
#                 self.th_grade = ' '
#                 self.th_point = 0

#         self.percent = self.total_mo * 100 / self.total_fm
#         self.total_grade, self.total_point = get_grade_point(self.percent)


class GradeAndGpa:
    def __init__(self, fm_th, fm_pr, mo_th, mo_pr, priority, result_type=None):
        self.fm_th = fm_th
        self.fm_pr = fm_pr
        # self.pm_th = pm_th
        # self.pm_pr = pm_pr
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
                    
        if(self.total_fm <= 0):
            self.percent = 0
        else:
            self.percent = (self.total_mo / self.total_fm)*100
            
        self.total_grade, self.total_symbol, self.total_point = get_grade_point(self.percent)

        if priority:
            if self.total_point < 1.6:
                self.final_fail += 1
                #self.total_grade += "FAIL"
            

# def get_grade_point(self, percent):
#     if 0 > percent > 100:
#         self.grade = "SOMETHING WRONG"
#         self.point = 0.0
#     elif 90 <= percent <= 100:
#         self.grade = "A+"
#         self.point = 4.0
#     elif 80 <= percent < 90:
#         self.grade = "A"
#         self.point = 3.6
#     elif 70 <= percent < 80:
#         self.grade = "B+"
#         self.point = 3.2
#     elif 60 <= percent < 70:
#         self.grade = "B"
#         self.point = 2.8
#     elif 50 <= percent < 60:
#         self.grade = "C+"
#         self.point = 2.4
#     elif 40 <= percent < 50:
#         self.grade = "C"
#         self.point = 2.0
#     elif 35 <= percent < 40:
#         self.grade = "D"
#         self.point = 1.6
#     elif 0 <= percent < 35:
#         self.grade = "NG"
#         self.point = 0


def get_percentage(obtained,full):
    return obtained*100/full


def get_grade_point(percent):
    if 0 > percent > 100:
        return ["SOMETHING WRONG", " ", 0.0]
    elif 90 <= percent <= 100:
        return ["A","+", 4.0]
    elif 80 <= percent < 90:
        return ["A"," ", 3.6]
    elif 70 <= percent < 80:
        return ["B","+", 3.2]
    elif 60 <= percent < 70:
        return ["B"," ", 2.8]
    elif 50 <= percent < 60:
        return ["C","+", 2.4]
    elif 40 <= percent < 50:
        return ["C"," ", 2.0]
    elif 35 <= percent < 40:
        return ["D"," ", 1.6]
    elif 0 <= percent < 35:
        return ["NG"," ", 0]


class GradeAndGpaNonGraded:
    def __init__(self, fm_th, fm_pr, mo_th, mo_pr, priority):
        self.fm_th = fm_th
        self.fm_pr = fm_pr
        # self.pm_th = pm_th
        # self.pm_pr = pm_pr
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

        if fm_th > 0:
            if fm_pr > 0:
                # Both theory and practical marks
                self.total_fm = fm_th + fm_pr
                self.total_mo = mo_th + mo_pr

                th_percent = get_percentage(mo_th, fm_th)
                pr_percent = get_percentage(mo_pr, fm_pr)

                self.th_grade, self.th_symbol, self.th_point = get_grade_point(th_percent)
                self.pr_grade, self.pr_symbol, self.pr_point = get_grade_point(pr_percent)

                if (mo_th/fm_th)*100 < 35 or (mo_pr/fm_pr)*100 < 40:
                    self.fail += 1


                # if priority:
                #     if self.th_point < 1.6 or self.pr_point < 1.6:
                #         self.fail += 1
                #         #self.pr_grade +="FAIL THPR"
                #         #self.th_grade +="FAIL THPR"
            else:
                # Only theory marks
                self.total_fm = fm_th
                self.total_mo = mo_th

                th_percent = get_percentage(mo_th, fm_th)
                self.th_grade, self.th_symbol, self.th_point = get_grade_point(th_percent)
                self.pr_grade = ' '
                self.pr_point = 0

                if (mo_th/fm_th)*100 < 35:
                    self.fail += 1
                
                # if priority:
                #     if self.th_point < 1.6:
                #         self.fail += 1
                #         #self.th_grade +="FAIL TH"
        else:
            if fm_pr > 0:
                # Only Practical Marks
                self.total_fm = fm_pr
                self.total_mo = mo_pr

                pr_percent = get_percentage(mo_pr, fm_pr)
                self.pr_grade, self.pr_symbol, self.pr_point = get_grade_point(pr_percent)
                self.th_grade = ' '
                self.th_point = 0

                if (mo_pr/fm_pr)*100 < 40:
                    self.fail += 1

                # if priority:
                #     if self.pr_point < 1.6:
                #         self.fail += 1
                #         #self.pr_grade +="FAIL PR"
                    
        if(self.total_fm <= 0):
            self.percent = 0
        else:
            self.percent = (self.total_mo / self.total_fm)*100
            
        self.total_grade, self.total_symbol, self.total_point = get_grade_point(self.percent)

        # if priority:
        #     if self.total_point < 1.6:
        #         self.final_fail += 1
        #         #self.total_grade += "FAIL"
        if self.fail >0:
            self.final_fail +=1
            

class GradeAndGpaNonGradeTheory:
    def __init__(self, fm_th, mo_th):
        self.fm_th = fm_th
        # self.pm_th = pm_th
        # self.pm_pr = pm_pr
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

            if (mo_th/fm_th)*100 < 35:
                self.fail += 1
                    
        if(self.fm_th <= 0):
            self.percent = 0
        else:
            self.percent = (self.mo_th / self.fm_th)*100
            
        self.total_grade, self.total_symbol, self.total_point = get_grade_point(self.percent)

        if self.fail >0:
            self.final_fail +=1

class GradeAndGpaNonGradePractical:
    def __init__(self, fm_pr, mo_pr):
        self.fm_pr = fm_pr
        # self.pm_th = pm_th
        # self.pm_pr = pm_pr
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
            # Only Practical Marks
            self.total_fm = fm_pr
            self.total_mo = mo_pr

            pr_percent = get_percentage(mo_pr, fm_pr)
            self.pr_grade, self.pr_symbol, self.pr_point = get_grade_point(pr_percent)
            self.th_grade = ' '
            self.th_point = 0

            if (mo_pr/fm_pr)*100 < 40:
                self.fail += 1


                    
        if(self.fm_pr <= 0):
            self.percent = 0
        else:
            self.percent = (self.mo_pr / self.fm_pr)*100
            
        self.total_grade, self.total_symbol, self.total_point = get_grade_point(self.percent)

        # if priority:
        #     if self.total_point < 1.6:
        #         self.final_fail += 1
        #         #self.total_grade += "FAIL"
        if self.fail >0:
            self.final_fail +=1


class GradeAndGpaNew:
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

        # Calculate theory and practical grades/points
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

                if priority and self.th_point < 1.6:
                    self.th_fail = True
                    self.fail += 1

        elif fm_pr > 0:
            # Only Practical Marks
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

        # Default grade assignment before result_type handling
        self.total_grade, self.total_symbol, self.total_point = get_grade_point(self.percent)

        # Final fail (priority subjects below threshold)
        if priority and self.total_point < 1.6:
            self.final_fail += 1

        # Special logic for result_type 2
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




class ExamUpdateComponent:
    """Handles grading for individual components with dynamic pass percentages"""
    def __init__(self, full_marks, marks_obtained, component_type, school):
        self.full_marks = full_marks
        self.marks_obtained = marks_obtained
        self.component_type = component_type  # 'theory' or 'practical'
        
        # Get pass percentage from school configuration
        self.pass_percent = school.theory_pass_percent if component_type == 'theory' else school.practical_pass_percent
        
        self.grade = ' '
        self.symbol = ' '
        self.point = 0
        self.is_passed = False
        
        self._calculate_grade()
    
    def _calculate_grade(self):
        if self.full_marks > 0:
            percentage = (self.marks_obtained / self.full_marks) * 100
            self.grade, self.symbol, self.point = get_grade_point(percentage)
            self.is_passed = percentage >= self.pass_percent

class ExamUpdateSubjectResult:
    """Combines theory and practical results with school-specific pass requirements"""
    def __init__(self, th_fm, pr_fm, th_mo, pr_mo, school):
        self.theory = ExamUpdateComponent(th_fm, th_mo, 'theory', school)
        self.practical = ExamUpdateComponent(pr_fm, pr_mo, 'practical', school)
        self.is_passed = self.theory.is_passed and self.practical.is_passed
        
        # Calculate combined results
        self._calculate_combined_results()
    
    def _calculate_combined_results(self):
        if not self.is_passed:
            self.grade = "NG"
            self.symbol = ""
            self.point = 0
            return
            
        # Calculate weighted average if both components exist
        if self.theory.point > 0 and self.practical.point > 0:
            self.point = (self.theory.point + self.practical.point) / 2
        elif self.theory.point > 0:
            self.point = self.theory.point
        else:
            self.point = self.practical.point
            
        self.grade, self.symbol = get_grade_point_from_point(self.point)


class GradeAndGpaNonGradeTheoryExam:
    def __init__(self, fm_th, mo_th):
        self.fm_th = fm_th
        self.mo_th = mo_th
        self.th_symbol = ' '
        self.th_grade = ' '
        self.th_point = 0
        self.fail = 0
        self.final_fail = 0
        self.total_symbol = ' '

        if fm_th > 0:
            th_percent = get_percentage(mo_th, fm_th)
            self.th_grade, self.th_symbol, self.th_point = get_grade_point_exam(th_percent)
            
            # Explicitly set grade point to 0 for failed subjects
            if th_percent < 40:
                self.fail = 1
                self.th_point = 0  # Force 0 grade points for failures
                
        self.percent = (mo_th / fm_th * 100) if fm_th > 0 else 0
        
        # Final grade calculation with enforced 0 points for failures
        if self.fail:
            self.total_grade = "NG"
            self.total_symbol = " "
            self.total_point = 0
            self.final_fail = 1
        else:
            self.total_grade, self.total_symbol, self.total_point = get_grade_point_exam(self.percent)


class GradeAndGpaNonGradePracticalExam:
    def __init__(self, fm_pr, mo_pr):
        self.fm_pr = fm_pr
        self.mo_pr = mo_pr
        self.pr_symbol = ' '
        self.pr_grade = ' '
        self.pr_point = 0
        self.fail = 0
        self.final_fail = 0
        self.total_symbol = ' '

        if fm_pr > 0:
            pr_percent = get_percentage(mo_pr, fm_pr)
            self.pr_grade, self.pr_symbol, self.pr_point = get_grade_point(pr_percent)
            
            # Explicitly set grade point to 0 for failed subjects
            if pr_percent < 40:
                self.fail = 1
                self.pr_point = 0  # Force 0 grade points for failures
                
        self.percent = (mo_pr / fm_pr * 100) if fm_pr > 0 else 0
        
        # Final grade calculation with enforced 0 points for failures
        if self.fail:
            self.total_grade = "NG"
            self.total_symbol = " "
            self.total_point = 0
            self.final_fail = 1
        else:
            self.total_grade, self.total_symbol, self.total_point = get_grade_point(self.percent)


def _as_float(val):
    try:
        return float(val)
    except Exception:
        return 0.0


def get_grade_point_exam(percent):
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
        return ["D", " ", 1.6]  # Changed to 0 points
    else:
        return ["NG", " ", 0]  # Explicit 0 points for failures


def _parse_weighted_term_config(weight_config, target_term_id, include_current=False):
    """
    Normalize weighted-term config to:
      {
        source_term_id: {
          "th_from_th": weight_decimal,
          "th_from_pr": weight_decimal,
          "pr_from_th": weight_decimal,
          "pr_from_pr": weight_decimal,
          "plan": global_plan,
          "th_target_fm": target_fm_th,
          "pr_target_fm": target_fm_pr,
        }
      }
    """
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

    # Root meta data
    global_plan = weight_config.get("plan", "direct")
    target_fm_th = float(weight_config.get("target_fm_th", 100))
    target_fm_pr = float(weight_config.get("target_fm_pr", 100))
    
    # Identify the block containing source terms
    sources_block = {}
    if "sources" in weight_config:
        sources_block = weight_config["sources"]
    elif "weights" in weight_config:
        weights_block = weight_config.get("weights", {})
        target_block = weights_block.get(str(target_term_id)) or weights_block.get(target_term_id, {})
        sources_block = target_block.get("sources", target_block)
    else:
        # Check if root keys are numeric (legacy/direct shape)
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
            # Extremely simple legacy shape
            th_from_th = pr_from_pr = float(value)
        elif isinstance(value, dict):
            # Check for nested th/pr blocks (current shape)
            th_block = value.get("th", {})
            pr_block = value.get("pr", {})
            
            if isinstance(th_block, dict):
                th_from_th = _as_float(th_block.get("th", 0))
                th_from_pr = _as_float(th_block.get("pr", 0))
            else:
                # legacy dict shape: {"th": 10, "pr": 5}
                th_from_th = _as_float(value.get("th", 0))
                th_from_pr = _as_float(value.get("pr", 0))

            if isinstance(pr_block, dict):
                pr_from_th = _as_float(pr_block.get("th", 0))
                pr_from_pr = _as_float(pr_block.get("pr", 0))
            else:
                # legacy dict shape: {"th": 10, "pr": 5}
                pr_from_th = _as_float(value.get("th", 0))
                pr_from_pr = _as_float(value.get("pr", 0))

        # Only include if there is some weight (> 0)
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

    return normalized


def calculate_weighted_term_results(
    school_id,
    session_id,
    grade_id,
    target_term_id,
    weight_config,
    student_ids=None,
    include_inactive_subjects=False,
):
    """
    New weighted-result calculator (does NOT modify old logic).

    Rule (per user spec):
      final_th = current_th + sum( w_th_th*prev_th + w_th_pr*prev_pr )
      final_pr = current_pr + sum( w_pr_th*prev_th + w_pr_pr*prev_pr )
      final_th_fm = current_th_fm + sum( w_th_th*prev_th_fm + w_th_pr*prev_pr_fm )
      final_pr_fm = current_pr_fm + sum( w_pr_th*prev_th_fm + w_pr_pr*prev_pr_fm )

    Grading uses get_grade_point_exam(percent) for each component and total.
    """
    weights = _parse_weighted_term_config(weight_config, target_term_id, include_current=True)
    if target_term_id not in weights:
        weights[target_term_id] = {
            "th_from_th": 1.0,
            "th_from_pr": 0.0,
            "pr_from_th": 0.0,
            "pr_from_pr": 1.0,
            "th_plan": "direct",
            "pr_plan": "direct",
            "th_target_fm": 100,
            "pr_target_fm": 100,
        }
    term_ids = list(weights.keys())

    subjects_qs = Subject.objects.filter(
        branch_id=school_id, grade_id=grade_id, session_id=session_id
    )
    if not include_inactive_subjects:
        subjects_qs = subjects_qs.filter(status=True)

    subjects = list(subjects_qs)
    if not subjects:
        return {}

    subject_ids = [s.id for s in subjects]

    students_qs = StudentSession.objects.filter(
        session_id=session_id, grade_id=grade_id, status=True
    )
    if student_ids:
        students_qs = students_qs.filter(student_id__in=student_ids)

    student_id_list = list(students_qs.values_list("student_id", flat=True))
    if not student_id_list:
        return {}

    marks_qs = MarkObtained.objects.filter(
        school_id=school_id,
        session_id=session_id,
        grade_id=grade_id,
        term_id__in=term_ids,
        subject_id__in=subject_ids,
        student_id__in=student_id_list,
    ).values("student_id", "term_id", "subject_id", "th_mo", "pr_mo")

    marks_map = {}
    for m in marks_qs:
        marks_map[(m["student_id"], m["term_id"], m["subject_id"])] = (
            m.get("th_mo", 0) or 0,
            m.get("pr_mo", 0) or 0,
        )

    fullmarks_qs = GradeFullMarks.objects.filter(
        school_id=school_id,
        session_id=session_id,
        grade_id=grade_id,
        term_id__in=term_ids,
        subject_id__in=subject_ids,
    ).values("term_id", "subject_id", "th_fm", "pr_fm", "th_pm", "pr_pm")

    fm_map = {}
    for fm in fullmarks_qs:
        fm_map[(fm["term_id"], fm["subject_id"])] = (
            fm.get("th_fm", 0) or 0,
            fm.get("pr_fm", 0) or 0,
            fm.get("th_pm", 0) or 0,
            fm.get("pr_pm", 0) or 0,
        )

    results = {}
    for student_id in student_id_list:
        student_result = {"subjects": {}, "totals": {}}
        total_points = 0.0
        subject_count = 0
        failed_subjects = 0

        for subject in subjects:
            th_total = 0.0
            pr_total = 0.0
            th_fm_total = 0.0
            pr_fm_total = 0.0

            for term_id, weight in weights.items():
                src_th, src_pr = marks_map.get((student_id, term_id, subject.id), (0, 0))
                src_th_fm, src_pr_fm, _, _ = fm_map.get((term_id, subject.id), (0, 0, 0, 0))

                # Calculation Plan Handling
                if weight.get("plan") == "scaling":
                    th_target = weight.get("th_target_fm", 100)
                    pr_target = weight.get("pr_target_fm", 100)
                    th_contrib_th = (src_th / src_th_fm * th_target * weight["th_from_th"]) if src_th_fm > 0 else 0
                    th_contrib_pr = (src_pr / src_pr_fm * th_target * weight["th_from_pr"]) if src_pr_fm > 0 else 0
                    pr_contrib_th = (src_th / src_th_fm * pr_target * weight["pr_from_th"]) if src_th_fm > 0 else 0
                    pr_contrib_pr = (src_pr / src_pr_fm * pr_target * weight["pr_from_pr"]) if src_pr_fm > 0 else 0
                else:
                    th_contrib_th = src_th * weight["th_from_th"]
                    th_contrib_pr = src_pr * weight["th_from_pr"]
                    pr_contrib_th = src_th * weight["pr_from_th"]
                    pr_contrib_pr = src_pr * weight["pr_from_pr"]

                th_total += th_contrib_th + th_contrib_pr
                pr_total += pr_contrib_th + pr_contrib_pr

                # For FM total, we also need to handle scaling
                if weight.get("plan") == "scaling":
                    th_target = weight.get("th_target_fm", 100)
                    pr_target = weight.get("pr_target_fm", 100)
                    th_fm_total += (th_target * weight["th_from_th"]) + (th_target * weight["th_from_pr"])
                    pr_fm_total += (pr_target * weight["pr_from_th"]) + (pr_target * weight["pr_from_pr"])
                else:
                    th_fm_total += (src_th_fm * weight["th_from_th"]) + (src_pr_fm * weight["th_from_pr"])
                    pr_fm_total += (src_th_fm * weight["pr_from_th"]) + (src_pr_fm * weight["pr_from_pr"])

            th_percent = (th_total * 100 / th_fm_total) if th_fm_total > 0 else 0
            pr_percent = (pr_total * 100 / pr_fm_total) if pr_fm_total > 0 else 0

            th_grade, th_symbol, th_point = get_grade_point_exam(th_percent)
            pr_grade, pr_symbol, pr_point = get_grade_point_exam(pr_percent)

            total_mo = th_total + pr_total
            total_fm = th_fm_total + pr_fm_total
            total_percent = (total_mo * 100 / total_fm) if total_fm > 0 else 0
            total_grade, total_symbol, total_point = get_grade_point_exam(total_percent)

            if th_percent < 40 or pr_percent < 40:
                failed_subjects += 1

            if total_fm > 0:
                total_points += total_point
                subject_count += 1

            student_result["subjects"][subject.id] = {
                "subject_name": subject.subject,
                "th_mo": round(th_total, 2),
                "pr_mo": round(pr_total, 2),
                "th_fm": round(th_fm_total, 2),
                "pr_fm": round(pr_fm_total, 2),
                "th_percent": round(th_percent, 2),
                "pr_percent": round(pr_percent, 2),
                "th_grade": th_grade,
                "th_symbol": th_symbol,
                "pr_grade": pr_grade,
                "pr_symbol": pr_symbol,
                "total_mo": round(total_mo, 2),
                "total_fm": round(total_fm, 2),
                "total_percent": round(total_percent, 2),
                "total_grade": total_grade,
                "total_symbol": total_symbol,
                "total_point": total_point,
            }

        cgpa = round(total_points / subject_count, 2) if subject_count else 0
        student_result["totals"] = {
            "cgpa": cgpa,
            "subjects": subject_count,
            "failed_subjects": failed_subjects,
        }

        results[student_id] = student_result

    return results


def build_weighted_mo_dict_for_students(
    school,
    this_session,
    this_grade,
    target_term,
    students,
    subjects,
    term_list,
    weight_config,
):
    student_list = list(students)
    student_ids = [s.student_id for s in student_list]
    subject_ids = [s.id for s in subjects]

    if not student_ids or not subject_ids:
        return {}, {}

    marks_qs = MarkObtained.objects.filter(
        school=school,
        session=this_session,
        grade=this_grade,
        term_id__in=term_list,
        subject_id__in=subject_ids,
        student_id__in=student_ids,
    ).values("student_id", "term_id", "subject_id", "th_mo", "pr_mo")

    marks_map = {}
    for m in marks_qs:
        marks_map[(m["student_id"], m["term_id"], m["subject_id"])] = (
            m.get("th_mo", 0) or 0,
            m.get("pr_mo", 0) or 0,
        )

    fm_qs = GradeFullMarks.objects.filter(
        school=school,
        session=this_session,
        grade=this_grade,
        term_id__in=term_list,
        subject_id__in=subject_ids,
    ).values("term_id", "subject_id", "th_fm", "pr_fm")

    fm_map = {}
    for fm in fm_qs:
        fm_map[(fm["term_id"], fm["subject_id"])] = (
            fm.get("th_fm", 0) or 0,
            fm.get("pr_fm", 0) or 0,
        )

    mo_dict = {}
    for student in student_list:
        reg_no = student.student.reg_no
        for term_id in term_list:
            for subject in subjects:
                th_mo, pr_mo = marks_map.get((student.student_id, term_id, subject.id), (0, 0))
                th_fm, pr_fm = fm_map.get((term_id, subject.id), (0, 0))

                if th_fm > 0:
                    th_percent = th_mo * 100 / th_fm
                    th_grade, th_symbol, th_point = get_grade_point_exam(th_percent)
                else:
                    th_grade, th_symbol, th_point = "", " ", 0

                if pr_fm > 0:
                    pr_percent = pr_mo * 100 / pr_fm
                    pr_grade, pr_symbol, pr_point = get_grade_point_exam(pr_percent)
                else:
                    pr_grade, pr_symbol, pr_point = "", " ", 0

                key_base = f"{reg_no}_{subject.id}_{term_id}"
                mo_dict[f"{key_base}_th_grade"] = th_grade
                mo_dict[f"{key_base}_th_symbol"] = th_symbol
                mo_dict[f"{key_base}_th_point"] = th_point
                mo_dict[f"{key_base}_pr_grade"] = pr_grade
                mo_dict[f"{key_base}_pr_symbol"] = pr_symbol
                mo_dict[f"{key_base}_pr_point"] = pr_point

    weighted_results = calculate_weighted_term_results(
        school_id=school.id,
        session_id=this_session.id,
        grade_id=this_grade.id,
        target_term_id=target_term.id,
        weight_config=weight_config,
        student_ids=student_ids,
    )

    totals_map = {}
    for student in student_list:
        reg_no = student.student.reg_no
        result = weighted_results.get(student.student_id)
        if not result:
            continue
        totals_map[student.student_id] = result.get("totals", {})
        totals = totals_map.get(student.student_id, {})
        cgpa = totals.get("cgpa", 0)
        failed_subjects = totals.get("failed_subjects", 0)
        
        target_term_id = target_term.id
        for subject in subjects:
            sub_result = result["subjects"].get(subject.id)
            if not sub_result:
                continue

            # Keys for individual subject results (Weighted Totals for the target term)
            # Format: {reg_no}_{subject.id}_{target_term_id}_th_grade
            if sub_result.get("th_fm", 0) > 0:
                th_grade, th_symbol, th_point = get_grade_point_exam(sub_result["th_percent"])
                mo_dict[f"{reg_no}_{subject.id}_{target_term_id}_th_grade"] = th_grade
                mo_dict[f"{reg_no}_{subject.id}_{target_term_id}_th_symbol"] = th_symbol
            else:
                mo_dict[f"{reg_no}_{subject.id}_{target_term_id}_th_grade"] = ""
                mo_dict[f"{reg_no}_{subject.id}_{target_term_id}_th_symbol"] = " "

            if sub_result.get("pr_fm", 0) > 0:
                pr_grade, pr_symbol, pr_point = get_grade_point_exam(sub_result["pr_percent"])
                mo_dict[f"{reg_no}_{subject.id}_{target_term_id}_pr_grade"] = pr_grade
                mo_dict[f"{reg_no}_{subject.id}_{target_term_id}_pr_symbol"] = pr_symbol
            else:
                mo_dict[f"{reg_no}_{subject.id}_{target_term_id}_pr_grade"] = ""
                mo_dict[f"{reg_no}_{subject.id}_{target_term_id}_pr_symbol"] = " "

            # Also provide the total_grade if the template needs it
            mo_dict[f"{reg_no}_{subject.id}_total_grade"] = sub_result["total_grade"]
            mo_dict[f"{reg_no}_{subject.id}_total_symbol"] = sub_result["total_symbol"]
            mo_dict[f"{reg_no}_{subject.id}_total_grade_point"] = sub_result["total_point"]

        mo_dict[f"{reg_no}_gpa"] = cgpa
        mo_dict[f"{reg_no}_remarks"] = "Labour Hard" if failed_subjects > 0 else remarks(cgpa)

    return mo_dict, totals_map
