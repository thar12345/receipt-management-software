receipt_schema = {
    "type": "json_schema",
    "json_schema": {
        "name": "receipt_schema",
        "schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string"},
                "address": {"type": "string"},
                "date": {"type": "string"},
                "time": {"type": "string"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "product_id": {"type": "string"},
                            "quantity": {"type": "number"},
                            "quantity_unit": {"type": "string"},
                            "price": {"type": "number"},
                            "total_price": {"type": "number"}
                        },
                        "required": [
                            "description",
                            "total_price"
                        ]
                    }
                },
                "sub_total": {"type": "number"},
                "tax": {"type": "number"},
                "total": {"type": "number"},
                "tip": {"type": "number"},
                "receipt_type": {
                    "description": "The type of receipt as integer: 1=Groceries, 2=Apparel, 3=Dining Out, 4=Electronics, 5=Supplies, 6=Healthcare, 7=Home, 8=Utilities, 9=Transportation, 10=Insurance, 11=Personal Care, 12=Subscriptions, 13=Entertainment, 14=Education, 15=Pets, 16=Travel, 17=Other",
                    "type": "integer",
                    "enum": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
                },
                "receipt_currency_symbol": {"description":"The character symbol for the currency, such as $ or €",
                                            "type": "string"},
                "receipt_currency_code": {"type": "string"},
                "item_count": {"type": "number"}
            },
            "required": [
                "company",
                "date",
                "time",
                "items",
                "sub_total",
                "tax",
                "total",
                "receipt_type",
                "receipt_currency_symbol",
                "receipt_currency_code",
                "item_count"
            ]
        }
    }
}
