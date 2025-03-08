from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

class ChatbotTestCase(TestCase):
    
    def setUp(self):
        """Set up test data."""
        User = get_user_model()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        
        # Get authentication token
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_chatbot_imports(self):
        """Test that all chatbot imports work correctly."""
        try:
            from chatbot.utils.query_processor import (
                extract_search_terms,
                load_faiss_indexes,
                search_with_faiss,
                get_executable_code_with_feedback,
                execute_code,
                format_results_with_gpt,
                detect_malicious_intent
            )
            self.assertTrue(True, "All imports successful")
        except ImportError as e:
            self.fail(f"Import error: {e}")
    
    def test_chatbot_settings(self):
        """Test that chatbot settings are properly configured."""
        from django.conf import settings
        
        required_settings = [
            'FAISS_CACHE_DIR',
            'FAISS_CONTAINER', 
            'FAISS_PREFIX'
        ]
        
        for setting in required_settings:
            self.assertTrue(hasattr(settings, setting), f"Missing setting: {setting}")
    
    def test_chatbot_endpoint_structure(self):
        """Test that the chatbot endpoint exists and has proper structure."""
        # Test that URL exists
        url = reverse('chatbot:process_query')
        self.assertIsNotNone(url)
        
        # Test that endpoint responds (even if it fails due to missing env vars)
        response = self.client.post(url, data={'query': 'test query'})
        
        # Should not be 404 (endpoint exists)
        self.assertNotEqual(response.status_code, 404)
        
        # Should not be 405 (method allowed)
        self.assertNotEqual(response.status_code, 405)
