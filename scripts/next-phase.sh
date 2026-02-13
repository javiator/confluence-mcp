#!/bin/bash
# Helper script to create next phase branch

set -e

CURRENT_BRANCH=$(git branch --show-current)

# Extract session ID from current branch (format: claude/phase-N-SESSION_ID or claude/project-name-SESSION_ID)
if [[ $CURRENT_BRANCH =~ claude/phase-([0-9]+)-(.+)$ ]]; then
    CURRENT_PHASE=${BASH_REMATCH[1]}
    SESSION_ID=${BASH_REMATCH[2]}
    NEXT_PHASE=$((CURRENT_PHASE + 1))
elif [[ $CURRENT_BRANCH =~ claude/.+-(.+)$ ]]; then
    # First time - on project branch, starting phase 1
    CURRENT_PHASE=0
    SESSION_ID=${BASH_REMATCH[1]}
    NEXT_PHASE=1
else
    echo "❌ Error: Could not determine session ID from branch: ${CURRENT_BRANCH}"
    echo "Expected format: claude/phase-N-SESSION_ID or claude/project-name-SESSION_ID"
    exit 1
fi

echo "🌳 Creating next phase branch"
echo "================================"
echo ""
echo "Current: ${CURRENT_BRANCH} (Phase ${CURRENT_PHASE})"
echo "Next: claude/phase-${NEXT_PHASE}-${SESSION_ID}"
    echo ""

    # Check for uncommitted changes
    if [[ -n $(git status -s) ]]; then
        echo "⚠️  Warning: You have uncommitted changes"
        echo ""
        git status -s
        echo ""
        read -p "Commit these changes first? (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git add .
            read -p "Commit message: Phase ${CURRENT_PHASE}: " COMMIT_MSG
            git commit -m "Phase ${CURRENT_PHASE}: ${COMMIT_MSG}"
            git push origin "${CURRENT_BRANCH}"
            echo "✓ Changes committed and pushed"
        else
            echo "❌ Aborting. Commit your changes first."
            exit 1
        fi
    fi

    # Create new branch
    echo ""
    echo "Creating claude/phase-${NEXT_PHASE}-${SESSION_ID}..."
    git checkout -b "claude/phase-${NEXT_PHASE}-${SESSION_ID}"

    # Push to remote
    echo "Pushing to remote..."
    git push -u origin "claude/phase-${NEXT_PHASE}-${SESSION_ID}"

    echo ""
    echo "✅ Success!"
    echo ""
    echo "📋 Next steps:"
    echo "  1. Update PHASE_TRACKER.md with new phase"
    echo "  2. Read Phase ${NEXT_PHASE} objectives in ROADMAP.md"
    echo "  3. Start implementing Phase ${NEXT_PHASE}"
    echo ""

else
    echo "❌ Error: Not on a phase branch"
    echo "Current branch: ${CURRENT_BRANCH}"
    echo ""
    echo "Expected format: learning/phase-{N}"
    echo ""
    echo "Are you on the correct branch?"
    exit 1
fi
