import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

load_dotenv()

from src.confluence_mcp.server import search_confluence

# Test searches
print("=" * 80)
print("Testing search for 'docker'")
print("=" * 80)
results = search_confluence("docker")
print(f"\nFound {len(results)} results:")
for r in results:
    print(f" - {r['title']} (ID: {r['id']})")
    print(f"   URL: {r['url']}")

print("\n" + "=" * 80)
print("Testing search for 'google'")
print("=" * 80)
results = search_confluence("google")
print(f"\nFound {len(results)} results:")
for r in results:
    print(f" - {r['title']} (ID: {r['id']})")
    print(f"   URL: {r['url']}")
