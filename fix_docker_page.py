import boto3, json, uuid

lambda_client = boto3.client('lambda', region_name='us-east-1')
function_name = 'ConfluenceTools'

perfect_html = """
<h2>How to Install Docker on Ubuntu</h2>
<p>To perform a clean installation of Docker, first remove any conflicting or older versions.</p>
<ol>
<li>First, stop and remove all running containers:
<ac:structured-macro ac:name="code" ac:schema-version="1" ac:macro-id="macro-stop-containers">
  <ac:parameter ac:name="language">bash</ac:parameter>
  <ac:plain-text-body><![CDATA[docker stop $(docker ps -aq) && docker rm $(docker ps -aq)]]></ac:plain-text-body>
</ac:structured-macro>
</li>
<li>Uninstall Docker Engine, CLI, Containerd, and Docker Compose:
<ac:structured-macro ac:name="code" ac:schema-version="1" ac:macro-id="macro-uninstall">
  <ac:parameter ac:name="language">bash</ac:parameter>
  <ac:plain-text-body><![CDATA[sudo apt-get purge docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-ce-rootless-extras]]></ac:plain-text-body>
</ac:structured-macro>
</li>
<li>Remove all Docker data directories:
<ac:structured-macro ac:name="code" ac:schema-version="1" ac:macro-id="macro-remove-data">
  <ac:parameter ac:name="language">bash</ac:parameter>
  <ac:plain-text-body><![CDATA[sudo rm -rf /var/lib/docker
sudo rm -rf /var/lib/containerd]]></ac:plain-text-body>
</ac:structured-macro>
</li>
<li>Update the package list after removal:
<ac:structured-macro ac:name="code" ac:schema-version="1" ac:macro-id="macro-update">
  <ac:parameter ac:name="language">bash</ac:parameter>
  <ac:plain-text-body><![CDATA[sudo apt-get update]]></ac:plain-text-body>
</ac:structured-macro>
</li>
</ol>
<p>Note: These steps will completely remove Docker and its associated components from your system. Make sure to backup any important container data before proceeding with the uninstallation.</p>

<h2>Upgrading Docker</h2>
<p>To upgrade Docker on Ubuntu, follow these steps:</p>
<ol>
<li>Update package index:
<ac:structured-macro ac:name="code" ac:schema-version="1" ac:macro-id="macro-upgrade-1">
  <ac:parameter ac:name="language">bash</ac:parameter>
  <ac:plain-text-body><![CDATA[sudo apt-get update]]></ac:plain-text-body>
</ac:structured-macro>
</li>
<li>Install latest packages:
<ac:structured-macro ac:name="code" ac:schema-version="1" ac:macro-id="macro-upgrade-2">
  <ac:parameter ac:name="language">bash</ac:parameter>
  <ac:plain-text-body><![CDATA[sudo apt-get install docker-ce]]></ac:plain-text-body>
</ac:structured-macro>
</li>
</ol>
<p>After running these commands, you should see the upgraded version numbers for all Docker components.</p>
"""

payload = {
    'actionGroup': 'writer-actions',
    'function': 'update_confluence_page_full',
    'parameters': [
        {'name': 'page_id', 'value': '70090849'},
        {'name': 'body', 'value': perfect_html}
    ]
}

print("Invoking Lambda to update the page...")
response = lambda_client.invoke(
    FunctionName=function_name,
    InvocationType='RequestResponse',
    Payload=json.dumps(payload)
)
result = json.loads(response['Payload'].read().decode('utf-8'))
body_str = result.get('response', {}).get('functionResponse', {}).get('responseBody', {}).get('TEXT', {}).get('body', '{}')
print(body_str)
