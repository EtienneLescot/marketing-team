
# ============================================================================
# Social Media Team Agents
# ============================================================================

def create_social_media_team(config: AgentConfig) -> StateGraph:
    """Create social media team with HITL for publishing"""
    
    @monitor_agent_call("social_media_supervisor")
    async def social_media_supervisor_node(state: TeamState) -> Command[Literal["linkedin_manager", "twitter_manager", "publisher", "__end__"]]:
        """Social media team supervisor with LLM routing"""
        if state.get("iteration_count", 0) >= 3:
            return Command(goto=END)
        
        try:
            decision = await config.social_media_team_router.route(state)
            print(f"DEBUG: Social Media Supervisor Decision: {decision.next_node}")

            monitor = get_global_monitor()
            monitor.record_routing_decision(
                supervisor_name="social_media_supervisor",
                decision=decision.dict(),
                duration_ms=0
            )
            
            update_data = {
                "iteration_count": state.get("iteration_count", 0) + 1,
                "current_agent": decision.next_node if decision.next_node != "FINISH" else None,
                "routing_decision": decision.dict()
            }

            if decision.instructions:
                update_data["messages"] = state.get("messages", []) + [HumanMessage(content=decision.instructions, name="supervisor_instructions")]
            
            if decision.should_terminate or decision.next_node == "FINISH":
                return Command(goto=END, update=update_data)
            
            return Command(goto=decision.next_node, update=update_data)
            
        except Exception as e:
            print(f"Social media supervisor routing failed: {e}")
            # Fallback to publisher if content exists, otherwise finish
            return Command(goto="publisher", update={"iteration_count": state.get("iteration_count", 0) + 1})

    @monitor_agent_call("linkedin_manager")
    async def linkedin_manager_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """LinkedIn Manager Agent"""
        monitor = get_global_monitor()
        try:
            original_task = state["messages"][-1].content if state["messages"] else "No task provided"
            context = "\n".join([f"{msg.name}: {msg.content}" for msg in state["messages"] if hasattr(msg, "name") and msg.name not in ["user", "system"]])
            
            # Using content writer model for now
            llm = config.llm_provider.get_agent_config("content_writer").get_model() 
            
            prompt = f"You are a LinkedIn Manager. Create a professional LinkedIn post based on:\nTask: {original_task}\nContext: {context}"
            monitor.record_agent_prompt("linkedin_manager", prompt)
            
            response = await asyncio.wait_for(llm.ainvoke([{"role": "user", "content": prompt}]), timeout=60.0)
            content = response.content
            
            monitor.record_agent_output("linkedin_manager", content)
            
            return Command(
                goto="supervisor",
                update={
                    "messages": create_agent_response(content, "linkedin_manager", True, original_task),
                    "task_completed": True
                }
            )
        except Exception as e:
            return Command(goto="supervisor", update={"error": str(e)})

    @monitor_agent_call("twitter_manager")
    async def twitter_manager_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Twitter Manager Agent"""
        monitor = get_global_monitor()
        try:
            original_task = state["messages"][-1].content if state["messages"] else "No task provided"
            context = "\n".join([f"{msg.name}: {msg.content}" for msg in state["messages"] if hasattr(msg, "name") and msg.name not in ["user", "system"]])
            
            llm = config.llm_provider.get_agent_config("content_writer").get_model()
            
            prompt = f"You are a Twitter Manager. Create a threaded tweet based on:\nTask: {original_task}\nContext: {context}"
            monitor.record_agent_prompt("twitter_manager", prompt)
            
            response = await asyncio.wait_for(llm.ainvoke([{"role": "user", "content": prompt}]), timeout=60.0)
            content = response.content
            
            monitor.record_agent_output("twitter_manager", content)
            
            return Command(
                goto="supervisor",
                update={
                    "messages": create_agent_response(content, "twitter_manager", True, original_task),
                    "task_completed": True
                }
            )
        except Exception as e:
            return Command(goto="supervisor", update={"error": str(e)})

    @monitor_agent_call("publisher")
    async def publisher_node(state: TeamState) -> Command[Literal["supervisor"]]:
        """Publisher Agent with Human-in-the-Loop"""
        monitor = get_global_monitor()
        
        # Get content to publish (from last manager message)
        content_to_publish = "No content found"
        platform = "Unknown"
        
        for msg in reversed(state["messages"]):
            if hasattr(msg, "name") and msg.name in ["linkedin_manager", "twitter_manager"]:
                content_to_publish = msg.content
                platform = "LinkedIn" if msg.name == "linkedin_manager" else "Twitter"
                break
        
        # Create approval request
        approval_request = f"Please review this {platform} post:\n\n{content_to_publish}\n\nType 'approved' to publish or provide feedback."
        
        # INTERRUPT FOR HUMAN APPROVAL
        monitor.record_event(agent_name="publisher", event_type="waiting_for_approval", data={"content": content_to_publish})
        print(f"\n[bold yellow]✋ Review Required for {platform} Post:[/bold yellow]")
        print(f"{content_to_publish}")
        
        user_feedback = interrupt(approval_request)
        
        if str(user_feedback).lower().strip() == "approved":
            result = f"✅ Successfully published to {platform}!"
            monitor.record_agent_output("publisher", result)
            return Command(
                goto="supervisor", 
                update={
                    "messages": [AIMessage(content=result, name="publisher")],
                    "task_completed": True
                }
            )
        else:
            result = f"❌ Publication rejected. Feedback: {user_feedback}"
            monitor.record_agent_output("publisher", result)
            return Command(
                goto="supervisor", 
                update={
                    "messages": [AIMessage(content=result, name="publisher")],
                    "task_completed": False
                }
            )

    # Build social media team graph
    builder = StateGraph(TeamState)
    builder.add_node("supervisor", social_media_supervisor_node)
    builder.add_node("linkedin_manager", linkedin_manager_node)
    builder.add_node("twitter_manager", twitter_manager_node)
    builder.add_node("publisher", publisher_node)
    
    builder.add_edge(START, "supervisor")
    builder.add_edge("linkedin_manager", "supervisor")
    builder.add_edge("twitter_manager", "supervisor")
    builder.add_edge("publisher", "supervisor")
    
    return builder.compile()
