from django.contrib import admin
from .models import Receipt, Item, Tag
from django.utils.html import format_html


def get_return_status_html(obj):
    """Utility function to generate return status HTML for admin display."""
    if not obj.returnable_by_date:
        return format_html('<span style="color: gray;">Unknown</span>')
    
    from datetime import date
    today = date.today()
    
    if obj.returnable_by_date == date(9999, 12, 31):
        return format_html('<span style="color: green; font-weight: bold;">Unlimited</span>')
    elif obj.returnable_by_date >= today:
        days_left = (obj.returnable_by_date - today).days
        return format_html('<span style="color: green;">Returnable ({} days left)</span>', days_left)
    else:
        days_past = (today - obj.returnable_by_date).days
        return format_html('<span style="color: red;">Expired ({} days ago)</span>', days_past)


class ItemInline(admin.TabularInline):
    model = Item
    extra = 0
    fields = ('description', 'quantity', 'quantity_unit', 'price', 'total_price', 'item_category', 'returnable_by_date', 'return_status')
    readonly_fields = ('total_price', 'return_status')
    
    def return_status(self, obj):
        return get_return_status_html(obj)
    
    return_status.short_description = 'Return Status'

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('description', 'receipt', 'quantity', 'total_price', 'item_category', 'returnable_by_date', 'return_status')
    list_filter = ('item_category', 'returnable_by_date', 'receipt__company', 'receipt__user')
    search_fields = ('description', 'receipt__company', 'receipt__user__username')
    date_hierarchy = 'receipt__date'
    
    def return_status(self, obj):
        return get_return_status_html(obj)
    
    return_status.short_description = 'Return Status'
    return_status.admin_order_field = 'returnable_by_date'

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('company', 'user', 'date', 'total', 'receipt_type', 'item_count', 'created_at', 'display_tags')
    list_filter = ('receipt_type', 'date', 'created_at', 'manual_entry', 'user')
    search_fields = ('company', 'user__username', 'user__email')
    date_hierarchy = 'date'
    readonly_fields = ('created_at',)
    inlines = [ItemInline]
    filter_horizontal = ('tags',)
    
    def display_tags(self, obj):
        return ", ".join([tag.name for tag in obj.tags.all()])
    display_tags.short_description = 'Tags'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'company', 'address', 'date', 'time')
        }),
        ('Financial Details', {
            'fields': ('sub_total', 'tax', 'total', 'tip', 'receipt_currency_symbol', 'receipt_currency_code')
        }),
        ('Metadata', {
            'fields': ('receipt_type', 'manual_entry', 'created_at', 'tags')
        }),
        ('Raw Data', {
            'classes': ('collapse',),
            'fields': ('raw_email', 'raw_images')
        }),
    )

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'receipt_count')
    list_filter = ('user',)
    search_fields = ('name', 'user__username')
    
    def receipt_count(self, obj):
        return obj.receipts.count()
    receipt_count.short_description = 'Number of Receipts'
