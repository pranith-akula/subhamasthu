import sys
import os
from pydantic import ValidationError

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings

def test_redis_url_validation():
    print("Testing Redis URL validation logic...")
    
    # 1. Plain redis URL (should remain unchanged)
    s1 = Settings(redis_url="redis://localhost:6379/0")
    print(f"Input: redis://localhost:6379/0 -> Output: {s1.redis_url}")
    assert s1.redis_url == "redis://localhost:6379/0"
    
    # 2. rediss URL without params (should append ?ssl_cert_reqs=none)
    s2 = Settings(redis_url="rediss://my-redis.railway.app:6379/0")
    print(f"Input: rediss://my-redis.railway.app:6379/0 -> Output: {s2.redis_url}")
    assert "ssl_cert_reqs=none" in s2.redis_url
    
    # 3. rediss URL with existing params (should append &ssl_cert_reqs=none)
    s3 = Settings(redis_url="rediss://u:p@host:6379/0?foo=bar")
    print(f"Input: rediss://u:p@host:6379/0?foo=bar -> Output: {s3.redis_url}")
    assert "foo=bar" in s3.redis_url
    assert "&ssl_cert_reqs=none" in s3.redis_url
    
    # 4. rediss URL already having it (should remain unchanged)
    s4 = Settings(redis_url="rediss://host:6379?ssl_cert_reqs=required")
    print(f"Input: rediss://host:6379?ssl_cert_reqs=required -> Output: {s4.redis_url}")
    assert s4.redis_url == "rediss://host:6379?ssl_cert_reqs=required"
    
    print("\nAll validation tests passed!")

if __name__ == "__main__":
    try:
        test_redis_url_validation()
    except Exception as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
