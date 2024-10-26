import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import json
import requests

category_url = input("Enter the category URLs: ")
if not category_url:
    category_url = "https://tuoitre.vn/cong-nghe.htm"
category_urls = [url.strip() for url in category_url.split(",")]
k = input("Number of posts to retrieve: ").strip()
if not k or int(k) < 100:
    k = 100
else:
    k = int(k) 


# create storage folder
os.makedirs('data', exist_ok=True)
os.makedirs('audio', exist_ok=True)
os.makedirs('images', exist_ok=True)


# setup selenium
options = Options()
options.add_argument('--headless=new')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
driver = webdriver.Chrome(options=options)


# utility functions
def scroll_to_bottom(driver):
    wait = WebDriverWait(driver, 5)
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        try:
            wait.until(lambda driver: driver.execute_script("return document.body.scrollHeight") > last_height)
            last_height = driver.execute_script("return document.body.scrollHeight")
        except:
            break

def click_load_more(driver, num_clicks):
    wait = WebDriverWait(driver, 5)
    for _ in range(num_clicks):
        try:
            scroll_to_bottom(driver)
            load_more_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "box-viewmore")))
            load_more_button.click()
        except Exception as e:
            break

def extract_date(date):
    return date.split(" ")[0].strip()

def craw_data(driver, url):
    news_list = driver.find_element(By.ID, "load-list-news")
    box_items = news_list.find_elements(By.CLASS_NAME, "box-category-item")

    cnt = 1

    for box in box_items:
        if cnt > int(k):
            break

        try:
            data = {}

            # Extract basic information from the main page
            box_category = box.find_element(By.XPATH, './div[@class="box-category-content"]/a')
            box_category_sapo = box.find_element(By.XPATH, './div[@class="box-category-content"]/p')

            link_and_avatar_box = box.find_element(By.CLASS_NAME, "box-category-link-title")
            title = link_and_avatar_box.get_attribute("title")
            href = link_and_avatar_box.get_attribute("href")
            category = box_category.get_attribute("title")
            content = box_category_sapo.text

            # Open the post link in a new tab to extract the author's name
            current_window = driver.current_window_handle
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[-1])
            driver.get(href)

            author_info = driver.find_element(By.CLASS_NAME, "author-info")
            author_name = author_info.find_element(By.CLASS_NAME, "name").text
            detail_time = driver.find_element(By.CLASS_NAME, "detail-time")
            date = detail_time.text

            # Populate the data dictionary
            data['postId'] = f'{cnt:03d}'
            data['title'] = title
            data['link'] = href
            data['category'] = category
            data['date'] = extract_date(date)
            data['author'] = author_name
            data['author'] = author_name
            data['content'] = content

            content_div = driver.find_element(By.CSS_SELECTOR, 'div.detail-content.afcbc-body[data-role="content"][itemprop="articleBody"]')
            figure_elements = content_div.find_elements(By.TAG_NAME, 'figure')
            image_counter = 1
            for figure in figure_elements:
                # Inside each figure, find img tags
                img_elements = figure.find_elements(By.TAG_NAME, 'img')
                for img in img_elements:
                    img_url = img.get_attribute('src')
                    if img_url:
                        # Download the image and save it
                        try:
                            image_response = requests.get(img_url, stream=True, timeout=10)
                            if image_response.status_code == 200:
                                image_path = os.path.join(f'images/{cnt:03d}', f'image{image_counter}.jpg')
                                with open(image_path, 'wb') as f:
                                    for chunk in image_response.iter_content(1024):
                                        f.write(chunk)
                                image_counter += 1
                        except Exception as e:
                            print(f"Error downloading image {img_url}: {e}")

            # Save the data to a JSON file
            postID = data['postId']
            with open(f'data/{postID}.json', 'w', encoding='utf-8') as json_file:
                json.dump(data, json_file, ensure_ascii=False, indent=4)

            print(data, sep='\n\n')


            # Increment the counter after successful processing
            cnt += 1

        except Exception as e:
            # Print the error and skip to the next box
            print(f"Error processing box {cnt}: {e}")
            # Optionally, you can log the exception details for debugging
        finally:
            # Close the new tab if it's open and switch back to the main window
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(current_window)
            else:
                driver.switch_to.window(current_window)


# crawl data
for url in category_urls:
    driver.get(url)
    click_load_more(driver, 2)
    craw_data(driver, url)
