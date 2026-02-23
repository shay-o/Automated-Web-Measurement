"""
Page Analyzer - Uses OpenRouter API to analyze crawled pages and identify
trackable user interactions, page elements, and data points.
"""

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Try to import openai, but allow fallback to mock for demo
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "anthropic/claude-opus-4.5"


@dataclass
class PageAnalysis:
    url: str
    page_type: str
    page_purpose: str
    interactive_elements: list[dict] = field(default_factory=list)
    trackable_actions: list[dict] = field(default_factory=list)
    data_points: list[dict] = field(default_factory=list)
    recommended_events: list[dict] = field(default_factory=list)
    raw_analysis: str = ""


ANALYSIS_PROMPT = """You are a Google Analytics 4 tracking specialist. Analyze this web page and provide structured recommendations for GA4 event tracking.

## Page Information
- URL: {url}
- Page Type: {page_type}
- Page Title: {title}

## HTML Content (condensed)
{html_content}

## Your Task

Analyze this page and respond with a JSON object containing:

1. **page_purpose**: A one-sentence description of what this page does for users.

2. **interactive_elements**: Array of objects describing each interactive element:
   - `element`: What the element is (e.g., "Add to Cart button", "Size selector dropdown")
   - `selector_hint`: CSS selector or identifying attribute
   - `interaction_type`: click, form_submit, scroll, hover, input_change, etc.

3. **trackable_actions**: Array of user actions worth tracking:
   - `action`: Description (e.g., "User adds item to cart")
   - `business_value`: Why this matters for analytics (e.g., "Measures purchase intent")
   - `frequency`: expected_high, expected_medium, expected_low

4. **data_points**: Array of data available on this page that could be sent as event parameters:
   - `name`: Parameter name (e.g., "product_name", "collection_name")
   - `source`: Where it comes from (e.g., "product title element", "URL path", "data attribute")
   - `example_value`: Example of what the value might look like

5. **recommended_events**: Array of GA4 events to implement:
   - `event_name`: GA4 event name (use GA4 recommended events where applicable: page_view, view_item, view_item_list, select_item, add_to_cart, remove_from_cart, begin_checkout, purchase, search, sign_up, login, share, select_content, generate_lead, etc. Use custom events only when no standard event fits.)
   - `trigger_description`: When this event should fire
   - `parameters`: Object mapping parameter names to descriptions of their values
   - `is_standard`: true if this is a GA4 recommended event, false if custom
   - `priority`: high, medium, low

Respond with ONLY the JSON object, no markdown formatting or explanation."""


def condense_html(html: str, max_chars: int = 8000) -> str:
    """Strip non-essential HTML to fit in context window while preserving structure."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")

    # Remove scripts, styles, SVGs, and other non-content elements
    for tag in soup.find_all(["script", "style", "svg", "noscript", "iframe"]):
        tag.decompose()

    # Remove country selector bloat (common in Shopify)
    for tag in soup.find_all("option"):
        tag.decompose()

    # Remove excessive image tags (keep alt text)
    for img in soup.find_all("img"):
        alt = img.get("alt", "")
        if alt:
            img.replace_with(f"[IMG: {alt}]")
        else:
            img.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Collapse whitespace
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    # Deduplicate consecutive identical lines
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)

    result = "\n".join(deduped)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n... [truncated]"
    return result


def analyze_page(page, api_key: str = None) -> PageAnalysis:
    """Analyze a single page using the OpenRouter API."""
    if not HAS_OPENAI:
        raise ImportError("openai package not installed. Run: pip install openai")

    client = OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)

    condensed = condense_html(page.html)
    prompt = ANALYSIS_PROMPT.format(
        url=page.url,
        page_type=page.page_type,
        title=page.title,
        html_content=condensed,
    )

    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.choices[0].message.content
    # Strip markdown code fences if present
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
    if raw_text.endswith("```"):
        raw_text = raw_text.rsplit("```", 1)[0]

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON from Claude response for {page.url}")
        data = {}

    return PageAnalysis(
        url=page.url,
        page_type=page.page_type,
        page_purpose=data.get("page_purpose", ""),
        interactive_elements=data.get("interactive_elements", []),
        trackable_actions=data.get("trackable_actions", []),
        data_points=data.get("data_points", []),
        recommended_events=data.get("recommended_events", []),
        raw_analysis=raw_text,
    )


def generate_demo_analyses() -> list[PageAnalysis]:
    """
    Generate realistic demo analyses for Oaklandish.com pages.
    Used when the Claude API is not available.
    """
    analyses = [
        PageAnalysis(
            url="https://www.oaklandish.com/",
            page_type="homepage",
            page_purpose="Main landing page showcasing featured collections, promotions, and brand identity to drive browsing and purchasing.",
            interactive_elements=[
                {"element": "Navigation menu links", "selector_hint": "nav a", "interaction_type": "click"},
                {"element": "Hero banner carousel", "selector_hint": ".slideshow, .hero", "interaction_type": "click"},
                {"element": "Featured collection product cards", "selector_hint": ".product-card a", "interaction_type": "click"},
                {"element": "Announcement bar links", "selector_hint": ".announcement-bar a", "interaction_type": "click"},
                {"element": "Email signup form", "selector_hint": "form.newsletter, .klaviyo-form", "interaction_type": "form_submit"},
                {"element": "Search icon/bar", "selector_hint": "[data-search], .search-modal", "interaction_type": "click"},
                {"element": "Cart icon", "selector_hint": ".cart-icon, [href='/cart']", "interaction_type": "click"},
                {"element": "Country/currency selector", "selector_hint": ".country-selector", "interaction_type": "click"},
            ],
            trackable_actions=[
                {"action": "User views homepage", "business_value": "Measures site traffic entry point and brand awareness", "frequency": "expected_high"},
                {"action": "User clicks hero banner CTA", "business_value": "Measures effectiveness of homepage merchandising", "frequency": "expected_high"},
                {"action": "User clicks featured product", "business_value": "Measures product discovery from homepage", "frequency": "expected_medium"},
                {"action": "User signs up for email", "business_value": "Lead generation and remarketing list building", "frequency": "expected_low"},
                {"action": "User opens search", "business_value": "Indicates user has specific product intent", "frequency": "expected_medium"},
                {"action": "User clicks navigation category", "business_value": "Shows browsing preferences and popular categories", "frequency": "expected_high"},
            ],
            data_points=[
                {"name": "page_location", "source": "URL", "example_value": "https://www.oaklandish.com/"},
                {"name": "promotion_name", "source": "Announcement bar text", "example_value": "FREE US SHIPPING $150+"},
                {"name": "hero_banner_content", "source": "Hero section", "example_value": "New Arrivals - Coach Beam Collection"},
            ],
            recommended_events=[
                {
                    "event_name": "page_view",
                    "trigger_description": "Fires on homepage load",
                    "parameters": {"page_title": "Homepage title", "page_location": "Full URL"},
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "view_promotion",
                    "trigger_description": "Fires when hero banner/promotional content is visible in viewport",
                    "parameters": {
                        "promotion_id": "Banner/promo identifier",
                        "promotion_name": "Descriptive name of promotion",
                        "creative_name": "Banner creative variant",
                        "creative_slot": "Position on page (hero, mid, footer)",
                    },
                    "is_standard": True,
                    "priority": "medium",
                },
                {
                    "event_name": "select_promotion",
                    "trigger_description": "Fires when user clicks a promotional banner or CTA",
                    "parameters": {
                        "promotion_id": "Banner/promo identifier",
                        "promotion_name": "Descriptive name of promotion",
                        "creative_name": "Banner creative variant",
                        "creative_slot": "Position on page",
                    },
                    "is_standard": True,
                    "priority": "medium",
                },
                {
                    "event_name": "view_item_list",
                    "trigger_description": "Fires when featured product grid becomes visible",
                    "parameters": {
                        "item_list_id": "Collection/list identifier",
                        "item_list_name": "e.g., 'Homepage Featured' or 'Best Sellers'",
                        "items": "Array of item objects with id, name, price, category",
                    },
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "select_item",
                    "trigger_description": "Fires when user clicks a product card on the homepage",
                    "parameters": {
                        "item_list_id": "List the product was selected from",
                        "item_list_name": "Display name of the list",
                        "items": "Array with the selected item object",
                    },
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "sign_up",
                    "trigger_description": "Fires on successful email newsletter signup",
                    "parameters": {"method": "email_newsletter"},
                    "is_standard": True,
                    "priority": "medium",
                },
                {
                    "event_name": "search",
                    "trigger_description": "Fires when user submits a search query",
                    "parameters": {"search_term": "The search query text"},
                    "is_standard": True,
                    "priority": "high",
                },
            ],
        ),
        PageAnalysis(
            url="https://www.oaklandish.com/collections/tops",
            page_type="collection",
            page_purpose="Displays a filtered grid of products within the 'Tops' category, allowing users to browse, sort, and select items.",
            interactive_elements=[
                {"element": "Product cards (image + title + price)", "selector_hint": ".product-card, .grid-product", "interaction_type": "click"},
                {"element": "Sort dropdown", "selector_hint": "select[name='sort_by'], .collection-sort", "interaction_type": "input_change"},
                {"element": "Filter controls", "selector_hint": ".filter-group, .facets", "interaction_type": "click"},
                {"element": "Pagination / load more", "selector_hint": ".pagination a, .load-more", "interaction_type": "click"},
                {"element": "Quick add to cart buttons", "selector_hint": ".quick-add, .add-to-cart", "interaction_type": "click"},
            ],
            trackable_actions=[
                {"action": "User views collection page", "business_value": "Measures category interest and browsing patterns", "frequency": "expected_high"},
                {"action": "User clicks a product from the grid", "business_value": "Measures product appeal and click-through from browse", "frequency": "expected_high"},
                {"action": "User changes sort order", "business_value": "Reveals user preferences (price-sensitive, new-seekers, etc.)", "frequency": "expected_medium"},
                {"action": "User applies a filter", "business_value": "Shows which product attributes matter to shoppers", "frequency": "expected_medium"},
                {"action": "User scrolls to load more products", "business_value": "Measures depth of browsing engagement", "frequency": "expected_medium"},
            ],
            data_points=[
                {"name": "item_list_name", "source": "Collection title element", "example_value": "Tops"},
                {"name": "item_list_id", "source": "URL path segment", "example_value": "tops"},
                {"name": "items", "source": "Product cards in grid", "example_value": "[{id: 'classic-logo-tee', name: 'Classic Logo Tee', price: 38.00, category: 'Tops'}]"},
                {"name": "sort_order", "source": "Sort dropdown value", "example_value": "best-selling"},
            ],
            recommended_events=[
                {
                    "event_name": "page_view",
                    "trigger_description": "Fires on collection page load",
                    "parameters": {"page_title": "Collection page title", "page_location": "Full URL"},
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "view_item_list",
                    "trigger_description": "Fires when the product grid is visible on page load",
                    "parameters": {
                        "item_list_id": "Collection handle from URL (e.g., 'tops')",
                        "item_list_name": "Collection display name (e.g., 'Tops')",
                        "items": "Array of visible product objects with item_id, item_name, price, item_category, index",
                    },
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "select_item",
                    "trigger_description": "Fires when user clicks a product card in the grid",
                    "parameters": {
                        "item_list_id": "Collection handle",
                        "item_list_name": "Collection display name",
                        "items": "Array with single selected item object",
                    },
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "collection_sort",
                    "trigger_description": "Fires when user changes the sort order dropdown",
                    "parameters": {
                        "collection_name": "Current collection name",
                        "sort_value": "Selected sort option (e.g., 'price-ascending')",
                    },
                    "is_standard": False,
                    "priority": "medium",
                },
                {
                    "event_name": "collection_filter",
                    "trigger_description": "Fires when user applies or changes a filter",
                    "parameters": {
                        "collection_name": "Current collection name",
                        "filter_type": "Filter category (e.g., 'size', 'color')",
                        "filter_value": "Selected filter value",
                    },
                    "is_standard": False,
                    "priority": "medium",
                },
            ],
        ),
        PageAnalysis(
            url="https://www.oaklandish.com/products/classic-logo-tee",
            page_type="product",
            page_purpose="Product detail page where users view product information, select variants (size/color), and add items to their cart.",
            interactive_elements=[
                {"element": "Product image gallery", "selector_hint": ".product-images, .product-gallery", "interaction_type": "click"},
                {"element": "Size selector", "selector_hint": ".variant-selector, [name='Size']", "interaction_type": "click"},
                {"element": "Color/style selector", "selector_hint": ".swatch-selector, [name='Color']", "interaction_type": "click"},
                {"element": "Quantity input", "selector_hint": "input[name='quantity']", "interaction_type": "input_change"},
                {"element": "Add to Cart button", "selector_hint": ".product-form__submit, [name='add']", "interaction_type": "click"},
                {"element": "Size chart link", "selector_hint": ".size-chart-link", "interaction_type": "click"},
                {"element": "Product description accordion", "selector_hint": ".product-description, .accordion", "interaction_type": "click"},
                {"element": "Share buttons", "selector_hint": ".social-sharing a", "interaction_type": "click"},
                {"element": "Related/recommended products", "selector_hint": ".related-products .product-card", "interaction_type": "click"},
            ],
            trackable_actions=[
                {"action": "User views product detail page", "business_value": "Measures product interest — key funnel step before purchase", "frequency": "expected_high"},
                {"action": "User selects a size variant", "business_value": "Shows purchase intent and popular sizes", "frequency": "expected_high"},
                {"action": "User adds item to cart", "business_value": "Critical conversion event — strongest purchase intent signal", "frequency": "expected_high"},
                {"action": "User clicks product image to zoom", "business_value": "Indicates engagement depth with product", "frequency": "expected_medium"},
                {"action": "User opens size chart", "business_value": "May correlate with returns — sizing uncertainty", "frequency": "expected_low"},
                {"action": "User shares product", "business_value": "Organic marketing amplification", "frequency": "expected_low"},
                {"action": "User clicks a recommended product", "business_value": "Measures recommendation engine effectiveness", "frequency": "expected_medium"},
            ],
            data_points=[
                {"name": "item_id", "source": "Shopify product ID / SKU", "example_value": "classic-logo-tee-black-m"},
                {"name": "item_name", "source": "Product title", "example_value": "Classic Logo Tee"},
                {"name": "price", "source": "Product price element", "example_value": "38.00"},
                {"name": "currency", "source": "Store currency setting", "example_value": "USD"},
                {"name": "item_category", "source": "Product type / collection", "example_value": "Tops"},
                {"name": "item_category2", "source": "Sub-category", "example_value": "T-Shirts"},
                {"name": "item_variant", "source": "Selected size/color", "example_value": "Black / M"},
                {"name": "item_brand", "source": "Vendor field", "example_value": "Oaklandish"},
                {"name": "quantity", "source": "Quantity input", "example_value": "1"},
            ],
            recommended_events=[
                {
                    "event_name": "page_view",
                    "trigger_description": "Fires on product page load",
                    "parameters": {"page_title": "Product page title", "page_location": "Full URL"},
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "view_item",
                    "trigger_description": "Fires on product page load, captures full product details",
                    "parameters": {
                        "currency": "USD",
                        "value": "Product price",
                        "items": "Array with single item: item_id, item_name, item_brand, item_category, price, item_variant",
                    },
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "add_to_cart",
                    "trigger_description": "Fires when user clicks Add to Cart and item is successfully added",
                    "parameters": {
                        "currency": "USD",
                        "value": "Total value (price × quantity)",
                        "items": "Array with item: item_id, item_name, item_brand, item_category, item_variant, price, quantity",
                    },
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "select_item",
                    "trigger_description": "Fires when user clicks a recommended/related product from this page",
                    "parameters": {
                        "item_list_id": "related_products",
                        "item_list_name": "You May Also Like",
                        "items": "Array with selected item",
                    },
                    "is_standard": True,
                    "priority": "medium",
                },
                {
                    "event_name": "share",
                    "trigger_description": "Fires when user clicks a social sharing button",
                    "parameters": {
                        "method": "Social platform (facebook, twitter, pinterest, etc.)",
                        "content_type": "product",
                        "item_id": "Product identifier",
                    },
                    "is_standard": True,
                    "priority": "low",
                },
                {
                    "event_name": "view_size_chart",
                    "trigger_description": "Fires when user opens the size chart modal/link",
                    "parameters": {
                        "item_name": "Product name",
                        "item_category": "Product category",
                    },
                    "is_standard": False,
                    "priority": "low",
                },
            ],
        ),
        PageAnalysis(
            url="https://www.oaklandish.com/cart",
            page_type="cart",
            page_purpose="Shopping cart page where users review selected items, modify quantities, and proceed to checkout.",
            interactive_elements=[
                {"element": "Quantity increment/decrement buttons", "selector_hint": ".quantity-selector button, .cart-qty", "interaction_type": "click"},
                {"element": "Remove item button", "selector_hint": ".cart-remove, .remove-item", "interaction_type": "click"},
                {"element": "Checkout button", "selector_hint": ".checkout-button, [name='checkout']", "interaction_type": "click"},
                {"element": "Continue shopping link", "selector_hint": "a[href='/collections']", "interaction_type": "click"},
                {"element": "Discount code input", "selector_hint": "input[name='discount']", "interaction_type": "form_submit"},
                {"element": "Order note textarea", "selector_hint": "textarea[name='note']", "interaction_type": "input_change"},
            ],
            trackable_actions=[
                {"action": "User views cart", "business_value": "Key conversion funnel step — user is evaluating purchase", "frequency": "expected_high"},
                {"action": "User changes item quantity", "business_value": "Indicates price sensitivity or commitment changes", "frequency": "expected_medium"},
                {"action": "User removes item from cart", "business_value": "Identifies products or friction points causing drop-off", "frequency": "expected_medium"},
                {"action": "User clicks checkout", "business_value": "Critical funnel transition — begin_checkout event", "frequency": "expected_high"},
                {"action": "User applies discount code", "business_value": "Measures coupon usage and marketing campaign effectiveness", "frequency": "expected_low"},
            ],
            data_points=[
                {"name": "cart_items", "source": "Cart line items", "example_value": "[{item_id: '...', item_name: 'Classic Logo Tee', quantity: 1, price: 38.00}]"},
                {"name": "cart_total", "source": "Cart subtotal element", "example_value": "76.00"},
                {"name": "currency", "source": "Store currency", "example_value": "USD"},
                {"name": "coupon", "source": "Discount code input", "example_value": "OAKLAND20"},
            ],
            recommended_events=[
                {
                    "event_name": "page_view",
                    "trigger_description": "Fires on cart page load",
                    "parameters": {"page_title": "Cart page title", "page_location": "Full URL"},
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "view_cart",
                    "trigger_description": "Fires on cart page load with full cart contents",
                    "parameters": {
                        "currency": "USD",
                        "value": "Cart subtotal",
                        "items": "Array of all cart items with full item details",
                    },
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "remove_from_cart",
                    "trigger_description": "Fires when user removes an item or decrements quantity to zero",
                    "parameters": {
                        "currency": "USD",
                        "value": "Value of removed item(s)",
                        "items": "Array with removed item details",
                    },
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "begin_checkout",
                    "trigger_description": "Fires when user clicks the Checkout button",
                    "parameters": {
                        "currency": "USD",
                        "value": "Cart total at checkout initiation",
                        "coupon": "Applied discount code, if any",
                        "items": "Full array of items being checked out",
                    },
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "apply_coupon",
                    "trigger_description": "Fires when user successfully applies a discount code",
                    "parameters": {
                        "coupon": "The discount code applied",
                    },
                    "is_standard": False,
                    "priority": "medium",
                },
            ],
        ),
        PageAnalysis(
            url="https://www.oaklandish.com/blogs/news",
            page_type="blog_index",
            page_purpose="Blog listing page that showcases news articles, artist features, and community stories to build brand engagement.",
            interactive_elements=[
                {"element": "Blog post cards (image + title + excerpt)", "selector_hint": ".blog-post-card, .article-card", "interaction_type": "click"},
                {"element": "Read more links", "selector_hint": ".read-more, .article-card a", "interaction_type": "click"},
                {"element": "Pagination links", "selector_hint": ".pagination a", "interaction_type": "click"},
            ],
            trackable_actions=[
                {"action": "User views blog index", "business_value": "Measures content marketing reach and brand engagement", "frequency": "expected_medium"},
                {"action": "User clicks a blog post", "business_value": "Measures content appeal and which stories drive engagement", "frequency": "expected_medium"},
                {"action": "User navigates to next page of posts", "business_value": "Shows depth of content consumption", "frequency": "expected_low"},
            ],
            data_points=[
                {"name": "page_location", "source": "URL", "example_value": "https://www.oaklandish.com/blogs/news"},
                {"name": "content_group", "source": "Blog section", "example_value": "Blog"},
            ],
            recommended_events=[
                {
                    "event_name": "page_view",
                    "trigger_description": "Fires on blog index load",
                    "parameters": {"page_title": "Blog page title", "page_location": "Full URL", "content_group": "Blog"},
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "select_content",
                    "trigger_description": "Fires when user clicks a blog post card",
                    "parameters": {
                        "content_type": "blog_post",
                        "item_id": "Blog post slug/handle",
                    },
                    "is_standard": True,
                    "priority": "medium",
                },
            ],
        ),
        PageAnalysis(
            url="https://www.oaklandish.com/pages/retail",
            page_type="info_page",
            page_purpose="Store locator page listing physical retail locations with addresses, hours, and directions to help drive in-store visits.",
            interactive_elements=[
                {"element": "Store address/map links", "selector_hint": ".store-location a, a[href*='maps']", "interaction_type": "click"},
                {"element": "Phone number links", "selector_hint": "a[href^='tel:']", "interaction_type": "click"},
                {"element": "Store detail sections", "selector_hint": ".store-card, .location-block", "interaction_type": "scroll"},
            ],
            trackable_actions=[
                {"action": "User views store locator page", "business_value": "Indicates intent to visit physical store — omnichannel signal", "frequency": "expected_medium"},
                {"action": "User clicks store address/directions", "business_value": "Strong in-store visit intent signal", "frequency": "expected_medium"},
                {"action": "User clicks phone number", "business_value": "Direct contact intent — potential high-value customer", "frequency": "expected_low"},
            ],
            data_points=[
                {"name": "store_name", "source": "Store location heading", "example_value": "Oaklandish Downtown Shop"},
                {"name": "store_address", "source": "Address element", "example_value": "1444 Broadway, Oakland, CA 94612"},
            ],
            recommended_events=[
                {
                    "event_name": "page_view",
                    "trigger_description": "Fires on store locator page load",
                    "parameters": {"page_title": "Page title", "page_location": "Full URL", "content_group": "Store Info"},
                    "is_standard": True,
                    "priority": "high",
                },
                {
                    "event_name": "store_directions_click",
                    "trigger_description": "Fires when user clicks a map/directions link for a store",
                    "parameters": {
                        "store_name": "Name of store location",
                        "store_address": "Store address",
                    },
                    "is_standard": False,
                    "priority": "medium",
                },
                {
                    "event_name": "store_phone_click",
                    "trigger_description": "Fires when user clicks a store phone number",
                    "parameters": {
                        "store_name": "Name of store location",
                        "link_url": "tel: link value",
                    },
                    "is_standard": False,
                    "priority": "medium",
                },
            ],
        ),
    ]
    return analyses
