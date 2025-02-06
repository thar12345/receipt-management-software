from rest_framework import serializers
from django.utils import timezone
from receipt_mgmt.models import Tag, Receipt, Item


class ItemSerializer(serializers.ModelSerializer):
    """
    A simple ModelSerializer for the `Item` model.
    """
    item_category_display = serializers.SerializerMethodField()
    returnable_by_date = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = [ 
            'id',
            'description',
            'product_id',
            'quantity',
            'quantity_unit',
            'price',
            'total_price',
            'item_category',
            'item_category_display',
            'returnable_by_date',
        ]
    
    def get_item_category_display(self, obj):
        """Return the human-readable display name for the item category"""
        return obj.get_item_category_display()
    
    def get_returnable_by_date(self, obj):
        """Return the returnable by date, showing 'unlimited' for unlimited returns"""
        if obj.returnable_by_date:
            # Check if it's unlimited return (9999-12-31)
            if obj.returnable_by_date.year == 9999:
                return "unlimited"
            return obj.returnable_by_date.isoformat()
        return None


class ReceiptCreateSerializer(serializers.ModelSerializer):
    """
    Allow the creation of a Receipt with nested Items in a single request.
    Handles field validation, decimal rounding, and text formatting.
    """

    items = ItemSerializer(many=True)

    class Meta:
        model = Receipt
        fields = [
            'company',
            'company_phone',
            'address',
            'country_region',
            'date',
            'time',
            'sub_total',
            'tax',
            'tax_rate',
            'total',
            'tip',
            'receipt_type',
            'item_count',
            'items',
            'raw_email',
            'raw_images',
            'receipt_currency_symbol',
            'receipt_currency_code',
        ]

    def create(self, validated_data):
        # Pop items from the data
        items_data = validated_data.pop('items', [])
        
        # Ensure receipt_type is set to Other if not provided
        if 'receipt_type' not in validated_data or validated_data['receipt_type'] is None:
            validated_data['receipt_type'] = Receipt.ReceiptType.OTHER
        
        # Create the receipt
        receipt = Receipt.objects.create(**validated_data)

        # Create items
        for item_data in items_data:
            Item.objects.create(receipt=receipt, **item_data)

        return receipt
    
class TagSummarySerializer(serializers.ModelSerializer):
    """Minimal representation of a tag (just id + name)."""
    class Meta:
        model  = Tag
        fields = ("id", "name")

class ReceiptSerializer(serializers.ModelSerializer):
    tags  = TagSummarySerializer(many=True, read_only=True)
    items = ItemSerializer(many=True, read_only=True)
    receipt_type_display = serializers.CharField(source='get_receipt_type_display', read_only=True)

    class Meta:
        model = Receipt
        fields = [
            "id",
            "company",
            "company_phone",
            "address",
            "country_region",
            "date",
            "time",
            "sub_total",
            "tax",
            "tax_rate",
            "total",
            "tip",
            "receipt_type",
            "receipt_type_display",
            "receipt_currency_symbol",
            "receipt_currency_code",
            "item_count",
            "items",
            "raw_email",
            'raw_images',
            "tags",
            "manual_entry",
            "created_at",
        ]


class TagSerializer(serializers.ModelSerializer):
    receipts = serializers.PrimaryKeyRelatedField(queryset=Receipt.objects.all(), many=True)
    class Meta:
        model = Tag
        fields = ["id", "name", "receipts"]
        # 'user' is implicitly handled in the view (we set it to request.user), 
        # so we don't expose it directly unless we want to.

    def create(self, validated_data):
        # Assign the current user as the tag's owner
        # if we want to handle it inside the serializer:
        request = self.context['request']
        validated_data['user'] = request.user
        return super().create(validated_data)


class ReceiptListSerializer(serializers.ModelSerializer):
    receipt_type_display = serializers.CharField(source='get_receipt_type_display', read_only=True)
    
    class Meta:
        model  = Receipt
        fields = [
            "id",
            "company",
            "total",
            "date",
            "receipt_type",
            "receipt_type_display",
            "receipt_currency_symbol",
            "created_at",
            "address",
        ]
        