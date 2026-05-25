from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from sms.models import TeacherSubjectAccess

class Command(BaseCommand):
    help = 'List TeacherSubjectAccess rows for a teacher (by username)'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username of the teacher (as stored in the User model)')
        parser.add_argument('--session', type=int, help='Optional session ID to filter')
        parser.add_argument('--status', type=bool, default=True, help='Filter by active status (default True)')

    def handle(self, *args, **options):
        username = options['username']
        session_id = options.get('session')
        status = options.get('status')
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User with username "{username}" does not exist')

        qs = TeacherSubjectAccess.objects.filter(teacher=user)
        if session_id:
            qs = qs.filter(session_id=session_id)
        if status is not None:
            qs = qs.filter(status=status)
        qs = qs.select_related('grade__school', 'section', 'subject')
        if not qs.exists():
            self.stdout.write(self.style.WARNING('No TeacherSubjectAccess rows found for this teacher'))
            return
        for access in qs:
            school_name = access.grade.school.name if access.grade and access.grade.school else '-'
            self.stdout.write(
                f"Teacher: {user.username} | Grade: {getattr(access.grade, 'grade_name', '-')}, "
                f"Section: {getattr(access.section, 'section', '-')}, "
                f"Subject: {getattr(access, 'subject', '-')}, "
                f"School: {school_name}, Status: {access.status}"
            )
