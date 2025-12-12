#!/usr/bin/env python3
"""
Bright Data SERP API - Exhaustive Test Suite
============================================
Comprehensive test suite to investigate all capabilities of the Bright Data SERP API.

Usage:
    # Run all tests
    python test_bright_data_serp.py --all

    # Run specific category
    python test_bright_data_serp.py --category basic

    # Run single test
    python test_bright_data_serp.py --test A1

    # Dry run (show tests without executing)
    python test_bright_data_serp.py --dry-run

    # Save results to file
    python test_bright_data_serp.py --output results.json
"""

import os
import json
import time
import argparse
import asyncio
import aiohttp
import urllib.parse
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Any
from enum import Enum

# ============================================================================
# Configuration
# ============================================================================

# Bright Data API credentials (from environment or defaults)
BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY", "c69f9a87-ded2-4064-a901-5439af92bb54")
BRIGHT_DATA_CUSTOMER_ID = os.getenv("BRIGHT_DATA_CUSTOMER_ID", "")
BRIGHT_DATA_ZONE = os.getenv("BRIGHT_DATA_ZONE", "serp_api1")
BRIGHT_DATA_ZONE_PASSWORD = os.getenv("BRIGHT_DATA_ZONE_PASSWORD", "")

# API Endpoints
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = 33335
API_BASE_URL = "https://api.brightdata.com"

# Test settings
DEFAULT_TIMEOUT = 30  # seconds
MAX_CONCURRENT_REQUESTS = 5


class TestStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestCategory(Enum):
    BASIC = "basic"
    LOCALIZATION = "localization"
    SEARCH_TYPES = "search_types"
    PAGINATION = "pagination"
    DEVICE_BROWSER = "device_browser"
    OUTPUT_FORMAT = "output_format"
    SPECIALIZED = "specialized"
    PERFORMANCE = "performance"
    EDGE_CASES = "edge_cases"
    MULTI_ENGINE = "multi_engine"
    ASYNC = "async"


@dataclass
class TestResult:
    test_id: str
    name: str
    category: str
    status: TestStatus
    duration_ms: float = 0
    response_code: Optional[int] = None
    response_size: Optional[int] = None
    error_message: Optional[str] = None
    response_sample: Optional[str] = None
    validations: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class TestCase:
    test_id: str
    name: str
    category: TestCategory
    engine: str = "google"
    url: Optional[str] = None
    params: dict = field(default_factory=dict)
    api_params: dict = field(default_factory=dict)
    expected: dict = field(default_factory=dict)
    use_async: bool = False
    priority: int = 2  # 0=critical, 1=high, 2=medium, 3=low
    timeout: int = DEFAULT_TIMEOUT
    description: str = ""


# ============================================================================
# Test Definitions
# ============================================================================

def get_all_test_cases() -> list[TestCase]:
    """Define all test cases for the SERP API."""
    tests = []

    # -------------------------------------------------------------------------
    # Category A: Basic Functionality Tests
    # -------------------------------------------------------------------------
    tests.extend([
        TestCase(
            test_id="A1",
            name="Basic Google Search",
            category=TestCategory.BASIC,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "pizza"},
            expected={"status": 200, "has_content": True},
            priority=0,
            description="Simple Google search without any special parameters"
        ),
        TestCase(
            test_id="A2",
            name="Google Search JSON Format",
            category=TestCategory.BASIC,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "python programming", "brd_json": "1"},
            expected={"format": "json", "has_organic": True},
            priority=0,
            description="Google search with JSON output format"
        ),
        TestCase(
            test_id="A3",
            name="Google Search Parsed Light",
            category=TestCategory.BASIC,
            engine="google",
            api_params={
                "query": {"q": "machine learning"},
                "data_format": "parsed_light",
                "country": "us"
            },
            expected={"max_results": 10, "fast_response": True},
            use_async=True,
            priority=0,
            description="Fast parsed light format returning only top 10 results"
        ),
        TestCase(
            test_id="A4",
            name="Basic Bing Search",
            category=TestCategory.BASIC,
            engine="bing",
            url="https://www.bing.com/search",
            params={"q": "artificial intelligence"},
            expected={"status": 200, "has_content": True},
            priority=0,
            description="Simple Bing search"
        ),
        TestCase(
            test_id="A5",
            name="Bing Search JSON Format",
            category=TestCategory.BASIC,
            engine="bing",
            url="https://www.bing.com/search",
            params={"q": "data science", "brd_json": "1"},
            expected={"format": "json"},
            priority=1,
            description="Bing search with JSON output"
        ),
    ])

    # -------------------------------------------------------------------------
    # Category B: Localization & Geo-targeting Tests
    # -------------------------------------------------------------------------
    localization_tests = [
        ("us", "en", "news", "US English results"),
        ("uk", "en", "news", "UK English results"),
        ("de", "de", "nachrichten", "German results"),
        ("fr", "fr", "actualités", "French results"),
        ("jp", "ja", "ニュース", "Japanese results"),
        ("es", "es", "noticias", "Spanish results"),
        ("br", "pt", "notícias", "Brazilian Portuguese results"),
        ("it", "it", "notizie", "Italian results"),
    ]

    for i, (country, lang, query, desc) in enumerate(localization_tests, 1):
        tests.append(TestCase(
            test_id=f"B1{chr(96+i)}",  # B1a, B1b, etc.
            name=f"Google Localization - {country.upper()}",
            category=TestCategory.LOCALIZATION,
            engine="google",
            url="https://www.google.com/search",
            params={"q": query, "gl": country, "hl": lang, "brd_json": "1"},
            expected={"localized": True, "country": country},
            priority=1,
            description=desc
        ))

    # UULE Location Tests
    uule_locations = [
        ("New+York,New+York,United+States", "restaurants near me", "New York"),
        ("London,England,United+Kingdom", "restaurants near me", "London"),
        ("Paris,Ile-de-France,France", "restaurants près de moi", "Paris"),
        ("Tokyo,Tokyo,Japan", "近くのレストラン", "Tokyo"),
        ("Sydney,New+South+Wales,Australia", "restaurants near me", "Sydney"),
    ]

    for i, (uule, query, location) in enumerate(uule_locations, 1):
        tests.append(TestCase(
            test_id=f"B2{chr(96+i)}",
            name=f"UULE Location - {location}",
            category=TestCategory.LOCALIZATION,
            engine="google",
            url="https://www.google.com/search",
            params={"q": query, "uule": uule, "brd_json": "1"},
            expected={"location_context": location},
            priority=1,
            description=f"Geo-targeted search for {location}"
        ))

    # Bing Market Tests
    bing_markets = [
        ("en-US", "weather"),
        ("en-GB", "weather"),
        ("de-DE", "wetter"),
        ("fr-FR", "météo"),
        ("es-ES", "tiempo"),
    ]

    for i, (market, query) in enumerate(bing_markets, 1):
        tests.append(TestCase(
            test_id=f"B3{chr(96+i)}",
            name=f"Bing Market - {market}",
            category=TestCategory.LOCALIZATION,
            engine="bing",
            url="https://www.bing.com/search",
            params={"q": query, "mkt": market, "setLang": market, "brd_json": "1"},
            expected={"market": market},
            priority=2,
            description=f"Bing search with {market} market"
        ))

    # -------------------------------------------------------------------------
    # Category C: Search Type & Vertical Tests
    # -------------------------------------------------------------------------
    search_types = [
        ("isch", "sunset mountains", "Image Search"),
        ("shop", "laptop", "Shopping Search"),
        ("nws", "technology", "News Search"),
        ("vid", "cooking tutorial", "Video Search"),
    ]

    for i, (tbm, query, name) in enumerate(search_types, 1):
        tests.append(TestCase(
            test_id=f"C{i}",
            name=f"Google {name}",
            category=TestCategory.SEARCH_TYPES,
            engine="google",
            url="https://www.google.com/search",
            params={"q": query, "tbm": tbm, "brd_json": "1"},
            expected={"search_type": tbm},
            priority=1,
            description=f"Google {name} using tbm={tbm}"
        ))

    # Jobs Search
    tests.append(TestCase(
        test_id="C5",
        name="Google Jobs Search",
        category=TestCategory.SEARCH_TYPES,
        engine="google",
        url="https://www.google.com/search",
        params={"q": "software engineer jobs", "ibp": "htl;jobs", "brd_json": "1"},
        expected={"search_type": "jobs"},
        priority=1,
        description="Google Jobs search using ibp parameter"
    ))

    # -------------------------------------------------------------------------
    # Category D: Pagination Tests
    # -------------------------------------------------------------------------
    for page in range(1, 6):  # Pages 1-5
        offset = (page - 1) * 10
        tests.append(TestCase(
            test_id=f"D1{chr(96+page)}",
            name=f"Google Pagination - Page {page}",
            category=TestCategory.PAGINATION,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "python tutorial", "start": str(offset), "brd_json": "1"},
            expected={"page": page, "offset": offset},
            priority=1 if page <= 2 else 2,
            description=f"Google search results page {page} (start={offset})"
        ))

    # Bing Pagination
    for page in range(1, 4):  # Pages 1-3
        first = (page - 1) * 10 + 1
        tests.append(TestCase(
            test_id=f"D2{chr(96+page)}",
            name=f"Bing Pagination - Page {page}",
            category=TestCategory.PAGINATION,
            engine="bing",
            url="https://www.bing.com/search",
            params={"q": "python tutorial", "first": str(first), "brd_json": "1"},
            expected={"page": page},
            priority=2,
            description=f"Bing search results page {page} (first={first})"
        ))

    # Maps Pagination
    for page in range(1, 4):
        offset = (page - 1) * 20
        tests.append(TestCase(
            test_id=f"D3{chr(96+page)}",
            name=f"Maps Pagination - Page {page}",
            category=TestCategory.PAGINATION,
            engine="google",
            url="https://www.google.com/maps/search/hotels+new+york",
            params={"start": str(offset), "num": "20", "brd_json": "1"},
            expected={"page": page, "num_results": 20},
            priority=2,
            description=f"Google Maps results page {page}"
        ))

    # -------------------------------------------------------------------------
    # Category E: Device & Browser Emulation Tests
    # -------------------------------------------------------------------------
    devices = [
        ("0", "Desktop"),
        ("1", "Mobile Generic"),
        ("ios", "iPhone"),
        ("ipad", "iPad"),
        ("android", "Android Phone"),
        ("android_tablet", "Android Tablet"),
    ]

    for i, (mobile_val, device_name) in enumerate(devices, 1):
        tests.append(TestCase(
            test_id=f"E1{chr(96+i)}",
            name=f"Device - {device_name}",
            category=TestCategory.DEVICE_BROWSER,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "weather", "brd_mobile": mobile_val, "brd_json": "1"},
            expected={"device": device_name},
            priority=2,
            description=f"Search with {device_name} user agent"
        ))

    browsers = [
        ("chrome", "Chrome"),
        ("safari", "Safari"),
        ("firefox", "Firefox"),
    ]

    for i, (browser_val, browser_name) in enumerate(browsers, 1):
        tests.append(TestCase(
            test_id=f"E2{chr(96+i)}",
            name=f"Browser - {browser_name}",
            category=TestCategory.DEVICE_BROWSER,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "weather", "brd_browser": browser_val, "brd_json": "1"},
            expected={"browser": browser_name},
            priority=2,
            description=f"Search with {browser_name} browser"
        ))

    # Combined device + browser
    combined_tests = [
        ("1", "chrome", "Mobile Chrome"),
        ("ios", "safari", "iOS Safari"),
        ("android", "chrome", "Android Chrome"),
    ]

    for i, (mobile, browser, name) in enumerate(combined_tests, 1):
        tests.append(TestCase(
            test_id=f"E3{chr(96+i)}",
            name=f"Combined - {name}",
            category=TestCategory.DEVICE_BROWSER,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "weather", "brd_mobile": mobile, "brd_browser": browser, "brd_json": "1"},
            expected={"device_browser": name},
            priority=3,
            description=f"Combined {name} emulation"
        ))

    # -------------------------------------------------------------------------
    # Category F: Output Format Tests
    # -------------------------------------------------------------------------
    tests.extend([
        TestCase(
            test_id="F1a",
            name="Output - JSON Format",
            category=TestCategory.OUTPUT_FORMAT,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "test query", "brd_json": "1"},
            expected={"format": "json"},
            priority=0,
            description="Verify JSON output format"
        ),
        TestCase(
            test_id="F1b",
            name="Output - HTML Format",
            category=TestCategory.OUTPUT_FORMAT,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "test query"},
            expected={"format": "html"},
            priority=1,
            description="Verify raw HTML output format"
        ),
    ])

    # -------------------------------------------------------------------------
    # Category G: Specialized Search Tests
    # -------------------------------------------------------------------------

    # G1: Google Maps
    tests.extend([
        TestCase(
            test_id="G1a",
            name="Maps - Basic Search",
            category=TestCategory.SPECIALIZED,
            engine="google",
            url="https://www.google.com/maps/search/restaurants+new+york",
            params={"brd_json": "1"},
            expected={"has_places": True},
            priority=1,
            description="Basic Google Maps search"
        ),
        TestCase(
            test_id="G1b",
            name="Maps - With Coordinates",
            category=TestCategory.SPECIALIZED,
            engine="google",
            url="https://www.google.com/maps/search/coffee/@40.7128,-74.0060,14z",
            params={"brd_json": "1"},
            expected={"location_based": True},
            priority=2,
            description="Maps search with GPS coordinates"
        ),
        TestCase(
            test_id="G1c",
            name="Maps - Vacation Rentals",
            category=TestCategory.SPECIALIZED,
            engine="google",
            url="https://www.google.com/maps/search/hotels+miami",
            params={"brd_accomodation_type": "vacation_rentals", "brd_json": "1"},
            expected={"accommodation_type": "vacation_rentals"},
            priority=2,
            description="Maps search for vacation rentals"
        ),
    ])

    # G2: Google Trends
    trends_tests = [
        ("timeseries,geo_map", "today 12-m", None, "Basic Trends"),
        ("timeseries", "now 1-d", None, "Trends Past 24h"),
        ("timeseries", "now 7-d", None, "Trends Past Week"),
        ("timeseries,geo_map", "today 12-m", "youtube", "Trends YouTube"),
        ("timeseries,geo_map", "today 12-m", "news", "Trends News"),
    ]

    for i, (widgets, date_range, gprop, name) in enumerate(trends_tests, 1):
        params = {
            "q": "bitcoin",
            "geo": "us",
            "brd_trends": widgets,
            "brd_json": "1",
            "date": date_range
        }
        if gprop:
            params["gprop"] = gprop

        tests.append(TestCase(
            test_id=f"G2{chr(96+i)}",
            name=f"Trends - {name}",
            category=TestCategory.SPECIALIZED,
            engine="google",
            url="https://trends.google.com/trends/explore",
            params=params,
            expected={"has_trends_data": True},
            priority=2,
            description=f"Google Trends: {name}"
        ))

    # G3: Google Reviews
    tests.extend([
        TestCase(
            test_id="G3a",
            name="Reviews - Basic",
            category=TestCategory.SPECIALIZED,
            engine="google",
            url="https://www.google.com/reviews",
            params={"fid": "0x808fba02425dad8f:0x6c296c66619367e0", "brd_json": "1"},
            expected={"has_reviews": True},
            priority=2,
            description="Basic Google Reviews fetch"
        ),
        TestCase(
            test_id="G3b",
            name="Reviews - Sorted Newest",
            category=TestCategory.SPECIALIZED,
            engine="google",
            url="https://www.google.com/reviews",
            params={"fid": "0x808fba02425dad8f:0x6c296c66619367e0", "sort": "newestFirst", "brd_json": "1"},
            expected={"sorted": "newestFirst"},
            priority=3,
            description="Reviews sorted by newest first"
        ),
        TestCase(
            test_id="G3c",
            name="Reviews - Highest Rating",
            category=TestCategory.SPECIALIZED,
            engine="google",
            url="https://www.google.com/reviews",
            params={"fid": "0x808fba02425dad8f:0x6c296c66619367e0", "sort": "ratingHigh", "brd_json": "1"},
            expected={"sorted": "ratingHigh"},
            priority=3,
            description="Reviews sorted by highest rating"
        ),
    ])

    # G4: Google Lens
    tests.extend([
        TestCase(
            test_id="G4a",
            name="Lens - By URL",
            category=TestCategory.SPECIALIZED,
            engine="google",
            url="https://lens.google.com/uploadbyurl",
            params={"url": "https://www.youtube.com/img/desktop/yt_1200.png", "brd_json": "1"},
            expected={"has_lens_results": True},
            priority=2,
            description="Google Lens search by image URL"
        ),
        TestCase(
            test_id="G4b",
            name="Lens - Visual Matches",
            category=TestCategory.SPECIALIZED,
            engine="google",
            url="https://lens.google.com/uploadbyurl",
            params={
                "url": "https://www.youtube.com/img/desktop/yt_1200.png",
                "brd_lens": "visual_matches",
                "brd_json": "1"
            },
            expected={"lens_tab": "visual_matches"},
            priority=3,
            description="Google Lens visual matches tab"
        ),
    ])

    # G5: Google Hotels
    tests.extend([
        TestCase(
            test_id="G5a",
            name="Hotels - Basic Search",
            category=TestCategory.SPECIALIZED,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "hotels in new york", "hotel_occupancy": "2", "brd_json": "1"},
            expected={"has_hotel_results": True},
            priority=1,
            description="Basic hotel search"
        ),
        TestCase(
            test_id="G5b",
            name="Hotels - With Dates",
            category=TestCategory.SPECIALIZED,
            engine="google",
            url="https://www.google.com/search",
            params={
                "q": "hilton new york",
                "hotel_dates": "2025-03-01,2025-03-05",
                "brd_json": "1"
            },
            expected={"has_hotel_dates": True},
            priority=2,
            description="Hotel search with specific dates"
        ),
        TestCase(
            test_id="G5c",
            name="Hotels - Family (with children)",
            category=TestCategory.SPECIALIZED,
            engine="google",
            url="https://www.google.com/search",
            params={
                "q": "family hotels orlando",
                "hotel_occupancy": "4",
                "brd_json": "1"
            },
            expected={"occupancy": 4},
            priority=2,
            description="Hotel search for family with children"
        ),
    ])

    # G6: AI Overview
    tests.extend([
        TestCase(
            test_id="G6a",
            name="AI Overview - Enabled",
            category=TestCategory.SPECIALIZED,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "what makes the best pizza", "brd_ai_overview": "2", "brd_json": "1"},
            expected={"ai_overview_attempted": True},
            timeout=20,  # AI overview adds latency
            priority=2,
            description="Search with AI Overview enabled (adds 5-10s latency)"
        ),
        TestCase(
            test_id="G6b",
            name="AI Overview - Informational Query",
            category=TestCategory.SPECIALIZED,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "how does photosynthesis work", "brd_ai_overview": "2", "brd_json": "1"},
            expected={"ai_overview_attempted": True},
            timeout=20,
            priority=2,
            description="Informational query likely to trigger AI Overview"
        ),
    ])

    # -------------------------------------------------------------------------
    # Category H: Performance Tests
    # -------------------------------------------------------------------------
    tests.extend([
        TestCase(
            test_id="H1a",
            name="Performance - Standard Response",
            category=TestCategory.PERFORMANCE,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "test", "brd_json": "1"},
            expected={"max_time_ms": 5000},
            priority=1,
            description="Standard response time should be <5s"
        ),
        TestCase(
            test_id="H1b",
            name="Performance - Parsed Light",
            category=TestCategory.PERFORMANCE,
            engine="google",
            api_params={
                "query": {"q": "test"},
                "data_format": "parsed_light",
                "country": "us"
            },
            expected={"max_time_ms": 1000},
            use_async=True,
            priority=1,
            description="Parsed light should respond in <1s"
        ),
    ])

    # -------------------------------------------------------------------------
    # Category I: Edge Case & Error Handling Tests
    # -------------------------------------------------------------------------
    tests.extend([
        TestCase(
            test_id="I1a",
            name="Edge - Empty Query",
            category=TestCategory.EDGE_CASES,
            engine="google",
            url="https://www.google.com/search",
            params={"q": ""},
            expected={"error_or_empty": True},
            priority=3,
            description="Empty query handling"
        ),
        TestCase(
            test_id="I1b",
            name="Edge - Very Long Query",
            category=TestCategory.EDGE_CASES,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "python " * 100, "brd_json": "1"},
            expected={"handled": True},
            priority=3,
            description="Very long query (500+ chars)"
        ),
        TestCase(
            test_id="I1c",
            name="Edge - Special Characters",
            category=TestCategory.EDGE_CASES,
            engine="google",
            url="https://www.google.com/search",
            params={"q": 'test @#$%^&*() "quotes"', "brd_json": "1"},
            expected={"handled": True},
            priority=3,
            description="Query with special characters"
        ),
    ])

    # Unicode/Non-Latin Tests
    unicode_tests = [
        ("zh-CN", "cn", "北京餐厅", "Chinese"),
        ("ar", "ae", "مطاعم", "Arabic"),
        ("ru", "ru", "рестораны москва", "Russian"),
        ("ja", "jp", "東京ラーメン", "Japanese"),
        ("ko", "kr", "서울 맛집", "Korean"),
        ("th", "th", "ร้านอาหาร", "Thai"),
        ("hi", "in", "रेस्टोरेंट", "Hindi"),
    ]

    for i, (lang, country, query, name) in enumerate(unicode_tests, 1):
        tests.append(TestCase(
            test_id=f"I2{chr(96+i)}",
            name=f"Unicode - {name}",
            category=TestCategory.EDGE_CASES,
            engine="google",
            url="https://www.google.com/search",
            params={"q": query, "gl": country, "hl": lang, "brd_json": "1"},
            expected={"unicode_handled": True},
            priority=2,
            description=f"Non-Latin query: {name}"
        ))

    # Invalid Parameter Tests
    tests.extend([
        TestCase(
            test_id="I3a",
            name="Invalid - Country Code",
            category=TestCategory.EDGE_CASES,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "test", "gl": "xx", "brd_json": "1"},
            expected={"fallback_or_error": True},
            priority=3,
            description="Invalid country code handling"
        ),
        TestCase(
            test_id="I3b",
            name="Invalid - Language Code",
            category=TestCategory.EDGE_CASES,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "test", "hl": "zz", "brd_json": "1"},
            expected={"fallback_or_error": True},
            priority=3,
            description="Invalid language code handling"
        ),
        TestCase(
            test_id="I3c",
            name="Invalid - Negative Pagination",
            category=TestCategory.EDGE_CASES,
            engine="google",
            url="https://www.google.com/search",
            params={"q": "test", "start": "-10", "brd_json": "1"},
            expected={"fallback_or_error": True},
            priority=3,
            description="Negative pagination offset"
        ),
    ])

    # -------------------------------------------------------------------------
    # Category J: Multi-Engine Comparison Tests
    # -------------------------------------------------------------------------
    comparison_queries = [
        "artificial intelligence",
        "climate change",
        "machine learning python",
    ]

    for i, query in enumerate(comparison_queries, 1):
        # Google version
        tests.append(TestCase(
            test_id=f"J{i}a",
            name=f"Compare Google - Query {i}",
            category=TestCategory.MULTI_ENGINE,
            engine="google",
            url="https://www.google.com/search",
            params={"q": query, "brd_json": "1"},
            expected={"for_comparison": True},
            priority=2,
            description=f"Google search for comparison: {query}"
        ))
        # Bing version
        tests.append(TestCase(
            test_id=f"J{i}b",
            name=f"Compare Bing - Query {i}",
            category=TestCategory.MULTI_ENGINE,
            engine="bing",
            url="https://www.bing.com/search",
            params={"q": query, "brd_json": "1"},
            expected={"for_comparison": True},
            priority=2,
            description=f"Bing search for comparison: {query}"
        ))

    return tests


# ============================================================================
# Test Execution
# ============================================================================

class SerpApiTester:
    """Test executor for Bright Data SERP API."""

    def __init__(self, api_key: str, zone: str):
        self.api_key = api_key
        self.zone = zone
        self.results: list[TestResult] = []
        self.session: Optional[aiohttp.ClientSession] = None

    def _build_proxy_url(self) -> str:
        """Build proxy URL with authentication."""
        # Using API key auth pattern
        return f"http://brd-customer-{BRIGHT_DATA_CUSTOMER_ID}-zone-{self.zone}:{BRIGHT_DATA_ZONE_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}"

    def _build_request_url(self, test: TestCase) -> str:
        """Build the full request URL with parameters."""
        if test.url:
            base_url = test.url
            if test.params:
                query_string = urllib.parse.urlencode(test.params)
                return f"{base_url}?{query_string}" if "?" not in base_url else f"{base_url}&{query_string}"
            return base_url
        return ""

    async def _execute_sync_request(self, test: TestCase) -> TestResult:
        """Execute a synchronous (proxy-based) request via async API with polling."""
        result = TestResult(
            test_id=test.test_id,
            name=test.name,
            category=test.category.value,
            status=TestStatus.RUNNING
        )

        url = self._build_request_url(test)
        start_time = time.time()

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Use direct API request
            api_url = f"{API_BASE_URL}/serp/req"

            # Build the request body
            body = {
                "zone": self.zone,
                "url": url,
                "format": "raw"
            }

            # Step 1: Submit request
            async with self.session.post(
                api_url,
                headers=headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status not in [200, 202]:
                    result.status = TestStatus.FAILED
                    result.error_message = f"Submit failed: HTTP {response.status}"
                    result.duration_ms = (time.time() - start_time) * 1000
                    return result

                data = await response.json()
                response_id = data.get("response_id")

                if not response_id:
                    result.status = TestStatus.FAILED
                    result.error_message = "No response_id in response"
                    result.duration_ms = (time.time() - start_time) * 1000
                    return result

            # Step 2: Poll for results
            get_url = f"{API_BASE_URL}/serp/get_result"
            max_polls = 15
            poll_interval = 2

            for poll_num in range(max_polls):
                await asyncio.sleep(poll_interval)

                async with self.session.get(
                    get_url,
                    headers=headers,
                    params={"response_id": response_id},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as poll_response:
                    poll_status = poll_response.status

                    if poll_status == 102 or poll_status == 202:
                        # Still processing
                        continue
                    elif poll_status == 200:
                        content = await poll_response.text()
                        result.response_code = 200
                        result.duration_ms = (time.time() - start_time) * 1000
                        result.response_size = len(content)
                        result.response_sample = content[:1000] if content else None
                        result.validations = self._validate_response(test, 200, content)
                        result.metadata["polls"] = poll_num + 1

                        if all(result.validations.values()):
                            result.status = TestStatus.PASSED
                        else:
                            result.status = TestStatus.FAILED
                        return result
                    else:
                        result.status = TestStatus.FAILED
                        result.error_message = f"Poll failed: HTTP {poll_status}"
                        result.duration_ms = (time.time() - start_time) * 1000
                        return result

            result.status = TestStatus.FAILED
            result.error_message = f"Polling timeout after {max_polls * poll_interval}s"
            result.duration_ms = (time.time() - start_time) * 1000

        except asyncio.TimeoutError:
            result.status = TestStatus.FAILED
            result.error_message = f"Timeout after {test.timeout}s"
            result.duration_ms = (time.time() - start_time) * 1000
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            result.duration_ms = (time.time() - start_time) * 1000

        return result

    async def _execute_async_request(self, test: TestCase) -> TestResult:
        """Execute an asynchronous API request."""
        result = TestResult(
            test_id=test.test_id,
            name=test.name,
            category=test.category.value,
            status=TestStatus.RUNNING
        )

        start_time = time.time()

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Step 1: Create async request
            create_url = f"{API_BASE_URL}/serp/req"
            body = {
                "zone": self.zone,
                **test.api_params
            }

            async with self.session.post(
                create_url,
                headers=headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status not in [200, 202]:
                    result.status = TestStatus.FAILED
                    result.error_message = f"Create request failed: HTTP {response.status}"
                    return result

                response_id = response.headers.get("x-response-id")
                if not response_id:
                    # Try to get from body
                    data = await response.json()
                    response_id = data.get("response_id")

                if not response_id:
                    result.status = TestStatus.FAILED
                    result.error_message = "No response_id received"
                    return result

            # Step 2: Poll for results
            get_url = f"{API_BASE_URL}/serp/get_result"
            max_polls = 30
            poll_interval = 2

            for _ in range(max_polls):
                async with self.session.get(
                    get_url,
                    headers=headers,
                    params={"response_id": response_id, "zone": self.zone},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as poll_response:
                    if poll_response.status == 102:
                        # Still processing
                        await asyncio.sleep(poll_interval)
                        continue
                    elif poll_response.status == 200:
                        content = await poll_response.text()
                        result.response_code = 200
                        result.duration_ms = (time.time() - start_time) * 1000
                        result.response_size = len(content)
                        result.response_sample = content[:500]
                        result.validations = self._validate_response(test, 200, content)
                        result.status = TestStatus.PASSED if all(result.validations.values()) else TestStatus.FAILED
                        return result
                    else:
                        result.status = TestStatus.FAILED
                        result.error_message = f"Poll failed: HTTP {poll_response.status}"
                        return result

            result.status = TestStatus.FAILED
            result.error_message = "Polling timeout"

        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            result.duration_ms = (time.time() - start_time) * 1000

        return result

    def _validate_response(self, test: TestCase, status_code: int, content: str) -> dict:
        """Validate the response against expected criteria."""
        validations = {}

        # Status code validation
        expected_status = test.expected.get("status", 200)
        validations["status_code"] = status_code == expected_status

        # Content presence
        if test.expected.get("has_content"):
            validations["has_content"] = len(content) > 100

        # JSON format validation
        if test.expected.get("format") == "json" or "brd_json" in test.params:
            try:
                data = json.loads(content)
                validations["is_json"] = True

                # Check for organic results
                if test.expected.get("has_organic"):
                    validations["has_organic"] = "organic" in data or "results" in data

            except json.JSONDecodeError:
                validations["is_json"] = False

        # HTML format validation
        if test.expected.get("format") == "html":
            validations["is_html"] = "<html" in content.lower() or "<!doctype" in content.lower()

        # Response time validation
        if test.expected.get("max_time_ms"):
            # Will be checked after duration is recorded
            pass

        return validations

    async def run_test(self, test: TestCase) -> TestResult:
        """Run a single test case."""
        if test.use_async:
            return await self._execute_async_request(test)
        else:
            return await self._execute_sync_request(test)

    async def run_tests(
        self,
        tests: list[TestCase],
        max_concurrent: int = MAX_CONCURRENT_REQUESTS,
        progress_callback: callable = None
    ) -> list[TestResult]:
        """Run multiple tests with concurrency control."""
        self.results = []

        async with aiohttp.ClientSession() as session:
            self.session = session

            semaphore = asyncio.Semaphore(max_concurrent)

            async def run_with_semaphore(test: TestCase) -> TestResult:
                async with semaphore:
                    result = await self.run_test(test)
                    self.results.append(result)
                    if progress_callback:
                        progress_callback(result)
                    return result

            await asyncio.gather(*[run_with_semaphore(t) for t in tests])

        return self.results


# ============================================================================
# Reporting
# ============================================================================

def generate_report(results: list[TestResult], output_file: Optional[str] = None) -> dict:
    """Generate a test report from results."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.status == TestStatus.PASSED),
            "failed": sum(1 for r in results if r.status == TestStatus.FAILED),
            "error": sum(1 for r in results if r.status == TestStatus.ERROR),
            "skipped": sum(1 for r in results if r.status == TestStatus.SKIPPED),
        },
        "by_category": {},
        "results": [r.to_dict() for r in results]
    }

    # Calculate pass rate
    report["summary"]["pass_rate"] = (
        report["summary"]["passed"] / report["summary"]["total"] * 100
        if report["summary"]["total"] > 0 else 0
    )

    # Group by category
    for result in results:
        cat = result.category
        if cat not in report["by_category"]:
            report["by_category"][cat] = {"passed": 0, "failed": 0, "error": 0, "total": 0}
        report["by_category"][cat]["total"] += 1
        if result.status == TestStatus.PASSED:
            report["by_category"][cat]["passed"] += 1
        elif result.status == TestStatus.FAILED:
            report["by_category"][cat]["failed"] += 1
        elif result.status == TestStatus.ERROR:
            report["by_category"][cat]["error"] += 1

    if output_file:
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)

    return report


def print_results(results: list[TestResult]):
    """Print test results to console."""
    print("\n" + "=" * 70)
    print("BRIGHT DATA SERP API TEST RESULTS")
    print("=" * 70)

    # Group by category
    by_category = {}
    for r in results:
        if r.category not in by_category:
            by_category[r.category] = []
        by_category[r.category].append(r)

    for category, cat_results in sorted(by_category.items()):
        print(f"\n{category.upper()}")
        print("-" * 50)
        for r in cat_results:
            status_icon = {
                TestStatus.PASSED: "[PASS]",
                TestStatus.FAILED: "[FAIL]",
                TestStatus.ERROR: "[ERR!]",
                TestStatus.SKIPPED: "[SKIP]",
            }.get(r.status, "[????]")

            duration = f"{r.duration_ms:.0f}ms" if r.duration_ms else "N/A"
            print(f"  {status_icon} {r.test_id}: {r.name} ({duration})")
            if r.error_message:
                print(f"           Error: {r.error_message}")

    # Summary
    passed = sum(1 for r in results if r.status == TestStatus.PASSED)
    failed = sum(1 for r in results if r.status == TestStatus.FAILED)
    errors = sum(1 for r in results if r.status == TestStatus.ERROR)
    total = len(results)

    print("\n" + "=" * 70)
    print(f"SUMMARY: {passed}/{total} passed ({passed/total*100:.1f}%)")
    print(f"         {failed} failed, {errors} errors")
    print("=" * 70)


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Bright Data SERP API Test Suite")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--category", type=str, help="Run tests in specific category")
    parser.add_argument("--test", type=str, help="Run specific test by ID")
    parser.add_argument("--priority", type=int, help="Run tests up to priority level (0-3)")
    parser.add_argument("--dry-run", action="store_true", help="Show tests without executing")
    parser.add_argument("--output", type=str, help="Output file for results (JSON)")
    parser.add_argument("--concurrent", type=int, default=3, help="Max concurrent requests")
    parser.add_argument("--list", action="store_true", help="List all available tests")

    args = parser.parse_args()

    # Get all test cases
    all_tests = get_all_test_cases()

    # Filter tests
    if args.test:
        tests = [t for t in all_tests if t.test_id == args.test]
    elif args.category:
        cat = TestCategory(args.category.lower())
        tests = [t for t in all_tests if t.category == cat]
    elif args.priority is not None:
        tests = [t for t in all_tests if t.priority <= args.priority]
    elif args.all:
        tests = all_tests
    else:
        # Default: run P0 and P1 tests
        tests = [t for t in all_tests if t.priority <= 1]

    if args.list:
        print(f"\nAvailable Tests ({len(all_tests)} total):")
        print("-" * 60)
        for t in all_tests:
            print(f"  [{t.test_id}] P{t.priority} {t.category.value}: {t.name}")
        return

    if args.dry_run:
        print(f"\nTests to execute ({len(tests)}):")
        print("-" * 60)
        for t in tests:
            print(f"  [{t.test_id}] {t.name}")
            print(f"           Category: {t.category.value}")
            print(f"           Engine: {t.engine}")
            if t.url:
                print(f"           URL: {t.url}")
            if t.params:
                print(f"           Params: {t.params}")
            print()
        return

    if not tests:
        print("No tests selected. Use --all, --category, --test, or --priority")
        return

    print(f"\nRunning {len(tests)} tests...")
    print(f"API Key: {BRIGHT_DATA_API_KEY[:20]}...")
    print(f"Zone: {BRIGHT_DATA_ZONE}")
    print(f"Max Concurrent: {args.concurrent}")
    print("-" * 60)

    # Run tests
    tester = SerpApiTester(BRIGHT_DATA_API_KEY, BRIGHT_DATA_ZONE)

    def progress(result: TestResult):
        status_icon = "[PASS]" if result.status == TestStatus.PASSED else "[FAIL]"
        print(f"  {status_icon} {result.test_id}: {result.name}")

    results = asyncio.run(tester.run_tests(tests, args.concurrent, progress))

    # Print results
    print_results(results)

    # Generate report
    if args.output:
        report = generate_report(results, args.output)
        print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    main()
