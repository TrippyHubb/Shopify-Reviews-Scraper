import requests
from bs4 import BeautifulSoup
from bs4 import Tag
import pandas as pd
from datetime import datetime
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def fetch_shopify_apps(base_url):
    apps = []
    response = requests.get(base_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    divs = soup.select('div.tw-text-body-sm.tw-font-link')

    for div in divs:
        app_name = div.find('a').text.strip()
        app_url = div.find('a')['href']
        if not app_url.startswith('http'):
            app_url = f"https://apps.shopify.com{app_url}"
        apps.append({'name': app_name, 'url': app_url})

    print(f"✅ Found {len(apps)} apps.")
    return apps

def extract_rating(review):
    rating_div = (
        review.find('div', class_='tw-flex tw-relative tw-space-x-0.5 tw-w-[88px] tw-h-md')
        or review.find('div', attrs={'aria-label': True})
    )
    if rating_div and 'aria-label' in rating_div.attrs:
        try:
            return rating_div['aria-label'].split(' ')[0]
        except IndexError:
            return None
    return None

def parse_review_date(date_str):
    if 'Edited' in date_str:
        date_str = date_str.split('Edited')[1].strip()
    else:
        date_str = date_str.strip()
    try:
        return datetime.strptime(date_str, '%B %d, %Y')
    except ValueError:
        return None

def fetch_reviews(app_url, app_name, start_date, end_date):
    base_url = app_url.split('?')[0]
    if base_url.endswith('/reviews'):
        base_url = base_url.rsplit('/reviews', 1)[0]  # Clean trailing /reviews

    page = 1
    reviews = []

    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    while True:
        reviews_url = f"{base_url}/reviews?sort_by=newest&page={page}"
        print(f"🔗 Fetching: {reviews_url}")

        try:
            response = session.get(reviews_url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        review_divs = soup.find_all("div", attrs={"data-merchant-review": True},
                                    class_="lg:tw-grid lg:tw-grid-cols-4 lg:tw-gap-x-gutter--desktop")

        print(f"🔹 Found {len(review_divs)} reviews on page {page}")
        if not review_divs:
            print('❌ No more reviews found.')
            break

        has_recent_reviews_on_page = False

        for review_div in review_divs:
            review_text_div = review_div.find('div', {'data-truncate-content-copy': True})
            review_text = review_text_div.find('p').text.strip() if review_text_div and review_text_div.find('p') else "No review text"

            reviewer_name = "No reviewer name"
            location = "N/A"
            duration = "N/A"

            reviewer_info_block = (
                review_div.find('div', class_='tw-order-2 lg:tw-order-1 lg:tw-row-span-2 tw-mt-md md:tw-mt-0 tw-space-y-1 md:tw-space-y-2 tw-text-fg-tertiary tw-text-body-xs')
                or review_div.find('div', class_='tw-mt-md')
            )

            if reviewer_info_block:
                reviewer_name_div = (
                    reviewer_info_block.find('div', class_='tw-text-heading-xs tw-text-fg-primary tw-overflow-hidden tw-text-ellipsis tw-whitespace-nowrap')
                    or reviewer_info_block.find('div')
                )
                reviewer_name = reviewer_name_div.text.strip() if reviewer_name_div else "No reviewer name"

                found_location = False
                info_children_divs = [child for child in reviewer_info_block.children if isinstance(child, Tag) and child.name == 'div']
                for child_div in info_children_divs:
                    if child_div == reviewer_name_div:
                        continue
                    text_content = child_div.text.strip()
                    if 'using the app' in text_content:
                        duration = text_content.replace(' using the app', '')
                    elif not found_location and len(text_content) > 0:
                        location = text_content
                        found_location = True

            date_and_rating_container = review_div.find('div', class_='tw-flex tw-items-center tw-justify-between tw-mb-md')
            review_date_str = "No review date"
            if date_and_rating_container:
                review_date_div = (
                    date_and_rating_container.find('div', class_='tw-text-body-xs tw-text-fg-tertiary')
                    or date_and_rating_container.find('div')
                )
                review_date_str = review_date_div.text.strip() if review_date_div else "No review date"

            rating = extract_rating(review_div)
            review_date = parse_review_date(review_date_str)

            if review_date:
                if review_date > start_date:
                    has_recent_reviews_on_page = True
                    continue
                elif start_date >= review_date >= end_date:
                    reviews.append({
                        'app_name': app_name,
                        'review': review_text,
                        'reviewer': reviewer_name,
                        'date': review_date_str,
                        'location': location,
                        'duration': duration,
                        'rating': rating
                    })
                    has_recent_reviews_on_page = True
                else:
                    print(f"🛑 Review too old: {review_date_str}. Stopping for {app_name}.")
                    break
            else:
                print(f"⚠️ Could not parse date for review: '{review_date_str}'. Skipping.")
                continue

        if not has_recent_reviews_on_page and page > 1:
            print(f'✅ All relevant reviews collected for {app_name}.')
            break

        if reviews and review_date and review_date < end_date:
            break

        page += 1
        time.sleep(random.uniform(1.2, 3.0))

    return reviews

# --- Configuration ---
base_url = 'https://apps.shopify.com/checkout-blocks/reviews'  # individual app test
# base_url = 'https://apps.shopify.com/partners/cedcommerce'   # developer test
start_date = datetime(2025, 7, 14)
end_date = datetime(2017, 1, 1)

# --- Main Execution ---
def main():
    print("🔍 Detecting URL type...")

    if "/partners/" in base_url:
        apps = fetch_shopify_apps(base_url)
    elif "apps.shopify.com/" in base_url:
        cleaned_url = base_url.split('?')[0]
        if cleaned_url.endswith('/reviews'):
            cleaned_url = cleaned_url.rsplit('/reviews', 1)[0]
        app_name = cleaned_url.split('/')[-1]
        print(f"🧪 Treating as individual app: {app_name} → {cleaned_url}")
        apps = [{'name': app_name, 'url': cleaned_url}]
    else:
        print("❌ Invalid Shopify URL.")
        return

    print(f"🔹 Total Apps to Fetch: {len(apps)}")

    app_reviews = {}
    for app in apps:
        reviews = fetch_reviews(app['url'], app['name'], start_date, end_date)
        app_reviews[app['name']] = reviews

    print(f"📦 Total Apps with Reviews: {len(app_reviews)}")

    data = []
    for app_name, reviews in app_reviews.items():
        for review in reviews:
            row_data = {
                'app_name': app_name,
                'review': review.get('review', 'No review'),
                'reviewer': review.get('reviewer', 'No reviewer'),
                'date': review.get('date', 'No date'),
                'rating': review.get('rating', 'No rating'),
                'duration': review.get('duration', 'No duration'),
                'location': review.get('location', 'No location'),
            }
            data.append(row_data)

    print(f"📊 Total Reviews Collected: {len(data)}")
    df = pd.DataFrame(data)

    now = datetime.now()
    csv_file_path = f'shopify_app_reviews_{now.strftime("%Y%m%d_%H%M%S")}.csv'
    df.to_csv(csv_file_path, index=False, encoding='utf-8')

    print(f"✅ Data has been written to {csv_file_path}")

if __name__ == '__main__':
    main()
