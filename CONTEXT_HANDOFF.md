# Confluence MAS - Phase 4.3 Status

## Project
`/home/javiator/work/projects/learning/confluence-mcp` — branch `claude/phase-4-ceArC`

A Multi-Agent System (MAS) using AWS Bedrock Agents + a Confluence MCP Server (runs as ECR container in AWS Lambda `ConfluenceMCPServer`). A second Lambda `ConfluenceTools` acts as a Bedrock action group handler that proxies calls to `ConfluenceMCPServer` as JSON-RPC.

---

## STATUS: RESOLVED ✅ (with known limitations)

### ✅ **Fixed Issues**

1. **Empty body bug** - Implemented server-side caching to avoid passing large XML between tool calls
   - `prepare_confluence_page_merge_update` now caches content server-side, returns minimal metadata
   - `update_confluence_page_full` retrieves cached content and merges automatically
   - Writer Agent no longer sends empty strings
   - See [server.py:544-562](src/confluence_mcp/server.py#L544-L562) and [server.py:356-367](src/confluence_mcp/server.py#L356-L367)

2. **Wiki markup support** - Added automatic conversion from Confluence Wiki Markup to XHTML
   - Converts `h1.` `h2.` headings, `{code:bash}...{code}` blocks, lists
   - Handles CDATA wrapping for code blocks: `<![CDATA[...]]>`
   - Unwraps agent-generated `<p>` tags around Wiki markup
   - See [server.py:108-181](src/confluence_mcp/server.py#L108-L181)

3. **Writer Agent configuration** - Updated to use Wiki Markup format
   - Instruction modified to specify Wiki format instead of XHTML
   - Prompt override with `maximumLength: 4096` managed via [fix_writer_orch_template.py](fix_writer_orch_template.py)
   - See [terraform/main.tf:223](terraform/main.tf#L223)

### ⚠️ **Known Limitations**

1. **Code blocks via Bedrock Agent** - CDATA content gets stripped when Writer Agent generates code blocks
   - **Root cause**: Bedrock's orchestration appears to escape/strip CDATA during agent→Lambda communication
   - **Evidence**: Direct Lambda calls with Wiki markup work perfectly (CDATA preserved)
   - **Workaround**: Use direct API calls or avoid code-heavy updates via agents for now
   - **Test**: Run `uv run python test_wiki_direct.py` to verify server-side conversion works

2. **append_confluence_page tool** - Exists but needs deployment verification
   - Tool implemented in [server.py:529](src/confluence_mcp/server.py#L529)
   - Included in terraform schema [main.tf:293-306](terraform/main.tf#L293-L306)
   - May need MCP server redeploy to register properly

### ✅ **Verified Working Flows**

- **Search**: Search Agent finds pages, returns URLs and summaries ✅
- **Read**: Retrieves page content successfully ✅
- **Create**: Creates new pages with proper parent/space validation ✅
- **Update (simple text)**: Text updates work via server-side merge ✅
- **Update (with code - direct)**: Wiki markup conversion works via direct Lambda calls ✅

---

## Key Implementation Details

### Server-Side Caching (The Fix)
```python
# In-memory cache at server.py:14
_prepared_pages_cache: Dict[str, Dict[str, Any]] = {}

# prepare stores content, returns metadata only
_prepared_pages_cache[page_id] = {...content...}
return {"status": "prepared", "page_id": page_id, ...}

# update retrieves and merges
cached_data = _prepared_pages_cache.get(page_id)
merged_body = existing_content + "\n" + new_content
```

### Wiki Markup Converter
```python
# Detects Wiki markup patterns
if re.match(r'^h[1-6]\.', line):  # h1. h2. headings
if line.startswith('{code'):      # {code:bash}...{code} blocks

# Generates proper XHTML with CDATA
<ac:structured-macro ac:name="code">
  <ac:parameter ac:name="language">bash</ac:parameter>
  <ac:plain-text-body><![CDATA[code here]]></ac:plain-text-body>
</ac:structured-macro>
```

---

## Agent Configuration

### Writer Agent (M1SKX5WXKI)
- **Instruction**: Uses Wiki Markup format (h1., {code}, etc.)
- **Prompt Override**: `maximumLength: 4096` for ORCHESTRATION (via boto3)
- **Tools**: `create_confluence_page`, `update_confluence_page_full`, `prepare_confluence_page_merge_update`, `append_confluence_page`

### Search Agent (HMUJPTSXHZ)
- **Tools**: `search_confluence`, `get_confluence_page`, `get_confluence_children`
- **Status**: Fully working ✅

### Reviewer Agent (CEXKSDYGIG)
- **Tools**: `get_confluence_page`
- **Purpose**: Quality validation

### Supervisor Agent (WRRZLA5LTA)
- **Collaborators**: Search, Writer, Reviewer
- **Status**: Orchestrates multi-agent workflows

---

## Key Files Modified

### Core Implementation
- [src/confluence_mcp/server.py](src/confluence_mcp/server.py) - Server-side caching, Wiki markup converter
- [terraform/main.tf](terraform/main.tf) - Writer Agent instruction updated for Wiki markup
- [fix_writer_orch_template.py](fix_writer_orch_template.py) - Script to set `maximumLength: 4096`

### Testing Scripts
- [test_writer_markup.py](test_writer_markup.py) - Test Writer Agent with XHTML
- [test_prepare_lambda.py](test_prepare_lambda.py) - Test prepare function output
- [test_wiki_direct.py](test_wiki_direct.py) - Verify Wiki→XHTML conversion works
- [test_update_with_cdata.py](test_update_with_cdata.py) - Test CDATA preservation

---

## Deployment Commands

### Deploy MCP Server Changes
```bash
cd /home/javiator/work/projects/learning/confluence-mcp

# Build and push Docker image
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 383226947124.dkr.ecr.us-east-1.amazonaws.com
docker build -t 383226947124.dkr.ecr.us-east-1.amazonaws.com/confluence-mcp-server:latest .
docker push 383226947124.dkr.ecr.us-east-1.amazonaws.com/confluence-mcp-server:latest

# Update Lambda
aws lambda update-function-code \
  --function-name ConfluenceMCPServer \
  --image-uri 383226947124.dkr.ecr.us-east-1.amazonaws.com/confluence-mcp-server:latest \
  --region us-east-1
```

### Update Writer Agent Configuration
```bash
# Apply terraform changes
cd terraform && terraform apply -auto-approve

# Prepare agent (required after any config change)
aws bedrock-agent prepare-agent --agent-id M1SKX5WXKI --region us-east-1

# Update prompt override (if needed)
uv run python fix_writer_orch_template.py
```

---

## Testing

### Test Search & Read
```bash
uv run python -c "
import boto3, uuid
client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
response = client.invoke_agent(
    agentId='HMUJPTSXHZ',
    agentAliasId='LRCPLKP7QR',
    sessionId=str(uuid.uuid4()),
    inputText='Search for Docker pages',
    enableTrace=False
)
for event in response.get('completion'):
    if 'chunk' in event: print(event['chunk']['bytes'].decode())
"
```

### Test Wiki Markup Conversion (Direct)
```bash
uv run python test_wiki_direct.py
```

### Test Writer Agent
```bash
uv run python test_writer_markup.py
```

---

## Agent IDs Reference

| Agent | ID | Alias | Status |
|---|---|---|---|
| Supervisor | `WRRZLA5LTA` | `TSTALIASID` | ✅ Working |
| Writer | `M1SKX5WXKI` | `XN7Q0IVSHR` | ⚠️ Working (except code blocks) |
| Search | `HMUJPTSXHZ` | `LRCPLKP7QR` | ✅ Working |
| Reviewer | `CEXKSDYGIG` | `XVRG1JV6YW` | ✅ Working |

---

## Recommendations for Production Use

### ✅ Safe to Use
- Search functionality (find pages, get metadata)
- Read page content
- Create new pages
- Simple text updates without code blocks

### ⚠️ Use with Caution
- Updates containing code blocks (CDATA may be stripped)
- Workaround: Use direct Lambda API calls instead of Bedrock Agents

### 🔧 Future Improvements
1. Investigate Bedrock Agent CDATA escaping behavior
2. Consider creating dedicated `add_code_section(page_id, heading, code, language)` tool
3. Verify `append_confluence_page` tool registration
4. Add integration tests for Wiki markup conversion
