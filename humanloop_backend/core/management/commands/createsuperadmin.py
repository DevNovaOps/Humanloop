"""
Management command: Create the single HumanLoop super-admin.

This is the ONLY way to create an admin account.
Regular users CANNOT register as admin through the signup page.

Usage:
    python manage.py createsuperadmin
    python manage.py createsuperadmin --force
    python manage.py createsuperadmin --email admin@humanloop.com --password Admin@123 --name "HumanLoop Admin"
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from core.models import User


class Command(BaseCommand):
    help = 'Create the single HumanLoop super-admin (the only way to get an admin account)'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, default='admin@humanloop.com',
                            help='Admin email (default: admin@humanloop.com)')
        parser.add_argument('--password', type=str, default='Admin@123',
                            help='Admin password (default: Admin@123)')
        parser.add_argument('--name', type=str, default='HumanLoop Admin',
                            help='Admin display name (default: HumanLoop Admin)')
        parser.add_argument('--force', action='store_true',
                            help='Force reset existing admin without asking')

    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        password = options['password']
        name = options['name'].strip()
        force = options['force']

        # ── Check if an admin already exists ──
        existing_admin = User.objects.filter(role='admin').first()
        if existing_admin:
            if not force:
                self.stdout.write(self.style.WARNING(
                    f'\nAn admin already exists: {existing_admin.email} (id={existing_admin.id})'
                ))
                ans = input('Reset this admin? [y/N] ').strip().lower()
                if ans != 'y':
                    self.stdout.write(self.style.NOTICE('Aborted.'))
                    return

            # Reset existing admin
            existing_admin.name = name
            existing_admin.email = email
            existing_admin.password = make_password(password)
            existing_admin.is_active = True
            existing_admin.verified = True
            existing_admin.save()
            self.stdout.write(self.style.SUCCESS(
                f'\nAdmin account reset!'
                f'\n  Email:    {email}'
                f'\n  Password: {password}'
                f'\n  Name:     {name}'
            ))
            return

        # ── Check if email is used by another role ──
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.ERROR(
                f'\nThe email {email} is already registered as a non-admin user.'
                f'\nUse a different email with: --email youremail@domain.com'
            ))
            return

        # ── Create the super-admin ──
        admin = User.objects.create(
            name=name,
            email=email,
            password=make_password(password),
            role='admin',
            organization='HumanLoop',
            verified=True,
            is_active=True,
        )

        self.stdout.write(self.style.SUCCESS(
            f'\nSuper-admin created!'
            f'\n  Email:    {email}'
            f'\n  Password: {password}'
            f'\n  Name:     {name}'
            f'\n  ID:       {admin.id}'
            f'\n'
            f'\n  Login at: http://localhost:8000/login/'
        ))
