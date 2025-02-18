"""
Additional tests for receipt views that aren't covered in existing test files.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date, time
from decimal import Decimal
from unittest.mock import patch, Mock

from receipt_mgmt.models import Receipt, Item, Tag

User = get_user_model()


class ReceiptImageUrlTestCase(TestCase):
    """Test cases for receipt_image_url endpoint."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.receipt = Receipt.objects.create(
            user=self.user,
            company='Test Store',
            date=date.today(),
            total=Decimal('10.00'),
            raw_images=['image1.jpg', 'image2.jpg', 'image3.jpg']
        )
    
    @patch('receipt_mgmt.views_receipt.make_private_download_url')
    def test_receipt_image_url_success(self, mock_make_url):
        """Test successful image URL generation."""
        mock_make_url.return_value = 'https://example.com/sas-url'
        
        url = reverse('receipt-image-url', kwargs={'receipt_id': self.receipt.id, 'idx': 0})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_make_url.assert_called_once_with('image1.jpg')
    
    def test_receipt_image_url_not_found_receipt(self):
        """Test image URL with non-existent receipt."""
        url = reverse('receipt-image-url', kwargs={'receipt_id': 99999, 'idx': 0})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_receipt_image_url_unauthorized_access(self):
        """Test that users can't access other users' receipt images."""
        other_user = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='testpass123'
        )
        
        other_receipt = Receipt.objects.create(
            user=other_user,
            company='Other Store',
            date=date.today(),
            total=Decimal('20.00'),
            raw_images=['other_image.jpg']
        )
        
        url = reverse('receipt-image-url', kwargs={'receipt_id': other_receipt.id, 'idx': 0})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_receipt_image_url_index_out_of_bounds(self):
        """Test image URL with index out of bounds."""
        url = reverse('receipt-image-url', kwargs={'receipt_id': self.receipt.id, 'idx': 5})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['detail'], 'Image not found')
    
    def test_receipt_image_url_negative_index(self):
        """Test image URL with negative index."""
        # The URL pattern doesn't allow negative indices, so this should fail at URL resolution
        with self.assertRaises(Exception):  # Could be NoReverseMatch or similar
            url = reverse('receipt-image-url', kwargs={'receipt_id': self.receipt.id, 'idx': -1})
    
    def test_receipt_image_url_unauthenticated(self):
        """Test that unauthenticated requests are rejected."""
        self.client.force_authenticate(user=None)
        
        url = reverse('receipt-image-url', kwargs={'receipt_id': self.receipt.id, 'idx': 0})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ReceiptViewsEdgeCasesTestCase(TestCase):
    """Test edge cases for receipt views."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_receipt_list_empty(self):
        """Test receipt list when user has no receipts."""
        response = self.client.get('/receipt-mgmt/receipts/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 0)
    
    def test_receipt_by_vendor_empty(self):
        """Test by-vendor view when user has no receipts."""
        response = self.client.get('/receipt-mgmt/receipts/by-vendor/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
    
    def test_receipt_smart_search_no_query(self):
        """Test smart search without search parameter."""
        response = self.client.get('/receipt-mgmt/receipts/search/')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Missing ?search=<term> parameter', response.data['detail'])
    
    def test_receipt_smart_search_empty_query(self):
        """Test smart search with empty search parameter."""
        response = self.client.get('/receipt-mgmt/receipts/search/?search=')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Missing ?search=<term> parameter', response.data['detail'])
    
    def test_receipt_smart_search_whitespace_query(self):
        """Test smart search with whitespace-only search parameter."""
        response = self.client.get('/receipt-mgmt/receipts/search/?search=   ')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Missing ?search=<term> parameter', response.data['detail'])
    
    def test_receipt_detail_large_receipt(self):
        """Test receipt detail view with a receipt containing many items."""
        receipt = Receipt.objects.create(
            user=self.user,
            company='Large Store',
            date=date.today(),
            total=Decimal('1000.00'),
            receipt_type=Receipt.ReceiptType.GROCERIES
        )
        
        # Create 50 items
        for i in range(50):
            Item.objects.create(
                receipt=receipt,
                description=f'Item {i+1}',
                total_price=Decimal('20.00')
            )
        
        response = self.client.get(f'/receipt-mgmt/receipts/{receipt.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['items']), 50)
    
    def test_receipt_list_with_special_characters(self):
        """Test receipt list with special characters in company names."""
        special_chars_receipt = Receipt.objects.create(
            user=self.user,
            company='Café & Résturant "L\'Étoile"',
            date=date.today(),
            total=Decimal('25.50')
        )
        
        response = self.client.get('/receipt-mgmt/receipts/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['company'], 'Café & Résturant "L\'Étoile"')
    
    def test_receipt_by_vendor_with_unicode(self):
        """Test by-vendor view with unicode company names."""
        Receipt.objects.create(
            user=self.user,
            company='北京烤鸭店',  # Chinese characters
            date=date.today(),
            total=Decimal('30.00')
        )
        
        Receipt.objects.create(
            user=self.user,
            company='مطعم الشرق',  # Arabic characters
            date=date.today(),
            total=Decimal('40.00')
        )
        
        response = self.client.get('/receipt-mgmt/receipts/by-vendor/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        companies = {bucket['company'] for bucket in response.data}
        self.assertIn('北京烤鸭店', companies)
        self.assertIn('مطعم الشرق', companies)


class ReceiptFilteringTestCase(TestCase):
    """Test advanced filtering scenarios."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create receipts with different types and dates
        self.grocery_receipt = Receipt.objects.create(
            user=self.user,
            company='Grocery Store',
            date=date.today(),
            total=Decimal('50.00'),
            receipt_type=Receipt.ReceiptType.GROCERIES
        )
        
        self.dining_receipt = Receipt.objects.create(
            user=self.user,
            company='Restaurant',
            date=date.today(),
            total=Decimal('75.00'),
            receipt_type=Receipt.ReceiptType.DINING_OUT
        )
        
        self.electronics_receipt = Receipt.objects.create(
            user=self.user,
            company='Electronics Store',
            date=date.today(),
            total=Decimal('200.00'),
            receipt_type=Receipt.ReceiptType.ELECTRONICS
        )
    
    def test_filter_by_multiple_categories(self):
        """Test filtering by multiple receipt categories."""
        # Test filtering by multiple integer IDs
        response = self.client.get('/receipt-mgmt/receipts/?category=1,4')  # Groceries and Electronics
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 2)
        
        companies = {r['company'] for r in results}
        self.assertIn('Grocery Store', companies)
        self.assertIn('Electronics Store', companies)
        self.assertNotIn('Restaurant', companies)
    
    def test_filter_by_mixed_category_formats(self):
        """Test filtering by mixing string names and integer IDs."""
        # Mix string and integer filtering
        response = self.client.get('/receipt-mgmt/receipts/?category=Groceries,4')  # Groceries (string) and Electronics (int)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 2)
        
        companies = {r['company'] for r in results}
        self.assertIn('Grocery Store', companies)
        self.assertIn('Electronics Store', companies)
    
    def test_filter_by_invalid_category(self):
        """Test filtering by invalid category."""
        response = self.client.get('/receipt-mgmt/receipts/?category=InvalidCategory')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 0)  # No matches for invalid category
    
    def test_filter_by_company_case_insensitive(self):
        """Test company filtering is case insensitive."""
        response = self.client.get('/receipt-mgmt/receipts/?company=GROCERY STORE')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['company'], 'Grocery Store')


class ReceiptPaginationTestCase(TestCase):
    """Test pagination behavior."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create many receipts to test pagination
        for i in range(25):
            Receipt.objects.create(
                user=self.user,
                company=f'Store {i+1}',
                date=date.today(),
                total=Decimal(f'{10 + i}.00')
            )
    
    def test_receipt_list_pagination(self):
        """Test that receipt list is properly paginated."""
        # Create many receipts to test pagination
        for i in range(25):
            Receipt.objects.create(
                user=self.user,
                company=f'Store {i+1}',
                date=date.today(),
                total=Decimal(f'{i+10}.00'),
                receipt_type=Receipt.ReceiptType.OTHER
            )
        
        response = self.client.get('/receipt-mgmt/receipts/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check if it's using cursor pagination (which doesn't have 'count')
        if 'next' in response.data and 'previous' in response.data:
            # Cursor pagination
            self.assertIn('results', response.data)
            self.assertTrue(len(response.data['results']) <= 20)  # Default page size
        else:
            # Regular pagination
            self.assertIn('count', response.data)
            self.assertIn('results', response.data)
    
    def test_receipt_list_ordering(self):
        """Test that receipts are ordered by creation date (newest first)."""
        response = self.client.get('/receipt-mgmt/receipts/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        
        # Check that results are ordered by created_at descending
        if len(results) > 1:
            for i in range(len(results) - 1):
                current_date = results[i]['created_at']
                next_date = results[i + 1]['created_at']
                # Current should be newer than or equal to next
                self.assertGreaterEqual(current_date, next_date) 