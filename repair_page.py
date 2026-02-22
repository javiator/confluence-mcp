#!/usr/bin/env python3
"""Direct page repair script - bypasses agents to fix corrupted Confluence XHTML."""
import boto3, requests, json, sys

ssm = boto3.client('ssm', region_name='us-east-1')
BASE_URL = ssm.get_parameter(Name='/confluence/base_url', WithDecryption=True)['Parameter']['Value'].rstrip('/')
EMAIL = ssm.get_parameter(Name='/confluence/email', WithDecryption=True)['Parameter']['Value']
TOKEN = ssm.get_parameter(Name='/confluence/api_token', WithDecryption=True)['Parameter']['Value']

PAGE_ID = sys.argv[1] if len(sys.argv) > 1 else "41123863"
auth = (EMAIL, TOKEN)
headers = {"Content-Type": "application/json", "Accept": "application/json"}

resp = requests.get(f"{BASE_URL}/rest/api/content/{PAGE_ID}", auth=auth, params={"expand": "version,title"}, headers=headers, timeout=15)
resp.raise_for_status()
data = resp.json()
version = data['version']['number']
title = data['title']
print(f"Title: {title}, Current version: {version}")

body = """<ac:structured-macro ac:name="info"><ac:rich-text-body>
  <p>This guide explains how to install Docker Engine, Docker CLI, and Docker Compose on Ubuntu 18.04 or later.</p>
</ac:rich-text-body></ac:structured-macro>

<h2>Prerequisites</h2>
<ul>
  <li>Ubuntu 18.04 or later</li>
  <li>Sudo (administrator) privileges</li>
</ul>

<h2>Installation Steps</h2>

<h3>Step 1: Update the package index</h3>
<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">bash</ac:parameter><ac:plain-text-body><![CDATA[sudo apt-get update]]></ac:plain-text-body></ac:structured-macro>

<h3>Step 2: Install HTTPS transport packages</h3>
<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">bash</ac:parameter><ac:plain-text-body><![CDATA[sudo apt-get install -y ca-certificates curl gnupg lsb-release]]></ac:plain-text-body></ac:structured-macro>

<h3>Step 3: Add Docker&apos;s official GPG key</h3>
<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">bash</ac:parameter><ac:plain-text-body><![CDATA[sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg]]></ac:plain-text-body></ac:structured-macro>

<h3>Step 4: Set up the repository</h3>
<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">bash</ac:parameter><ac:plain-text-body><![CDATA[echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null]]></ac:plain-text-body></ac:structured-macro>

<h3>Step 5: Install Docker Engine</h3>
<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">bash</ac:parameter><ac:plain-text-body><![CDATA[sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin]]></ac:plain-text-body></ac:structured-macro>

<h3>Step 6: Verify the installation</h3>
<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">bash</ac:parameter><ac:plain-text-body><![CDATA[sudo docker run hello-world]]></ac:plain-text-body></ac:structured-macro>

<ac:structured-macro ac:name="note"><ac:rich-text-body>
  <p>The <strong>hello-world</strong> container confirms Docker is installed and running correctly. You should see a <em>Hello from Docker!</em> confirmation message.</p>
</ac:rich-text-body></ac:structured-macro>"""

payload = {
    "id": PAGE_ID,
    "type": "page",
    "title": title,
    "version": {"number": version + 1},
    "body": {"storage": {"value": body, "representation": "storage"}}
}

r = requests.put(f"{BASE_URL}/rest/api/content/{PAGE_ID}", auth=auth, headers=headers, json=payload, timeout=15)
if r.status_code == 200:
    url = r.json().get('_links', {}).get('base', BASE_URL) + r.json().get('_links', {}).get('webui', '')
    print(f"SUCCESS! Page updated.")
    print(f"URL: {url}")
else:
    print(f"FAILED {r.status_code}: {r.text[:400]}")
