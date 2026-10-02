from django.urls import path

from payments import views

app_name = "payments"

urlpatterns = [
    path("plans/", views.plan_list, name="plan_list"),
    path("membership/", views.membership_hub, name="membership_hub"),
    path("checkout/<uuid:plan_id>/", views.checkout, name="checkout"),
    path("callback/", views.callback, name="callback"),
]
