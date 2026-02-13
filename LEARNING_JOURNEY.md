# Multi-Agent Confluence System - Learning Journey 🚀

> **Building a production-ready multi-agent system through hands-on framework experimentation**

**Status**: ⚪ Not Started | **Your Level**: Intermediate | **Timeline**: Flexible

---

## 📖 Documentation Index

### 🎯 Start Here
- **[ROADMAP_SUMMARY.md](./ROADMAP_SUMMARY.md)** ← **READ THIS FIRST**
  - Quick overview of all 11 phases
  - Timeline and deliverables
  - Success metrics

### 📋 Planning & Tracking
- **[ROADMAP.md](./ROADMAP.md)** - Detailed phase-by-phase plan
- **[PHASE_TRACKER.md](./PHASE_TRACKER.md)** - Track your progress
- **[BLOG_TEMPLATE.md](./BLOG_TEMPLATE.md)** - Blog post format & examples

### 🤝 Working with Claude Code
- **[CLAUDE_CODE_GUIDE.md](./CLAUDE_CODE_GUIDE.md)** - Effective prompts & collaboration tips
- **[LEARNING_SETUP.md](./LEARNING_SETUP.md)** - Setup instructions & daily workflow

### 🛠️ Scripts & Tools
- **[scripts/phase0_setup.sh](./scripts/phase0_setup.sh)** - Automated environment setup (uses uv)
- **[scripts/phase_helper.sh](./scripts/phase_helper.sh)** - Phase management utilities
- **[scripts/next-phase.sh](./scripts/next-phase.sh)** - Create next phase branch automatically
- **[GIT_BRANCHING_STRATEGY.md](./GIT_BRANCHING_STRATEGY.md)** - Git workflow and branching guide

---

## 🎯 The Mission

Build a **production-ready multi-agent Confluence system** while:
1. ✅ Learning 6 major frameworks hands-on
2. ✅ Comparing their strengths/weaknesses
3. ✅ Making informed architectural decisions
4. ✅ Documenting journey through blog posts
5. ✅ Creating a portfolio piece

---

## 🗺️ The Path

```
Phase 0: Foundation (Current State)
    ↓ Blog: Evolution 0
Phase 1: Multi-Agent Basics (LangGraph)
    ↓ Blog: Evolution 1
Phase 2: Memory & Intelligence
    ↓ Blog: Evolution 2
Phase 3-7: Framework Experiments
    ├─ CrewAI (Evolution 3)
    ├─ AWS Bedrock (Evolution 4)
    ├─ Azure AI Foundry (Evolution 5)
    ├─ Google Vertex AI (Evolution 6)
    └─ n8n Workflows (Evolution 7)
    ↓ Blog: 5 evolution posts
Phase 8: Framework Decision
    ↓ Blog: Evolution 8 (Comparison)
Phase 9: Production Build
    ↓ Blog: Evolution 9
Phase 10: Advanced Features
    ↓ Blog: Evolution 10
Phase 11: Polish & Launch
    ↓ Blog: Evolution 11

Result: Production System + 11-part Blog Series
```

---

## 📊 Frameworks You'll Master

| Framework | Type | Why Try It | Phase |
|-----------|------|------------|-------|
| **LangGraph** | Open Source | Maximum flexibility & control | 0-2 |
| **CrewAI** | Open Source | Role-based, easy to learn | 3 |
| **AWS Bedrock** | Managed Service | Cloud-native, enterprise-ready | 4 |
| **Azure AI Foundry** | Managed Service | Microsoft ecosystem integration | 5 |
| **Google Vertex AI** | Managed Service | GCP-native, Gemini models | 6 |
| **n8n** | Low-Code | Visual workflows, business user friendly | 7 |

By Phase 8, you'll know which fits YOUR needs best.

---

## ✍️ Blog Series (architectureon.co.uk Format)

Each phase produces an evolution blog post:

**Main Project Page**: Multi-Agent Confluence System
- Overview & tech stack
- All evolutions listed with status
- Architecture evolution diagrams
- Learning outcomes summary

**11 Evolution Posts**: Detailed implementation journey
- Evolution 0: Foundation & Baseline
- Evolution 1: Multi-Agent Orchestration
- Evolution 2: Intelligence & Memory
- Evolution 3: CrewAI Exploration
- Evolution 4: AWS Bedrock Agents
- Evolution 5: Azure AI Foundry
- Evolution 6: Google Vertex AI
- Evolution 7: n8n Workflows
- Evolution 8: Framework Selection
- Evolution 9: Production System
- Evolution 10: Advanced Features
- Evolution 11: Launch Ready

See [BLOG_TEMPLATE.md](./BLOG_TEMPLATE.md) for format details.

---

## 🛠️ Tech Stack & Tools

### Package Management: uv
All Python commands use **[uv](https://github.com/astral-sh/uv)** - the fast Python package installer:
- Faster than pip
- Better dependency resolution
- Consistent environments

```bash
# Run with uv
uv run confluence-mcp
uv run pytest tests/
uv run chainlit run src/confluence_mcp/agent/app.py
```

### Git Strategy: Phase Branches
Each phase gets its own branch:
```
learning/phase-0 → learning/phase-1 → learning/phase-2 → ...
```

Benefits:
- Progressive history
- Isolated experiments
- Blog alignment (branch = evolution)
- Easy comparison

See [GIT_BRANCHING_STRATEGY.md](./GIT_BRANCHING_STRATEGY.md) for details.

---

## 🚀 Quick Start (3 Steps)

### 1. Read the Plan (15 minutes)
```bash
# Read the summary first
cat ROADMAP_SUMMARY.md

# Then review detailed roadmap
cat ROADMAP.md
```

### 2. Set Up Environment (5 minutes)
```bash
# Installs uv, creates .venv, installs dependencies, creates learning/phase-0 branch
./scripts/phase0_setup.sh

# Activate environment
source .venv/bin/activate
```

### 3. Start Phase 0 (1-3 days)
Tell Claude Code:
```
"I've reviewed the roadmap. Start Phase 0 - help me audit the codebase
and establish baseline metrics for Evolution 0 blog post."
```

---

## 🎓 What You'll Gain

### Technical Skills
- ✅ **Multi-agent system design** - Supervisor patterns, agent specialization, orchestration
- ✅ **Framework expertise** - 6 frameworks, hands-on experience, production knowledge
- ✅ **Production deployment** - Scaling, monitoring, optimization, cloud deployment
- ✅ **Performance optimization** - RAG, caching, knowledge graphs, token efficiency

### Soft Skills
- ✅ **Technical writing** - 11 blog posts documenting your journey
- ✅ **Decision-making** - Framework selection based on real experience
- ✅ **Critical thinking** - Comparing trade-offs, evaluating options
- ✅ **Portfolio building** - Public learning journey, technical credibility

### Deliverables
- ✅ **Production system** - Fully functional, deployed, monitored
- ✅ **Blog series** - 11-part evolution series on architectureon.co.uk
- ✅ **GitHub repo** - Clean, documented, production-ready code
- ✅ **Framework comparison** - Authoritative comparison based on experience

---

## 📈 Success Indicators

### Week 2-3 (Phases 0-2)
- ✅ Multi-agent system running
- ✅ First 3 blog posts published
- ✅ Comfortable with LangGraph

### Week 4-8 (Phases 3-7)
- ✅ Tried all 6 frameworks
- ✅ 8 evolution posts published
- ✅ Strong opinions on each framework

### Week 9-12 (Phases 8-9)
- ✅ Framework decision made
- ✅ Production system built
- ✅ 10 evolution posts published

### Week 13-14 (Phases 10-11)
- ✅ Advanced features implemented
- ✅ System deployed & monitored
- ✅ Complete blog series published
- ✅ Can teach others confidently

---

## 💡 Your Advantages (Intermediate Level)

You already understand:
- ✅ Python, async/await, APIs
- ✅ LangChain/LangGraph basics
- ✅ Git, Docker, cloud services
- ✅ Software architecture patterns

This means:
- ⚡ **Faster pace** - Implement from objectives, not step-by-step
- 🔬 **More experimentation** - Try different approaches freely
- 🧠 **Critical thinking** - Question decisions, compare options
- 📝 **Better blog posts** - You can explain deeply

---

## 🎯 Key Principles

### 1. Learn by Doing
Don't just read about frameworks - build with them. Real experience > documentation.

### 2. Document as You Go
Blog posts force deep understanding. If you can teach it, you know it.

### 3. Compare Objectively
Fill out comparison matrix with REAL data, not opinions formed from reading docs.

### 4. Start Simple, Build Up
Each phase builds on the previous. Don't skip ahead.

### 5. Flexible Timeline
Go at your own pace. Quality > speed.

### 6. Ask Questions
Use Claude Code extensively. No question is too basic.

---

## 🔄 Daily Workflow

### Morning (5 min)
```bash
# Check status
./scripts/phase_helper.sh status

# Activate environment
source venv-multiagent/bin/activate
```

### During Work
- Reference ROADMAP.md for current phase
- Take notes in docs/PHASE_X_NOTES.md
- Use CLAUDE_CODE_GUIDE.md for effective prompts
- Update PHASE_TRACKER.md as you complete tasks

### End of Day (10 min)
```bash
# Commit progress
git add .
git commit -m "Phase X: [what you did]"
git push

# Update tracker
# Plan tomorrow
```

### End of Phase
- Write evolution blog post
- Publish to architectureon.co.uk
- Update main project page
- Move to next phase

---

## 📚 Resources

### Your Documentation
- [Roadmap Summary](./ROADMAP_SUMMARY.md)
- [Detailed Roadmap](./ROADMAP.md)
- [Progress Tracker](./PHASE_TRACKER.md)
- [Blog Template](./BLOG_TEMPLATE.md)
- [Claude Code Guide](./CLAUDE_CODE_GUIDE.md)

### Framework Documentation
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [CrewAI Docs](https://docs.crewai.com/)
- [AWS Bedrock Docs](https://docs.aws.amazon.com/bedrock/)
- [Azure AI Foundry](https://learn.microsoft.com/azure/ai-studio/)
- [Vertex AI Docs](https://cloud.google.com/vertex-ai/docs/)
- [n8n Docs](https://docs.n8n.io/)

### Learning Resources
- [LangGraph Tutorials](https://langchain-ai.github.io/langgraph/tutorials/)
- [CrewAI Examples](https://github.com/joaomdmoura/crewAI-examples)
- [AWS Bedrock Workshop](https://catalog.workshops.aws/bedrock/)
- [Azure AI Learning](https://learn.microsoft.com/training/paths/azure-ai-fundamentals/)

---

## 🆘 Getting Help

### From Claude Code
```
"I'm working on Phase X and need help with [specific task].
Context: [your situation]"
```

See [CLAUDE_CODE_GUIDE.md](./CLAUDE_CODE_GUIDE.md) for effective prompts.

### Community
- LangGraph Discord
- CrewAI Discussions
- AWS/Azure/GCP Forums
- n8n Community

### Your Blog Readers
- Once you publish evolutions, you'll get feedback
- Engage with comments and questions
- Learn from reader perspectives

---

## 🎉 Ready to Begin?

### Pre-Flight Checklist
- [ ] Read ROADMAP_SUMMARY.md
- [ ] Understand the 11-phase journey
- [ ] Review blog template format
- [ ] Run setup script
- [ ] Tell Claude Code you're ready

### Your First Command
```
"I've reviewed the complete learning journey documentation.
I'm ready to start Phase 0. Help me audit the codebase,
establish baseline metrics, and create my first blog post
(Evolution 0: Foundation & Baseline)."
```

---

## 📊 Project Stats (Will Track)

| Metric | Start | Current | End Goal |
|--------|-------|---------|----------|
| **Frameworks Tried** | 1 | ? | 6 |
| **Blog Posts Published** | 0 | ? | 11 |
| **Response Time** | 5-10s | ? | <3s |
| **Token Usage** | ~10k | ? | <2k |
| **Lines of Code** | ~500 | ? | ~3000 |
| **Production Ready** | No | ? | Yes |

---

## 🌟 The End Goal

By completion, you'll have:

1. **Production System**
   - Multi-agent architecture
   - Chosen framework implementation
   - Deployed and monitored
   - Scalable and maintainable

2. **Technical Portfolio**
   - 11-part blog series
   - Framework comparison article
   - Open-source GitHub repo
   - Demonstrated expertise

3. **Deep Knowledge**
   - Multi-agent design patterns
   - 6 framework hands-on experience
   - Production deployment skills
   - Performance optimization techniques

4. **Confidence**
   - Can build multi-agent systems independently
   - Can evaluate and choose frameworks
   - Can deploy to production
   - Can teach others

---

**Let's build something amazing and document the journey! 🚀**

---

**Next**: Read [ROADMAP_SUMMARY.md](./ROADMAP_SUMMARY.md) then run `./scripts/phase0_setup.sh`
