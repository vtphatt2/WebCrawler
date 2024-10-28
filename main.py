import os
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
from functools import partial

# ===========================
# Utility Functions
# ===========================

def setup_driver():
    """
    Initializes and returns a Selenium WebDriver instance with specified options.
    """
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    return driver

def scroll_to_bottom(driver):
    """
    Scrolls to the bottom of the page to load dynamic content.
    """
    wait = WebDriverWait(driver, 5)
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)  # Wait for the page to load
        try:
            wait.until(lambda d: d.execute_script("return document.body.scrollHeight") > last_height)
            last_height = driver.execute_script("return document.body.scrollHeight")
        except:
            break

def click_load_more(driver, num_clicks):
    """
    Clicks the 'Load More' button a specified number of times to load additional posts.
    """
    wait = WebDriverWait(driver, 5)
    for _ in range(num_clicks):
        try:
            scroll_to_bottom(driver)
            load_more_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "box-viewmore")))
            load_more_button.click()
            time.sleep(2)  # Wait for new posts to load
        except Exception as e:
            print(f"No more 'Xem them' button available or error occurred: {e}")
            break

def extract_date(date_str):
    """
    Extracts the date from a date string.
    """
    return date_str.split(" ")[0].strip()

def download_file(url, path):
    """
    Downloads a file from the given URL to the specified path.
    """
    try:
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code == 200:
            with open(path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    if chunk:
                        f.write(chunk)
            return True
        else:
            print(f"Failed to download file from {url}. Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error downloading file from {url}: {e}")
        return False

def collect_post_links(driver, url, max_posts):
    """
    Collects post links from the given category URL up to max_posts.
    """
    driver.get(url)
    click_load_more(driver, 2)

    news_list = driver.find_element(By.ID, "load-list-news")
    box_items = news_list.find_elements(By.CLASS_NAME, "box-category-item")

    post_links = []
    for box in box_items:
        if len(post_links) >= max_posts:
            break
        try:
            link_and_avatar_box = box.find_element(By.CLASS_NAME, "box-category-link-title")
            href = link_and_avatar_box.get_attribute("href")
            if href and href not in post_links:
                post_links.append(href)
        except Exception as e:
            print(f"Error collecting link: {e}")
    
    return post_links

def process_post(link, post_id):
    """
    Processes a single post: extracts data, downloads media, and saves JSON.
    """
    driver = setup_driver()
    data = {}
    try:
        driver.get(link)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "author-info")))

        # Extract basic information
        author_info = driver.find_element(By.CLASS_NAME, "author-info")
        author_name = author_info.find_element(By.CLASS_NAME, "name").text

        detail_time = driver.find_element(By.CLASS_NAME, "detail-time")
        date = extract_date(detail_time.text)

        # Extract title, category, and content
        box_category = driver.find_element(By.XPATH, '//div[@class="box-category-content"]/a')
        title = box_category.get_attribute("title")
        category = box_category.get_attribute("title")
        box_category_sapo = driver.find_element(By.XPATH, '//div[@class="box-category-content"]/p')
        content = box_category_sapo.text

        # Populate the data dictionary
        data['postId'] = f'{post_id:03d}'
        data['title'] = title
        data['link'] = link
        data['category'] = category
        data['date'] = date
        data['author'] = author_name
        data['content'] = content
        data['images'] = []
        data['votes'] = {}
        data['comments'] = []
        data['audio_link'] = ""
        data['audio_path'] = ""

        # Extract images
        try:
            content_div = driver.find_element(By.CSS_SELECTOR, 'div.detail-content.afcbc-body[data-role="content"][itemprop="articleBody"]')
            figure_elements = content_div.find_elements(By.TAG_NAME, 'figure')
            image_counter = 1
            for figure in figure_elements:
                img_elements = figure.find_elements(By.TAG_NAME, 'img')
                for img in img_elements:
                    img_url = img.get_attribute('src')
                    if img_url:
                        data['images'].append(img_url)
                        # Create directory for images of this post
                        os.makedirs(f'images/{post_id:03d}', exist_ok=True)
                        image_path = os.path.join(f'images/{post_id:03d}', f'image{image_counter}.jpg')
                        if download_file(img_url, image_path):
                            image_counter += 1
        except Exception as e:
            print(f"Error extracting images for post {post_id}: {e}")

        # Extract audio
        try:
            audio_element = driver.find_element(By.TAG_NAME, 'audio')
            audio_url = audio_element.get_attribute('src')
            data['audio_link'] = audio_url
            if audio_url:
                audio_path = os.path.join('audio', f'{post_id:03d}.mp3')
                if download_file(audio_url, audio_path):
                    data['audio_path'] = audio_path
        except Exception as e:
            print(f"No audio found for post {post_id} or error occurred: {e}")

        # Extract votes
        try:
            react_info = driver.find_element(By.CLASS_NAME, "reactinfo")
            votes = {
                "icostar": "0",
                "icolikeauthor": "0",
                "icoheartauthor": "0"
            }

            # icostar
            try:
                icostar_span = react_info.find_element(By.CSS_SELECTOR, "i.icostar + span")
                votes["icostar"] = icostar_span.text.strip()
            except:
                votes["icostar"] = "0"

            # icolikeauthor
            try:
                icolikeauthor_span = react_info.find_element(By.CSS_SELECTOR, "i.icolikeauthor + span")
                votes["icolikeauthor"] = icolikeauthor_span.text.strip()
            except:
                votes["icolikeauthor"] = "0"

            # icoheartauthor
            try:
                icoheartauthor_span = react_info.find_element(By.CSS_SELECTOR, "i.icoheartauthor + span")
                votes["icoheartauthor"] = icoheartauthor_span.text.strip()
            except:
                votes["icoheartauthor"] = "0"

            data['votes'] = votes
        except Exception as e:
            print(f"Cannot extract votes for post {post_id}: {e}")
            data['votes'] = {
                "icostar": "0",
                "icolikeauthor": "0",
                "icoheartauthor": "0"
            }

        # Extract comments
        try:
            comment_ul = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'ul[data-view="listcm"]')))
            comment_items = driver.find_elements(By.XPATH, '//ul[@data-view="listcm"]/li[contains(@class, "item-comment")]')

            comments = []
            for comment_item in comment_items:
                comment = {}
                comment['commentId'] = comment_item.get_attribute('data-cmid')
                comment['author'] = comment_item.get_attribute('data-replyname')
                comment['text'] = comment_item.find_element(By.CLASS_NAME, 'contentcomment').text
                comment['date'] = comment_item.find_element(By.CLASS_NAME, 'timeago').get_attribute('title')
                comment['votes'] = []

                try:
                    btnright_hasreaction = comment_item.find_element(By.CSS_SELECTOR, 'div.btnright.hasreaction')
                    wrapreact = btnright_hasreaction.find_element(By.CSS_SELECTOR, 'div.wrapreact')
                    listreact = wrapreact.find_element(By.CSS_SELECTOR, 'div.listreact')
                    colreacts = listreact.find_elements(By.CSS_SELECTOR, 'div.colreact')

                    for colreact in colreacts:
                        reaction = {}
                        span_icon = colreact.find_element(By.CSS_SELECTOR, 'span[class^="spritecmt"]')
                        reaction_class = span_icon.get_attribute('class').strip()
                        num_span = colreact.find_element(By.CLASS_NAME, 'num')
                        num = num_span.get_attribute('textContent').strip()
                        # Debugging statements
                        print(f"Reaction Class: {reaction_class}, Count: {num}")
                        reaction[reaction_class] = num
                        comment['votes'].append(reaction)
                except Exception as e:
                    print(f"Error extracting votes for comment {comment['commentId']}: {e}")
                    comment['votes'] = []

                comments.append(comment)

            data['comments'] = comments
        except Exception as e:
            print(f"Error extracting comments for post {post_id}: {e}")
            data['comments'] = []

        # Save the data to a JSON file
        postID = data['postId']
        with open(f'data/{postID}.json', 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, ensure_ascii=False, indent=4)

        print(f"Successfully processed post {post_id}: {title}\n")

    except Exception as e:
        print(f"Error processing post {post_id} ({link}): {e}")
    finally:
        driver.quit()

def main():
    # ===========================
    # User Inputs
    # ===========================
    category_url = input("Enter the category URLs (comma-separated): ").strip()
    if not category_url:
        category_url = "https://tuoitre.vn/cong-nghe.htm"
    category_urls = [url.strip() for url in category_url.split(",")]
    k_input = input("Number of posts to retrieve: ").strip()
    try:
        k = int(k_input)
        if k < 100:
            print("Number of posts less than 100. Setting k=100.")
            k = 100
    except (ValueError, TypeError):
        print("Invalid input for number of posts. Setting k=100.")
        k = 100

    # ===========================
    # Create Storage Folders
    # ===========================
    os.removedirs('data')
    os.removedirs('audio')
    os.removedirs('images')
    os.makedirs('data', exist_ok=True)
    os.makedirs('audio', exist_ok=True)
    os.makedirs('images', exist_ok=True)

    # ===========================
    # Setup Selenium WebDriver for Link Collection
    # ===========================
    main_driver = setup_driver()

    # ===========================
    # Collect All Post Links
    # ===========================
    all_post_links = []
    for url in category_urls:
        try:
            post_links = collect_post_links(main_driver, url, k)
            all_post_links.extend(post_links)
            print(f"Collected {len(post_links)} links from {url}")
        except Exception as e:
            print(f"Error processing category URL {url}: {e}")

    main_driver.quit()

    # Limit to k posts
    all_post_links = all_post_links[:k]
    print(f"Total posts to process: {len(all_post_links)}")

    # ===========================
    # Process Posts in Parallel
    # ===========================
    max_workers = min(8, os.cpu_count() or 1)  # Adjust the number of workers based on CPU cores
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for idx, link in enumerate(all_post_links, start=1):
            futures.append(executor.submit(process_post, link, idx))
        
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Exception occurred during processing: {e}")

    print("Crawling completed.")

if __name__ == "__main__":
    main()
