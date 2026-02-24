import boto3

def list_groups():
    client = boto3.client("logs", region_name="us-east-1")
    try:
        groups = client.describe_log_groups(logGroupNamePrefix="/aws/bedrock-agentcore/")
        for g in groups.get("logGroups", []):
            print(g["logGroupName"])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_groups()
