from django.urls import path
from analytics import views

urlpatterns = [
    # Analytics Endpoints
    path("category-spend/", views.get_spending_by_category, name="user-category-spend",),  
    path("weekly-total/", views.get_total_spent_this_week, name="user-weekly-total",),

    # Reports
    path("report/select-receipts/pdf/<str:receipt_ids>/", views.report_multireceipt_pdf, name="report-multireceipt-pdf"),
    path("report/select-receipts/csv/<str:receipt_ids>/", views.report_multireceipt_csv, name="report-multireceipt-csv"),
]