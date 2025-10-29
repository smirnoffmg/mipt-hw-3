from unittest.mock import Mock, patch

import pytest

from scraper import BookData, get_book_data, scrape_books


@pytest.fixture
def sample_html():
    """Sample HTML content for testing book data extraction."""
    return """
    <html>
        <body>
            <h1>Test Book Title</h1>
            <p class="price_color">£51.77</p>
            <p class="star-rating Three"></p>
            <p class="instock availability">In stock (22 available)</p>
            <div id="product_description"></div>
            <p>Test book description</p>
            <table class="table table-striped">
                <tr>
                    <th>UPC</th>
                    <td>a897fe39b1053632</td>
                </tr>
                <tr>
                    <th>Product Type</th>
                    <td>Books</td>
                </tr>
            </table>
        </body>
    </html>
    """


@pytest.fixture
def sample_book_data():
    """Sample BookData object for testing."""
    return BookData(
        title="Test Book Title",
        price="£51.77",
        rating="Three",
        availability="In stock (22 available)",
        description="Test book description",
        product_info={"UPC": "a897fe39b1053632", "Product Type": "Books"},
    )


@pytest.fixture
def sample_urls():
    """Sample book URLs for testing."""
    return [
        "http://books.toscrape.com/catalogue/book1/index.html",
        "http://books.toscrape.com/catalogue/book2/index.html",
        "http://books.toscrape.com/catalogue/book3/index.html",
    ]


class TestGetBookData:
    """Test cases for get_book_data function."""

    @patch("scraper.requests.get")
    def test_get_book_data_returns_dict_with_required_keys(self, mock_get, sample_html):
        """Test that get_book_data returns BookData with all required fields."""
        # Arrange
        mock_response = Mock()
        mock_response.content = sample_html.encode("utf-8")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        test_url = "http://books.toscrape.com/catalogue/test-book/index.html"

        # Act
        result = get_book_data(test_url)

        # Assert
        assert result is not None
        assert isinstance(result, BookData)
        assert hasattr(result, "title")
        assert hasattr(result, "price")
        assert hasattr(result, "rating")
        assert hasattr(result, "availability")
        assert hasattr(result, "description")
        assert hasattr(result, "product_info")

        assert isinstance(result.title, str)
        assert isinstance(result.price, str)
        assert isinstance(result.rating, str)
        assert isinstance(result.availability, str)
        assert isinstance(result.description, str)
        assert isinstance(result.product_info, dict)

    @patch("scraper.requests.get")
    def test_book_data_fields_are_correct(self, mock_get, sample_html):
        """Test that extracted values match expected values."""
        # Arrange
        mock_response = Mock()
        mock_response.content = sample_html.encode("utf-8")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        test_url = "http://books.toscrape.com/catalogue/test-book/index.html"

        # Act
        result = get_book_data(test_url)

        # Assert
        assert result.title == "Test Book Title"
        assert result.price == "£51.77"
        assert result.rating == "Three"
        assert result.availability == "In stock (22 available)"
        assert result.description == "Test book description"
        assert result.product_info["UPC"] == "a897fe39b1053632"
        assert result.product_info["Product Type"] == "Books"

    @patch("scraper.requests.get")
    def test_get_book_data_handles_network_error(self, mock_get):
        """Test that get_book_data handles network errors gracefully."""
        # Arrange
        mock_get.side_effect = Exception("Network error")
        test_url = "http://books.toscrape.com/catalogue/test-book/index.html"

        # Act
        result = get_book_data(test_url)

        # Assert
        assert result is None


class TestScrapeBooks:
    """Test cases for scrape_books function."""

    @patch("scraper.get_book_data")
    @patch("scraper._collect_book_urls")
    def test_scrape_books_returns_list(
        self, mock_collect_urls, mock_get_book, sample_urls, sample_book_data
    ):
        """Test that scrape_books returns a list of BookData objects."""
        # Arrange
        mock_collect_urls.return_value = sample_urls
        mock_get_book.return_value = sample_book_data

        # Act
        result = scrape_books(is_save=False)

        # Assert
        assert isinstance(result, list)
        assert len(result) == len(sample_urls)
        for book in result:
            assert isinstance(book, BookData)
            assert book.title == "Test Book Title"

    @patch("scraper.get_book_data")
    @patch("scraper._collect_book_urls")
    def test_scrape_books_handles_empty_catalog(self, mock_collect_urls, mock_get_book):
        """Test that scrape_books handles empty catalog gracefully."""
        # Arrange
        mock_collect_urls.return_value = []

        # Act
        result = scrape_books(is_save=False)

        # Assert
        assert isinstance(result, list)
        assert len(result) == 0

    @patch("scraper.get_book_data")
    @patch("scraper._collect_book_urls")
    def test_scrape_books_handles_failed_scraping(
        self, mock_collect_urls, mock_get_book, sample_urls
    ):
        """Test that scrape_books handles failed individual book scraping."""
        # Arrange
        mock_collect_urls.return_value = sample_urls
        mock_get_book.side_effect = [
            BookData("Book1", "£10", "One", "In stock", "Desc1", {}),
            None,  # This one fails
            BookData("Book3", "£30", "Three", "In stock", "Desc3", {}),
        ]

        # Act
        result = scrape_books(is_save=False)

        # Assert
        assert isinstance(result, list)
        assert len(result) == 2  # Only 2 successful scrapes

        titles = [book.title for book in result]
        assert "Book1" in titles
        assert "Book3" in titles


class TestCollectBookUrls:
    """Test cases for _collect_book_urls function."""

    @patch("scraper.requests.get")
    def test_collect_book_urls_returns_list(self, mock_get):
        """Test that _collect_book_urls returns a list of URLs."""
        # Arrange
        catalog_html = """
        <html>
            <body>
                <article class="product_pod">
                    <h3><a href="book1/index.html">Book 1</a></h3>
                </article>
                <article class="product_pod">
                    <h3><a href="book2/index.html">Book 2</a></h3>
                </article>
            </body>
        </html>
        """

        # Mock first page returns books, second page returns 404 to stop loop
        def side_effect(url, **kwargs):
            mock_response = Mock()
            if "page-1.html" in url:
                mock_response.status_code = 200
                mock_response.content = catalog_html.encode("utf-8")
            else:
                mock_response.status_code = 404
                mock_response.content = b"Not found"
            return mock_response

        mock_get.side_effect = side_effect

        # Act
        from scraper import _collect_book_urls

        result = _collect_book_urls()

        # Assert
        assert isinstance(result, list)
        assert len(result) == 2  # Should return 2 URLs from first page

    @patch("scraper.requests.get")
    def test_collect_book_urls_handles_no_books(self, mock_get):
        """Test that _collect_book_urls handles pages with no books."""
        # Arrange
        empty_html = "<html><body></body></html>"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = empty_html.encode("utf-8")
        mock_get.return_value = mock_response

        # Act
        from scraper import _collect_book_urls

        result = _collect_book_urls()

        # Assert
        assert isinstance(result, list)
        assert len(result) == 0
