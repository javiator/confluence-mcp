import boto3, json, re

lambda_client = boto3.client('lambda', region_name='us-east-1')
function_name = 'ConfluenceTools'

def invoke_lambda(action_group, function, params):
    payload = {
        'actionGroup': action_group,
        'function': function,
        'parameters': [{'name': k, 'value': v} for k, v in params.items()]
    }
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    result = json.loads(response['Payload'].read().decode('utf-8'))
    body_str = result.get('response', {}).get('functionResponse', {}).get('responseBody', {}).get('TEXT', {}).get('body', '{}')
    try:
        if body_str.startswith('Error'):
            return {"error": body_str}
        return json.loads(body_str)
    except:
        return {"raw": body_str}

print("Fetching page 70090849...")
res = invoke_lambda('writer-actions', 'prepare_confluence_page_merge_update', {'page_id': '70090849'})
content = res.get('raw', '')
if not content:
    print("Failed to get content")
    exit(1)

# The content comes back as "Page Preparation Data:\nTitle: ...\nVersion: ...\n\nCurrent Content:\n"
parts = content.split("Current Content:\n")
if len(parts) < 2:
    print("Error parsing:", content)
    exit(1)

body = parts[1]
print("--- ORIGINAL CONTENT ---")
print(body[:500])

# Fix Headers
body = re.sub(r'(?m)^###\s+(.*)$', r'<h3>\1</h3>', body)
body = re.sub(r'(?m)^##\s+(.*)$', r'<h2>\1</h2>', body)
body = re.sub(r'(?m)^#\s+(.*)$', r'<h1>\1</h1>', body)

# Fix empty macros or markdown code blocks
# If the agent wrote ```bash \n ... \n ```
def code_macro(match):
    code = match.group(1).strip()
    return f'<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">bash</ac:parameter><ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body></ac:structured-macro>'

body = re.sub(r'```bash\s*(.*?)\s*```', code_macro, body, flags=re.DOTALL)
body = re.sub(r'```\s*(.*?)\s*```', code_macro, body, flags=re.DOTALL)

# Ensure existing macros have CDATA if they lost it (without messing up valid ones)
# Wait, if they are already empty in Confluence, we can't recover the code.
# The user's screenshot had literally "1. First, stop and remove all running containers:"
# If the code block is empty in Confluence storage, it's unrecoverable from storage format.
# Let's write the repaired body to a file to inspect first before uploading.

with open('repaired_body.txt', 'w') as f:
    f.write(body)
print("Saved to repaired_body.txt")
