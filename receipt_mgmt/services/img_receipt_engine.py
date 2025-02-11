"""
Azure Document Intelligence receipt parsing service.

This module provides functionality to extract structured receipt data from images
using Azure's Document Intelligence API.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Union
from decimal import Decimal, ROUND_HALF_UP

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError

logger = logging.getLogger(__name__)


def extract_receipt(
    image: Union[str, Path, bytes, BinaryIO],
    *,
    endpoint: str,
    key: str,
    poll_timeout: int = 60,
) -> Dict[str, Any]:
    """
    Parse a receipt image with Azure Document Intelligence and return
    a dictionary matching the shape expected by ReceiptCreateSerializer.

    Args:
        image: Image data as file path, bytes, or file-like object
        endpoint: Azure Document Intelligence endpoint URL
        key: Azure Document Intelligence API key
        poll_timeout: Maximum seconds to wait for Azure to finish analyzing

    Returns:
        Dictionary with receipt data matching ReceiptCreateSerializer fields

    Raises:
        ValueError: If no receipt document is detected in the image
        AzureError: If Azure API call fails
        Exception: For other processing errors
    """
    try:
        logger.info("Starting receipt extraction from image")
        
        # Load the image into bytes
        image_bytes = _read_as_bytes(image)
        logger.debug(f"Image loaded, size: {len(image_bytes)} bytes")

        # Call Azure Document Intelligence
        client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key),
        )
        
        logger.info("Calling Azure Document Intelligence API")
        poller = client.begin_analyze_document(
            model_id="prebuilt-receipt",
            body=image_bytes,
        )
        
        result: AnalyzeResult = poller.result(timeout=poll_timeout)
        logger.info("Azure Document Intelligence analysis completed")

        # Extract and transform the data
        receipt_data = _build_serializer_dict(result)
        logger.info("Receipt data extraction completed successfully")
        
        return receipt_data
        
    except AzureError as e:
        logger.error(f"Azure Document Intelligence API error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error during receipt extraction: {str(e)}")
        raise


def _read_as_bytes(src: Union[str, Path, bytes, BinaryIO]) -> bytes:
    """
    Coerce source into a bytes object.
    
    Args:
        src: Source data as file path, bytes, or file-like object
        
    Returns:
        Bytes representation of the source data
        
    Raises:
        IOError: If file cannot be read
        Exception: For other processing errors
    """
    try:
        if isinstance(src, (str, Path)):
            with open(src, "rb") as fh:
                return fh.read()
        if isinstance(src, bytes):
            return src
        # Assume file-like object
        return src.read()
    except Exception as e:
        logger.error(f"Error reading image data: {str(e)}")
        raise


def _safe_field(obj: dict, key: str, sub_key: str, default=None):
    """
    Safely extract a nested field from Azure result dictionary.
    
    Args:
        obj: Dictionary to extract from
        key: Primary key to look for
        sub_key: Secondary key to extract
        default: Default value if field not found
        
    Returns:
        Extracted value or default
    """
    field = obj.get(key)
    if field is None:
        return default
    return field.get(sub_key, default)


def _round_decimal(value: Optional[float]) -> Optional[Decimal]:
    """
    Round a float value to 2 decimal places and return as Decimal.
    
    Args:
        value: Float value to round
        
    Returns:
        Rounded Decimal value or None if input is None
    """
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _round_quantity(value: Optional[float]) -> Optional[Decimal]:
    """
    Round a quantity value to 2 decimal places and return as Decimal.
    
    Args:
        value: Float value to round
        
    Returns:
        Rounded Decimal value or None if input is None
    """
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _format_title_case(text: Optional[str]) -> str:
    """
    Format text to title case, handling None values.
    
    Args:
        text: Text to format
        
    Returns:
        Title case formatted text or empty string if None
    """
    if not text:
        return ""
    return text.title()


def _build_serializer_dict(
    result: AnalyzeResult,
) -> Dict[str, Any]:
    """
    Build a dictionary from Azure result matching ReceiptCreateSerializer fields.
    
    Args:
        result: Azure Document Intelligence analysis result
        
    Returns:
        Dictionary with receipt data
        
    Raises:
        ValueError: If no receipt document is detected
    """
    if not result.documents:
        raise ValueError("No receipt document detected in the image.")

    fields = result.documents[0].fields
    logger.debug(f"Processing {len(fields)} fields from Azure result")

    # Extract company - try MerchantName.valueString first, then MerchantName.content
    company = _safe_field(fields, "MerchantName", "valueString", "")
    if not company:
        company = _safe_field(fields, "MerchantName", "content", "")
    company = _format_title_case(company)  # Format to title case
    
    # Extract address from MerchantAddress.content
    address = _safe_field(fields, "MerchantAddress", "content", "")
    
    # Extract country code from CountryRegion.valueCountryRegion
    country_region = _safe_field(fields, "CountryRegion", "valueCountryRegion", "")
    
    # Extract phone number from MerchantPhoneNumber
    company_phone = _safe_field(fields, "MerchantPhoneNumber", "valuePhoneNumber", "")
    
    # Extract date and time in the format Document Intelligence returns them
    date_raw = _safe_field(fields, "TransactionDate", "valueDate")
    time_raw = _safe_field(fields, "TransactionTime", "valueTime")
    
    # Extract currency amounts and round to 2 decimal places
    sub_total = _round_decimal(_extract_currency_amount(fields, "Subtotal"))
    total = _round_decimal(_extract_currency_amount(fields, "Total"))
    tip = _round_decimal(_extract_currency_amount(fields, "Tip"))
    
    # Extract tax - try TotalTax first, then sum from TaxDetails
    tax = _round_decimal(_extract_tax_amount(fields))
    
    # Extract tax rate from first TaxDetails entry
    tax_rate = _round_decimal(_extract_tax_rate(fields))
    
    # Extract currency information from Total field
    currency_field = _safe_field(fields, "Total", "valueCurrency", {})
    currency_symbol = currency_field.get("currencySymbol", "")
    currency_code = currency_field.get("currencyCode", "")


    # Parse date and time - keep in original format from Document Intelligence
    date_val = _parse_date(date_raw)
    time_val = _parse_time(time_raw)

    # Extract line items with proper formatting
    items = _extract_items(fields)
    
    logger.info(f"Extracted {len(items)} items from receipt")

    # Build final dictionary with all required fields
    receipt_data = {
        "company": company,
        "company_phone": company_phone,
        "address": address,
        "country_region": country_region,
        "date": date_val,
        "time": time_val,
        "sub_total": sub_total,
        "tax": tax,
        "tax_rate": tax_rate,
        "total": total,
        "tip": tip,
        "item_count": len(items),
        "items": items,
        "receipt_currency_symbol": currency_symbol,
        "receipt_currency_code": currency_code,
    }
    
    logger.debug(f"Built receipt data with {len(receipt_data)} fields")
    return receipt_data


def _extract_currency_amount(parent: dict, key: str) -> Optional[float]:
    """
    Extract currency amount from Azure result field.
    
    Args:
        parent: Parent dictionary containing the field
        key: Key to extract currency amount from
        
    Returns:
        Currency amount as float or None if not found
    """
    currency_field = _safe_field(parent, key, "valueCurrency")
    if currency_field:
        return currency_field.get("amount")
    return None


def _extract_tax_amount(fields: dict) -> Optional[float]:
    """
    Extract tax amount - try TotalTax first, then sum from TaxDetails.
    
    Args:
        fields: Azure result fields dictionary
        
    Returns:
        Tax amount as float or None if not found
    """
    # Try TotalTax.valueCurrency.amount first
    total_tax = _extract_currency_amount(fields, "TotalTax")
    if total_tax is not None:
        return total_tax
    
    # If TotalTax not available, sum from TaxDetails.valueArray
    tax_details_field = fields.get("TaxDetails", {})
    tax_details_array = tax_details_field.get("valueArray", [])
    
    if not tax_details_array:
        return None
    
    total_tax_sum = 0.0
    for tax_detail_wrap in tax_details_array:
        tax_detail_obj = tax_detail_wrap.get("valueObject", {})
        tax_amount_field = tax_detail_obj.get("Amount", {})
        tax_currency = tax_amount_field.get("valueCurrency", {})
        tax_amount = tax_currency.get("amount")
        
        if tax_amount is not None:
            total_tax_sum += tax_amount
    
    return total_tax_sum if total_tax_sum > 0 else None


def _extract_tax_rate(fields: dict) -> Optional[float]:
    """
    Extract tax rate from first TaxDetails entry.
    
    Args:
        fields: Azure result fields dictionary
        
    Returns:
        Tax rate as float or None if not found
    """
    tax_details_field = fields.get("TaxDetails", {})
    tax_details_array = tax_details_field.get("valueArray", [])
    
    if not tax_details_array:
        return None
    
    # Get first tax detail entry
    first_tax_detail = tax_details_array[0].get("valueObject", {})
    tax_rate_field = first_tax_detail.get("Rate", {})
    
    # Try different possible field names for tax rate
    tax_rate = tax_rate_field.get("valueNumber")
    if tax_rate is None:
        tax_rate = tax_rate_field.get("valueString")
        if tax_rate is not None:
            try:
                tax_rate = float(tax_rate)
            except (ValueError, TypeError):
                tax_rate = None
    
    return tax_rate


def _parse_date(date_raw: Optional[str]) -> Optional[datetime.date]:
    """
    Parse date string from Azure result.
    
    Args:
        date_raw: Raw date string in YYYY-MM-DD format
        
    Returns:
        Parsed date object or None if parsing fails
    """
    if not date_raw:
        return None
        
    try:
        return datetime.strptime(date_raw, "%Y-%m-%d").date()
    except ValueError as e:
        logger.warning(f"Failed to parse date '{date_raw}': {str(e)}")
        return None


def _parse_time(time_raw: Optional[str]) -> Optional[datetime.time]:
    """
    Parse time string from Azure result.
    
    Args:
        time_raw: Raw time string in HH:MM:SS or HH:MM format
        
    Returns:
        Parsed time object or None if parsing fails
    """
    if not time_raw:
        return None
        
    # Try multiple time formats
    time_formats = ["%H:%M:%S", "%H:%M"]
    
    for fmt in time_formats:
        try:
            return datetime.strptime(time_raw, fmt).time()
        except ValueError:
            continue
    
    logger.warning(f"Failed to parse time '{time_raw}' with any known format")
    return None


def _extract_items(fields: dict) -> List[Dict[str, Any]]:
    """
    Extract line items from Azure result fields with proper formatting.
    
    Args:
        fields: Azure result fields dictionary
        
    Returns:
        List of item dictionaries with formatted data
    """
    items = []
    items_field = fields.get("Items", {})
    
    for item_wrap in items_field.get("valueArray", []):
        item_obj = item_wrap.get("valueObject", {})
        
        # Extract basic item fields
        description = _safe_field(item_obj, "Description", "valueString", "")
        description = _format_title_case(description)  # Format to title case
        
        # If description is empty, use the model's default value
        if not description:
            description = "Unknown"
        
        product_code = _safe_field(item_obj, "ProductCode", "valueString", "")
        quantity = _round_quantity(_safe_field(item_obj, "Quantity", "valueNumber", 1.0))
        
        # Extract quantity_unit with proper default handling
        quantity_unit = _safe_field(item_obj, "QuantityUnit", "valueString", "")
        # If Azure returns empty string, use the model's default value
        if not quantity_unit:
            quantity_unit = "Unit(s)"
        
        # Extract price and total price with rounding
        price = _round_decimal(_extract_currency_amount(item_obj, "Price"))
        total_price = _round_decimal(_extract_currency_amount(item_obj, "TotalPrice"))
        
        # If TotalPrice is null but Price is not null, set TotalPrice = Price
        if total_price is None and price is not None:
            total_price = price
        
        # If total_price is still None, use the model's default value of 0
        if total_price is None:
            total_price = Decimal('0.00')
        
        item_data = {
            "description": description,
            "product_id": product_code,
            "quantity": quantity,
            "quantity_unit": quantity_unit,
            "price": price,
            "total_price": total_price,
            # item_category will be set to Other by the serializer
        }
        
        items.append(item_data)
    
    return items



