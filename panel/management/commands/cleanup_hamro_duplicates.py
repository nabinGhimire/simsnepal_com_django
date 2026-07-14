import logging
from django.core.management.base import BaseCommand
from panel.platform_sync import cleanup_duplicate_threads
from sms.models import EduSession, SchoolBranch

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Find and clean up duplicate Hamro channels/groups in the database. Use --dry-run to preview without making changes.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--school-id', type=int, help='Specific school branch ID to clean up. If omitted, processes all schools.'
        )
        parser.add_argument(
            '--session-year', type=int, help='Specific session year (e.g., 2083). If omitted, uses the latest active session.'
        )
        parser.add_argument(
            '--dry-run', action='store_true', help='Preview changes without actually deleting anything.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be made'))

        # Resolve session
        session_year = options.get('session_year')
        if session_year:
            try:
                session = EduSession.objects.get(year=session_year)
            except EduSession.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'Session {session_year} not found'))
                return
        else:
            session = EduSession.objects.filter(status=True).order_by('-year').first()
            if not session:
                self.stderr.write(self.style.ERROR('No active session found'))
                return

        self.stdout.write(f'Using session: {session.year}')

        # Resolve schools
        school_id = options.get('school_id')
        if school_id:
            schools = SchoolBranch.objects.filter(id=school_id)
            if not schools.exists():
                self.stderr.write(self.style.ERROR(f'School {school_id} not found'))
                return
        else:
            schools = SchoolBranch.objects.all()

        total_cleaned = 0
        for school in schools:
            self.stdout.write(f'\nProcessing school: {school.name} (ID: {school.id})')
            actions = cleanup_duplicate_threads(school, session, dry_run=dry_run)
            
            if not actions:
                self.stdout.write(f'  No duplicates found')
                continue
                
            for action in actions:
                total_cleaned += 1
                if action.get('action') == 'cleared_stale_external_id':
                    self.stdout.write(self.style.WARNING(
                        f"  [{action['type']}] '{action['name']}': cleared stale external_id {action['old_id']}"
                    ))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"  [{action['type']}] '{action['name']}': "
                        f"kept={action.get('kept_id')} removed={action.get('removed_id')}"
                    ))

        if dry_run:
            self.stdout.write(self.style.WARNING(f'\nDry run complete. {total_cleaned} duplicates found. Run without --dry-run to apply.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\nCleanup complete. {total_cleaned} duplicates resolved.'))
