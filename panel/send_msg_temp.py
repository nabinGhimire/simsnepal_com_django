def send_parent_message(request):
    """Handle sending a free‑form message to a student's parents via Hamro.
    Expects POST with 'reg_no' and 'message_body'.
    """
    from django.http import HttpResponseForbidden
    from django.contrib import messages
    from django.shortcuts import redirect
    from sms.models import Student
    
    if request.method != "POST":
        return HttpResponseForbidden('Invalid request method')
    reg_no = request.POST.get('reg_no')
    message_body = request.POST.get('message_body', '').strip()
    if not reg_no or not message_body:
        messages.error(request, 'Student and message are required.')
        return redirect(request.META.get('HTTP_REFERER', 'panel:index'))
    try:
        student = Student.objects.get(reg_no=reg_no)
    except Student.DoesNotExist:
        messages.error(request, 'Student not found.')
        return redirect(request.META.get('HTTP_REFERER', 'panel:index'))
    # Gather parent contacts without creating new Hamro users
    contacts = []
    if student.fathers_phone:
        contacts.append(('phone', student.fathers_phone))
    if student.fathers_email:
        contacts.append(('email', student.fathers_email))
    if student.mothers_phone:
        contacts.append(('phone', student.mothers_phone))
    if student.mothers_email:
        contacts.append(('email', student.mothers_email))
    parent_ids = []
    from sms.hamro import lookup_hamro_user
    def lookup_external_id(kind, val):
        if kind == 'email':
            return lookup_hamro_user(email=val)
        else:
            return lookup_hamro_user(phone=val)
    for kind, val in contacts:
        ext_id = lookup_external_id(kind, val)
        if ext_id:
            parent_ids.append(ext_id)
    if not parent_ids:
        messages.error(request, 'No registered parent found on Hamro for this student.')
        return redirect(request.META.get('HTTP_REFERER', 'panel:index'))
    # Ensure group exists (or create)
    from sms.hamro import ensure_group, add_user_to_group, send_message_to_thread
    group_name = f"Student_{reg_no}_Parents"
    current_session = get_current_session()
    group = ensure_group(group_name, current_session.id, school=student.school)
    if not group:
        messages.error(request, 'Failed to create or retrieve Hamro group.')
        return redirect(request.META.get('HTTP_REFERER', 'panel:index'))
    # Add parents to group (deduplicate)
    for pid in set(parent_ids):
        add_user_to_group(pid, group.external_id)
    # Send message to group's thread
    hamro_msg_id = send_message_to_thread(group.external_id, message_body)
    # Log the message
    from panel.models import ParentMessageLog
    ParentMessageLog.objects.create(
        sender=request.user,
        student=student,
        content=message_body,
        hamro_message_id=hamro_msg_id,
        status='SENT' if hamro_msg_id else 'FAILED'
    )
    if hamro_msg_id:
        messages.success(request, 'Message sent successfully.')
    else:
        messages.warning(request, 'Message could not be delivered to Hamro.')
    return redirect(request.META.get('HTTP_REFERER', 'panel:index'))
