from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from receipt_mgmt.models import Receipt
from django.db.models import Sum
from django.utils import timezone
import datetime as dt
from decimal import Decimal
import logging
from analytics.permissions import MonthlyReportLimit
from analytics.signals import report_downloaded
from django.http import JsonResponse
from django.http import HttpResponse
from io import StringIO
from io import BytesIO
from django.template.loader import render_to_string
from xhtml2pdf import pisa
import csv

logger = logging.getLogger(__name__)

# 1. Function that calculates the total spend and per-category spend
#    for the authenticated user within an inclusive date range.
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_spending_by_category(request):
    """
    DRF view-helper to calculate total spend and per-category spend
    for the authenticated user within an inclusive date range.

    ── Query-string params ─────────────────────────────────────────────
      • start : YYYY-MM-DD   (required, inclusive)
      • end   : YYYY-MM-DD   (required, inclusive)

    ── Response ───────────────────────────────────────────────────────
      HTTP 200
      {
        "total_spent": 357.01,
        "spend_by_category": [
          {"category": "Restaurant",   "total_spent": 245.67},
          {"category": "Groceries",    "total_spent": 102.34},
          {"category": "Uncategorised","total_spent":  8.99}
        ]
      }
    """
    # 1. Extract & validate query parameters
    start_s = request.query_params.get("start")
    end_s   = request.query_params.get("end")

    if not (start_s and end_s):
        return Response(
            {"error": "`start` and `end` query params are required (YYYY-MM-DD)"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        start_date = dt.date.fromisoformat(start_s)
        end_date   = dt.date.fromisoformat(end_s)
    except ValueError as exc:
        logger.error("Date parsing failed in get_spending_by_category: start=%s end=%s error=%s", start_s, end_s, exc,)
        return Response(
            {"error": "Dates must be in ISO format: YYYY-MM-DD"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if start_date > end_date:
        return Response(
            {"error": "`start` date must be on or before `end` date"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 2. Query the database once for the receipt subset
    qset = Receipt.objects.filter(
        user=request.user,
        date__range=[start_date, end_date],
    )

    # Overall total for the range (Decimal → float for JSON)
    total_spent = float(qset.aggregate(Sum("total"))["total__sum"] or Decimal("0"))

    # Per-category aggregation
    rows = (
        qset.values("receipt_type")          # GROUP BY receipt_type
            .annotate(total_spent=Sum("total"))
            .order_by("-total_spent")
    )

    # 3. Serialise rows for JSON output
    per_category = [
        {
            "category": row["receipt_type"] or "Uncategorised",
            "total_spent": float(row["total_spent"] or 0),
        }
        for row in rows
    ]

    # 4. Return DRF Response (HTTP 200 default)
    return Response(
        {
            "total_spent": total_spent,
            "spend_by_category": per_category,
        }
    )

# 2. Function that calculates the total spend for the current week for the authenticated user. 
#    This function is used in the get_total_spent_this_week_view function to get the data for 
#    the API response.
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_total_spent_this_week(request):
    """
    DRF view-helper to compute the authenticated user’s spend from the Monday of the
    current ISO week up to (and including) today.

     ── Response ───────────────────────────────────────────────────────
    {
        "start_date": "2025-04-28",           // Monday of the current ISO week
        "end_date":   "2025-04-29",           // “today” in the project time-zone
        "total_spent_this_week": 123.45       // summed Receipt.total over that range
    }
    """

    today = timezone.localdate()                       # respects TIME_ZONE
    start_of_week = today - dt.timedelta(days=today.weekday())  # Monday == 0

    total = (
        Receipt.objects
        .filter(user=request.user, date__range=[start_of_week, today])
        .aggregate(total=Sum("total"))["total"] or Decimal("0")
    )

    return Response(
        {
            "start_date": start_of_week.isoformat(),
            "end_date": today.isoformat(),
            "total_spent_this_week": float(total),
        }
    )

@api_view(["GET"])
@permission_classes([IsAuthenticated, MonthlyReportLimit])
def report_multireceipt_pdf(request, receipt_ids: str):
    """Return a PDF summary of the given comma-separated receipt IDs."""
    try:
        id_list = [int(i) for i in receipt_ids.split(",") if i.isdigit()]
    except ValueError:
        return JsonResponse({"error": "Bad IDs"}, status=400)
    if not id_list:
        return JsonResponse({"error": "No IDs"}, status=400)

    receipts = (
        Receipt.objects
        .filter(user=request.user, id__in=id_list)
        .prefetch_related("items")
    )
    if not receipts:
        return JsonResponse({"error": "Not found"}, status=404)

    grand_sub = sum(r.sub_total or Decimal("0") for r in receipts)
    grand_tax = sum(r.tax       or Decimal("0") for r in receipts)
    grand_tot = sum(r.total     or Decimal("0") for r in receipts)

    html = render_to_string(
        "expense_report.html",
        {
            "receipts": receipts,
            "grand_subtotal": grand_sub,
            "grand_tax": grand_tax,
            "grand_total": grand_tot,
        }
    )

    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=pdf_buffer)
    if pisa_status.err:
        return JsonResponse({"error": "PDF generation failed"}, status=500)

    resp = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = "attachment; filename=expense_report.pdf"
    report_downloaded.send(
        sender=request.user.__class__,
        user=request.user,
    )
    return resp



@api_view(["GET"])
@permission_classes([IsAuthenticated, MonthlyReportLimit])
def report_multireceipt_csv(request, receipt_ids):
    """
    Generates a CSV file for multiple receipts (by comma-separated IDs).
    Example URL: /api/receipt/multi/download/csv/1,2,3/
    """
    # Parse and validate IDs
    try:
        receipt_ids_list = [int(i) for i in receipt_ids.split(",") if i.isdigit()]
    except ValueError:
        return response({"error": "Invalid receipt IDs format"}, status=400)

    # Fetch only receipts that belong to the current user
    receipts = Receipt.objects.filter( id__in=receipt_ids_list).prefetch_related('items')
    if not receipts.exists():
        return response({"error": "No receipts found for the given IDs"}, status=404)

    # Calculate grand totals
    grand_subtotal = sum(r.sub_total or Decimal('0.00') for r in receipts)
    grand_tax = sum(r.tax or Decimal('0.00') for r in receipts)
    grand_total = sum(r.total or Decimal('0.00') for r in receipts)

    # Create an in-memory buffer to hold CSV data
    output = StringIO()
    writer = csv.writer(output)

    # Write a header row
    writer.writerow([
        "Receipt ID", "Vendor", "Date", "Time", 
        "Item Description", "Quantity", "Price (each)", "Total (Item)", 
        "Receipt Subtotal", "Receipt Tax", "Receipt Total"
    ])

    # Write each row for every item in each receipt
    for receipt in receipts:
        for item in receipt.items.all():
            writer.writerow([
                receipt.id,
                receipt.company,
                receipt.date,
                receipt.time,
                item.description,
                item.quantity,
                # Some receipts may not have item.price; show it or "--"
                item.price if item.price is not None else "--",
                item.total_price,
                receipt.sub_total or 0,
                receipt.tax,
                receipt.total,
            ])

    # Optionally, write a blank row, then the grand totals
    writer.writerow([])
    writer.writerow(["", "", "", "", "", "", "", "", "Grand Subtotal", "Grand Tax", "Grand Total"])
    writer.writerow(["", "", "", "", "", "", "", "", grand_subtotal, grand_tax, grand_total])

    # Build a response with the CSV data
    response = HttpResponse(
        content_type='text/csv',
    )
    response['Content-Disposition'] = 'attachment; filename="expense_report.csv"'
    response.write(output.getvalue())

    report_downloaded.send(
        sender=request.user.__class__,
        user=request.user,
    )

    return response 
 