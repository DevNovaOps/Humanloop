"""
Core views — all page rendering + API endpoints.
Uses manual session-based auth (request.session['user_id']).
"""
import json
import random
import re
from datetime import timedelta, datetime as dt

from django.conf import settings
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import send_mail
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from decimal import Decimal

from .models import (
    User, Pilot, Expense, Feedback, Notification, AuditLog,
    TeamMember, BeneficiaryEnrollment, OrgMember, PilotAssignment,
    Certificate, Document, Payment,
)
from .forms import (
    SignupForm, LoginForm, ForgotPasswordForm, OTPVerificationForm,
    ProfileForm, ChangePasswordForm, PilotForm, FeedbackForm, ExpenseForm,
)
from .ai_service import generate_plan, match_ngos, generate_insights
from .translations import get_translations


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────

def get_current_user(request):
    """Get the currently logged-in user from session, or None."""
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    try:
        return User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return None


def login_required_json(view_func):
    """Decorator: return 401 JSON if not logged in."""
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


def user_context(request):
    """Build template context with current user info."""
    user = get_current_user(request)
    ctx = {'user': user}
    if user:
        ctx['user_json'] = json.dumps({
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'organization': user.organization,
            'verified': user.verified,
            'language': user.language,
        })
    else:
        ctx['user_json'] = 'null'
    return ctx


def log_audit(user, action, details='', request=None):
    """Create an audit log entry."""
    try:
        ip = None
        if request:
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
            if ip and ',' in ip:
                ip = ip.split(',')[0].strip()
            # Truncate overly long IP values to avoid DB errors
            if ip and len(ip) > 39:
                ip = ip[:39]
        AuditLog.objects.create(user=user, action=action, details=details, ip_address=ip)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f'log_audit failed: {e}')


# ──────────────────────────────────────────────────────────
# Page Views (render templates)
# ──────────────────────────────────────────────────────────

def page_index(request):
    return render(request, 'index.html', user_context(request))


def page_login(request):
    if request.session.get('user_id'):
        user = get_current_user(request)
        if user:
            dashboards = {
                'innovator': 'dashboard',
                'ngo': 'dashboard_ngo',
                'beneficiary': 'dashboard_beneficiary',
                'admin': 'dashboard_admin',
            }
            return redirect(dashboards.get(user.role, 'dashboard'))
        else:
            # Stale session — clear it so user can log in again
            request.session.flush()
    return render(request, 'login.html', user_context(request))


def page_register(request):
    if request.session.get('user_id'):
        user = get_current_user(request)
        if user:
            # User is logged in — redirect to their dashboard
            dashboards = {
                'innovator': 'dashboard',
                'ngo': 'dashboard_ngo',
                'beneficiary': 'dashboard_beneficiary',
                'admin': 'dashboard_admin',
            }
            return redirect(dashboards.get(user.role, 'dashboard'))
        else:
            # Stale session (user deleted/suspended) — clear it
            request.session.flush()
    return render(request, 'register.html', user_context(request))


def page_forgot_password(request):
    return render(request, 'forgot-password.html', user_context(request))


def page_verify_otp(request):
    return render(request, 'verify-otp.html', user_context(request))


def page_dashboard(request):
    ctx = user_context(request)
    user = ctx['user']
    if not user:
        return redirect('login')
    # Stats for innovator dashboard
    ctx['total_pilots'] = Pilot.objects.filter(created_by=user).count()
    ctx['active_pilots'] = Pilot.objects.filter(created_by=user, status='active').count()
    ctx['total_beneficiaries'] = Pilot.objects.filter(created_by=user).aggregate(t=Sum('target_beneficiaries'))['t'] or 0
    ctx['total_budget'] = Pilot.objects.filter(created_by=user).aggregate(t=Sum('budget'))['t'] or 0
    ctx['recent_pilots'] = Pilot.objects.filter(created_by=user)[:5]
    return render(request, 'dashboard.html', ctx)


def page_dashboard_admin(request):
    ctx = user_context(request)
    user = ctx['user']
    if not user or user.role != 'admin':
        return redirect('login')
    ctx['total_users'] = User.objects.count()
    ctx['active_users'] = User.objects.filter(is_active=True).count()
    ctx['total_pilots'] = Pilot.objects.count()
    ctx['total_ngos'] = User.objects.filter(role='ngo').count()
    ctx['users'] = User.objects.all().order_by('-created_at')[:20]
    ctx['audit_logs'] = AuditLog.objects.select_related('user').all()[:15]
    # Assignment requests pending admin review (NGO already accepted)
    ctx['pending_assignments'] = PilotAssignment.objects.filter(
        status='ngo_accepted'
    ).select_related('pilot', 'requested_ngo', 'requested_by').order_by('-created_at')[:10]
    ctx['pending_count'] = PilotAssignment.objects.filter(status='ngo_accepted').count()
    # Certificate issuance data
    ctx['beneficiary_users'] = User.objects.filter(role='beneficiary', is_active=True).order_by('name')
    ctx['all_pilots'] = Pilot.objects.all().order_by('-created_at')
    # Pilot completion requests pending admin approval
    ctx['completion_requests'] = Pilot.objects.filter(
        status='pending_completion'
    ).select_related('assigned_ngo', 'created_by').order_by('-updated_at')
    return render(request, 'dashboard-admin.html', ctx)


def page_dashboard_ngo(request):
    ctx = user_context(request)
    user = ctx['user']
    if not user or user.role != 'ngo':
        return redirect('login')
    assigned = Pilot.objects.filter(assigned_ngo=user)
    ctx['assigned_pilots'] = assigned
    ctx['active_count'] = assigned.filter(status='active').count()
    ctx['team_count'] = OrgMember.objects.filter(
        organization=user.organization or ''
    ).count()
    # Avg progress across assigned pilots
    all_progress = [p.progress for p in assigned]
    ctx['avg_progress'] = round(sum(all_progress) / len(all_progress)) if all_progress else 0
    # Total beneficiaries reached
    ctx['beneficiaries_reached'] = BeneficiaryEnrollment.objects.filter(pilot__assigned_ngo=user).count()
    return render(request, 'dashboard-ngo.html', ctx)


def page_dashboard_beneficiary(request):
    ctx = user_context(request)
    user = ctx['user']
    if not user or user.role != 'beneficiary':
        return redirect('login')
    enrollments = BeneficiaryEnrollment.objects.filter(user=user).select_related('pilot')
    ctx['enrollments'] = enrollments
    ctx['program_count'] = enrollments.count()
    ctx['badges_count'] = sum(len(e.badges_earned) for e in enrollments)
    # Feedback for this user
    past_feedback = Feedback.objects.filter(user=user).select_related('pilot').order_by('-created_at')[:5]
    ctx['past_feedback'] = past_feedback
    ctx['has_past_feedback'] = past_feedback.exists()
    ctx['feedback_count'] = Feedback.objects.filter(user=user).count()
    # Certificates for this user
    ctx['certificates'] = Certificate.objects.filter(beneficiary=user).select_related('pilot')
    ctx['certificate_count'] = ctx['certificates'].count()
    # Multilingual support
    translations = get_translations(user.language)
    ctx['translations'] = translations
    ctx['translations_json'] = json.dumps(translations)
    ctx['current_language'] = user.language
    return render(request, 'dashboard-beneficiary.html', ctx)


def page_planner(request):
    ctx = user_context(request)
    if not ctx['user']:
        return redirect('login')
    return render(request, 'planner.html', ctx)


def page_pilot(request):
    ctx = user_context(request)
    user = ctx['user']
    if not user:
        return redirect('login')
    if user.role == 'admin':
        pilots = list(Pilot.objects.filter(status='active'))
    elif user.role == 'ngo':
        pilots = list(Pilot.objects.filter(assigned_ngo=user))
    else:
        pilots = list(Pilot.objects.filter(created_by=user))

    # Handle pilot_id selection from URL params
    pilot_id = request.GET.get('pilot_id')
    selected_pilot = None
    if pilot_id:
        try:
            pid = int(pilot_id)
            selected_pilot = next((p for p in pilots if p.id == pid), None)
        except (ValueError, TypeError):
            pass

    # If no specific pilot selected, use the first one
    if not selected_pilot and pilots:
        selected_pilot = pilots[0]

    # Move selected pilot to front of list so template's pilots.0 works
    if selected_pilot and pilots:
        pilots = [selected_pilot] + [p for p in pilots if p.id != selected_pilot.id]

    # Annotate each pilot with tasks_json for the template JS
    for p in pilots:
        p.tasks_json = json.dumps(p.tasks or [])
    ctx['pilots'] = pilots
    ctx['selected_pilot_id'] = selected_pilot.id if selected_pilot else None
    return render(request, 'pilot.html', ctx)


def page_expenses(request):
    ctx = user_context(request)
    user = ctx['user']
    if not user:
        return redirect('login')
    if user.role == 'admin':
        pilots = Pilot.objects.all()
    elif user.role == 'ngo':
        pilots = Pilot.objects.filter(assigned_ngo=user)
    else:
        pilots = Pilot.objects.filter(created_by=user)
    ctx['pilots'] = pilots

    # Handle pilot_id filter from URL params
    pilot_id = request.GET.get('pilot_id')
    selected_pilot_id = None
    if pilot_id:
        try:
            selected_pilot_id = int(pilot_id)
            ctx['expenses'] = Expense.objects.filter(pilot_id=selected_pilot_id, pilot__in=pilots)
        except (ValueError, TypeError):
            ctx['expenses'] = Expense.objects.filter(pilot__in=pilots)
    else:
        ctx['expenses'] = Expense.objects.filter(pilot__in=pilots)

    ctx['selected_pilot_id'] = selected_pilot_id
    ctx['total_spent'] = ctx['expenses'].aggregate(t=Sum('amount'))['t'] or 0
    return render(request, 'expenses.html', ctx)


def page_feedback(request):
    ctx = user_context(request)
    user = ctx['user']
    if not user:
        return redirect('login')

    # Real enrolled programs for this user
    enrollments = BeneficiaryEnrollment.objects.filter(user=user).select_related('pilot')
    ctx['enrollments'] = enrollments

    # Past feedback this user actually submitted (real DB data)
    past_feedback = Feedback.objects.filter(user=user).select_related('pilot').order_by('-created_at')[:10]
    ctx['past_feedback'] = past_feedback
    ctx['has_past_feedback'] = past_feedback.exists()

    # Multilingual support
    translations = get_translations(user.language)
    ctx['translations'] = translations
    ctx['translations_json'] = json.dumps(translations)
    ctx['current_language'] = user.language
    return render(request, 'feedback.html', ctx)


def page_settings(request):
    ctx = user_context(request)
    user = ctx['user']
    if not user:
        return redirect('login')
    # Multilingual support — beneficiary only
    if user.role == 'beneficiary':
        translations = get_translations(user.language)
    else:
        translations = get_translations('en')  # Always English for non-beneficiary
    ctx['translations'] = translations
    ctx['translations_json'] = json.dumps(translations)
    ctx['current_language'] = user.language if user.role == 'beneficiary' else 'en'
    return render(request, 'settings.html', ctx)


def page_explore_programs(request):
    """Browse active programs and enroll — beneficiary only."""
    ctx = user_context(request)
    user = ctx['user']
    if not user:
        return redirect('login')
    # All active pilots
    pilots = Pilot.objects.filter(status='active').order_by('-created_at')
    # Which pilots is this user already enrolled in?
    enrolled_ids = set(
        BeneficiaryEnrollment.objects.filter(user=user).values_list('pilot_id', flat=True)
    )
    ctx['available_programs'] = pilots
    ctx['enrolled_ids'] = enrolled_ids
    translations = get_translations(user.language)
    ctx['translations'] = translations
    ctx['translations_json'] = json.dumps(translations)
    ctx['current_language'] = user.language
    return render(request, 'explore-programs.html', ctx)


def page_about(request):
    return render(request, 'about.html', user_context(request))


def page_demo(request):
    return render(request, 'demo.html', user_context(request))


def page_contact(request):
    return render(request, 'contact.html', user_context(request))


def page_privacy_policy(request):
    return render(request, 'privacy-policy.html', user_context(request))


def page_terms_of_service(request):
    return render(request, 'terms-of-service.html', user_context(request))


def page_cookie_policy(request):
    return render(request, 'cookie-policy.html', user_context(request))


def page_partners(request):
    return render(request, 'partners.html', user_context(request))


def page_team(request):
    ctx = user_context(request)
    if not ctx['user']:
        return redirect('login')
    return render(request, 'team.html', ctx)


def page_403(request):
    return render(request, '403.html', user_context(request), status=403)


# ──────────────────────────────────────────────────────────
# Auth API Endpoints
# ──────────────────────────────────────────────────────────

@csrf_exempt
def api_register(request):
    """POST: Register a new user and send welcome email."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'innovator')
    organization = data.get('organization', '')

    # Validations
    if not name or not email or not password:
        return JsonResponse({'error': 'Name, email and password are required'}, status=400)

    if any(char.isdigit() for char in name):
        return JsonResponse({'error': 'Name cannot contain numbers'}, status=400)

    password_regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%?&])[A-Za-z\d@$!%?&]{8,}$'
    if not re.match(password_regex, password):
        return JsonResponse({'error': 'Password must be 8+ chars with uppercase, lowercase, number, and special char'}, status=400)

    try:
        if User.objects.filter(email=email).exists():
            return JsonResponse({'error': 'Email already registered'}, status=400)

        # Admin cannot be self-registered — only created via management command
        if role not in ['innovator', 'ngo', 'beneficiary']:
            role = 'innovator'

        user = User.objects.create(
            name=name,
            email=email,
            password=make_password(password),
            role=role,
            organization=organization,
        )

        # Audit log (non-critical)
        try:
            log_audit(user, 'User registered', f'Role: {role}', request)
        except Exception:
            pass

        # Build response FIRST — don't let email block the response
        response = JsonResponse({
            'success': True,
            'message': 'Registration successful',
            'user': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'role': user.role,
            }
        })

        # Send welcome email in background thread so it never blocks the response
        import threading
        def _send_welcome():
            try:
                send_mail(
                    'Welcome to HumanLoop',
                    f'Dear {user.name},\n\nThank you for signing up with HumanLoop! '
                    'We are excited to have you on board. You can now log in and start '
                    'making a social impact.\n\nBest regards,\nThe HumanLoop Team',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=True,
                )
            except Exception:
                pass
        threading.Thread(target=_send_welcome, daemon=True).start()

        return response

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f'Registration failed for {email}: {e}')
        return JsonResponse({
            'error': f'Registration failed: {str(e)}'
        }, status=500)


@csrf_exempt
def api_login(request):
    """POST: Log in with email and password, create session."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return JsonResponse({'error': 'Email and password are required'}, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User does not exist'}, status=404)

    if not user.is_active:
        # Admin superuser can never be locked out — auto-reactivate
        if user.role == 'admin' and check_password(password, user.password):
            user.is_active = True
            user.save()
            log_audit(user, 'Admin auto-reactivated on login', '', request)
        else:
            return JsonResponse({'error': 'Account is suspended'}, status=403)

    if not check_password(password, user.password):
        return JsonResponse({'error': 'Incorrect password'}, status=401)

    dashboards = {
        'innovator': 'dashboard',
        'ngo': 'dashboard-ngo',
        'beneficiary': 'dashboard-beneficiary',
        'admin': 'dashboard-admin',
    }

    # If 2FA is enabled, don't complete login yet — require TOTP code
    if user.two_fa_enabled:
        request.session['pending_2fa_user_id'] = user.id
        return JsonResponse({
            'requires_2fa': True,
            'message': 'Please enter your 2FA code',
        })

    # Normal login (no 2FA)
    request.session['user_id'] = user.id
    log_audit(user, 'User logged in', '', request)

    return JsonResponse({
        'success': True,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'organization': user.organization,
            'verified': user.verified,
            'language': user.language,
        },
        'redirect': dashboards.get(user.role, 'dashboard'),
    })


@csrf_exempt
def api_logout(request):
    """POST: Clear session."""
    user = get_current_user(request)
    if user:
        log_audit(user, 'User logged out', '', request)
    request.session.flush()
    return JsonResponse({'success': True})


@csrf_exempt
def api_send_otp(request):
    """POST: Send 6-digit OTP to email for password reset or verification."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    email = data.get('email', '').strip().lower()
    if not email:
        return JsonResponse({'error': 'Email is required'}, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User does not exist'}, status=404)

    otp = str(random.randint(100000, 999999))
    otp_expiry = timezone.now() + timedelta(minutes=5)

    request.session['reset_email'] = email
    request.session['otp'] = otp
    request.session['otp_expiry'] = otp_expiry.isoformat()

    try:
        send_mail(
            'HumanLoop — Password Reset OTP',
            f'Dear {user.name},\n\nYour OTP for password reset is: {otp}\n\n'
            'This OTP is valid for 5 minutes.\n\nIf you did not request this, '
            'please ignore this email.\n\nBest regards,\nHumanLoop Team',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
    except Exception as e:
        return JsonResponse({'error': f'Failed to send email: {str(e)}'}, status=500)

    return JsonResponse({'success': True, 'message': 'OTP sent to your email'})


@csrf_exempt
def api_verify_otp(request):
    """POST: Verify OTP code."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    otp_entered = data.get('otp', '')
    otp_stored = request.session.get('otp')
    otp_expiry = request.session.get('otp_expiry')
    email = request.session.get('reset_email')

    if not otp_stored or not otp_expiry or not email:
        return JsonResponse({'error': 'No OTP session found. Please request a new OTP.'}, status=400)

    if timezone.now() > dt.fromisoformat(otp_expiry):
        return JsonResponse({'error': 'OTP has expired. Please request a new one.'}, status=400)

    if otp_entered != otp_stored:
        return JsonResponse({'error': 'Invalid OTP'}, status=400)

    request.session['otp_verified'] = True

    # Auto-login — OTP proves identity
    try:
        user = User.objects.get(email=email)
        request.session['user_id'] = user.id
        dashboards = {
            'innovator': '/dashboard/',
            'ngo': '/dashboard-ngo/',
            'beneficiary': '/dashboard-beneficiary/',
            'admin': '/dashboard-admin/',
        }
        redirect_url = dashboards.get(user.role, '/dashboard/')
        return JsonResponse({
            'success': True, 'message': 'OTP verified',
            'email': email, 'role': user.role, 'redirect': redirect_url,
        })
    except User.DoesNotExist:
        return JsonResponse({'success': True, 'message': 'OTP verified', 'email': email})


@csrf_exempt
def api_reset_password(request):
    """POST: Reset password after OTP verification."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not request.session.get('otp_verified'):
        return JsonResponse({'error': 'Please verify OTP first'}, status=403)

    email = request.session.get('reset_email')
    new_password = data.get('new_password', '')
    if not new_password:
        return JsonResponse({'error': 'New password is required'}, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    user.password = make_password(new_password)
    user.save()

    # Clear OTP session
    for key in ['reset_email', 'otp', 'otp_expiry', 'otp_verified']:
        request.session.pop(key, None)

    try:
        send_mail(
            'HumanLoop — Password Reset Successful',
            f'Dear {user.name},\n\nYour password has been successfully reset.\n\n'
            'If you did not perform this action, please contact support immediately.\n\n'
            'Best regards,\nHumanLoop Team',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
    except Exception:
        pass

    log_audit(user, 'Password reset', '', request)

    # Auto-login after password reset
    request.session['user_id'] = user.id

    dashboards = {
        'innovator': '/dashboard/',
        'ngo': '/dashboard-ngo/',
        'beneficiary': '/dashboard-beneficiary/',
        'admin': '/dashboard-admin/',
    }
    redirect_url = dashboards.get(user.role, '/dashboard/')

    return JsonResponse({
        'success': True,
        'message': 'Password reset successful',
        'role': user.role,
        'redirect': redirect_url,
    })


# ──────────────────────────────────────────────────────────
# Settings API Endpoints
# ──────────────────────────────────────────────────────────

@csrf_exempt
@login_required_json
def api_profile(request):
    """GET: Get profile. PUT: Update profile."""
    user = get_current_user(request)

    if request.method == 'GET':
        return JsonResponse({
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'organization': user.organization,
            'mobile': user.mobile,
            'dob': str(user.dob) if user.dob else '',
            'language': user.language,
            'verified': user.verified,
            'two_fa_enabled': user.two_fa_enabled,
        })

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if 'name' in data:
            user.name = data['name']
        if 'organization' in data:
            user.organization = data['organization']
        if 'mobile' in data:
            user.mobile = data['mobile']
        if 'dob' in data and data['dob']:
            user.dob = data['dob']
        user.save()
        log_audit(user, 'Profile updated', '', request)
        return JsonResponse({'success': True, 'message': 'Profile updated'})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@login_required_json
def api_change_password(request):
    """POST: Change password (requires current password)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user = get_current_user(request)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    current = data.get('current_password', '')
    new_pwd = data.get('new_password', '')

    if not check_password(current, user.password):
        return JsonResponse({'error': 'Current password is incorrect'}, status=400)

    if len(new_pwd) < 8:
        return JsonResponse({'error': 'Password must be at least 8 characters'}, status=400)

    user.password = make_password(new_pwd)
    user.save()
    log_audit(user, 'Password changed', '', request)
    return JsonResponse({'success': True, 'message': 'Password changed successfully'})


@csrf_exempt
@login_required_json
def api_settings_notifications(request):
    """GET/PUT notification preferences."""
    user = get_current_user(request)

    if request.method == 'GET':
        return JsonResponse({
            'notif_email': user.notif_email,
            'notif_pilot_updates': user.notif_pilot_updates,
            'notif_team_activity': user.notif_team_activity,
            'notif_weekly_digest': user.notif_weekly_digest,
        })

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if 'notif_email' in data:
            user.notif_email = data['notif_email']
        if 'notif_pilot_updates' in data:
            user.notif_pilot_updates = data['notif_pilot_updates']
        if 'notif_team_activity' in data:
            user.notif_team_activity = data['notif_team_activity']
        if 'notif_weekly_digest' in data:
            user.notif_weekly_digest = data['notif_weekly_digest']
        user.save()
        return JsonResponse({'success': True, 'message': 'Notification preferences updated'})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@login_required_json
def api_settings_privacy(request):
    """GET/PUT privacy settings."""
    user = get_current_user(request)

    if request.method == 'GET':
        return JsonResponse({
            'profile_visibility': user.profile_visibility,
            'activity_status': user.activity_status,
            'usage_analytics': user.usage_analytics,
        })

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if 'profile_visibility' in data:
            user.profile_visibility = data['profile_visibility']
        if 'activity_status' in data:
            user.activity_status = data['activity_status']
        if 'usage_analytics' in data:
            user.usage_analytics = data['usage_analytics']
        user.save()
        return JsonResponse({'success': True, 'message': 'Privacy settings updated'})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@login_required_json
def api_settings_language(request):
    """PUT: Set language preference — beneficiary only."""
    if request.method != 'PUT':
        return JsonResponse({'error': 'PUT required'}, status=405)

    user = get_current_user(request)

    # Multilingual is beneficiary-only
    if user.role != 'beneficiary':
        return JsonResponse({'error': 'Language switching is only available for beneficiary accounts'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    lang = data.get('language', 'en')
    valid_langs = [c[0] for c in User._meta.get_field('language').choices]
    if lang not in valid_langs:
        return JsonResponse({'error': f'Invalid language: {lang}'}, status=400)

    user.language = lang
    user.save()
    return JsonResponse({'success': True, 'message': 'Language updated', 'language': lang})


@csrf_exempt
@login_required_json
def api_delete_account(request):
    """POST: Deactivate (soft-delete) account."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user = get_current_user(request)
    user.is_active = False
    user.save()
    log_audit(user, 'Account deactivated', '', request)
    request.session.flush()
    return JsonResponse({'success': True, 'message': 'Account deactivated'})


# ──────────────────────────────────────────────────────────
# Two-Factor Authentication API Endpoints
# ──────────────────────────────────────────────────────────

@csrf_exempt
@login_required_json
def api_2fa_setup(request):
    """GET: Generate TOTP secret + QR code for 2FA setup."""
    import pyotp
    import qrcode
    import io
    import base64

    user = get_current_user(request)

    if user.two_fa_enabled:
        return JsonResponse({'error': '2FA is already enabled'}, status=400)

    # Generate a new secret
    secret = pyotp.random_base32()

    # Store in session temporarily until verified
    request.session['pending_2fa_secret'] = secret

    # Generate provisioning URI for authenticator apps
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user.email, issuer_name='HumanLoop')

    # Generate QR code as base64 image
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return JsonResponse({
        'success': True,
        'secret': secret,
        'qr_code': f'data:image/png;base64,{qr_base64}',
    })


@csrf_exempt
@login_required_json
def api_2fa_verify_setup(request):
    """POST: Verify TOTP code to complete 2FA setup."""
    import pyotp

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user = get_current_user(request)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    code = data.get('code', '').strip()
    secret = request.session.get('pending_2fa_secret')

    if not secret:
        return JsonResponse({'error': 'No 2FA setup in progress. Please start setup again.'}, status=400)

    if not code:
        return JsonResponse({'error': 'Verification code is required'}, status=400)

    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        return JsonResponse({'error': 'Invalid code. Please try again.'}, status=400)

    # Enable 2FA
    user.two_fa_secret = secret
    user.two_fa_enabled = True
    user.save()

    # Clean up session
    request.session.pop('pending_2fa_secret', None)

    log_audit(user, '2FA enabled', '', request)

    return JsonResponse({'success': True, 'message': 'Two-Factor Authentication enabled successfully'})


@csrf_exempt
@login_required_json
def api_2fa_disable(request):
    """POST: Disable 2FA (requires current password + TOTP code)."""
    import pyotp

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user = get_current_user(request)

    if not user.two_fa_enabled:
        return JsonResponse({'error': '2FA is not enabled'}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    password = data.get('password', '')
    code = data.get('code', '').strip()

    if not check_password(password, user.password):
        return JsonResponse({'error': 'Incorrect password'}, status=400)

    totp = pyotp.TOTP(user.two_fa_secret)
    if not totp.verify(code, valid_window=1):
        return JsonResponse({'error': 'Invalid 2FA code'}, status=400)

    user.two_fa_enabled = False
    user.two_fa_secret = ''
    user.save()

    log_audit(user, '2FA disabled', '', request)

    return JsonResponse({'success': True, 'message': 'Two-Factor Authentication disabled'})


@csrf_exempt
def api_2fa_verify_login(request):
    """POST: Verify TOTP code during login (second step)."""
    import pyotp

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    user_id = request.session.get('pending_2fa_user_id')
    if not user_id:
        return JsonResponse({'error': 'No pending 2FA login. Please log in again.'}, status=400)

    code = data.get('code', '').strip()
    if not code:
        return JsonResponse({'error': '2FA code is required'}, status=400)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    totp = pyotp.TOTP(user.two_fa_secret)
    if not totp.verify(code, valid_window=1):
        return JsonResponse({'error': 'Invalid 2FA code. Please try again.'}, status=400)

    # Complete login
    request.session['user_id'] = user.id
    request.session.pop('pending_2fa_user_id', None)

    log_audit(user, 'User logged in (2FA verified)', '', request)

    dashboards = {
        'innovator': 'dashboard',
        'ngo': 'dashboard-ngo',
        'beneficiary': 'dashboard-beneficiary',
        'admin': 'dashboard-admin',
    }

    return JsonResponse({
        'success': True,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'organization': user.organization,
            'verified': user.verified,
            'language': user.language,
        },
        'redirect': dashboards.get(user.role, 'dashboard'),
    })


# ──────────────────────────────────────────────────────────
# Dashboard & Data API Endpoints
# ──────────────────────────────────────────────────────────

@csrf_exempt
@login_required_json
def api_dashboard_stats(request):
    """GET: Dashboard stats for the current user."""
    user = get_current_user(request)

    if user.role == 'admin':
        data = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'total_pilots': Pilot.objects.count(),
            'active_pilots': Pilot.objects.filter(status='active').count(),
            'total_ngos': User.objects.filter(role='ngo').count(),
            'total_beneficiaries': User.objects.filter(role='beneficiary').count(),
            'total_budget': float(Pilot.objects.aggregate(t=Sum('budget'))['t'] or 0),
        }
    elif user.role == 'ngo':
        assigned = Pilot.objects.filter(assigned_ngo=user)
        count = assigned.count()
        progress_sum = assigned.aggregate(a=Sum('progress'))['a'] or 0
        data = {
            'assigned_pilots': count,
            'active_pilots': assigned.filter(status='active').count(),
            'team_members': TeamMember.objects.filter(pilot__assigned_ngo=user).count(),
            'avg_progress': round(progress_sum / max(count, 1)),
        }
    elif user.role == 'beneficiary':
        enrollments = BeneficiaryEnrollment.objects.filter(user=user).select_related('pilot')
        data = {
            'programs': enrollments.count(),
            'feedback_count': Feedback.objects.filter(user=user).count(),
            'certificate_count': Certificate.objects.filter(beneficiary=user).count(),
            'badges': sum(len(e.badges_earned) for e in enrollments),
            'enrollments': [{
                'pilot_id': e.pilot.id,
                'pilot_title': e.pilot.title,
                'pilot_location': e.pilot.location,
                'status': e.pilot.status,
                'badges': e.badges_earned,
            } for e in enrollments],
        }
    else:
        # innovator
        my_pilots = Pilot.objects.filter(created_by=user)
        data = {
            'total_pilots': my_pilots.count(),
            'active_pilots': my_pilots.filter(status='active').count(),
            'total_beneficiaries': my_pilots.aggregate(t=Sum('target_beneficiaries'))['t'] or 0,
            'total_budget': float(my_pilots.aggregate(t=Sum('budget'))['t'] or 0),
            'total_spent': float(Expense.objects.filter(pilot__in=my_pilots).aggregate(t=Sum('amount'))['t'] or 0),
        }

    return JsonResponse(data)


@csrf_exempt
@login_required_json
def api_pilots(request):
    """GET: List pilots. POST: Create a pilot."""
    user = get_current_user(request)

    if request.method == 'GET':
        if user.role == 'admin':
            pilots = Pilot.objects.all()
        elif user.role == 'ngo':
            pilots = Pilot.objects.filter(assigned_ngo=user)
        else:
            pilots = Pilot.objects.filter(created_by=user)

        pilot_list = [{
            'id': p.id,
            'title': p.title,
            'activity_type': p.activity_type,
            'location': p.location,
            'target_date': str(p.target_date),
            'budget': float(p.budget),
            'status': p.status,
            'progress': p.progress,
            'created_at': p.created_at.isoformat(),
        } for p in pilots]

        return JsonResponse({'pilots': pilot_list})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        # Determine assigned NGO and status
        assigned_ngo = None
        selected_ngo_id = data.get('selected_ngo_id')  # From the planner step 2
        
        if user.role == 'ngo':
            # NGO creating their own pilot — directly active
            assigned_ngo = user
            initial_status = 'active'
        elif selected_ngo_id:
            # Innovator selected an NGO — needs admin approval first
            initial_status = 'pending_admin'
        else:
            # No NGO selected — draft
            initial_status = data.get('status', 'draft')

        # Validate target date is not in the past
        target_date_str = data.get('date', '')
        if target_date_str:
            from datetime import datetime as dt
            try:
                target_date = dt.strptime(target_date_str, '%Y-%m-%d').date()
                if target_date < timezone.now().date():
                    return JsonResponse({'error': 'Target date cannot be in the past'}, status=400)
            except ValueError:
                pass

        pilot = Pilot.objects.create(
            title=data.get('title', f"{data.get('activity_type', 'Pilot')} at {data.get('location', 'TBD')}"),
            activity_type=data.get('activity_type', ''),
            location=data.get('location', ''),
            target_date=data.get('date', timezone.now().date()),
            budget=data.get('budget', 0),
            expected_members=data.get('members', 0),
            target_beneficiaries=data.get('beneficiaries', 0),
            status=initial_status,
            ai_plan=data.get('ai_plan', ''),
            ai_ngo_recommendations=data.get('ai_ngo_recommendations', []),
            created_by=user,
            assigned_ngo=assigned_ngo,
            tasks=data.get('tasks', [
                {'name': 'Confirm venue and logistics', 'done': False},
                {'name': 'Recruit team members', 'done': False},
                {'name': 'Purchase materials and supplies', 'done': False},
                {'name': 'Notify beneficiaries', 'done': False},
                {'name': 'Conduct pilot activity', 'done': False},
                {'name': 'Collect feedback', 'done': False},
                {'name': 'Submit final report', 'done': False},
            ]),
        )

        log_audit(user, 'Pilot created', f'Pilot: {pilot.title}', request)

        # If innovator selected an NGO, create the assignment request
        if selected_ngo_id and user.role != 'ngo':
            try:
                requested_ngo = User.objects.get(id=selected_ngo_id, role='ngo')
                PilotAssignment.objects.create(
                    pilot=pilot,
                    requested_ngo=requested_ngo,
                    requested_by=user,
                    status='pending_ngo',
                )
                # Update pilot status
                pilot.status = 'pending_ngo'
                pilot.save()
                # Notify the NGO (first step in flow)
                Notification.objects.create(
                    user=requested_ngo,
                    title='New Pilot Request 🤝',
                    message=f'{user.name} has requested you to manage the pilot "{pilot.title}". Please accept or decline.',
                    icon='fa-handshake',
                )
                log_audit(user, 'NGO assignment requested',
                          f'{pilot.title} → {requested_ngo.name}', request)
            except User.DoesNotExist:
                pass

        # Notify the creator
        Notification.objects.create(
            user=user,
            title='Pilot Created',
            message=f'Your pilot "{pilot.title}" has been created successfully.' + (
                ' Request sent to NGO for acceptance.' if selected_ngo_id else ''
            ),
            icon='fa-rocket',
        )

        return JsonResponse({
            'success': True,
            'pilot': {
                'id': pilot.id,
                'title': pilot.title,
                'status': pilot.status,
            }
        })

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@login_required_json
def api_pilot_detail(request, pilot_id):
    """GET: Pilot detail. PUT: Update pilot (tasks, status, etc.)."""
    pilot = get_object_or_404(Pilot, id=pilot_id)

    if request.method == 'GET':
        # Calculate spent budget
        spent = Expense.objects.filter(pilot=pilot).aggregate(total=Sum('amount'))['total'] or 0
        # Team members for this pilot
        team = TeamMember.objects.filter(pilot=pilot).select_related('user')
        team_list = [{'id': t.id, 'name': t.user.name, 'role': t.team_role} for t in team]

        # Also include OrgMembers from the assigned NGO's organization
        if pilot.assigned_ngo and not team_list:
            org_members = OrgMember.objects.filter(organization=pilot.assigned_ngo.organization)
            team_list = [{'id': m.id, 'name': m.name, 'role': m.job_role} for m in org_members]

        return JsonResponse({
            'id': pilot.id,
            'title': pilot.title,
            'activity_type': pilot.activity_type,
            'location': pilot.location,
            'target_date': str(pilot.target_date),
            'budget': float(pilot.budget),
            'spent': float(spent),
            'expected_members': pilot.expected_members,
            'target_beneficiaries': pilot.target_beneficiaries,
            'status': pilot.status,
            'progress': pilot.progress,
            'tasks': pilot.tasks or [],
            'ai_plan': pilot.ai_plan,
            'ai_ngo_recommendations': pilot.ai_ngo_recommendations,
            'assigned_ngo': pilot.assigned_ngo.name if pilot.assigned_ngo else None,
            'created_by': pilot.created_by.name,
            'team': team_list,
            'created_at': pilot.created_at.isoformat(),
        })

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        user = get_current_user(request)

        # ── Handle completion request (NGO requests → pending_completion) ──
        if data.get('status') == 'completed':
            # Only NGO can request completion
            if user.role not in ('ngo', 'admin'):
                return JsonResponse({'error': 'Only the assigned NGO can request pilot completion.'}, status=403)

            # Admin direct approval of pending_completion
            if user.role == 'admin' and pilot.status == 'pending_completion':
                pilot.status = 'completed'
                pilot.save()
                log_audit(user, 'Pilot completion approved', f'{pilot.title}', request)
                # Notify NGO
                if pilot.assigned_ngo:
                    Notification.objects.create(
                        user=pilot.assigned_ngo,
                        title='Pilot Completion Approved',
                        message=f'Admin has approved the completion of "{pilot.title}".',
                        icon='fa-circle-check',
                    )
                # Notify innovator
                Notification.objects.create(
                    user=pilot.created_by,
                    title='Pilot Completed',
                    message=f'"{pilot.title}" has been officially marked as completed.',
                    icon='fa-circle-check',
                )
                return JsonResponse({
                    'success': True,
                    'message': 'Pilot completion approved by admin.',
                    'status': pilot.status,
                    'progress': pilot.progress,
                })

            # NGO requesting completion — validate conditions
            errors = []

            # Check 1: All tasks must be completed
            tasks = pilot.tasks or []
            if not tasks:
                errors.append('No tasks found. Please add tasks before completing.')
            else:
                incomplete_tasks = [t.get('name', 'Unnamed') for t in tasks if not t.get('done')]
                if incomplete_tasks:
                    errors.append(f'{len(incomplete_tasks)} task(s) are still incomplete: {", ".join(incomplete_tasks[:5])}')

            # Check 2: Budget must be fully allocated (spent >= 80% of budget)
            spent = Expense.objects.filter(pilot=pilot).aggregate(total=Sum('amount'))['total'] or 0
            budget = float(pilot.budget)
            if budget > 0:
                spent_pct = (float(spent) / budget) * 100
                if spent_pct < 80:
                    errors.append(
                        f'Only {spent_pct:.0f}% of the budget has been allocated '
                        f'(Rs.{float(spent):,.0f} of Rs.{budget:,.0f}). '
                        f'At least 80% must be allocated before completion.'
                    )
            else:
                errors.append('No budget set for this pilot.')

            # If validation fails, return errors
            if errors:
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot mark pilot as complete.',
                    'reasons': errors,
                }, status=400)

            # All checks passed → set to pending_completion
            pilot.status = 'pending_completion'
            pilot.save()
            log_audit(user, 'Pilot completion requested', f'{pilot.title}', request)

            # Notify all admins
            admins = User.objects.filter(role='admin', is_active=True)
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    title='Pilot Completion Request',
                    message=f'NGO "{user.name}" has requested completion approval for "{pilot.title}". Please review.',
                    icon='fa-clipboard-check',
                )

            return JsonResponse({
                'success': True,
                'message': 'Completion request submitted. Waiting for admin approval.',
                'status': pilot.status,
                'progress': pilot.progress,
            })

        # ── Handle admin rejection of completion ──
        if data.get('status') == 'active' and pilot.status == 'pending_completion':
            if user.role != 'admin':
                return JsonResponse({'error': 'Only admin can reject completion.'}, status=403)
            pilot.status = 'active'
            pilot.save()
            log_audit(user, 'Pilot completion rejected', f'{pilot.title}', request)

            rejection_reason = data.get('rejection_reason', 'No reason provided.')
            if pilot.assigned_ngo:
                Notification.objects.create(
                    user=pilot.assigned_ngo,
                    title='Pilot Completion Rejected',
                    message=f'Admin has rejected the completion of "{pilot.title}". Reason: {rejection_reason}',
                    icon='fa-times-circle',
                )
            return JsonResponse({
                'success': True,
                'message': 'Completion rejected. Pilot set back to active.',
                'status': pilot.status,
                'progress': pilot.progress,
            })

        # ── Normal updates (tasks, title, etc.) ──
        if 'status' in data:
            pilot.status = data['status']
        if 'title' in data:
            pilot.title = data['title']
        if 'tasks' in data:
            pilot.tasks = data['tasks']
            tasks = data['tasks']
            if tasks:
                done = sum(1 for t in tasks if t.get('done'))
                pilot.progress = round(done / len(tasks) * 100)
            else:
                pilot.progress = 0
        if 'progress' in data and 'tasks' not in data:
            pilot.progress = data['progress']
        pilot.save()

        return JsonResponse({
            'success': True,
            'message': 'Pilot updated',
            'progress': pilot.progress,
            'status': pilot.status,
        })

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@login_required_json
def api_expenses(request, pilot_id):
    """GET: List expenses for a pilot. POST: Add expense."""
    pilot = get_object_or_404(Pilot, id=pilot_id)
    user = get_current_user(request)

    if request.method == 'GET':
        expenses = Expense.objects.filter(pilot=pilot)
        return JsonResponse({
            'expenses': [{
                'id': e.id,
                'description': e.description,
                'amount': float(e.amount),
                'category': e.category,
                'date': str(e.date),
            } for e in expenses],
            'total': float(expenses.aggregate(t=Sum('amount'))['t'] or 0),
        })

    if request.method == 'POST':
        # Only NGOs and admins can add expenses
        if user.role == 'innovator':
            return JsonResponse({'error': 'Only the assigned NGO can add expenses'}, status=403)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        expense = Expense.objects.create(
            pilot=pilot,
            description=data.get('item', data.get('description', '')),
            amount=data.get('amount', 0),
            category=data.get('category', 'other'),
            created_by=user,
        )
        return JsonResponse({'success': True, 'id': expense.id})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@login_required_json
def api_expense_delete(request, expense_id):
    """DELETE: Remove an expense."""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'DELETE required'}, status=405)

    user = get_current_user(request)
    if user.role == 'innovator':
        return JsonResponse({'error': 'Only the assigned NGO can delete expenses'}, status=403)

    expense = get_object_or_404(Expense, id=expense_id)
    expense.delete()
    return JsonResponse({'success': True})


@csrf_exempt
@login_required_json
def api_feedback(request):
    """GET: List user's own feedback. POST: Submit new feedback."""
    user = get_current_user(request)

    if request.method == 'GET':
        feedbacks = Feedback.objects.filter(user=user).select_related('pilot').order_by('-created_at')[:20]
        return JsonResponse({'feedback': [{
            'id': f.id,
            'pilot_id': f.pilot.id if f.pilot else None,
            'pilot_title': f.pilot.title if f.pilot else 'General',
            'rating': f.rating,
            'message': f.message,
            'created_at': f.created_at.isoformat(),
        } for f in feedbacks]})

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    pilot = None
    if data.get('pilot_id'):
        pilot = Pilot.objects.filter(id=data['pilot_id']).first()

    # Build message including tags and category for richer context
    message = data.get('message', '')
    tags = data.get('tags', [])
    category = data.get('category', '')
    if tags or category:
        suffix_parts = []
        if category:
            suffix_parts.append(f'[Category: {category}]')
        if tags:
            suffix_parts.append(f'[Tags: {", ".join(tags)}]')
        message = message + '\n' + ' '.join(suffix_parts) if message else ' '.join(suffix_parts)

    Feedback.objects.create(
        user=user,
        pilot=pilot,
        rating=data.get('rating', 5),
        message=message,
    )
    return JsonResponse({'success': True, 'message': 'Feedback submitted'})




@csrf_exempt
@login_required_json
def api_notifications(request):
    """GET: List notifications for current user."""
    user = get_current_user(request)
    notifs = Notification.objects.filter(user=user)[:20]
    return JsonResponse({
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'icon': n.icon,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
        } for n in notifs],
        'unread_count': Notification.objects.filter(user=user, is_read=False).count(),
    })


# ──────────────────────────────────────────────────────────
# Admin API Endpoints
# ──────────────────────────────────────────────────────────

@csrf_exempt
@login_required_json
def api_admin_users(request):
    """GET: List all users (admin only)."""
    user = get_current_user(request)
    if user.role != 'admin':
        return JsonResponse({'error': 'Admin access required'}, status=403)

    users = User.objects.all().order_by('-created_at')
    return JsonResponse({
        'users': [{
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'role': u.role,
            'organization': u.organization,
            'is_active': u.is_active,
            'created_at': u.created_at.isoformat(),
        } for u in users]
    })


@csrf_exempt
@login_required_json
def api_admin_toggle_user(request, user_id):
    """POST: Suspend/activate a user (admin only)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    admin = get_current_user(request)
    if admin.role != 'admin':
        return JsonResponse({'error': 'Admin access required'}, status=403)

    target = get_object_or_404(User, id=user_id)
    target.is_active = not target.is_active
    target.save()

    action = 'activated' if target.is_active else 'suspended'
    log_audit(admin, f'User {action}', f'{target.name} ({target.email})', request)

    return JsonResponse({
        'success': True,
        'is_active': target.is_active,
        'message': f'User {action}',
    })


@csrf_exempt
@login_required_json
def api_admin_audit_log(request):
    """GET: Get audit log (admin only)."""
    user = get_current_user(request)
    if user.role != 'admin':
        return JsonResponse({'error': 'Admin access required'}, status=403)

    logs = AuditLog.objects.select_related('user').all()[:50]
    return JsonResponse({
        'logs': [{
            'id': l.id,
            'user': l.user.name if l.user else 'System',
            'action': l.action,
            'details': l.details,
            'ip_address': l.ip_address,
            'created_at': l.created_at.isoformat(),
        } for l in logs]
    })


# ──────────────────────────────────────────────────────────
# AI Endpoint
# ──────────────────────────────────────────────────────────

@csrf_exempt
@login_required_json
def api_generate_plan(request):
    """POST: Generate AI pilot plan using RAG engine + qwen2:0.5b."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user = get_current_user(request)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    result = generate_plan(data)
    log_audit(user, 'AI plan generated', f"Activity: {data.get('activity_type', 'N/A')}", request)

    return JsonResponse({
        'success': True,
        'plan': result.get('plan', ''),
        'ngo_recommendations': result.get('ngo_recommendations', []),
        'sources': result.get('sources', []),
        'estimates': result.get('estimates'),
        'error': result.get('error'),
    })


# ──────────────────────────────────────────────────────────
# Team API Endpoints
# ──────────────────────────────────────────────────────────

@csrf_exempt
@login_required_json
def api_team(request):
    """GET: List org team members. POST: Add a new team member."""
    user = get_current_user(request)
    org = user.organization or ''

    if request.method == 'GET':
        members = OrgMember.objects.filter(organization=org).order_by('name')
        return JsonResponse({
            'members': [{
                'id': m.id,
                'name': m.name,
                'email': m.email,
                'job_role': m.job_role,
                'joined': str(m.joined),
            } for m in members]
        })

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        job_role = data.get('job_role', 'Member').strip()

        if not name or len(name) < 2:
            return JsonResponse({'error': 'Name is required (at least 2 characters)'}, status=400)
        if not any(c.isalpha() for c in name):
            return JsonResponse({'error': 'Name must contain at least one letter'}, status=400)
        if not email:
            return JsonResponse({'error': 'Email is required'}, status=400)

        if OrgMember.objects.filter(email=email, organization=org).exists():
            return JsonResponse({'error': 'This member is already on your team'}, status=400)

        member = OrgMember.objects.create(
            name=name,
            email=email,
            job_role=job_role,
            organization=org,
            added_by=user,
        )
        log_audit(user, 'Team member added', f'{name} ({email})', request)
        return JsonResponse({
            'success': True,
            'member': {
                'id': member.id,
                'name': member.name,
                'email': member.email,
                'job_role': member.job_role,
                'joined': str(member.joined),
            }
        })

    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ──────────────────────────────────────────────────────────
# Enrollment API
# ──────────────────────────────────────────────────────────
@csrf_exempt
def api_enroll(request):
    """POST — enroll the logged-in beneficiary in a pilot program."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    user = get_current_user(request)
    if not user:
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    pilot_id = body.get('pilot_id')
    if not pilot_id:
        return JsonResponse({'error': 'pilot_id is required'}, status=400)

    try:
        pilot = Pilot.objects.get(id=pilot_id, status='active')
    except Pilot.DoesNotExist:
        return JsonResponse({'error': 'Program not found or not active'}, status=404)

    # Prevent duplicate enrollment
    if BeneficiaryEnrollment.objects.filter(user=user, pilot=pilot).exists():
        t = get_translations(user.language)
        return JsonResponse({'error': t.get('already_enrolled', 'Already enrolled')}, status=409)

    enrollment = BeneficiaryEnrollment.objects.create(
        user=user,
        pilot=pilot,
        total_sessions=10,
    )
    log_audit(user, 'Enrolled in program', f'{pilot.title}', request)

    return JsonResponse({
        'success': True,
        'enrollment': {
            'id': enrollment.id,
            'pilot_id': pilot.id,
            'pilot_title': pilot.title,
            'enrolled_at': str(enrollment.enrolled_at),
        }
    })


# ──────────────────────────────────────────────────────────
# Assignment Workflow APIs
# ──────────────────────────────────────────────────────────
@csrf_exempt
@login_required_json
def api_assignments(request):
    """GET: List assignment requests (filtered by role)."""
    user = get_current_user(request)

    if request.method == 'GET':
        if user.role == 'admin':
            # Admins see pending requests
            qs = PilotAssignment.objects.select_related(
                'pilot', 'requested_ngo', 'requested_by'
            ).all()
        elif user.role == 'ngo':
            # NGO sees requests sent to them
            qs = PilotAssignment.objects.filter(
                requested_ngo=user
            ).select_related('pilot', 'requested_by')
        elif user.role == 'innovator':
            # Innovator sees their own requests
            qs = PilotAssignment.objects.filter(
                requested_by=user
            ).select_related('pilot', 'requested_ngo')
        else:
            qs = PilotAssignment.objects.none()

        items = []
        for a in qs[:50]:
            items.append({
                'id': a.id,
                'pilot_id': a.pilot.id,
                'pilot_title': a.pilot.title,
                'pilot_activity': a.pilot.activity_type,
                'pilot_location': a.pilot.location,
                'pilot_budget': float(a.pilot.budget),
                'requested_ngo_id': a.requested_ngo.id,
                'requested_ngo_name': a.requested_ngo.name,
                'requested_by_name': a.requested_by.name,
                'status': a.status,
                'admin_notes': a.admin_notes,
                'ngo_notes': a.ngo_notes,
                'created_at': a.created_at.isoformat(),
            })

        return JsonResponse({'assignments': items})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@login_required_json
def api_assignment_action(request, assignment_id):
    """PUT: Admin approves or rejects an assignment request (after NGO accepted)."""
    if request.method != 'PUT':
        return JsonResponse({'error': 'PUT required'}, status=405)

    user = get_current_user(request)
    if user.role != 'admin':
        return JsonResponse({'error': 'Admin access required'}, status=403)

    assignment = get_object_or_404(PilotAssignment, id=assignment_id)

    if assignment.status != 'ngo_accepted':
        # If already approved, return success message instead of error
        if assignment.status in ('admin_approved', 'payment_pending', 'payment_done'):
            return JsonResponse({
                'success': True,
                'message': '✅ Already approved successfully!',
                'status': assignment.status,
            })
        return JsonResponse({'error': f'Cannot review — current status is {assignment.status}'}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    action = data.get('action')  # 'approve' or 'reject'
    notes = data.get('notes', '')

    if action == 'approve':
        assignment.status = 'admin_approved'
        assignment.admin_reviewed_by = user
        assignment.admin_notes = notes
        assignment.admin_reviewed_at = timezone.now()
        assignment.save()

        # Update pilot status to payment pending
        assignment.pilot.status = 'pending_payment'
        assignment.pilot.save()

        # Notify the innovator — payment gateway is now open
        Notification.objects.create(
            user=assignment.requested_by,
            title='Pilot Verified! 🎉 Payment Required',
            message=f'Your pilot "{assignment.pilot.title}" has been verified by admin. Please complete payment to activate it.',
            icon='fa-credit-card',
        )

        # Send email to innovator
        try:
            from django.core.mail import send_mail
            from django.conf import settings as django_settings
            pilot = assignment.pilot
            commission = float(pilot.budget) * 0.05
            total = float(pilot.budget) + commission
            send_mail(
                subject=f'✅ Pilot "{pilot.title}" Verified — Complete Payment',
                message=(
                    f'Dear {assignment.requested_by.name},\n\n'
                    f'Great news! Your pilot "{pilot.title}" has been verified by admin '
                    f'and accepted by {assignment.requested_ngo.name}.\n\n'
                    f'To activate the pilot, please complete the payment:\n'
                    f'  Pilot Budget: ₹{pilot.budget}\n'
                    f'  Platform Fee (5%): ₹{commission:.2f}\n'
                    f'  Total: ₹{total:.2f}\n\n'
                    f'Log in to your dashboard and click "Pay Now" to proceed.\n\n'
                    f'Best regards,\nHumanLoop Team'
                ),
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[assignment.requested_by.email],
                fail_silently=True,
            )
        except Exception:
            pass  # Email failure should not block the approval

        log_audit(user, 'Assignment approved by admin', f'{assignment.pilot.title} → {assignment.requested_ngo.name}', request)

        return JsonResponse({'success': True, 'status': 'admin_approved'})

    elif action == 'reject':
        assignment.status = 'admin_rejected'
        assignment.admin_reviewed_by = user
        assignment.admin_notes = notes
        assignment.admin_reviewed_at = timezone.now()
        assignment.save()

        # Revert pilot to draft
        assignment.pilot.status = 'draft'
        assignment.pilot.save()

        # Notify innovator
        Notification.objects.create(
            user=assignment.requested_by,
            title='Assignment Rejected by Admin',
            message=f'Admin rejected "{assignment.pilot.title}". Reason: {notes or "No reason given."}',
            icon='fa-circle-xmark',
        )
        # Notify NGO
        Notification.objects.create(
            user=assignment.requested_ngo,
            title='Assignment Rejected by Admin',
            message=f'Admin rejected the assignment for "{assignment.pilot.title}".',
            icon='fa-circle-xmark',
        )

        log_audit(user, 'Assignment rejected by admin', f'{assignment.pilot.title}', request)

        return JsonResponse({'success': True, 'status': 'admin_rejected'})

    return JsonResponse({'error': 'Invalid action. Use "approve" or "reject".'}, status=400)


@csrf_exempt
@login_required_json
def api_ngo_respond(request, assignment_id):
    """PUT: NGO accepts or rejects an assignment request (first step)."""
    if request.method != 'PUT':
        return JsonResponse({'error': 'PUT required'}, status=405)

    user = get_current_user(request)
    assignment = get_object_or_404(PilotAssignment, id=assignment_id)

    if assignment.requested_ngo != user:
        return JsonResponse({'error': 'This request is not for you'}, status=403)

    if assignment.status != 'pending_ngo':
        return JsonResponse({'error': f'Cannot respond — current status is {assignment.status}'}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    action = data.get('action')  # 'accept' or 'reject'
    notes = data.get('notes', '')

    if action == 'accept':
        assignment.status = 'ngo_accepted'
        assignment.ngo_notes = notes
        assignment.ngo_responded_at = timezone.now()
        assignment.save()

        # Update pilot status — now pending admin review
        assignment.pilot.status = 'pending_admin'
        assignment.pilot.save()

        # Notify innovator
        Notification.objects.create(
            user=assignment.requested_by,
            title='NGO Accepted! Pending Admin Review',
            message=f'{user.name} has accepted to manage "{assignment.pilot.title}". Waiting for admin verification.',
            icon='fa-circle-check',
        )

        log_audit(user, 'NGO accepted assignment', f'{assignment.pilot.title}', request)

        return JsonResponse({'success': True, 'status': 'ngo_accepted'})

    elif action == 'reject':
        assignment.status = 'ngo_rejected'
        assignment.ngo_notes = notes
        assignment.ngo_responded_at = timezone.now()
        assignment.save()

        # Revert pilot to draft
        assignment.pilot.status = 'draft'
        assignment.pilot.save()

        # Notify innovator
        Notification.objects.create(
            user=assignment.requested_by,
            title='NGO Declined',
            message=f'{user.name} declined to manage "{assignment.pilot.title}". You may select another NGO.',
            icon='fa-circle-xmark',
        )

        log_audit(user, 'NGO rejected assignment', f'{assignment.pilot.title}', request)

        return JsonResponse({'success': True, 'status': 'ngo_rejected'})

    return JsonResponse({'error': 'Invalid action. Use "accept" or "reject".'}, status=400)


# ──────────────────────────────────────────────────────────
# Data Download API (Settings)
# ──────────────────────────────────────────────────────────
@csrf_exempt
@login_required_json
def api_download_data(request):
    """GET: Download all user data as JSON."""
    user = get_current_user(request)

    # Gather all user's data
    pilots = Pilot.objects.filter(created_by=user)
    expenses = Expense.objects.filter(created_by=user)
    feedbacks = Feedback.objects.filter(user=user)
    notifications = Notification.objects.filter(user=user)
    audit = AuditLog.objects.filter(user=user)

    profile_data = {
        'name': user.name,
        'email': user.email,
        'role': user.role,
        'organization': user.organization,
        'mobile': user.mobile,
        'language': user.language,
        'created_at': user.created_at.isoformat(),
    }

    pilots_data = [
        {
            'title': p.title,
            'activity_type': p.activity_type,
            'location': p.location,
            'status': p.status,
            'budget': float(p.budget),
            'progress': p.progress,
            'created_at': p.created_at.isoformat(),
        }
        for p in pilots
    ]

    expenses_data = [
        {
            'description': e.description,
            'amount': float(e.amount),
            'category': e.category,
            'date': str(e.date),
        }
        for e in expenses
    ]

    feedbacks_data = [
        {
            'rating': f.rating,
            'message': f.message,
            'created_at': f.created_at.isoformat(),
        }
        for f in feedbacks
    ]

    activity_data = [
        {
            'action': a.action,
            'details': a.details,
            'created_at': a.created_at.isoformat(),
        }
        for a in audit[:100]
    ]

    # Build a ZIP file containing separate JSON files
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('profile.json', json.dumps(profile_data, indent=2, ensure_ascii=False))
        zf.writestr('pilots.json', json.dumps(pilots_data, indent=2, ensure_ascii=False))
        zf.writestr('expenses.json', json.dumps(expenses_data, indent=2, ensure_ascii=False))
        zf.writestr('feedbacks.json', json.dumps(feedbacks_data, indent=2, ensure_ascii=False))
        zf.writestr('activity_log.json', json.dumps(activity_data, indent=2, ensure_ascii=False))
    buffer.seek(0)

    from django.http import HttpResponse
    response = HttpResponse(buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="humanloop_data_{user.id}.zip"'
    return response


# ──────────────────────────────────────────────────────────
# AI Insights API
# ──────────────────────────────────────────────────────────
@csrf_exempt
@login_required_json
def api_ai_insights(request):
    """GET: Get AI-powered insights for the current user's role."""
    user = get_current_user(request)
    # Get user's preferred language for multilingual insights
    lang = getattr(user, 'preferred_language', 'en') or 'en'
    insights = generate_insights(user, lang=lang)
    return JsonResponse({'insights': insights})


# ──────────────────────────────────────────────────────────
# Certificate API Endpoints
# ──────────────────────────────────────────────────────────
@csrf_exempt
@login_required_json
def api_certificates(request):
    """GET: List certificates for the current user (beneficiary) or all (admin)."""
    user = get_current_user(request)

    if user.role == 'admin':
        certs = Certificate.objects.all().select_related('beneficiary', 'pilot', 'issued_by')
    elif user.role == 'beneficiary':
        certs = Certificate.objects.filter(beneficiary=user).select_related('pilot', 'issued_by')
    else:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    return JsonResponse({'certificates': [{
        'id': c.id,
        'certificate_number': c.certificate_number,
        'title': c.title,
        'description': c.description,
        'pilot_title': c.pilot.title if c.pilot else '',
        'pilot_id': c.pilot.id if c.pilot else None,
        'beneficiary_name': c.beneficiary.name,
        'beneficiary_id': c.beneficiary.id,
        'issued_by': c.issued_by.name if c.issued_by else '',
        'issued_at': c.issued_at.isoformat(),
    } for c in certs]})


@csrf_exempt
@login_required_json
def api_issue_certificate(request):
    """POST: Admin issues a certificate to a beneficiary for a pilot."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user = get_current_user(request)
    if user.role != 'admin':
        return JsonResponse({'error': 'Admin access required'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    beneficiary_id = data.get('beneficiary_id')
    pilot_id = data.get('pilot_id')

    if not beneficiary_id or not pilot_id:
        return JsonResponse({'error': 'beneficiary_id and pilot_id are required'}, status=400)

    try:
        beneficiary = User.objects.get(id=beneficiary_id, role='beneficiary')
    except User.DoesNotExist:
        return JsonResponse({'error': 'Beneficiary not found'}, status=404)

    try:
        pilot = Pilot.objects.get(id=pilot_id)
    except Pilot.DoesNotExist:
        return JsonResponse({'error': 'Pilot not found'}, status=404)

    # Check if already issued
    if Certificate.objects.filter(beneficiary=beneficiary, pilot=pilot).exists():
        return JsonResponse({'error': 'Certificate already issued for this beneficiary and pilot'}, status=409)

    import uuid
    cert_number = f'HL-{timezone.now().strftime("%Y%m%d")}-{uuid.uuid4().hex[:8].upper()}'

    cert = Certificate.objects.create(
        beneficiary=beneficiary,
        pilot=pilot,
        issued_by=user,
        certificate_number=cert_number,
        title=data.get('title', f'Certificate of Completion — {pilot.title}'),
        description=data.get('description', f'This certifies that {beneficiary.name} has successfully completed the program "{pilot.title}".'),
    )

    # Notify beneficiary
    Notification.objects.create(
        user=beneficiary,
        title='Certificate Issued! 🎓',
        message=f'You have been awarded a certificate for "{pilot.title}". Download it from your dashboard.',
        icon='fa-certificate',
    )

    log_audit(user, 'Certificate issued', f'{cert.certificate_number} to {beneficiary.name}', request)

    return JsonResponse({
        'success': True,
        'certificate': {
            'id': cert.id,
            'certificate_number': cert.certificate_number,
            'title': cert.title,
        }
    })


@csrf_exempt
def api_certificate_pdf(request, cert_id):
    """GET: Generate and download a certificate as PDF."""
    user = get_current_user(request)
    if not user:
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    cert = get_object_or_404(Certificate, id=cert_id)

    # Only the beneficiary who owns it or an admin can download
    if user.role != 'admin' and cert.beneficiary != user:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    from django.http import HttpResponse
    import html as html_module

    # Generate a premium HTML certificate with HumanLoop branding
    bene_name = html_module.escape(cert.beneficiary.name)
    desc = html_module.escape(cert.description)
    pilot_title = html_module.escape(cert.pilot.title) if cert.pilot else 'Program'
    issuer = html_module.escape(cert.issued_by.name if cert.issued_by else 'HumanLoop Admin')
    date_str = cert.issued_at.strftime('%B %d, %Y')
    cert_no = cert.certificate_number

    cert_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Certificate - {bene_name}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700;800&family=Inter:wght@300;400;500;600&family=Great+Vibes&display=swap" rel="stylesheet">
    <style>
        @page {{ size: A4 landscape; margin: 0; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            width: 297mm; height: 210mm;
            font-family: 'Inter', 'Segoe UI', sans-serif;
            background: #f0f0f0;
            display: flex; align-items: center; justify-content: center;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}
        .cert {{
            width: 283mm; height: 196mm;
            position: relative;
            background: #ffffff;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
        }}
        /* Outer gold border */
        .cert::before {{
            content: '';
            position: absolute;
            inset: 0;
            border: 5px solid #c5a455;
            pointer-events: none;
            z-index: 5;
        }}
        /* Inner blue border */
        .cert::after {{
            content: '';
            position: absolute;
            inset: 10px;
            border: 1.5px solid #1A56DB;
            pointer-events: none;
            z-index: 5;
        }}
        /* Third inner gold fine line */
        .inner-border {{
            position: absolute;
            inset: 15px;
            border: 0.5px solid #d4b96a;
            pointer-events: none;
            z-index: 5;
        }}
        /* Background pattern */
        .bg-pattern {{
            position: absolute;
            inset: 0;
            z-index: 0;
            opacity: 0.03;
            background-image:
                radial-gradient(circle at 20% 30%, #1A56DB 1px, transparent 1px),
                radial-gradient(circle at 80% 70%, #0D9488 1px, transparent 1px),
                radial-gradient(circle at 50% 50%, #c5a455 1px, transparent 1px);
            background-size: 40px 40px, 45px 45px, 50px 50px;
        }}
        /* Left accent bar */
        .accent-bar {{
            position: absolute;
            left: 0; top: 0; bottom: 0;
            width: 14px;
            background: linear-gradient(180deg, #1A56DB, #0D9488, #c5a455, #0D9488, #1A56DB);
            z-index: 6;
        }}
        /* Right accent bar */
        .accent-bar-right {{
            position: absolute;
            right: 0; top: 0; bottom: 0;
            width: 14px;
            background: linear-gradient(180deg, #c5a455, #0D9488, #1A56DB, #0D9488, #c5a455);
            z-index: 6;
        }}
        /* Corner ornaments */
        .corner {{
            position: absolute;
            width: 70px; height: 70px;
            z-index: 6;
        }}
        .corner svg {{ width: 100%; height: 100%; }}
        .corner.tl {{ top: 18px; left: 18px; }}
        .corner.tr {{ top: 18px; right: 18px; transform: scaleX(-1); }}
        .corner.bl {{ bottom: 18px; left: 18px; transform: scaleY(-1); }}
        .corner.br {{ bottom: 18px; right: 18px; transform: scale(-1,-1); }}
        /* Content */
        .content {{
            position: relative;
            z-index: 2;
            padding: 22px 50px 20px 50px;
            height: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: space-evenly;
        }}
        /* Header */
        .header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 4px;
        }}
        .logo-svg {{ width: 42px; height: 42px; flex-shrink: 0; }}
        .brand {{
            font-family: 'Inter', sans-serif;
            font-size: 24px;
            font-weight: 700;
            color: #1A56DB;
            letter-spacing: 1px;
        }}
        .brand span {{ color: #0D9488; }}
        .tagline {{
            font-size: 9px;
            color: #999;
            letter-spacing: 3px;
            text-transform: uppercase;
            margin-bottom: 6px;
        }}
        /* Title ribbon */
        .ribbon {{
            background: linear-gradient(135deg, #1A56DB, #0D9488);
            color: white;
            padding: 10px 60px;
            text-align: center;
            position: relative;
            margin: 4px 0 8px;
        }}
        .ribbon::before, .ribbon::after {{
            content: '';
            position: absolute;
            top: 0; bottom: 0;
            width: 30px;
        }}
        .ribbon::before {{
            left: -15px;
            background: linear-gradient(135deg, #1A56DB, #0D9488);
            clip-path: polygon(100% 0, 100% 100%, 0 50%);
        }}
        .ribbon::after {{
            right: -15px;
            background: linear-gradient(135deg, #1A56DB, #0D9488);
            clip-path: polygon(0 0, 0 100%, 100% 50%);
        }}
        .ribbon h1 {{
            font-family: 'Playfair Display', serif;
            font-size: 30px;
            font-weight: 700;
            letter-spacing: 8px;
            text-transform: uppercase;
            line-height: 1;
        }}
        .ribbon .sub {{
            font-size: 11px;
            letter-spacing: 6px;
            text-transform: uppercase;
            opacity: 0.85;
            margin-top: 2px;
        }}
        /* Divider */
        .divider {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            margin: 6px 0;
            width: 100%;
        }}
        .divider .line {{
            flex: 1;
            max-width: 200px;
            height: 1px;
            background: linear-gradient(90deg, transparent, #c5a455 30%, #c5a455 70%, transparent);
        }}
        .divider .diamond {{
            width: 8px; height: 8px;
            background: #c5a455;
            transform: rotate(45deg);
            flex-shrink: 0;
        }}
        /* Body */
        .body {{
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 2px;
            width: 100%;
        }}
        .presented {{
            font-size: 12px;
            color: #888;
            letter-spacing: 4px;
            text-transform: uppercase;
        }}
        .name {{
            font-family: 'Great Vibes', cursive;
            font-size: 50px;
            color: #1A56DB;
            line-height: 1.2;
        }}
        .name-underline {{
            width: 320px;
            height: 2px;
            background: linear-gradient(90deg, transparent, #c5a455 15%, #c5a455 85%, transparent);
            margin: 2px auto 8px;
        }}
        .description {{
            font-size: 13px;
            color: #555;
            line-height: 1.6;
            max-width: 580px;
            font-weight: 400;
        }}
        .program-name {{
            font-family: 'Playfair Display', serif;
            font-size: 22px;
            font-weight: 700;
            color: #0D9488;
            margin: 6px 0 2px;
            letter-spacing: 1px;
        }}
        /* Skills / Achievements badges */
        .skills {{
            display: flex;
            gap: 10px;
            justify-content: center;
            flex-wrap: wrap;
            margin: 8px 0 4px;
        }}
        .skill-badge {{
            background: linear-gradient(135deg, rgba(26,86,219,0.08), rgba(13,148,136,0.08));
            border: 1px solid rgba(26,86,219,0.15);
            color: #1A56DB;
            font-size: 10px;
            font-weight: 600;
            padding: 4px 14px;
            border-radius: 20px;
            letter-spacing: 0.5px;
        }}
        /* Seal */
        .seal {{
            width: 85px; height: 85px;
            flex-shrink: 0;
        }}
        .seal-outer {{
            width: 85px; height: 85px;
            border-radius: 50%;
            background: conic-gradient(
                #c5a455, #e8d48b, #c5a455, #e8d48b,
                #c5a455, #e8d48b, #c5a455, #e8d48b,
                #c5a455, #e8d48b, #c5a455, #e8d48b,
                #c5a455
            );
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 18px rgba(197,164,85,0.4);
        }}
        .seal-mid {{
            width: 72px; height: 72px;
            border-radius: 50%;
            background: linear-gradient(135deg, #c5a455, #dfc87a);
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .seal-inner {{
            width: 60px; height: 60px;
            border-radius: 50%;
            border: 1.5px solid rgba(255,255,255,0.5);
            background: linear-gradient(135deg, #d4b96a, #c5a455);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: #5a4210;
        }}
        .seal-inner svg {{ width: 20px; height: 20px; margin-bottom: 1px; }}
        .seal-inner .seal-text {{
            font-size: 7px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-family: 'Inter', sans-serif;
            font-weight: 700;
        }}
        .seal-inner .seal-sub {{
            font-size: 5px;
            letter-spacing: 1px;
            opacity: 0.7;
            font-family: 'Inter', sans-serif;
        }}
        /* Footer */
        .footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
            padding: 0 30px;
        }}
        .footer .col {{
            text-align: center;
            min-width: 180px;
        }}
        .footer .col .sign-line {{
            width: 180px;
            border-top: 1.5px solid #bbb;
            margin: 0 auto 5px;
        }}
        .footer .col .lbl {{
            font-size: 8px;
            text-transform: uppercase;
            letter-spacing: 2.5px;
            color: #aaa;
            font-weight: 600;
        }}
        .footer .col .val {{
            font-size: 12px;
            color: #333;
            margin-top: 2px;
            font-weight: 500;
        }}
        .footer-center {{
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
        }}
        .footer-center .org {{
            font-size: 8px;
            color: #bbb;
            letter-spacing: 2px;
            text-transform: uppercase;
        }}
        .cert-id {{
            position: absolute;
            bottom: 16px;
            left: 35px;
            font-size: 7.5px;
            color: #ccc;
            letter-spacing: 2px;
            font-family: 'Inter', sans-serif;
            z-index: 7;
        }}
        /* Quote at bottom */
        .quote {{
            font-style: italic;
            font-size: 10px;
            color: #aaa;
            text-align: center;
            margin-top: 6px;
            letter-spacing: 0.3px;
        }}
        @media print {{
            body {{ background: white; }}
            .cert {{ box-shadow: none; }}
        }}
    </style>
</head>
<body>
    <div class="cert">
        <div class="accent-bar"></div>
        <div class="accent-bar-right"></div>
        <div class="bg-pattern"></div>
        <div class="inner-border"></div>

        <!-- Corner ornaments -->
        <div class="corner tl"><svg viewBox="0 0 70 70"><path d="M6 6 Q6 35,35 35 Q6 35,6 64" stroke="#c5a455" stroke-width="1.8" fill="none"/><path d="M12 6 Q12 28,35 28" stroke="#c5a455" stroke-width="0.8" fill="none" opacity="0.5"/><path d="M6 12 Q28 12,28 35" stroke="#c5a455" stroke-width="0.8" fill="none" opacity="0.5"/><circle cx="6" cy="6" r="3" fill="#c5a455"/><circle cx="35" cy="35" r="1.5" fill="#c5a455" opacity="0.5"/></svg></div>
        <div class="corner tr"><svg viewBox="0 0 70 70"><path d="M6 6 Q6 35,35 35 Q6 35,6 64" stroke="#c5a455" stroke-width="1.8" fill="none"/><path d="M12 6 Q12 28,35 28" stroke="#c5a455" stroke-width="0.8" fill="none" opacity="0.5"/><path d="M6 12 Q28 12,28 35" stroke="#c5a455" stroke-width="0.8" fill="none" opacity="0.5"/><circle cx="6" cy="6" r="3" fill="#c5a455"/><circle cx="35" cy="35" r="1.5" fill="#c5a455" opacity="0.5"/></svg></div>
        <div class="corner bl"><svg viewBox="0 0 70 70"><path d="M6 6 Q6 35,35 35 Q6 35,6 64" stroke="#c5a455" stroke-width="1.8" fill="none"/><path d="M12 6 Q12 28,35 28" stroke="#c5a455" stroke-width="0.8" fill="none" opacity="0.5"/><path d="M6 12 Q28 12,28 35" stroke="#c5a455" stroke-width="0.8" fill="none" opacity="0.5"/><circle cx="6" cy="6" r="3" fill="#c5a455"/><circle cx="35" cy="35" r="1.5" fill="#c5a455" opacity="0.5"/></svg></div>
        <div class="corner br"><svg viewBox="0 0 70 70"><path d="M6 6 Q6 35,35 35 Q6 35,6 64" stroke="#c5a455" stroke-width="1.8" fill="none"/><path d="M12 6 Q12 28,35 28" stroke="#c5a455" stroke-width="0.8" fill="none" opacity="0.5"/><path d="M6 12 Q28 12,28 35" stroke="#c5a455" stroke-width="0.8" fill="none" opacity="0.5"/><circle cx="6" cy="6" r="3" fill="#c5a455"/><circle cx="35" cy="35" r="1.5" fill="#c5a455" opacity="0.5"/></svg></div>

        <div class="content">
            <!-- Logo -->
            <div class="header">
                <svg class="logo-svg" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect width="100" height="100" rx="18" fill="url(#lg)"/>
                    <path d="M25 22V78M25 50H52C62 50 72 55 72 64V68C72 74 67 78 62 78H44" stroke="#fff" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M52 22V50" stroke="#fff" stroke-width="8" stroke-linecap="round"/>
                    <path d="M72 40V27C72 22 67 18 62 18" stroke="#a5f3fc" stroke-width="8" stroke-linecap="round"/>
                    <circle cx="72" cy="40" r="4.5" fill="#a5f3fc"/>
                    <defs><linearGradient id="lg" x1="0" y1="0" x2="100" y2="100"><stop stop-color="#1A56DB"/><stop offset="1" stop-color="#0D9488"/></linearGradient></defs>
                </svg>
                <div class="brand">Human<span>Loop</span></div>
            </div>
            <div class="tagline">Empowering Communities Through Innovation</div>

            <!-- Title Ribbon -->
            <div class="ribbon">
                <h1>Certificate</h1>
                <div class="sub">of Completion</div>
            </div>

            <div class="divider">
                <div class="line"></div>
                <div class="diamond"></div>
                <div class="line"></div>
            </div>

            <!-- Body -->
            <div class="body">
                <div class="presented">This certificate is proudly presented to</div>
                <div class="name">{bene_name}</div>
                <div class="name-underline"></div>
                <div class="description">
                    {desc}
                </div>
                <div class="program-name">&#127942; {pilot_title}</div>

                <div class="skills">
                    <span class="skill-badge">&#10003; Program Completed</span>
                    <span class="skill-badge">&#10003; Skills Acquired</span>
                    <span class="skill-badge">&#10003; Assessment Passed</span>
                    <span class="skill-badge">&#10003; Community Impact</span>
                </div>
            </div>

            <div class="divider">
                <div class="line"></div>
                <div class="diamond"></div>
                <div class="line"></div>
            </div>

            <div class="quote">"The best way to predict the future is to create it." &mdash; HumanLoop Initiative</div>

            <!-- Footer -->
            <div class="footer">
                <div class="col">
                    <!-- Left signature - flowing cursive -->
                    <svg viewBox="0 0 180 55" style="width:150px;height:45px;display:block;margin:0 auto -2px;" fill="none">
                        <path d="M18 40 C18 40,16 35,18 28 C20 18,26 12,32 14 C38 16,36 26,30 30 C24 34,20 36,22 32 C24 28,34 18,44 16 C50 15,48 22,52 20 C56 18,54 14,60 15 C64 16,62 22,66 20 L70 18" stroke="#1a2744" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                        <path d="M70 18 C74 16,76 20,80 18 C86 15,82 12,88 14 C94 16,90 24,96 20 C100 17,98 14,104 16 C108 18,106 24,112 20 C116 17,118 22,124 18 C128 15,132 20,136 18 C140 16,142 22,148 20 C152 18,154 24,160 22" stroke="#1a2744" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
                        <path d="M60 30 C80 34,100 30,120 32" stroke="#1a2744" stroke-width="0.7" stroke-linecap="round" opacity="0.4"/>
                    </svg>
                    <div class="sign-line"></div>
                    <div class="lbl">Date of Issue</div>
                    <div class="val">{date_str}</div>
                </div>
                <div class="footer-center">
                    <div class="seal">
                        <div class="seal-outer">
                            <div class="seal-mid">
                                <div class="seal-inner">
                                    <svg viewBox="0 0 24 24" fill="#5a4210"><path d="M12 2L14.09 8.26L20.18 8.97L15.55 13.22L16.82 19.57L12 16.27L7.18 19.57L8.45 13.22L3.82 8.97L9.91 8.26L12 2Z"/></svg>
                                    <div class="seal-text">Verified</div>
                                    <div class="seal-sub">HumanLoop</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="org">HumanLoop Social Innovation Platform</div>
                </div>
                <div class="col">
                    <!-- Right signature - sharp strokes with loop -->
                    <svg viewBox="0 0 180 55" style="width:150px;height:45px;display:block;margin:0 auto -2px;" fill="none">
                        <path d="M20 38 C20 38,22 16,30 12 C36 9,40 14,38 22 C36 30,28 36,32 34 C36 32,44 14,52 12 C58 10,56 18,60 16 C64 14,62 10,68 12 C72 14,70 20,76 16 C80 13,78 10,84 12 C88 14,86 20,92 16 C96 13,98 16,104 14 C108 12,110 18,116 14 C120 11,124 16,128 14" stroke="#1a2744" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                        <path d="M128 14 C132 12,136 18,140 16 C144 14,146 20,150 18 C154 16,156 14,160 18" stroke="#1a2744" stroke-width="1.4" stroke-linecap="round"/>
                        <path d="M52 28 C60 26,68 28,76 26 C84 24,92 28,100 26" stroke="#1a2744" stroke-width="0.7" stroke-linecap="round" opacity="0.4"/>
                        <circle cx="164" cy="18" r="1" fill="#1a2744" opacity="0.6"/>
                    </svg>
                    <div class="sign-line"></div>
                    <div class="lbl">Authorized Signatory</div>
                    <div class="val">{issuer}</div>
                </div>
            </div>
        </div>

        <div class="cert-id">CERTIFICATE NO: {cert_no}</div>
    </div>
</body>
</html>"""

    # Return as downloadable HTML (can be printed to PDF from browser)
    response = HttpResponse(cert_html, content_type='text/html')
    response['Content-Disposition'] = f'inline; filename="certificate_{cert.certificate_number}.html"'
    return response


# ──────────────────────────────────────────────────────────
# Document Vault API Endpoints
# ──────────────────────────────────────────────────────────

@csrf_exempt
@login_required_json
def api_documents(request):
    """GET: List documents for the current user."""
    user = get_current_user(request)
    docs = Document.objects.filter(user=user)
    return JsonResponse({
        'documents': [{
            'id': d.id,
            'filename': d.filename,
            'file_size': d.file_size,
            'uploaded_at': d.uploaded_at.isoformat(),
        } for d in docs]
    })


@csrf_exempt
@login_required_json
def api_document_upload(request):
    """POST: Upload a document file."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user = get_current_user(request)
    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return JsonResponse({'error': 'No file provided'}, status=400)

    # Limit file size to 10MB
    if uploaded_file.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'File too large. Maximum size is 10 MB.'}, status=400)

    doc = Document.objects.create(
        user=user,
        filename=uploaded_file.name,
        file=uploaded_file,
        file_size=uploaded_file.size,
    )
    log_audit(user, 'Document uploaded', f'{uploaded_file.name}', request)
    return JsonResponse({
        'success': True,
        'document': {
            'id': doc.id,
            'filename': doc.filename,
            'file_size': doc.file_size,
        }
    })


@login_required_json
def api_document_download(request, doc_id):
    """GET: Download a document file."""
    user = get_current_user(request)
    doc = get_object_or_404(Document, id=doc_id, user=user)
    from django.http import FileResponse
    response = FileResponse(doc.file.open('rb'), content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{doc.filename}"'
    return response


@csrf_exempt
@login_required_json
def api_document_delete(request, doc_id):
    """POST: Delete a document."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user = get_current_user(request)
    doc = get_object_or_404(Document, id=doc_id, user=user)
    filename = doc.filename
    # Delete the actual file from storage
    if doc.file:
        doc.file.delete(save=False)
    doc.delete()
    log_audit(user, 'Document deleted', f'{filename}', request)
    return JsonResponse({'success': True, 'message': 'Document deleted'})


# ──────────────────────────────────────────────────────────
# Payment Gateway — Razorpay Integration
# ──────────────────────────────────────────────────────────

@csrf_exempt
@login_required_json
def api_payment_create_order(request):
    """POST: Create a Razorpay order for a pilot assignment payment."""
    import razorpay

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user = get_current_user(request)
    if user.role != 'innovator':
        return JsonResponse({'error': 'Only innovators can make payments'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    assignment_id = data.get('assignment_id')
    if not assignment_id:
        return JsonResponse({'error': 'assignment_id is required'}, status=400)

    try:
        assignment = PilotAssignment.objects.get(id=assignment_id, requested_by=user)
    except PilotAssignment.DoesNotExist:
        return JsonResponse({'error': 'Assignment not found'}, status=404)

    if assignment.status not in ('admin_approved', 'payment_pending'):
        return JsonResponse({'error': f'Payment not applicable — status is {assignment.status}'}, status=400)

    pilot = assignment.pilot
    budget = Decimal(str(pilot.budget))
    commission_pct = Decimal(str(settings.PLATFORM_COMMISSION_PERCENT))
    commission = (budget * commission_pct / 100).quantize(Decimal('0.01'))
    total = budget + commission

    # Check if there's already an unpaid payment with a valid order
    existing_payment = Payment.objects.filter(
        assignment=assignment, status='created'
    ).order_by('-created_at').first()

    if existing_payment and existing_payment.razorpay_order_id:
        # Reuse existing order
        return JsonResponse({
            'success': True,
            'order': {
                'id': existing_payment.razorpay_order_id,
                'amount': int(existing_payment.total_amount * 100),
                'currency': 'INR',
                'key': settings.RAZORPAY_KEY_ID,
            },
            'payment': {
                'id': existing_payment.id,
                'amount': float(existing_payment.amount),
                'commission': float(existing_payment.commission),
                'total': float(existing_payment.total_amount),
                'pilot_title': pilot.title,
                'ngo_name': assignment.requested_ngo.name,
            }
        })

    # Convert to paise (Razorpay expects amount in paise)
    amount_paise = int(total * 100)

    # Create Razorpay order
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    order_data = {
        'amount': amount_paise,
        'currency': 'INR',
        'receipt': f'pilot_{pilot.id}_assign_{assignment.id}',
        'notes': {
            'pilot_title': pilot.title,
            'innovator': user.name,
            'ngo': assignment.requested_ngo.name,
        }
    }

    try:
        razorpay_order = client.order.create(data=order_data)
    except Exception as e:
        return JsonResponse({'error': f'Razorpay order creation failed: {str(e)}'}, status=500)

    # Save payment record
    payment = Payment.objects.create(
        assignment=assignment,
        user=user,
        pilot=pilot,
        amount=budget,
        commission=commission,
        total_amount=total,
        razorpay_order_id=razorpay_order['id'],
    )

    # Update assignment status
    assignment.status = 'payment_pending'
    assignment.save()

    log_audit(user, 'Payment order created', f'{pilot.title} — ₹{total}', request)

    return JsonResponse({
        'success': True,
        'order': {
            'id': razorpay_order['id'],
            'amount': amount_paise,
            'currency': 'INR',
            'key': settings.RAZORPAY_KEY_ID,
        },
        'payment': {
            'id': payment.id,
            'amount': float(budget),
            'commission': float(commission),
            'total': float(total),
            'pilot_title': pilot.title,
            'ngo_name': assignment.requested_ngo.name,
        }
    })


@csrf_exempt
@login_required_json
def api_payment_verify(request):
    """POST: Verify Razorpay payment signature and activate the pilot."""
    import razorpay
    import hmac
    import hashlib

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user = get_current_user(request)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    razorpay_order_id = data.get('razorpay_order_id', '')
    razorpay_payment_id = data.get('razorpay_payment_id', '')
    razorpay_signature = data.get('razorpay_signature', '')

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        return JsonResponse({'error': 'Missing payment verification fields'}, status=400)

    try:
        payment = Payment.objects.get(razorpay_order_id=razorpay_order_id, user=user)
    except Payment.DoesNotExist:
        return JsonResponse({'error': 'Payment record not found'}, status=404)

    # Verify signature
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        payment.status = 'failed'
        payment.save()
        return JsonResponse({'error': 'Payment signature verification failed'}, status=400)

    # Payment verified — update records
    payment.razorpay_payment_id = razorpay_payment_id
    payment.razorpay_signature = razorpay_signature
    payment.status = 'paid'
    payment.paid_at = timezone.now()
    payment.save()

    # Update assignment status
    assignment = payment.assignment
    assignment.status = 'payment_done'
    assignment.save()

    # Activate the pilot and assign the NGO
    pilot = payment.pilot
    pilot.assigned_ngo = assignment.requested_ngo
    pilot.status = 'active'
    pilot.save()

    # Notify everyone
    Notification.objects.create(
        user=user,
        title='Payment Successful! 🎉',
        message=f'Payment of ₹{payment.total_amount} completed for "{pilot.title}". The pilot is now active!',
        icon='fa-circle-check',
    )
    Notification.objects.create(
        user=assignment.requested_ngo,
        title='Pilot Activated! 🚀',
        message=f'The pilot "{pilot.title}" is now active. You can start managing it.',
        icon='fa-rocket',
    )

    # Send confirmation email
    try:
        send_mail(
            subject=f'💳 Payment Confirmed — "{pilot.title}" is Now Active',
            message=(
                f'Dear {user.name},\n\n'
                f'Your payment of ₹{payment.total_amount} for "{pilot.title}" has been confirmed.\n\n'
                f'  Budget: ₹{payment.amount}\n'
                f'  Platform Fee (5%): ₹{payment.commission}\n'
                f'  Total Paid: ₹{payment.total_amount}\n'
                f'  Payment ID: {razorpay_payment_id}\n\n'
                f'The pilot is now active and {assignment.requested_ngo.name} has been officially assigned.\n\n'
                f'Best regards,\nHumanLoop Team'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        pass

    log_audit(user, 'Payment verified', f'{pilot.title} — ₹{payment.total_amount}', request)

    return JsonResponse({
        'success': True,
        'message': 'Payment verified and pilot activated!',
        'payment_id': razorpay_payment_id,
    })


@csrf_exempt
@login_required_json
def api_payment_simulate_test(request):
    """POST: Simulate a successful payment in TEST MODE only (bypasses Razorpay)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    # Only allow in test mode
    if not settings.RAZORPAY_KEY_ID.startswith('rzp_test_'):
        return JsonResponse({'error': 'Simulation only available in test mode'}, status=403)

    user = get_current_user(request)
    if user.role != 'innovator':
        return JsonResponse({'error': 'Only innovators can make payments'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    assignment_id = data.get('assignment_id')
    if not assignment_id:
        return JsonResponse({'error': 'assignment_id is required'}, status=400)

    try:
        assignment = PilotAssignment.objects.get(id=assignment_id, requested_by=user)
    except PilotAssignment.DoesNotExist:
        return JsonResponse({'error': 'Assignment not found'}, status=404)

    if assignment.status not in ('admin_approved', 'payment_pending'):
        return JsonResponse({'error': f'Payment not applicable — status is {assignment.status}'}, status=400)

    pilot = assignment.pilot
    budget = Decimal(str(pilot.budget))
    commission_pct = Decimal(str(settings.PLATFORM_COMMISSION_PERCENT))
    commission = (budget * commission_pct / 100).quantize(Decimal('0.01'))
    total = budget + commission

    # Create or get payment record
    payment, created = Payment.objects.get_or_create(
        assignment=assignment,
        user=user,
        pilot=pilot,
        defaults={
            'amount': budget,
            'commission': commission,
            'total_amount': total,
            'razorpay_order_id': f'test_order_{assignment.id}_{timezone.now().strftime("%Y%m%d%H%M%S")}',
        }
    )

    # Mark as paid
    payment.razorpay_payment_id = f'test_pay_{assignment.id}_{timezone.now().strftime("%Y%m%d%H%M%S")}'
    payment.status = 'paid'
    payment.paid_at = timezone.now()
    payment.save()

    # Update assignment
    assignment.status = 'payment_done'
    assignment.save()

    # Activate pilot
    pilot.assigned_ngo = assignment.requested_ngo
    pilot.status = 'active'
    pilot.save()

    # Notifications
    Notification.objects.create(
        user=user,
        title='Payment Successful! 🎉',
        message=f'[TEST] Payment of ₹{total} completed for "{pilot.title}". The pilot is now active!',
        icon='fa-circle-check',
    )
    Notification.objects.create(
        user=assignment.requested_ngo,
        title='Pilot Activated! 🚀',
        message=f'The pilot "{pilot.title}" is now active. You can start managing it.',
        icon='fa-rocket',
    )

    log_audit(user, 'Test payment simulated', f'{pilot.title} — ₹{total}', request)

    return JsonResponse({
        'success': True,
        'message': f'Test payment simulated! Pilot "{pilot.title}" is now active.',
        'total': float(total),
    })

@login_required_json
def api_payment_status(request, assignment_id):
    """GET: Check payment status for an assignment."""
    user = get_current_user(request)

    try:
        assignment = PilotAssignment.objects.get(id=assignment_id)
    except PilotAssignment.DoesNotExist:
        return JsonResponse({'error': 'Assignment not found'}, status=404)

    # Only innovator, admin, or assigned NGO can check
    if user.role not in ('admin',) and user != assignment.requested_by and user != assignment.requested_ngo:
        return JsonResponse({'error': 'Access denied'}, status=403)

    payment = Payment.objects.filter(assignment=assignment).order_by('-created_at').first()

    if not payment:
        return JsonResponse({
            'has_payment': False,
            'assignment_status': assignment.status,
        })

    return JsonResponse({
        'has_payment': True,
        'assignment_status': assignment.status,
        'payment': {
            'id': payment.id,
            'amount': float(payment.amount),
            'commission': float(payment.commission),
            'total_amount': float(payment.total_amount),
            'status': payment.status,
            'razorpay_order_id': payment.razorpay_order_id,
            'razorpay_payment_id': payment.razorpay_payment_id,
            'paid_at': str(payment.paid_at) if payment.paid_at else None,
        }
    })


# ──────────────────────────────────────────────────────────
# Payment Gateway — Stripe Integration
# ──────────────────────────────────────────────────────────

@csrf_exempt
@login_required_json
def api_stripe_create_session(request):
    """POST: Create a Stripe Checkout Session for a pilot assignment payment."""
    import stripe

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user = get_current_user(request)
    if user.role != 'innovator':
        return JsonResponse({'error': 'Only innovators can make payments'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    assignment_id = data.get('assignment_id')
    if not assignment_id:
        return JsonResponse({'error': 'assignment_id is required'}, status=400)

    try:
        assignment = PilotAssignment.objects.get(id=assignment_id, requested_by=user)
    except PilotAssignment.DoesNotExist:
        return JsonResponse({'error': 'Assignment not found'}, status=404)

    if assignment.status not in ('admin_approved', 'payment_pending'):
        return JsonResponse({'error': f'Payment not applicable — status is {assignment.status}'}, status=400)

    pilot = assignment.pilot
    budget = Decimal(str(pilot.budget))
    commission_pct = Decimal(str(settings.PLATFORM_COMMISSION_PERCENT))
    commission = (budget * commission_pct / 100).quantize(Decimal('0.01'))
    total = budget + commission

    # Amount in paise (Stripe uses smallest currency unit)
    amount_paise = int(total * 100)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        # Create Stripe Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'inr',
                    'product_data': {
                        'name': f'Pilot: {pilot.title}',
                        'description': f'NGO: {assignment.requested_ngo.name} | Budget: ₹{budget} + Commission: ₹{commission}',
                    },
                    'unit_amount': amount_paise,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=request.build_absolute_uri('/api/payments/stripe/success/') + '?session_id={CHECKOUT_SESSION_ID}&assignment_id=' + str(assignment.id),
            cancel_url=request.build_absolute_uri('/dashboard/'),
            customer_email=user.email,
            metadata={
                'assignment_id': str(assignment.id),
                'pilot_id': str(pilot.id),
                'innovator_id': str(user.id),
            },
        )
    except Exception as e:
        return JsonResponse({'error': f'Stripe session creation failed: {str(e)}'}, status=500)

    # Save payment record
    payment = Payment.objects.create(
        assignment=assignment,
        user=user,
        pilot=pilot,
        amount=budget,
        commission=commission,
        total_amount=total,
        payment_gateway='stripe',
        stripe_session_id=session.id,
    )

    # Update assignment status
    assignment.status = 'payment_pending'
    assignment.save()

    log_audit(user, 'Stripe session created', f'{pilot.title} — ₹{total}', request)

    return JsonResponse({
        'success': True,
        'checkout_url': session.url,
        'session_id': session.id,
    })


def api_stripe_success(request):
    """GET: Handle Stripe success redirect — verify and activate pilot."""
    import stripe

    # Must be logged in (redirect to login if not, since this is a browser redirect)
    user = get_current_user(request)
    if not user:
        return redirect('/login/')

    session_id = request.GET.get('session_id')
    assignment_id = request.GET.get('assignment_id')

    if not session_id or not assignment_id:
        return redirect('/dashboard/')

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        logger.error(f"Stripe session retrieve failed: {e}")
        return redirect('/dashboard/')

    if session.payment_status != 'paid':
        logger.warning(f"Stripe session {session_id} not paid: {session.payment_status}")
        return redirect('/dashboard/')

    try:
        payment = Payment.objects.get(stripe_session_id=session_id)
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for Stripe session: {session_id}")
        return redirect('/dashboard/')

    if payment.status == 'paid':
        # Already processed — just go to dashboard
        return redirect('/dashboard/')

    # Mark as paid
    payment.stripe_payment_intent = session.payment_intent or ''
    payment.status = 'paid'
    payment.paid_at = timezone.now()
    payment.save()

    # Update assignment & pilot
    assignment = payment.assignment
    assignment.status = 'payment_done'
    assignment.save()

    pilot = payment.pilot
    pilot.assigned_ngo = assignment.requested_ngo
    pilot.status = 'active'
    pilot.save()

    # Notifications
    Notification.objects.create(
        user=user,
        title='Payment Successful! 🎉',
        message=f'Stripe payment of ₹{payment.total_amount} completed for "{pilot.title}". The pilot is now active!',
        icon='fa-circle-check',
    )
    Notification.objects.create(
        user=assignment.requested_ngo,
        title='Pilot Activated! 🚀',
        message=f'The pilot "{pilot.title}" is now active. You can start managing it.',
        icon='fa-rocket',
    )

    log_audit(user, 'Stripe payment completed', f'{pilot.title} — ₹{payment.total_amount}', request)

    return redirect('/dashboard/')


@csrf_exempt
def api_health(request):
    """GET: Health check — diagnose DB and migration status."""
    import django
    checks = {
        'django_version': django.get_version(),
        'database': 'unknown',
        'users_table': False,
        'audit_logs_table': False,
        'user_count': 0,
    }
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks['database'] = 'connected'
    except Exception as e:
        checks['database'] = f'error: {str(e)}'
        return JsonResponse(checks, status=500)

    try:
        checks['user_count'] = User.objects.count()
        checks['users_table'] = True
    except Exception as e:
        checks['users_table'] = f'error: {str(e)}'

    try:
        AuditLog.objects.count()
        checks['audit_logs_table'] = True
    except Exception as e:
        checks['audit_logs_table'] = f'error: {str(e)}'

    return JsonResponse(checks)

