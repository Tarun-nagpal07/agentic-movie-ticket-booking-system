import sys
import socket
from pathlib import Path
from urllib.parse import urlparse

sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import settings

print("=========================================")
print("  CLOUD CONNECTION DIAGNOSTICS")
print("=========================================\n")

# 1. DNS Resolution Check
print("1. Testing DNS resolution:")
for name, url in [
    ("Supabase Host", settings.SUPABASE_DB_URL),
    ("Qdrant Host", settings.QDRANT_URL),
    ("Redis Host", settings.REDIS_URL),
]:
    if not url:
        print(f"  [SKIP] {name}: URL is empty")
        continue
    try:
        # Extract hostname
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            # Maybe it's a plain host or host:port
            host = url.split("://")[-1].split(":")[0].split("/")[0]
        
        print(f"  Resolving {name} hostname: '{host}'...")
        ip = socket.gethostbyname(host)
        print(f"  [OK]   {name} resolved to {ip}")
    except Exception as e:
        print(f"  [FAIL] {name} resolution failed: {e}")

# 2. Supabase / Postgres connection check
print("\n2. Testing PostgreSQL / Supabase connection:")
if settings.SUPABASE_DB_URL:
    try:
        import psycopg2
        print("  Connecting to PostgreSQL...")
        conn = psycopg2.connect(settings.SUPABASE_DB_URL)
        conn.close()
        print("  [OK]   PostgreSQL connection successful!")
    except Exception as e:
        print(f"  [FAIL] PostgreSQL connection failed: {e}")
else:
    print("  [SKIP] SUPABASE_DB_URL not set")

# 3. Redis Connection check
print("\n3. Testing Redis Cloud connection:")
if settings.REDIS_URL:
    try:
        import redis
        print("  Connecting to Redis...")
        r = redis.from_url(settings.REDIS_URL)
        ping = r.ping()
        print(f"  [OK]   Redis ping successful! Response: {ping}")
    except Exception as e:
        print(f"  [FAIL] Redis connection failed: {e}")
else:
    print("  [SKIP] REDIS_URL not set")

# 4. Qdrant Connection check
print("\n4. Testing Qdrant Cloud connection:")
if settings.QDRANT_URL:
    try:
        from qdrant_client import QdrantClient
        print("  Connecting to Qdrant...")
        api_key = settings.QDRANT_API_KEY or settings.QDRANT_API
        client = QdrantClient(url=settings.QDRANT_URL, api_key=api_key if api_key else None)
        collections = client.get_collections()
        names = [c.name for c in collections.collections]
        print(f"  [OK]   Qdrant connection successful! Collections found: {names}")
    except Exception as e:
        print(f"  [FAIL] Qdrant connection failed: {e}")
else:
    print("  [SKIP] QDRANT_URL not set")
