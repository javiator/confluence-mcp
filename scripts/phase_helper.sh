#!/bin/bash
# Helper script for phase management

case "$1" in
    "status")
        echo "Current Phase Status:"
        grep "Current Phase:" PHASE_TRACKER.md
        ;;
    "next")
        echo "What to work on next:"
        grep -A 5 "Next Session Goals" PHASE_TRACKER.md
        ;;
    "test")
        source venv-multiagent/bin/activate
        pytest tests/ -v
        ;;
    *)
        echo "Usage: ./scripts/phase_helper.sh {status|next|test}"
        ;;
esac
