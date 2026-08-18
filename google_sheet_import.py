from datetime import date

import json
import os
from functools import lru_cache

import numpy as np
import pandas as pd
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


# ---------------------------------------------------------------------------
# Google Sheets
# ---------------------------------------------------------------------------

def get_google_sheet_data():
    """Load and clean expense data from the Responses sheet."""

    service_account_info = json.loads(
        os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    )

    SPREADSHEET_ID = "1MVeRNsn2NJaLaHRGiSYtZYq9RyKD7MNE7bYYAMbUX6g"
    RANGE_NAME = "Responses"

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly"
    ]

    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=scopes,
    )

    # Build the service
    service = build("sheets", "v4", credentials=creds)

    # Call the Sheets API
    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME,
    ).execute()

    values = result.get("values", [])

    if not values:
        return pd.DataFrame(), pd.DataFrame()

    # Convert to DataFrame
    headers = values[0]
    rows = values[1:]

    df = pd.DataFrame(rows, columns=headers)

    # -----------------------------------------------------------------------
    # Data types
    # -----------------------------------------------------------------------

    df["Timestamp"] = pd.to_datetime(
        df["Timestamp"],
        format="%m/%d/%Y %H:%M:%S",
        errors="coerce",
    )

    df["Category"] = df["Category"].astype("string")
    df["Currency"] = df["Currency"].astype("string")
    df["Person"] = df["Person"].astype("string")
    df["Extra Note"] = df["Extra Note"].astype("string")

    df["Price"] = pd.to_numeric(
        df["Price"],
        errors="coerce",
    )

    df["First Night in Accom"] = pd.to_datetime(
        df["First Night in Accom"],
        format="%m/%d/%Y",
        errors="coerce",
    )

    df["Total Nights in Accom"] = pd.to_numeric(
        df["Total Nights in Accom"],
        errors="coerce",
    ).astype("Int64")

    # -----------------------------------------------------------------------
    # Expense date
    # -----------------------------------------------------------------------

    purchase_col = "Expense Date"

    purchase_raw = df[purchase_col].replace(
        ["", " ", "NA"],
        pd.NA,
    )

    purchase_dt = pd.to_datetime(
        purchase_raw,
        errors="coerce",
    )

    df["Expense Date"] = (
        purchase_dt
        .fillna(df["Timestamp"])
        .dt.normalize()
    )

    # -----------------------------------------------------------------------
    # Separate transfers
    # -----------------------------------------------------------------------

    transfer_df = df[df["Category"] == "Transfer"].copy()

    df = df[df["Category"] != "Transfer"].copy()

    return df, transfer_df

# ---------------------------------------------------------------------------
# Both
# ---------------------------------------------------------------------------

def split_both_rows(df):
    """
    Split rows where user is 'both' into two duplicate rows, one for Jesse and one for Bridget
    """

    rows = []

    for _, row in df.iterrows():
        user = str(
            row.get("Person", "")
        ).strip().casefold()

        if user == "both":
            for person in ["Jesse", "Bridget"]:
                new_row = row.copy()
                new_row["Person"] = person
                new_row["Price"] = row.get("Price") / 2
                rows.append(new_row)
        else:
            rows.append(row.copy())

    out = pd.DataFrame(rows).reset_index(drop=True)

    return out

# ---------------------------------------------------------------------------
# Accommodation
# ---------------------------------------------------------------------------

def split_accommodation_rows(df):
    """
    Expand accommodation purchases into one row per night.

    The Google Sheet stores the full accommodation charge on a single row,
    alongside the first night and the total number of nights.

    This helper turns that into daily rows so downstream charts and averages
    treat each night as its own expense.
    """

    rows = []

    for _, row in df.iterrows():
        category = str(
            row.get("Category", "")
        ).strip().casefold()

        first_night = row.get("First Night in Accom")
        nights_raw = row.get("Total Nights in Accom")
        price = row.get("Price")

        is_accom = category in {"accom", "accommodation"}
        has_accom_dates = pd.notna(first_night)
        has_nights = pd.notna(nights_raw)

        if (
            is_accom
            and has_accom_dates
            and has_nights
            and pd.notna(price)
        ):
            try:
                total_nights = int(float(nights_raw))
            except (TypeError, ValueError):
                total_nights = 0

            if total_nights > 0:
                nightly_price = price / total_nights

                for night in range(total_nights):
                    new_row = row.copy()

                    accom_date = (
                        pd.Timestamp(first_night)
                        + pd.Timedelta(days=night)
                    ).normalize()

                    new_row["Expense Date"] = accom_date
                    new_row["Price"] = nightly_price
                    new_row["Total Nights in Accom"] = 1

                    if "Accommodation Night" in new_row.index:
                        new_row["Accommodation Night"] = accom_date

                    rows.append(new_row)

                continue

        rows.append(row.copy())

    out = pd.DataFrame(rows).reset_index(drop=True)

    out["Expense Date"] = (
        pd.to_datetime(
            out["Expense Date"],
            errors="coerce",
        )
        .dt.normalize()
    )

    return out


# ---------------------------------------------------------------------------
# Frankfurter v2
# ---------------------------------------------------------------------------

def add_nzd_converted_column(df):
    """
    Add a 'Price NZD' column using Frankfurter API v2.

    Frankfurter v2 returns rates in a flat format:

        [
            {
                "date": "2026-07-14",
                "base": "NZD",
                "quote": "USD",
                "rate": 0.58
            },
            ...
        ]

    Since the expense data can contain multiple currencies and dates,
    we request the complete NZD-based time series once and reshape it
    into a date/currency lookup.

    For weekends/holidays where no rate exists, the most recent earlier
    available rate is used, matching the behaviour of the original code.
    """

    df = df.copy()

    if df.empty:
        df["Price NZD"] = pd.Series(
            dtype="Float64",
            index=df.index,
        )
        return df

    # -----------------------------------------------------------------------
    # Clean expense dates
    # -----------------------------------------------------------------------

    df["Expense Date"] = (
        pd.to_datetime(
            df["Expense Date"],
            errors="coerce",
        )
        .dt.normalize()
    )

    valid_dates = df["Expense Date"].dropna()

    if valid_dates.empty:
        df["Price NZD"] = pd.Series(
            pd.NA,
            index=df.index,
            dtype="Float64",
        )
        return df

    start_date = valid_dates.min().date()

    # Do not ask Frankfurter for future rates.
    end_date = min(
        valid_dates.max().date(),
        date.today(),
    )

    if start_date > end_date:
        df["Price NZD"] = pd.Series(
            pd.NA,
            index=df.index,
            dtype="Float64",
        )
        return df

    # -----------------------------------------------------------------------
    # Fetch Frankfurter v2 rates
    # -----------------------------------------------------------------------

    url = "https://api.frankfurter.dev/v2/rates"

    params = {
        "base": "NZD",
        "from": start_date.strftime("%Y-%m-%d"),
        "to": end_date.strftime("%Y-%m-%d"),
    }

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    # v2 returns a flat list:
    #
    # [
    #     {
    #         "date": "2026-07-14",
    #         "base": "NZD",
    #         "quote": "USD",
    #         "rate": 0.58
    #     },
    #     ...
    # ]

    if not data:
        df["Price NZD"] = pd.Series(
            pd.NA,
            index=df.index,
            dtype="Float64",
        )
        return df

    rates_df = pd.DataFrame(data)

    # -----------------------------------------------------------------------
    # Normalise the v2 response
    # -----------------------------------------------------------------------

    rates_df["date"] = pd.to_datetime(
        rates_df["date"],
        errors="coerce",
    ).dt.normalize()

    rates_df["quote"] = (
        rates_df["quote"]
        .astype("string")
        .str.upper()
    )

    rates_df["rate"] = pd.to_numeric(
        rates_df["rate"],
        errors="coerce",
    )

    rates_df = rates_df.dropna(
        subset=["date", "quote", "rate"]
    )

    # Create:
    #
    #                         quote
    # date              AUD    USD    GBP ...
    # 2026-01-01        ...    ...    ...
    # 2026-01-02        ...    ...    ...
    #
    rates_lookup = rates_df.pivot_table(
        index="date",
        columns="quote",
        values="rate",
        aggfunc="last",
    ).sort_index()

    # -----------------------------------------------------------------------
    # Make sure we can look backwards for weekends/holidays
    # -----------------------------------------------------------------------

    expense_dates = (
        pd.Series(
            df["Expense Date"].dropna().unique()
        )
        .sort_values()
    )

    # Reindex the rates to every expense date and forward-fill.
    #
    # Example:
    #
    # Friday     -> rate available
    # Saturday   -> Friday rate
    # Sunday     -> Friday rate
    # Monday     -> Monday rate
    #
    # This is equivalent to the original "look backwards up to 120 days"
    # behaviour, but done efficiently for the entire dataset.

    all_dates = pd.DatetimeIndex(expense_dates)

    rates_for_expenses = (
        rates_lookup
        .reindex(all_dates)
        .ffill()
    )

    # -----------------------------------------------------------------------
    # Convert prices to NZD
    # -----------------------------------------------------------------------

    def convert_to_nzd(row):
        currency = row["Currency"]
        price = row["Price"]
        expense_date = row["Expense Date"]

        if (
            pd.isna(price)
            or pd.isna(expense_date)
            or pd.isna(currency)
        ):
            return pd.NA

        currency = str(currency).strip().upper()

        # Already NZD
        if currency == "NZD":
            return price

        try:
            rate = rates_for_expenses.loc[
                expense_date,
                currency,
            ]
        except (KeyError, TypeError):
            return pd.NA

        if pd.isna(rate):
            return pd.NA

        # Frankfurter gives:
        #
        #     1 NZD = X foreign currency
        #
        # Therefore:
        #
        #     foreign amount / X = NZD amount
        #
        return price / rate

    df["Price NZD"] = df.apply(
        convert_to_nzd,
        axis=1,
    )

    return df


# ---------------------------------------------------------------------------
# Final processed dataset
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_processed_data():
    df_full, transfer = get_google_sheet_data()

    df_both_split = split_both_rows(
        df_full
    )

    df_accom_split = split_accommodation_rows(
        df_both_split
    )

    df_final = add_nzd_converted_column(
        df_accom_split
    )

    transfer = transfer.drop(
        columns=[
            "First Night in Accom",
            "Total Nights in Accom",
            "Category",
            "Expense Date",
            "Currency",
        ],
        errors="ignore",
    )

    return df_final, transfer


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_locations_data():
    service_account_info = json.loads(
        os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    )

    SPREADSHEET_ID = (
        "1MVeRNsn2NJaLaHRGiSYtZYq9RyKD7MNE7bYYAMbUX6g"
    )

    RANGE_NAME = "Locations"

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly"
    ]

    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=scopes,
    )

    service = build(
        "sheets",
        "v4",
        credentials=creds,
    )

    sheet = service.spreadsheets()

    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME,
    ).execute()

    values = result.get("values", [])

    if not values or len(values) < 2:
        return pd.DataFrame(
            columns=[
                "Timestamp",
                "latitude",
                "longitude",
                "town",
                "country",
            ]
        )

    headers = values[0]
    rows = values[1:]

    df = pd.DataFrame(
        rows,
        columns=headers,
    )

    df = df.rename(
        columns={
            "Timestamp": "Date"
        }
    )

    df["Date"] = (
        pd.to_datetime(
            df["Date"],
            errors="coerce",
        )
        .dt.normalize()
    )

    df["latitude"] = pd.to_numeric(
        df["latitude"],
        errors="coerce",
    )

    df["longitude"] = pd.to_numeric(
        df["longitude"],
        errors="coerce",
    )

    df["town"] = df["town"].astype("string")
    df["country"] = df["country"].astype("string")

    return df