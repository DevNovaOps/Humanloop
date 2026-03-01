"""
Management command: Create the single HumanLoop super-admin.

This is the ONLY way to create an admin account.
Regular users CANNOT register as admin through the signup page.

Usage (local):
    python manage.py createsuperadmin
    python manage.py createsuperadmin --force
    python manage.py createsuperadmin --email admin@humanloop.com --password Admin@123 --name "HumanLoop Admin"

Usage (Railway — via env vars):
    Set ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME in Railway dashboard.
    The command runs automatically on deploy via railway.json.
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from core.models import User


class Command(BaseCommand):
    help = 'Create the single HumanLoop super-admin (the only way to get an admin account)'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, default=None,
                            help='Admin email (default: env ADMIN_EMAIL or admin@humanloop.com)')
        parser.add_argument('--password', type=str, default=None,
                            help='Admin password (default: env ADMIN_PASSWORD or Admin@123)')
        parser.add_argument('--name', type=str, default=None,
                            help='Admin display name (default: env ADMIN_NAME or HumanLoop Admin)')
        parser.add_argument('--force', action='store_true',
                            help='Force reset existing admin without asking')
        parser.add_argument('--no-input', action='store_true',
                            help='Run non-interactively (auto-skip prompts, used on Railway)')

    def handle(self, *args, **options):
        # Read from CLI args → env vars → defaults (in that priority)
        email = (options['email']
                 or os.getenv('ADMIN_EMAIL', 'admin@humanloop.com')).strip().lower()
        password = (options['password']
                    or os.getenv('ADMIN_PASSWORD', 'Admin@123'))
        name = (options['name']
                or os.getenv('ADMIN_NAME', 'HumanLoop Admin')).strip()
        force = options['force']
        no_input = options['no_input']

        # Auto-detect Railway (always non-interactive on Railway)
        is_railway = os.getenv('RAILWAY_ENVIRONMENT') is not None
        if is_railway:
            no_input = True

        # ── Check if an admin already exists ──
        existing_admin = User.objects.filter(role='admin').first()
        if existing_admin:
            if not force and not no_input:
                self.stdout.write(self.style.WARNING(
                    f'\nAn admin already exists: {existing_admin.email} (id={existing_admin.id})'
                ))
                ans = input('Reset this admin? [y/N] ').strip().lower()
                if ans != 'y':
                    self.stdout.write(self.style.NOTICE('Aborted.'))
                    return

            if no_input and not force:
                # On Railway, skip silently if admin already exists (idempotent)
                self.stdout.write(self.style.SUCCESS(
                    f'Admin already exists: {existing_admin.email} — skipping.'
                ))
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
                f'\n  Password: {"*" * len(password)}'
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
            f'\n  Password: {"*" * len(password)}'
            f'\n  Name:     {name}'
            f'\n  ID:       {admin.id}'
        ))
