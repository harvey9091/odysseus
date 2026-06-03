#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_scrape_verbose():
    try:
        from services.scraper.service import ScraperService
        
        print("Creating scraper service...")
        service = ScraperService()
        print("Service created successfully")
        
        print("Starting test scrape run...")
        # Start a small test scrape with just a few stories from Hacker News
        result = service.start_run(
            providers=['hackernews'], 
            filters={
                'days_back': 2,  # Increase to 2 days to get more stories
                'max_stories': 20  # Get more stories
            }, 
            owner='test_user'
        )
        
        print(f"Scrape started: {result}")
        
        run_id = result['run_id']
        print(f"Run ID: {run_id}")
        
        # Monitor progress by checking status periodically
        last_event_count = 0
        max_wait_time = 30  # Maximum wait time in seconds
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # Check if we've waited too long
            if asyncio.get_event_loop().time() - start_time > max_wait_time:
                print("Timeout reached")
                break
                
            # Get current status
            status = service.get_status(run_id)
            if not status:
                print("Run not found")
                break
                
            print(f"Status: {status.get('status')}")
            
            # Show new progress events
            events = status.get('progress_events', [])
            if len(events) > last_event_count:
                new_events = events[last_event_count:]
                for event in new_events:
                    print(f"  Progress: {event.get('type')} - {event.get('message', '')}")
                last_event_count = len(events)
            
            # If completed, break
            if status.get('status') in ['completed', 'failed', 'cancelled']:
                print(f"Run finished with status: {status.get('status')}")
                if status.get('error'):
                    print(f"Error: {status.get('error')}")
                break
                
            # Wait before checking again
            await asyncio.sleep(2)
        
        # Get final results
        print("\n=== FINAL RESULTS ===")
        leads_result = service.get_leads(owner='test_user', limit=20)
        total_leads = leads_result.get('total', 0)
        print(f"Total leads found: {total_leads}")
        
        leads = leads_result.get('leads', [])
        print(f"Showing up to 5 leads:")
        for i, lead in enumerate(leads[:5]):
            print(f"\nLead {i+1}:")
            print(f"  ID: {lead.get('id')}")
            print(f"  Name: {lead.get('name')}")
            print(f"  Website: {lead.get('website')}")
            print(f"  Score: {lead.get('affordability_score')}/100")
            print(f"  Emails: {lead.get('emails', [])}")
            print(f"  Founders: {[f.get('name') for f in lead.get('founders', []) if isinstance(f, dict) and f.get('name')]}")
            print(f"  Source: {lead.get('source_provider')}")
            if lead.get('ai_summary'):
                print(f"  AI Summary: {lead.get('ai_summary')[:100]}...")
        
        print("\nTest completed successfully")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_scrape_verbose())
    sys.exit(0 if success else 1)