import json
import os
from playwright.sync_api import sync_playwright

# Посилання на сайт: https://happypaw.ua/ua/shelter
# Сторінка є динамічною: після кліку на фільтр породи/виду тварини
# контент каталогу оновлюється через JavaScript (AJAX) без перезавантаження сторінки.

BASE_URL = "https://happypaw.ua"
TARGET_URL = f"{BASE_URL}/ua/shelter"
OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "happypaw_pets.json")


def run():
    # Створюємо папку data, якщо її немає
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    with sync_playwright() as p:
        print("[1] Запуск браузера...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"[2] Відкриваємо сторінку: {TARGET_URL}")
        page.goto(TARGET_URL)

        # Явне очікування завантаження карток на сторінці
        page.wait_for_selector(".list-results .list-item")

        print("[3] Клікаємо на фільтр 'Кіт'...")
        # Знаходимо потрібний фільтр і натискаємо на нього
        page.locator("label[for='edit-field-animal-type-target-id-8']").click()

        # Чекаємо оновлення сторінки через JS
        page.wait_for_load_state("networkidle")
        page.wait_for_selector(".list-results .list-item")

        print("[4] Збираємо дані про тварин...")
        cards = page.locator(".list-results .list-item").all()
        print(f"Знайдено карток: {len(cards)}")

        pets_data = []

        for card in cards:
            # Отримуємо посилання
            href = card.get_attribute("href")
            link = BASE_URL + href if href else ""

            # Отримуємо ID
            pet_id = ""
            if card.locator(".list-item-id").count() > 0:
                pet_id = card.locator(".list-item-id").inner_text().replace("ID", "").strip()

            # Статус (чи влаштована тварина)
            status = ""
            if card.locator(".list-item-label").count() > 0:
                status = card.locator(".list-item-label").first.inner_text().strip()

            # Кличка тварини
            name = ""
            if card.locator(".list-item-title span").count() > 0:
                name = card.locator(".list-item-title span").inner_text().strip()

            # Опис (вік, стать)
            details = ""
            if card.locator(".list-item-text").count() > 0:
                # ' '.join(text.split()) видаляє всі зайві пробіли та переноси рядків
                raw_details = card.locator(".list-item-text").inner_text()
                details = " ".join(raw_details.split())

            # Посилання на фото
            photo_url = ""
            if card.locator("img.list-item-image-src").count() > 0:
                img_src = card.locator("img.list-item-image-src").get_attribute("src")
                if img_src:
                    photo_url = BASE_URL + img_src

            # Додаємо запис до списку
            pets_data.append({
                "id": pet_id,
                "name": name,
                "category": "Кіт",
                "status": status,
                "details": details,
                "profile_url": link,
                "image_url": photo_url
            })

        browser.close()

    print(f"[5] Зберігаємо результати у {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(pets_data, file, ensure_ascii=False, indent=4)

    print("Готово!")


if __name__ == "__main__":
    run()