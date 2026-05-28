
import pandas as pd
import numpy as np
import os
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import requests

import json


def get_google_sheet_data():
    # Configuration
    SERVICE_ACCOUNT_FILE = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    SPREADSHEET_ID = '1MVeRNsn2NJaLaHRGiSYtZYq9RyKD7MNE7bYYAMbUX6g'
    RANGE_NAME = 'Responses' 
    
    #Gets google sheet data as a list 
    scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)

    # Build the service
    service = build('sheets', 'v4', credentials=creds)

    # Call the Sheets API
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    values = result.get('values', [])
  
  #Converting to dataframe
    headers = values[0]
    rows = values[1:]

    df = pd.DataFrame(rows, columns=headers)

    df["Timestamp"] = pd.to_datetime(df["Timestamp"],format="%m/%d/%Y %H:%M:%S", errors="coerce")

    df["Category"] = df["Category"].astype("string")
    df["Currency"] = df["Currency"].astype("string")
    df["Person"] = df["Person"].astype("string")
    df["Extra Note"] = df["Extra Note"].astype("string")

    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")

    df["First Night in Accom"] = pd.to_datetime(
        df["First Night in Accom"], format="%m/%d/%Y", errors="coerce"
    )

    df["Total Nights in Accom"] = pd.to_numeric(
        df["Total Nights in Accom"], errors="coerce"
    ).astype("Int64")   


    purchase_col = "Expense Date"

    purchase_raw = df[purchase_col].replace(["", " ", "NA"], pd.NA)

    purchase_dt = pd.to_datetime(purchase_raw, errors="coerce")

    df["Expense Date"] = (
        purchase_dt
        .fillna(df["Timestamp"])
        .dt.normalize()
    )
    transfer_df = df[df["Category"] == 'Transfer']

    df = df[df["Category"] != 'Transfer']

    return df, transfer_df

#Helper function to split accomodation rows
def split_accommodation_rows(df):
    rows = []

    for _, row in df.iterrows():
        is_accom = row["Category"] == "Accommodation"
        has_accom_dates = pd.notna(row["First Night in Accom"])
        has_nights = pd.notna(row["Total Nights in Accom"])

        if is_accom and has_accom_dates and has_nights:
            total_nights = int(row["Total Nights in Accom"])
            nightly_price = row["Price"] / total_nights

            for night in range(total_nights):
                new_row = row.copy()

                accom_date = (
                    row["First Night in Accom"] + pd.Timedelta(days=night)
                ).normalize()

                new_row["Expense Date"] = accom_date
                new_row["Price"] = nightly_price
                new_row["Total Nights in Accom"] = 1

                rows.append(new_row)
        else:
            rows.append(row.copy())

    return pd.DataFrame(rows).reset_index(drop=True)

    # mask = (
    #     (df_accom_split["Category"] == "Accommodation") &
    #     (df_accom_split["Accommodation Night"].notna())
    # )

    # df_accom_split.loc[mask, "Expense Date"] = df_accom_split.loc[mask, "Accommodation Night"]


#Helper function to convert values to nzd
def add_nzd_converted_column(df):
    df = df.copy()

    rate_cache = {}

    unique_dates = sorted(
        pd.to_datetime(df["Expense Date"], errors="coerce")
        .dropna()
        .dt.normalize()
        .unique()
    )

    def fetch_rates_for_date(target_date, max_lookback_days=3650):
        """Return rates for target_date or the most recent earlier available date."""
        current_date = pd.Timestamp(target_date).normalize()
        lower_bound = current_date - pd.Timedelta(days=max_lookback_days)

        while current_date >= lower_bound:
            expense_date = current_date.strftime("%Y-%m-%d")

            if expense_date in rate_cache:
                return rate_cache[expense_date]

            url = f"https://api.frankfurter.dev/v1/{expense_date}"
            params = {"base": "NZD"}

            try:
                response = requests.get(url, params=params, timeout=20)
                if response.status_code == 404:
                    current_date -= pd.Timedelta(days=1)
                    continue

                response.raise_for_status()
                data = response.json()
                rates = data.get("rates", {})

                rate_cache[expense_date] = rates
                return rates

            except requests.RequestException:
                # For transient errors, try the previous date as well.
                current_date -= pd.Timedelta(days=1)

        return None

    for expense_date in unique_dates:
        rate_cache[expense_date.strftime("%Y-%m-%d")] = fetch_rates_for_date(expense_date)

    def convert_to_nzd(row):
        currency = row["Currency"]
        price = row["Price"]

        if pd.isna(price) or pd.isna(row["Expense Date"]) or pd.isna(currency):
            return pd.NA

        expense_date = pd.to_datetime(row["Expense Date"]).strftime("%Y-%m-%d")

        if currency == "NZD":
            return price

        rates = rate_cache.get(expense_date)

        if not rates or currency not in rates:
            return pd.NA

        return price / rates[currency]

    df["Price NZD"] = df.apply(convert_to_nzd, axis=1)

    return df

#Final Function to load fully processed dataset
from functools import lru_cache

@lru_cache(maxsize=1)
def load_processed_data():
    df_full,transfer = get_google_sheet_data()
    df_accom_split = split_accommodation_rows(df_full)    

    df_final = add_nzd_converted_column(df_accom_split)

    return df_final, transfer.drop(columns=['First Night in Accom', 'Total Nights in Accom', 'Category', 'Expense Date', 'Currency'])





@lru_cache(maxsize=1)
def load_locations_data():
    SERVICE_ACCOUNT_FILE = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    SPREADSHEET_ID = "1MVeRNsn2NJaLaHRGiSYtZYq9RyKD7MNE7bYYAMbUX6g"
    RANGE_NAME = "Locations"
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    service = build("sheets", "v4", credentials=creds)

    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME
    ).execute()

    values = result.get("values", [])
    if not values or len(values) < 2:
        return pd.DataFrame(columns=["Timestamp", "latitude", "longitude", "town", 'country'])

    headers = values[0]
    rows = values[1:]
    df = pd.DataFrame(rows, columns=headers)

    df = df.rename(columns={"Timestamp": "Date"})

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.normalize()
    df["latitude"] = df["latitude"].astype("float")
    df["longitude"] = df["longitude"].astype("float")
    df["town"] = df["town"].astype("string")
    df["country"] = df["country"].astype("string")

    return df

