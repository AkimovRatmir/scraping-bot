import os
import asyncio
from playwright.async_api import async_playwright
import psycopg2
from psycopg2 import sql

# PostgreSQL connection parameters
DB_HOST = "localhost"
DB_NAME = "products_python_bot"
DB_USER = "postgres"  # Replace with your PostgreSQL username
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")  # Replace with your PostgreSQL password

login_email = os.environ["KASPI_LOGIN"]
password = os.environ["KASPI_PASSWORD"]


# Function to connect to the PostgreSQL database
def connect_db():
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return connection
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None

def write_and_save_to_db(data):
    product_name = data[0]  # Название товара
    found = False
    
    # Connect to the database
    conn = connect_db()
    if conn:
        cursor = conn.cursor()
        
        # Check if the product already exists
        cursor.execute("SELECT * FROM products WHERE product_name = %s", (product_name,))
        existing_product = cursor.fetchone()

        if existing_product:
            # Product found, update the existing data
            cursor.execute("""
                UPDATE products
                SET url = %s, current_price = %s, price_on_page = %s, sku = %s, image_url = %s
                WHERE product_name = %s
            """, (data[1], data[2], data[3], data[4], data[5], product_name))
            print(f"Товар '{product_name}' найден, данные обновлены.")
        else:
            # Product not found, insert a new record
            cursor.execute("""
                INSERT INTO products (product_name, url, current_price, price_on_page, sku, image_url, decrease, increase, max_price, min_price, step)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, data)
            print(f"Товар '{product_name}' не найден, добавляем новый.")
        
        conn.commit()
        cursor.close()
        conn.close()


async def login(page):
    await page.goto('https://kaspi.kz/mc/#/login')
    await page.wait_for_load_state('networkidle')
    await asyncio.sleep(1)

    await page.click('input#user_email_field')
    await page.fill('input#user_email_field', login_email)
    await asyncio.sleep(1)

    await page.click('button.button.is-primary')
    await page.wait_for_selector('input#password_field', timeout=10000)
    await page.fill('input#password_field', password)
    await asyncio.sleep(1)
    
    await page.click('button.button.is-primary')
    await page.wait_for_load_state('networkidle')
    await asyncio.sleep(2)

    # Переход на страницу активных товаров после логина
    await page.goto('https://kaspi.kz/mc/#/products/active/1')
    await page.wait_for_load_state('networkidle')
    await asyncio.sleep(2)


async def get_product_url_and_sku(page, product_name):
    try:
        print(f"Ищем продукт с именем: {product_name}")
        await page.click(f"//a[contains(text(), '{product_name}')]")
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)

        # Извлечение URL товара
        locator = page.locator(
            '#app > section > div.main-content > div > div.master-product__content > div:nth-child(4) > div:nth-child(2) > div > div:nth-child(1) > div.product-info-field-value > div:nth-child(2) > a'
        )
        product_url = await locator.get_attribute('href') if await locator.count() > 0 else None

        # Извлечение артикула товара
        sku_locator = page.locator(
            '#app > section > div.main-content > div > div.master-product__content > div:nth-child(4) > div:nth-child(2) > div > div:nth-child(2) > div.product-info-field-value'
        )
        product_sku = await sku_locator.inner_text() if await sku_locator.count() > 0 else None

        # Извлечение ссылки на изображение
        image_locator = page.locator(
            '#app > section > div.main-content > div > div.master-product__content > div.master-product-images > div > div.image-list__main-image-container > div.thumbnail-container > img'
        )
        product_image_url = await image_locator.get_attribute('src') if await image_locator.count() > 0 else None

        if product_url:
            print(f"Найден URL для товара '{product_name}': {product_url}")
        else:
            print(f"Не удалось найти URL для товара: {product_name}")

        if product_sku:
            print(f"Артикул товара '{product_name}': {product_sku}")
        else:
            print(f"Не удалось найти артикул для товара: {product_name}")

        return product_url, product_sku, product_image_url

    except Exception as e:
        print(f"Ошибка при получении URL, артикула и изображения для товара '{product_name}': {e}")
        return None, None, None


async def adjust_price(page, product_name, new_price):
    try:
        # Функция для изменения цены товара
        offer_update_url = 'URL_для_изменения_предложения'  # Установите фактический URL для изменения цены

        await page.goto(offer_update_url)
        await page.wait_for_load_state('networkidle')
        await page.reload()
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(1)

        # Используем точный селектор для поля ввода цены
        price_input_selector = 'div.field input.input[type="text"]'
        price_input = await page.wait_for_selector(price_input_selector, timeout=10000)

        # Очищаем поле ввода
        await price_input.click()
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await asyncio.sleep(1)
        
        # Вводим новую цену
        formatted_price = str(int(new_price))
        await price_input.type(formatted_price)
        await asyncio.sleep(1)
        
        # Нажимаем кнопку "Сохранить"
        save_button_selector = 'button.button.is-primary span:has-text("Сохранить")'
        await page.wait_for_selector(save_button_selector, timeout=10000)
        await page.click(save_button_selector)
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(1)
        
        print(f'Цена обновлена до {new_price} ₸')

        # Now, update the price in PostgreSQL after the webpage price update
        # Connect to the database
        conn = connect_db()
        if conn:
            cursor = conn.cursor()

            # Update the price in the database
            cursor.execute("""
                UPDATE products
                SET current_price = %s
                WHERE product_name = %s
            """, (new_price, product_name))

            conn.commit()
            cursor.close()
            conn.close()

            print(f"Цена для товара '{product_name}' обновлена в базе данных до {new_price} ₸")

    except Exception as e:
        print(f"Ошибка при обновлении цены для товара '{product_name}': {e}")


async def get_all_product_info(page):
    current_page = 1
    while True:
        await page.goto(f'https://kaspi.kz/mc/#/products/active/{current_page}')
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)

        current_page_products = await page.evaluate('''() => {
            return Array.from(document.querySelectorAll('tr')).map(row => {
                const productNameElement = row.querySelector('td[data-label="Товар"] p.is-5 a');
                const productName = productNameElement ? productNameElement.innerText.trim() : null;
                const productPriceElement = row.querySelector('td[data-label="Цена, тенге"] p.subtitle.is-5');
                const productPrice = productPriceElement ? parseFloat(productPriceElement.innerText.replace('₸', '').replace(' ', '').replace(' ', '').trim()) : null;
                if (productName && productPrice !== null) {
                    return { productName, productPrice };
                } else {
                    return null;
                }
            }).filter(product => product !== null);
        }''')

        if not current_page_products:
            print("На текущей странице нет товаров.")
            break
        
        for idx, product in enumerate(current_page_products, start=2):
            product_url, article_number, product_image_url = await get_product_url_and_sku(page, product['productName'])
            if product_url:
                min_price = 1000  # Example min price
                competitor_price = product['productPrice']  # This is just for example
                if competitor_price is not None:
                    # Prepare data to insert into PostgreSQL
                    data = [
                        product['productName'],
                        f"https://kaspi.kz{product_url}",
                        product['productPrice'],
                        competitor_price,
                        article_number,
                        product_image_url,  # Now we use the image URL here
                        'off', 'on', 5000, 1000, 10
                    ]
                    print(f"Записываем данные в базу данных: {data}")
                    write_and_save_to_db(data)
            else:
                print(f"Не удалось получить URL для товара: {product['productName']}")


        print(f"Текущая страница: обработано {len(current_page_products)} товаров.")

        next_button = await page.query_selector('#offers-table > div.level-right > div > nav > a.pagination-link.pagination-next')
        if next_button:
            current_page += 1
            await next_button.click()
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(2)
        else:
            print("Все страницы обработаны.")
            break


async def process_products(playwright):
    print("Логинимся на сайт Kaspi.kz...")
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page()

    await login(page)
    
    print("Переход на страницу активных товаров...")
    await get_all_product_info(page)

    await browser.close()


async def main():
    async with async_playwright() as playwright:
        await process_products(playwright)

# Запуск основной функции
asyncio.run(main())
