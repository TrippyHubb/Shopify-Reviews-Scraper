import streamlit as st
import pandas as pd
from datetime import datetime
from scraper import fetch_shopify_apps, fetch_reviews  # Import your logic

st.set_page_config(page_title="Shopify Review Scraper", layout="wide")
st.title("📦 Shopify Review Scraper")

developer_url = st.text_input("Enter Shopify Developer URL (e.g. https://apps.shopify.com/partners/cedcommerce)")
start_date = st.date_input("Start Date", value=datetime(2025, 7, 14))
end_date = st.date_input("End Date", value=datetime(2017, 1, 1))

if st.button("Fetch Reviews"):
    if not developer_url:
        st.warning("Please enter a developer URL.")
    else:
        with st.spinner("Fetching apps..."):
            apps = fetch_shopify_apps(developer_url)
        st.success(f"Found {len(apps)} apps.")

        all_reviews = []
        for app in apps:
            st.write(f"🔍 Fetching reviews for: {app['name']}")
            reviews = fetch_reviews(app['url'], app['name'], start_date, end_date)
            all_reviews.extend(reviews)

        if all_reviews:
            df = pd.DataFrame(all_reviews)
            st.dataframe(df)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv, "shopify_reviews.csv", "text/csv")
        else:
            st.warning("No reviews found.")
