#!/usr/bin/env python3
"""
Quick test to verify Vertex AI Search is working.
"""

import os
import time
from dotenv import load_dotenv
from google.cloud import discoveryengine_v1 as discoveryengine

load_dotenv()

def test_vertex_search():
    """Test Vertex AI Search directly."""
    
    project_id = os.getenv("GCP_PROJECT_ID")
    location = os.getenv("VERTEX_LOCATION", "global")
    datastore_id = os.getenv("VERTEX_DATASTORE_ID", "data-discovery-metadata")
    
    print(f"Testing Vertex AI Search...")
    print(f"  Project: {project_id}")
    print(f"  Location: {location}")
    print(f"  Datastore: {datastore_id}")
    print()
    
    # Build serving config path
    serving_config = (
        f"projects/{project_id}/locations/{location}/"
        f"collections/default_collection/dataStores/{datastore_id}/"
        f"servingConfigs/default_config"
    )
    
    print(f"Serving config: {serving_config}")
    print()
    
    # Create search client
    print("Creating search client...")
    search_client = discoveryengine.SearchServiceClient()
    print("✓ Client created")
    print()
    
    # Create search request
    print("Creating search request...")
    search_request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query="tables with data",
        page_size=5,
        filter='has_pii="true"',  # Boolean values must be quoted!
    )
    print("✓ Request created")
    print()
    
    # Execute search
    print("Calling Vertex AI Search API...")
    print("(This is where it might hang...)")
    start_time = time.time()
    
    try:
        response = search_client.search(
            request=search_request,
            timeout=10.0,  # 10 second timeout for testing
        )
        
        elapsed = time.time() - start_time
        print(f"✓ Got response in {elapsed:.2f}s")
        print()
        
        # Iterate results
        print("Iterating results...")
        result_count = 0
        for result in response.results:
            result_count += 1
            print(f"  Result {result_count}: {result.document.id}")
            if result_count >= 3:
                break
        
        print()
        print(f"✓ SUCCESS! Found {result_count} results")
        return True
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"✗ FAILED after {elapsed:.2f}s")
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_vertex_search()
    exit(0 if success else 1)

