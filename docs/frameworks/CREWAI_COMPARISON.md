# CrewAI Framework Comparison

## Developer Experience
- **Setup time**: Very fast (simple class instantiations vs LangGraph's node/edge wiring).
- **Code clarity**: 9/10 (Agents and Tasks are defined declaratively).
- **Learning curve**: Easy. Role-playing abstractions make intuitive sense.

## Technical Findings
- **Pydantic v2**: `BaseTool` is highly sensitive to Pydantic v2 validation. Dynamic tool creation requires explicit `args_schema` derived from MCP JSON schemas.
- **Async Bridging**: Integrating with async frameworks (MCP) requires `asyncio.run_coroutine_threadsafe` because CrewAI agents run in separate worker threads by default.
- **LiteLLM**: Implicitly used for model routing; requires explicit installation of provider extras (e.g., `crewai[google-genai]`) for Gemini support.

## Performance
- **Speed**: Sequential execution is the default, which is slower than parallel nodes in LangGraph.
- **Responsiveness**: Requires `step_callback` hooks for real-time UI updates in frameworks like Chainlit.
- **Token efficiency**: Higher overhead due to verbose scratchpads and internal thought cycles.

## Pros
- Outstanding abstraction model (Agents, Tasks, Crew).
- Very low boiler-plate for simple linear chains.
- Robust built-in error handling and self-correction during tool calls.

## Cons
- Less fine-grained control over specific execution paths compared to LangGraph.
- Debugging cross-thread issues is non-trivial.
- Statically typed tool schemas are harder to generate dynamically than LangChain's `StructuredTool`.
- **Memory Handling**: CrewAI Tasks are stateless by default. Conversation history from frameworks like Chainlit must be manually formatted and injected into task descriptions to maintain context.

## Verdict
- **Current Choice**: LangGraph remains better for complex, cyclical, or human-gate-heavy systems. 
- **CrewAI Best Use**: Excellent for "autonomous research/content teams" where the target outcome is a refined document and sequential logic is sufficient.
