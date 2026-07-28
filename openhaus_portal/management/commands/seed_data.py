from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from memberships.models import MembershipPlan


class Command(BaseCommand):
    help = "Seed initial data for OpenHaus"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== Seeding OpenHaus initial data ==="))

        plans = [
            {
                "name": "Student Basic",
                "slug": "student-basic",
                "description": "Basic plan for students",
                "price": 0.00,
                "duration_days": 30,
                "included_quota_gb": 10,
                "max_devices": 2,
                "speed_limit_mbps": 5,
            },
            {
                "name": "Student Premium",
                "slug": "student-premium",
                "description": "Premium plan for students",
                "price": 1500.00,
                "duration_days": 30,
                "included_quota_gb": 50,
                "max_devices": 5,
                "speed_limit_mbps": 0,
            },
            {
                "name": "Staff Plan",
                "slug": "staff",
                "description": "Staff membership with full access",
                "price": 0.00,
                "duration_days": 365,
                "included_quota_gb": 100,
                "max_devices": 8,
                "speed_limit_mbps": 0,
            },
        ]

        for data in plans:
            plan, created = MembershipPlan.objects.get_or_create(slug=data["slug"], defaults=data)
            status = "✅ Created" if created else "Already exists"
            self.stdout.write(self.style.SUCCESS(f"{status}: {plan.name}"))

        # Test superuser
        User = get_user_model()
        if not User.objects.filter(email="admin@bazeuniversity.edu.ng").exists():
            User.objects.create_superuser(
                email="admin@bazeuniversity.edu.ng",
                password="admin123",
                first_name="Admin",
                last_name="User",
                user_type="staff",
                is_email_verified=True,
            )
            self.stdout.write(
                self.style.SUCCESS("✅ Created superuser: admin@bazeuniversity.edu.ng")
            )
        else:
            self.stdout.write(self.style.WARNING("Superuser already exists."))

        self.stdout.write(self.style.SUCCESS("=== Seeding completed successfully! ==="))
