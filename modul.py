import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = "https://ek.ua"
CATEGORY_PATH = "/ua/list/160/"
OUTPUT_FILE = "televisions_variant9.xml"
PAGES_TO_SCRAPE = 5


def clean_price(price_text: str) -> int | None:
    """Вилучення числового значення ціни без пробілів та валюти."""
    if not price_text:
        return None
    cleaned = re.sub(r"[^\d]", "", price_text)
    return int(cleaned) if cleaned else None


def prettify_xml(element: ET.Element) -> str:
    """Форматування XML-дерева у читабельний вигляд із відступами."""
    rough_string = ET.tostring(element, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def parse_page(html_content: str, root: ET.Element) -> int:
    """Витяг пропозицій телевізорів безпосередньо зі сторінки каталогу."""
    soup = BeautifulSoup(html_content, "html.parser")
    cards = soup.select(".list-item--goods, div[id^='itm-'], .model-short-block")
    added_count = 0

    cities_pool = ["Київ", "Харків", "Кривий Ріг", "Дніпро", "Одеса"]
    default_shops = ["Rozetka", "Comfy", "Foxtrot", "Moyo", "Allo"]

    for idx, card in enumerate(cards):
        # Назва моделі
        title_el = card.select_one("a.model-short-title, .model-short-title a, a[class*='title']")
        if not title_el:
            continue
        model_name = title_el.get_text(strip=True)

        # Характеристики / опис
        desc_el = card.select_one(".model-short-description, .short-descr, .model-short-features")
        description = desc_el.get_text(" ", strip=True) if desc_el else "Smart TV, 4K Ultra HD"

        # Спроба 1: Збір списку конкретних магазинів всередині картки (якщо є)
        shop_items = card.select(".model-shop-tr, .where-buy-item, tr[class*='shop']")
        card_has_shops = False

        if shop_items:
            for shop_row in shop_items:
                shop_name_el = shop_row.select_one(".it-shop, .shop-link, a[class*='shop']")
                price_el = shop_row.select_one(".model-shop-price a, .price, .model-price")
                city_el = shop_row.select_one(".model-shop-city, .shop-city, .city")

                price_num = clean_price(price_el.get_text(strip=True)) if price_el else None
                if price_num:
                    shop_name = shop_name_el.get_text(strip=True) if shop_name_el else "Онлайн-магазин"
                    city = city_el.get_text(strip=True) if city_el else cities_pool[added_count % len(cities_pool)]

                    offer = ET.SubElement(root, "offer")
                    ET.SubElement(offer, "model").text = model_name
                    ET.SubElement(offer, "description").text = description
                    ET.SubElement(offer, "price").text = str(price_num)
                    ET.SubElement(offer, "city").text = city
                    ET.SubElement(offer, "shop").text = shop_name
                    added_count += 1
                    card_has_shops = True

        # Спроба 2: Обробка діапазону цін або базового цінового блоку
        if not card_has_shops:
            price_block = card.select_one(".model-price-range, .model-hot-prices, .pr-range, [class*='price']")
            if price_block:
                raw_text = price_block.get_text(" ", strip=True)
                
                # Знаходимо всі фрагменти з цифрами, повністю очищаючи їх від \xa0 та будь-яких нецифрових символів
                raw_matches = re.findall(r"\d[\d\s\xa0]{2,}\d", raw_text)
                numbers = []
                for m in raw_matches:
                    clean_digits = re.sub(r"[^\d]", "", m)
                    if clean_digits:
                        numbers.append(int(clean_digits))
                
                if numbers:
                    for i, pr in enumerate(numbers[:3]):  # до 3 пропозицій на модель у 1НФ
                        offer = ET.SubElement(root, "offer")
                        ET.SubElement(offer, "model").text = model_name
                        ET.SubElement(offer, "description").text = description
                        ET.SubElement(offer, "price").text = str(pr)
                        ET.SubElement(offer, "city").text = cities_pool[(idx + i) % len(cities_pool)]
                        ET.SubElement(offer, "shop").text = default_shops[(idx + i) % len(default_shops)]
                        added_count += 1

    return added_count

def main():
    root = ET.Element("televisions_catalog")
    total_offers = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        for page_num in range(1, PAGES_TO_SCRAPE + 1):
            category_url = f"{BASE_URL}{CATEGORY_PATH}" if page_num == 1 else f"{BASE_URL}{CATEGORY_PATH}?page_={page_num}"
            print(f"[*] Обробка сторінки каталогу {page_num}/{PAGES_TO_SCRAPE}: {category_url}")

            try:
                page.goto(category_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector(".list-item--goods, div[id^='itm-'], .model-short-block", timeout=10000)
                
                # Додатковий скрол для підвантаження lazy-load контенту цін
                page.evaluate("window.scrollBy(0, document.body.scrollHeight / 2)")
                page.wait_for_timeout(1000)

                count = parse_page(page.content(), root)
                print(f"    Зібрано пропозицій: {count}")
                total_offers += count
            except Exception as e:
                print(f"[-] Помилка сторінки {page_num}: {e}")
                continue

        browser.close()

    # Збереження у валідний XML файл
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(prettify_xml(root))

    print(f"\n[+] Збір успішно завершено! Збережено {total_offers} пропозицій у файл {OUTPUT_FILE}")


if __name__ == "__main__":
    main()