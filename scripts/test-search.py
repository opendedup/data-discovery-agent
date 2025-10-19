#!/usr/bin/env python3
"""
Simple script to test Vertex AI Search

Usage:
    poetry run python scripts/test-search.py "your search query"
"""

import sys
from google.cloud import discoveryengine_v1


def search(query: str, max_results: int = 10):
    """Search the Vertex AI Search data store"""
    
    # Initialize client
    client = discoveryengine_v1.SearchServiceClient()
    
    # Search config
    serving_config = (
        "projects/lennyisagoodboy/locations/global/collections/default_collection/"
        "dataStores/data-discovery-metadata/servingConfigs/default_config"
    )
    
    # Create search request
    request = discoveryengine_v1.SearchRequest(
        serving_config=serving_config,
        query=query,
        page_size=max_results,
    )
    
    print(f"\n{'=' * 70}")
    print(f"Search Query: '{query}'")
    print('=' * 70)
    
    try:
        response = client.search(request=request)
        
        total = response.total_size if hasattr(response, 'total_size') else 'Unknown'
        print(f"\nTotal Results: {total}")
        print()
        
        result_count = 0
        for result in response.results:
            result_count += 1
            doc = result.document
            
            print(f"\n{result_count}. Document ID: {doc.id}")
            
            # Extract metadata from struct_data
            if doc.struct_data:
                struct_dict = dict(doc.struct_data)
                
                project = struct_dict.get('project_id', '?')
                dataset = struct_dict.get('dataset_id', '?')
                table = struct_dict.get('table_id', '?')
                
                print(f"   Table: {project}.{dataset}.{table}")
                print(f"   Type: {struct_dict.get('asset_type', '?')}")
                print(f"   Rows: {struct_dict.get('row_count', '?'):,}")
                
                if struct_dict.get('has_pii'):
                    print(f"   ⚠ Contains PII")
                if struct_dict.get('has_phi'):
                    print(f"   ⚠ Contains PHI")
            
            # Show content excerpt
            if doc.content and doc.content.raw_bytes:
                content_text = doc.content.raw_bytes.decode('utf-8', errors='ignore')
                # Show first 200 chars
                excerpt = content_text[:200].replace('\n', ' ')
                print(f"   Excerpt: {excerpt}...")
        
        if result_count == 0:
            print("⚠ No results found. Try a different query.")
        
        print(f"\n{'=' * 70}\n")
        
    except Exception as e:
        print(f"\n✗ Search failed: {e}\n")
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: poetry run python scripts/test-search.py 'your search query'")
        print("\nExamples:")
        print("  poetry run python scripts/test-search.py 'game'")
        print("  poetry run python scripts/test-search.py 'PII'")
        print("  poetry run python scripts/test-search.py 'post_game_summaries'")
        print("  poetry run python scripts/test-search.py 'player statistics'")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    search(query)

