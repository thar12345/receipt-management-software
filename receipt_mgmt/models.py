from django.db import models
from django.contrib.auth import get_user_model


# Create your models here.
# Receipt Model
class Receipt(models.Model):
    
    # Receipt Type Choices - using integers for better performance
    class ReceiptType(models.IntegerChoices):
        GROCERIES = 1, 'Groceries'
        APPAREL = 2, 'Apparel'
        DINING_OUT = 3, 'Dining Out'
        ELECTRONICS = 4, 'Electronics'
        SUPPLIES = 5, 'Supplies'
        HEALTHCARE = 6, 'Healthcare'
        HOME = 7, 'Home'
        UTILITIES = 8, 'Utilities'
        TRANSPORTATION = 9, 'Transportation'
        INSURANCE = 10, 'Insurance'
        PERSONAL_CARE = 11, 'Personal Care'
        SUBSCRIPTIONS = 12, 'Subscriptions'
        ENTERTAINMENT = 13, 'Entertainment'
        EDUCATION = 14, 'Education'
        PETS = 15, 'Pets'
        TRAVEL = 16, 'Travel'
        OTHER = 17, 'Other'
    
    # Class-level constant for string-to-int mapping to avoid recreation on every call
    _STRING_TO_INT_MAPPING = {
        'Groceries': ReceiptType.GROCERIES,
        'Apparel': ReceiptType.APPAREL,
        'Dining Out': ReceiptType.DINING_OUT,
        'Electronics': ReceiptType.ELECTRONICS,
        'Supplies': ReceiptType.SUPPLIES,
        'Healthcare': ReceiptType.HEALTHCARE,
        'Home': ReceiptType.HOME,
        'Utilities': ReceiptType.UTILITIES,
        'Transportation': ReceiptType.TRANSPORTATION,
        'Insurance': ReceiptType.INSURANCE,
        'Personal Care': ReceiptType.PERSONAL_CARE,
        'Subscriptions': ReceiptType.SUBSCRIPTIONS,
        'Entertainment': ReceiptType.ENTERTAINMENT,
        'Education': ReceiptType.EDUCATION,
        'Pets': ReceiptType.PETS,
        'Travel': ReceiptType.TRAVEL,
        'Other': ReceiptType.OTHER,
    }

    user = models.ForeignKey(
        get_user_model(), 
        on_delete=models.CASCADE, 
        related_name="receipts"
    )
    
    company = models.CharField(max_length=255)
    company_phone = models.CharField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    date = models.DateField()
    time = models.TimeField(blank=True, null=True)
    sub_total = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tax = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tax_rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    tip = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    receipt_type = models.IntegerField(
        choices=ReceiptType.choices,
        default=ReceiptType.OTHER,
        help_text="Category of the receipt"
    )
    country_region = models.TextField(blank=True, null=True)

    receipt_currency_symbol = models.CharField(blank=True, max_length=5)
    receipt_currency_code = models.CharField(blank=True, max_length=5)
    item_count = models.PositiveIntegerField(default=0)
    raw_email = models.TextField(blank=True, null=True)
    raw_images = models.JSONField(
        blank=True,
        default=list,
        help_text="List of all uploaded image URLs for this receipt."
    )
    # Many-to-many to Tag
    tags = models.ManyToManyField(
        "Tag",
        blank=True,
        related_name="receipts"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the receipt record was created."
    )

    manual_entry = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.company} on {self.date}"

    @classmethod
    def get_receipt_type_from_string(cls, string_value):
        """Convert old string receipt types to new integer values"""
        return cls._STRING_TO_INT_MAPPING.get(string_value, cls.ReceiptType.OTHER)

    class Meta:
        indexes = [
            # Main list view (user's receipts by date)
            models.Index(fields=['user', '-created_at']),
            # Company grouping with dates (for by-vendor view)
            models.Index(fields=['user', 'company', '-created_at']),
            # Receipt type filtering with dates
            models.Index(fields=['user', 'receipt_type', '-created_at']),
        ]
        ordering = ['-created_at']



# Item Model
class Item(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name="items")
    description = models.TextField(default="Unknown")
    product_id = models.TextField(blank=True)
    quantity = models.DecimalField(blank=True, null=True, default=1, decimal_places=5, max_digits=10)
    quantity_unit = models.TextField(blank=True, null=True, default="Unit(s)")
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    item_category = models.IntegerField(
        choices=Receipt.ReceiptType.choices,
        default=Receipt.ReceiptType.OTHER,
        help_text="Category of the individual item"
    )
    returnable_by_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date by which this item can be returned, determined by AI analysis"
    )

    def __str__(self):
        return f"{self.description} (x{self.quantity}) => {self.total_price}"
    
    class Meta:
        indexes = [
            # Primary index for fetching items for a receipt in order
            models.Index(fields=['receipt', 'id']),
            # Index for filtering items by category
            models.Index(fields=['item_category']),
        ]
        ordering = ['id']  # Maintain consistent order when displaying items


class Tag(models.Model):
    """
    User-defined tag with a name and color.
    Each user has their own set of tags.
    """
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="tags"
    )
    name = models.CharField(max_length=50)
    class Meta:
        unique_together = ("user", "name")

    def __str__(self):
        return f"{self.name} (User: {self.user.username})"
