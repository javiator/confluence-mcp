# AI Agent Guide for Confluence MCP Multi-Agent Project

Welcome! If you are an AI assistant (like Claude, Cursor, Copilot, or Antigravity) joining this workspace, please read this file first. 

This project is a **multi-phase learning journey** aimed at building a production-ready multi-agent Confluence system while experimenting with various AI frameworks (LangGraph, CrewAI, AWS Bedrock, etc.). 

To avoid confusion and ensure you are working on the right phase, follow these strict guidelines:

## 1. Determine the Current Phase
Your very first action should be to check the current phase of the project.
👉 **Always read `PHASE_TRACKER.md` first.** 
It contains the active phase, branch name, and progress status. Make sure your context aligns with the "Current Phase" defined there.

## 2. Understand the Progress and Goals
Do not guess the architecture or next steps. The full roadmap and summary of what is being built are documented.
👉 **Read `ROADMAP_SUMMARY.md`** for a quick overview of the 11-phase journey.
👉 **Read `ROADMAP.md`** for deeply detailed objectives of the specific phase you are assisting with.

## 3. Respect the Branching Strategy
We use a strict branch-per-phase strategy. We never build Phase 3 on the `main` branch, for example.
👉 **Read `GIT_BRANCHING_STRATEGY.md`** to understand the `claude/phase-{N}-{SESSION_ID}` naming convention.
👉 **Do not manually create phase branches.** Use the provided script: `./scripts/next-phase.sh` to transition between phases. It automatically handles commits, branching, and pushing.

## 4. Documentation Rules
- **Do not duplicate information.** When updating project status, only update `PHASE_TRACKER.md`. Do not create new tracker files.
- **Log learnings.** Phase specific notes are kept in `docs/PHASE{N}_NOTES.md`.
- **Blog driven.** Each phase results in a blog evolution post. The format and expectations are in `BLOG_TEMPLATE.md`.

## Summary of Core Files for Agents:
1. `PHASE_TRACKER.md` - Your source of truth for "Where are we right now?"
2. `ROADMAP.md` / `ROADMAP_SUMMARY.md` - "What are we building?"
3. `GIT_BRANCHING_STRATEGY.md` - "How do we manage versions?"
4. `src/confluence_mcp/agent/` - "Where does the agent code live?"

**Ready?** Check `PHASE_TRACKER.md` now and ask the user how you can help with the current phase!
