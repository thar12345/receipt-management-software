from django.urls import path

from receipt_mgmt import views_tags, views_receipt
from receipt_mgmt.services.receipt_image import receipt_upload_image_azure

urlpatterns = [

    # Receipts Create Endpoints
    path("receipt/upload/image/", views_receipt.receipt_upload_image, name="receipt-upload-image"),
    path("receipt/upload/image-azure/", receipt_upload_image_azure, name="receipt-upload-image-azure"),
    path("receipt/upload/manual/", views_receipt.receipt_upload_manual, name="receipt-upload-manual"),

    # Receipts Retrieve Endpoints
    path("receipts/",             views_receipt.ReceiptListView.as_view()),
    path("receipts/by-vendor/",   views_receipt.ReceiptByVendorView.as_view()),
    path("receipts/<int:pk>/",    views_receipt.ReceiptDetailView.as_view()),
    path("receipts/search/", views_receipt.ReceiptSmartSearchView.as_view(), name="receipt-smart-search"),
    
    path("receipt/<int:receipt_id>/image/<int:idx>/", views_receipt.receipt_image_url, name="receipt-image-url"), 
 

    # Tag endpoints
    path('tag/listall/', views_tags.tag_listall, name='tag-listall'),
    path('tag/add/', views_tags.tag_add, name='tag-add'),
    path('tag/remove/', views_tags.tag_remove, name='tag-remove'),
    path('tag/delete/<int:tag_id>/', views_tags.tag_delete, name='tag-delete'),
    path('tag/edit-name/', views_tags.tag_edit_name, name='tag-edit-name'),
]

