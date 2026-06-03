#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_scrape():
    try:
        from services.scraper.service import ScraperService
        
        print("Creating scraper service...")
        service = ScraperService()
        print("Service created successfully")
        
        # Configure LLM if needed (optional for now)
        # service.configure_llm("http://localhost:11434", "llama2")
        
        print("Starting test scrape run...")
        # Start a small test scrape with just a few stories from Hacker News
        result = service.start_run(
            providers=['hackernews'], 
            filters={
                'days_back': 1, 
                'max_stories': 10  # Just get 10 stories for testing
            }, 
            owner='test_user'
        )
        
        print(f"Scrape started: {result}")
        
        run_id = result['run_id']
        print(f"Run ID: {run_id}")
        
        # Wait a bit for the scrape to process
        print("Waiting for scrape to complete...")
        await asyncio.sleep(5)
        
        # Check status
        status = service.get_status(run_id)
        print(f"Current status: {status}")
        
        # Get some leads
        leads_result = service.get_leads(owner='test_user', limit=5)
        print(f"Found {leads_result.get('total', 0)} leads")
        
        leads = leads_result.get('leads', [])
        for i, lead in enumerate(leads[:3]):  # Show first 3 leads
            print(f"\nLead {i+1}:")
            print(f"  Name: {lead.get('name')}")
            print(f"  Website: {lead.get('website')}")
            print(f"  Score: {lead.get('affordability_score')}")
            print(f"  Emails: {lead.get('emails', [])}")
            print(f"  Founders: {[f.get('name') for f in lead.get('founders', []) if isinstance(f, dict)]}")
        
        # Wait a bit more if still running
        if status and status.get('status') == 'running':
            print("Still running, waiting a bit more...")
            await asyncio.sleep(10)
            
            # Check final status
            status = service.get_status(run_id)
            print(f"Final status: {status}")
        
        print("Test completed successfully")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_scrape())
    sys.exit(0 if success else 1)