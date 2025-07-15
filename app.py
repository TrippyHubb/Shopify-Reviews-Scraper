import streamlit as st
import pandas as pd
from datetime import datetime, date
from scraper import fetch_shopify_apps, fetch_reviews  # all logic is in scraper.py

# Set up page
st.set_page_config(page_title="Shopify Review Scraper", layout="wide")
st.title("📦 Shopify Review Scraper")

# User inputs
developer_url = st.text_input("Enter Shopify Developer URL (e.g. https://apps.shopify.com/partners/cedcommerce)")

# Date inputs
start_date = st.date_input("Start Date", value=date.today())
end_date = st.date_input("End Date", value=date(2017, 1, 1))

# 🛠 Fix: Convert date to datetime to avoid TypeError
start_date = datetime.combine(start_date, datetime.min.time())
end_date = datetime.combine(end_date, datetime.min.time())

if st.button("Fetch Reviews"):
    if not developer_url.strip():
        st.warning("⚠️ Please enter a valid Shopify developer URL.")
    else:
        with st.spinner("🔍 Fetching apps..."):
            apps = fetch_shopify_apps(developer_url)

        st.success(f"✅ Found {len(apps)} apps.")

        all_reviews = []
        for app in apps:
            st.write(f"📘 Fetching reviews for: **{app['name']}**")
            reviews = fetch_reviews(app['url'], app['name'], start_date, end_date)
            all_reviews.extend(reviews)

        if all_reviews:
            df = pd.DataFrame(all_reviews)
            st.write("📊 Reviews Preview:")
            st.dataframe(df)

            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Reviews as CSV", csv, "shopify_reviews.csv", "text/csv")
        else:
            st.warning("😕 No reviews found for the selected date range.")
