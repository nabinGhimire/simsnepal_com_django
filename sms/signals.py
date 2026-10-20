import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Student, PlatformUserMapping, GroupMembershipCache, Group, StudentSession

logger = logging.getLogger(__name__)

# ─── helpers ──────────────────────────────────────────────────────────────────

def _parent_contacts(student):
    """Return a flat list of (normalized_key, raw_value) tuples for all parent contacts."""
    from sms.hamro import format_phone
    contacts = []
    for phone in [student.fathers_phone, student.mothers_phone, student.guardian_phone]:
        if phone:
            try:
                normalized = format_phone(str(phone))
                if normalized.startswith('+'):
                    normalized = normalized[1:]
                contacts.append(normalized)
            except Exception:
                pass
    for email in [student.fathers_email, student.mothers_email, student.guardian_email]:
        if email:
            contacts.append(str(email).strip().lower())
    return contacts


def _changed_contacts(old_student, new_student):
    """Return (removed_keys, added_keys) comparing old vs new parent contacts."""
    old_keys = set(_parent_contacts(old_student)) if old_student else set()
    new_keys = set(_parent_contacts(new_student))
    removed = old_keys - new_keys
    added = new_keys - old_keys
    return removed, added


def _groups_for_student(student):
    """
    Return all Group objects whose parents include this student.
    Covers:
      - class groups (grade+section match) for all active StudentSessions
      - school-wide group
      - dedicated StudentParentGroup if it exists
    """
    from .models import StudentParentGroup

    groups = []

    # Class/section groups via active StudentSession records
    sessions = StudentSession.objects.filter(
        student=student, status=True
    ).select_related('grade', 'section', 'session', 'grade__school')

    for ss in sessions:
        school = ss.grade.school if ss.grade else student.school
        qs = Group.objects.filter(
            session=ss.session,
            school=school,
        ).filter(
            # school-wide or class-level groups
            group_type__in=['school', 'class']
        )
        # narrow class groups to this grade/section
        for g in qs:
            if g.group_type == 'school':
                groups.append(g)
            elif g.group_type == 'class' and g.grade == ss.grade and g.section == ss.section:
                groups.append(g)

    # Dedicated per-student parent group
    try:
        spg = StudentParentGroup.objects.select_related('group').get(student=student)
        groups.append(spg.group)
    except Exception:
        pass

    return groups


# ─── signals ──────────────────────────────────────────────────────────────────

@receiver(pre_save, sender=Student)
def _capture_old_student(sender, instance, **kwargs):
    """Snapshot the pre-save state so post_save can diff the contacts."""
    if instance.pk:
        try:
            instance._pre_save_snapshot = Student.objects.get(pk=instance.pk)
        except Student.DoesNotExist:
            instance._pre_save_snapshot = None
    else:
        instance._pre_save_snapshot = None


@receiver(post_save, sender=Student)
def invalidate_parent_cache_on_contact_change(sender, instance, created, **kwargs):
    """
    When parent contact details change on a Student:
      1. Remove stale PlatformUserMapping entries for removed contacts so
         the next sync re-looks them up.
      2. For added contacts: force a fresh lookup by deleting any existing
         mapping (it may point to a different person's old account).
      3. Remove GroupMembershipCache entries for the old parent's platform ID
         across all groups this student belongs to — forces the next sync to
         re-evaluate membership rather than treating the stale entry as current.
    """
    old_student = getattr(instance, '_pre_save_snapshot', None)

    if created:
        # New student — no cache to invalidate yet
        return

    removed_keys, added_keys = _changed_contacts(old_student, instance)

    if not removed_keys and not added_keys:
        return  # contacts unchanged — nothing to do

    logger.info(
        f"Student {instance.reg_no} parent contacts changed. "
        f"Removed: {removed_keys}, Added: {added_keys}"
    )

    # ── Step 1: collect platform IDs for removed contacts before deleting ──
    old_platform_ids = set()
    if removed_keys:
        old_mappings = PlatformUserMapping.objects.filter(
            phone_or_email__in=removed_keys,
            external_id__isnull=False
        )
        for m in old_mappings:
            if m.external_id:
                old_platform_ids.add(m.external_id)
        # Delete stale mappings so next sync re-looks them up
        PlatformUserMapping.objects.filter(phone_or_email__in=removed_keys).delete()
        logger.info(f"Deleted PlatformUserMapping for removed contacts: {removed_keys}")

    # ── Step 2: delete mappings for added contacts (may be stale/wrong person) ──
    if added_keys:
        PlatformUserMapping.objects.filter(phone_or_email__in=added_keys).delete()
        logger.info(f"Deleted PlatformUserMapping for new contacts (force re-lookup): {added_keys}")

    # ── Step 3: remove stale GroupMembershipCache entries for old platform IDs ──
    if old_platform_ids:
        groups = _groups_for_student(instance)
        if groups:
            deleted_count, _ = GroupMembershipCache.objects.filter(
                group__in=groups,
                platform_user_id__in=old_platform_ids
            ).delete()
            logger.info(
                f"Deleted {deleted_count} GroupMembershipCache entries "
                f"for old parent IDs {old_platform_ids} across {len(groups)} groups"
            )
