from rest_framework.response import Response
from rest_framework import status
import json
import logging
from datetime import datetime, date
from receipt_mgmt.serializers import ReceiptCreateSerializer, ReceiptSerializer
import openai
from receipt_mgmt.services.receipt_schema import receipt_schema
from django.contrib.auth import get_user_model
import base64
from receipt_mgmt.models import Receipt
from receipt_mgmt.utils.azure_utils import upload_receipt_image
from receipt_mgmt.signals import receipt_uploaded
from receipt_mgmt.services.system_messages import system_message_image, system_message_email
from receipt_mgmt.services.return_tracking_engine import process_return_receipt

logger = logging.getLogger(__name__)
 



def receipt_upload_image(request):
    """
    Receives one or more images, sends ALL of them to OpenAI as a single conversation,
    parses the resulting JSON for a single Receipt, uploads all images to Azure,
    and stores those image URLs in the 'raw_images' field.
    """
    # 1) Get all uploaded files
    files = request.FILES.getlist('receipt_images')
    if not files:
        logger.error("400 error in parse-receipt-image: No 'receipt_images' file(s) found.")
        return Response(
            {"error": "No 'receipt_images' file(s) found in the request."},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = request.user
    if not user:
        logger.error("404 error in parse-receipt-image: A user was not found.")
        return Response(
            {"error": "404 error in parse-receipt-image: A user was not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    # 2) Build the messages array for OpenAI
    #    - The system message with instructions
    #    - Then, for each image, a user message containing the base64 data
    current_month_name = date.today().strftime("%B")
    current_month_number = date.today().month


    messages = [system_message_image(current_month_name, current_month_number)]

    # Append each image as a user message
    for file_obj in files:
        image_data = file_obj.read()
        base64_image = base64.b64encode(image_data).decode("utf-8")

        user_message = {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{file_obj.content_type};base64,{base64_image}",
                        "detail": "high"
                    }
                }
            ],
        }
        messages.append(user_message)

    # 3) Call OpenAI once with all images
    try:
        response = openai.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            response_format=receipt_schema,
            store=False,
            temperature=0.3
        )
    except Exception as e:
        logger.error("500 error in parse-receipt-image, OpenAI API error: %s", str(e))
        return Response(
            {"error": f"Error calling OpenAI's API: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # 4) Extract JSON from OpenAI's response
    try:
        raw_content = response.choices[0].message.content
        parsed_data = json.loads(raw_content)
    except Exception as e:
        logger.error("500 error in parse-receipt-html, error extracting JSON from OpenAI response: %s", str(e))
        return Response(
            {"error": f"Error extracting JSON from the OpenAI response: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # 5) Convert date/time strings to Python objects
    transaction_date_str = parsed_data.get("date")
    if transaction_date_str:
        try:
            date_obj = datetime.strptime(transaction_date_str, "%Y/%m/%d").date()
        except ValueError:
            date_obj = None  
    else:
        date_obj = None    

    # Time extraction
    transaction_time_str = parsed_data.get("time")
    if transaction_time_str:
        # Some receipts might have HH:mm:ss or HH:mm
        time_obj = None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                time_obj = datetime.strptime(transaction_time_str, fmt).time()
                break
            except ValueError:
                continue
        if not time_obj:
            time_obj = None  # error
    else:
        time_obj = None # error

    # Replace the date/time in the parsed_data with actual Python date/time objects
    parsed_data["date"] = date_obj
    parsed_data["time"] = time_obj

    # 8) Validate the data (without raw_images) and save the receipt
    serializer = ReceiptCreateSerializer(data=parsed_data)
    if not serializer.is_valid():
        logger.error(
            "400 error in parse-receipt-image, serializer error: %s",
            serializer.errors
        )
        return Response(
            {"error": f"Serializer error: {serializer.errors}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # If valid, create the new Receipt (no raw_images yet)
    new_receipt = serializer.save(user=user)

    # 7) Upload each image to Azure
    blob_names: list[str] = []
    for file_obj in files:
        file_obj.seek(0)
        try:
            blob_name = upload_receipt_image(
                image_data=file_obj.read(),
                content_type=file_obj.content_type,
                user_id=user.id,
            )
            blob_names.append(blob_name)
        except Exception as exc:
            logger.error("Azure upload failed: %s", exc)
            blob_names.append("upload_failed")          # sentinel

    # 10) Now that we have the Azure URLs, update the receipt's raw_images
    new_receipt.raw_images = blob_names
    new_receipt.save(update_fields=["raw_images"])

    # 11) Serialize the final version
    receipt_id = new_receipt.id

    #13) Signal receipt upload + send websocket notification
    receipt_uploaded.send(user=user, sender=Receipt, receipt_id=receipt_id)

    return Response(
        {
            "status": "success",
            "message": "Receipt(s) parsed and stored successfully.",
            "receipt_id": receipt_id,
        },
        status=status.HTTP_201_CREATED
    )
 

def receipt_upload_email(html_content, user):
    """
    Receives an HTML file from the webhook and calls OpenAI's ChatGPT to parse the receipt.
    Creates a receipt object, and adds to users data. 
    """
    logger.info("Starting receipt_upload_email")
    try:
        current_month_name = date.today().strftime("%B")
        current_month_number = date.today().month 
        response = openai.chat.completions.create(
            model="gpt-4o-mini",  
            messages=[
                system_message_email(current_month_name, current_month_number),
                {
                    "role": "user",
                    "content": html_content
                }
            ],
            response_format=receipt_schema,
            store=False,
            temperature=0.3
        )
    except Exception as e:
        logger.error("500 error in parse-receipt-html, OpenAI API error: %s", str(e))
        return Response(
            {"error": f"Error calling OpenAI's API: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    try:
        raw_content = response.choices[0].message.content
        parsed_data = json.loads(raw_content)
    except Exception as e:
        logger.error("500 error in parse-receipt-html, error extracting JSON from OpenAI response: %s", str(e))
        return Response(
            {"error": f"Error extracting JSON from the OpenAI response: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Convert date and time from strings to objects
    transaction_date_str = parsed_data.get("date")
    if transaction_date_str:
        try:
            date_obj = datetime.strptime(transaction_date_str, "%Y/%m/%d").date()
        except ValueError:
            date_obj = None  
    else:
        date_obj = None 

    # Time extraction
    transaction_time_str = parsed_data.get("time")
    if transaction_time_str:
        # Some receipts might have HH:mm:ss or HH:mm
        time_obj = None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                time_obj = datetime.strptime(transaction_time_str, fmt).time()
                break
            except ValueError:
                continue
        if not time_obj:
            time_obj = None  
    else:
        time_obj = None 

    parsed_data["date"] = date_obj
    parsed_data["time"] = time_obj
    parsed_data["raw_email"] = html_content

    # Validate & save
    serializer = ReceiptCreateSerializer(data=parsed_data)
    if serializer.is_valid():
        new_receipt = serializer.save(user=user)
        receipt_id = new_receipt.id

        #13) Signal receipt upload and send websocket notification
        receipt_uploaded.send(user=user, sender=Receipt, receipt_id=receipt_id)

        return Response(
            {"status": "success", "message": "Receipt was successfully parsed and stored in DB"},
            status=status.HTTP_201_CREATED
        )
    
    else:
        print("400 error in parse-receipt-html, serializer error: %s", serializer.errors)
        logger.error("400 error in parse-receipt-html, serializer error: %s", serializer.errors)
        return Response(f"Serializer error: {serializer.errors}", status=status.HTTP_400_BAD_REQUEST)


def receipt_upload_manual(request):
    """
    API endpoint to manually upload a receipt.
    """
    data = request.data.copy()
    
    # Handle return receipt logic
    is_return_receipt = data.get('is_return', False)
    if is_return_receipt:
        logger.info("Processing manual return receipt - checking if amounts need to be converted to negative")
        data = process_return_receipt(data)
        # Remove the is_return flag from data before serialization
        data.pop('is_return', None)
    
    serializer = ReceiptCreateSerializer(data=data)
    if not serializer.is_valid():
        logger.error("400 error in parse-receipt-manual, serializer error: %s", serializer.errors)
        return Response(
            {"error": f"Serializer error: {serializer.errors}"},
            status=status.HTTP_400_BAD_REQUEST
        )
    new_receipt = serializer.save(user=request.user)
    new_receipt.manual_entry = True
    new_receipt.save(update_fields=["manual_entry"])
    receipt_uploaded.send(user=request.user, sender=Receipt, receipt_id=new_receipt.id)
    return Response (
        {
            "status": "success",
            "message": "Receipt uploaded successfully.",
            "receipt": ReceiptSerializer(new_receipt).data
        },
        status=status.HTTP_201_CREATED
    )


