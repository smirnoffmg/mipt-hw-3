# Парсер книг

Веб-скрапер для сбора данных о книгах с сайта Books to Scrape (http://books.toscrape.com).

## Описание

Проект реализует автоматический сбор данных о книгах:
- Извлечение данных об одной книге
- Парсинг всего каталога
- Автоматическое ежедневное выполнение
- Юнит-тесты
- Работа с Git

## Установка

```bash
git clone <repository-url>
cd mipt-hw-3
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Использование

```python
from scraper import get_book_data, scrape_books

# Парсинг одной книги
book_data = get_book_data('http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html')

# Парсинг всех книг с сохранением
all_books = scrape_books(save_to_file=True)

# Автоматическое выполнение каждый день в 19:00
from scraper import run_scheduler
run_scheduler()
```

## Структура проекта

```
mipt-hw-3/
├── artifacts/           # Результаты парсинга
├── notebooks/           # Jupyter notebook
├── tests/              # Тесты
├── scraper.py          # Основной код
├── requirements.txt    # Зависимости
└── README.md          # Документация
```

## Тестирование

```bash
pytest tests/
```

## Зависимости

- `requests` - HTTP запросы
- `beautifulsoup4` - Парсинг HTML
- `schedule` - Автоматизация задач
- `pytest` - Тестирование

## Максим, откуда тут этот репозиторий?

Проект выполнен в рамках изучения "Программирование на Python" МФТИ.