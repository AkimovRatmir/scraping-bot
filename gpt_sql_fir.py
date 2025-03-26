import os
import asyncio
from playwright.async_api import async_playwright
import psycopg2
from psycopg2 import sql

# Логин и пароль для входа на сайт Kaspi
login_email = os.environ["KASPI_LOGIN"]
password = os.environ["KASPI_PASSWORD"]

GREEN_CHECK = "\033[92m✔\033[0m"  # Зеленый символ для уведомления
RED_CROSS = "\033[91m✖\033[0m"    # Красный символ для уведомления

# PostgreSQL connection parameters
DB_HOST = "localhost"
DB_NAME = "products_python_bot"
DB_USER = "postgres"  # Replace with your PostgreSQL username
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")  # Replace with your PostgreSQL password

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

def get_min_price_from_db(product_sku):
    # Connect to the database and fetch the min_price
    conn = connect_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT min_price FROM products WHERE sku = %s", (product_sku,))
        min_price = cursor.fetchone()
        cursor.close()
        conn.close()

        if min_price:
            return float(min_price[0])  # Return the min_price as a float
        else:
            print(f"Не найден min_price для артикулa: {product_sku}")
            return None
    else:
        print("Ошибка при подключении к базе данных.")
        return None

def get_step_from_db(product_sku):
    # Connect to the database and fetch the step value
    conn = connect_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT step FROM products WHERE sku = %s", (product_sku,))
        step = cursor.fetchone()
        cursor.close()
        conn.close()

        if step:
            return float(step[0])  # Return the step as a float
        else:
            print(f"Не найден step для артикулa: {product_sku}")
            return None
    else:
        print("Ошибка при подключении к базе данных.")
        return None

# def get_increase_from_db(product_sku):
#     conn = connect_db()
#     if conn:
#         cursor = conn.cursor()
#         cursor.execute("SELECT increase FROM products WHERE sku = %s", (product_sku,))  # Notice the comma here
#         increase = cursor.fetchone()
#         cursor.close()
#         conn.close()

#         if increase:
#             return str(increase[0])  # Fetch the actual value from the tuple
#         else:
#             print(f"Не найден increase для артикулa: {product_sku}")
#             return None
#     else:
#         print("Ошибка при подключении к базе данных.")
#         return None

def get_cur_price_from_db(product_sku):
    conn = connect_db()
    if conn: 
        cursor = conn.cursor()
        cursor.execute("SELECT current_price FROM products WHERE sku = %s", (product_sku))
        cur_pri = cursor.fetchone()
        cursor.close()
        conn.close()

        if cur_pri:
            return float(cur_pri[0])  # Return the step as a float
        else:
            print(f"Не найден current_price для артикулa: {product_sku}")
            return None
    else:
        print("Ошибка при подключении к базе данных.")
        return None

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

async def analyze_and_update_price(page, product_name, product_url, current_price, product_sku):
    #increase = get_increase_from_db(product_sku)

    try:
        full_url = f"https://kaspi.kz{product_url}"
        await page.goto(full_url)
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)

        # Получаем текущую цену товара на странице
        price_selector = '#ItemView > div.item > div > div.item__inner-right > div > div:nth-child(1) > div.item__price > div.item__price-left-side > div.item__price-once'
        competitor_price_element = await page.query_selector(price_selector)
        competitor_price_text = await competitor_price_element.inner_text()
        competitor_price = float(competitor_price_text.replace('₸', '').replace(' ', '').replace('&nbsp', '').replace(';', '').strip())

        print(f"Текущая цена: {current_price} ₸, Цена на странице товара: {competitor_price} ₸")

        if competitor_price < current_price:
            print(f"{GREEN_CHECK} Цена товара ниже текущей, обновляем цену.")
            # Here you can add the logic for adjusting the price
            await adjust_price(page, product_name, competitor_price, product_sku)
        else:
            # if competitor_price > current_price:
            #     if increase == "on":
            #         print(f"the competitor price is higher that the current price")
            #         await adjust_price(page, product_name, competitor_price, product_sku)
            print(f"{GREEN_CHECK} Изменение цены не требуется.")
        
        return competitor_price

    except Exception as e:
        print(f"Ошибка при анализе и изменении цены для товара '{product_name}': {e}")
        return None

async def adjust_price(page, product_name, new_price, product_sku):
    try:
        # Fetch min_price and step from the database
        min_price = get_min_price_from_db(product_sku)
        step = get_step_from_db(product_sku)
        # cur_pri = get_cur_price_from_db(product_sku)

        if min_price is not None and step is not None:
            # Compare new price with min_price and use the higher value or decrease by step if necessary
            if new_price < min_price:
                print(f"Цена конкурента ({new_price}) ниже минимальной цены в базе данных ({min_price}). Устанавливаем минимальную цену.")
                new_price = min_price  # Use min_price instead of new price
            else:
                print(f"Цена конкурента ({new_price}) выше минимальной цены в базе данных. Устанавливаем цену конкурента.")
                # # Decrease the price by the step if it's higher than min_price
                # if new_price > cur_pri:
                #     print(f"the competitor price is higher adjusting: the increase is set to on")
                #     new_price = new_price - step
                # else:
                    # Decrease the price by the step if it's higher than min_price
                new_price = new_price - step
                if new_price <= 10: 
                    print(f"the new price is lower than 10 adjusting to 10")
                    new_price = new_price + step
                print(f"Цена конкурента не ниже минимальной, уменьшаем цену на шаг ({step}) до {new_price} ₸.")

        # Use the product_sku to build the correct URL for price editing
        offer_update_url = f'https://kaspi.kz/mc/#/offer/{product_sku}'
        await page.goto(offer_update_url)
        print(f"Перехожу на страницу изменения товара: {offer_update_url}")
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(1)

        # Reload the page to ensure all elements are loaded correctly
        await page.reload()
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(1)

        # Use the exact selector for the price input field
        price_change_selector = '#app > section > div.main-content > div > div.master-product__content > div:nth-child(3) > div:nth-child(2) > div > button > span'
        price_change_input = await page.wait_for_selector(price_change_selector, timeout=10000)

        # Clear the input field
        await price_change_input.click()
        price_input_selector = '#app > section > div.main-content > div > div.offer-price-edit-analytics-context > div > div.animation-content.modal-content > div > section > div > div > div:nth-child(1) > input'
        price_input = await page.wait_for_selector(price_input_selector, timeout=1000)
        await price_input.click()
        await page.keyboard.press("Control+A")  # Select all text in the input field
        await page.keyboard.press("Backspace")  # Delete selected text
        print(f"Поле для ввода цены очищено.")
        await asyncio.sleep(1)
        
        # Enter the new price
        formatted_price = str(int(new_price))  # Ensure price is formatted correctly
        print(f"Вводим новую цену: {formatted_price} ₸")
        await price_input.type(formatted_price)
        await asyncio.sleep(1)

        # Click the "Save" button
        save_button_selector = 'button.button.is-primary span:has-text("Сохранить")'
        await page.wait_for_selector(save_button_selector, timeout=10000)
        await page.click(save_button_selector)
        print(f"Нажата кнопка 'Сохранить' для товара '{product_name}' с новой ценой.")
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(1)

        print(f'Цена для товара {product_name} обновлена до {new_price} ₸ на странице.')

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



async def write_and_save_to_db(data):
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
                INSERT INTO products (product_name, url, current_price, price_on_page, sku, image_url)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, data)
            print(f"Товар '{product_name}' не найден, добавляем новый.")
        
        conn.commit()
        cursor.close()
        conn.close()


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
            product_url, product_sku, product_image_url = await get_product_url_and_sku(page, product['productName'])
            if product_url:
                competitor_price = await analyze_and_update_price(page, product['productName'], product_url, product['productPrice'], product_sku)
                if competitor_price is not None:
                    data = [product['productName'], f"https://kaspi.kz{product_url}", product['productPrice'], competitor_price, product_sku, product_image_url]
                    print(f"Записываем данные в базу данных: {data}")
                    await write_and_save_to_db(data)
            else:
                print(f"Не удалось получить URL для товара: {product['productName']}")

            await page.goto(f'https://kaspi.kz/mc/#/products/active/{current_page}')
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(2)

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
