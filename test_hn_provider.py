#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_hn_provider():
    try:
        from services.scraper.providers.hackernews import HackerNewsProvider
        
        print("Creating HackerNews provider...")
        provider = HackerNewsProvider()
        print("Provider created successfully")
        
        print("Testing scrape...")
        # Test with a small number of stories
        results = await provider.scrape(
            filters={
                'days_back': 2,
                'max_stories': 10
            }
        )
        
        print(f"Provider returned {len(results)} results")
        
        for i, result in enumerate(results[:5]):  # Show first 5
            print(f"\nResult {i+1}:")
            print(f"  Name: {getattr(result, 'name', 'N/A')}")
            print(f"  Website: {getattr(result, 'website', 'N/A')}")
            print(f"  Description: {getattr(result, 'description', 'N/A')[:100]}...")
            print(f"  Domain: {getattr(result, 'domain', 'N/A')}")
            
        # Clean up
        await provider.close()
        print("Provider closed successfully")
        
    except Exception as e:
        print(f"Error testing HN provider: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_hn_provider())
    sys.exit(0 if success else 1)