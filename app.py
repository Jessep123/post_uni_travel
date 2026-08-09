#Required packages and whatnot
import json
import os

from datetime import date
from xmlrpc.client import Transport

from google_sheet_import import load_processed_data
import pandas as pd
import numpy as np
import matplotlib

from faicons import icon_svg
import plotly.express as px
import plotly.io as pio

# Load data and compute static values
from shinywidgets import render_plotly

from shiny import reactive, render
from shiny.express import input, ui, app

from google_sheet_import import load_locations_data
import plotly.graph_objs as go

# importing data
df_full, transfer_df = load_processed_data()
df_locations = load_locations_data()
df_full = df_full.merge(
    df_locations[["Date", "country"]],
    left_on="Expense Date",
    right_on="Date",
    how="left"
)
df_full = df_full.drop(columns=["Date"])

df_full["country"] = (
    df_full["country"]
    .fillna("NA")
    .astype("string")
)

df_data = reactive.value(df_full)

def rebuild_data():
    global df_full, transfer_df, df_locations, min_date, max_date

    # clear cached loaders so the next call hits Google Sheets again
    load_processed_data.cache_clear()
    load_locations_data.cache_clear()

    # reload fresh data
    df_full, transfer_df = load_processed_data()
    df_locations = load_locations_data()

    # rebuild merged dataset
    df_full = df_full.merge(
        df_locations[["Date", "country"]],
        left_on="Expense Date",
        right_on="Date",
        how="left",
    )
    df_full = df_full.drop(columns=["Date"])
    df_full["country"] = df_full["country"].fillna("NA").astype("string")

    # update date bounds used by the UI
    min_date = df_full["Expense Date"].min().date()
    max_date = df_full["Expense Date"].max().date()
# ================================================================================================================================
# UI
# ================================================================================================================================
# Add page title and sidebar
ui.page_opts(title="Jesse + Bridget Camino Adventure", fillable=True)

ui.tags.style("""
.bslib-value-box {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 16px;
}

.bslib-value-box .value-box-showcase {
    order: 0;
    flex-shrink: 0;
    margin: 0;
}

.bslib-value-box .value-box-area {
    order: 1;
    flex: 1;
}
""")

# ================================================================================================================================
# Sidebar
# ================================================================================================================================
with ui.layout_sidebar():
    with ui.sidebar(open="desktop"):
        min_date = df_full["Expense Date"].min().date()
        max_date = df_full["Expense Date"].max().date()

        ui.input_date_range(
            "date_range",
            "Select date range",
            start=min_date,
            end=max_date,
            min=min_date,
            max=max_date,
        )

        ui.input_checkbox_group(
            "who",
            "Which Person",
            ["Jesse", "Bridget"],
            selected=["Jesse"],
            inline=True,
        )

        ui.input_checkbox_group(
            "where",
            "Country",
            choices=sorted(df_full["country"].dropna().unique().tolist()),
            selected=sorted(df_full["country"].dropna().unique().tolist()),
            inline=True,
        )

        ui.input_radio_buttons(
            "avg_type",
            "Average Type",
            choices={"mean": "Mean", "median": "Median"},
            selected="mean",
        )

        ui.input_action_button("reset", "Reset filter")

        ui.input_action_button("refresh_data", "Refresh data - BRIDGET DON'T TOUCH PLEASE X")

    with ui.navset_bar(title = '', id="main_tabs"):
        with ui.nav_menu("Tabs"):

            # ================================================================================================================================
            # Today Tab
            # ================================================================================================================================
            with ui.nav_panel("Today"):
                with ui.layout_columns(fill=False):
                    with ui.value_box(showcase=ui.img(src="flight_socks.jpeg", style="width: 100px; height: 100px; object-fit: cover; border-radius: 8px; margin-top: 10px;", showcase_layout="left center")):
                        "Total"
                        @render.express
                        def today_cost():
                            today_expenses = today_df()
                            price_col = input.today_currency()
                            cost = today_expenses[price_col].sum()
                            f"${cost:,.2f}"

                    with ui.value_box(showcase=ui.img(src="chomp.jpeg", style="width: 100px; height: 100px; object-fit: cover; border-radius: 8px; margin-top: 10px;", showcase_layout="left center")):
                        "Food"
                        @render.express
                        def food_today():
                            today_expenses = today_df()
                            price_col = input.today_currency()

                            today_food = (
                                today_expenses.loc[
                                    today_expenses["Category"] == "Food",
                                    price_col
                                ].sum()
                            )
                            f"${today_food:,.2f}"

                    with ui.value_box(showcase=ui.img(src="nap.jpeg", style="width: 100px; height: 100px; object-fit: cover; border-radius: 8px; margin-top: 10px;", showcase_layout="left center")):
                        "Accom"
                        @render.express
                        def accom_today():
                            today_expenses = today_df()
                            price_col = input.today_currency()

                            today_accom = (
                                today_expenses.loc[
                                    today_expenses["Category"] == "Accom",
                                    price_col
                                ].sum()
                            )
                            f"${today_accom:,.2f}"

                    with ui.value_box(showcase=ui.img(src="walk.jpeg", style="width: 100px; height: 100px; object-fit: cover; border-radius: 8px; margin-top: 10px;", showcase_layout="left center")):
                        "Transport"
                        @render.express
                        def transport_today():
                            today_expenses = today_df()
                            price_col = input.today_currency()

                            today_transport = (
                                today_expenses.loc[
                                    today_expenses["Category"] == "Transport",
                                    price_col
                                ].sum()
                            )
                            f"${today_transport:,.2f}"

                    with ui.value_box(showcase=ui.img(src="woof.jpeg", style="width: 100px; height: 100px; object-fit: cover; border-radius: 8px; margin-top: 10px;", showcase_layout="left center")):
                        "Misc"
                        @render.express
                        def misc_today():
                            today_expenses = today_df()
                            price_col = input.today_currency()

                            today_misc = (
                                today_expenses.loc[
                                    today_expenses["Category"] == "Misc",
                                    price_col
                                ].sum()
                            )

                            f"${today_misc:,.2f}"

                    
                    ui.input_date(
                        "today_date",
                        "Select day",
                        value=date.today(),
                        min=min_date,
                        max=max_date,
                    )

                    ui.input_radio_buttons(
                        "today_currency",
                        "",
                        choices={"Price NZD": "NZD", "Price": "Local Currency"},
                        selected="Price NZD"
                    )

                    @render.data_frame
                    def today_table():
                        df = today_df()

                        columns_to_show = [
                            "Category",
                            "Price NZD",
                            "Extra Note",
                            "Price",
                            "Currency",
                            "Person"
                        ]
                        df["Price NZD"] = df["Price NZD"].round(2)
                        df["Price"] = df["Price"].round(2)

                        return df[columns_to_show]

            # ================================================================================================================================
            # Summary Stats Tab
            # ================================================================================================================================

            with ui.nav_panel("Summary Stats"):
                with ui.layout_columns(fill=False):
                    with ui.value_box(showcase=ui.img(src="7_11_bby.JPG", style="width: 100px; height: 100px; object-fit: cover; border-radius: 8px; margin-top: 10px;", showcase_layout="left center")):
                        "Daily Spend"
                        @render.express
                        def daily_spend():
                            df = filtered_df()
                            daily_total = df[df['Category'] != "Flights"].groupby("Expense Date")["Price NZD"].sum()
                            value = avg_calc(daily_total)
                            f"${value:,.2f}"

                    with ui.value_box(showcase=ui.img(src="chomp.jpeg", style="width: 100px; height: 100px; object-fit: cover; border-radius: 8px; margin-top: 10px;", showcase_layout="left center")):
                        "Daily Food"
                        @render.express
                        def daily_food():
                            df = filtered_df()
                            daily_food = df[df['Category'] == 'Food'].groupby("Expense Date")["Price NZD"].sum()
                            value = avg_calc(daily_food)
                            f"${value:,.2f}"

                    with ui.value_box(showcase=ui.img(src="nap.jpeg", style="width: 100px; height: 100px; object-fit: cover; border-radius: 8px; margin-top: 10px;", showcase_layout="left center")):
                        "Accom"
                        @render.express
                        def accom_av():
                            df = filtered_df()
                            accom = df[df['Category'] == 'Accom'].groupby("Expense Date")["Price NZD"].sum()
                            value = avg_calc(accom)
                            f"${value:,.2f}"

                    with ui.value_box(showcase=ui.img(src="flight_socks.jpeg", style="width: 100px; height: 100px; object-fit: cover; border-radius: 8px; margin-top: 10px;", showcase_layout="left center")):
                        "Total"
                        @render.express
                        def flight_cost():
                            df = filtered_df()
                            cost = df["Price NZD"].sum()
                            f"${cost:,.2f}"

            # ================================================================================================================================
            # Explore Tab
            # ================================================================================================================================

            with ui.nav_panel("Explore"):
                with ui.navset_pill(id="viz_tabs"):
                    with ui.nav_panel("Line"):
                        with ui.card():
                            @render_plotly
                            def line_plot():
                                plot_df = line_plot_df()

                                fig = px.line(
                                    plot_df,
                                    x="Date",
                                    y="Price NZD",
                                    color="Category",
                                    markers=True,
                                    title="Daily Spend by Category",
                                    hover_data=["Price NZD", "Category"],
                                    template="seaborn",
                                    color_discrete_map={
                                        "Food": "#2ca02c",
                                        "Accommodation": "#1f77b4",
                                        "Misc": "#ff7f0e",
                                        "Flights": "#9467bd",
                                        "Transport": "#a21414",
                                        "Total": "#000000",
                                        "Rolling Average": "#444444",
                                    },
                                )

                                fig.update_xaxes(type="date", tickformat="%d %b")

                                fig.update_layout(
                                    xaxis_title="Date",
                                    yaxis_title="Spend NZD",
                                    hovermode="x unified",
                                    legend=dict(
                                        orientation="h",
                                        yanchor="top",
                                        y=-0.2,
                                        xanchor="center",
                                        x=0.5
                                    )
                                )

                                fig.update_traces(
                                    hovertemplate=(
                                        "<b>%{fullData.name}</b><br>"
                                        "Spend: $%{y:.2f}<extra></extra>"
                                    )
                                )

                                return fig

                            ui.input_checkbox_group(
                                "line_cats",
                                "Categories",
                                choices=[],
                                selected=[],
                                inline=True,
                            )

                    with ui.nav_panel("Box Plot"):
                        with ui.card():
                            @render_plotly
                            def box_plot():
                                df = box_plot_df()

                                fig = px.box(
                                    df,
                                    x="Category",
                                    y="plot_data",
                                    labels={"plot_data": "Price (NZD)"},
                                    template="seaborn",
                                    color="Category",
                                    color_discrete_map={
                                        "Food": "#2ca02c",
                                        "Accommodation": "#1f77b4",
                                        "Misc": "#ff7f0e",
                                        "Flights": "#9467bd",
                                        "Transport": "#a21414",
                                    },
                                )

                                if input.box_daily() == "daily":
                                    fig.update_traces(
                                        customdata=df[["Expense Date", "Price NZD"]],
                                        hovertemplate=(
                                            "<b>%{x}</b><br>"
                                            "Date: %{customdata[0]|%d %b %Y}<br>"
                                            "Daily Cost: $%{customdata[1]:,.2f}"
                                            "<extra></extra>"
                                        )
                                    )
                                else:
                                    fig.update_traces(
                                        customdata=df[["Price NZD", "Extra Note"]],
                                        hovertemplate=(
                                            "<b>%{x}</b><br>"
                                            "Price: $%{customdata[0]:,.2f}<br>"
                                            "Note: %{customdata[1]}"
                                            "<extra></extra>"
                                        )
                                    )

                                fig.update_layout(
                                    yaxis_title="Price (NZD)",
                                    legend=dict(
                                        orientation="h",
                                        yanchor="top",
                                        y=-0.2,
                                        xanchor="center",
                                        x=0.5
                                    )
                                )
                                return fig

                            ui.input_checkbox(
                                "scale_box",
                                "Scale Data",
                                value=False
                            )

                            ui.input_radio_buttons(
                                "box_daily",
                                "",
                                choices={"daily": "Daily Spend", "total": "Total Spend"},
                                selected="total"
                            )

                            ui.input_checkbox_group(
                                "box_cats",
                                "Categories",
                                choices=[],
                                selected=[],
                                inline=True,
                            )

                    with ui.nav_panel("Pie Chart"):
                        with ui.card():
                            @render_plotly
                            def bar():
                                df = bar_data()

                                fig = px.pie(
                                    df,
                                    names="Category",
                                    values="Price NZD",
                                    title="Spending Proportion",
                                    template="seaborn",
                                    color="Category",
                                    color_discrete_map={
                                        "Food": "#2ca02c",
                                        "Accommodation": "#1f77b4",
                                        "Misc": "#ff7f0e",
                                        "Flights": "#9467bd",
                                        "Transport": "#a21414",
                                    }
                                )

                                fig.update_layout(
                                    legend=dict(
                                        orientation="h",
                                        yanchor="top",
                                        y=-0.2,
                                        xanchor="center",
                                        x=0.5
                                    )
                                )

                                return fig

                            ui.input_radio_buttons(
                                "bar_daily",
                                "",
                                choices={"daily": "Daily Spend", "total": "Total Spend"},
                                selected="total"
                            )

# ================================================================================================================================
# Our Journey tab
# ================================================================================================================================

            with ui.nav_panel("Our Journey"):
                @render_plotly
                def journey_map():
                    map_df = journey_map_df()

                    if map_df.empty:
                        fig = go.Figure()
                        fig.add_annotation(
                            text="No location data available for the current filters.",
                            showarrow=False,
                            x=0.5, y=0.5,
                            xref="paper", yref="paper"
                        )
                        fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
                        return fig

                    lat = map_df["latitude"].astype(float)
                    lon = map_df["longitude"].astype(float)

                    exclude_cols = {"Expense Date", "Date", "latitude", "longitude", "town"}
                    category_cols = [c for c in map_df.columns if c not in exclude_cols]

                    # Replace NaN values so JSON serialization succeeds
                    map_df["town"] = map_df["town"].fillna("").astype(str)
                    map_df["Date"] = map_df["Date"].fillna("").astype(str)
                    map_df[category_cols] = map_df[category_cols].fillna(0)

                    # Build hover text so each location shows all its dates with the daily total spend
                    hover_lookup = {}
                    group_cols = ["latitude", "longitude", "town"]

                    for (lat_val, lon_val, town_val), group in map_df.groupby(group_cols, sort=False):
                        lines = [f"<b>{town_val}</b>"]
                        group = group.sort_values("Expense Date")

                        for _, row in group.iterrows():
                            total_spend = float(row.get("Total", 0) or 0)
                            lines.append(f"{row['Date']} — ${total_spend:,.2f}")

                        hover_lookup[(lat_val, lon_val, town_val)] = "<br>".join(lines) + "<extra></extra>"

                    hover_text = map_df.apply(
                        lambda row: hover_lookup[(row["latitude"], row["longitude"], row["town"])],
                        axis=1,
                    )

                    fig = go.Figure(
                        go.Scattermap(
                            lat=lat,
                            lon=lon,
                            mode="markers+lines",
                            text=hover_text,
                            hovertemplate="%{text}",
                            # customdata=customdata,
                            # hovertemplate=hovertemplate,
                            hoverlabel=dict(namelength=-1),
                        )
                    )

                    padding = 0.2
                    center = {"lat": float(lat.mean()), "lon": float(lon.mean())}

                    lat_range = (lat.max() - lat.min()) + padding * 2
                    lon_range = (lon.max() - lon.min()) + padding * 2
                    max_range = max(lat_range, lon_range)

                    zoom = 8 - np.log(max_range + 1e-6)
                    zoom = max(min(zoom, 15), 3)

                    fig.update_layout(
                        map=dict(
                            center=center,
                            zoom=zoom,
                            style="open-street-map",
                        ),
                        margin={"r": 0, "t": 0, "l": 0, "b": 0},
                        height=650,
                    )

                    return fig              
                
            #Map dataframe for manually checking results
            # @render.data_frame
            # def journey_table():
            #     return journey_map_df()
        
# ================================================================================================================================
# Dataframe tab
# ================================================================================================================================
            with ui.nav_panel("Dataframe"):
                @render.data_frame
                def dataframe_table():
                    df = filtered_df()

                    columns_to_show = [
                        "Expense Date",
                        "Person",
                        "Category",
                        "Price NZD",
                        "Extra Note",
                        "country"
                    ]
                    return render.DataGrid(df[columns_to_show])
        
# ================================================================================================================================
# Jesse Owe Bridget Tab
# ================================================================================================================================
        
            with ui.nav_panel("Transfers"):
                with ui.value_box():
                    "Jesse Owes"
                    @render.express
                    def jesse_owes():
                        df = filtered_df()
                        jesse_spend = df[df['Person'] == 'Jesse']["Price NZD"].sum()
                        jesse_transfer = transfer_df["Price"].sum()
                        jesse_owe = jesse_spend -jesse_transfer
                        colour = "red" if jesse_owe > 0 else "green"

                        ui.HTML(
                            f"<span style='color:{colour}; font-weight:bold;'>"
                            f"${jesse_owe:,.2f}"
                            f"</span>"
                        )

                @render.data_frame
                def transfer_table():
                    return render.DataGrid(transfer_df)

# ================================================================================================================================
# Budget Forecast Tab
# ================================================================================================================================


            with ui.nav_panel("Forecast"):
                #Helper function for building the forecast table
                def build_forecast_table():
                            """Return a daily dataframe for the forecast window with budget, observed actuals,
                            linear-forecasted actuals, and cumulative series (actuals offset by pre-window total).
                            """
                            df = df_data().copy()
                            df = df[df["Person"] == "Bridget"]
                            df = df[df["Expense Date"] >= pd.to_datetime("2026-08-13")]
                            df = df[df["Expense Date"] <= pd.to_datetime("2026-11-02")]
                            df = df[df["Category"] != "Flights"]
                            df = df.groupby("Expense Date", as_index=False)["Price NZD"].sum()
                
                            daily_total = pd.DataFrame()
                            daily_total['Date'] = pd.date_range(start='2026-08-13', end='2026-11-02')
                
                            # Budget per day: 60 until and including 2026-10-19, then 80 afterwards
                            daily_total["Budget Spend"] = np.where(
                                daily_total["Date"] > pd.to_datetime("2026-10-19"), 80, 60
                            )
                            daily_total = daily_total.merge(df, left_on="Date", right_on="Expense Date", how="left").drop(columns=["Expense Date"])
                            daily_total.rename(columns={"Price NZD": "Actual Spend"}, inplace=True)
                
                            return daily_total
                with ui.navset_pill(id="forecast_tabs"):
                    with ui.nav_panel("Daily"): 
                        with ui.card():
                            @render_plotly
                            def daily_forecast_plot():
                                #Actual spending dataframe
                                daily_total = build_forecast_table().copy()
                                daily_total["Actual Spend"] = daily_total["Actual Spend"].fillna(0)

                                plot_df = pd.melt(
                                    daily_total,
                                    id_vars="Date",
                                    value_vars=["Budget Spend", "Actual Spend"],
                                    var_name="Spend Type",
                                    value_name="Amount"
                                )

                                fig = px.line(
                                    plot_df,
                                    x="Date",
                                    y="Amount",
                                    color="Spend Type",
                                    title="Budget vs Actual",
                                    template="seaborn",
                                    markers=True,
                                )

                                # fig.update_traces(mode="lines+markers")
                                fig.update_layout(
                                    xaxis_title="Date",
                                    yaxis_title="Spend (NZD)",
                                )

                                # fig.update_xaxes(type="date", tickformat="%d %b")
                                # fig.update_layout(
                                #     xaxis_title="Date",
                                #     yaxis_title="Cumulative Spend (NZD)",
                                #     hovermode="x unified"
                                # )
                                # fig.update_traces(
                                #     hovertemplate="<b>%{x|%d %b %Y}</b><br>Cumulative Spend: $%{y:,.2f}<extra></extra>"
                                # )

                                return fig

                    with ui.nav_panel("Cumulative Spend"):
                        with ui.card():
                            @render_plotly
                            def cumulative_forecast_plot():
                                # Actual spending dataframe
                                daily_total = build_forecast_table().copy()
                                observed_mask = daily_total["Actual Spend"].notna()
                                daily_total["Actual Spend"] = daily_total["Actual Spend"].fillna(0)

                                observed = daily_total.loc[observed_mask].copy()
                                daily_total["Forecast Actual"] = daily_total["Actual Spend"].copy()

                                if len(observed) >= 2:
                                    x_obs = observed["Date"].map(pd.Timestamp.toordinal).values
                                    y_obs = observed["Actual Spend"].values
                                    coeffs = np.polyfit(x_obs, y_obs, 1)

                                    missing_mask = ~observed_mask
                                    if missing_mask.any():
                                        x_missing = daily_total.loc[missing_mask, "Date"].map(pd.Timestamp.toordinal).values
                                        preds = np.polyval(coeffs, x_missing)
                                        daily_total.loc[missing_mask, "Forecast Actual"] = np.where(preds < 0, 0, preds)
                                elif len(observed) == 1:
                                    flat = observed["Actual Spend"].iloc[0]
                                    daily_total.loc[~observed_mask, "Forecast Actual"] = flat
                                else:
                                    daily_total["Forecast Actual"] = np.zeros(len(daily_total))

                                # Cumulative series
                                daily_total["Cumulative Budget"] = daily_total["Budget Spend"].cumsum()
                                daily_total["Cumulative Actual"] = daily_total["Forecast Actual"].cumsum()

                                # Final totals to display as annotations
                                final_budget = daily_total["Cumulative Budget"].iloc[-1]
                                final_actual = daily_total["Cumulative Actual"].iloc[-1]
                                delta = final_actual - final_budget

                                plot_df = pd.melt(
                                    daily_total,
                                    id_vars="Date",
                                    value_vars=["Cumulative Budget", "Cumulative Actual"],
                                    var_name="Spend Type",
                                    value_name="Amount",
                                )

                                fig = px.line(
                                    plot_df,
                                    x="Date",
                                    y="Amount",
                                    color="Spend Type",
                                    title="Cumulative Budget vs Actual (forecast)",
                                    template="seaborn",
                                )

                                fig.update_xaxes(type="date", tickformat="%d %b")
                                fig.update_layout(
                                    xaxis_title="Date",
                                    yaxis_title="Cumulative Spend (NZD)",
                                    hovermode="x unified",
                                    legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
                                )

                                fig.update_traces(
                                    hovertemplate=("<b>%{fullData.name}</b><br>" "Date: %{x|%d %b %Y}<br>" "Cumulative: $%{y:,.2f}<extra></extra>")
                                )

                                # Add annotations for the final cumulative values
                                last_date = daily_total["Date"].iloc[-1]

                                fig.add_annotation(
                                    x=last_date,
                                    y=final_budget,
                                    text=f"Budget: ${final_budget:,.2f}",
                                    showarrow=False,
                                    # arrowhead=1,
                                    ax=-60,
                                    ay=-30,
                                    bgcolor="rgba(255,255,255,0.8)",
                                )

                                fig.add_annotation(
                                    x=last_date,
                                    y=final_actual,
                                    text=f"Actual (forecast): ${final_actual:,.2f}",
                                    showarrow=False,
                                    # arrowhead=1,
                                    ax=-60,
                                    ay=30,
                                    bgcolor="rgba(255,255,255,0.8)",
                                )

                                # Add delta annotation
                                fig.add_annotation(
                                    x=last_date,
                                    y=max(final_budget, final_actual),
                                    text=(f"Δ ${delta:,.2f}" if delta >= 0 else f"Δ -${abs(delta):,.2f}"),
                                    showarrow=False,
                                    yshift=60,
                                    bgcolor="rgba(255,255,255,0.8)",
                                )

                                return fig

                        # @render.data_frame
                        # def cum_table():
                        #     df = build_forecast_table()
    
                        #     return render.DataGrid(df)
# ================================================================================================================================
# Reactive calcs and functions
# ================================================================================================================================
@reactive.calc
def filtered_df_date():
    df = filtered_df_person().copy()

    # selected_people = input.who()
    # if selected_people:
    #     df = df[df["Person"].isin(selected_people)]

    selected_range = input.date_range()
    if selected_range:
        start_date, end_date = selected_range

        df = df[
            (df["Expense Date"].dt.date >= start_date)
            & (df["Expense Date"].dt.date <= end_date)
        ]

    df["Expense Date"] = pd.to_datetime(df["Expense Date"])

    return df

@reactive.calc
def filtered_df_person():
    df = df_full.copy()

    selected_people = input.who()
    if selected_people:
        df = df[df["Person"].isin(selected_people)]

    return df

@reactive.calc
def filtered_df():
    df = filtered_df_date().copy()

    selected_cunts = input.where()
    if selected_cunts:
        df = df[df["country"].isin(selected_cunts)]

    return df

@reactive.calc
def country_choices():
    df = filtered_df_date().copy()
    return sorted(df["country"].dropna().unique().tolist())

@reactive.effect
def _():
    ui.update_checkbox_group(
        "where",
        choices=country_choices(),
        selected=country_choices()
    )

@reactive.calc
def line_plot_df():
    df = filtered_df()
    df = df[df["Category"] != "Flights"].copy()

    df["Expense Date"] = pd.to_datetime(df["Expense Date"]).dt.normalize()


    start_date = df["Expense Date"].min()
    end_date = df["Expense Date"].max()
    all_dates = pd.date_range(start=start_date, end=end_date, freq="D")

    all_categories = df["Category"].dropna().unique()

    full_index = pd.MultiIndex.from_product(
        [all_dates, all_categories],
        names=["Expense Date", "Category"]
    )

    daily_category = (
        df.groupby(["Expense Date", "Category"])["Price NZD"]
        .sum()
        .reindex(full_index, fill_value=0)
        .reset_index()
    )

    daily_total = (
                    daily_category.groupby("Expense Date", as_index=False)["Price NZD"]
                    .sum()
                )
    daily_total["Category"] = "Total"

    # --- rolling average ---
    rolling_total = daily_total.copy()
    rolling_total["Price NZD"] = (
        rolling_total["Price NZD"]
        .rolling(3, min_periods=1)
        .mean()
    )
    rolling_total["Category"] = "Rolling Average"

    # --- combine everything ---
    plot_df = pd.concat(
        [daily_category, daily_total, rolling_total],
        ignore_index=True
    )


    plot_df["Date"] = plot_df["Expense Date"].dt.strftime("%Y-%m-%d")

    selected_cats = input.line_cats()
    plot_df = plot_df[plot_df["Category"].isin(selected_cats)]

    return plot_df


def avg_calc(data):
    selected = input.avg_type()
    if selected == "mean":
        value = data.mean()
    else:
        value = data.median()

    return value

@reactive.effect
@reactive.event(input.reset)
def reset_filters():
    ui.update_date_range("date_range", start=min_date, end=max_date)
    ui.update_date("today_date", value=date.today())
    ui.update_checkbox_group("who", selected=["Jesse"])
    ui.update_radio_buttons("avg_type", selected = "mean")
    ui.update_checkbox_group("where", selected=country_choices())

@reactive.calc
def category_choices():
    df = filtered_df()
    cats = sorted(df["Category"].dropna().unique().tolist())   

    return cats

@reactive.effect
def _():

    cats = category_choices()
    cats = [c for c in cats if c != "Flights"]
    line_cats = cats + ["Rolling Average", "Total"]

    ui.update_checkbox_group(
        "line_cats",
        choices=line_cats,
        selected=cats + ['Total']
    )
@reactive.effect
def _():
    ui.update_checkbox_group(
        "box_cats",
        choices=category_choices(),
        selected=category_choices()
    )

@reactive.calc
def box_plot_df():
    plot_df = filtered_df()
    selected_cats = input.box_cats()
    plot_df = plot_df[plot_df["Category"].isin(selected_cats)]
    

    if input.box_daily() == "daily":  # daily aggregation first
        plot_df = (
            plot_df.groupby(["Expense Date", "Category"], as_index=False)["Price NZD"]
            .sum()
        )


    plot_df["plot_data"] = plot_df["Price NZD"]

    if input.scale_box():
        def zscore(group):
            std = group.std()
            if std != 0:
                return (group - group.mean()) / std
            else:
                return 0

        plot_df["plot_data"] = (
            plot_df.groupby("Category")["plot_data"]
            .transform(zscore)
        )


    return plot_df
@reactive.calc
def bar_data():
    df = filtered_df()

    if input.bar_daily() == "daily":  # daily aggregation first
            df = (
            df.groupby(["Expense Date", "Category"], as_index=False)["Price NZD"]
            .sum()
        )

            df = (
                df.groupby("Category", as_index=False)["Price NZD"]
                .mean()
            )

            df = df[df['Category'] != 'Flights'] #removing flight as it is not relevant to daily spending

    return df

@reactive.calc
def journey_map_df():
    df = filtered_df().copy()
    df = df[df["Category"] != "Flights"].copy()
    df["Expense Date"] = pd.to_datetime(df["Expense Date"]).dt.normalize()

    daily_category = (
        df.groupby(["Expense Date", "Category"])["Price NZD"]
        .sum()
        .reset_index()
    )

    daily_total = (
        daily_category.groupby("Expense Date", as_index=False)["Price NZD"]
        .sum()
    )
    daily_total["Category"] = "Total"

    map_df = pd.concat([daily_category, daily_total], ignore_index=True)

    map_df = map_df.pivot(
        index="Expense Date",
        columns="Category",
        values="Price NZD"
    ).reset_index()

    geo_df = df_locations.rename(columns={"Date": "Expense Date"})[
    ["Expense Date", "latitude", "longitude", "town"]
]

    geo_df["Expense Date"] = pd.to_datetime(geo_df["Expense Date"]).dt.normalize()

    geo_df = (
        geo_df.groupby("Expense Date", as_index=False)
        .agg(
            latitude=("latitude", "first"),
            longitude=("longitude", "first"),
            town=("town", lambda s: "<br>".join(s.dropna().astype(str)))
        )
    )

    map_df = pd.merge(map_df, geo_df, on="Expense Date", how="inner")
    map_df["Date"] = pd.to_datetime(map_df["Expense Date"]).dt.strftime("%a %d %b")

    return map_df.sort_values("Expense Date")


@reactive.calc
def today_df():
    df = filtered_df_person().copy()

    selected_day = input.today_date()
    if selected_day is None:
        selected_day = date.today()

    df = df[df["Category"] != "Flights"].copy()

    today_expenses = df[
        df["Expense Date"].dt.date == selected_day
    ]

    

    return today_expenses

@reactive.effect
@reactive.event(input.refresh_data)
def _():
    rebuild_data()

    ui.update_date_range(
        "date_range",
        start=min_date,
        end=max_date,
        min=min_date,
        max=max_date,
    )

    ui.update_checkbox_group(
        "where",
        choices=sorted(df_full["country"].dropna().unique().tolist()),
        selected=sorted(df_full["country"].dropna().unique().tolist()),
    )