# Bright Data SERP API - Comprehensive Test Design

## Overview

This document outlines an exhaustive test suite for investigating and validating all capabilities of the Bright Data SERP API.

---

## 1. API Input Parameters Reference

### 1.1 Common Parameters (All Engines)

| Parameter | Type | Description | Values |
|-----------|------|-------------|--------|
| `brd_json` | int/string | Output format | `1` (JSON), `"html"` (raw HTML) |
| `brd_mobile` | int/string | Device type | `0`, `1`, `ios`, `iphone`, `ipad`, `android`, `android_tablet` |
| `brd_browser` | string | Browser UA | `chrome`, `safari`, `firefox` |
| `country` | string | Country code | 2-letter ISO (e.g., `us`, `uk`, `de`) |

### 1.2 Google Search Parameters

| Parameter | Type | Description | Example Values |
|-----------|------|-------------|----------------|
| `q` | string | Search query | `pizza`, `best restaurants` |
| `gl` | string | Country for results | `us`, `uk`, `de`, `jp` |
| `hl` | string | Language code | `en`, `es`, `fr`, `de` |
| `tbm` | string | Search type | `isch` (images), `shop` (shopping), `nws` (news), `vid` (videos) |
| `ibp` | string | Jobs search | `htl;jobs` |
| `start` | int | Pagination offset | `0`, `10`, `20` |
| `uule` | string | Encoded location | Canonical name or encoded string |
| `hotel_occupancy` | int | Hotel guests | `1`, `2`, `3`, `4` |
| `hotel_dates` | string | Check-in/out dates | `YYYY-MM-DD,YYYY-MM-DD` |
| `brd_ai_overview` | int | AI Overview mode | `2` (enhanced) |
| `data_format` | string | Response format | `parsed_light` (fast, top 10 only) |

### 1.3 Google Maps Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `@lat,lng,zoom` | geo | GPS coordinates | `@47.30227,1.67458,14.00z` |
| `num` | int | Results count | `20`, `40`, `50` |
| `fid` | string | Place feature ID | `0x89e37742d0f37093:0xbc048b8a744ff75a` |
| `brd_accomodation_type` | string | Accommodation filter | `hotels`, `vacation_rentals` |

### 1.4 Google Trends Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `geo` | string | Location code | `us`, `uk` |
| `date` | string | Time range | `now 1-H`, `now 1-d`, `today 12-m`, `2020-07-01 2020-12-31` |
| `cat` | int | Category ID | `3` (Arts & Entertainment) |
| `gprop` | string | Google property | `images`, `news`, `froogle`, `youtube` |
| `brd_trends` | string | Widget data | `timeseries`, `geo_map`, `timeseries,geo_map` |

### 1.5 Google Reviews Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `fid` | string | Feature ID | From `knowledge.fid` field |
| `sort` | string | Sort order | `qualityScore`, `newestFirst`, `ratingHigh`, `ratingLow` |
| `filter` | string | Keyword filter | `awesome`, `terrible` |
| `num` | int | Results count | `10`, `20` (max) |

### 1.6 Google Lens Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `url` | string | Image URL | URL-encoded image path |
| `brd_lens` | string | Lens tab | `products`, `homework`, `visual_matches`, `exact_matches` |

### 1.7 Google Hotels Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `brd_dates` | string | Booking dates | `YYYY-MM-DD,YYYY-MM-DD` |
| `brd_occupancy` | string | Guests/children | `2`, `1,5,7,12` (adults,child ages) |
| `brd_free_cancellation` | bool | Free cancel only | `true`, `false` |
| `brd_currency` | string | Price currency | `USD`, `EUR`, `INR` |

### 1.8 Google Flights Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `tfs` | string | Flight search params | Encoded string |
| `curr` | string | Currency | `USD`, `EUR` |

### 1.9 Bing Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `q` | string | Search query | `pizza` |
| `setLang` | string | UI language | `en-US`, `de-DE` |
| `cc` | string | Country code | `us`, `uk` |
| `mkt` | string | Market | `en-US`, `de-DE` |
| `first` | int | Offset | `1`, `11`, `21` |
| `safesearch` | string | Safe search | `off`, `moderate`, `strict` |
| `filters` | string | Date filter | `ex1:"ez5_19757_19773"` |

---

## 2. Test Categories

### Category A: Basic Functionality Tests
### Category B: Localization & Geo-targeting Tests
### Category C: Search Type & Vertical Tests
### Category D: Pagination Tests
### Category E: Device & Browser Emulation Tests
### Category F: Output Format Tests
### Category G: Specialized Search Tests (Maps, Hotels, Flights)
### Category H: Performance & Reliability Tests
### Category I: Edge Case & Error Handling Tests
### Category J: Multi-Engine Comparison Tests

---

## 3. Detailed Test Cases

### Category A: Basic Functionality Tests

#### A1: Simple Google Search
```python
test_config = {
    "test_id": "A1",
    "name": "Basic Google Search",
    "engine": "google",
    "url": "https://www.google.com/search",
    "params": {
        "q": "pizza"
    },
    "expected": {
        "status": 200,
        "has_organic_results": True,
        "min_results": 5
    }
}
```

#### A2: Google Search with JSON Output
```python
test_config = {
    "test_id": "A2",
    "name": "Google Search JSON Format",
    "engine": "google",
    "url": "https://www.google.com/search",
    "params": {
        "q": "python programming",
        "brd_json": 1
    },
    "expected": {
        "format": "json",
        "has_organic_field": True
    }
}
```

#### A3: Google Search with Parsed Light
```python
test_config = {
    "test_id": "A3",
    "name": "Google Search Parsed Light (Fast)",
    "engine": "google",
    "api_params": {
        "query": {"q": "machine learning"},
        "data_format": "parsed_light"
    },
    "expected": {
        "max_results": 10,
        "response_time_ms": 3000
    }
}
```

#### A4: Basic Bing Search
```python
test_config = {
    "test_id": "A4",
    "name": "Basic Bing Search",
    "engine": "bing",
    "url": "https://www.bing.com/search",
    "params": {
        "q": "artificial intelligence"
    },
    "expected": {
        "status": 200,
        "has_organic_results": True
    }
}
```

---

### Category B: Localization & Geo-targeting Tests

#### B1: Country-Specific Results (Google)
```python
test_configs = [
    {
        "test_id": "B1a",
        "name": "Google Search - US Results",
        "params": {"q": "news", "gl": "us", "hl": "en"},
        "expected": {"results_from": "us"}
    },
    {
        "test_id": "B1b",
        "name": "Google Search - UK Results",
        "params": {"q": "news", "gl": "uk", "hl": "en"},
        "expected": {"results_from": "uk"}
    },
    {
        "test_id": "B1c",
        "name": "Google Search - German Results",
        "params": {"q": "nachrichten", "gl": "de", "hl": "de"},
        "expected": {"results_from": "de", "language": "de"}
    },
    {
        "test_id": "B1d",
        "name": "Google Search - Japan Results",
        "params": {"q": "ニュース", "gl": "jp", "hl": "ja"},
        "expected": {"results_from": "jp", "language": "ja"}
    }
]
```

#### B2: UULE Geo-Location Tests
```python
test_configs = [
    {
        "test_id": "B2a",
        "name": "UULE - New York Location",
        "params": {"q": "restaurants near me", "uule": "New+York,New+York,United+States"},
        "expected": {"location_context": "New York"}
    },
    {
        "test_id": "B2b",
        "name": "UULE - London Location",
        "params": {"q": "restaurants near me", "uule": "London,England,United+Kingdom"},
        "expected": {"location_context": "London"}
    },
    {
        "test_id": "B2c",
        "name": "UULE - Tokyo Location",
        "params": {"q": "レストラン", "uule": "Tokyo,Tokyo,Japan"},
        "expected": {"location_context": "Tokyo"}
    }
]
```

#### B3: Bing Market Tests
```python
test_configs = [
    {
        "test_id": "B3a",
        "name": "Bing Market - en-US",
        "engine": "bing",
        "params": {"q": "weather", "mkt": "en-US", "setLang": "en-US"},
        "expected": {"market": "en-US"}
    },
    {
        "test_id": "B3b",
        "name": "Bing Market - de-DE",
        "engine": "bing",
        "params": {"q": "wetter", "mkt": "de-DE", "setLang": "de-DE"},
        "expected": {"market": "de-DE"}
    }
]
```

---

### Category C: Search Type & Vertical Tests

#### C1: Google Image Search
```python
test_config = {
    "test_id": "C1",
    "name": "Google Image Search",
    "params": {"q": "sunset mountains", "tbm": "isch"},
    "expected": {"result_type": "images", "has_image_urls": True}
}
```

#### C2: Google Shopping Search
```python
test_config = {
    "test_id": "C2",
    "name": "Google Shopping Search",
    "params": {"q": "laptop", "tbm": "shop"},
    "expected": {"result_type": "shopping", "has_prices": True}
}
```

#### C3: Google News Search
```python
test_config = {
    "test_id": "C3",
    "name": "Google News Search",
    "params": {"q": "technology", "tbm": "nws"},
    "expected": {"result_type": "news", "has_dates": True}
}
```

#### C4: Google Video Search
```python
test_config = {
    "test_id": "C4",
    "name": "Google Video Search",
    "params": {"q": "cooking tutorial", "tbm": "vid"},
    "expected": {"result_type": "videos", "has_video_urls": True}
}
```

#### C5: Google Jobs Search
```python
test_config = {
    "test_id": "C5",
    "name": "Google Jobs Search",
    "params": {"q": "software engineer", "ibp": "htl;jobs"},
    "expected": {"result_type": "jobs", "has_job_listings": True}
}
```

---

### Category D: Pagination Tests

#### D1: Google Pagination
```python
test_configs = [
    {"test_id": "D1a", "name": "Google Page 1", "params": {"q": "python", "start": 0}},
    {"test_id": "D1b", "name": "Google Page 2", "params": {"q": "python", "start": 10}},
    {"test_id": "D1c", "name": "Google Page 3", "params": {"q": "python", "start": 20}},
    {"test_id": "D1d", "name": "Google Page 5", "params": {"q": "python", "start": 40}},
    {"test_id": "D1e", "name": "Google Page 10", "params": {"q": "python", "start": 90}}
]
```

#### D2: Bing Pagination
```python
test_configs = [
    {"test_id": "D2a", "name": "Bing Page 1", "engine": "bing", "params": {"q": "python", "first": 1}},
    {"test_id": "D2b", "name": "Bing Page 2", "engine": "bing", "params": {"q": "python", "first": 11}},
    {"test_id": "D2c", "name": "Bing Page 3", "engine": "bing", "params": {"q": "python", "first": 21}}
]
```

#### D3: Maps Pagination
```python
test_configs = [
    {"test_id": "D3a", "name": "Maps Results 1-20", "url": "maps", "params": {"q": "hotels new york", "start": 0, "num": 20}},
    {"test_id": "D3b", "name": "Maps Results 21-40", "url": "maps", "params": {"q": "hotels new york", "start": 20, "num": 20}},
    {"test_id": "D3c", "name": "Maps Results 41-60", "url": "maps", "params": {"q": "hotels new york", "start": 40, "num": 20}}
]
```

---

### Category E: Device & Browser Emulation Tests

#### E1: Mobile Device Tests
```python
test_configs = [
    {"test_id": "E1a", "name": "Desktop User Agent", "params": {"q": "test", "brd_mobile": 0}},
    {"test_id": "E1b", "name": "Generic Mobile", "params": {"q": "test", "brd_mobile": 1}},
    {"test_id": "E1c", "name": "iPhone User Agent", "params": {"q": "test", "brd_mobile": "ios"}},
    {"test_id": "E1d", "name": "iPad User Agent", "params": {"q": "test", "brd_mobile": "ipad"}},
    {"test_id": "E1e", "name": "Android Phone", "params": {"q": "test", "brd_mobile": "android"}},
    {"test_id": "E1f", "name": "Android Tablet", "params": {"q": "test", "brd_mobile": "android_tablet"}}
]
```

#### E2: Browser Tests
```python
test_configs = [
    {"test_id": "E2a", "name": "Chrome Browser", "params": {"q": "test", "brd_browser": "chrome"}},
    {"test_id": "E2b", "name": "Safari Browser", "params": {"q": "test", "brd_browser": "safari"}},
    {"test_id": "E2c", "name": "Firefox Browser", "params": {"q": "test", "brd_browser": "firefox"}}
]
```

#### E3: Combined Device + Browser
```python
test_configs = [
    {"test_id": "E3a", "name": "Mobile Chrome", "params": {"q": "test", "brd_mobile": 1, "brd_browser": "chrome"}},
    {"test_id": "E3b", "name": "iOS Safari", "params": {"q": "test", "brd_mobile": "ios", "brd_browser": "safari"}},
    {"test_id": "E3c", "name": "Android Chrome", "params": {"q": "test", "brd_mobile": "android", "brd_browser": "chrome"}}
]
```

---

### Category F: Output Format Tests

#### F1: JSON vs HTML
```python
test_configs = [
    {"test_id": "F1a", "name": "JSON Output", "params": {"q": "test", "brd_json": 1}, "expected": {"format": "json"}},
    {"test_id": "F1b", "name": "HTML Output", "params": {"q": "test"}, "expected": {"format": "html"}}
]
```

#### F2: Parsed Light Format
```python
test_config = {
    "test_id": "F2",
    "name": "Parsed Light Format",
    "api_params": {"query": {"q": "test"}, "data_format": "parsed_light"},
    "expected": {"fields": ["organic"], "max_results": 10}
}
```

---

### Category G: Specialized Search Tests

#### G1: Google Maps Search
```python
test_configs = [
    {
        "test_id": "G1a",
        "name": "Maps Basic Search",
        "url": "https://www.google.com/maps/search/restaurants+new+york",
        "params": {"brd_json": 1},
        "expected": {"has_places": True}
    },
    {
        "test_id": "G1b",
        "name": "Maps with Coordinates",
        "url": "https://www.google.com/maps/search/coffee/@40.7128,-74.0060,14z",
        "params": {"brd_json": 1},
        "expected": {"location_based": True}
    },
    {
        "test_id": "G1c",
        "name": "Maps Place by FID",
        "url": "http://www.google.com/maps/place/data=!3m1!4b1!4m2!3m1!1s0x89e37742d0f37093:0xbc048b8a744ff75a",
        "expected": {"has_place_details": True}
    }
]
```

#### G2: Google Trends
```python
test_configs = [
    {
        "test_id": "G2a",
        "name": "Trends Basic",
        "url": "https://trends.google.com/trends/explore",
        "params": {"q": "bitcoin", "geo": "us", "brd_trends": "timeseries,geo_map", "brd_json": 1}
    },
    {
        "test_id": "G2b",
        "name": "Trends Past 24 Hours",
        "url": "https://trends.google.com/trends/explore",
        "params": {"q": "news", "date": "now 1-d", "brd_trends": "timeseries", "brd_json": 1}
    },
    {
        "test_id": "G2c",
        "name": "Trends YouTube Property",
        "url": "https://trends.google.com/trends/explore",
        "params": {"q": "music", "gprop": "youtube", "brd_trends": "timeseries", "brd_json": 1}
    },
    {
        "test_id": "G2d",
        "name": "Trends Custom Date Range",
        "url": "https://trends.google.com/trends/explore",
        "params": {"q": "election", "date": "2024-01-01 2024-06-30", "brd_trends": "timeseries,geo_map", "brd_json": 1}
    }
]
```

#### G3: Google Reviews
```python
test_configs = [
    {
        "test_id": "G3a",
        "name": "Reviews Basic",
        "url": "https://www.google.com/reviews",
        "params": {"fid": "0x808fba02425dad8f:0x6c296c66619367e0", "brd_json": 1}
    },
    {
        "test_id": "G3b",
        "name": "Reviews Sorted Newest",
        "url": "https://www.google.com/reviews",
        "params": {"fid": "0x808fba02425dad8f:0x6c296c66619367e0", "sort": "newestFirst", "brd_json": 1}
    },
    {
        "test_id": "G3c",
        "name": "Reviews Filtered",
        "url": "https://www.google.com/reviews",
        "params": {"fid": "0x808fba02425dad8f:0x6c296c66619367e0", "filter": "great", "brd_json": 1}
    }
]
```

#### G4: Google Lens
```python
test_configs = [
    {
        "test_id": "G4a",
        "name": "Lens by URL",
        "url": "https://lens.google.com/uploadbyurl",
        "params": {"url": "https://www.youtube.com/img/desktop/yt_1200.png", "brd_json": 1}
    },
    {
        "test_id": "G4b",
        "name": "Lens Visual Matches",
        "url": "https://lens.google.com/uploadbyurl",
        "params": {"url": "https://example.com/image.png", "brd_lens": "visual_matches", "brd_json": 1}
    },
    {
        "test_id": "G4c",
        "name": "Lens Products",
        "url": "https://lens.google.com/uploadbyurl",
        "params": {"url": "https://example.com/product.png", "brd_lens": "products", "brd_json": 1}
    }
]
```

#### G5: Google Hotels
```python
test_configs = [
    {
        "test_id": "G5a",
        "name": "Hotels Basic Search",
        "search_query": "hotels in new york",
        "params": {"hotel_occupancy": 2, "brd_json": 1}
    },
    {
        "test_id": "G5b",
        "name": "Hotels with Dates",
        "search_query": "hilton new york",
        "params": {"brd_dates": "2025-02-01,2025-02-05", "brd_occupancy": 2, "brd_json": 1}
    },
    {
        "test_id": "G5c",
        "name": "Hotels with Children",
        "search_query": "family hotels orlando",
        "params": {"brd_occupancy": "2,5,8", "brd_json": 1}
    },
    {
        "test_id": "G5d",
        "name": "Hotels Free Cancellation",
        "search_query": "hotels miami",
        "params": {"brd_free_cancellation": "true", "brd_json": 1}
    },
    {
        "test_id": "G5e",
        "name": "Hotels Vacation Rentals",
        "search_query": "vacation rentals hawaii",
        "params": {"brd_accomodation_type": "vacation_rentals", "brd_json": 1}
    },
    {
        "test_id": "G5f",
        "name": "Hotels Currency EUR",
        "search_query": "hotels paris",
        "params": {"brd_currency": "EUR", "brd_json": 1}
    }
]
```

#### G6: Google Flights
```python
test_configs = [
    {
        "test_id": "G6a",
        "name": "Flights Basic",
        "url": "https://www.google.com/travel/flights/search",
        "params": {"tfs": "CBwQAhoiEgoyMDI1LTAzLTAxagsIAhIHL20vMGszcHIHCAESA1hSSkABSAFwAYIBCwj___________8BmAEC", "brd_json": 1}
    },
    {
        "test_id": "G6b",
        "name": "Flights with Currency",
        "url": "https://www.google.com/travel/flights/search",
        "params": {"tfs": "...", "curr": "EUR", "brd_json": 1}
    }
]
```

#### G7: AI Overview
```python
test_configs = [
    {
        "test_id": "G7a",
        "name": "AI Overview Enabled",
        "params": {"q": "what makes the best pizza", "brd_ai_overview": 2, "brd_json": 1},
        "expected": {"may_have_ai_overview": True, "extra_latency": True}
    },
    {
        "test_id": "G7b",
        "name": "AI Overview Informational Query",
        "params": {"q": "how does photosynthesis work", "brd_ai_overview": 2, "brd_json": 1}
    }
]
```

---

### Category H: Performance & Reliability Tests

#### H1: Response Time Tests
```python
test_configs = [
    {"test_id": "H1a", "name": "Standard Response Time", "params": {"q": "test"}, "expected": {"max_time_ms": 5000}},
    {"test_id": "H1b", "name": "Parsed Light Response Time", "api_params": {"data_format": "parsed_light"}, "expected": {"max_time_ms": 1000}},
    {"test_id": "H1c", "name": "AI Overview Response Time", "params": {"brd_ai_overview": 2}, "expected": {"max_time_ms": 15000}}
]
```

#### H2: Concurrent Request Tests
```python
test_config = {
    "test_id": "H2",
    "name": "Concurrent Requests",
    "concurrent_count": 10,
    "params": {"q": "test"},
    "expected": {"success_rate": 0.95}
}
```

#### H3: Large Result Set Tests
```python
test_config = {
    "test_id": "H3",
    "name": "Large Maps Result Set",
    "url": "maps",
    "params": {"q": "restaurants", "num": 50},
    "expected": {"min_results": 40}
}
```

---

### Category I: Edge Case & Error Handling Tests

#### I1: Empty/Invalid Query
```python
test_configs = [
    {"test_id": "I1a", "name": "Empty Query", "params": {"q": ""}, "expected": {"error": True}},
    {"test_id": "I1b", "name": "Very Long Query", "params": {"q": "a" * 500}, "expected": {"handled": True}},
    {"test_id": "I1c", "name": "Special Characters", "params": {"q": "test @#$%^&*()"}, "expected": {"handled": True}}
]
```

#### I2: Unicode/Non-Latin Queries
```python
test_configs = [
    {"test_id": "I2a", "name": "Chinese Query", "params": {"q": "北京餐厅", "gl": "cn", "hl": "zh-CN"}},
    {"test_id": "I2b", "name": "Arabic Query", "params": {"q": "مطاعم", "gl": "ae", "hl": "ar"}},
    {"test_id": "I2c", "name": "Russian Query", "params": {"q": "рестораны москва", "gl": "ru", "hl": "ru"}},
    {"test_id": "I2d", "name": "Japanese Query", "params": {"q": "東京ラーメン", "gl": "jp", "hl": "ja"}},
    {"test_id": "I2e", "name": "Korean Query", "params": {"q": "서울 맛집", "gl": "kr", "hl": "ko"}}
]
```

#### I3: Invalid Parameter Tests
```python
test_configs = [
    {"test_id": "I3a", "name": "Invalid Country Code", "params": {"q": "test", "gl": "xx"}},
    {"test_id": "I3b", "name": "Invalid Language Code", "params": {"q": "test", "hl": "zz"}},
    {"test_id": "I3c", "name": "Invalid Pagination", "params": {"q": "test", "start": -10}},
    {"test_id": "I3d", "name": "Invalid TBM Value", "params": {"q": "test", "tbm": "invalid"}}
]
```

#### I4: Rate Limiting Tests
```python
test_config = {
    "test_id": "I4",
    "name": "Rate Limit Behavior",
    "rapid_requests": 100,
    "expected": {"rate_limit_response": True, "recovery": True}
}
```

---

### Category J: Multi-Engine Comparison Tests

#### J1: Cross-Engine Same Query
```python
test_config = {
    "test_id": "J1",
    "name": "Multi-Engine Comparison",
    "query": "artificial intelligence",
    "engines": ["google", "bing"],
    "compare": ["result_count", "top_domains", "response_time"]
}
```

#### J2: Engine-Specific Features
```python
test_configs = [
    {
        "test_id": "J2a",
        "name": "Google-Specific (Knowledge Panel)",
        "engine": "google",
        "params": {"q": "Albert Einstein"},
        "expected": {"has_knowledge_panel": True}
    },
    {
        "test_id": "J2b",
        "name": "Bing Safe Search",
        "engine": "bing",
        "params": {"q": "adult content", "safesearch": "strict"},
        "expected": {"filtered_results": True}
    }
]
```

---

## 4. Async Request Tests

### Async Flow Tests
```python
test_configs = [
    {
        "test_id": "ASYNC1",
        "name": "Async Request Flow",
        "step1": {"method": "POST", "endpoint": "/serp/req", "body": {"query": {"q": "test"}, "country": "us"}},
        "step2": {"method": "GET", "endpoint": "/serp/get_result", "params": {"response_id": "{from_step1}"}},
        "expected": {"status_102_while_processing": True, "final_status_200": True}
    },
    {
        "test_id": "ASYNC2",
        "name": "Async with Webhook",
        "body": {
            "query": {"q": "test"},
            "webhook_url": "https://your-webhook.com/callback",
            "webhook_method": "POST"
        },
        "expected": {"webhook_called": True}
    }
]
```

---

## 5. Test Execution Matrix

| Test Category | Google | Bing | Maps | Trends | Hotels | Flights | Lens |
|---------------|--------|------|------|--------|--------|---------|------|
| Basic Search | ✓ | ✓ | ✓ | - | - | - | - |
| Localization | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Pagination | ✓ | ✓ | ✓ | - | - | - | - |
| Device/Browser | ✓ | ✓ | ✓ | - | ✓ | - | - |
| JSON Output | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Filters/Sorting | ✓ | ✓ | ✓ | ✓ | ✓ | - | ✓ |

---

## 6. Expected Response Schemas

### Google Organic Result Schema
```json
{
  "organic": [
    {
      "link": "string",
      "title": "string",
      "description": "string",
      "global_rank": "number",
      "extensions": [
        {
          "type": "string",
          "link": "string",
          "text": "string"
        }
      ]
    }
  ],
  "knowledge": {},
  "ads": [],
  "related_searches": [],
  "people_also_ask": []
}
```

### Maps Result Schema
```json
{
  "places": [
    {
      "name": "string",
      "address": "string",
      "rating": "number",
      "reviews_count": "number",
      "fid": "string",
      "coordinates": {
        "lat": "number",
        "lng": "number"
      }
    }
  ]
}
```

---

## 7. Test Implementation Notes

### Authentication
All requests require:
- Proxy: `brd.superproxy.io:33335`
- Proxy-User: `brd-customer-<customer-id>-zone-<zone-name>:<zone-password>`
- Or API: `Authorization: Bearer <API_KEY>`

### API Endpoints
- Sync Proxy: `brd.superproxy.io:33335`
- Async Request: `POST https://api.brightdata.com/serp/req`
- Async Result: `GET https://api.brightdata.com/serp/get_result`

### Rate Limits
- Default: 1 request per second per API key
- Async: Higher throughput, up to 5 minutes callback

### Cost Considerations
- Each request is billed
- Async multi-requests are billed as 2 requests
- Use parsed_light for cost-effective high-volume testing

---

## 8. Test Priority Matrix

| Priority | Test IDs | Rationale |
|----------|----------|-----------|
| P0 (Critical) | A1, A2, A4, B1, F1 | Core functionality |
| P1 (High) | C1-C5, D1, G1, G5 | Key features |
| P2 (Medium) | E1-E3, G2-G4, H1 | Device/specialized |
| P3 (Low) | I1-I4, J1-J2 | Edge cases |

---

## 9. Success Criteria

- **Pass Rate**: >95% of P0/P1 tests pass
- **Response Time**: <5s for standard, <1s for parsed_light
- **Data Accuracy**: JSON schema validation passes
- **Error Handling**: All edge cases handled gracefully
- **Multi-Engine**: Consistent results across engines for same queries
