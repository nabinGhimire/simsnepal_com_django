# webview/utils.py
import json
import logging

from django.conf import settings
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

from webview.models import Teacher, TeacherSubjectAccess
from webview.views import get_current_session   # adjust import if helper lives elsewhere


logger = logging.getLogger(__name__)

def inspect_webview_token(token: str, *, max_age: int = 86400, show_access: bool = False):
    """
    Decode a Laravel‑generated web‑view token, print its payload,
    and optionally list the related TeacherSubjectAccess rows.

    Parameters
    ----------
    token: str
        The raw token string returned by the Laravel endpoint.
    max_age: int (default 86400 seconds = 24 h)
        Maximum allowed age before the token is considered expired.
    show_access: bool (default False)
        If True, the function will query TeacherSubjectAccess for the
        teacher identified by the token and print a short summary.
    """
    # --------------------------------------------------------------
    # 1️⃣  Grab the secret key that Laravel used to sign the token.
    # --------------------------------------------------------------
    signer_key = getattr(settings, "SIMS_WEBVIEW_SIGNER_KEY", None)
    if not signer_key:
        raise RuntimeError(
            "SIMS_WEBVIEW_SIGNER_KEY is not defined in Django settings. "
            "Add the same value that Laravel uses."
        )

    signer = TimestampSigner(key=signer_key)

    # --------------------------------------------------------------
    # 2️⃣  Unsigned (decode) the token.
    # --------------------------------------------------------------
    try:
        raw_payload = signer.unsign(token, max_age=max_age)
    except SignatureExpired:
        raise ValueError(f"Token has expired (max_age={max_age}s).")
    except BadSignature:
        raise ValueError("Token is malformed or signed with a different key.")

    # Payload is JSON -> Python dict
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Payload is not valid JSON: {exc}")

    # --------------------------------------------------------------
    # 3️⃣  Show the decoded payload.
    # --------------------------------------------------------------
    print("\n✅ Decoded token payload:")
    print(json.dumps(payload, indent=4, ensure_ascii=False))

    phone = payload.get("phone")
    hamro_uuid = payload.get("hamro_uuid")

    if not phone and not hamro_uuid:
        print("\n⚠️  No phone or uuid in payload – cannot locate a teacher.")
        return

    # --------------------------------------------------------------
    # 4️⃣  Look up the Teacher record (try both UUID and phone).
    # --------------------------------------------------------------
    teacher = None

    if hamro_uuid:
        # If you store the UUID on a related User model, adjust accordingly:
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(id=hamro_uuid).first()
            teacher = Teacher.objects.filter(user=user).first()
        except Exception:
            # No direct FK – ignore
            pass

    if not teacher and phone:
        teacher = Teacher.objects.filter(mobile_number=phone).first()

    if not teacher:
        print("\n⚠️  No Teacher record found for this token data.")
        return

    print(f"\n👩‍🏫 Teacher found: {teacher} (phone={phone})")

    # --------------------------------------------------------------
    # 5️⃣  Optional: List TeacherSubjectAccess rows for the current session.
    # --------------------------------------------------------------
    if show_access:
        session = get_current_session()
        access_qs = TeacherSubjectAccess.objects.filter(
            teacher=teacher, session=session, status=True
        ).select_related("grade__school")

        # fallback to phone lookup, mirroring the view logic
        if not access_qs.exists() and phone:
            access_qs = TeacherSubjectAccess.objects.filter(
                teacher__mobile_number=phone, session=session, status=True
            ).select_related("grade__school")

        count = access_qs.count()
        print(f"\n📚 Subject‑access rows (session={session}): {count}")

        for entry in access_qs[:20]:   # limit to first 20 for readability
            school_name = (
                entry.grade.school.name if entry.grade and entry.grade.school else "-"
            )
            print(
                f"  • Grade: {getattr(entry.grade, 'grade_name', '-')}, "
                f"Section: {getattr(entry.section, 'section', '-')}, "
                f"Subject: {getattr(entry, 'subject', '-')}, "
                f"School: {school_name}"
            )
        if count > 20:
            print("  … (more rows omitted)")
