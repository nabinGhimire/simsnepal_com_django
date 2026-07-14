import logging
from django.core.management.base import BaseCommand
from panel.platform_sync import cleanup_duplicate_threads, cleanup_hamro_orphans
from sms.models import EduSession, SchoolBranch

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Clean up duplicate Hamro channels/groups. Use --dry-run to preview.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--school-id', type=int, help='Specific school branch ID. If omitted, processes all schools.'
        )
        parser.add_argument(
            '--session-year', type=int, help='Session year (e.g., 2083). If omitted, uses latest active session.'
        )
        parser.add_argument(
            '--dry-run', action='store_true', help='Preview changes without deleting anything.'
        )
        parser.add_argument(
            '--hamro-cleanup', action='store_true',
            help='Also query Hamro API to find and delete orphaned/duplicate threads on the platform.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        hamro_cleanup = options['hamro_cleanup']
        
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

        for school in schools:
            self.stdout.write(f'\n{"="*60}')
            self.stdout.write(f'Processing school: {school.name} (ID: {school.id})')
            self.stdout.write(f'{"="*60}')

            # Step 1: Clean DB-side duplicates
            self.stdout.write('\n--- Step 1: Cleaning DB duplicates ---')
            actions = cleanup_duplicate_threads(school, session, dry_run=dry_run)
            
            if not actions:
                self.stdout.write('  No DB duplicates found')
            else:
                for action in actions:
                    if action.get('action') == 'cleared_stale_external_id':
                        self.stdout.write(self.style.WARNING(
                            f"  [{action['type']}] '{action['name']}': cleared stale external_id {action['old_id']}"
                        ))
                    else:
                        self.stdout.write(self.style.SUCCESS(
                            f"  [{action['type']}] '{action['name']}': "
                            f"kept={action.get('kept_id')} removed={action.get('removed_id')}"
                        ))

            # Step 2: Clean Hamro-side orphans (optional)
            if hamro_cleanup:
                self.stdout.write('\n--- Step 2: Cleaning Hamro platform orphans ---')
                hamro_actions = cleanup_hamro_orphans(school, session, dry_run=dry_run)
                
                if not hamro_actions:
                    self.stdout.write('  No Hamro orphans found')
                else:
                    for action in hamro_actions:
                        self.stdout.write(self.style.WARNING(
                            f"  [{action['type']}] '{action['name']}': deleted {action['deleted_id']}"
                            + (f" (kept {action.get('kept_id')})" if action.get('kept_id') else "")
                        ))

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDry run complete. Run without --dry-run to apply.'))
        else:
            self.stdout.write(self.style.SUCCESS('\nCleanup complete.'))
