async def run(self, providers: List[str], filters: Dict) -> Dict:
    """
    Execute the complete pipeline.
    
    Args:
        providers: List of provider names to use
        filters: Filters to apply (date range, etc.)
        
    Returns:
        Dictionary with pipeline results and analytics
    """
    print(f"[DEBUG] Pipeline run method called with {len(providers)} providers")
    stage_start_time = time.time()
    
    try:
        self.progress({"type": "log", "message": f"Starting new scraper pipeline with {len(providers)} providers"})
        print(f"[DEBUG] Sent start progress message")
        logger.info(f"Starting pipeline {self.run_id} with {len(providers)} providers")
        print(f"[DEBUG] Logged start message")
        
        # Pre-load existing domain dedup cache from DB
        print(f"[DEBUG] About to load dedup cache")
        await self._load_existing_dedup_cache()
        print(f"[DEBUG] Finished loading dedup cache")
        
        total_leads = 0
        total_qualified = 0
        provider_results = {}
        
        # Process each provider
        for provider_name in providers:
            if self._cancelled:
                self.progress({"type": "warning", "message": "Pipeline cancelled"})
                break
                
            provider_start = time.time()
            
            logger.info(f"Processing provider: {provider_name}")
            print(f"[DEBUG] Processing provider: {provider_name}")
            provider = get_provider(provider_name)
            if not provider:
                self.progress({"type": "warning", "provider": provider_name,
                              "message": f"Unknown provider: {provider_name}"})
                logger.warning(f"Unknown provider: {provider_name}")
                continue
                
            self.progress({"type": "provider_update", "provider": provider_name, "status": "discovering"})
            logger.info(f"Provider {provider_name} status: discovering")
            print(f"[DEBUG] Set provider {provider_name} status to discovering")
            
            try:
                # Stage 1: Startup Discovery Layer (Provider scraping)
                logger.info(f"Calling provider.scrape for {provider_name}")
                print(f"[DEBUG] About to call provider.scrape for {provider_name}")
                raw_results = await provider.scrape(filters, self.progress)
                provider_raw_count = len(raw_results)
                self.analytics["raw_candidates"] += provider_raw_count
                
                logger.info(f"Provider {provider_name} returned {provider_raw_count} raw results")
                print(f"[DEBUG] Provider {provider_name} returned {provider_raw_count} raw results")
                self.progress({
                    "type": "log",
                    "provider": provider_name,
                    "message": f"Discovered {provider_raw_count} raw candidates"
                })
                logger.info(f"Sent progress message: Discovered {provider_raw_count} raw candidates")
                print(f"[DEBUG] Sent progress message about raw candidates")
                
                # Process each candidate through the pipeline
                provider_qualified = 0
                provider_stored = 0
                
                for i, result in enumerate(raw_results):
                    if self._cancelled:
                        logger.info("Pipeline cancelled, breaking")
                        break
                        
                    stage_start = time.time()
                    
                    # Convert provider result to dictionary
                    lead_data = result.to_dict() if hasattr(result, 'to_dict') else dict(result)
                    
                    # Ensure we have basic fields
                    if not lead_data.get("name") or not lead_data.get("website"):
                        self.analytics["rejected_candidates"] += 1
                        logger.debug(f"Rejected candidate due to missing name/website: {lead_data.get('name', 'N/A')}")
                        continue
                    
                    self.analytics["candidates_processed"] += 1
                    
                    # Log every 10th candidate to avoid too much output
                    if i % 10 == 0:
                        logger.debug(f"Processing candidate {i}: {lead_data.get('name', 'N/A')}")
                    
                    # Stage 2: Basic validation (filter obvious non-starts)
                    validation = self.validator.validate(lead_data)
                    if validation.is_article or validation.is_platform_page or not validation.is_valid:
                        self.analytics["rejected_candidates"] += 1
                        logger.debug(f"Rejected candidate {lead_data.get('name', 'N/A')} due to validation: article={validation.is_article}, platform={validation.is_platform_page}, valid={validation.is_valid}")
                        continue
                    
                    # Stage 3: Startup Qualification Engine
                    qualification = self.qualifier.qualify(lead_data)
                    if not qualification.is_startup:
                        self.analytics["rejected_candidates"] += 1
                        logger.debug(f"Rejected candidate {lead_data.get('name', 'N/A')} due to qualification: {qualification.is_startup}, confidence={qualification.confidence}")
                        continue
                    
                    self.analytics["qualified_startups"] += 1
                    provider_qualified += 1
                    logger.info(f"Qualified startup: {lead_data.get('name', 'N/A')} with confidence {qualification.confidence}")
                    
                    # Add qualification data to lead
                    lead_data["startup_confidence"] = qualification.confidence
                    lead_data["company_stage"] = qualification.company_stage
                    lead_data["qualification_signals"] = qualification.signals
                    
                    # Stage 4: Check for duplicates (cross-provider and within-run)
                    if self._is_duplicate(lead_data):
                        self.analytics["rejected_candidates"] += 1
                        logger.debug(f"Rejected candidate {lead_data.get('name', 'N/A')} due to duplication")
                        continue
                    
                    # Mark as seen for deduplication
                    self._mark_as_seen(lead_data)
                    
                    # Stage 5: Video detection (exclude leads with existing promo videos)
                    if lead_data.get("website"):
                        try:
                            video_result = await self.video_detector.check(lead_data["website"])
                            if video_result.get("has_video"):
                                self.analytics["rejected_candidates"] += 1
                                logger.debug(f"Rejected candidate {lead_data.get('name', 'N/A')} due to existing video")
                                continue
                        except Exception as e:
                            logger.warning(f"Video detection failed for {lead_data.get('website')}: {e}")
                            pass  # Continue if video detection fails
                    
                    # Stage 6: Contact Discovery Engine (Email-First)
                    logger.debug(f"Starting email discovery for {lead_data.get('name', 'N/A')}")
                    emails = await self.email_discovery.discover_emails(lead_data)
                    if emails:
                        lead_data["emails"] = [email["email"] for email in emails]
                        lead_data["email_details"] = emails
                        self.analytics["emails_found"] += len(emails)
                        # Count verified emails (high confidence)
                        verified_count = sum(1 for email in emails if email.get("confidence", 0) >= 80)
                        self.analytics["verified_emails"] += verified_count
                        logger.info(f"Found {len(emails)} emails ({verified_count} high confidence) for {lead_data.get('name', 'N/A')}")
                    else:
                        # No emails found - this significantly reduces lead value
                        # But we continue with enrichment in case we can find emails later
                        lead_data["emails"] = []
                        lead_data["email_details"] = []
                        logger.debug(f"No emails found for {lead_data.get('name', 'N/A')}")
                    
                    # Stage 7: Lead Enrichment Engine
                    try:
                        logger.debug(f"Starting enrichment for {lead_data.get('name', 'N/A')}")
                        enriched_data = await self.enrichment_engine.enrich_lead(
                            lead_data, 
                            emails=lead_data.get("email_details", []),
                            founders=lead_data.get("founders", []),
                            social=lead_data.get("social", {})
                        )
                        lead_data.update(enriched_data)
                        logger.debug(f"Enrichment completed for {lead_data.get('name', 'N/A')}")
                    except Exception as e:
                        logger.warning(f"Enrichment failed for {lead_data.get('name')}: {e}")
                        # Continue with basic data
                    
                    # Stage 8: Scoring Engine (using legacy format for backward compatibility)
                    try:
                        logger.debug(f"Starting scoring for {lead_data.get('name', 'N/A')}")
                        legacy_scores = self.scorer.score_lead_legacy_format(lead_data)
                        lead_data.update(legacy_scores)
                        
                        # Also store the detailed scores for internal use
                        lead_data["startup_score"] = lead_data["affordability_score"]  # For internal tracking
                        
                        logger.info(f"Scored lead {lead_data.get('name', 'N/A')}: {lead_data.get('affordability_score')} "
                                   f"(affordability: {lead_data.get('affordability_score')}, "
                                   f"video_fit: {lead_data.get('promo_video_fit_score')})")
                    
                    except Exception as e:
                        logger.warning(f"Scoring failed for {lead_data.get('name')}: {e}")
                        # Provide default legacy scores
                        lead_data.update({
                            "affordability_score": 0,
                            "promo_video_fit_score": 0,
                            "urgency_score": 0,
                            "funding_probability": 0,
                            "ai_summary": "Scoring failed",
                            "ai_reasoning": "{}",
                            "outreach_recommendations": "Manual review recommended"
                        })
                    
                    # Stage 9: Storage Engine
                    try:
                        logger.debug(f"Attempting to store lead {lead_data.get('name', 'N/A')}")
                        stored_lead = self.store.create_lead(self.run_id, lead_data, self.owner)
                        if stored_lead:
                            total_leads += 1
                            provider_stored += 1
                            self.analytics["stored_leads"] += 1
                            
                            self.progress({
                                "type": "lead_found",
                                "provider": provider_name,
                                "lead": {
                                    "id": stored_lead.id,
                                    "name": lead_data.get("name"),
                                    "website": lead_data.get("website"),
                                    "score": lead_data.get("affordability_score", 0),
                                    "emails_found": len(lead_data.get("emails", []))
                                }
                            })
                            logger.info(f"Stored lead: {lead_data.get('name', 'N/A')} with score {lead_data.get('affordability_score', 0)}")
                            
                    except Exception as e:
                        logger.warning(f"Failed to store lead {lead_data.get('name')}: {e}")
                        import traceback
                        logger.warning(traceback.format_exc())
                    
                    # Update stage timing
                    stage_time = time.time() - stage_start
                    stage_name = "pipeline_stage"
                    current_time = self.analytics["stage_timings"].get(stage_name, 0)
                    self.analytics["stage_timings"][stage_name] = current_time + stage_time
                    
                    # Rate limiting between leads
                    await asyncio.sleep(0.2)
                
                provider_time = time.time() - provider_start
                provider_results[provider_name] = {
                    "raw_candidates": provider_raw_count,
                    "qualified_startups": provider_qualified,
                    "stored_leads": provider_stored,
                    "time_taken": provider_time
                }
                
                logger.info(f"Provider {provider_name} completed: {provider_qualified} qualified, {provider_stored} stored (took {provider_time:.1f}s)")
                print(f"[DEBUG] Provider {provider_name} completed: {provider_qualified} qualified, {provider_stored} stored")
                self.progress({
                    "type": "log",
                    "provider": provider_name,
                    "message": f"Processed: {provider_qualified} qualified, {provider_stored} stored "
                             f"(took {provider_time:.1f}s)"
                )
                
            except Exception as e:
                logger.error(f"[{provider_name}] Pipeline error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                self.progress({
                    "type": "error",
                    "provider": provider_name,
                    "message": f"Error: {str(e)}"
                })
                
            finally:
                # Close provider
                try:
                    await provider.close()
                except Exception as e:
                    logger.warning(f"Error closing provider {provider_name}: {e}")
                pass
                
            self.progress({"type": "provider_update", "provider": provider_name, "status": "completed"})
            logger.info(f"Provider {provider_name} status: completed")
            print(f"[DEBUG] Provider {provider_name} status set to completed")
        
        # Finalize analytics
        self.analytics["end_time"] = time.time()
        self.analytics["total_time"] = self.analytics["end_time"] - self.analytics["start_time"]
        
        # Update run status in storage
        self.store.update_run_status(
            self.run_id, 
            "completed" if not self._cancelled else "cancelled",
            leads_found=total_leads,
            leads_qualified=total_qualified  # Note: this is different from our qualified_startups
        )
        
        self.progress({
            "type": "completed",
            "stats": {
                "raw_candidates": self.analytics["raw_candidates"],
                "qualified_startups": self.analytics["qualified_startups"],
                "emails_found": self.analytics["emails_found"],
                "verified_emails": self.analytics["verified_emails"],
                "stored_leads": self.analytics["stored_leads"],
                "total_time": f"{self.analytics['total_time']:.1f}s"
            }
        })
        
        logger.info(f"Pipeline {self.run_id} completed: "
                   f"{self.analytics['raw_candidates']} raw → "
                   f"{self.analytics['qualified_startups']} qualified → "
                   f"{self.analytics['stored_leads']} stored")
        print(f"[DEBUG] Pipeline {self.run_id} completed")
        
        return {
            "success": not self._cancelled,
            "run_id": self.run_id,
            "analytics": self.analytics.copy(),
            "provider_results": provider_results
        }
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        self.store.update_run_status(self.run_id, "failed", error=str(e))
        self.progress({"type": "error", "message": f"Pipeline failed: {str(e)}"})
        raise