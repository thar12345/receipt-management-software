# api/views.py
from django.db.models import Prefetch, Q
from rest_framework.generics import ListAPIView, RetrieveDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from receipt_mgmt.models import Receipt, Item, Tag
from receipt_mgmt.serializers import (
    ReceiptSerializer,
    ReceiptListSerializer,
)
from receipt_mgmt.filters import ReceiptFilter
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from receipt_mgmt.models import Receipt
from receipt_mgmt.utils.azure_utils import make_private_download_url
from rest_framework.decorators import api_view, permission_classes
from receipt_mgmt.services import receipt_parsing

# ──────────────────────────────────────────────────────────
# A)  /api/receipts/        (flat list, default desc by created_at)
# ──────────────────────────────────────────────────────────
class ReceiptListView(ListAPIView):
    serializer_class   = ReceiptListSerializer
    filterset_class    = ReceiptFilter
   # search_fields      = ["company", "items__description"]
    ordering_fields    = ["created_at", "total", "date"]
    ordering           = ["-created_at"]      # default
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Receipt.objects
            .filter(user=self.request.user)
            .select_related('user')  # Include user data in initial query
            .prefetch_related(
                Prefetch(
                    "items",
                    queryset=Item.objects.only(
                        "id", "description", "total_price"
                    ).order_by('id')
                )
            )
            .prefetch_related(
                Prefetch(
                    "tags",
                    queryset=Tag.objects.only("id", "name")
                )
            )
        )


# ──────────────────────────────────────────────────────────
# B)  /api/receipts/by-vendor/   (grouped folders)
# ──────────────────────────────────────────────────────────
class ReceiptByVendorView(ListAPIView):
    serializer_class   = ReceiptListSerializer
    filterset_class    = ReceiptFilter
    search_fields      = ["company"]
    permission_classes = [IsAuthenticated]
    pagination_class   = None           # still no outer pagination

    def get_queryset(self):
        return (
            Receipt.objects
            .filter(user=self.request.user)
            .select_related()
            .prefetch_related("tags")
        )

    def list(self, request, *args, **kwargs):
        qs = (
            self.filter_queryset(self.get_queryset())
            .order_by("-created_at")           # newest first
        )

        company_map: dict[str, dict] = {}

        for r in qs:
            bucket = company_map.setdefault(
                r.company,
                {"company": r.company, "receipts": []}
            )
            if len(bucket["receipts"]) < 20:   # preview cap
                bucket["receipts"].append(ReceiptListSerializer(r).data)

        return Response(list(company_map.values()))


# ──────────────────────────────────────────────────────────
# C)  /api/receipts/<pk>/   (single receipt detail)
# ──────────────────────────────────────────────────────────
class ReceiptDetailView(RetrieveDestroyAPIView):
    serializer_class   = ReceiptSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Receipt.objects
            .filter(user=self.request.user)
            .prefetch_related("items", "tags")
        )
    

class ReceiptSmartSearchView(ListAPIView):
    """
    Split-search endpoint.
    ───────────────────────────────────────────────────────
    • Company-name hits   → grouped into vendor buckets
    • Item-description hits → flat list
    • All other filters (date_period, tags, receipt_type, etc.)
      still work because we run ReceiptFilter first.
    """
    serializer_class   = ReceiptListSerializer
    filterset_class    = ReceiptFilter
    permission_classes = [IsAuthenticated]
    pagination_class   = None        # manual parceling
    ordering_fields    = ["created_at", "total", "date"]
    ordering           = ["-created_at"]      # default

    # --- helper to reuse queryset build ----
    def _base_qs(self):
        return (
            Receipt.objects
            .filter(user=self.request.user)
            .select_related()
            .prefetch_related("tags")
            .prefetch_related(
                Prefetch("items", Item.objects.only("id", "description"))
            )
        )

    def list(self, request, *args, **kwargs):
        term = request.GET.get("search", "").strip()
        if not term:
            return Response(
                {"detail": "Missing ?search=<term> parameter."},
                status=400,
            )

        # Non-search filters first
        qs_filtered = self.filter_queryset(self._base_qs())

        # Split by where the match occurs
        company_q = Q(company__icontains=term)
        item_q    = Q(items__description__icontains=term)

        qs_company = qs_filtered.filter(company_q).distinct()
        qs_items   = (
            qs_filtered.filter(item_q)
            .exclude(id__in=qs_company)   # avoid duplicates
            .distinct()
        )

        # Build vendor buckets (preview up to 20 each)
        buckets: dict[str, dict] = {}
        for r in qs_company:
            bucket = buckets.setdefault(
                r.company, {"company": r.company, "receipts": []}
            )
            if len(bucket["receipts"]) < 20:
                bucket["receipts"].append(ReceiptListSerializer(r).data)

        # Flat list for item matches
        item_matches = [
            ReceiptListSerializer(r).data
            for r in qs_items
        ]

        return Response({
            "companies":    list(buckets.values()),
            "item_matches": item_matches,
        })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def receipt_image_url(request, receipt_id: int, idx: int):
    """
    Return a 5-min SAS URL for the idx-th image of `receipt_id`.
    """

    # 1) Fetch the receipt that matches the ID **and** is owned by the
    #    authenticated user.  get_object_or_404 both retrieves the object
    #    and returns a 404 if it is missing or belongs to someone else,
    #    preventing unauthorized access to other users' data.
    receipt = get_object_or_404(Receipt, pk=receipt_id, user=request.user)

    try:
        # 2) Pull the requested blob name from the Receipt's `raw_images`
        #    list, which stores Azure blob names in order of upload.
        blob_name = receipt.raw_images[idx]
    except IndexError:
        #    If the index is out of bounds (e.g., user asked for image 5
        #    but only 3 exist), return a graceful "not found" response.
        return Response({"detail": "Image not found"}, status=404)

    # 3) Generate a short-lived (≈5 min) read-only SAS URL so the client
    #    can download the image directly from Azure Blob Storage without
    #    exposing the underlying blob or container to public access.
    url = make_private_download_url(blob_name)      # 5-minute link

    # 4) Send the signed URL back to the caller.
    return Response({"url": url})



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def receipt_upload_image(request):
    """
    API endpoint to upload receipt images for parsing.
    Accepts one or more images and returns the parsed receipt data.
    """
    return receipt_parsing.receipt_upload_image(request)



@api_view(["POST"])
@permission_classes([IsAuthenticated]) 
def receipt_upload_manual(request):
    """
    API endpoint to manually upload receipt data.
    Accepts JSON receipt data and returns the created receipt.
    """
    return receipt_parsing.receipt_upload_manual(request)

