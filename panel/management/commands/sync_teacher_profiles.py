import requests
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from sms.models import Teacher
from sso.models import HamroUserProfile

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Syncs teacher profile pictures from Hamro ecosystem in batches.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of profiles to fetch per request.'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        self.stdout.write(self.style.SUCCESS('Starting teacher profile sync...'))

        api_key = getattr(settings, 'HAMRO_SYSTEM_API_KEY', None)
        api_base_url = getattr(settings, 'HAMRO_API_BASE_URL', 'https://messengerin.hamro.com').rstrip('/')

        if not api_key:
            self.stdout.write(self.style.ERROR('HAMRO_SYSTEM_API_KEY is missing from settings.'))
            return

        headers = {
            'X-System-API-Key': api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        # Fetch all unique teacher users
        teachers = Teacher.objects.select_related('teacher', 'teacher__hamro_profile').all()
        
        # Deduplicate users (in case one User is assigned as multiple Teachers)
        users = {}
        for t in teachers:
            users[t.teacher.id] = t.teacher
        
        user_list = list(users.values())
        total_users = len(user_list)
        self.stdout.write(f'Found {total_users} unique teacher accounts.')

        for i in range(0, total_users, batch_size):
            batch = user_list[i:i + batch_size]
            
            contacts_to_search = []
            user_map = {}
            
            for user_obj in batch:
                contact = user_obj.email or user_obj.username
                if contact:
                    contacts_to_search.append(contact)
                    user_map[contact] = user_obj
            
            if not contacts_to_search:
                continue

            self.stdout.write(f'Processing batch {i//batch_size + 1} ({len(contacts_to_search)} contacts)...')
            
            payload = {'contacts': contacts_to_search}
            try:
                resp = requests.post(
                    f'{api_base_url}/api/v1/system/contacts/find',
                    json=payload,
                    headers=headers,
                    timeout=10,
                    verify=True
                )
                if resp.status_code == 200:
                    results = resp.json().get('data', [])
                    updated_count = 0
                    for result in results:
                        if result.get('found'):
                            user_data = result.get('user', {})
                            avatar_url = user_data.get('avatar_url', '')
                            hamro_uuid = user_data.get('id', '')
                            mobile_number = user_data.get('mobile_number', '')
                            contact = user_data.get('email') or user_data.get('mobile_number', '')
                            
                            if avatar_url and contact:
                                user_obj = user_map.get(contact)
                                if not user_obj:
                                    for c, u in user_map.items():
                                        if c.replace('-','').replace(' ','') == contact.replace('-','').replace(' ',''):
                                            user_obj = u
                                            break
                                
                                if user_obj:
                                    try:
                                        profile = user_obj.hamro_profile
                                    except Exception:
                                        profile = None
                                    
                                    if profile:
                                        changed = False
                                        if profile.avatar_url != avatar_url:
                                            profile.avatar_url = avatar_url
                                            changed = True
                                        if hamro_uuid and profile.hamro_uuid != hamro_uuid:
                                            # Check UUID not taken by another user
                                            if not HamroUserProfile.objects.filter(hamro_uuid=hamro_uuid).exclude(id=profile.id).exists():
                                                profile.hamro_uuid = hamro_uuid
                                                changed = True
                                        if mobile_number:
                                            profile.mobile_number = mobile_number
                                            changed = True
                                        if changed:
                                            profile.save()
                                    else:
                                        # Create new profile
                                        defaults = {
                                            'avatar_url': avatar_url,
                                            'mobile_number': mobile_number,
                                        }
                                        if hamro_uuid:
                                            defaults['hamro_uuid'] = hamro_uuid
                                            HamroUserProfile.objects.get_or_create(
                                                user=user_obj, defaults=defaults
                                            )
                                        else:
                                            HamroUserProfile.objects.get_or_create(
                                                user=user_obj, defaults=defaults
                                            )
                                    updated_count += 1
                                    
                    self.stdout.write(self.style.SUCCESS(f'Successfully synced {updated_count} profiles in this batch.'))
                else:
                    self.stdout.write(self.style.ERROR(f'API returned status {resp.status_code} for batch {i//batch_size + 1}.'))
            except Exception as e:
                logger.error(f"Error fetching bulk profiles: {e}")
                self.stdout.write(self.style.ERROR(f'Failed to process batch {i//batch_size + 1}: {e}'))

        self.stdout.write(self.style.SUCCESS('Teacher profile sync complete!'))
