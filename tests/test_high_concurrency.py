#!/usr/bin/env python3
"""Test high concurrency limits for Bright Data SERP API."""

import asyncio
import aiohttp
import time

BRIGHT_DATA_API_KEY = "c69f9a87-ded2-4064-a901-5439af92bb54"
BRIGHT_DATA_ZONE = "serp_api1"
API_BASE_URL = "https://api.brightdata.com"


async def make_request(session, query, rid):
    start = time.time()
    headers = {
        "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "zone": BRIGHT_DATA_ZONE,
        "url": f"https://www.google.com/search?q={query}&gl=us&hl=en&brd_json=1",
        "format": "raw"
    }

    try:
        async with session.post(
            f"{API_BASE_URL}/serp/req",
            headers=headers,
            json=body,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as r:
            data = await r.json()
            response_id = data.get("response_id")
            if not response_id:
                return {"id": rid, "status": "no_id"}

        for _ in range(20):
            await asyncio.sleep(2)
            async with session.get(
                f"{API_BASE_URL}/serp/get_result",
                headers=headers,
                params={"response_id": response_id},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as pr:
                if pr.status == 200:
                    return {"id": rid, "status": "ok", "time": round(time.time() - start, 2)}
                elif pr.status not in [102, 202]:
                    return {"id": rid, "status": f"http_{pr.status}"}
        return {"id": rid, "status": "timeout"}
    except Exception as e:
        return {"id": rid, "status": "error", "msg": str(e)[:50]}


async def test_high_concurrency(n):
    print(f"Testing {n} concurrent requests...")
    start = time.time()
    async with aiohttp.ClientSession() as session:
        tasks = [make_request(session, f"test{i}", i) for i in range(n)]
        results = await asyncio.gather(*tasks)
    wall = time.time() - start
    ok = len([r for r in results if r["status"] == "ok"])
    failed = [r for r in results if r["status"] != "ok"]
    print(f"  Success: {ok}/{n} | Wall time: {wall:.1f}s | Throughput: {ok/wall:.2f} req/s")
    if failed:
        print(f"  Failed: {len(failed)} requests")
        # Show first few failures
        for f in failed[:3]:
            print(f"    - {f}")
    return ok, n, wall


async def main():
    print("HIGH CONCURRENCY TEST")
    print("=" * 50)
    for n in [100, 150, 200]:
        await test_high_concurrency(n)
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
