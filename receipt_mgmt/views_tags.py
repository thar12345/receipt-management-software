import logging
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from receipt_mgmt.models import Receipt, Tag
from receipt_mgmt.serializers import TagSerializer, ReceiptSerializer

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tag_listall(request):
    """
    Lists all tags belonging to the authenticated user.
    """
    user = request.user
    tags = Tag.objects.filter(user=user)
    serializer = TagSerializer(tags, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tag_add(request):
    """
    Adds a tag to the given receipt.
    If the tag does not exist, it is created.
    Request payload example:
    {
      "name": "Groceries",
      "color": "#FF0000"
    }
    """
    user = request.user
    
    receipt_id = request.data.get("receipt_id")
    if not receipt_id:
        return Response(
            {"error": "Missing 'receipt_id' field in request data."},
            status=status.HTTP_400_BAD_REQUEST
        )

    tag_name = request.data.get("name")
    if not tag_name:
        return Response(
            {"error": "Missing 'name' field in request data."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 1) Get the receipt by ID
    receipt = get_object_or_404(Receipt, pk=receipt_id, user=user)

    # 2) Get or create the Tag
    tag, created = Tag.objects.get_or_create(
        user=user,
        name=tag_name,
   )

    # 3) Add the tag to the receipt's M2M field
    receipt.tags.add(tag)
    receipt.save()

    # 4) Return updated receipt (or a success message)
    receipt_serializer = ReceiptSerializer(receipt)
    tag_serializer = TagSerializer(tag)
    return Response(
        {
            "message": "Tag added successfully.",
            "receipt": receipt_serializer.data,
            "tag": tag_serializer.data
        },
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tag_remove(request):
    """
    Removes a specific tag (identified by tag_id) from a given receipt (receipt_id).
    If the tag has no receipts associated with it after removal, the tag is automatically deleted.
    """

    receipt_id = request.data.get("receipt_id")
    if not receipt_id:
        return Response(
            {"error": "Missing 'receipt_id' field in request data."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    tag_id = request.data.get("tag_id")
    if not tag_id:
        return Response(
            {"error": "Missing 'tag_id' field in request data."},
            status=status.HTTP_400_BAD_REQUEST
        )


    user = request.user
    receipt = get_object_or_404(Receipt, pk=receipt_id, user=user)

    # 1) Get the tag by ID
    tag = get_object_or_404(Tag, pk=tag_id, user=user)
    
    # 2) Check if the tag is already associated with the receipt
    if tag not in receipt.tags.all():
        return Response(
            {"error": f"Tag '{tag.name}' is not associated with this receipt."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 3) Remove the association
    receipt.tags.remove(tag)

    # 4) Check if tag has any remaining receipts
    if tag.receipts.count() == 0:
        # Tag has no receipts left, delete it
        tag_name = tag.name
        tag.delete()
        
        # Log the automatic deletion
        logger.info(f"User {user} automatically deleted orphaned tag '{tag_name}' (ID: {tag_id}) after removing from receipt.")
        
        return Response(
            {
                "message": f"Tag '{tag_name}' removed from receipt and deleted (no remaining receipts).",
                "receipt": ReceiptSerializer(receipt).data,
                "tag_deleted": True
            },
            status=status.HTTP_200_OK
        )
    else:
        # Tag still has other receipts, keep it
        return Response(
            {
                "message": f"Tag '{tag.name}' removed successfully from receipt.",
                "receipt": ReceiptSerializer(receipt).data,
                "tag": TagSerializer(tag).data,
                "tag_deleted": False
            },
            status=status.HTTP_200_OK
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def tag_delete(request, tag_id):
    """
    Deletes the specified tag entirely from the DB.
    All receipts that had this tag will also lose association.
    """
    user = request.user
    tag = get_object_or_404(Tag, pk=tag_id, user=user)

    tag_name = tag.name

    # Retrieve all receipts associated with the tag before deletion
    receipts = tag.receipts.all()

    # Serialize the receipts using ReceiptSerializer
    receipt_serializer = ReceiptSerializer(receipts, many=True)
    
    # Now delete the tag
    tag.delete()

    # Log the deletion action
    logger.info(f"User {user} deleted tag '{tag_name}' (ID: {tag_id}).")

    return Response(
        {
            "message": f"Tag '{tag_name}' has been deleted.",
            "updated_receipts": receipt_serializer.data  # Add the array of receipts
        },
        status=status.HTTP_200_OK
    )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def tag_edit_name(request):
    """
    Edits the name of a tag.
    """
    user = request.user
    tag_id = request.data.get("tag_id")
    new_name = request.data.get("name")

    if not tag_id or not new_name:
        return Response(
            {"error": "Missing 'tag_id' or 'name' field in request data."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 1) Get the Tag and verify it is owned by this user
    tag = get_object_or_404(Tag, pk=tag_id, user=user)

    # 2) Check if another Tag (owned by user) has the same name
    if Tag.objects.filter(user=user, name=new_name).exclude(pk=tag.pk).exists():
        return Response(
            {"error": f"A tag named '{new_name}' already exists."},
            status=status.HTTP_409_CONFLICT
        )

    # 3) Update the tag's name
    tag.name = new_name
    tag.save()

    return Response(
        {"message": "Tag name updated successfully."},
        status=status.HTTP_200_OK
    )
