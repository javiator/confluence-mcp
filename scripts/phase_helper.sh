#!/bin/bash
# Helper script for phase management

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

case "$1" in
    "status")
        echo "📊 Current Phase Status"
        echo "======================="
        echo ""

        # Current branch
        CURRENT_BRANCH=$(git branch --show-current)
        echo "Current branch: ${CURRENT_BRANCH}"

        # Extract phase number if on phase branch
        if [[ $CURRENT_BRANCH =~ learning/phase-([0-9]+) ]]; then
            PHASE=${BASH_REMATCH[1]}
            echo "Current phase: Phase ${PHASE}"
        fi

        echo ""
        echo "Uncommitted changes:"
        git status -s || echo "  None"

        echo ""
        echo "Recent commits:"
        git log --oneline -3

        echo ""
        echo "📋 From PHASE_TRACKER.md:"
        grep -A 1 "Current Phase:" PHASE_TRACKER.md 2>/dev/null || echo "  (Update PHASE_TRACKER.md)"
        ;;

    "next")
        echo "🎯 What to Work on Next"
        echo "======================="
        echo ""

        CURRENT_BRANCH=$(git branch --show-current)
        if [[ $CURRENT_BRANCH =~ learning/phase-([0-9]+) ]]; then
            PHASE=${BASH_REMATCH[1]}
            echo "Current: Phase ${PHASE}"
            echo ""
            echo "Check ROADMAP.md for Phase ${PHASE} objectives"
            echo ""
            echo "From PHASE_TRACKER.md:"
            grep -A 5 "Next Session Goals" PHASE_TRACKER.md 2>/dev/null || echo "  (Update PHASE_TRACKER.md)"
        else
            echo "Not on a phase branch. Run './scripts/phase0_setup.sh' to start."
        fi
        ;;

    "test")
        echo "🧪 Running Tests"
        echo "==============="
        echo ""
        source .venv/bin/activate 2>/dev/null || echo "Virtual environment not found"
        uv run pytest tests/ -v
        ;;

    "run")
        echo "🚀 Running Application"
        echo "===================="
        echo ""

        if [ -z "$2" ]; then
            echo "Specify what to run:"
            echo "  ./scripts/phase_helper.sh run mcp      - Run MCP server"
            echo "  ./scripts/phase_helper.sh run ui       - Run Chainlit UI"
            echo "  ./scripts/phase_helper.sh run api      - Run FastAPI (if implemented)"
        else
            source .venv/bin/activate 2>/dev/null || echo "Virtual environment not found"

            case "$2" in
                "mcp")
                    uv run confluence-mcp
                    ;;
                "ui")
                    uv run chainlit run src/confluence_mcp/agent/app.py -w
                    ;;
                "api")
                    uv run uvicorn src.confluence_mcp.api.main:app --reload
                    ;;
                *)
                    echo "Unknown target: $2"
                    ;;
            esac
        fi
        ;;

    "branch")
        echo "🌳 Branch Information"
        echo "===================="
        echo ""

        echo "All phase branches:"
        git branch | grep learning/phase || echo "  No phase branches found"

        echo ""
        echo "Current branch: $(git branch --show-current)"

        echo ""
        echo "To create next phase branch:"
        echo "  ./scripts/next-phase.sh"
        ;;

    "commit")
        echo "💾 Quick Commit"
        echo "=============="
        echo ""

        if [ -z "$2" ]; then
            echo "Usage: ./scripts/phase_helper.sh commit \"message\""
            echo ""
            echo "Example:"
            echo "  ./scripts/phase_helper.sh commit \"Implemented search agent\""
        else
            CURRENT_BRANCH=$(git branch --show-current)
            if [[ $CURRENT_BRANCH =~ learning/phase-([0-9]+) ]]; then
                PHASE=${BASH_REMATCH[1]}
                git add .
                git commit -m "Phase ${PHASE}: $2"
                git push origin "${CURRENT_BRANCH}"
                echo "✓ Committed and pushed to ${CURRENT_BRANCH}"
            else
                echo "Not on a phase branch"
            fi
        fi
        ;;

    "blog")
        echo "✍️  Blog Post Helper"
        echo "==================="
        echo ""

        CURRENT_BRANCH=$(git branch --show-current)
        if [[ $CURRENT_BRANCH =~ learning/phase-([0-9]+) ]]; then
            PHASE=${BASH_REMATCH[1]}
            echo "Current phase: ${PHASE}"
            echo ""
            echo "Blog post checklist:"
            echo "  [ ] Implementation complete"
            echo "  [ ] Code committed and pushed"
            echo "  [ ] Notes consolidated from docs/PHASE_${PHASE}_NOTES.md"
            echo "  [ ] Screenshots/diagrams created"
            echo "  [ ] Blog post drafted (see BLOG_TEMPLATE.md)"
            echo "  [ ] Technical review done"
            echo "  [ ] Published to architectureon.co.uk"
            echo "  [ ] Main project page updated"
            echo ""
            echo "See BLOG_TEMPLATE.md for detailed format"
        fi
        ;;

    "phase-complete")
        echo "✅ Mark Phase Complete"
        echo "====================="
        echo ""

        CURRENT_BRANCH=$(git branch --show-current)
        if [[ $CURRENT_BRANCH =~ learning/phase-([0-9]+) ]]; then
            PHASE=${BASH_REMATCH[1]}

            echo "Completing Phase ${PHASE}..."
            echo ""
            echo "Checklist:"
            echo "  [ ] All code implemented and tested"
            echo "  [ ] Blog post published"
            echo "  [ ] PHASE_TRACKER.md updated"
            echo "  [ ] All changes committed"
            echo ""
            read -p "Is everything complete? (y/n) " -n 1 -r
            echo ""

            if [[ $REPLY =~ ^[Yy]$ ]]; then
                echo ""
                echo "Creating final commit for Phase ${PHASE}..."
                read -p "Brief phase summary: " SUMMARY

                git add .
                git commit -m "$(cat <<EOF
Phase ${PHASE}: Complete ${SUMMARY}

Phase ${PHASE} deliverables:
- Implementation complete
- Tests passing
- Blog post published
- Documentation updated

Ready for Phase $((PHASE + 1))

https://claude.ai/code/session_XXXXX
EOF
)"
                git push origin "${CURRENT_BRANCH}"

                echo ""
                echo "✓ Phase ${PHASE} marked complete!"
                echo ""
                echo "Next: Create Phase $((PHASE + 1)) branch"
                echo "  ./scripts/next-phase.sh"
            else
                echo ""
                echo "Complete remaining tasks first"
            fi
        else
            echo "Not on a phase branch"
        fi
        ;;

    *)
        echo "📚 Phase Helper Commands"
        echo "======================="
        echo ""
        echo "Usage: ./scripts/phase_helper.sh <command>"
        echo ""
        echo "Commands:"
        echo "  status          - Show current phase and git status"
        echo "  next            - Show what to work on next"
        echo "  test            - Run test suite with uv"
        echo "  run <target>    - Run application (mcp|ui|api)"
        echo "  branch          - Show branch information"
        echo "  commit \"msg\"    - Quick commit with phase prefix"
        echo "  blog            - Blog post checklist"
        echo "  phase-complete  - Mark current phase as complete"
        echo ""
        echo "Examples:"
        echo "  ./scripts/phase_helper.sh status"
        echo "  ./scripts/phase_helper.sh run ui"
        echo "  ./scripts/phase_helper.sh commit \"Implement search agent\""
        echo "  ./scripts/phase_helper.sh phase-complete"
        echo ""
        ;;
esac
