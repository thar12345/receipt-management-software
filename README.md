# Receipt Management
## Overview

This project is an intelligent receipt management and expense tracking application that uses AI to automatically parse, categorize, and analyze receipts from both image uploads and email processing. Built with Django and integrated with Azure Document Intelligence, it transforms messy receipt data into organized financial insights.

## Features

- **Smart Receipt Processing**: Upload receipt images or forward emails for automatic parsing using Azure Document Intelligence
- **AI-Powered Categorization**: Automatically categorizes receipts into 17+ categories (Groceries, Dining, Electronics, etc.)
- **Google OAuth Integration**: Seamless authentication with Google accounts
- **Advanced Analytics**: Generate spending reports by category, time period, and vendor with PDF/CSV export
- **Smart Search**: Intelligent search across receipt content, vendors, and items
- **Email Receipt Processing**: Automatic receipt extraction from forwarded emails via SendGrid
- **Tagging System**: Custom tags for better organization and filtering
- **Phone Verification**: SMS-based phone number verification through Twilio

## Tech Stack

- **Backend**: Django 4.2.17, Django REST Framework, Celery
- **Database**: PostgreSQL with full-text search, SQLite (development)
- **Authentication**: JWT tokens, Google OAuth2, Phone verification (Twilio)
- **AI/ML**: Azure Document Intelligence, OpenAI API for categorization
- **Real-time**: Django Channels, Redis for WebSocket connections
- **Cloud Storage**: Azure Blob Storage for receipt images
- **Email Processing**: SendGrid Inbound Parse webhook
- **API Documentation**: Django REST Framework browsable API
- **Testing**: pytest, Django test framework

## Challenges & What I Learned

Building this project taught me how to integrate multiple cloud services and AI APIs into a cohesive system. The biggest challenge was creating a reliable document parsing pipeline that could handle various receipt formats while maintaining accuracy. I learned to implement usage-based billing logic, optimize database queries for analytics, and build a scalable architecture that separates concerns between receipt processing, user management, and analytics. Working with real-time features through WebSockets and managing asynchronous tasks with Celery deepened my understanding of concurrent systems.

## How to Run

1. **Clone and setup environment**:
   ```bash
   git clone <repo link>
   cd squirll
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables** (create `.env` file):
   ```bash
   # Database
   DATABASE_URL=postgresql://user:pass@localhost:5432/squirll
   
   # Azure Services
   DOCUMENT_INTELLIGENCE_ENDPOINT=your_azure_endpoint
   DOCUMENT_INTELLIGENCE_KEY=your_azure_key
   
   # Google OAuth
   GOOGLE_OAUTH_CLIENT_IDS=your_google_client_id
   
   # Other services (optional for basic functionality)
   SENTRY_DSN=your_sentry_dsn
   TWILIO_ACCOUNT_SID=your_twilio_sid
   TWILIO_AUTH_TOKEN=your_twilio_token
   ```

3. **Run migrations and start server**:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py runserver
   ```

4. **Start background services** (optional):
   ```bash
   # Redis (for real-time features)
   redis-server
   
   # Celery (for background tasks)
   celery -A squirll worker -l info
   ```

## Future Improvements

- **Mobile Applications**: iOS and Android apps for on-the-go receipt capture
- **Receipt Splitting**: Support for splitting receipts among multiple people/categories
- **Budget Tracking**: Set spending limits and get notifications when approaching them
- **Merchant Recognition**: Build a database of merchant logos for faster categorization
- **Receipt Rewards Integration**: Connect with loyalty programs and cashback services  
- **Advanced Analytics**: Predictive spending analysis and personalized financial insights
- **Export Integrations**: Direct integration with accounting software (QuickBooks, Xero)
- **Bulk Processing**: Upload and process multiple receipts simultaneously
- **Receipt Verification**: Cross-reference with bank statements for accuracy checking
- **Tax Preparation**: Automated tax category assignment and deduction optimization
