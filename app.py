import streamlit as st
import pandas as pd
from datetime import datetime, date, time # Import time as well for datetime.combine
from urllib.parse import urlparse

# Assuming your combined scraping logic is in a file named 'scraper.py'
# If you put the combined code directly into this file, you can remove these imports
from scraper import fetch_shopify_apps, fetch_reviews, parse_review_date, extract_rating


st.set_page_config(page_title="Shopify Review Scraper", layout="wide")
st.title("📦 Shopify Review Scraper")

# Single input for the URL
input_url = st.text_input("Enter Shopify URL {Developer Page or Single App Review Page(Please Select All Review then Copy the URL)}",
                           value="Example Of Developer Page URL: https://apps.shopify.com/partners/cedcommerce Example Of Single Page URL: https://apps.shopify.com/amazon-by-cedcommerce/reviews") # Default value for testing

# Get date inputs from Streamlit
start_date_input = st.date_input("Fetch From (Latest Date)", value=date.today())
end_date_input = st.date_input("Fetch Until (Earliest Date)", value=datetime(2017, 1, 1))

# Convert date objects to datetime objects for consistent comparison in scraper.py
# Set time to midnight (00:00:00) for the start date
start_date = datetime.combine(start_date_input, time.min)
# Set time to the end of the day (23:59:59) for the end date to include the full day
end_date = datetime.combine(end_date_input, time.max)


if st.button("Fetch Reviews"):
    if not input_url:
        st.warning("Please enter a Shopify URL.")
    else:
        all_collected_reviews = []
        csv_filename_prefix = "shopify_reviews" # Default prefix

        with st.spinner("Detecting URL type and fetching reviews..."):
            if "/partners/" in input_url:
                st.info("Detected developer page URL. Fetching all apps from this developer.")
                apps = fetch_shopify_apps(input_url)
                st.success(f"Found {len(apps)} apps.")

                # Extract developer handle for CSV naming
                parsed_url = urlparse(input_url)
                path_segments = [s for s in parsed_url.path.split('/') if s]
                developer_handle = path_segments[-1] if path_segments else "unknown_developer"
                csv_filename_prefix = f'shopify_developer_reviews_{developer_handle}'

                for app in apps:
                    st.write(f"🔍 Fetching reviews for: {app['name']}")
                    # Pass the converted datetime objects
                    reviews = fetch_reviews(app['url'], app['name'], start_date, end_date)
                    for review in reviews:
                        review['app_name'] = app['name'] # Ensure app_name is set
                        all_collected_reviews.append(review)

            elif input_url.endswith("/reviews"):
                st.info("Detected single app review page URL.")
                parsed_url = urlparse(input_url)
                path_segments = [s for s in parsed_url.path.split('/') if s]

                app_handle = path_segments[-2] if len(path_segments) >= 2 and path_segments[-1] == 'reviews' else None
                if not app_handle:
                    st.error("Could not parse app name from URL ending with /reviews. Please check the URL format.")
                    st.stop()

                base_app_url = f"https://apps.shopify.com/{app_handle}"
                app_name = app_handle.replace('-', ' ').title()

                st.write(f"🔍 Fetching reviews for: {app_name} ({base_app_url})")
                # Pass the converted datetime objects
                reviews = fetch_reviews(base_app_url, app_name, start_date, end_date)

                for review in reviews:
                    review['app_name'] = app_name # Ensure app_name is set
                    all_collected_reviews.append(review)

                csv_filename_prefix = f'shopify_single_app_reviews_{app_name.replace(" ", "_").lower()}'

            else:
                st.error("Invalid Shopify URL provided. Please provide a developer page URL (e.g., `https://apps.shopify.com/partners/developer_name`) or a single app review page URL (e.g., `https://apps.shopify.com/app_name/reviews`).")
                st.stop()

        st.success(f"Finished fetching reviews. Total collected: {len(all_collected_reviews)}")

        if all_collected_reviews:
            df = pd.DataFrame(all_collected_reviews)
            st.dataframe(df)

            # Generate a timestamped filename for the CSV output.
            now = datetime.now()
            csv_file_path = f'{csv_filename_prefix}_{now.strftime("%Y%m%d_%H%M%S")}.csv'

            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=csv_file_path,
                mime="text/csv"
            )
        else:
            st.warning("No reviews found for the given URL and date range.")
