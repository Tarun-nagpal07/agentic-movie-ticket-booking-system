import redis
import sys

urls = [
    "redis://:14382571@redis-13383.c56.east-us.azure.cloud.redislabs.com:13383",
    "rediss://:14382571@redis-13383.c56.east-us.azure.cloud.redislabs.com:13383",
    "redis://database-genai:14382571@redis-13383.c56.east-us.azure.cloud.redislabs.com:13383",
    "rediss://database-genai:14382571@redis-13383.c56.east-us.azure.cloud.redislabs.com:13383",
    "redis://default:14382571@redis-13383.c56.east-us.azure.cloud.redislabs.com:13383",
    "rediss://default:14382571@redis-13383.c56.east-us.azure.cloud.redislabs.com:13383"
]

for url in urls:
    print(f"\nTrying connection: {url.split('@')[0]}@...")
    try:
        r = redis.from_url(url)
        # Attempt to ping
        r.ping()
        print("✅ SUCCESS!")
        print(f"Working URL: {url}")
        sys.exit(0)
    except redis.exceptions.AuthenticationError as ae:
        print(f"❌ Authentication Error: {ae}")
    except redis.exceptions.ConnectionError as ce:
        print(f"❌ Connection Error (Network/SSL/Port): {ce}")
    except Exception as e:
        print(f"❌ Other Error: {e}")

print("\nAll connection attempts failed.")
sys.exit(1)
