import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.utils import timezone

import nepali_datetime

from sms.models import (
    BranchUser, Student, StudentSession, SchoolGrade, Section, Subject,
    EduSession, Homework,
)

from .models import (
    Remark,
    RemarkEditLog,
    Concern,
    CommunicationLog,
    RemarkTemplate,
)


def _get_school(user):
    """Return the BranchUser + school for the current user, or None."""
    try:
        bu = BranchUser.objects.select_related('school').get(user=user)
        return bu
    except BranchUser.DoesNotExist:
        return None


def _parse_bs_date(date_str):
    if not date_str:
        return None
    try:
        parts = [int(p) for p in date_str.split('-')]
        return nepali_datetime.date(parts[0], parts[1], parts[2])
    except (ValueError, IndexError):
        return None


# ── Admin dashboard ──────────────────────────────────────────────────────

@login_required
def concerns_dashboard(request):
    bu = _get_school(request.user)
    if not bu:
        return HttpResponse('Not allowed. <a href="/">Home</a>')
    school = bu.school
    if not bu.admin_status:
        return HttpResponse('Admin only. <a href="/">Home</a>')

    from collections import Counter
    category_counts = Counter(
        Remark.objects.filter(school=school, active=True).values_list('category', flat=True)
    )
    severity_counts = Counter(
        Remark.objects.filter(school=school, active=True).values_list('severity', flat=True)
    )
    concern_status_counts = Counter(
        Concern.objects.filter(school=school).values_list('status', flat=True)
    )

    open_concerns = Concern.objects.filter(school=school).exclude(
        status__in=['resolved', 'closed', 'dismissed']
    ).select_related('student', 'assigned_to')[:15]

    open_remarks = Remark.objects.filter(
        school=school, active=True, status='open'
    ).select_related('student', 'teacher', 'grade')[:15]

    total_remarks = Remark.objects.filter(school=school, active=True).count()
    total_concerns = Concern.objects.filter(school=school).count()

    context = {
        'school': school,
        'open_concerns': open_concerns,
        'open_remarks': open_remarks,
        'category_counts': dict(category_counts),
        'severity_counts': dict(severity_counts),
        'concern_status_counts': dict(concern_status_counts),
        'total_remarks': total_remarks,
        'total_concerns': total_concerns,
        'open_remark_count': Remark.objects.filter(school=school, active=True, status='open').count(),
        'escalated_remark_count': Remark.objects.filter(school=school, active=True, status='escalated').count(),
        'dismissed_remark_count': Remark.objects.filter(school=school, active=True, status='dismissed').count(),
        'high_severity_count': Remark.objects.filter(school=school, active=True, severity='high').count(),
        'parent_visible_remark_count': Remark.objects.filter(school=school, active=True, visibility='parent_visible').count(),
        'open_concern_count': Concern.objects.filter(school=school).exclude(
            status__in=['resolved', 'closed', 'dismissed']).count(),
        'open_concern_only_count': Concern.objects.filter(school=school, status='open').count(),
        'in_progress_concern_count': Concern.objects.filter(school=school, status='in_progress').count(),
        'awaiting_parent_concern_count': Concern.objects.filter(school=school, status='awaiting_parent').count(),
        'resolved_concern_count': Concern.objects.filter(school=school, status='resolved').count(),
        'closed_concern_count': Concern.objects.filter(school=school, status='closed').count(),
        'dismissed_concern_count': Concern.objects.filter(school=school, status='dismissed').count(),
    }
    return render(request, 'concerns/dashboard.html', context)


# ── Remark list ──────────────────────────────────────────────────────────

@login_required
def remark_list(request):
    bu = _get_school(request.user)
    if not bu:
        return HttpResponse('Not allowed. <a href="/">Home</a>')
    school = bu.school

    remarks = Remark.objects.filter(school=school, active=True).select_related(
        'student', 'teacher', 'grade', 'subject'
    ).order_by('-remark_date', '-created_at')

    # Filters
    category = request.GET.get('category')
    if category:
        remarks = remarks.filter(category=category)

    status = request.GET.get('status')
    if status:
        remarks = remarks.filter(status=status)

    severity = request.GET.get('severity')
    if severity:
        remarks = remarks.filter(severity=severity)

    grade_id = request.GET.get('grade')
    if grade_id:
        remarks = remarks.filter(grade_id=grade_id)

    teacher_id = request.GET.get('teacher')
    if teacher_id:
        remarks = remarks.filter(teacher_id=teacher_id)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        bs = _parse_bs_date(date_from)
        if bs:
            remarks = remarks.filter(remark_date__gte=bs)
    if date_to:
        bs = _parse_bs_date(date_to)
        if bs:
            remarks = remarks.filter(remark_date__lte=bs)

    # ── Export ─────────────────────────────────────────────────────────
    if request.GET.get('export') == 'csv':
        import csv
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="remarks.csv"'
        writer = csv.writer(response)
        writer.writerow(['Student', 'Reg No', 'Grade', 'Section', 'Subject', 'Category', 'Reason', 'Note',
                         'Severity', 'Visibility', 'Status', 'Teacher', 'Date'])
        for r in remarks:
            writer.writerow([
                r.student.name, r.student.reg_no,
                r.grade.grade_name if r.grade else '',
                r.section.section if r.section else '',
                r.subject.subject if r.subject else '',
                r.category, r.reason, r.note, r.severity, r.visibility, r.status,
                r.teacher.get_full_name() if r.teacher else '',
                r.remark_date,
            ])
        return response

    # ── Count cards ────────────────────────────────────────────────────
    base_qs = Remark.objects.filter(school=school, active=True)
    counts = {
        'total': base_qs.count(),
        'open': base_qs.filter(status='open').count(),
        'escalated': base_qs.filter(status='escalated').count(),
        'dismissed': base_qs.filter(status='dismissed').count(),
        'high_severity': base_qs.filter(severity='high').count(),
        'parent_visible': base_qs.filter(visibility='parent_visible').count(),
    }

    # ── Pagination ────────────────────────────────────────────────────
    from django.core.paginator import Paginator
    paginator = Paginator(remarks, 25)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)

    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('grade_weight')
    teachers = User.objects.filter(remarks_made__school=school, remarks_made__active=True).distinct()

    # Build query string for pagination links (strip page param)
    query_params = request.GET.copy()
    query_params.pop('page', '')
    query_string = query_params.urlencode()

    context = {
        'remarks': page_obj,
        'page_obj': page_obj,
        'counts': counts,
        'school': school,
        'grades': grades,
        'teachers': teachers,
        'selected_category': category or '',
        'selected_status': status or '',
        'selected_severity': severity or '',
        'selected_grade': grade_id or '',
        'selected_teacher': teacher_id or '',
        'date_from': date_from or '',
        'date_to': date_to or '',
        'query_string': query_string,
    }
    return render(request, 'concerns/remark_list.html', context)


# ── Remark detail API (for modal) ────────────────────────────────────────

@login_required
def remark_detail_api(request, pk):
    bu = _get_school(request.user)
    if not bu:
        return JsonResponse({'error': 'Not allowed'}, status=403)
    remark = get_object_or_404(Remark, pk=pk, school=bu.school, active=True)
    edit_logs = remark.edit_logs.select_related('changed_by').order_by('-changed_at')[:10]
    data = {
        'pk': remark.pk,
        'student_name': remark.student.name,
        'student_regno': remark.student.reg_no,
        'category': remark.category,
        'reason': remark.reason,
        'note': remark.note,
        'severity': remark.severity,
        'visibility': remark.visibility,
        'status': remark.status,
        'teacher': remark.teacher.get_full_name() or remark.teacher.username if remark.teacher else '—',
        'grade': remark.grade.grade_name if remark.grade else '—',
        'section': remark.section.section if remark.section else '',
        'subject': remark.subject.subject if remark.subject else '—',
        'remark_date': str(remark.remark_date),
        'created_at': remark.created_at.strftime('%Y-%m-%d %H:%M'),
        'edit_logs': [
            {
                'changed_by': log.changed_by.get_full_name() or log.changed_by.username if log.changed_by else '—',
                'field': log.field,
                'old_value': log.old_value,
                'new_value': log.new_value,
                'changed_at': log.changed_at.strftime('%Y-%m-%d %H:%M'),
            }
            for log in edit_logs
        ],
        'student_url': f'/concerns/student/{remark.student.reg_no}/',
        'convert_url': f'/concerns/remarks/{remark.pk}/convert/',
        'escalate_url': f'/concerns/remarks/{remark.pk}/escalate/',
        'dismiss_url': f'/concerns/remarks/{remark.pk}/dismiss/',
        'toggle_vis_url': f'/concerns/remarks/{remark.pk}/toggle-visibility/',
    }
    return JsonResponse(data)


# ── Remark add (admin) ───────────────────────────────────────────────────

@login_required
def remark_add(request):
    bu = _get_school(request.user)
    if not bu or not bu.admin_status:
        return HttpResponse('Admin only. <a href="/">Home</a>')
    school = bu.school
    session = EduSession.objects.filter(status=True).order_by('-year').first()

    if request.method == 'POST':
        student_regno = request.POST.get('student')
        category = request.POST.get('category', 'homework')
        reason = (request.POST.get('reason') or '').strip()
        note = (request.POST.get('note') or '').strip()
        severity = request.POST.get('severity', 'low')
        remark_date_str = request.POST.get('remark_date') or str(nepali_datetime.date.today())
        grade_id = request.POST.get('grade')
        section_id = request.POST.get('section')
        subject_id = request.POST.get('subject')

        student = get_object_or_404(Student, reg_no=student_regno, school=school)
        grade = get_object_or_404(SchoolGrade, id=grade_id, school=school)
        section = Section.objects.filter(id=section_id, grade=grade).first() if section_id else None
        subject = Subject.objects.filter(id=subject_id, session=session, branch=school).first() if subject_id else None
        bs_date = _parse_bs_date(remark_date_str) or nepali_datetime.date.today()

        remark = Remark.objects.create(
            school=school, session=session, student=student, teacher=request.user,
            grade=grade, section=section, subject=subject,
            category=category, reason=reason, note=note, severity=severity,
            remark_date=bs_date, visibility='private', status='open', active=True,
        )
        messages.success(request, f'Remark added for {student.name}.')
        return redirect('concerns:remark_list')

    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('grade_weight')
    templates = RemarkTemplate.objects.filter(school=school, active=True).order_by('category', 'sort_order')

    context = {
        'school': school, 'grades': grades,
        'templates': templates,
        'today_bs': str(nepali_datetime.date.today()),
    }
    return render(request, 'concerns/remark_add.html', context)


# ── Student search API (for remark add form) ─────────────────────────────

@login_required
def student_search_api(request):
    """Search students by name or reg_no — returns JSON for autocomplete."""
    bu = _get_school(request.user)
    if not bu:
        return JsonResponse({'results': []})
    school = bu.school
    query = (request.GET.get('q') or '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    session = EduSession.objects.filter(status=True).order_by('-year').first()
    qs = StudentSession.objects.filter(
        student__school=school,
        student__status=True,
        session=session,
        status=True,
    ).select_related('student', 'grade', 'section')

    if query.isdigit():
        qs = qs.filter(student__reg_no__icontains=query)
    else:
        qs = qs.filter(student__name__icontains=query)

    results = []
    for ss in qs[:20]:
        results.append({
            'reg_no': ss.student.reg_no,
            'name': ss.student.name,
            'grade_id': ss.grade_id,
            'grade_name': ss.grade.grade_name,
            'section_id': ss.section_id,
            'section_name': ss.section.section if ss.section else '',
            'roll_no': ss.roll_no,
        })
    return JsonResponse({'results': results})


@login_required
def student_detail_api(request):
    """Return a student's current grade, section, and available subjects."""
    bu = _get_school(request.user)
    if not bu:
        return JsonResponse({'error': 'Not allowed'}, status=403)
    school = bu.school
    regno = request.GET.get('regno')
    if not regno:
        return JsonResponse({'error': 'No reg_no'}, status=400)

    session = EduSession.objects.filter(status=True).order_by('-year').first()
    try:
        ss = StudentSession.objects.select_related('student', 'grade', 'section').get(
            student__reg_no=regno, student__school=school,
            session=session, status=True,
        )
    except StudentSession.DoesNotExist:
        return JsonResponse({'error': 'Student not found in current session'}, status=404)

    # Subjects available for this grade (and optionally section)
    subjects = Subject.objects.filter(
        session=session, branch=school, status=True,
        grade=ss.grade,
    ).select_related('grade')
    if ss.section:
        section_subjects = subjects.filter(section=ss.section)
        if section_subjects.exists():
            subjects = section_subjects

    subject_list = [
        {'id': s.id, 'name': s.subject}
        for s in subjects
    ]

    return JsonResponse({
        'reg_no': ss.student.reg_no,
        'name': ss.student.name,
        'grade_id': ss.grade_id,
        'grade_name': ss.grade.grade_name,
        'section_id': ss.section_id,
        'section_name': ss.section.section if ss.section else '',
        'roll_no': ss.roll_no,
        'subjects': subject_list,
    })


# ── Remark actions ──────────────────────────────────────────────────────

@login_required
@require_POST
def escalate_remark(request, pk):
    bu = _get_school(request.user)
    if not bu or not bu.admin_status:
        return HttpResponse('Not allowed.', status=403)
    remark = get_object_or_404(Remark, pk=pk, school=bu.school, active=True)
    old_status = remark.status
    remark.status = 'escalated'
    remark.save(update_fields=['status', 'updated_at'])
    RemarkEditLog.objects.create(remark=remark, changed_by=request.user,
        field='status', old_value=old_status, new_value='escalated')
    messages.success(request, f'Remark escalated for {remark.student.name}.')
    return redirect(request.META.get('HTTP_REFERER', 'concerns:remark_list'))


@login_required
@require_POST
def dismiss_remark(request, pk):
    bu = _get_school(request.user)
    if not bu or not bu.admin_status:
        return HttpResponse('Not allowed.', status=403)
    remark = get_object_or_404(Remark, pk=pk, school=bu.school, active=True)
    old_status = remark.status
    remark.status = 'dismissed'
    remark.save(update_fields=['status', 'updated_at'])
    RemarkEditLog.objects.create(remark=remark, changed_by=request.user,
        field='status', old_value=old_status, new_value='dismissed')
    messages.success(request, f'Remark dismissed for {remark.student.name}.')
    return redirect(request.META.get('HTTP_REFERER', 'concerns:remark_list'))


@login_required
@require_POST
def toggle_remark_visibility(request, pk):
    bu = _get_school(request.user)
    if not bu or not bu.admin_status:
        return HttpResponse('Not allowed.', status=403)
    remark = get_object_or_404(Remark, pk=pk, school=bu.school, active=True)
    old_vis = remark.visibility
    remark.visibility = 'parent_visible' if old_vis == 'private' else 'private'
    remark.save(update_fields=['visibility', 'updated_at'])
    RemarkEditLog.objects.create(remark=remark, changed_by=request.user,
        field='visibility', old_value=old_vis, new_value=remark.visibility)
    messages.success(request, f'Visibility toggled for {remark.student.name}.')
    return redirect(request.META.get('HTTP_REFERER', 'concerns:remark_list'))


@login_required
@require_POST
def convert_remark_to_concern(request, pk):
    """Convert an escalated remark into a formal Concern."""
    bu = _get_school(request.user)
    if not bu or not bu.admin_status:
        return HttpResponse('Not allowed.', status=403)
    remark = get_object_or_404(Remark, pk=pk, school=bu.school, active=True)

    # Check if a concern already exists from this remark
    if remark.concerns.exists():
        existing = remark.concerns.first()
        messages.info(request, f'A concern already exists from this remark: {existing.title}')
        return redirect('concerns:concern_detail', pk=existing.pk)

    concern = Concern.objects.create(
        school=bu.school, session=remark.session, student=remark.student,
        grade=remark.grade, section=remark.section, source_remark=remark,
        title=f"{remark.category.title()} concern — {remark.reason or 'General'}",
        description=remark.note or f"Escalated from remark dated {remark.remark_date}",
        category=remark.category, status='open',
        assigned_to=request.user, created_by=request.user,
    )
    # Mark remark as escalated
    if remark.status == 'open':
        old_status = remark.status
        remark.status = 'escalated'
        remark.save(update_fields=['status', 'updated_at'])
        RemarkEditLog.objects.create(remark=remark, changed_by=request.user,
            field='status', old_value=old_status, new_value='escalated')

    messages.success(request, f'Remark converted to concern for {remark.student.name}.')
    return redirect('concerns:concern_detail', pk=concern.pk)


# ── Concern views ────────────────────────────────────────────────────────

@login_required
def concern_list(request):
    bu = _get_school(request.user)
    if not bu or not bu.admin_status:
        return HttpResponse('Admin only. <a href="/">Home</a>')

    concerns = Concern.objects.filter(school=bu.school).select_related(
        'student', 'assigned_to', 'source_remark', 'created_by'
    ).order_by('-created_at')

    status = request.GET.get('status')
    if status:
        concerns = concerns.filter(status=status)

    category = request.GET.get('category')
    if category:
        concerns = concerns.filter(category=category)

    teacher_id = request.GET.get('teacher')
    if teacher_id:
        concerns = concerns.filter(created_by_id=teacher_id)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        try:
            from datetime import datetime as dt
            d = dt.strptime(date_from, '%Y-%m-%d')
            concerns = concerns.filter(created_at__date__gte=d.date())
        except ValueError:
            pass
    if date_to:
        try:
            from datetime import datetime as dt
            d = dt.strptime(date_to, '%Y-%m-%d')
            concerns = concerns.filter(created_at__date__lte=d.date())
        except ValueError:
            pass

    search = request.GET.get('q')
    if search:
        concerns = concerns.filter(
            Q(student__name__icontains=search) |
            Q(student__reg_no__icontains=search) |
            Q(title__icontains=search)
        )

    # ── Export ─────────────────────────────────────────────────────────
    if request.GET.get('export') == 'csv':
        import csv
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="concerns.csv"'
        writer = csv.writer(response)
        writer.writerow(['Student', 'Reg No', 'Grade', 'Title', 'Category', 'Status',
                         'Assigned To', 'Created By', 'Source', 'Created At', 'Description'])
        for c in concerns:
            writer.writerow([
                c.student.name, c.student.reg_no,
                c.grade.grade_name if c.grade else '',
                c.title, c.category, c.status,
                c.assigned_to.get_full_name() if c.assigned_to else '',
                c.created_by.get_full_name() if c.created_by else '',
                'Remark' if c.source_remark_id else 'Direct',
                c.created_at.strftime('%Y-%m-%d %H:%M'),
                c.description,
            ])
        return response

    # ── Count cards ────────────────────────────────────────────────────
    base_qs = Concern.objects.filter(school=bu.school)
    counts = {
        'total': base_qs.count(),
        'open': base_qs.filter(status='open').count(),
        'in_progress': base_qs.filter(status='in_progress').count(),
        'awaiting_parent': base_qs.filter(status='awaiting_parent').count(),
        'resolved': base_qs.filter(status='resolved').count(),
        'closed': base_qs.filter(status='closed').count(),
        'dismissed': base_qs.filter(status='dismissed').count(),
    }

    # ── Pagination ────────────────────────────────────────────────────
    from django.core.paginator import Paginator
    paginator = Paginator(concerns, 25)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)

    teachers = User.objects.filter(concerns_created__school=bu.school).distinct()

    query_params = request.GET.copy()
    query_params.pop('page', '')
    query_string = query_params.urlencode()

    context = {
        'concerns': page_obj,
        'page_obj': page_obj,
        'counts': counts,
        'school': bu.school, 'teachers': teachers,
        'selected_status': status or '', 'selected_category': category or '',
        'selected_teacher': teacher_id or '',
        'date_from': date_from or '', 'date_to': date_to or '',
        'search_q': search or '',
        'query_string': query_string,
    }
    return render(request, 'concerns/concern_list.html', context)


@login_required
def concern_detail(request, pk):
    bu = _get_school(request.user)
    if not bu or not bu.admin_status:
        return HttpResponse('Admin only. <a href="/">Home</a>')
    concern = get_object_or_404(Concern, pk=pk, school=bu.school)
    comms = concern.communications.select_related('author').order_by('-created_at')
    context = {'concern': concern, 'comms': comms, 'school': bu.school}
    return render(request, 'concerns/concern_detail.html', context)


@login_required
def concern_detail_api(request, pk):
    """JSON detail for modal display."""
    bu = _get_school(request.user)
    if not bu:
        return JsonResponse({'error': 'Not allowed'}, status=403)
    concern = get_object_or_404(Concern, pk=pk, school=bu.school)
    comms = concern.communications.select_related('author').order_by('-created_at')
    data = {
        'pk': concern.pk,
        'title': concern.title,
        'student_name': concern.student.name,
        'student_regno': concern.student.reg_no,
        'category': concern.category,
        'status': concern.status,
        'assigned_to': concern.assigned_to.get_full_name() if concern.assigned_to else 'Unassigned',
        'created_by': concern.created_by.get_full_name() if concern.created_by else '—',
        'created_at': concern.created_at.strftime('%Y-%m-%d %H:%M'),
        'description': concern.description,
        'source_remark_pk': concern.source_remark_id,
        'student_url': f'/concerns/student/{concern.student.reg_no}/',
        'detail_url': f'/concerns/concerns/{concern.pk}/',
        'status_url': f'/concerns/concerns/{concern.pk}/status/',
        'comm_url': f'/concerns/concerns/{concern.pk}/comm/',
        'communications': [
            {
                'direction': comm.direction,
                'channel': comm.channel,
                'author': comm.author.get_full_name() if comm.author else '—',
                'message': comm.message,
                'created_at': comm.created_at.strftime('%Y-%m-%d %H:%M'),
            }
            for comm in comms
        ],
    }
    return JsonResponse(data)


@login_required
@require_POST
def concern_update_status(request, pk):
    bu = _get_school(request.user)
    if not bu or not bu.admin_status:
        return HttpResponse('Not allowed.', status=403)
    concern = get_object_or_404(Concern, pk=pk, school=bu.school)
    new_status = request.POST.get('status', concern.status)
    if new_status in dict(Concern.CONCERN_STATUS_CHOICES):
        concern.status = new_status
        if new_status in ('resolved', 'closed'):
            concern.resolved_at = timezone.now()
        concern.save()
        messages.success(request, f'Status updated to {new_status}.')
    return redirect(request.META.get('HTTP_REFERER', f'/concerns/concerns/{pk}/'))


@login_required
@require_POST
def concern_add_comm(request, pk):
    bu = _get_school(request.user)
    if not bu or not bu.admin_status:
        return HttpResponse('Not allowed.', status=403)
    concern = get_object_or_404(Concern, pk=pk, school=bu.school)
    msg = (request.POST.get('message') or '').strip()
    channel = request.POST.get('channel', 'app')
    if msg:
        CommunicationLog.objects.create(concern=concern, author=request.user,
            direction='outbound', channel=channel, message=msg)
        messages.success(request, 'Communication logged.')
    return redirect(request.META.get('HTTP_REFERER', f'/concerns/concerns/{pk}/'))


# ── Concern add (admin) ───────────────────────────────────────────────────

@login_required
def concern_add(request):
    bu = _get_school(request.user)
    if not bu or not bu.admin_status:
        return HttpResponse('Admin only. <a href="/">Home</a>')
    school = bu.school
    session = EduSession.objects.filter(status=True).order_by('-year').first()

    if request.method == 'POST':
        student_regno = request.POST.get('student')
        category = request.POST.get('category', 'homework')
        title = (request.POST.get('title') or '').strip()
        description = (request.POST.get('description') or '').strip()
        grade_id = request.POST.get('grade')
        section_id = request.POST.get('section')

        student = get_object_or_404(Student, reg_no=student_regno, school=school)
        grade = get_object_or_404(SchoolGrade, id=grade_id, school=school)
        section = Section.objects.filter(id=section_id, grade=grade).first() if section_id else None

        concern = Concern.objects.create(
            school=school, session=session, student=student,
            grade=grade, section=section, title=title, description=description,
            category=category, status='open',
            assigned_to=request.user, created_by=request.user,
        )
        messages.success(request, f'Concern created for {student.name}.')
        return redirect('concerns:concern_detail', pk=concern.pk)

    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('grade_weight')
    students = Student.objects.filter(school=school, status=True).values('reg_no', 'name').order_by('name')[:500]

    context = {'school': school, 'grades': grades, 'students': list(students)}
    return render(request, 'concerns/concern_add.html', context)


# ── Per-student concerns ──────────────────────────────────────────────────

@login_required
def student_concerns(request, regno):
    bu = _get_school(request.user)
    if not bu:
        return HttpResponse('Not allowed. <a href="/">Home</a>')
    school = bu.school
    student = get_object_or_404(Student, reg_no=regno, school=school)

    remarks = Remark.objects.filter(
        student=student, school=school, active=True
    ).select_related('teacher', 'grade', 'subject').order_by('-remark_date', '-created_at')

    concerns = Concern.objects.filter(
        student=student, school=school
    ).select_related('assigned_to', 'source_remark', 'created_by').order_by('-created_at')

    status = request.GET.get('status')
    if status:
        remarks = remarks.filter(status=status)
        concerns = concerns.filter(status=status)

    category = request.GET.get('category')
    if category:
        remarks = remarks.filter(category=category)
        concerns = concerns.filter(category=category)

    current_session_id = request.session.get('active_session_id')
    student_session = None
    if current_session_id:
        student_session = StudentSession.objects.filter(
            student=student, session_id=current_session_id
        ).select_related('grade', 'section').first()

    context = {
        'student': student, 'student_session': student_session,
        'remarks': remarks, 'concerns': concerns, 'school': school,
        'remark_count': remarks.count(), 'concern_count': concerns.count(),
        'selected_status': request.GET.get('status', ''),
        'selected_category': request.GET.get('category', ''),
        'is_admin': bu.admin_status,
    }
    return render(request, 'concerns/student_concerns.html', context)


# ── Templates management ─────────────────────────────────────────────────

@login_required
def template_list(request):
    bu = _get_school(request.user)
    if not bu or not bu.admin_status:
        return HttpResponse('Admin only. <a href="/">Home</a>')
    templates = RemarkTemplate.objects.filter(school=bu.school).order_by('category', 'sort_order')

    # Collect custom categories (those not in the predefined list)
    predefined = {'homework', 'behavior', 'cleanliness', 'regularity', 'other'}
    used_categories = set(
        templates.values_list('category', flat=True).distinct()
    )
    custom_categories = sorted(used_categories - predefined)

    context = {
        'templates': templates,
        'school': bu.school,
        'custom_categories': custom_categories,
    }
    return render(request, 'concerns/template_list.html', context)


@login_required
def template_add(request):
    bu = _get_school(request.user)
    if not bu or not bu.admin_status:
        return HttpResponse('Admin only.', status=403)
    if request.method == 'POST':
        category = request.POST.get('category', 'homework')
        # Handle custom category from the text input
        category_custom = request.POST.get('category_custom', '').strip()
        if category == '__custom__' and category_custom:
            category = category_custom.lower().replace(' ', '_')
        text = (request.POST.get('text') or '').strip()
        sort_order = int(request.POST.get('sort_order', 0))
        if text and category:
            RemarkTemplate.objects.get_or_create(
                school=bu.school, category=category, text=text,
                defaults={'sort_order': sort_order, 'active': True}
            )
            messages.success(request, f'Template added under {category}.')
        return redirect('concerns:template_list')
    return redirect('concerns:template_list')


@login_required
@require_POST
def template_delete(request, pk):
    bu = _get_school(request.user)
    if not bu or not bu.admin_status:
        return HttpResponse('Not allowed.', status=403)
    template = get_object_or_404(RemarkTemplate, pk=pk, school=bu.school)
    template.active = False
    template.save(update_fields=['active'])
    messages.success(request, f'Template "{template.text}" deactivated.')
    return redirect('concerns:template_list')
