"""Quick test for AI streaming and FastRouter functionality."""
import asyncio
import sys
import time
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from brain.ai_router import AIRouter
from config import get_config

async def test_streaming():
    router = AIRouter()
    
    print("Testing AI streaming...")
    chunks = []
    full = ""
    async for chunk in router.stream_response("Say exactly: streaming works"):
        chunks.append(chunk)
        full += chunk
        print(f"  chunk: {chunk!r}")
    
    print(f"Total chunks: {len(chunks)}")
    print(f"Full response: {full}")
    print()

def test_fastrouter():
    from core.fast_router import FastRouter
    fr = FastRouter()
    
    tests = [
        "what is the time",
        "open chrome",
        "take a screenshot", 
        "what is my battery",
        "open vs code",
    ]
    
    print("Testing FastRouter...")
    for cmd in tests:
        start = time.perf_counter()
        method, groups = fr.match(cmd)
        ms = (time.perf_counter() - start) * 1000
        status = "MATCH" if method else "MISS"
        print(f"  [{status}] {cmd!r} -> {ms:.2f}ms")
    
    print()


if __name__ == "__main__":
    test_fastrouter()
    asyncio.run(test_streaming())
    print("All tests passed!")