import json
from collections import defaultdict
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from nepali_datetime import date as nepali_date

from panel.views import get_current_session
from sms.models import (
    BranchUser,
    EduSession,
    GradeLevel,
    Homework,
    SchoolBranch,
    SchoolGrade,
    Section,
    Subject,
)

from .models import HomeworkEntry, HomeworkTemplate, HomeworkComplain


def _parse_hw_json(hw_json_str):
    """
    Parse Homework.homework JSON blob into per-subject data.

    Handles all three formats written over time:
    1. Old section-keyed:  {subject_id: {section_id: {teacher_name, text}}}
    2. Current webview:    {subject_id: {teacher_user_id: {teacher_name, text}}}
    3. Flat (grihakarya):  {subject_id: "text"}

    Returns dict: {subject_id_str: {'text': str, 'teachers': [{'teacher_name': str, 'user_id': str}]}}
    """
    try:
        data = json.loads(hw_json_str)
    except (json.JSONDecodeError, TypeError):
        return {}

    result = {}
    for subj_id, value in data.items():
        if isinstance(value, str):
            # Flat format
            result[subj_id] = {'text': value, 'teachers': []}
        elif isinstance(value, dict):
            if 'text' in value:
                # Direct leaf: {teacher_name, text}
                result[subj_id] = {
                    'text': value.get('text', ''),
                    'teachers': [{'teacher_name': value.get('teacher_name', ''), 'user_id': ''}],
                }
            else:
                # Nested by teacher_user_id OR section_id — either way same structure
                # Merge all sub-entries into combined text + list of teachers
                texts = []
                teachers = []
                for sub_key, sub_val in value.items():
                    if isinstance(sub_val, dict) and sub_val.get('text'):
                        texts.append(sub_val['text'])
                        teachers.append({'teacher_name': sub_val.get('teacher_name', ''), 'user_id': sub_key})
                    elif isinstance(sub_val, str) and sub_val:
                        texts.append(sub_val)
                # Use first text (teachers often enter same homework for a subject)
                combined_text = texts[0] if texts else ''
                result[subj_id] = {'text': combined_text, 'teachers': teachers}
    return result

def _parse_bs_date(date_str):
    """Parse a Nepali date string (YYYY-MM-DD) into a nepali_date.date, or None."""
    if not date_str:
        return None
    try:
        parts = [int(p) for p in str(date_str).split('-')]
        if len(parts) != 3:
            return None
        return nepali_date(parts[0], parts[1], parts[2])
    except (ValueError, TypeError):
        return None


@login_required
def grihakarya_homework_dashboard(request):
    """Grihakarya homework dashboard.

    GET: render homework for a specific date (default today), with date switching.
    POST (admin only): create a Homework + normalized HomeworkEntry records.
    """
    user = request.user
    try:
        branchuser = BranchUser.objects.select_related('school').get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. '
            'Click <a href="/">Here</a> to go the homepage.'
        )

    school = branchuser.school
    is_admin = branchuser.admin_status
    current_session = get_current_session()
    today_bs = nepali_date.today()

    if not current_session:
        messages.error(request, 'No active session found. Please set a session first.')
        return redirect('panel:index')

    # ---- Date switching ----
    selected_bs = _parse_bs_date(request.GET.get('date')) or today_bs
    print_all = request.GET.get('print', '').lower() == 'all'

    grades = SchoolGrade.objects.filter(session=current_session, school=school, active=True).order_by('grade_weight')
    sections = Section.objects.filter(session=current_session, school=school).select_related('grade').order_by('grade__grade_weight', 'section')
    subjects = Subject.objects.filter(session=current_session, branch=school, status=True).select_related('grade')

    # ---- POST: create homework (admin only) ----
    add_form_open = False
    if request.method == 'POST':
        if not is_admin:
            messages.error(request, 'Only administrators can add homework.')
            return redirect('grihakarya:dashboard')

        add_form_open = True
        grade_id = request.POST.get('grade')
        section_id = request.POST.get('section') or None
        nepali_date_str = request.POST.get('nepali_date') or str(selected_bs)

        homework_bs = _parse_bs_date(nepali_date_str) or selected_bs

        try:
            grade = SchoolGrade.objects.get(id=grade_id, session=current_session, school=school)
        except (SchoolGrade.DoesNotExist, ValueError):
            messages.error(request, 'Invalid grade.')
            add_form_open = True
            return render(request, 'grihakarya/homework_dashboard.html', _build_context(
                request, branchuser, school, is_admin, current_session, selected_bs,
                grades, sections, subjects, add_form_open=add_form_open,
                selected_grade_id=grade_id, selected_section_id=section_id,
                selected_nepali_date=str(nepali_date_str),
            ))

        section_obj = None
        if section_id:
            try:
                section_obj = Section.objects.get(id=section_id, grade=grade, session=current_session, school=school)
            except (Section.DoesNotExist, ValueError):
                messages.error(request, 'Invalid section.')
                add_form_open = True
                return render(request, 'grihakarya/homework_dashboard.html', _build_context(
                    request, branchuser, school, is_admin, current_session, selected_bs,
                    grades, sections, subjects, add_form_open=add_form_open,
                    selected_grade_id=grade_id, selected_section_id=section_id,
                    selected_nepali_date=str(nepali_date_str),
                ))

        # Collect subject -> text rows from dynamic form fields.
        hw_json = {}
        entry_rows = []
        subject_ids = [k for k in request.POST if k.startswith('subject_')]
        for key in subject_ids:
            try:
                subject_id = int(key.split('_', 1)[1])
            except ValueError:
                continue
            text = (request.POST.get(key) or '').strip()
            if not text:
                continue
            try:
                subject = Subject.objects.get(id=subject_id, session=current_session, branch=school, status=True)
            except Subject.DoesNotExist:
                continue
            if subject.grade_id != grade.id:
                continue
            hw_json[str(subject.id)] = text
            entry_rows.append((subject, text))

        if not hw_json:
            messages.error(request, 'Enter homework text for at least one subject.')
            add_form_open = True
            return render(request, 'grihakarya/homework_dashboard.html', _build_context(
                request, branchuser, school, is_admin, current_session, selected_bs,
                grades, sections, subjects, add_form_open=add_form_open,
                selected_grade_id=grade_id, selected_section_id=section_id,
                selected_nepali_date=str(nepali_date_str),
            ))

        # Determine if admin is acting as a teacher (impersonation)
        teacher_name_input = (request.POST.get('teacher_name') or '').strip()
        is_impersonated = bool(teacher_name_input)
        display_teacher = teacher_name_input or request.user.get_full_name() or request.user.username

        # Optional due date (vacation homework)
        due_date_str = (request.POST.get('due_date') or '').strip()
        due_date_bs = _parse_bs_date(due_date_str) if due_date_str else None

        # Find existing homework for this date/grade/section (modal edit) or create new.
        homework, created = Homework.objects.update_or_create(
            session=current_session,
            grade=grade,
            section=section_obj,
            nepali_date=homework_bs,
            defaults={
                'homework': json.dumps(hw_json),
                'date': homework_bs.to_datetime_date(),
                'due_date': due_date_bs,
            },
        )
        # Upsert entries per subject, recording who added them.
        for subject, text in entry_rows:
            HomeworkEntry.objects.update_or_create(
                homework=homework,
                subject=subject,
                defaults={
                    'homework_text': text,
                    'added_by': request.user,
                    'teacher_name': display_teacher,
                    'is_impersonated': is_impersonated,
                },
            )
        # Remove entries for subjects no longer in the form.
        existing_subject_ids = {s[0].id for s in entry_rows}
        homework.entries.exclude(subject_id__in=existing_subject_ids).delete()

        messages.success(request, 'Homework saved successfully.')
        return redirect(f"{request.path}?date={homework_bs}")

    # ---- GET: build dashboard data ----
    if print_all:
        pass  # handled below

    # Active vacation/long-term homework: assigned BEFORE selected date, due ON/AFTER selected date.
    active_vacation_hw = (
        Homework.objects
        .filter(
            session=current_session,
            grade__school=school,
            due_date__gte=selected_bs,       # due date is today or in the future
        )
        .exclude(nepali_date=selected_bs)     # not today's regular homework (already shown below)
        .select_related('grade', 'section')
        .order_by('due_date', 'grade__grade_weight')
    )
    # Parse those into same section-card-like structure for display
    all_subjects_map_vacation = {str(s.id): s for s in subjects}
    vacation_cards = []
    for hw in active_vacation_hw:
        parsed = _parse_hw_json(hw.homework)
        entries = []
        for subj_id_str, data in parsed.items():
            subj = all_subjects_map_vacation.get(subj_id_str)
            if not subj:
                continue
            text = data.get('text', '') if isinstance(data, dict) else data
            if not text:
                continue
            teachers = data.get('teachers', []) if isinstance(data, dict) else []
            entries.append({'subject': subj, 'homework_text': text, 'teachers': teachers})
        entries.sort(key=lambda e: e['subject'].subject)
        vacation_cards.append({
            'homework': hw,
            'grade': hw.grade,
            'section': hw.section,
            'assigned_date': str(hw.nepali_date),
            'due_date': str(hw.due_date),
            'entries': entries,
        })

    if print_all:
        # ---- Excel export ----
        if request.GET.get('export') == 'excel':
            try:
                import openpyxl
                from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
                from django.http import HttpResponse
            except ImportError:
                messages.error(request, 'openpyxl is not installed. Cannot export to Excel.')
                return redirect(f"{request.path}?date={selected_gs}")

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Homework"

            header_fill = PatternFill(start_color="008877", end_color="008877", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")
            thin = Side(style="thin", color="999999")
            border = Border(left=thin, right=thin, top=thin, bottom=thin)

            headers = ["Date (BS)", "Date (AD)", "Grade", "Section", "Subject", "Homework"]
            ws.append(headers)
            for col in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")
                cell.border = border

            date_from = _parse_bs_date(request.GET.get('date_from'))
            date_to = _parse_bs_date(request.GET.get('date_to'))
            filter_grade_id = request.GET.get('grade') or None
            filter_section_id = request.GET.get('section') or None

            qs = (
                Homework.objects
                .filter(session=current_session, grade__school=school)
                .select_related('grade', 'section')
                .order_by('nepali_date', 'grade__grade_weight', 'section__section')
            )
            if date_from:
                qs = qs.filter(nepali_date__gte=date_from)
            if date_to:
                qs = qs.filter(nepali_date__lte=date_to)
            if filter_grade_id:
                qs = qs.filter(grade_id=filter_grade_id)
            if filter_section_id:
                qs = qs.filter(section_id=filter_section_id)

            for hw in qs:
                for entry in hw.entries.select_related('subject').all():
                    row = [
                        str(hw.nepali_date),
                        hw.nepali_date.to_datetime_date().isoformat(),
                        hw.grade.grade_name,
                        hw.section.section if hw.section else "",
                        entry.subject.subject,
                        entry.homework_text,
                    ]
                    ws.append(row)
                    for col in range(1, len(headers) + 1):
                        cell = ws.cell(row=ws.max_row, column=col)
                        cell.border = border
                        cell.alignment = Alignment(wrap_text=True, vertical="top")

            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = f'attachment; filename="grihakarya_homework_{selected_gs}.xlsx"'
            wb.save(response)
            return response

        # ---- Print All with filters ----
        date_from = _parse_bs_date(request.GET.get('date_from'))
        date_to = _parse_bs_date(request.GET.get('date_to'))
        filter_grade_id = request.GET.get('grade') or None
        filter_section_id = request.GET.get('section') or None

        # Default: show today's date range (single day) if no dates specified
        if date_from is None and date_to is None:
            date_from = selected_bs
            date_to = selected_bs

        qs = (
            Homework.objects
            .filter(session=current_session, grade__school=school)
            .select_related('grade', 'section')
            .order_by('nepali_date', 'grade__grade_weight', 'section__section')
        )
        if date_from:
            qs = qs.filter(nepali_date__gte=date_from)
        if date_to:
            qs = qs.filter(nepali_date__lte=date_to)
        if filter_grade_id:
            qs = qs.filter(grade_id=filter_grade_id)
        if filter_section_id:
            qs = qs.filter(section_id=filter_section_id)

        # Group by date -> grade -> section -> entries.
        all_homework_map = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        for hw in qs:
            entries = hw.entries.select_related('subject').all()
            hw_date_str = str(hw.nepali_date)
            all_homework_map[hw_date_str][hw.grade][hw.section].extend(entries)

        print_dates = []
        for hw_date_str in sorted(all_homework_map.keys(), reverse=True):
            date_grades = []
            for grade in grades:
                grade_sections = all_homework_map.get(hw_date_str, {}).get(grade, {})
                if not grade_sections:
                    continue
                for section, entries in grade_sections.items():
                    date_grades.append({
                        'grade': grade,
                        'section': section,
                        'nepali_date': hw_date_str,
                        'entries': entries,
                    })
            print_dates.append({
                'date': hw_date_str,
                'classes': date_grades,
            })

        total_entries = sum(len(d['classes']) for d in print_dates)

        context = _build_context(
            request, branchuser, school, is_admin, current_session, selected_bs,
            grades, sections, subjects,
            today_list=[],
            missing_classes=[],
            missing_subjects=[],
            add_form_open=False,
            date_from=date_from,
            date_to=date_to,
            filter_grade_id=filter_grade_id,
            filter_section_id=filter_section_id,
        )
        context.update({
            'print_all': True,
            'print_dates': print_dates,
            'print_total_entries': total_entries,
            'vacation_cards': [],
            'stats': {
                'total_classes': len(grades),
                'classes_with_hw': len(print_dates),
                'classes_missing_hw': 0,
                'classes_pct': 0,
                'total_subjects': subjects.count(),
                'subjects_with_hw': 0,
                'subjects_missing_hw': 0,
                'subjects_pct': 0,
                'total_entries': total_entries,
            },
        })
        return render(request, 'grihakarya/homework_dashboard.html', context)

    homeworks = (
        Homework.objects
        .filter(session=current_session, grade__school=school, nepali_date=selected_bs)
        .select_related('grade', 'section')
        .order_by('grade__grade_weight', 'section__section')
    )

    # Build a map: (grade, section) -> {subject_id_str: {text, teachers}}
    # Reading directly from Homework.homework JSON — no HomeworkEntry needed.
    all_subjects_map = {str(s.id): s for s in subjects}
    hw_json_map = {}  # (grade.id, section.id) -> parsed dict
    for hw in homeworks:
        parsed = _parse_hw_json(hw.homework)
        hw_json_map[(hw.grade.id, hw.section_id)] = parsed

    classes_with_hw = set(hw_json_map.keys())

    all_classes = []
    for grade in grades:
        grade_sections = [s for s in sections if s.grade_id == grade.id]
        for section in grade_sections:
            all_classes.append({
                'grade': grade,
                'section': section,
                'has_homework': (grade.id, section.id) in classes_with_hw,
            })

    missing_classes = [c for c in all_classes if not c['has_homework']]

    # Per-section subject coverage for compact cards.
    section_cards = []
    for grade in grades:
        grade_subjects = list(subjects.filter(grade=grade).order_by('subject'))
        grade_sections = [s for s in sections if s.grade_id == grade.id]
        for section in grade_sections:
            parsed = hw_json_map.get((grade.id, section.id), {})
            subject_rows = []
            completed = 0
            for s in grade_subjects:
                entry = parsed.get(str(s.id), {})
                text = entry.get('text', '') if isinstance(entry, dict) else ''
                teachers = entry.get('teachers', []) if isinstance(entry, dict) else []
                if text:
                    completed += 1
                subject_rows.append({
                    'subject': s,
                    'existing_text': text,
                    'teachers': teachers,
                })
            missing = len(grade_subjects) - completed
            if len(grade_subjects) == 0:
                status = 'none'
            elif completed == len(grade_subjects):
                status = 'complete'
            elif completed > 0:
                status = 'partial'
            else:
                status = 'none'
            section_cards.append({
                'grade': grade,
                'section': section,
                'total_subjects': len(grade_subjects),
                'completed_subjects': completed,
                'missing_subjects': missing,
                'status': status,
                'subject_rows': subject_rows,
            })

    # today_list for stats
    today_list = []
    for hw in homeworks:
        parsed = hw_json_map.get((hw.grade.id, hw.section_id), {})
        total_entries = sum(1 for v in parsed.values() if (isinstance(v, dict) and v.get('text')) or isinstance(v, str))
        today_list.append({'grade': hw.grade, 'section': hw.section, 'nepali_date': str(selected_bs), 'entries': [None] * total_entries})

    context = _build_context(
        request, branchuser, school, is_admin, current_session, selected_bs,
        grades, sections, subjects,
        today_list=today_list,
        missing_classes=missing_classes,
        missing_subjects=[],
        add_form_open=add_form_open,
    )
    # Add summary stats.
    total_classes = len(all_classes)
    classes_with_hw_count = total_classes - len(missing_classes)
    total_subjects_count = subjects.count()
    subjects_with_hw_count = sum(c['completed_subjects'] for c in section_cards)
    total_entries = sum(len(day['entries']) for day in today_list)
    classes_pct = round((classes_with_hw_count / total_classes * 100), 1) if total_classes > 0 else 0
    subjects_pct = round((subjects_with_hw_count / total_subjects_count * 100), 1) if total_subjects_count > 0 else 0

    # Group section_cards by grade level (mirrors attendance cards_by_level).
    grade_levels = GradeLevel.objects.filter(
        schoolgrade__school=school, schoolgrade__active=True
    ).distinct().order_by('id')
    cards_by_level = []
    for level in grade_levels:
        level_cards = [c for c in section_cards if c['grade'].level_id == level.id]
        if level_cards:
            cards_by_level.append({'level': level, 'cards': level_cards})

    context.update({
        'stats': {
            'total_classes': total_classes,
            'classes_with_hw': classes_with_hw_count,
            'classes_missing_hw': len(missing_classes),
            'classes_pct': classes_pct,
            'total_subjects': total_subjects_count,
            'subjects_with_hw': subjects_with_hw_count,
            'subjects_missing_hw': total_subjects_count - subjects_with_hw_count,
            'subjects_pct': subjects_pct,
            'total_entries': total_entries,
        },
        'section_cards': section_cards,
        'cards_by_level': cards_by_level,
        'vacation_cards': vacation_cards,
    })
    return render(request, 'grihakarya/homework_dashboard.html', context)


def _build_context(request, branchuser, school, is_admin, current_session, selected_bs,
                   grades, sections, subjects, today_list=None, missing_classes=None,
                   missing_subjects=None, add_form_open=False,
                   selected_grade_id=None, selected_section_id=None, selected_nepali_date=None,
                   print_all=False, date_from=None, date_to=None,
                   filter_grade_id=None, filter_section_id=None):
    """Build shared context for grihakarya views."""
    # Prev/next available dates that have homeworks.
    all_homework_dates = list(
        Homework.objects
        .filter(session=current_session, grade__school=school)
        .order_by('nepali_date')
        .values_list('nepali_date', flat=True)
        .distinct()
    )
    date_objs = [d for d in all_homework_dates if d is not None]
    prev_date = next_date = None
    for i, d in enumerate(date_objs):
        if d == selected_bs:
            if i > 0:
                prev_date = date_objs[i - 1]
            if i < len(date_objs) - 1:
                next_date = date_objs[i + 1]
            break

    ctx = {
        'branchuser': branchuser,
        'school': school,
        'current_session': current_session,
        'is_admin': is_admin,
        'today_bs': nepali_date.today(),
        'today_gs': nepali_date.today().to_datetime_date().isoformat(),
        'selected_bs': selected_bs,
        'selected_gs': selected_bs.to_datetime_date().isoformat(),
        'grades': grades,
        'sections': sections,
        'subjects': subjects,
        'today_list': today_list if today_list is not None else [],
        'missing_classes': missing_classes if missing_classes is not None else [],
        'missing_subjects': missing_subjects if missing_subjects is not None else [],
        'add_form_open': add_form_open,
        'prev_date': prev_date,
        'next_date': next_date,
        'selected_grade_id': selected_grade_id or '',
        'selected_section_id': selected_section_id or '',
        'selected_nepali_date': selected_nepali_date or str(selected_bs),
        'print_all': print_all,
        'print_date_from': date_from,
        'print_date_to': date_to,
        'print_filter_grade': filter_grade_id or '',
        'print_filter_section': filter_section_id or '',
    }
    return ctx


@login_required
def grihakarya_homework_list(request):
    """List all homeworks grouped by class, with full subject/homework detail per class."""
    user = request.user
    try:
        branchuser = BranchUser.objects.select_related('school').get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse('Sorry! Not allowed. <a href="/">Home</a>')

    school = branchuser.school
    is_admin = branchuser.admin_status
    current_session = get_current_session()
    today_bs = nepali_date.today()

    if not current_session:
        messages.error(request, 'No active session found.')
        return redirect('panel:index')

    all_dates = list(
        Homework.objects
        .filter(session=current_session, grade__school=school)
        .order_by('-nepali_date')
        .values_list('nepali_date', flat=True)
        .distinct()
    )
    date_objs = [d for d in all_dates if d is not None]

    selected_bs = _parse_bs_date(request.GET.get('date'))
    if selected_bs is None:
        selected_bs = date_objs[0] if date_objs else today_bs

    subjects_qs = Subject.objects.filter(session=current_session, branch=school, status=True).select_related('grade')
    all_subjects_map = {str(s.id): s for s in subjects_qs}

    homeworks = (
        Homework.objects
        .filter(session=current_session, grade__school=school, nepali_date=selected_bs)
        .select_related('grade', 'section')
        .order_by('grade__grade_weight', 'section__section')
    )

    # Build detailed class rows — use HomeworkEntry for teacher info when available,
    # fall back to JSON-embedded teacher data for homeworks added via other channels.
    hw_ids = [hw.pk for hw in homeworks]
    entries_qs = (
        HomeworkEntry.objects
        .filter(homework_id__in=hw_ids)
        .select_related('subject', 'added_by')
    )
    # Build lookup: homework_id -> subject_id -> entry
    entry_lookup = {}
    for e in entries_qs:
        entry_lookup.setdefault(e.homework_id, {})[e.subject_id] = e

    class_rows = []
    for hw in homeworks:
        parsed = _parse_hw_json(hw.homework)
        hw_entries = entry_lookup.get(hw.pk, {})
        entries = []
        for subj_id_str, data in parsed.items():
            subj = all_subjects_map.get(subj_id_str)
            if subj is None:
                continue
            text = data.get('text', '') if isinstance(data, dict) else data
            if not text:
                continue

            # Prefer HomeworkEntry teacher info over JSON-embedded info
            db_entry = hw_entries.get(subj.id)
            if db_entry:
                teacher_display = db_entry.teacher_name or (
                    db_entry.added_by.get_full_name() or db_entry.added_by.username
                    if db_entry.added_by else '—'
                )
                is_impersonated = db_entry.is_impersonated
                teachers = [{'teacher_name': teacher_display}]
                entry_pk = db_entry.pk
            else:
                # No HomeworkEntry yet — derive teacher info from JSON blob.
                json_teachers = data.get('teachers', []) if isinstance(data, dict) else []
                teachers = json_teachers
                is_impersonated = False

                # For admin view: auto-create a HomeworkEntry so the edit button works.
                if is_admin:
                    # Pick best teacher name from JSON if available.
                    json_teacher_name = json_teachers[0].get('teacher_name', '') if json_teachers else ''
                    db_entry, _ = HomeworkEntry.objects.get_or_create(
                        homework=hw,
                        subject=subj,
                        defaults={
                            'homework_text': text,
                            'added_by': None,
                            'teacher_name': json_teacher_name,
                            'is_impersonated': False,
                        },
                    )
                    entry_pk = db_entry.pk
                    # Use the newly created entry's teacher name if available.
                    if db_entry.teacher_name:
                        teachers = [{'teacher_name': db_entry.teacher_name}]
                else:
                    entry_pk = None

            entries.append({
                'subject': subj,
                'homework_text': text,
                'teachers': teachers,
                'is_impersonated': is_impersonated,
                'entry_pk': entry_pk,
                'homework_pk': hw.pk,
            })
        entries.sort(key=lambda e: e['subject'].subject)
        class_rows.append({
            'homework': hw,
            'grade': hw.grade,
            'section': hw.section,
            'nepali_date': str(hw.nepali_date),
            'entries': entries,
            'entry_count': len(entries),
        })

    # Grade-level grouping.
    grade_levels = GradeLevel.objects.filter(
        schoolgrade__school=school, schoolgrade__active=True
    ).distinct().order_by('id')
    rows_by_level = []
    for level in grade_levels:
        level_rows = [r for r in class_rows if r['grade'].level_id == level.id]
        if level_rows:
            rows_by_level.append({'level': level, 'rows': level_rows})

    # Prev/next dates.
    # date_objs is sorted descending (newest first), so:
    #   index i-1 = newer date  → "next" (forward in time)
    #   index i+1 = older date  → "prev" (back in time)
    prev_date = next_date = None
    for i, d in enumerate(date_objs):
        if d == selected_bs:
            if i < len(date_objs) - 1:
                prev_date = date_objs[i + 1]   # older date
            if i > 0:
                next_date = date_objs[i - 1]   # newer date
            break

    # Group all_dates by year-month for the tabbed jump UI.
    # date_objs is descending, so we iterate to preserve order.
    from collections import OrderedDict
    from nepali_datetime import _days_in_month
    BS_MONTHS = ['Baisakh','Jestha','Ashadh','Shrawan','Bhadra','Ashwin',
                 'Kartik','Mangsir','Poush','Magh','Falgun','Chaitra']
    months_map = OrderedDict()
    for d in sorted(date_objs):  # ascending so months appear oldest→newest left→right
        key = (d.year, d.month)
        if key not in months_map:
            months_map[key] = {
                'year': d.year,
                'month': d.month,
                'month_name': BS_MONTHS[d.month - 1],
                'label': f"{BS_MONTHS[d.month - 1]} {d.year}",
                'total_days': _days_in_month(d.year, d.month),
                'hw_days': [],       # day numbers (ints) that have homework, ascending
                'date_map': {},      # day int → full BS date string for href
            }
        months_map[key]['hw_days'].append(d.day)
        months_map[key]['date_map'][d.day] = str(d)
    # sort hw_days ascending; build full day grid (1..total_days) for template
    for grp in months_map.values():
        hw_set = set(grp['hw_days'])
        grp['hw_days'] = sorted(hw_set)
        # grid: list of (day_num, date_str|None, is_selected)
        sel_day = selected_bs.day if (selected_bs.year == grp['year'] and selected_bs.month == grp['month']) else None
        grp['day_grid'] = [
            {
                'day': d,
                'date_str': grp['date_map'].get(d),   # None if no homework
                'has_hw': d in hw_set,
                'is_active': d == sel_day,
            }
            for d in range(1, grp['total_days'] + 1)
        ]
    dates_by_month = list(months_map.values())
    # Which month tab should be active?
    active_month_year = selected_bs.year
    active_month_num = selected_bs.month

    context = {
        'branchuser': branchuser,
        'school': school,
        'current_session': current_session,
        'is_admin': is_admin,
        'today_bs': today_bs,
        'today_gs': today_bs.to_datetime_date().isoformat(),
        'selected_bs': selected_bs,
        'selected_gs': selected_bs.to_datetime_date().isoformat(),
        'class_rows': class_rows,
        'rows_by_level': rows_by_level,
        'total_classes': len(class_rows),
        'total_entries': sum(r['entry_count'] for r in class_rows),
        'prev_date': prev_date,
        'next_date': next_date,
        'all_dates': date_objs,
        'dates_by_month': dates_by_month,
        'active_month_year': active_month_year,
        'active_month_num': active_month_num,
    }
    return render(request, 'grihakarya/homeworks_list.html', context)


@login_required
def grihakarya_edit_entry(request, pk):
    """Edit a single HomeworkEntry. Records an audit log on every text change."""
    from .models import HomeworkEntryAuditLog

    try:
        branchuser = BranchUser.objects.select_related('school').get(user=request.user)
    except BranchUser.DoesNotExist:
        return HttpResponse('Not allowed. <a href="/">Home</a>')

    entry = get_object_or_404(
        HomeworkEntry.objects.select_related('homework__grade', 'homework__section', 'subject', 'added_by'),
        pk=pk,
        homework__grade__school=branchuser.school,
    )
    hw = entry.homework
    back_url = f"{reverse('grihakarya:homeworks')}?date={hw.nepali_date}"

    if request.method == 'POST':
        new_text = (request.POST.get('homework_text') or '').strip()
        if not new_text:
            messages.error(request, 'Homework text cannot be empty.')
        else:
            old_text = entry.homework_text
            if new_text != old_text:
                HomeworkEntryAuditLog.objects.create(
                    entry=entry,
                    changed_by=request.user,
                    old_text=old_text,
                    new_text=new_text,
                    source='admin',
                )
                entry.homework_text = new_text
                entry.save(update_fields=['homework_text'])

                # Keep Homework.homework JSON blob in sync.
                try:
                    hw_dict = json.loads(hw.homework or '{}')
                except (json.JSONDecodeError, TypeError):
                    hw_dict = {}
                subj_key = str(entry.subject_id)
                existing = hw_dict.get(subj_key)
                if isinstance(existing, dict) and 'text' in existing:
                    # Direct leaf format.
                    existing['text'] = new_text
                elif isinstance(existing, dict):
                    # Webview teacher-keyed format — update text inside every teacher sub-entry.
                    for uid, val in existing.items():
                        if isinstance(val, dict):
                            val['text'] = new_text
                else:
                    # Flat string format.
                    hw_dict[subj_key] = new_text
                hw.homework = json.dumps(hw_dict)
                hw.save(update_fields=['homework', 'updated_on'])
                messages.success(request, 'Homework updated.')
            else:
                messages.info(request, 'No changes detected.')
            return redirect(back_url)

    audit_logs = entry.audit_logs.select_related('changed_by').order_by('-changed_at')[:20]
    context = {
        'branchuser': branchuser,
        'entry': entry,
        'hw': hw,
        'audit_logs': audit_logs,
        'back_url': back_url,
    }
    return render(request, 'grihakarya/edit_entry.html', context)


@login_required
def grihakarya_entry_history(request, pk):
    """Full audit log for a HomeworkEntry."""
    from .models import HomeworkEntryAuditLog

    try:
        branchuser = BranchUser.objects.select_related('school').get(user=request.user)
    except BranchUser.DoesNotExist:
        return HttpResponse('Not allowed. <a href="/">Home</a>')

    entry = get_object_or_404(
        HomeworkEntry.objects.select_related('homework__grade', 'homework__section', 'subject', 'added_by'),
        pk=pk,
        homework__grade__school=branchuser.school,
    )
    audit_logs = entry.audit_logs.select_related('changed_by').order_by('-changed_at')
    back_url = f"{reverse('grihakarya:homeworks')}?date={entry.homework.nepali_date}"
    context = {
        'branchuser': branchuser,
        'entry': entry,
        'audit_logs': audit_logs,
        'back_url': back_url,
    }
    return render(request, 'grihakarya/entry_history.html', context)


@login_required
def grihakarya_complaints(request):
    user = request.user
    try:
        branchuser = BranchUser.objects.select_related('school').get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. '
            'Click <a href="/">Here</a> to go the homepage.'
        )

    school = branchuser.school
    is_admin = branchuser.admin_status
    current_session = get_current_session()

    if is_admin:
        complains = HomeworkComplain.objects.filter(grade__school=school).select_related('teacher', 'grade', 'section', 'subject')
    else:
        complains = HomeworkComplain.objects.filter(teacher=user, grade__school=school).select_related('grade', 'section', 'subject')

    context = {
        'branchuser': branchuser,
        'school': school,
        'current_session': current_session,
        'is_admin': is_admin,
        'complains': complains,
    }
    return render(request, 'grihakarya/complaints.html', context)


@login_required
def grihakarya_add_complain(request):
    """Teacher adds a homework complaint."""
    user = request.user
    try:
        branchuser = BranchUser.objects.select_related('school').get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. '
            'Click <a href="/">Here</a> to go the homepage.'
        )

    school = branchuser.school
    is_admin = branchuser.admin_status
    current_session = get_current_session()

    if request.method == 'POST':
        grade_id = request.POST.get('grade')
        section_id = request.POST.get('section') or None
        subject_id = request.POST.get('subject') or None
        homework_id = request.POST.get('homework') or None
        complaint_text = (request.POST.get('complaint_text') or '').strip()

        if not complaint_text:
            messages.error(request, 'Please enter your complaint.')
            return redirect('grihakarya:complaints')

        try:
            grade = SchoolGrade.objects.get(id=grade_id, session=current_session, school=school)
        except (SchoolGrade.DoesNotExist, ValueError):
            messages.error(request, 'Invalid grade.')
            return redirect('grihakarya:complains')

        section_obj = None
        if section_id:
            try:
                section_obj = Section.objects.get(id=section_id, grade=grade, session=current_session, school=school)
            except (Section.DoesNotExist, ValueError):
                messages.error(request, 'Invalid section.')
                return redirect('grihakarya:complains')

        subject_obj = None
        if subject_id:
            try:
                subject_obj = Subject.objects.get(id=subject_id, session=current_session, branch=school, status=True)
            except Subject.DoesNotExist:
                messages.error(request, 'Invalid subject.')
                return redirect('grihakarya:complains')

        homework_obj = None
        if homework_id:
            try:
                homework_obj = Homework.objects.get(id=homework_id, session=current_session, grade__school=school)
            except Homework.DoesNotExist:
                messages.error(request, 'Invalid homework.')
                return redirect('grihakarya:complains')

        HomeworkComplain.objects.create(
            homework=homework_obj,
            teacher=user,
            grade=grade,
            section=section_obj,
            subject=subject_obj,
            complaint_text=complaint_text,
        )
        messages.success(request, 'Complaint submitted successfully.')
        return redirect('grihakarya:complains')

    grades = SchoolGrade.objects.filter(session=current_session, school=school, active=True).order_by('grade_weight')
    sections = Section.objects.filter(session=current_session, school=school).select_related('grade').order_by('grade__grade_weight', 'section')
    subjects = Subject.objects.filter(session=current_session, branch=school, status=True).select_related('grade')
    homeworks = Homework.objects.filter(session=current_session, grade__school=school).select_related('grade', 'section').order_by('-nepali_date')[:50]

    context = {
        'branchuser': branchuser,
        'school': school,
        'current_session': current_session,
        'is_admin': is_admin,
        'grades': grades,
        'sections': sections,
        'subjects': subjects,
        'homeworks': homeworks,
    }
    return render(request, 'grihakarya/add_complain.html', context)


@login_required
def grihakarya_resolve_complain(request, pk):
    """Admin resolves or dismisses a complaint."""
    user = request.user
    try:
        branchuser = BranchUser.objects.select_related('school').get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. '
            'Click <a href="/">Here</a> to go the homepage.'
        )

    if not branchuser.admin_status:
        messages.error(request, 'Only administrators can resolve complaints.')
        return redirect('grihakarya:complains')

    school = branchuser.school
    complain = get_object_or_404(HomeworkComplain, pk=pk, grade__school=school)

    if request.method == 'POST':
        action = request.POST.get('action')
        admin_response = (request.POST.get('admin_response') or '').strip()

        if action == 'resolve':
            complain.status = 'resolved'
        elif action == 'dismiss':
            complain.status = 'dismissed'
        else:
            messages.error(request, 'Invalid action.')
            return redirect('grihakarya:complains')

        complain.admin_response = admin_response
        complain.resolved_by = user
        from django.utils import timezone
        complain.resolved_at = timezone.now()
        complain.save()

        messages.success(request, f'Complaint {action}ed successfully.')
        return redirect('grihakarya:complains')

    context = {
        'branchuser': branchuser,
        'school': school,
        'is_admin': True,
        'complain': complain,
    }
    return render(request, 'grihakarya/resolve_complain.html', context)
