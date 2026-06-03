from src.db.json_store import load_db
from src.config.constants import DBFile
from src.memory.long_term import save_user_memory, get_user_memory, redis_client
from src.utils.logger import get_logger

logger = get_logger(__name__)


def seed_users():
    """Load all users from users.json into Redis as long-term memory."""
    users_db = load_db(DBFile.USERS)
    users = users_db["users"]

    seeded = 0
    skipped = 0

    for user_id, user_data in users.items():
        # check if user already exists in Redis
        existing = get_user_memory(user_id)
        if existing:
            logger.info(f"user {user_id} already in Redis — skipping")
            skipped += 1
            continue

        save_user_memory(user_id, user_data)
        seeded += 1

    logger.info(f"seeding complete — {seeded} users added, {skipped} skipped")


def flush_users():
    """Remove all user keys from Redis. Use with caution."""
    users_db = load_db(DBFile.USERS)
    users = users_db["users"]

    for user_id in users:
        redis_client.delete(f"user:{user_id}")
        logger.info(f"deleted user:{user_id} from Redis")

    logger.info(f"flushed {len(users)} users from Redis")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--flush":
        flush_users()
        print("All user keys flushed from Redis.")
    else:
        seed_users()
        print("User data seeded to Redis.")

        # verify
        users_db = load_db(DBFile.USERS)
        for user_id in users_db["users"]:
            data = get_user_memory(user_id)
            if data:
                print(f"  ✓ user:{user_id} — {data['name']} ({data['city']})")
            else:
                print(f"  ✗ user:{user_id} — NOT FOUND")
