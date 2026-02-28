from django.db import models


ROLE_CHOICES = [
    ('innovator', 'Innovator'),
    ('ngo', 'NGO'),
    ('beneficiary', 'Beneficiary'),
    ('admin', 'Admin'),
]

LANGUAGE_CHOICES = [
    ('en', 'English'),
    ('hi', 'Hindi'),
    ('bn', 'Bengali'),
    ('te', 'Telugu'),
    ('mr', 'Marathi'),
    ('ta', 'Tamil'),
    ('gu', 'Gujarati'),
    ('kn', 'Kannada'),
    ('ml', 'Malayalam'),
    ('pa', 'Punjabi'),
    ('or', 'Odia'),
    ('as', 'Assamese'),
    ('ur', 'Urdu'),
]


class User(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='innovator')
    organization = models.CharField(max_length=200, blank=True, default='')
    mobile = models.CharField(max_length=20, blank=True, default='')
    dob = models.DateField(null=True, blank=True)
    verified = models.BooleanField(default=False)

    # Settings — Language
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='en')

    # Settings — Notifications
    notif_email = models.BooleanField(default=True)
    notif_pilot_updates = models.BooleanField(default=True)
    notif_team_activity = models.BooleanField(default=True)
    notif_weekly_digest = models.BooleanField(default=False)

    # Settings — Privacy
    profile_visibility = models.CharField(
        max_length=20,
        choices=[('public', 'Public'), ('team', 'Team Only'), ('private', 'Private')],
        default='team'
    )
    activity_status = models.BooleanField(default=True)
    usage_analytics = models.BooleanField(default=True)

    # Settings — Two-Factor Authentication
    two_fa_enabled = models.BooleanField(default=False)
    two_fa_secret = models.CharField(max_length=32, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f"{self.name} ({self.role})"


class Pilot(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_ngo', 'Pending NGO Acceptance'),
        ('pending_admin', 'Pending Admin Approval'),
        ('pending_payment', 'Pending Payment'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
    ]

    title = models.CharField(max_length=300, default='')
    activity_type = models.CharField(max_length=50)
    location = models.CharField(max_length=200)
    target_date = models.DateField()
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expected_members = models.IntegerField(default=0)
    target_beneficiaries = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # AI-generated plan
    ai_plan = models.TextField(blank=True, default='')
    ai_ngo_recommendations = models.JSONField(default=list, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_pilots')
    assigned_ngo = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_pilots')

    progress = models.IntegerField(default=0)  # 0-100
    tasks = models.JSONField(default=list, blank=True)  # [{name: str, done: bool}, ...]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pilots'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.status})"


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('transport', 'Transport'),
        ('materials', 'Materials'),
        ('food', 'Food & Refreshments'),
        ('venue', 'Venue'),
        ('marketing', 'Marketing'),
        ('other', 'Other'),
    ]

    pilot = models.ForeignKey(Pilot, on_delete=models.CASCADE, related_name='expenses')
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    date = models.DateField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        db_table = 'expenses'
        ordering = ['-date']

    def __str__(self):
        return f"₹{self.amount} — {self.description}"


class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')
    pilot = models.ForeignKey(Pilot, on_delete=models.SET_NULL, null=True, blank=True)
    rating = models.IntegerField(default=5)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'feedbacks'
        ordering = ['-created_at']

    def __str__(self):
        return f"Feedback by {self.user.name} — {self.rating}★"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    icon = models.CharField(max_length=50, default='fa-bell')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=200)
    details = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} by {self.user}"


class TeamMember(models.Model):
    ROLE_CHOICES = [
        ('lead', 'Team Lead'),
        ('data_analyst', 'Data Analyst'),
        ('budget_manager', 'Budget Manager'),
        ('community_organizer', 'Community Organizer'),
        ('field_coordinator', 'Field Coordinator'),
        ('member', 'Member'),
        ('volunteer', 'Volunteer'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_memberships')
    pilot = models.ForeignKey(Pilot, on_delete=models.CASCADE, related_name='team_members')
    team_role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'team_members'
        unique_together = ['user', 'pilot']

    def __str__(self):
        return f"{self.user.name} — {self.team_role}"


class BeneficiaryEnrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    pilot = models.ForeignKey(Pilot, on_delete=models.CASCADE, related_name='enrollments')
    sessions_attended = models.IntegerField(default=0)
    total_sessions = models.IntegerField(default=10)
    badges_earned = models.JSONField(default=list, blank=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'beneficiary_enrollments'
        unique_together = ['user', 'pilot']

    def __str__(self):
        return f"{self.user.name} enrolled in {self.pilot.title}"


class OrgMember(models.Model):
    """Simple org-scoped team member (for the Team Members page)."""
    name = models.CharField(max_length=150)
    email = models.EmailField()
    job_role = models.CharField(max_length=100, default='Member')
    organization = models.CharField(max_length=200, default='')  # matches User.organization
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='added_members')
    joined = models.DateField(auto_now_add=True)

    class Meta:
        db_table = 'org_members'
        unique_together = ['email', 'organization']

    def __str__(self):
        return f"{self.name} ({self.organization})"


class PilotAssignment(models.Model):
    """Tracks: Innovator → NGO acceptance → Admin approval → Payment."""
    STATUS_CHOICES = [
        ('pending_ngo', 'Pending NGO Acceptance'),
        ('ngo_accepted', 'NGO Accepted — Awaiting Admin'),
        ('ngo_rejected', 'NGO Rejected'),
        ('admin_approved', 'Admin Approved — Awaiting Payment'),
        ('admin_rejected', 'Admin Rejected'),
        ('payment_pending', 'Payment Pending'),
        ('payment_done', 'Payment Completed — Active'),
    ]

    pilot = models.ForeignKey(Pilot, on_delete=models.CASCADE, related_name='assignments')
    requested_ngo = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignment_requests')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_requests')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending_ngo')

    admin_reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_reviews'
    )
    admin_notes = models.TextField(blank=True, default='')
    admin_reviewed_at = models.DateTimeField(null=True, blank=True)

    ngo_notes = models.TextField(blank=True, default='')
    ngo_responded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pilot_assignments'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.pilot.title} → {self.requested_ngo.name} ({self.status})"


class Payment(models.Model):
    """Payment tracking for pilot assignments (Razorpay + Stripe)."""
    STATUS_CHOICES = [
        ('created', 'Order Created'),
        ('paid', 'Payment Successful'),
        ('failed', 'Payment Failed'),
    ]
    GATEWAY_CHOICES = [
        ('razorpay', 'Razorpay'),
        ('stripe', 'Stripe'),
    ]

    assignment = models.ForeignKey(PilotAssignment, on_delete=models.CASCADE, related_name='payments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    pilot = models.ForeignKey(Pilot, on_delete=models.CASCADE, related_name='payments')

    amount = models.DecimalField(max_digits=12, decimal_places=2)          # Full pilot budget
    commission = models.DecimalField(max_digits=12, decimal_places=2)      # 5% platform fee
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)    # amount + commission

    # Payment gateway identifier
    payment_gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES, default='razorpay')

    # Razorpay fields
    razorpay_order_id = models.CharField(max_length=100, blank=True, default='')
    razorpay_payment_id = models.CharField(max_length=100, blank=True, default='')
    razorpay_signature = models.CharField(max_length=256, blank=True, default='')

    # Stripe fields
    stripe_session_id = models.CharField(max_length=200, blank=True, default='')
    stripe_payment_intent = models.CharField(max_length=200, blank=True, default='')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment ({self.payment_gateway}) — ₹{self.total_amount} ({self.status})"


class Certificate(models.Model):
    """Certificate issued by admin to a beneficiary for completing a program."""
    beneficiary = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certificates')
    pilot = models.ForeignKey(Pilot, on_delete=models.CASCADE, related_name='certificates')
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='issued_certificates')
    certificate_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=300, default='Certificate of Completion')
    description = models.TextField(blank=True, default='')
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'certificates'
        unique_together = ['beneficiary', 'pilot']
        ordering = ['-issued_at']

    def __str__(self):
        return f"Certificate #{self.certificate_number} — {self.beneficiary.name}"


class Document(models.Model):
    """File uploaded by NGO/innovator to the Document Vault."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    filename = models.CharField(max_length=300)
    file = models.FileField(upload_to='documents/%Y/%m/')
    file_size = models.BigIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'documents'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.filename} by {self.user.name}"

