from celery import shared_task
from chatbot.utils.faiss_utils import append_for_receipt, full_rebuild

@shared_task
def append_faiss_vectors(receipt_id: int):
    append_for_receipt(receipt_id)

@shared_task
def nightly_rebuild_faiss():
    full_rebuild()
