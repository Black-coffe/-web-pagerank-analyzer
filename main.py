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

# Далее идет остальная часть скрипта...
def get_links(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)
        return [link['href'] for link in links]
    except Exception as e:
        logging.error(f"Error fetching links from {url}: {str(e)}")
        return []

def aggregate_anchor_texts(visited_pages, cursor):
    logging.info("Aggregating anchor texts...")
    anchor_texts = {}
    for url in visited_pages:
        cursor.execute("SELECT anchor_text, destination_url FROM links WHERE source_url=?", (url,))
        rows = cursor.fetchall()
        for row in rows:
            anchor = row[0]
            link_url = row[1]
            if anchor:
                if (anchor, link_url) not in anchor_texts:
                    anchor_texts[(anchor, link_url)] = 0
                anchor_texts[(anchor, link_url)] += 1
    logging.info("Anchor text aggregation completed.")
    return anchor_texts

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
    # Игнорируем ссылки с параметрами запроса или якорями
    if parsed_url.query or parsed_url.fragment:
        return False
    # Игнорируем не-HTML страницы (например, ссылки на файлы)
    if not (parsed_url.path.endswith('/') or parsed_url.path.endswith('.html') or parsed_url.path.endswith('.htm')):
        return False
    return True

# Получаем данные со страницы
def get_page_data(url, cursor, domain):
    global page_count
    page_count += 1
    elapsed_time = time.time() - start_time
    time_str = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
    print(f"Time: {time_str} | Page № {page_count} | Fetching data from: {url}")
    try:
        response = requests.get(url, timeout=cfg.TIMEOUT)
        # По умолчанию статус кода - ошибка, если не удастся получить страницу
        status_code = 'Fetch Error'
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string if soup.title else "No title"
            h1 = soup.h1.string if soup.h1 else "No H1 tag"
            body_content = ''.join(soup.body.stripped_strings)
            text_length = len(body_content)
            status_code = response.status_code

            # Изменение: исключение ссылок в определенных классах, ID и тегах
            content_soup = BeautifulSoup(response.text, 'html.parser')

            # Удаление элементов с указанными классами
            for excluded_class in cfg.EXCLUDED_CLASSES:
                for tag in content_soup.find_all(class_=excluded_class):
                    tag.decompose()

            # Удаление элементов с указанными ID
            for excluded_id in cfg.EXCLUDED_IDS:
                tag = content_soup.find(id=excluded_id)
                if tag:
                    tag.decompose()

            # Удаление элементов с указанными тегами
            for tag in content_soup.find_all(cfg.EXCLUDED_TAGS):
                tag.decompose()

            # Изменение: игнорирование ссылок до <h1>
            h1_tag = content_soup.find('h1')
            if h1_tag and cfg.EXCLUDED_LINKS_BEFORE_H1:
                for a in content_soup.find_all('a', href=True):
                    if a.find_previous('h1') is None:
                        a.decompose()

            # Изменение: игнорирование ссылок из StopLinkList
            for a in content_soup.find_all('a', href=True):
                link_url = urljoin(url, a.get('href'))
                if link_url in cfg.STOP_LINK_LINKS:
                    a.decompose()

            cursor.execute('INSERT OR REPLACE INTO pages (url, title, h1, text_length, status_code) VALUES (?, ?, ?, ?, ?)',
                           (url, title, h1, text_length, status_code))

            # Вставляем ссылки
            for a in content_soup.find_all('a', href=True):
                link_url = urljoin(url, a.get('href'))
                if is_valid_link(link_url, domain):
                    anchor = a.get_text(strip=True)
                    cursor.execute('INSERT INTO links (source_url, destination_url, anchor_text) VALUES (?, ?, ?)',
                                   (url, link_url, anchor))
        return status_code
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return 'Fetch Error'


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
        incoming_links = len(list(site_graph.predecessors(url)))
        outgoing_links = len(list(site_graph.successors(url)))
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
