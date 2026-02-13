#!/bin/bash
# Helper script to create next phase branch

set -e

CURRENT_BRANCH=$(git branch --show-current)

if [[ $CURRENT_BRANCH =~ learning/phase-([0-9]+) ]]; then
    CURRENT_PHASE=${BASH_REMATCH[1]}
    NEXT_PHASE=$((CURRENT_PHASE + 1))

    echo "🌳 Creating next phase branch"
    echo "================================"
    echo ""
    echo "Current: learning/phase-${CURRENT_PHASE}"
    echo "Next: learning/phase-${NEXT_PHASE}"
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
            git push origin "learning/phase-${CURRENT_PHASE}"
            echo "✓ Changes committed and pushed"
        else
            echo "❌ Aborting. Commit your changes first."
            exit 1
        fi
    fi

    # Create new branch
    echo ""
    echo "Creating learning/phase-${NEXT_PHASE}..."
    git checkout -b "learning/phase-${NEXT_PHASE}"

    # Push to remote
    echo "Pushing to remote..."
    git push -u origin "learning/phase-${NEXT_PHASE}"

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
