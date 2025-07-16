# Combined for Single App and Developer Page
import requests
from bs4 import BeautifulSoup
from bs4 import Tag
import pandas as pd
from datetime import datetime
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse # Import urlparse to extract app name from URL


def fetch_shopify_apps(base_url):
    """
    Fetches a list of all Shopify apps associated with a given developer page.

    Args:
        base_url (str): The base URL of the Shopify developer's app page.

    Returns:
        list: A list of dictionaries, where each dictionary contains the 'name'
              and 'url' of an app.
    """
    apps = []
    try:
        response = requests.get(base_url)
        response.raise_for_status() # Raise an exception for bad status codes
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to fetch developer page {base_url}: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')

    # Select all div elements that contain the app name and link.
    divs = soup.select('div.tw-text-body-sm.tw-font-link')

    for div in divs:
        app_name_tag = div.find('a')
        if app_name_tag:
            app_name = app_name_tag.text.strip()
            app_url = app_name_tag['href']

            # Ensure the app URL is absolute.
            if not app_url.startswith('http'):
                app_url = f"https://apps.shopify.com{app_url}"
            apps.append({'name': app_name, 'url': app_url})

    print(f"✅ Found {len(apps)} apps on developer page.")
    return apps

def extract_rating(review):
    """
    Extracts the star rating from a given review's BeautifulSoup object.

    Args:
        review (bs4.Tag): A BeautifulSoup Tag object representing a single review block.

    Returns:
        str or None: The star rating (e.g., "5") if found, otherwise None.
    """
    # Find the div containing the aria-label with the rating information.
    rating_div = review.find('div', class_='tw-flex tw-relative tw-space-x-0.5 tw-w-[88px] tw-h-md')
    if rating_div and 'aria-label' in rating_div.attrs:
        aria_label = rating_div['aria-label']
        try:
            # The rating is typically the first part of the aria-label (e.g., "5 out of 5 stars").
            return aria_label.split(' ')[0]
        except IndexError:
            return None
    return None

def parse_review_date(date_str):
    """
    Converts a Shopify review date string into a Python datetime object.

    Handles cases where the date string might include "Edited".

    Args:
        date_str (str): The date string from the review (e.g., "June 1, 2024" or "Edited June 1, 2024").

    Returns:
        datetime or None: A datetime object if parsing is successful, otherwise None.
    """
    if 'Edited' in date_str:
        date_str = date_str.split('Edited')[1].strip()
    else:
        date_str = date_str.strip()
    try:
        return datetime.strptime(date_str, '%B %d, %Y')
    except ValueError:
        return None

def fetch_reviews(app_url, app_name, start_date, end_date):
    """
    Fetches all reviews for a specific Shopify app within a given date range.

    Reviews are fetched page by page, sorted by newest, until an old review
    (outside the start_date and end_date range) is encountered. Includes
    a retry mechanism for robustness.

    Args:
        app_url (str): The URL of the Shopify app's page (e.g., https://apps.shopify.com/app-name).
        app_name (str): The name of the Shopify app.
        start_date (datetime): The inclusive start date for review collection.
        end_date (datetime): The inclusive end date for review collection.

    Returns:
        list: A list of dictionaries, where each dictionary represents a review
              with details like text, reviewer, date, rating, location, and duration.
    """
    # Ensure the URL is clean and points to the app's base page, not directly to reviews.
    # If the URL already contains '/reviews', remove it for constructing the base URL.
    if '/reviews' in app_url:
        base_url = app_url.split('/reviews')[0]
    else:
        base_url = app_url.split('?')[0] # Clean any query parameters if present

    page = 1
    reviews = []

    # Configure retries for the requests session
    retry_strategy = Retry(
        total=5,  # Total number of retries
        backoff_factor=1,  # Factor by which delay increases (1, 2, 4, 8, 16 seconds)
        status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
        allowed_methods=["HEAD", "GET", "OPTIONS"]  # HTTP methods to retry
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)


    while True:
        print(f"Fetching page {page} for {app_name}...")
        # Construct the reviews URL correctly, ensuring it's always '/reviews?sort_by=newest&page=X'
        reviews_url = f"{base_url}/reviews?sort_by=newest&page={page}"

        try:
            response = session.get(reviews_url)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed for {reviews_url}: {e}")
            # If the request fails after retries, stop fetching for this app.
            break


        soup = BeautifulSoup(response.content, 'html.parser')

        # Select all review blocks based on their attributes and class.
        review_divs = soup.find_all("div", attrs={"data-merchant-review": True},
                                     class_="lg:tw-grid lg:tw-grid-cols-4 lg:tw-gap-x-gutter--desktop")

        print(f"🔹 Found {len(review_divs)} reviews on page {page}")

        if not review_divs:
            print('❌ No more reviews found. Stopping.')
            break

        has_recent_reviews_on_page = False

        for review_div in review_divs:
            # Extract review text.
            review_text_div = review_div.find('div', {'data-truncate-content-copy': True})
            review_text = review_text_div.find('p').text.strip() if review_text_div and review_text_div.find('p') else "No review text"

            reviewer_name = "No reviewer name"
            location = "N/A"
            duration = "N/A"

            # Locate the reviewer information block.
            reviewer_info_block = review_div.find('div', class_='tw-order-2 lg:tw-order-1 lg:tw-row-span-2 tw-mt-md md:tw-mt-0 tw-space-y-1 md:tw-space-y-2 tw-text-fg-tertiary tw-text-body-xs')

            if reviewer_info_block:
                # Extract reviewer name.
                reviewer_name_div = reviewer_info_block.find('div', class_='tw-text-heading-xs tw-text-fg-primary tw-overflow-hidden tw-text-ellipsis tw-whitespace-nowrap')
                reviewer_name = reviewer_name_div.text.strip() if reviewer_name_div else "No reviewer name"

                # Extract location and duration by iterating through child divs.
                found_location = False
                info_children_divs = [child for child in reviewer_info_block.children if isinstance(child, Tag) and child.name == 'div']

                for child_div in info_children_divs:
                    if child_div == reviewer_name_div: # Skip the name div itself.
                        continue

                    text_content = child_div.text.strip()
                    if 'using the app' in text_content: # Identify duration by a specific phrase.
                        duration = text_content.replace(' using the app', '')
                    elif not found_location and len(text_content) > 0: # Assign first non-empty div to location.
                        location = text_content
                        found_location = True

            # Extract review date.
            date_and_rating_container = review_div.find('div', class_='tw-flex tw-items-center tw-justify-between tw-mb-md')
            review_date_str = "No review date"
            if date_and_rating_container:
                review_date_div = date_and_rating_container.find('div', class_='tw-text-body-xs tw-text-fg-tertiary')
                review_date_str = review_date_div.text.strip() if review_date_div else "No review date"

            # Extract rating using the helper function.
            rating = extract_rating(review_div)

            # Parse the date string into a datetime object for comparison.
            review_date = parse_review_date(review_date_str)

            # Ensure review_date is not None before comparison
            if review_date is not None:
                # Check if the review date is too new (after start_date).
                if review_date > start_date:
                    has_recent_reviews_on_page = True
                    continue
                # Check if the review date is within the desired range.
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
                    # If the review is older than the end_date, stop fetching for this app.
                    print(f"🛑 Review too old: {review_date_str}. Stopping for {app_name}.")
                    break # Break out of the inner for loop
            else:
                print(f"⚠️ Could not parse date for review: '{review_date_str}'. Skipping.")
                continue # Skip this review if its date can't be parsed.

        # Logic to determine if we should stop fetching pages.
        # If no recent reviews were found on the current page (and it's not the first page),
        # or if an old review caused the inner loop to break, stop.
        if not has_recent_reviews_on_page and page > 1:
            print(f'✅ All relevant reviews collected for {app_name}, or no new reviews found in the date range on this page.')
            break

        # If the inner loop broke because a review was too old, break the outer loop as well.
        # This condition is also refined to ensure review_date is not None.
        if reviews and review_date is not None and review_date < end_date:
            break

        page += 1
        # Introduce a random delay to avoid overwhelming the server.
        time.sleep(random.uniform(1.2, 3.0))

    return reviews

# --- Configuration ---
# Set the URL you want to scrape here.
# Example Developer Page: 'https://apps.shopify.com/partners/cedcommerce'
# Example Single App Page: 'https://apps.shopify.com/checkout-blocks/reviews'
input_url = "https://apps.shopify.com/partners/cedcommerce" # This is for local testing of scraper.py


# Define the date range for collecting reviews.
# Reviews older than 'end_date' will be ignored, and fetching will stop if
# a review older than 'end_date' is encountered.
# (Current date for context: July 16, 2025)
start_date = datetime(2025, 7, 16) # Includes reviews published today or earlier.
end_date = datetime(2017, 1, 1)    # Collects reviews up to this date (inclusive).

# --- Main Execution ---
def main():
    """
    Main function to orchestrate fetching app details and their reviews,
    then saving the collected data to a CSV file, based on the URL type.
    This main function is primarily for direct execution of scraper.py.
    For Streamlit, the logic is handled within app.py.
    """
    all_collected_reviews = []

    if "/partners/" in input_url:
        print("Detected developer page URL.")
        apps = fetch_shopify_apps(input_url)
        print(f"🔹 Total Apps Found: {len(apps)}")

        for app in apps:
            reviews = fetch_reviews(app['url'], app['name'], start_date, end_date)
            for review in reviews:
                review['app_name'] = app['name']
                all_collected_reviews.append(review)

        parsed_url = urlparse(input_url)
        path_segments = [s for s in parsed_url.path.split('/') if s]
        developer_handle = path_segments[-1] if path_segments else "unknown_developer"
        csv_filename_prefix = f'shopify_developer_reviews_{developer_handle}'

    elif input_url.endswith("/reviews"):
        print("Detected single app review page URL.")
        parsed_url = urlparse(input_url)
        path_segments = [s for s in parsed_url.path.split('/') if s]

        app_handle = path_segments[-2] if len(path_segments) >= 2 and path_segments[-1] == 'reviews' else None
        if not app_handle:
            print("❌ Could not parse app name from URL ending with /reviews. Exiting.")
            return

        base_app_url = f"https://apps.shopify.com/{app_handle}"
        app_name = app_handle.replace('-', ' ').title()

        print(f"🔹 Fetching reviews for single app: {app_name} ({base_app_url})")

        reviews = fetch_reviews(base_app_url, app_name, start_date, end_date)

        for review in reviews:
            review['app_name'] = app_name
            all_collected_reviews.append(review)

        csv_filename_prefix = f'shopify_single_app_reviews_{app_name.replace(" ", "_").lower()}'

    else:
        print("❌ Invalid Shopify URL provided. Please provide a developer page URL (e.g., https://apps.shopify.com/partners/developer_name) or a single app review page URL (e.g., https://apps.shopify.com/app_name/reviews).")
        return

    print(f"🔹 Total Reviews Collected: {len(all_collected_reviews)}")

    if all_collected_reviews:
        df = pd.DataFrame(all_collected_reviews)
        now = datetime.now()
        csv_file_path = f'{csv_filename_prefix}_{now.strftime("%Y%m%d_%H%M%S")}.csv'
        df.to_csv(csv_file_path, index=False, encoding='utf-8')
        print(f"✅ Data has been written to {csv_file_path}")
    else:
        print("No reviews were collected. CSV file not created.")

if __name__ == '__main__':
    main()
