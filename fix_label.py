import boto3, requests, json
ssm = boto3.client('ssm', region_name='us-east-1')
url = ssm.get_parameter(Name='/confluence/base_url', WithDecryption=True)['Parameter']['Value'].rstrip('/')
token = ssm.get_parameter(Name='/confluence/api_token', WithDecryption=True)['Parameter']['Value']
email = ssm.get_parameter(Name='/confluence/email')['Parameter']['Value']

page_id = '70090849'
headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
payload = [{'prefix': 'global', 'name': 'ai-managed'}]
r = requests.post(f'{url}/rest/api/content/{page_id}/label', auth=(email, token), json=payload, headers=headers)
print(r.status_code, r.text)
