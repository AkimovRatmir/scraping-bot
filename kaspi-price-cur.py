import os
import asyncio
from playwright.async_api import async_playwright
from openpyxl import load_workbook
import re

# Логин и пароль для входа на сайт Kaspi
login_email = os.environ["KASPI_LOGIN"]
password = os.environ["KASPI_PASSWORD"]

GREEN_CHECK = "\033[92m✔\033[0m"  # Зеленый символ для уведомления
RED_CROSS = "\033[91m✖\033[0m"    # Красный символ для уведомления

excel_path = r"/home/ratmir/kaspiBotBaza/baza.xlsx"

# Функция для записи данных в Excel-файл (обновляет данные, если товар уже существует)
def write_and_save_to_excel(workbook, worksheet, data):
    product_name = data[0]  # Название товара
    found = False
    
    for row in range(2, worksheet.max_row + 1):  # Начинаем со второй строки (пропуская заголовок)
        existing_product = worksheet[f"A{row}"].value
        if existing_product == product_name:
            worksheet[f"B{row}"] = data[1]  # URL
            worksheet[f"C{row}"] = data[2]  # Текущая цена
            worksheet[f"D{row}"] = data[3]  # Цена на странице товара
            worksheet[f"E{row}"] = data[4]  # Артикул
            worksheet[f"F{row}"] = data[5]  # Ссылка на изображение
            found = True
            print(f"Товар '{product_name}' найден, данные обновлены.")
            break
    
    if not found:
        next_row = worksheet.max_row + 1
        worksheet[f"A{next_row}"] = data[0]  # Название товара
        worksheet[f"B{next_row}"] = data[1]  # URL
        worksheet[f"C{next_row}"] = data[2]  # Текущая цена
        worksheet[f"D{next_row}"] = data[3]  # Цена на странице товара
        worksheet[f"E{next_row}"] = data[4]  # Артикул
        worksheet[f"F{next_row}"] = data[5]  # Ссылка на изображение
        print(f"Товар '{product_name}' не найден, добавляем новый.")
    
    workbook.save(excel_path)  # Сохранение данных после записи


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

async def analyze_and_update_price(page, product_name, product_url, current_price, worksheet, row):
    try:
        full_url = f"https://kaspi.kz{product_url}"
        await page.goto(full_url)
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)

        # Получаем текущую цену товара на странице
        price_selector = '#ItemView > div.item > div > div.item__inner-right > div > div:nth-child(1) > div.item__price > div.item__price-left-side > div.item__price-once'
        competitor_price_element = await page.query_selector(price_selector)
        competitor_price_text = await competitor_price_element.inner_text()

        # Clean the price text and check if it's valid
        competitor_price_text = competitor_price_text.replace('₸', '').replace(' ', '').replace('&nbsp', '').replace(';', '').strip()
        
        if competitor_price_text.lower() in ['off', 'on', 'нет в наличии', 'price unavailable']:  # Customize for your case
            print(f"Invalid price detected: {competitor_price_text}")
            competitor_price = None
        else:
            try:
                competitor_price = float(competitor_price_text)
            except ValueError:
                print(f"Failed to convert to float: {competitor_price_text}")
                competitor_price = None

        # Получаем цены всех продавцов на странице товара
        sellers_prices_elements = await page.query_selector_all('div.sellers-table__price-cell-text:not(._installments-price)')
        sellers_prices = [
            float((await element.inner_text()).replace('₸', '').replace(' ', '').replace(' ', '').strip())
            for element in sellers_prices_elements
        ]

        # Минимальная цена среди других продавцов, исключая текущую цену
        other_sellers_prices = [price for price in sellers_prices if price != current_price]
        min_seller_price = min(other_sellers_prices, default=None)

        # Получаем минимальную цену из столбца G
        min_price_from_g = worksheet[f"G{row}"].value
        min_price_from_g = float(min_price_from_g) if min_price_from_g is not None else None

        print(f"Текущая цена: {current_price} ₸, Цена на странице товара: {competitor_price} ₸, Минимальная цена среди других продавцов: {min_seller_price} ₸")
        print(f"Минимальная цена из столбца G: {min_price_from_g} ₸")

        # Если минимальная цена конкурентов ниже текущей цены и в столбце G есть значение, то не снижаем цену
        if min_price_from_g is not None and competitor_price < min_price_from_g:
            print(f"{GREEN_CHECK} Изменение цены не требуется: цена конкурента ниже, чем минимальная цена в столбце G.")
            return competitor_price, min_seller_price
        
        # Если минимальная цена конкурентов ниже текущей цены, устанавливаем новую цену
        if min_seller_price is not None and min_seller_price < current_price:
            new_price = min_seller_price - 10
            print(f"{GREEN_CHECK} Новая цена для товара: {new_price} ₸")
            # Здесь вы можете добавить логику для изменения цены
        else:
            print(f"{GREEN_CHECK} Изменение цены не требуется: текущая цена уже минимальная или равна конкурентной.")
        
        return competitor_price, min_seller_price

    except Exception as e:
        print(f"Ошибка при анализе и изменении цены для товара '{product_name}': {e}")
        return None, None

async def get_all_product_info(page, workbook, worksheet):
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
                competitor_price, min_seller_price = await analyze_and_update_price(page, product['productName'], product_url, product['productPrice'], worksheet, idx)
                if competitor_price is not None:
                    data = [product['productName'], f"https://kaspi.kz{product_url}", product['productPrice'], competitor_price, product_sku, product_image_url]
                    print(f"Записываем данные в Excel: {data}")
                    write_and_save_to_excel(workbook, worksheet, data)
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
    print(f"Открываем файл Excel: {excel_path}")
    workbook = load_workbook(excel_path)
    worksheet = workbook.active

    await get_all_product_info(page, workbook, worksheet)

    await browser.close()

async def main():
    async with async_playwright() as playwright:
        await process_products(playwright)

# Запуск основной функции
asyncio.run(main())