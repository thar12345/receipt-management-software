from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('receipt_mgmt', '0001_initial'),
    ]

    operations = [
        # Enable the pg_trgm extension
        TrigramExtension(),
        
        # Add GIN indexes for text search fields
        migrations.RunSQL(
            sql="""
            CREATE INDEX receipt_company_trigram_idx ON receipt_mgmt_receipt USING gin (company gin_trgm_ops);
            CREATE INDEX receipt_item_description_trigram_idx ON receipt_mgmt_item USING gin (description gin_trgm_ops);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS receipt_company_trigram_idx;
            DROP INDEX IF EXISTS receipt_item_description_trigram_idx;
            """
        ),
    ] 