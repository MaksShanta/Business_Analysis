import os
import re
import csv
import json
import sqlite3
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from requests import get
from bs4 import BeautifulSoup


BASE_URL = "https://books.toscrape.com/"
START_URL = f"{BASE_URL}index.html"
HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
}

DATA_DIR = "data"
IMAGES_DIR = os.path.join(DATA_DIR, "images")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

print(" Завдання 2: Перевірка статичності та завантаження")
page = get(START_URL, headers=HEADERS)
print(f"Статус відповіді сервера: {page.status_code}")

if page.status_code != 200:
    print(f"Помилка завантаження: {page.status_code}")
    exit()

# Виведення в консоль фрагмента сторінки
print("\n Фрагмент завантаженого коду сторінки ")
print(page.text[:400])
print("--------------------------------------------\n")

soup = BeautifulSoup(page.content, "html.parser")
# Знаходимо блок бічних категорій через find та find_all
side_categories = soup.find(class_="side_categories")
category_list = side_categories.find("ul").find("li").find("ul")
category_items = category_list.find_all("li")

print(f"Підтвердження статичності: виявлено {len(category_items)} підрозділів у розмітці HTML.")

print("\n Завдання 3: Парсинг підрозділів та збереження у TXT і XML")

divisions = []
DIVISIONS_TXT = os.path.join(DATA_DIR, "divisions.txt")

with open(DIVISIONS_TXT, "w", encoding="utf-8") as file:
    for li in category_items:
        a = li.find("a")
        cat_name = a.find(string=True, recursive=False).strip()
        cat_url = urljoin(BASE_URL, a.get("href"))
        
        divisions.append({"name": cat_name, "url": cat_url})
        
        file.write(f"Назва підрозділу: {cat_name}\n")
        file.write(f"URL: {cat_url}\n")
        file.write("-" * 40 + "\n")

print(f"1. Текстовий файл збережено: {DIVISIONS_TXT} ({len(divisions)} записів)")

# Збереження у формат XML
DIVISIONS_XML = os.path.join(DATA_DIR, "divisions.xml")
root = ET.Element("divisions")
for item in divisions:
    div_node = ET.SubElement(root, "division")
    name_node = ET.SubElement(div_node, "name")
    name_node.text = item["name"]
    url_node = ET.SubElement(div_node, "url")
    url_node.text = item["url"]

tree = ET.ElementTree(root)
ET.indent(tree, space="  ", level=0)
tree.write(DIVISIONS_XML, encoding="utf-8", xml_declaration=True)
print(f"2. XML-файл збережено: {DIVISIONS_XML}")

print("\nЗавдання 4: Скрапінг об'єктів (книг) з підрозділів")

selected_divisions = divisions[:2]
all_books = []
count_books = 0

BOOKS_TXT = os.path.join(DATA_DIR, "books.txt")

with open(BOOKS_TXT, "w", encoding="utf-8") as file:
    for division in selected_divisions:
        cat_name = division["name"]
        cat_url = division["url"]
        
        print(f"\nОбробка підрозділу: '{cat_name}'")
        file.write(f"=== ПІДРОЗДІЛ: {cat_name} ===\n")
        
        # Завантаження сторінки обраного підрозділу
        cat_page = get(cat_url, headers=HEADERS)
        cat_soup = BeautifulSoup(cat_page.content, "html.parser")
        
        # Знаходимо список карток книг (class_="product_pod")
        book_cards = cat_soup.find_all("article", class_="product_pod")
        
        for card in book_cards:
            # Знаходимо посилання та назву книги
            title_tag = card.find("h3").find("a")
            title = title_tag.get("title") if title_tag.get("title") else title_tag.find(string=True, recursive=False)
            book_url = urljoin(cat_url, title_tag.get("href"))
            
            # Знаходимо ціну товару 
            price_tag = card.find(class_="price_color")
            price = price_tag.find(string=True, recursive=False).strip() if price_tag else "N/A"
            
            # Статус наявності
            avail_tag = card.find(class_="availability")
            availability = avail_tag.get_text(strip=True) if avail_tag else "N/A"
            
            # Рейтинг за класом
            rating_tag = card.find(class_="star-rating")
            rating = "No rating"
            if rating_tag:
                classes = [c for c in rating_tag.get("class", []) if c != "star-rating"]
                rating = classes[0] if classes else "No rating"
                
            # Посилання на зображення обкладинки
            img_tag = card.find(class_="image_container").find("img")
            img_url = urljoin(cat_url, img_tag.get("src")) if img_tag else ""
            
            file.write(f"    Назва: {title}\n")
            file.write(f"    Ціна: {price}\n")
            file.write(f"    Наявність: {availability}\n")
            file.write(f"    Рейтинг: {rating}\n")
            file.write(f"    URL: {book_url}\n")
            file.write("-" * 30 + "\n")
            
            all_books.append({
                "category": cat_name,
                "title": title,
                "price": price,
                "availability": availability,
                "rating": rating,
                "product_url": book_url,
                "image_url": img_url,
                "local_image_path": ""
            })
            count_books += 1

print(f"Знайдено та збережено {count_books} об'єктів у {BOOKS_TXT}")

# Збереження списку об'єктів у JSON
BOOKS_JSON = os.path.join(DATA_DIR, "books.json")
with open(BOOKS_JSON, "w", encoding="utf-8") as json_file:
    json.dump(all_books, json_file, ensure_ascii=False, indent=4)
print(f"Дані збережено у JSON: {BOOKS_JSON}")


print("\n Завдання 5: Завантаження медіа та формування реєстрів ")

def sanitize_filename(name: str) -> str:
    clean_name = re.sub(r'[<>:"/\\|?*]', '_', name)
    return clean_name.strip()[:50]

images_meta = []

for idx, book in enumerate(all_books, start=1):
    img_url = book["image_url"]
    if not img_url:
        continue

    safe_title = sanitize_filename(book["title"])
    filename = f"{idx}_{safe_title}.jpg"
    local_path = os.path.join(IMAGES_DIR, filename)

    try:
        img_response = get(img_url, headers=HEADERS, timeout=10)
        if img_response.status_code == 200:
            with open(local_path, "wb") as f_img:
                f_img.write(img_response.content)

            book["local_image_path"] = local_path
            images_meta.append({
                "book_title": book["title"],
                "filename": filename,
                "local_path": local_path,
                "image_url": img_url
            })
            print(f"Збережено обкладинку [{idx}/{len(all_books)}]: {filename}")
    except Exception as err:
        print(f"Помилка завантаження фото {img_url}: {err}")

# Текстовий реєстр зображень
IMAGES_TXT = os.path.join(DATA_DIR, "images.txt")
with open(IMAGES_TXT, "w", encoding="utf-8") as file:
    for item in images_meta:
        file.write(f"Об'єкт: {item['book_title']}\n")
        file.write(f"Файл: {item['filename']}\n")
        file.write(f"Шлях: {item['local_path']}\n")
        file.write(f"URL: {item['image_url']}\n")
        file.write("-" * 40 + "\n")
print(f"1. Текстовий реєстр зображень збережено: {IMAGES_TXT}")

# Табличний реєстр зображень у CSV
IMAGES_CSV = os.path.join(DATA_DIR, "images.csv")
with open(IMAGES_CSV, "w", encoding="utf-8-sig", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=["book_title", "filename", "local_path", "image_url"], delimiter=";")
    writer.writeheader()
    writer.writerows(images_meta)
print(f"2. CSV реєстр зображень збережено: {IMAGES_CSV}")

print("\n Завдання 6: Збереження даних у реляційну БД SQLite")

DB_PATH = os.path.join(DATA_DIR, "books_data.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("PRAGMA foreign_keys = ON;")

# Таблиця підрозділів (категорій)
cursor.execute("""
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL
);
""")

# Таблиця об'єктів зі зв'язком 1-до-багатьох
cursor.execute("""
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    price TEXT,
    availability TEXT,
    rating TEXT,
    product_url TEXT,
    image_url TEXT,
    local_image_path TEXT,
    FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE
);
""")

# Вставка категорій
for cat in divisions:
    cursor.execute("""
        INSERT OR IGNORE INTO categories (name, url)
        VALUES (?, ?);
    """, (cat["name"], cat["url"]))

conn.commit()

# Отримання словника id категорій
cursor.execute("SELECT id, name FROM categories;")
category_map = {name: cat_id for cat_id, name in cursor.fetchall()}

# Вставка об'єктів (книг)
for book in all_books:
    cat_id = category_map.get(book["category"])
    if cat_id:
        cursor.execute("""
            INSERT INTO books (
                category_id, title, price, availability, rating, 
                product_url, image_url, local_image_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            cat_id,
            book["title"],
            book["price"],
            book["availability"],
            book["rating"],
            book["product_url"],
            book["image_url"],
            book["local_image_path"]
        ))

conn.commit()

# Контрольна вибірка через JOIN для перевірки цілісності
print("\n Контрольна вибірка з бази даних (JOIN) ")
cursor.execute("""
    SELECT c.name, b.title, b.price, b.rating, b.local_image_path
    FROM books b
    JOIN categories c ON b.category_id = c.id
    LIMIT 5;
""")

for row in cursor.fetchall():
    print(f"[{row[0]}] {row[1][:25]}... | Ціна: {row[2]} | Оцінка: {row[3]} | Фото: {row[4]}")

cursor.execute("SELECT COUNT(*) FROM categories;")
count_cats = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM books;")
count_bks = cursor.fetchone()[0]

print(f"\nБазу даних успішно заповнено: {count_cats} категорій та {count_bks} об'єктів збережено.")
conn.close()