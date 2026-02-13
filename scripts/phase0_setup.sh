#!/bin/bash
# Phase 0: Foundation & Setup Script
# Run this to get started with your multi-agent learning journey

set -e  # Exit on error

echo "🚀 Phase 0: Foundation & Setup"
echo "================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Create learning branch
echo "📦 Step 1: Creating learning branch..."
git checkout -b learning/multi-agent-journey 2>/dev/null || git checkout learning/multi-agent-journey
echo -e "${GREEN}✓${NC} Branch created/switched to: learning/multi-agent-journey"
echo ""

# Step 2: Set up Python environment
echo "🐍 Step 2: Setting up Python environment..."
if [ ! -d "venv-multiagent" ]; then
    python3 -m venv venv-multiagent
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${YELLOW}ℹ${NC} Virtual environment already exists"
fi

# Activate venv
source venv-multiagent/bin/activate

# Install base dependencies
echo "📦 Installing base dependencies..."
pip install -q --upgrade pip
pip install -q -e .
echo -e "${GREEN}✓${NC} Base dependencies installed"
echo ""

# Step 3: Install framework dependencies
echo "🧪 Step 3: Installing framework dependencies..."
pip install -q \
    crewai \
    crewai-tools \
    boto3 \
    google-cloud-aiplatform \
    pytest \
    pytest-asyncio \
    redis \
    prometheus-client \
    opentelemetry-api \
    opentelemetry-sdk

echo -e "${GREEN}✓${NC} Framework dependencies installed"
echo ""

# Step 4: Create directory structure
echo "📁 Step 4: Creating directory structure..."
mkdir -p tests/
mkdir -p src/confluence_mcp/agent/agents/
mkdir -p src/confluence_mcp/agent/frameworks/
mkdir -p docs/tutorials/
mkdir -p examples/
mkdir -p benchmarks/

echo -e "${GREEN}✓${NC} Directory structure created"
echo ""

# Step 5: Create basic test file
echo "🧪 Step 5: Creating basic test structure..."
cat > tests/test_phase0.py << 'EOF'
"""
Phase 0: Foundation Tests
Test current capabilities to establish baseline
"""
import pytest
from src.confluence_mcp.server import search_confluence, get_confluence_page

def test_environment_setup():
    """Verify environment is set up correctly"""
    import sys
    assert sys.version_info >= (3, 10), "Python 3.10+ required"

def test_imports():
    """Verify all required imports work"""
    try:
        import fastmcp
        import langchain
        import langgraph
        import chainlit
        assert True
    except ImportError as e:
        pytest.fail(f"Missing dependency: {e}")

# Add more tests as you understand the codebase
EOF

echo -e "${GREEN}✓${NC} Test structure created"
echo ""

# Step 6: Create Phase 0 documentation
echo "📝 Step 6: Creating Phase 0 documentation..."
cat > docs/PHASE0_NOTES.md << 'EOF'
# Phase 0: Foundation & Audit - Notes

## Date Started: [FILL IN]

## Current State Audit

### What Works Now
- [ ] MCP Server runs successfully
- [ ] Can search Confluence
- [ ] Can create pages
- [ ] Can update pages
- [ ] Chainlit UI works
- [ ] LangGraph agent works

### Current Architecture
```
[Draw or describe current architecture after audit]
```

### Current Capabilities
1. **Search**: [How it works]
2. **CRUD**: [What operations are supported]
3. **Agent**: [What the current agent does]

### Pain Points / Areas for Improvement
1. [List things you notice could be better]
2. [Add more as you discover]

### Token Usage Baseline
- Simple search: X tokens
- Page creation: X tokens
- Agent workflow: X tokens

### Performance Baseline
- Search latency: Xs
- Page creation: Xs
- Agent response: Xs

## Key Learnings
- [Add insights as you audit]

## Questions
- [Add questions that come up]

## Next Steps
After completing Phase 0, proceed to Phase 1:
- [ ] Create specialized agents
- [ ] Implement supervisor pattern
- [ ] Add agent visualization
EOF

echo -e "${GREEN}✓${NC} Documentation template created"
echo ""

# Step 7: Run basic checks
echo "✅ Step 7: Running basic checks..."

echo "  Checking Python version..."
python --version

echo "  Checking pip packages..."
pip list | grep -E "(langchain|langgraph|chainlit|fastmcp)" || echo "  Some packages not found - run: pip install -e ."

echo ""

# Step 8: Create helper script
cat > scripts/phase_helper.sh << 'EOF'
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
EOF
chmod +x scripts/phase_helper.sh

# Final summary
echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║   ✓ Phase 0 Setup Complete!                   ║"
echo "╚════════════════════════════════════════════════╝"
echo ""
echo "📋 What was created:"
echo "  • Learning branch: learning/multi-agent-journey"
echo "  • Virtual environment: venv-multiagent"
echo "  • Test structure: tests/test_phase0.py"
echo "  • Documentation: docs/PHASE0_NOTES.md"
echo "  • Helper scripts: scripts/phase_helper.sh"
echo ""
echo "🎯 Next Steps:"
echo "  1. Activate environment: source venv-multiagent/bin/activate"
echo "  2. Run the MCP server: confluence-mcp"
echo "  3. Run the Chainlit UI: chainlit run src/confluence_mcp/agent/app.py"
echo "  4. Audit the codebase and fill in docs/PHASE0_NOTES.md"
echo "  5. Run tests: pytest tests/ -v"
echo ""
echo "💡 Tips:"
echo "  • Use 'scripts/phase_helper.sh status' to check progress"
echo "  • Update PHASE_TRACKER.md as you complete tasks"
echo "  • Ask Claude Code for help anytime!"
echo ""
echo "📚 Read ROADMAP.md for full details"
echo ""
