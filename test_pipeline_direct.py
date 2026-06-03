#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_pipeline_directly():
    try:
        from services.scraper.pipeline_new import NewScraperPipeline
        from services.scraper.providers import get_provider
        
        print("Creating pipeline directly...")
        pipeline = NewScraperPipeline(
            run_id="test-run-123",
            owner="test_user",
            progress_callback=lambda x: print(f"Progress: {x.get('type')} - {x.get('message', '')}")
        )
        print("Pipeline created successfully")
        
        # Get a provider
        provider = get_provider("hackernews")
        if not provider:
            print("Failed to get provider")
            return False
            
        print("Provider obtained successfully")
        
        # Test the provider directly first
        print("Testing provider directly...")
        raw_results = await provider.scrape(
            filters={
                'days_back': 1,
                'max_stories': 5
            }
        )
        print(f"Provider returned {len(raw_results)} results directly")
        
        # Now test through pipeline
        print("Testing pipeline run...")
        result = await pipeline.run(
            providers=["hackernews"],
            filters={
                'days_back': 1,
                'max_stories': 5
            }
        )
        
        print(f"Pipeline result: {result}")
        
        # Clean up
        await provider.close()
        
        return True
        
    except Exception as e:
        print(f"Error in direct pipeline test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_pipeline_directly())
    sys.exit(0 if success else 1)