import os
import asyncio
from playwright.async_api import async_playwright
from openpyxl import load_workbook

# Логин и пароль для входа на сайт Kaspi
login_email = os.environ["KASPI_LOGIN"]
password = os.environ["KASPI_PASSWORD"]

GREEN_CHECK = "\033[92m✔\033[0m"  # Зеленый символ для уведомленияs
RED_CROSS = "\033[91m✖\033[0m"    # Красный символ для уведомления

excel_path = r"/home/ratmir/kaspiBotBaza/baza.xlsx"

def write_and_save_to_excel(workbook, worksheet, data):
    product_name = data[0]  # Название товара
    found = False
    
    # Проход по существующим строкам, чтобы найти товар по названию
    for row in range(2, worksheet.max_row + 1):  # Начинаем со второй строки (пропуская заголовок)
        existing_product = worksheet[f"A{row}"].value
        if existing_product == product_name:
            # Обновляем данные для существующего товара
            worksheet[f"B{row}"] = data[1]  # URL
            worksheet[f"C{row}"] = data[2]  # Текущая цена
            worksheet[f"D{row}"] = data[3]  # Цена на странице товара
            worksheet[f"E{row}"] = data[4]  # Артикул
            found = True
            print(f"Товар '{product_name}' найден, данные обновлены.")
            break
    
    if not found:
        # Если товар не найден, добавляем его в новую строку
        next_row = worksheet.max_row + 1
        worksheet[f"A{next_row}"] = data[0]  # Название товара
        worksheet[f"B{next_row}"] = data[1]  # URL
        worksheet[f"C{next_row}"] = data[2]  # Текущая цена
        worksheet[f"D{next_row}"] = data[3]  # Цена на странице товара
        worksheet[f"E{next_row}"] = data[4]  # Артикул
        print(f"Товар '{product_name}' не найден, добавляем новый.")
    
    workbook.save(excel_path)  # Сохранение данных после записи



# Функция для получения минимальной цены из столбца E
def get_min_price(worksheet, row_number):
    min_price_cell = worksheet[f"E{row_number}"]
    return min_price_cell.value if min_price_cell.value is not None else None

async def login(page):
    await page.goto('https://kaspi.kz/mc/#/login')
    await page.wait_for_load_state('networkidle')
    await asyncio.sleep(1)

    await page.click('//a[@id="12-label"]/span[text()="Email"]')
    await asyncio.sleep(1)
    
    await page.wait_for_selector('input#user_email_field', timeout=10000)
    await page.fill('input#user_email_field', login_email)
    await asyncio.sleep(1)

    await page.click('button#continue_button')
    await asyncio.sleep(1)
    
    await page.wait_for_selector('input#password_field', timeout=10000)
    await page.fill('input#password_field', password)
    await asyncio.sleep(1)
    
    await page.click('button#sign_in_button')
    await page.wait_for_load_state('networkidle')
    await asyncio.sleep(2)

    # Переход на страницу активных товаров после логина
    await page.goto('https://kaspi.kz/mc/#/products/active/1')
    await page.wait_for_load_state('networkidle')
    await asyncio.sleep(2)

async def get_product_url(page, product_name):
    try:
        print(f"Ищем продукт с именем: {product_name}")
        # Find the product link by matching the product name
        await page.click(f"//a[contains(text(), '{product_name}')]")
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)  # Increased wait time to ensure the page loads completely

        # Extract Артикул
        article_locator = page.locator('//div[text()="Артикул"]/following-sibling::div')
        if await article_locator.count() == 1:  # Ensure only one match is found
            article_number = await article_locator.inner_text()
            print(f"Артикул для товара '{product_name}': {article_number}")
        else:
            article_number = None
            print(f"Не удалось найти Артикул для товара: {product_name}")

        # Check if the 'Посмотреть на Kaspi.kz' link exists
        locator = page.locator(
            '//div[@data-v-3b7f754c]//a[contains(text(), "Посмотреть на Kaspi.kz")]'
        )

        if await locator.count() > 0:
            product_url = await locator.get_attribute('href')
            print(f"Найден URL для товара '{product_name}': {product_url}")
            return product_url, article_number
        else:
            print(f"Не удалось найти URL для товара: {product_name}")
            return None, article_number

    except Exception as e:
        print(f"Ошибка при получении URL для товара '{product_name}': {e}")
        return None, None



async def adjust_price(page, new_price):
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

async def check_and_compare_prices(page, product_url, current_price, min_price):
    try:
        full_url = f"https://kaspi.kz{product_url}"
        await page.goto(full_url)
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)

        # Получаем текущую цену товара на странице
        price_selector = '#ItemView > div.item > div > div.item__inner-right > div > div:nth-child(1) > div.item__price > div.item__price-left-side > div.item__price-once'
        competitor_price_element = await page.query_selector(price_selector)
        competitor_price_text = await competitor_price_element.inner_text()
        competitor_price = float(competitor_price_text.replace('₸', '').replace(' ', '').replace(' ', '').strip())

        # Получаем все цены продавцов на товарной странице, исключая цены в рассрочку
        sellers_prices_elements = await page.query_selector_all('div.sellers-table__price-cell-text:not(._installments-price)')
        sellers_prices = [
            float((await element.inner_text()).replace('₸', '').replace(' ', '').replace(' ', '').strip())
            for element in sellers_prices_elements
        ]

        # Найти минимальную цену среди других продавцов, исключая текущую цену
        other_sellers_prices = [price for price in sellers_prices if price != current_price]
        min_seller_price = min(other_sellers_prices, default=None)

        print(f"Текущая цена: {current_price} ₸, Цена на странице товара: {competitor_price} ₸, Минимальная цена среди других продавцов: {min_seller_price} ₸")

        # Логика изменения цены
        if min_seller_price is not None and current_price is not None:
            if current_price > min_seller_price:
                new_price = min_seller_price - 10
                print(f"{GREEN_CHECK} Изменяем цену на {new_price} ₸, так как она не является самой низкой.")
                await adjust_price(page, new_price)
            elif competitor_price < current_price and competitor_price >= min_price:
                print(f"{RED_CROSS} Необходимо снизить цену до {competitor_price} ₸ для товара: URL - {full_url}")
                await adjust_price(page, competitor_price)
            elif competitor_price < min_price:
                print(f"{RED_CROSS} Цена конкурента ниже минимальной, устанавливаем минимальную цену: {min_price} ₸ для товара: URL - {full_url}")
                await adjust_price(page, min_price)
            elif competitor_price == current_price:
                print(f"{GREEN_CHECK} Цена для товара по URL {full_url} соответствует текущей цене, изменение не требуется.")
            else:
                print(f"{GREEN_CHECK} Цена для товара по URL {full_url} выше текущей, изменение не требуется.")
        else:
            print(f"{GREEN_CHECK} Минимальная цена отсутствует или некорректна. Текущая цена: {current_price} ₸, Цена на странице товара: {competitor_price} ₸.")
        
        return competitor_price

    except Exception as e:
        print(f"Ошибка при проверке цены для URL '{product_url}': {e}")
        return None

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
            product_url, article_number = await get_product_url(page, product['productName'])
            if product_url:
                min_price = get_min_price(worksheet, idx)
                competitor_price = await check_and_compare_prices(page, product_url, product['productPrice'], min_price)
                if competitor_price is not None:
                    data = [product['productName'], f"https://kaspi.kz{product_url}", product['productPrice'], competitor_price, article_number]
                    print(f"Записываем данные в Excel: {data}")
                    write_and_save_to_excel(workbook, worksheet, data)
            else:
                print(f"Не удалось получить URL для товара: {product['productName']}")

            # Переход обратно на текущую страницу списка товаров
            await page.goto(f'https://kaspi.kz/mc/#/products/active/{current_page}')
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(2)

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