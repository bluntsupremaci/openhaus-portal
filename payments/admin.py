from django.contrib import admin

from payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "user",
        "plan",
        "amount",
        "currency",
        "status",
        "created_at",
        "paid_at",
    )
    list_filter = ("status", "currency", "created_at")
    search_fields = ("reference", "user__email")
    readonly_fields = (
        "id",
        "reference",
        "paystack_access_code",
        "raw_verify_response",
        "created_at",
        "updated_at",
        "paid_at",
    )
    raw_id_fields = ("user", "plan", "membership")
