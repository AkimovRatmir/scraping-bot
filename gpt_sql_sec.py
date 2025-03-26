import os
import asyncio
from playwright.async_api import async_playwright
import psycopg2

login_email = os.environ["KASPI_LOGIN"]
password = os.environ["KASPI_PASSWORD"]

# PostgreSQL connection parameters
DB_HOST = "localhost"
DB_NAME = "products_python_bot"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

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
    await page.goto('https://kaspi.kz/mc/#/products/active/1')
    await page.wait_for_load_state('networkidle')
    await asyncio.sleep(2)

async def get_product_url_and_sku(page, product_name):
    try:
        await page.click(f"//a[contains(text(), '{product_name}')]")
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)
        locator = page.locator('#app > section > div.main-content > div > div.master-product__content > div:nth-child(4) > div:nth-child(2) > div > div:nth-child(1) > div.product-info-field-value > div:nth-child(2) > a')
        product_url = await locator.get_attribute('href') if await locator.count() > 0 else None
        sku_locator = page.locator('#app > section > div.main-content > div > div.master-product__content > div:nth-child(4) > div:nth-child(2) > div > div:nth-child(2) > div.product-info-field-value')
        product_sku = await sku_locator.inner_text() if await sku_locator.count() > 0 else None
        image_locator = page.locator('#app > section > div.main-content > div > div.master-product__content > div.master-product-images > div > div.image-list__main-image-container > div.thumbnail-container > img')
        product_image_url = await image_locator.get_attribute('src') if await image_locator.count() > 0 else None
        return product_url, product_sku, product_image_url
    except Exception as e:
        print(f"Error fetching product data: {e}")
        return None, None, None

async def analyze_and_update_price(page, product_name, product_url, current_price):
    try:
        full_url = f"https://kaspi.kz{product_url}"
        await page.goto(full_url)
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)
        price_selector = '#ItemView > div.item > div > div.item__inner-right > div > div:nth-child(1) > div.item__price > div.item__price-left-side > div.item__price-once'
        competitor_price_element = await page.query_selector(price_selector)
        competitor_price_text = await competitor_price_element.inner_text()
        competitor_price = float(competitor_price_text.replace('₸', '').replace(' ', '').replace('&nbsp', '').replace(';', '').strip())
        return competitor_price
    except Exception as e:
        print(f"Error analyzing price: {e}")
        return None

async def write_and_save_to_db(data):
    product_name = data[0]
    conn = connect_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE product_name = %s", (product_name,))
        existing_product = cursor.fetchone()
        if existing_product:
            cursor.execute("""
                UPDATE products
                SET url = %s, current_price = %s, price_on_page = %s, sku = %s, image_url = %s
                WHERE product_name = %s
            """, (data[1], data[2], data[3], data[4], data[5], product_name))
            print(f"Product '{product_name}' updated in database.")
        else:
            cursor.execute("""
                INSERT INTO products (product_name, url, current_price, price_on_page, sku, image_url)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, data)
            print(f"Product '{product_name}' inserted into database.")
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
            print("No products on this page.")
            break

        for product in current_page_products:
            product_url, product_sku, product_image_url = await get_product_url_and_sku(page, product['productName'])
            if product_url:
                competitor_price = await analyze_and_update_price(page, product['productName'], product_url, product['productPrice'])
                if competitor_price is not None:
                    data = [product['productName'], f"https://kaspi.kz{product_url}", product['productPrice'], competitor_price, product_sku, product_image_url]
                    print(f"Writing data to DB: {data}")
                    await write_and_save_to_db(data)
            else:
                print(f"Failed to get URL for product: {product['productName']}")

        next_button = await page.query_selector('#offers-table > div.level-right > div > nav > a.pagination-link.pagination-next')
        if next_button:
            current_page += 1
            await next_button.click()
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(2)
        else:
            print("All pages processed.")
            break

async def process_products(playwright):
    print("Logging in to Kaspi.kz...")
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page()

    await login(page)
    print("Navigating to active products page...")
    await get_all_product_info(page)

    await browser.close()

async def main():
    async with async_playwright() as playwright:
        await process_products(playwright)

# Running the main function
asyncio.run(main())
