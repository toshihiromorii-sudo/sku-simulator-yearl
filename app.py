import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

st.set_page_config(page_title="SKUシミュレーター", layout="wide")

st.title("📦 SKU追加シミュレーター（年次 × ランプ効果 × 陳腐化＋人件費）")

# -----------------------------
# サイドバー入力
# -----------------------------
st.sidebar.header("シミュレーション設定")

# 期間
T = st.sidebar.number_input("シミュレーション期間（年）", 1, 20, 10)

# 販売パラメータ
q = st.sidebar.slider("販売率 q（1SKUあたり販売される割合）", 0.0, 1.0, 0.2, 0.01)
r0 = st.sidebar.slider("初年度売上率 r0", 0.0, 1.0, 0.5, 0.05)
r1 = st.sidebar.slider("2年目売上率 r1", 0.0, 1.0, 0.8, 0.05)
r2 = st.sidebar.slider("3年目以降売上率 r2", 0.0, 1.0, 1.0, 0.05)
d = st.sidebar.slider("年次陳腐化率 d", 0.0, 0.5, 0.05, 0.01)

# 登録オペレーション前提
st.sidebar.subheader("登録オペレーション前提")
time_per_sku = st.sidebar.number_input("1SKU登録時間（分）", 1, 120, 40)
wage_per_hour = st.sidebar.number_input("時給（円）", 1000, 10000, 2000, 100)
hours_per_month = st.sidebar.number_input("1人あたり月稼働時間（h）", 40, 200, 160)

# マスタアップロード
st.sidebar.subheader("カテゴリ平均単価マスタ")
uploaded_file = st.sidebar.file_uploader("CSVをアップロード（カテゴリ, 平均単価）", type=["csv"])

# 単価補正係数
unit_price_factor = st.sidebar.slider("平均単価係数（全カテゴリ共通調整）", 0.5, 2.0, 1.0, 0.1)

# -----------------------------
# デフォルトカテゴリマスタ
# -----------------------------
if uploaded_file:
    master_df = pd.read_csv(uploaded_file)
else:
    master_df = pd.DataFrame({
        "カテゴリ": ["OA・PC", "文具", "生活用品", "家具", "MRO", "メディカル", "その他"],
        "平均単価": [50000, 500, 1500, 20000, 3000, 8000, 10000]
    })

master_df["平均単価"] = master_df["平均単価"] * unit_price_factor

# -----------------------------
# SKU追加数入力
# -----------------------------
st.header("追加SKU数（カテゴリ別×年次）")

years = [f"Y{t}" for t in range(1, T+1)]
sku_plan = pd.DataFrame(0, index=master_df["カテゴリ"], columns=years)
edited_plan = st.data_editor(sku_plan, num_rows="dynamic")

# -----------------------------
# 売上・人件費計算ロジック
# -----------------------------
sales_records = []
labor_records = []

for t in range(1, T+1):
    year_sales = 0
    year_hours = 0

    for cat in master_df["カテゴリ"]:
        added = edited_plan.loc[cat, f"Y{t}"]
        unit_price = master_df.loc[master_df["カテゴリ"] == cat, "平均単価"].values[0]

        # 登録時間・人件費
        hours = added * time_per_sku / 60
        cost = hours * wage_per_hour
        year_hours += hours
        labor_records.append({"年": t, "カテゴリ": cat, "登録時間(h)": hours, "人件費(円)": cost})

        # 各年に追加したSKUが以降の年に売上貢献
        for future in range(t, T+1):
            age = future - t
            if age == 0:
                factor = r0
            elif age == 1:
                factor = r1
            else:
                factor = r2 * ((1 - d) ** (age - 2))
            contrib = added * q * unit_price * factor
            sales_records.append({"年": future, "カテゴリ": cat, "売上": contrib})

sales_df = pd.DataFrame(sales_records).groupby(["年", "カテゴリ"]).sum().reset_index()
labor_df = pd.DataFrame(labor_records).groupby(["年", "カテゴリ"]).sum().reset_index()

# -----------------------------
# 集計
# -----------------------------
sales_summary = sales_df.groupby("年")["売上"].sum().reset_index()
labor_summary = labor_df.groupby("年")[["登録時間(h)", "人件費(円)"]].sum().reset_index()
summary = pd.merge(sales_summary, labor_summary, on="年")
summary["差引利益(円)"] = summary["売上"] - summary["人件費(円)"]

# -----------------------------
# 出力
# -----------------------------
st.subheader("年次サマリー")
st.dataframe(summary)

st.subheader("売上推移")
st.altair_chart(
    alt.Chart(sales_summary).mark_line(point=True).encode(x="年:O", y="売上:Q"),
    use_container_width=True
)

st.subheader("人件費推移")
st.altair_chart(
    alt.Chart(labor_summary).mark_line(point=True).encode(x="年:O", y="人件費(円):Q"),
    use_container_width=True
)

st.subheader("差引利益推移")
st.altair_chart(
    alt.Chart(summary).mark_line(point=True).encode(x="年:O", y="差引利益(円):Q"),
    use_container_width=True
)

st.subheader("カテゴリ別売上")
st.dataframe(sales_df.pivot_table(index="カテゴリ", columns="年", values="売上", aggfunc="sum", fill_value=0))

# CSVダウンロード
st.download_button("📥 年次サマリーCSVダウンロード", summary.to_csv(index=False).encode("utf-8"), "summary.csv", "text/csv")
st.download_button("📥 カテゴリ別売上CSVダウンロード", sales_df.to_csv(index=False).encode("utf-8"), "sales_by_category.csv", "text/csv")
