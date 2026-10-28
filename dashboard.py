
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from alpha_vantage.fundamentaldata import FundamentalData
from stocknews import StockNews


# --------------------------------------------------
# Page setup
# --------------------------------------------------
st.set_page_config(
    page_title="📈 Financial Stock Dashboard Analysis",
    layout="wide"
)

st.title("📈 Financial Stock Dashboard Analysis")

st.markdown(
    """
    Explore stock performance, volatility, trading activity,
    financial statements, and market news.

    **Analyze thousands of publicly traded companies and other
    supported tickers available through Yahoo Finance.** Enter a
    ticker such as `AAPL` for Apple, `GOOGL` for Alphabet,
    `MSFT` for Microsoft, or `NVDA` for NVIDIA to explore its data.

    *Not sure which ticker to use? Start by entering a company symbol
    in the sidebar.*
    """
)


# --------------------------------------------------
# Sidebar filters
# --------------------------------------------------
st.sidebar.header("Dashboard Filters")

ticker_input = st.sidebar.text_input(
    "Search a company by ticker",
    value="",
    placeholder="Enter ticker symbol...",
    help="Examples: MSFT, AAPL, GOOGL, NVDA, AMZN",
    key="ticker_input"
).strip().upper()

today = pd.Timestamp.today().date()

start_date = st.sidebar.date_input(
    "Start date",
    value=today - pd.Timedelta(days=365),
    key="start_date"
)

end_date = st.sidebar.date_input(
    "End date",
    value=today,
    key="end_date"
)

submitted = st.sidebar.button(
    "Analyze Stock",
    use_container_width=True,
    type="primary"
)


# --------------------------------------------------
# Ticker submission and landing page
# --------------------------------------------------
if "active_ticker" not in st.session_state:
    st.session_state.active_ticker = ""

if submitted:
    if not ticker_input:
        st.sidebar.warning("Please enter a stock ticker.")
    elif start_date >= end_date:
        st.sidebar.warning(
            "Start date must be earlier than end date."
        )
    else:
        st.session_state.active_ticker = ticker_input

ticker = st.session_state.active_ticker

# Do not download data before a ticker is submitted.
if not ticker:
    st.info(
        "👈 Enter a stock ticker in the sidebar and click "
        "**Analyze Stock** to explore that company's dashboard."
    )
    st.stop()

# Validate the date range.
if start_date >= end_date:
    st.warning(
        "Choose a valid date range. The start date must be "
        "earlier than the end date."
    )
    st.stop()


# --------------------------------------------------
# Data loading
# --------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(symbol, start, end):
    result = yf.download(
        symbol,
        start=start,
        end=end + pd.Timedelta(days=1),
        auto_adjust=False,
        progress=False
    )

    if isinstance(result.columns, pd.MultiIndex):
        result.columns = result.columns.get_level_values(0)

    return result.loc[:, ~result.columns.duplicated()]


try:
    with st.spinner(f"Loading market data for {ticker}..."):
        data = get_stock_data(ticker, start_date, end_date)

    if data.empty:
        st.error(
            f"No price data found for {ticker}. "
            "Check the ticker symbol and date range."
        )
        st.stop()

except Exception as exc:
    st.error(
        "Unable to retrieve stock prices. "
        "Please check the ticker and try again."
    )
    print(
        f"Price data error for {ticker}: "
        f"{type(exc).__name__}: {exc}"
    )
    st.stop()


# --------------------------------------------------
# Prepare price data and metrics
# --------------------------------------------------
price_col = (
    "Adj Close" if "Adj Close" in data.columns else "Close"
)

if price_col not in data.columns:
    st.error(
        "The data provider did not return a closing-price column."
    )
    st.stop()

prices = pd.to_numeric(
    data[price_col],
    errors="coerce"
).dropna()

if prices.empty:
    st.error("No valid closing prices are available.")
    st.stop()

daily_returns = prices.pct_change().dropna()
latest_price = float(prices.iloc[-1])

previous_close = (
    float(prices.iloc[-2])
    if len(prices) >= 2
    else np.nan
)

daily_change = (
    latest_price - previous_close
    if pd.notna(previous_close)
    else np.nan
)

daily_change_pct = (
    daily_change / previous_close * 100
    if pd.notna(previous_close) and previous_close != 0
    else np.nan
)

period_return = (
    (prices.iloc[-1] / prices.iloc[0] - 1) * 100
    if len(prices) >= 2 and prices.iloc[0] != 0
    else np.nan
)

annualized_volatility = (
    daily_returns.std(ddof=1) * np.sqrt(252) * 100
    if len(daily_returns) >= 2
    else np.nan
)

chart_data = data.copy()

chart_data["Closing Price"] = pd.to_numeric(
    chart_data[price_col],
    errors="coerce"
)

chart_data["Daily Return (%)"] = (
    chart_data["Closing Price"].pct_change() * 100
)

chart_data["20-Day Moving Average"] = (
    chart_data["Closing Price"].rolling(20).mean()
)

chart_data["50-Day Moving Average"] = (
    chart_data["Closing Price"].rolling(50).mean()
)


# --------------------------------------------------
# KPI cards
# --------------------------------------------------
st.subheader(f"{ticker} Market Overview")

k1, k2, k3, k4 = st.columns(4)

k1.metric(
    "Latest Available Price",
    f"${latest_price:,.2f}",
    help="Last available price in the selected date range."
)

k2.metric(
    "Daily Change",
    f"{daily_change_pct:+.2f}%"
    if pd.notna(daily_change_pct)
    else "N/A",
    delta=(
        f"${daily_change:+.2f}"
        if pd.notna(daily_change)
        else None
    )
)

k3.metric(
    "Period Return",
    f"{period_return:+.2f}%"
    if pd.notna(period_return)
    else "N/A"
)

k4.metric(
    "Annualized Volatility",
    f"{annualized_volatility:.2f}%"
    if pd.notna(annualized_volatility)
    else "N/A"
)

st.caption(
    "Period return compares the first and last available closing "
    "prices. Annualized volatility is calculated from daily returns; "
    "it is not a forecast."
)


# --------------------------------------------------
# Price performance chart
# --------------------------------------------------
st.subheader("📊 Price Performance")

control1, control2 = st.columns(2)

with control1:
    chart_type = st.selectbox(
        "Chart type",
        ["Line", "Candlestick"]
    )

with control2:
    show_moving_averages = st.checkbox(
        "Show 20-day and 50-day moving averages",
        value=True
    )

fig = go.Figure()

if chart_type == "Line":
    fig.add_trace(
        go.Scatter(
            x=chart_data.index,
            y=chart_data["Closing Price"],
            mode="lines",
            name="Closing Price",
            line=dict(width=2)
        )
    )

    if show_moving_averages:
        fig.add_trace(
            go.Scatter(
                x=chart_data.index,
                y=chart_data["20-Day Moving Average"],
                mode="lines",
                name="20-day average",
                line=dict(dash="dot")
            )
        )

        fig.add_trace(
            go.Scatter(
                x=chart_data.index,
                y=chart_data["50-Day Moving Average"],
                mode="lines",
                name="50-day average",
                line=dict(dash="dash")
            )
        )

elif chart_type == "Candlestick":
    required = {"Open", "High", "Low", "Close"}

    if required.issubset(chart_data.columns):
        fig.add_trace(
            go.Candlestick(
                x=chart_data.index,
                open=chart_data["Open"],
                high=chart_data["High"],
                low=chart_data["Low"],
                close=chart_data["Close"],
                name=ticker
            )
        )
    else:
        st.warning(
            "Candlestick data is unavailable for this ticker."
        )

fig.update_layout(
    template="plotly_dark",
    height=480,
    xaxis_title="Date",
    yaxis_title="Price (USD)",
    hovermode="x unified",
    margin=dict(l=20, r=20, t=30, b=20),
    legend=dict(orientation="h", y=1.08)
)

st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------
# Trading volume and daily returns
# --------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Trading Volume")

    if "Volume" in chart_data.columns:
        volume_fig = go.Figure(
            go.Bar(
                x=chart_data.index,
                y=chart_data["Volume"],
                name="Volume"
            )
        )

        volume_fig.update_layout(
            template="plotly_dark",
            height=320,
            xaxis_title="Date",
            yaxis_title="Shares traded",
            margin=dict(l=15, r=15, t=20, b=15)
        )

        st.plotly_chart(
            volume_fig,
            use_container_width=True
        )
    else:
        st.info("Volume data is unavailable.")

with right:
    st.subheader("Daily Returns")

    returns_data = chart_data.dropna(
        subset=["Daily Return (%)"]
    )

    if not returns_data.empty:
        returns_fig = go.Figure(
            go.Bar(
                x=returns_data.index,
                y=returns_data["Daily Return (%)"],
                name="Daily return"
            )
        )

        returns_fig.add_hline(
            y=0,
            line_dash="dash"
        )

        returns_fig.update_layout(
            template="plotly_dark",
            height=320,
            xaxis_title="Date",
            yaxis_title="Return (%)",
            margin=dict(l=15, r=15, t=20, b=15)
        )

        st.plotly_chart(
            returns_fig,
            use_container_width=True
        )
    else:
        st.info(
            "Not enough observations to calculate daily returns."
        )


# --------------------------------------------------
# Tabs
# --------------------------------------------------
pricing_tab, fundamental_tab, news_tab = st.tabs(
    [
        "💹 Pricing Data",
        "📊 Fundamental Data",
        "📰 Market News"
    ]
)


# --------------------------------------------------
# Historical pricing data
# --------------------------------------------------
with pricing_tab:
    st.subheader(f"{ticker} Historical Data")

    display_data = chart_data.sort_index(ascending=False)

    st.dataframe(
        display_data,
        use_container_width=True
    )

    st.download_button(
        "Download Historical Data (CSV)",
        data=display_data.to_csv().encode("utf-8"),
        file_name=f"{ticker}_historical_data.csv",
        mime="text/csv"
    )


# --------------------------------------------------
# Fundamental data
# --------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def get_fundamental_data(symbol, method, api_key):
    fd = FundamentalData(
        key=api_key,
        output_format="pandas"
    )

    response = getattr(fd, method)(symbol)

    if not response or response[0] is None:
        return pd.DataFrame()

    statement = response[0]

    if not isinstance(statement, pd.DataFrame):
        return pd.DataFrame()

    statement = statement.copy()

    if "fiscalDateEnding" in statement.columns:
        statement["fiscalDateEnding"] = pd.to_datetime(
            statement["fiscalDateEnding"],
            errors="coerce"
        ).dt.strftime("%Y-%m-%d")

        statement = statement.set_index("fiscalDateEnding")

    return statement


with fundamental_tab:
    try:
        api_key = st.secrets["ALPHA_VANTAGE_API_KEY"]

        statements = [
            (
                "get_balance_sheet_annual",
                "Balance Sheet"
            ),
            (
                "get_income_statement_annual",
                "Income Statement"
            ),
            (
                "get_cash_flow_annual",
                "Cash Flow Statement"
            )
        ]

        for method, title in statements:
            st.subheader(title)

            try:
                with st.spinner(
                    f"Loading {title.lower()}..."
                ):
                    statement = get_fundamental_data(
                        ticker,
                        method,
                        api_key
                    )

                if statement.empty:
                    st.info(
                        f"{title} is unavailable for {ticker}."
                    )
                else:
                    st.dataframe(
                        statement,
                        use_container_width=True
                    )

            except Exception as exc:
                print(
                    f"{title} error for {ticker}: "
                    f"{type(exc).__name__}: {exc}"
                )

                st.warning(
                    f"{title} could not be loaded. "
                    "Check API access and rate limits."
                )

    except KeyError:
        st.info(
            "Configure ALPHA_VANTAGE_API_KEY in "
            "your Streamlit secrets."
        )

    except Exception as exc:
        print(
            f"Fundamental data error for {ticker}: "
            f"{type(exc).__name__}: {exc}"
        )

        st.warning(
            "Fundamental data is temporarily unavailable."
        )


# --------------------------------------------------
# Market news
# --------------------------------------------------
with news_tab:
    st.subheader(f"📰 Latest News — {ticker}")

    try:
        with st.spinner("Fetching stock news..."):
            news_client = StockNews(
                ticker,
                save_news=False
            )

            news_df = news_client.read_rss()

        if news_df is None or news_df.empty:
            st.info(f"No news articles found for {ticker}.")
        else:
            for _, article in news_df.head(10).iterrows():
                article_title = article.get(
                    "title",
                    "Untitled article"
                )

                with st.expander(str(article_title)):
                    st.caption(
                        "Published: "
                        f"{article.get('published', 'Unknown')}"
                    )

                    st.write(
                        article.get(
                            "summary",
                            "No summary available."
                        )
                    )

                    title_sentiment = article.get(
                        "sentiment_title"
                    )

                    summary_sentiment = article.get(
                        "sentiment_summary"
                    )

                    if pd.notna(title_sentiment):
                        st.write(
                            f"Title sentiment: {title_sentiment}"
                        )

                    if pd.notna(summary_sentiment):
                        st.write(
                            "Summary sentiment: "
                            f"{summary_sentiment}"
                        )

    except Exception as exc:
        print(
            f"News error for {ticker}: "
            f"{type(exc).__name__}: {exc}"
        )

        st.warning("News is temporarily unavailable.")