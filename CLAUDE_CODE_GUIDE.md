# Working with Claude Code - Quick Reference

> How to effectively use Claude Code to build your multi-agent system

---

## 🚀 Getting Started with a Phase

### Starting a New Phase
```
"I want to start Phase [number]. Show me what I need to do."
```

**Example**:
```
"I want to start Phase 1 - First Multi-Agent. Help me set up the supervisor pattern."
```

Claude Code will:
1. Check where you are in the roadmap
2. Show you the phase objectives
3. Help you implement each task
4. Test your implementation

---

## 💬 Effective Prompts for Each Phase Type

### For Implementation Phases (1, 2, 7, 8)

**Starting**:
```
"Start Phase [X]. I'm ready to implement [feature]. Guide me step by step."
```

**When Coding**:
```
"Create a [agent/component] that [does something].
Use the existing [file/pattern] as a reference."
```

**Example**:
```
"Create a SearchAgent class in src/confluence_mcp.chat_app/agents/search_agent.py
that specializes in Confluence search. Use the existing graph.py as a reference
for the agent pattern."
```

**Debugging**:
```
"I'm getting this error: [paste error]
Here's my code: [describe or show location]
Help me fix it."
```

---

### For Experiment Phases (3, 4, 5)

**Starting Experiment**:
```
"I want to try [Framework] now. Set up the basics and show me how to
port my existing [agent/workflow]."
```

**Example**:
```
"I want to try CrewAI now. Set up the basics and show me how to port
my supervisor pattern from LangGraph to CrewAI."
```

**Comparing**:
```
"I just finished Phase [X] with [Framework]. Help me document:
- What I liked
- What I didn't like
- Performance observations
- Would I use this in production?"
```

**Decision Time**:
```
"I've tried LangGraph, CrewAI, and AWS Bedrock. Help me compare them
and decide which to use for production based on:
- My use case: [describe]
- My constraints: [list]
- My priorities: [list]"
```

---

### For Documentation Phases (0, 6, 9)

**Auditing**:
```
"Help me audit [file/component/architecture]. Explain:
- What it does
- How it works
- What could be improved"
```

**Decision Documentation**:
```
"Help me document why I chose [Framework] over [alternatives].
Include trade-offs and future considerations."
```

**Creating Docs**:
```
"Create documentation for [feature] that includes:
- Overview
- Usage examples
- API reference
- Common pitfalls"
```

---

## 🎯 Phase-Specific Prompts

### Phase 0: Foundation
```bash
"Audit the current Confluence MCP codebase:
1. What are the main components?
2. How do they interact?
3. What's the current agent architecture?
4. What are the pain points?"
```

```bash
"Set up testing framework for multi-agent development.
Include fixtures for mocking Confluence API."
```

---

### Phase 1: First Multi-Agent
```bash
"Implement a supervisor pattern with 3 specialized agents:
- SearchAgent: Confluence search expert
- WriterAgent: Documentation writer
- ReviewerAgent: Quality reviewer

Start with the supervisor routing logic."
```

```bash
"Add visualization to the Chainlit UI showing:
- Which agent is currently active
- What each agent is doing
- Progress through the workflow"
```

---

### Phase 2: Intelligence & Memory
```bash
"Add persistent memory to the agents using LangGraph checkpointer.
Show me how to maintain conversation history across sessions."
```

```bash
"Create a SharedKnowledge class that all agents can read from and write to.
Include examples of what knowledge should be shared."
```

---

### Phase 3: CrewAI Experiment
```bash
"Port my supervisor pattern to CrewAI. Show me:
1. How to define agents as crew members
2. How to define tasks
3. How to set up sequential/parallel processes
4. How it compares to LangGraph"
```

---

### Phase 4: AWS Bedrock
```bash
"Set up AWS Bedrock Agent with CDK. Create:
1. Lambda functions for Confluence tools
2. Agent definition
3. Deploy script
4. Test script"
```

---

### Phase 5: Google Vertex AI
```bash
"Create Vertex AI Reasoning Engine for Confluence operations.
Show me how to deploy multiple specialized agents."
```

---

### Phase 7: Production Build
```bash
"Design production architecture for [chosen framework].
Include:
- High availability
- Monitoring
- Error handling
- Scaling strategy"
```

```bash
"Add OpenTelemetry tracing to track agent execution.
Include metrics for:
- Agent invocation count
- Execution time
- Success/failure rate
- Token usage"
```

---

### Phase 8: Advanced Features
```bash
"Implement selective RAG:
- Use native Confluence search for simple queries
- Use semantic search for complex queries
- Auto-route based on query complexity"
```

```bash
"Create a knowledge graph of Confluence pages:
- Build graph from page links
- Find orphaned pages
- Suggest new connections
- Identify central pages"
```

---

## 🐛 Debugging with Claude Code

### When Something Breaks
```
"I'm getting [error] when [doing action].

Context:
- Phase: [X]
- Task: [Y]
- What I tried: [Z]

Stack trace:
[paste error]

Help me debug."
```

### Performance Issues
```
"My agent workflow is taking [X] seconds. Expected [Y] seconds.

Current implementation:
[describe or show file path]

Help me identify bottlenecks and optimize."
```

### Understanding Errors
```
"I don't understand this error: [paste error]

Explain:
- What it means
- Why it's happening
- How to fix it
- How to prevent it"
```

---

## 📊 Progress Tracking with Claude Code

### Checking In
```
"What phase am I on? What have I completed? What's next?"
```

Claude Code will read PHASE_TRACKER.md and tell you.

### Updating Progress
```
"I just completed [task/phase]. Update my progress tracker."
```

### Getting Unstuck
```
"I'm stuck on [task]. I've been working on it for [time].
Here's what I've tried: [list]
What should I try next?"
```

---

## 🎓 Learning with Claude Code

### Deep Dives
```
"Explain [concept] in detail with examples from our codebase."
```

**Example**:
```
"Explain LangGraph state management in detail with examples
from our supervisor implementation."
```

### Comparisons
```
"Compare [approach A] vs [approach B] for [use case] in our system."
```

**Example**:
```
"Compare sequential vs parallel agent execution for our
documentation pipeline. Which is better and why?"
```

### Best Practices
```
"Review my [file/component] implementation.
Suggest improvements following best practices."
```

---

## 💡 Tips for Better Prompts

### ✅ DO:
- **Be specific**: "Create SearchAgent with CQL query expertise"
- **Provide context**: "I'm in Phase 1, working on supervisor pattern"
- **Reference existing code**: "Similar to how graph.py does it"
- **State constraints**: "Must work with existing MCP server"
- **Share errors fully**: Include stack traces
- **Ask for explanations**: "Explain why this approach is better"

### ❌ DON'T:
- Be vague: "Make it better"
- Skip context: "Fix this"
- Hide information: "Something's broken"
- Jump ahead: "Implement Phase 8 features" (when on Phase 2)
- Ignore roadmap: Build random features without context

---

## 🔄 Iterative Development Pattern

### 1. Plan
```
"I want to implement [feature]. Show me the plan:
- What files to create/modify
- What patterns to use
- What order to do things"
```

### 2. Implement
```
"Let's start with step 1: [specific task]"
```

### 3. Test
```
"Create tests for [feature]. Include:
- Unit tests
- Integration tests
- Example usage"
```

### 4. Review
```
"Review the [feature] implementation:
- Is it following best practices?
- Are there edge cases I missed?
- How can it be improved?"
```

### 5. Document
```
"Document [feature] with:
- Usage examples
- Configuration options
- Common issues"
```

---

## 🎯 Session Management

### Starting a Session
```
"I'm back to work on the multi-agent project.
Show me where I left off and what's next."
```

### Ending a Session
```
"I'm done for today. Summary:
- Completed: [what you did]
- Learned: [key insights]
- Next time: [what to do next]

Update the tracker."
```

---

## 🆘 When You're Completely Lost

```
"I'm lost. Help me:
1. Where am I in the roadmap?
2. What was I working on?
3. What should I focus on next?
4. Give me a simple task to get momentum."
```

---

## 📚 Quick Reference Commands

| Goal | Prompt Template |
|------|----------------|
| **Start Phase** | `"Start Phase [X]. Guide me through it."` |
| **Implement Feature** | `"Create [component] that does [thing]."` |
| **Debug Error** | `"Fix error: [error]. Context: [info]."` |
| **Compare Options** | `"Compare [A] vs [B] for [use case]."` |
| **Get Unstuck** | `"I'm stuck on [task]. Tried: [things]. Help."` |
| **Review Code** | `"Review [file]. Suggest improvements."` |
| **Check Progress** | `"Where am I? What's next?"` |
| **Learn Concept** | `"Explain [concept] with examples from our code."` |

---

## 🎓 Remember

1. **Claude Code has context** - It can read your files, understand your roadmap
2. **Be conversational** - You don't need perfect prompts
3. **Iterate** - Start simple, refine as you go
4. **Ask questions** - There are no dumb questions
5. **Reference the roadmap** - Phases are designed to build on each other
6. **Track progress** - Update PHASE_TRACKER.md regularly
7. **Learn actively** - Don't just copy code, understand it

---

**Ready to start? Try this:**

```
"I want to begin my multi-agent learning journey.
Start with Phase 0 setup and guide me through it."
```

Happy building! 🚀
