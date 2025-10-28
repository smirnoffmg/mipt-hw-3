import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("scraper.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@dataclass
class BookData:
    """
    Data class to hold book information scraped from Books to Scrape website.

    Attributes:
        title: Book title
        price: Book price as string (e.g., "£51.77")
        rating: Star rating (e.g., "Three", "Four", "Five")
        availability: Stock availability information
        description: Book description text
        product_info: Dictionary containing product information table data
    """

    title: str
    price: str
    rating: str
    availability: str
    description: str
    product_info: Dict[str, str]


def _extract_text(soup: BeautifulSoup, tag: str, default: str, **kwargs) -> str:
    """Extract text from HTML element.

    Args:
        soup: BeautifulSoup object to search in
        tag: HTML tag name to find
        default: Default value to return if element not found
        **kwargs: Additional arguments to pass to find()

    Returns:
        Extracted text or default value if element not found
    """
    element = soup.find(tag, **kwargs)
    return element.get_text(strip=True) if element else default


def _extract_attribute(
    soup: BeautifulSoup, tag: str, attr_name: str, default: str, **kwargs
) -> str:
    """Extract attribute value from HTML element.

    Args:
        soup: BeautifulSoup object to search in
        tag: HTML tag name to find
        attr_name: Name of attribute to extract
        default: Default value to return if attribute not found
        **kwargs: Additional arguments to pass to find()

    Returns:
        Attribute value or default value if not found
    """
    element = soup.find(tag, **kwargs)
    if element and attr_name in element.attrs:
        attr_value = element.attrs[attr_name]
        if isinstance(attr_value, list) and len(attr_value) > 1:
            return attr_value[1]  # For rating: get second class name
        return str(attr_value)
    return default


def _extract_text_from_next_sibling(
    soup: BeautifulSoup, parent_tag: str, sibling_tag: str, default: str, **kwargs
) -> str:
    """Extract text from next sibling element.

    Args:
        soup: BeautifulSoup object to search in
        parent_tag: HTML tag name of parent element
        sibling_tag: HTML tag name of sibling element to find
        default: Default value to return if sibling not found
        **kwargs: Additional arguments to pass to find()

    Returns:
        Text from sibling element or default value if not found
    """
    parent = soup.find(parent_tag, **kwargs)
    if parent:
        sibling = parent.find_next_sibling(sibling_tag)
        if sibling:
            return sibling.get_text(strip=True)
    return default


def _extract_table_data(soup: BeautifulSoup, tag: str, **kwargs) -> Dict[str, str]:
    """Extract key-value pairs from HTML table.

    Args:
        soup: BeautifulSoup object to search in
        tag: HTML tag name of table to find
        **kwargs: Additional arguments to pass to find()

    Returns:
        Dictionary with table data as key-value pairs
    """
    data = {}
    table = soup.find(tag, **kwargs)
    if table:
        rows = table.find_all("tr")
        for row in rows:
            th = row.find("th")
            td = row.find("td")
            if th and td:
                key = th.get_text(strip=True)
                value = td.get_text(strip=True)
                data[key] = value
    return data


def get_book_data(book_url: str) -> Optional[BookData]:
    """
    Scrape book information from a single book page on Books to Scrape website.

    Args:
        book_url: URL of the book page to scrape

    Returns:
        BookData object containing scraped book information, or None if scraping fails
    """
    try:
        response = requests.get(book_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        return BookData(
            title=_extract_text(soup, "h1", "Unknown Title"),
            price=_extract_text(soup, "p", "Price not available", class_="price_color"),
            rating=_extract_attribute(
                soup, "p", "class", "Not rated", class_="star-rating"
            ),
            availability=_extract_text(
                soup, "p", "Availability unknown", class_="instock availability"
            ),
            description=_extract_text_from_next_sibling(
                soup, "div", "p", "No description available", id="product_description"
            ),
            product_info=_extract_table_data(
                soup, "table", class_="table table-striped"
            ),
        )

    except requests.RequestException as e:
        logger.error(f"Network error occurred: {e}")
        return None
    except AttributeError as e:
        logger.error(f"Parsing error occurred: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
        return None


def _collect_book_urls() -> List[str]:
    """Collect all book URLs by iterating through catalog pages.

    Returns:
        List of absolute book URLs from all catalog pages
    """
    book_urls = []
    page = 1
    base_url = "http://books.toscrape.com/catalogue"

    while True:
        # Construct catalog page URL - start with page-1.html
        page_url = f"{base_url}/page-{page}.html"

        try:
            # Fetch and parse catalog page
            response = requests.get(page_url, timeout=10)
            if response.status_code != 200:
                break

            soup = BeautifulSoup(response.content, "html.parser")

            # Find all book links on this catalog page
            articles = soup.find_all("article", class_="product_pod")
            if not articles:
                break

            for article in articles:
                # Extract book URL from article
                link_element = article.find("h3").find("a")
                if link_element:
                    link = link_element["href"]
                    # Convert relative to absolute URL
                    absolute_url = f"http://books.toscrape.com/catalogue/{link}"
                    book_urls.append(absolute_url)

            logger.info(f"Catalog page {page}: found {len(articles)} books")
            page += 1

        except requests.RequestException as e:
            logger.error(f"Error fetching catalog page {page}: {e}")
            break

    return book_urls


def scrape_books(is_save: bool = False, max_workers: int = 10) -> List[BookData]:
    """Scrape all books from Books to Scrape catalog using concurrent execution.

    Args:
        is_save: If True, save results to artifacts/books_data.txt
        max_workers: Number of concurrent workers for parallel scraping

    Returns:
        List of BookData objects for all scraped books
    """
    # Phase 1: Collect all book URLs from catalog pages
    logger.info("Collecting book URLs from catalog pages...")
    book_urls = _collect_book_urls()
    logger.info(f"Found {len(book_urls)} books to scrape")

    if not book_urls:
        logger.info("No books found to scrape")
        return []

    # Phase 2: Scrape books concurrently
    logger.info(f"Scraping books with {max_workers} workers...")
    books = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(get_book_data, url): url for url in book_urls}

        completed = 0
        for future in as_completed(future_to_url):
            book_data = future.result()
            if book_data:
                books.append(book_data)
            completed += 1
            if completed % 100 == 0:
                logger.info(f"Progress: {completed}/{len(book_urls)} books scraped")

    logger.info(f"Successfully scraped {len(books)} books")

    # Save to file if requested
    if is_save:
        output_path = Path("artifacts/books_data.txt")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump([asdict(book) for book in books], f, indent=2, ensure_ascii=False)

        logger.info(f"Saved to {output_path}")

    return books


def run_scheduler():
    """Set up and run the automated daily data collection scheduler.

    The scheduler runs the book scraping function every day at 19:00 (7 PM)
    and saves the results to artifacts/books_data.txt. The function runs in an
    infinite loop with 60-second intervals to check for scheduled tasks.

    The scheduler can be stopped with Ctrl+C (KeyboardInterrupt).
    """
    import schedule

    def scheduled_scraping():
        """Wrapper function for scheduled book scraping.

        Runs the full book scraping process and logs the results.
        """
        logger.info("Starting scheduled book scraping...")

        try:
            # Run the scraping function with file saving enabled
            books = scrape_books(is_save=True, max_workers=5)
            logger.info(f"Successfully scraped {len(books)} books")
            logger.info("Data saved to artifacts/books_data.txt")

        except Exception as e:
            logger.error(f"Error during scheduled scraping: {e}")

    # Schedule the scraping function to run daily at 19:00
    schedule.every().day.at("19:00").do(scheduled_scraping)

    logger.info("Scheduler started! Book scraping is scheduled for 19:00 daily.")
    logger.info("Press Ctrl+C to stop the scheduler.")

    try:
        # Infinite loop to check for scheduled tasks
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute to avoid overloading the system

    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")


if __name__ == "__main__":
    logger.info("Books to Scrape - Web Scraper")
    logger.info("Starting full catalog scrape...")
    logger.info("This will scrape all books and save to artifacts/books_data.txt")

    try:
        # Run full scraper with file saving
        books = scrape_books(is_save=True, max_workers=10)

        logger.info("Scraping completed successfully!")
        logger.info(f"Total books scraped: {len(books)}")
        logger.info("Data saved to: artifacts/books_data.txt")

    except KeyboardInterrupt:
        logger.warning("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
