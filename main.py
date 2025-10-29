import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import networkx as nx
import pandas as pd
import sqlite3
import os
import logging
import time
import config as cfg


# Настройка логирования
logging.basicConfig(level=cfg.LOGGING_LEVEL, format=cfg.LOGGING_FORMAT)

start_time = time.time()  # Запоминаем время начала работы скрипта
page_count = 0  # Счетчик обработанных страниц

def remove_existing_files(db_path, excel_path):
    if os.path.isfile(db_path):
        os.remove(db_path)
    if os.path.isfile(excel_path):
        os.remove(excel_path)

# Создаем базу данных
def create_database(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS pages
                      (url TEXT PRIMARY KEY, title TEXT, h1 TEXT, text_length INTEGER, status_code TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS links
                      (source_url TEXT, destination_url TEXT, anchor_text TEXT,
                      FOREIGN KEY (source_url) REFERENCES pages (url))''')
    conn.commit()
    conn.close()

def is_valid_link(link_url, domain):
    """ Проверяет, допустима ли ссылка для добавления в стек. """
    parsed_url = urlparse(link_url)
    # Проверяем, что домен совпадает
    if parsed_url.netloc != domain:
        return False
    # Проверяем, начинается ли путь URL с указанного пути в START_PATH
    if cfg.START_PATH and not parsed_url.path.startswith(cfg.START_PATH):
        return False
    # Игнорируем якоря (фрагменты)
    if parsed_url.fragment:
        return False
    # Игнорируем параметры запроса, если настройка включена
    if cfg.IGNORE_QUERY_PARAMS and parsed_url.query:
        return False
    # Игнорируем файлы (изображения, документы, архивы и т.д.)
    # Разрешаем HTML страницы, чистые URL и URL с /
    file_extensions_to_ignore = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx',
                                   '.xls', '.xlsx', '.zip', '.rar', '.css', '.js', '.xml',
                                   '.json', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot']
    if any(parsed_url.path.lower().endswith(ext) for ext in file_extensions_to_ignore):
        return False
    return True

# Получаем данные со страницы
def get_page_data(url, cursor, domain):
    global page_count
    page_count += 1
    elapsed_time = time.time() - start_time
    time_str = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
    print(f"Time: {time_str} | Page № {page_count} | Fetching data from: {url}")

    # Задержка перед запросом для избежания перегрузки сервера
    if page_count > 1:
        time.sleep(cfg.REQUEST_DELAY)

    # Retry логика
    response = None
    status_code = 'Fetch Error'
    headers = {'User-Agent': cfg.USER_AGENT}

    for attempt in range(cfg.MAX_RETRIES):
        try:
            response = requests.get(url, timeout=cfg.TIMEOUT, headers=headers)
            break  # Успешный запрос, выходим из цикла
        except requests.exceptions.Timeout:
            logging.warning(f"Timeout on {url}, attempt {attempt + 1}/{cfg.MAX_RETRIES}")
            if attempt == cfg.MAX_RETRIES - 1:
                logging.error(f"Failed to fetch {url} after {cfg.MAX_RETRIES} attempts (timeout)")
                return 'Timeout'
            time.sleep(2 ** attempt)  # Экспоненциальная задержка: 1s, 2s, 4s
        except requests.exceptions.RequestException as e:
            logging.warning(f"Request error on {url}: {str(e)}, attempt {attempt + 1}/{cfg.MAX_RETRIES}")
            if attempt == cfg.MAX_RETRIES - 1:
                logging.error(f"Failed to fetch {url} after {cfg.MAX_RETRIES} attempts: {str(e)}")
                return 'Request Error'
            time.sleep(2 ** attempt)

    # Если response None (не должно быть после retry), возвращаем ошибку
    if response is None:
        return 'Fetch Error'

    try:
        status_code = str(response.status_code)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Извлекаем метаданные страницы перед фильтрацией
            title = soup.title.string if soup.title else "No title"
            h1 = soup.h1.string if soup.h1 else "No H1 tag"
            body_content = ''.join(soup.body.stripped_strings) if soup.body else ""
            text_length = len(body_content)
            status_code = response.status_code

            # Сохраняем данные страницы в БД
            cursor.execute('INSERT OR REPLACE INTO pages (url, title, h1, text_length, status_code) VALUES (?, ?, ?, ?, ?)',
                           (url, title, h1, text_length, status_code))

            # Теперь фильтруем soup для извлечения только нужных ссылок
            # Удаление элементов с указанными классами
            for excluded_class in cfg.EXCLUDED_CLASSES:
                for tag in soup.find_all(class_=excluded_class):
                    tag.decompose()

            # Удаление элементов с указанными ID
            for excluded_id in cfg.EXCLUDED_IDS:
                tag = soup.find(id=excluded_id)
                if tag:
                    tag.decompose()

            # Удаление элементов с указанными тегами
            for tag in soup.find_all(cfg.EXCLUDED_TAGS):
                tag.decompose()

            # Изменение: игнорирование ссылок до <h1>
            h1_tag = soup.find('h1')
            if h1_tag and cfg.EXCLUDED_LINKS_BEFORE_H1:
                for a in soup.find_all('a', href=True):
                    if a.find_previous('h1') is None:
                        a.decompose()

            # Изменение: игнорирование ссылок из StopLinkList
            for a in soup.find_all('a', href=True):
                link_url = urljoin(url, a.get('href'))
                if link_url in cfg.STOP_LINK_LINKS:
                    a.decompose()

            # Вставляем ссылки
            for a in soup.find_all('a', href=True):
                link_url = urljoin(url, a.get('href'))
                if is_valid_link(link_url, domain):
                    anchor = a.get_text(strip=True)
                    cursor.execute('INSERT INTO links (source_url, destination_url, anchor_text) VALUES (?, ?, ?)',
                                   (url, link_url, anchor))
        else:
            # Сохраняем информацию о странице с не-200 статусом
            cursor.execute('INSERT OR REPLACE INTO pages (url, title, h1, text_length, status_code) VALUES (?, ?, ?, ?, ?)',
                           (url, "Error page", "No H1", 0, status_code))
        return status_code
    except Exception as e:
        logging.error(f"Error parsing {url}: {str(e)}")
        print(f"Error parsing {url}: {str(e)}")
        return 'Parse Error'


# Рекурсивный обход сайта и другие функции...
def crawl_site(start_url, domain, cursor, filters=None):
    """ Рекурсивный обход сайта. """
    stack = [start_url]
    visited_pages = set()  # Используем множество для отслеживания посещенных страниц

    while stack:
        current_url = stack.pop()

        if current_url not in visited_pages:
            status_code = get_page_data(current_url, cursor, domain)
            visited_pages.add(current_url)  # Добавляем URL в множество посещенных

            # Получаем ссылки только если страница была успешно получена
            if status_code == 200:
                cursor.execute("SELECT destination_url FROM links WHERE source_url=?", (current_url,))
                links = cursor.fetchall()
                for link in links:
                    link_url = link[0]
                    if link_url not in visited_pages and (filters is None or all(f(link_url) for f in filters)):
                        stack.append(link_url)

            # Сохраняем изменения в БД после обработки каждой страницы
            cursor.connection.commit()

def calculate_internal_pagerank(cursor, damping_factor=0.85):
    print("Calculating PageRank...")

    # Создаем граф из данных в БД
    site_graph = nx.DiGraph()
    cursor.execute('SELECT source_url, destination_url FROM links')
    links = cursor.fetchall()
    for source, destination in links:
        site_graph.add_edge(source, destination)

    # Расчет PageRank
    pageranks = nx.pagerank(site_graph, alpha=damping_factor)
    return site_graph, pageranks

def export_data_to_excel(site_graph, pageranks, cursor, db_file):
    output_filename = f'data_{cfg.DB_FILE.split(".")[0]}.xlsx'
    excel_file = os.path.join(cfg.OUTPUT_DIR, output_filename)

    # Ensure the output directory exists
    if not os.path.exists(cfg.OUTPUT_DIR):
        os.makedirs(cfg.OUTPUT_DIR)

    # Получение данных о страницах и якорных текстах из базы данных
    cursor.execute('SELECT url, title, status_code FROM pages')
    pages_rows = cursor.fetchall()

    cursor.execute('SELECT source_url, destination_url, anchor_text FROM links')
    links_rows = cursor.fetchall()

    # Формирование данных для "Page Data"
    pages_data = []
    for page in pages_rows:
        url, title, status_code = page
        # Проверяем, существует ли страница в графе перед получением ссылок
        if url in site_graph:
            incoming_links = len(list(site_graph.predecessors(url)))
            outgoing_links = len(list(site_graph.successors(url)))
        else:
            incoming_links = 0
            outgoing_links = 0
        anchor_text_count = sum(1 for link in links_rows if link[1] == url)
        pagerank = pageranks.get(url, 0)
        pages_data.append([url, title, incoming_links, outgoing_links, anchor_text_count, pagerank, status_code])

    # Формирование данных для "Anchor Data"
    anchor_texts = {}
    for link in links_rows:
        source_url, destination_url, anchor_text = link
        if anchor_text:
            if (anchor_text, destination_url) not in anchor_texts:
                anchor_texts[(anchor_text, destination_url)] = 0
            anchor_texts[(anchor_text, destination_url)] += 1
    anchor_data = [[anchor, url, count] for (anchor, url), count in anchor_texts.items()]

    # Формирование данных для "Error Data"
    error_data = [[url, title, status_code] for url, title, status_code in pages_rows if status_code != '200']

    # Экспорт данных в Excel
    with pd.ExcelWriter(excel_file) as writer:
        pd.DataFrame(pages_data, columns=['URL', 'Title', 'Incoming Links', 'Outgoing Links', 'Anchor Text Count', 'PageRank', 'Status Code']).to_excel(writer, sheet_name='Page Data', index=False)
        pd.DataFrame(anchor_data, columns=['Anchor Text', 'URL', 'Occurrences']).to_excel(writer, sheet_name='Anchor Data', index=False)
        pd.DataFrame(error_data, columns=['URL', 'Title', 'Status Code']).to_excel(writer, sheet_name='Error Data', index=False)

    print(f"Data exported to {excel_file}")


# Функция main теперь использует глобальные переменные
def main():
    # Ensure the output directory exists
    if not os.path.exists(cfg.OUTPUT_DIR):
        os.makedirs(cfg.OUTPUT_DIR)

    db_path = os.path.join(cfg.OUTPUT_DIR, cfg.DB_FILE)

    # Remove existing files if they exist
    remove_existing_files(db_path, db_path.replace('.db', '.xlsx'))

    # Create a new database
    create_database(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        domain = urlparse(cfg.START_URL).netloc

        # Crawl the site and process data
        crawl_site(cfg.START_URL, domain, cursor)
        site_graph, pageranks = calculate_internal_pagerank(cursor)

        # Export data to Excel
        export_data_to_excel(site_graph, pageranks, cursor, db_path)

if __name__ == '__main__':
    main()
