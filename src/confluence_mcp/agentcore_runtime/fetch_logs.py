import boto3
import time

def get_logs():
    client = boto3.client("logs", region_name="us-east-1")
    log_group = "/aws/bedrock-agentcore/runtimes/hosted_agent_t61xh-LRcuKXEkqy-DEFAULT"
    
    try:
        streams = client.describe_log_streams(
            logGroupName=log_group,
            orderBy="LastEventTime",
            descending=True,
            limit=5
        )
        
        for stream in streams.get("logStreams", []):
            print(f"\n--- Log Stream: {stream['logStreamName']} ---")
            events = client.get_log_events(
                logGroupName=log_group,
                logStreamName=stream["logStreamName"],
                limit=50
            )
            for event in events.get("events", []):
                print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(event['timestamp']/1000.0))} {event['message']}")
                
    except Exception as e:
        print(f"Error fetching logs: {e}")

if __name__ == "__main__":
    get_logs()
