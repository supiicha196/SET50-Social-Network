import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
from pathlib import Path

st.set_page_config(
    page_title="SET50 Social Network",
    page_icon="📈",
    layout="wide"
)

st.title("📈 SET50 Social Network")
st.write("SET50 Company–Shareholder Relationship Network")

st.markdown("""
<style>
.main {background-color: #F8F9FA;}

h1, h2, h3 {color: #2E4057;}

div[data-testid="stMetric"] {
    background-color: white;
    padding: 15px;
    border-radius: 12px;
    border: 1px solid #E0E0E0;
}

.stDataFrame {background-color: white;}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Load Data
# -----------------------------

@st.cache_data
def load_data():
    set50_df = pd.read_csv("data/set50_companies.csv")
    shareholder_df = pd.read_csv("data/shareholders.csv")
    return set50_df, shareholder_df

set50_df, shareholder_df = load_data()

# -----------------------------
# Sidebar Filter
# -----------------------------

st.sidebar.header("Filter")

sector_options = ["Total"] + sorted(set50_df["sector"].dropna().unique().tolist())
selected_sector = st.sidebar.selectbox("Choose Sector", sector_options)

if selected_sector != "Total":
    set50_df = set50_df[set50_df["sector"] == selected_sector]

company_options = ["Total"] + sorted(set50_df["symbol"].unique().tolist())
selected_company = st.sidebar.selectbox("Choose Company", company_options)

if selected_company != "Total":
    set50_df = set50_df[set50_df["symbol"] == selected_company]

rank_options = sorted(shareholder_df["rank"].dropna().unique().tolist())
selected_ranks = st.sidebar.multiselect(
    "Choose Shareholder",
    rank_options,
    default=rank_options
)

shareholder_df = shareholder_df[
    (shareholder_df["symbol"].isin(set50_df["symbol"])) &
    (shareholder_df["rank"].isin(selected_ranks))
]

search_shareholder = st.sidebar.text_input(
    "Search Shareholder",
    ""
)

if search_shareholder:
    shareholder_df = shareholder_df[
        shareholder_df["shareholder_name"]
        .str.contains(search_shareholder, case=False, na=False)
    ]

    set50_df = set50_df[
        set50_df["symbol"].isin(shareholder_df["symbol"])
    ]

# -----------------------------
# KPI Summary
# -----------------------------

st.header("Dataset Overview")

total_companies = set50_df["symbol"].nunique()
total_shareholders = shareholder_df["shareholder_name"].nunique()
total_edges = len(shareholder_df)

top_shareholder = (
    shareholder_df["shareholder_name"]
    .value_counts()
    .idxmax()
    if len(shareholder_df) > 0
    else "-"
)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Companies", total_companies)
col2.metric("Unique Shareholders", total_shareholders)
col3.metric("Total Relationships", total_edges)
col4.metric("Most Common Shareholder", top_shareholder)

# -----------------------------
# Relationship Summary Table
# -----------------------------

st.header("Shareholder–Company Relationship Summary")

relationship_summary = (
    shareholder_df
    .groupby("shareholder_name")
    .agg(
        company_count=("symbol", "nunique"),
        related_companies=("symbol", lambda x: ", ".join(sorted(x.unique()))),
        avg_percent_share=("percent_share", "mean")
    )
    .reset_index()
    .sort_values("company_count", ascending=False)
)

styled_relationship = (
    relationship_summary.style
    .format({
        "avg_percent_share": "{:.2f}%"
    })
    .set_properties(
        subset=["company_count", "avg_percent_share"],
        **{"text-align": "right"}
    )
)

st.dataframe(
    styled_relationship,
    use_container_width=True,
    hide_index=True
)

# -----------------------------
# Data Table
# -----------------------------

st.header("Company and Shareholder Details")

col1, col2 = st.columns(2)

with col1:
    st.subheader("SET50 Companies")
    st.dataframe(set50_df.reset_index(drop=True), use_container_width=True, hide_index=True)

with col2:
    st.subheader("Top 5 Shareholders")

    styled_shareholder = (
        shareholder_df.style
        .format({
            "shares": "{:,.0f}",
            "percent_share": "{:.2f}%"
        })
        .set_properties(
            subset=["shares", "percent_share"],
            **{"text-align": "right"}
        )
    )

    st.dataframe(
        styled_shareholder,
        use_container_width=True,
        hide_index=True
    )

# -----------------------------
# Create Network Graph
# -----------------------------

st.header("Social Network Graph")

G = nx.Graph()

for _, row in set50_df.iterrows():
    G.add_node(
        row["symbol"],
        label=row["symbol"],
        title=row["company_name"],
        group="company"
    )

for _, row in shareholder_df.iterrows():
    company = row["symbol"]
    shareholder = row["shareholder_name"]

    G.add_node(
        shareholder,
        label=shareholder,
        title=f"Shareholders: {shareholder}",
        group="shareholder"
    )

    G.add_edge(
        company,
        shareholder,
        title=f"Rank {row['rank']} | {row['percent_share']}%",
        value=row["percent_share"] if row["percent_share"] > 0 else 1
    )

# -----------------------------
# Network Metrics
# -----------------------------

st.header("Network Metrics")

num_nodes = G.number_of_nodes()
num_edges = G.number_of_edges()

col1, col2 = st.columns(2)

col1.metric("Total Nodes", num_nodes)
col2.metric("Total Edges", num_edges)

net = Network(
    height="650px",
    width="100%",
    bgcolor="#ffffff",
    font_color="black"
)

net.from_nx(G)

company_nodes = set(set50_df["symbol"].astype(str))
shareholder_counts = shareholder_df["shareholder_name"].astype(str).value_counts()

for node in net.nodes:
    node_id = str(node["id"]).strip()

    if "group" in node:
        del node["group"]

    if node_id in company_nodes:
        node["color"] = {
            "background": "#6A5ACD",
            "border": "#483D8B"
        }
        node["size"] = 30

    elif shareholder_counts.get(node_id, 0) > 1:
        node["color"] = {
            "background": "#90EE90",
            "border": "#3CB371"
        }
        node["size"] = 16

    else:
        node["color"] = {
            "background": "#FFD700",
            "border": "#DAA520"
        }
        node["size"] = 16

net.set_options("""
{
  "nodes": {
    "font": {
      "size": 16
    }
  },
  "edges": {
    "color": {
      "color": "#999999"
    },
    "smooth": false
  },
  "physics": {
    "barnesHut": {
      "gravitationalConstant": -8000,
      "centralGravity": 0.5,
      "springLength": 100
    },
    "minVelocity": 0.75
  }
}
""")

html = net.generate_html()

st.caption(
    "🟣 Purple Nodes: SET50 Companies | "
    "🟢 Green Nodes: Shareholders with Holdings in Multiple Companies | "
    "🟡 Yellow Nodes: Shareholders with Holdings in a Single Company | "
    "➖ Gray Edges: Shareholding Relationships"
)

components.html(html, height=700, scrolling=True)