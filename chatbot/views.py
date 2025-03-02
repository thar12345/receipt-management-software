import os
import json
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from pathlib import Path

# Import the necessary functions from your script
from .utils.query_processor import (
    extract_search_terms,
    load_faiss_indexes,
    search_with_faiss,
    get_executable_code_with_feedback,
    execute_code,
    format_results_with_gpt,
    detect_malicious_intent
)
from sentence_transformers import SentenceTransformer


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, FormParser, MultiPartParser])
@csrf_exempt
def process_query(request):
    """
    POST chatbot/process/  →  JSON or FileResponse
    Supports both JSON and form data input.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are supported'}, status=405)

    # ──────────────────────────────── 1. pull + validate query
    try:
        # Support both JSON and form data
        if hasattr(request, 'data') and 'query' in request.data:
            user_query = request.data.get('query', '').strip()
        else:
            user_query = request.POST.get('query', '').strip()
            
        if not user_query:
            return JsonResponse({'error': 'Query is empty'}, status=400)
    except Exception as e:
        return JsonResponse({'stage': 'get_query', 'error': str(e)}, status=500)

    # ──────────────────────────────── 2. malicious-intent check
    try:
        is_bad, why = detect_malicious_intent(user_query)
        if is_bad:
            return JsonResponse({'stage': 'malicious_check',
                                 'error': f'Query not allowed: {why}'}, status=400)
    except Exception as e:
        return JsonResponse({'stage': 'malicious_check', 'error': str(e)}, status=500)

    # ──────────────────────────────── 3. load models.txt
    try:
        models_path = Path(__file__).resolve().parent / "data" / "model.txt"
        with models_path.open("r", encoding="utf-8") as fh:
            models_content = fh.read()
    except Exception as e:
        return JsonResponse({'stage': 'load_models_file', 'error': str(e)}, status=500)

    # ──────────────────────────────── 4. load FAISS indexes
    try:
        faiss_data = load_faiss_indexes()
    except Exception as e:
        return JsonResponse({'stage': 'load_faiss', 'error': str(e)}, status=500)

    # ──────────────────────────────── 5. NLP extraction + search
    try:
        search_terms   = extract_search_terms(user_query)
        embedder       = SentenceTransformer('all-MiniLM-L6-v2')
        faiss_results  = search_with_faiss(search_terms, faiss_data, embedder)
    except Exception as e:
        return JsonResponse({'stage': 'semantic_search', 'error': str(e)}, status=500)

    # ──────────────────────────────── 6. code generation
    try:
        executable_code = get_executable_code_with_feedback(
            user_query=user_query,
            models_content=models_content,
            faiss_results=faiss_results,
            user=request.user,
            max_attempts=3,
        )
        if not executable_code or executable_code == "Unable to process query":
            return JsonResponse({'stage': 'code_gen',
                                 'error': 'Unable to generate executable code'}, status=400)
    except Exception as e:
        return JsonResponse({'stage': 'code_gen', 'error': str(e)}, status=500)

    # ──────────────────────────────── 7. code execution
    try:
        exec_result = execute_code(executable_code)
    except Exception as e:
        return JsonResponse({'stage': 'code_exec', 'error': str(e)}, status=500)

    # ──────────────────────────────── 8. handle file-type result
    if isinstance(exec_result, dict) and exec_result.get('type') == 'file':
        try:
            return FileResponse(
                exec_result['stream'],
                as_attachment=True,
                filename=exec_result['filename'],
                content_type='application/octet-stream',
            )
        except Exception as e:
            return JsonResponse({'stage': 'file_response', 'error': str(e)}, status=500)

    # ──────────────────────────────── 9. format + return JSON
    try:
        pretty = format_results_with_gpt(user_query, exec_result)
        return JsonResponse({
            'query': user_query,
            'code': executable_code,
            'result': pretty,
        })
    except Exception as e:
        return JsonResponse({'stage': 'format_result', 'error': str(e)}, status=500)
