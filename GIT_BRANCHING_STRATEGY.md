# Git Branching Strategy for Learning Journey

> Each phase gets its own branch, building progressively from the previous phase

---

## 🌳 Branching Model

```
main (production-ready code)
  │
  └─ learning/phase-0 (Foundation)
       │
       ├─ learning/phase-1 (First Multi-Agent)
       │    │
       │    └─ learning/phase-2 (Memory & Intelligence)
       │         │
       │         ├─ learning/phase-3 (CrewAI)
       │         │    │
       │         │    └─ learning/phase-4 (AWS Bedrock)
       │         │         │
       │         │         ├─ learning/phase-5 (Azure AI Foundry)
       │         │         │    │
       │         │         │    └─ learning/phase-6 (Google Vertex AI)
       │         │         │         │
       │         │         │         └─ learning/phase-7 (n8n)
       │         │         │              │
       │         │         │              └─ learning/phase-8 (Decision)
       │         │         │                   │
       │         │         │                   └─ learning/phase-9 (Production)
       │         │         │                        │
       │         │         │                        └─ learning/phase-10 (Advanced)
       │         │         │                             │
       │         │         │                             └─ learning/phase-11 (Polish)
       │         │         │                                  │
       │         │         │                                  └─ (merge to main)
```

---

## 📋 Branch Naming Convention

```
learning/phase-{N}
```

Where `{N}` is the phase number (0-11).

---

## 🔄 Workflow for Each Phase

### Starting a New Phase

```bash
# Example: Moving from Phase 0 to Phase 1

# 1. Ensure Phase 0 work is committed
git status
git add .
git commit -m "Phase 0: Complete foundation and baseline"

# 2. Push Phase 0 branch
git push -u origin learning/phase-0

# 3. Create Phase 1 branch FROM Phase 0
git checkout -b learning/phase-1

# 4. Push Phase 1 branch
git push -u origin learning/phase-1

# 5. Start working on Phase 1
```

### During a Phase

```bash
# Regular commits as you work
git add .
git commit -m "Phase 1: Implement search agent"

# Push regularly
git push origin learning/phase-1
```

### Completing a Phase

```bash
# 1. Final commit with summary
git add .
git commit -m "Phase 1: Complete multi-agent implementation

- Implemented SearchAgent, WriterAgent, ReviewerAgent
- Added supervisor pattern
- Enhanced Chainlit UI with agent visualization
- Published Evolution 1 blog post

https://claude.ai/code/session_XXXXX"

# 2. Push final changes
git push origin learning/phase-1

# 3. Create next phase branch
git checkout -b learning/phase-2

# 4. Push new branch
git push -u origin learning/phase-2
```

---

## 📝 Commit Message Format

### Regular Commits
```
Phase {N}: {Brief description}

Optional: More details
```

### Phase Completion Commits
```
Phase {N}: Complete {phase name}

- Deliverable 1
- Deliverable 2
- Deliverable 3
- Published Evolution {N} blog post

https://claude.ai/code/session_XXXXX
```

---

## 🎯 Benefits of This Approach

### 1. **Progressive History**
- Each branch builds on the previous
- Can see evolution of code through branches
- Easy to compare phases

### 2. **Isolation**
- Experiments in one phase don't affect others
- Can try different approaches
- Easy to abandon failed experiments

### 3. **Documentation**
- Branch history tells the story
- Each branch corresponds to blog evolution
- Clear checkpoints

### 4. **Flexibility**
- Can go back to previous phase
- Can create multiple attempts (phase-3-attempt-2)
- Can merge selected features forward

### 5. **Blog Alignment**
- Branch = Evolution post
- Code in branch matches blog content
- Readers can explore specific evolution

---

## 🔀 Special Scenarios

### Returning to Previous Phase

```bash
# Want to review Phase 3 implementation
git checkout learning/phase-3

# Make changes
git commit -m "Phase 3: Fix bug in CrewAI implementation"
git push origin learning/phase-3

# Merge fix forward if needed
git checkout learning/phase-4
git merge learning/phase-3
```

### Experimenting with Alternatives

```bash
# Try alternative approach in Phase 5
git checkout learning/phase-5
git checkout -b learning/phase-5-alternative

# Experiment...
# If successful, rename or merge
# If not, just delete branch
```

### Merging to Main (Final)

```bash
# After Phase 11 is complete and polished

# 1. Create PR from learning/phase-11 to main
gh pr create --base main --head learning/phase-11 \
  --title "Multi-Agent System: Complete Implementation" \
  --body "$(cat <<EOF
# Multi-Agent Confluence System

Complete implementation after 11 phases of learning and experimentation.

## What's Included
- Production-ready multi-agent system
- Chosen framework: [Framework Name]
- Complete documentation
- Test suite
- Deployment configuration

## Blog Series
- 11 evolution posts published
- Complete learning journey documented

## Framework Comparison
- Tested 6 frameworks hands-on
- Detailed comparison available

See LEARNING_JOURNEY.md for complete details.
EOF
)"

# 2. Review and merge
```

---

## 🛠️ Helper Commands

### Quick Phase Switch
```bash
# Save as alias in ~/.bashrc or ~/.zshrc
alias phase="git checkout learning/phase-"

# Usage:
phase 3  # switches to learning/phase-3
```

### View All Phase Branches
```bash
git branch | grep learning/phase
```

### See Phase Progress
```bash
# List all phase branches with last commit
git for-each-ref --sort=-committerdate refs/heads/learning/phase-* \
  --format='%(refname:short) - %(subject) (%(committerdate:relative))'
```

### Create Next Phase Branch
```bash
#!/bin/bash
# Save as scripts/next-phase.sh

CURRENT_BRANCH=$(git branch --show-current)
if [[ $CURRENT_BRANCH =~ learning/phase-([0-9]+) ]]; then
    CURRENT_PHASE=${BASH_REMATCH[1]}
    NEXT_PHASE=$((CURRENT_PHASE + 1))

    echo "Creating learning/phase-${NEXT_PHASE} from ${CURRENT_BRANCH}"

    git checkout -b "learning/phase-${NEXT_PHASE}"
    git push -u origin "learning/phase-${NEXT_PHASE}"

    echo "✓ Created and pushed learning/phase-${NEXT_PHASE}"
else
    echo "Error: Not on a phase branch"
fi
```

---

## 📊 Branch Status Tracking

Update in PHASE_TRACKER.md:

```markdown
## Branch Status

| Phase | Branch | Status | Last Commit | Blog Post |
|-------|--------|--------|-------------|-----------|
| 0 | learning/phase-0 | ✅ Complete | 2 days ago | Published |
| 1 | learning/phase-1 | 🟡 In Progress | 1 hour ago | Draft |
| 2 | learning/phase-2 | ⚪ Not Started | - | - |
| 3 | learning/phase-3 | ⚪ Not Started | - | - |
| ... | ... | ... | ... | ... |
```

---

## ⚠️ Important Notes

### DO:
- ✅ Always branch from the previous phase
- ✅ Push branches regularly
- ✅ Write descriptive commit messages
- ✅ Complete one phase before starting next
- ✅ Tag major milestones

### DON'T:
- ❌ Branch from main for later phases
- ❌ Merge phases back to earlier phases (unless fixing bugs)
- ❌ Skip phase branches
- ❌ Force push (use --force-with-lease if absolutely needed)
- ❌ Delete phase branches (they're your history)

---

## 🎯 Example: Complete Phase Workflow

```bash
# ===== PHASE 0 =====
git checkout -b learning/phase-0
# Work on Phase 0...
git add . && git commit -m "Phase 0: Complete foundation"
git push -u origin learning/phase-0
# Write blog post...

# ===== PHASE 1 =====
git checkout -b learning/phase-1
# Work on Phase 1...
git add . && git commit -m "Phase 1: Implement multi-agent"
git push -u origin learning/phase-1
# Write blog post...

# ===== PHASE 2 =====
git checkout -b learning/phase-2
# Work on Phase 2...
git add . && git commit -m "Phase 2: Add memory system"
git push -u origin learning/phase-2
# Write blog post...

# Continue pattern for all phases...

# ===== PHASE 11 (FINAL) =====
git checkout -b learning/phase-11
# Polish everything...
git add . && git commit -m "Phase 11: Production ready"
git push -u origin learning/phase-11
# Write final blog post...

# Create PR to main
gh pr create --base main --head learning/phase-11
```

---

## 🚀 Using with Claude Code

When working with Claude Code, always mention your current phase:

```
"I'm on learning/phase-3 (CrewAI). Help me implement..."
```

Claude Code can:
- Check which branch you're on
- Help you commit and push
- Create next phase branch
- Merge changes if needed

---

**Key Principle**: Each phase branch is a checkpoint in your learning journey. Keep them all - they tell your story!
