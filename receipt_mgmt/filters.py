import django_filters as df
from django.utils import timezone
from .models import Receipt

class ReceiptFilter(df.FilterSet):
    """
    • date_period:   '7d' | '30d' | '3m'
    • receipt_type:  comma list – Groceries,Meals,... (strings) or 1,3,... (integers)
    • tags:          comma list of Tag IDs
    """
    # explicit range params if you need finer control
    date_after  = df.DateFilter(field_name="created_at", lookup_expr="gte")
    date_before = df.DateFilter(field_name="created_at", lookup_expr="lte")

    # quick presets 7d/30d/3m
    date_period = df.CharFilter(method="filter_period")
    receipt_type = df.CharFilter(method="filter_category")
    category = df.CharFilter(method="filter_category")
    tags = df.CharFilter(method="filter_tags")
    company      = df.CharFilter(field_name="company", lookup_expr="iexact")

    def filter_period(self, qs, name, value):
        today = timezone.now().date()
        mapping = {"7d": 7, "30d": 30, "3m": 90}
        days = mapping.get(value)
        if days:
            return qs.filter(created_at__gte=today - timezone.timedelta(days=days))
        return qs

    def filter_category(self, qs, name, value):
        cats = [cat.strip() for cat in value.split(",")]
        
        # Handle both string names and integer IDs
        integer_values = []
        string_values = []
        
        for cat in cats:
            if cat.isdigit():
                # It's an integer ID
                integer_values.append(int(cat))
            else:
                # It's a string name, convert to integer
                integer_value = Receipt.get_receipt_type_from_string(cat)
                if integer_value:
                    integer_values.append(integer_value)
        
        if integer_values:
            return qs.filter(receipt_type__in=integer_values)
        return qs

    def filter_tags(self, qs, name, value):
        tag_ids = [int(pk) for pk in value.split(",") if pk.isdigit()]
        return qs.filter(tags__id__in=tag_ids).distinct()

    class Meta:
        model  = Receipt
        fields = []          # we wire everything in custom methods above
