from django.contrib import admin
from .models import (
    User, Pilot, Expense, Feedback, Notification, AuditLog,
    TeamMember, BeneficiaryEnrollment, PilotAssignment, Certificate, Document, Payment,
)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'is_active']
    search_fields = ['name', 'email']


@admin.register(Pilot)
class PilotAdmin(admin.ModelAdmin):
    list_display = ['title', 'activity_type', 'status', 'budget', 'created_by', 'created_at']
    list_filter = ['status', 'activity_type']
    search_fields = ['title', 'location']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['description', 'amount', 'category', 'pilot', 'date']
    list_filter = ['category']


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['user', 'rating', 'pilot', 'created_at']
    list_filter = ['rating']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'is_read', 'created_at']
    list_filter = ['is_read']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'user', 'ip_address', 'created_at']
    search_fields = ['action']


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'pilot', 'team_role', 'joined_at']
    list_filter = ['team_role']


@admin.register(BeneficiaryEnrollment)
class BeneficiaryEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'pilot', 'sessions_attended', 'enrolled_at']


@admin.register(PilotAssignment)
class PilotAssignmentAdmin(admin.ModelAdmin):
    list_display = ['pilot', 'requested_ngo', 'requested_by', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['pilot__title', 'requested_ngo__name']


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ['certificate_number', 'beneficiary', 'pilot', 'issued_at']
    search_fields = ['certificate_number', 'beneficiary__name']


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'user', 'file_size', 'uploaded_at']
    list_filter = ['user']
    search_fields = ['filename']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['razorpay_order_id', 'user', 'pilot', 'total_amount', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['razorpay_order_id', 'razorpay_payment_id', 'user__name', 'pilot__title']
    readonly_fields = ['razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature']
