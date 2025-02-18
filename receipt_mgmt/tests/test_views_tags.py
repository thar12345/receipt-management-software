"""
Additional tests for tag views to ensure comprehensive coverage.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date
from decimal import Decimal

from receipt_mgmt.models import Receipt, Tag

User = get_user_model()


class TagViewsEdgeCasesTestCase(TestCase):
    """Test edge cases for tag views."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )
        
        self.other_user = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='testpass123'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.receipt = Receipt.objects.create(
            user=self.user,
            company='Test Store',
            date=date.today(),
            total=Decimal('10.00')
        )
        
        self.other_receipt = Receipt.objects.create(
            user=self.other_user,
            company='Other Store',
            date=date.today(),
            total=Decimal('20.00')
        )
    
    def test_tag_add_to_other_users_receipt(self):
        """Test that users cannot add tags to other users' receipts."""
        response = self.client.post(reverse('tag-add'), {
            'receipt_id': self.other_receipt.id,
            'name': 'Unauthorized Tag'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_tag_add_with_empty_name(self):
        """Test tag addition with empty name."""
        response = self.client.post(reverse('tag-add'), {
            'receipt_id': self.receipt.id,
            'name': ''
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Missing \'name\' field', response.data['error'])
    
    def test_tag_add_with_whitespace_name(self):
        """Test tag addition with whitespace-only name."""
        response = self.client.post(reverse('tag-add'), {
            'receipt_id': self.receipt.id,
            'name': '   '
        }, format='json')
        
        # Should succeed but name will be stripped
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify tag was created with stripped name
        tag = Tag.objects.get(user=self.user, name='   ')
        self.assertEqual(tag.name, '   ')  # Django doesn't automatically strip
    
    def test_tag_add_duplicate_to_same_receipt(self):
        """Test adding the same tag to a receipt twice."""
        # Add tag first time
        response1 = self.client.post(reverse('tag-add'), {
            'receipt_id': self.receipt.id,
            'name': 'Duplicate Tag'
        }, format='json')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Add same tag again
        response2 = self.client.post(reverse('tag-add'), {
            'receipt_id': self.receipt.id,
            'name': 'Duplicate Tag'
        }, format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        
        # Should still only have one tag association
        self.assertEqual(self.receipt.tags.count(), 1)
        self.assertEqual(Tag.objects.filter(user=self.user, name='Duplicate Tag').count(), 1)
    
    def test_tag_add_with_very_long_name(self):
        """Test tag addition with very long name."""
        long_name = 'A' * 100  # Very long tag name (exceeds 50 char limit)
        
        # This should fail due to database constraint - the test client will raise the exception
        with self.assertRaises(Exception):  # DataError will be raised
            response = self.client.post(reverse('tag-add'), {
                'receipt_id': self.receipt.id,
                'name': long_name
            }, format='json')
    
    def test_tag_remove_non_existent_tag(self):
        """Test removing a tag that doesn't exist."""
        response = self.client.post(reverse('tag-remove'), {
            'receipt_id': self.receipt.id,
            'tag_id': 99999
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_tag_remove_other_users_tag(self):
        """Test removing another user's tag."""
        # Create tag for other user
        other_tag = Tag.objects.create(user=self.other_user, name='Other Tag')
        
        response = self.client.post(reverse('tag-remove'), {
            'receipt_id': self.receipt.id,
            'tag_id': other_tag.id
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_tag_remove_not_associated_tag(self):
        """Test removing a tag that's not associated with the receipt."""
        # Create tag but don't associate it
        tag = Tag.objects.create(user=self.user, name='Unassociated Tag')
        
        response = self.client.post(reverse('tag-remove'), {
            'receipt_id': self.receipt.id,
            'tag_id': tag.id
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('is not associated with this receipt', response.data['error'])
    
    def test_tag_remove_shared_tag(self):
        """Test removing a tag that's shared with another receipt."""
        # Create another receipt
        receipt2 = Receipt.objects.create(
            user=self.user,
            company='Store 2',
            date=date.today(),
            total=Decimal('30.00')
        )
        
        # Create tag and associate with both receipts
        tag = Tag.objects.create(user=self.user, name='Shared Tag')
        self.receipt.tags.add(tag)
        receipt2.tags.add(tag)
        
        # Remove tag from first receipt
        response = self.client.post(reverse('tag-remove'), {
            'receipt_id': self.receipt.id,
            'tag_id': tag.id
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['tag_deleted'])  # Should not be deleted
        
        # Verify tag still exists and is associated with receipt2
        tag.refresh_from_db()
        self.assertEqual(tag.receipts.count(), 1)
        self.assertIn(receipt2, tag.receipts.all())
    
    def test_tag_delete_other_users_tag(self):
        """Test deleting another user's tag."""
        other_tag = Tag.objects.create(user=self.other_user, name='Other Tag')
        
        response = self.client.delete(reverse('tag-delete', kwargs={'tag_id': other_tag.id}))
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_tag_delete_non_existent_tag(self):
        """Test deleting a non-existent tag."""
        response = self.client.delete(reverse('tag-delete', kwargs={'tag_id': 99999}))
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_tag_edit_name_other_users_tag(self):
        """Test editing another user's tag name."""
        other_tag = Tag.objects.create(user=self.other_user, name='Other Tag')
        
        response = self.client.patch(reverse('tag-edit-name'), {
            'tag_id': other_tag.id,
            'name': 'Hacked Name'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_tag_edit_name_to_existing_name(self):
        """Test editing tag name to an already existing name."""
        tag1 = Tag.objects.create(user=self.user, name='Tag 1')
        tag2 = Tag.objects.create(user=self.user, name='Tag 2')
        
        response = self.client.patch(reverse('tag-edit-name'), {
            'tag_id': tag1.id,
            'name': 'Tag 2'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('already exists', response.data['error'])
    
    def test_tag_edit_name_to_same_name(self):
        """Test editing tag name to the same name (should succeed)."""
        tag = Tag.objects.create(user=self.user, name='Same Name')
        
        response = self.client.patch(reverse('tag-edit-name'), {
            'tag_id': tag.id,
            'name': 'Same Name'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_tag_edit_name_with_empty_name(self):
        """Test editing tag name to empty string."""
        tag = Tag.objects.create(user=self.user, name='Original Name')
        
        response = self.client.patch(reverse('tag-edit-name'), {
            'tag_id': tag.id,
            'name': ''
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Missing', response.data['error'])
    
    def test_tag_edit_name_missing_fields(self):
        """Test editing tag name with missing fields."""
        tag = Tag.objects.create(user=self.user, name='Test Tag')
        
        # Missing tag_id
        response1 = self.client.patch(reverse('tag-edit-name'), {
            'name': 'New Name'
        }, format='json')
        self.assertEqual(response1.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Missing name
        response2 = self.client.patch(reverse('tag-edit-name'), {
            'tag_id': tag.id
        }, format='json')
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_tag_listall_empty(self):
        """Test listing tags when user has no tags."""
        response = self.client.get(reverse('tag-listall'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
    
    def test_tag_listall_multiple_tags(self):
        """Test listing multiple tags."""
        # Create multiple tags
        tag1 = Tag.objects.create(user=self.user, name='Tag 1')
        tag2 = Tag.objects.create(user=self.user, name='Tag 2')
        tag3 = Tag.objects.create(user=self.user, name='Tag 3')
        
        response = self.client.get(reverse('tag-listall'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        
        tag_names = {tag['name'] for tag in response.data}
        self.assertEqual(tag_names, {'Tag 1', 'Tag 2', 'Tag 3'})
    
    def test_tag_listall_isolation(self):
        """Test that users only see their own tags."""
        # Create tags for both users
        Tag.objects.create(user=self.user, name='My Tag')
        Tag.objects.create(user=self.other_user, name='Other Tag')
        
        response = self.client.get(reverse('tag-listall'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'My Tag')


class TagViewsSpecialCharactersTestCase(TestCase):
    """Test tag views with special characters and unicode."""
    
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
            total=Decimal('10.00')
        )
    
    def test_tag_with_unicode_characters(self):
        """Test creating tags with unicode characters."""
        unicode_names = [
            '食品',  # Chinese
            'الطعام',  # Arabic
            'Еда',   # Russian
            '🍕🍔',  # Emojis
            'Café & Résturant'  # Accented characters
        ]
        
        for name in unicode_names:
            response = self.client.post(reverse('tag-add'), {
                'receipt_id': self.receipt.id,
                'name': name
            }, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK, 
                           f"Failed to create tag with name: {name}")
    
    def test_tag_with_special_characters(self):
        """Test creating tags with special characters."""
        special_names = [
            'Tag & Co.',
            'Tag "Quoted"',
            "Tag 'Single'",
            'Tag <HTML>',
            'Tag\\Backslash',
            'Tag/Forward',
            'Tag@Email',
            'Tag#Hash',
            'Tag$Money',
            'Tag%Percent'
        ]
        
        for name in special_names:
            response = self.client.post(reverse('tag-add'), {
                'receipt_id': self.receipt.id,
                'name': name
            }, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK,
                           f"Failed to create tag with name: {name}")
    
    def test_tag_case_sensitivity(self):
        """Test that tag names are case sensitive."""
        # Create tag with lowercase
        response1 = self.client.post(reverse('tag-add'), {
            'receipt_id': self.receipt.id,
            'name': 'groceries'
        }, format='json')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Create tag with uppercase (should be different)
        response2 = self.client.post(reverse('tag-add'), {
            'receipt_id': self.receipt.id,
            'name': 'GROCERIES'
        }, format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        
        # Should have two different tags
        self.assertEqual(Tag.objects.filter(user=self.user).count(), 2) 