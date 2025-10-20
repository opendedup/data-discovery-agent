#!/usr/bin/env python3
"""Test wildcard query."""

import os
import time
from dotenv import load_dotenv
from google.cloud import discoveryengine_v1 as discoveryengine

load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID")
location = os.getenv("VERTEX_LOCATION", "global")
datastore_id = os.getenv("VERTEX_DATASTORE_ID", "data-discovery-metadata")

serving_config = (
    f"projects/{project_id}/locations/{location}/"
    f"collections/default_collection/dataStores/{datastore_id}/"
    f"servingConfigs/default_config"
)

search_client = discoveryengine.SearchServiceClient()

print("Test 1: Wildcard query (no filter)")
print("Query: '*'")
try:
    start = time.time()
    search_request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query="*",  # Wildcard
        page_size=10,
    )
    response = search_client.search(request=search_request, timeout=5.0)
    
    count = sum(1 for _ in response.results)
    elapsed = time.time() - start
    print(f"✓ SUCCESS in {elapsed:.2f}s - Found {count} results\n")
except Exception as e:
    elapsed = time.time() - start
    print(f"✗ FAILED in {elapsed:.2f}s: {e}\n")

print("Test 2: Empty query (no filter)")
print('Query: ""')
try:
    start = time.time()
    search_request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query="",  # Empty
        page_size=10,
    )
    response = search_client.search(request=search_request, timeout=5.0)
    
    count = sum(1 for _ in response.results)
    elapsed = time.time() - start
    print(f"✓ SUCCESS in {elapsed:.2f}s - Found {count} results\n")
except Exception as e:
    elapsed = time.time() - start
    print(f"✗ FAILED in {elapsed:.2f}s: {e}\n")

