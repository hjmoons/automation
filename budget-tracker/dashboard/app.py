import os
from datetime import date, datetime

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="가계부 대시보드", layout="wide")
st.title("가계부 대시보드")


def get_categories():
    return requests.get(f"{API_URL}/categories/").json()


def get_assets():
    return requests.get(f"{API_URL}/assets/").json()


def get_transactions():
    return requests.get(f"{API_URL}/transactions/").json()


def compute_current_balance(asset_id, opening_balance, transactions):
    balance = opening_balance or 0
    for t in transactions:
        if t["type"] == "income" and t["asset_id"] == asset_id:
            balance += t["amount"]
        elif t["type"] == "expense" and t["asset_id"] == asset_id:
            balance -= t["amount"]
        elif t["type"] == "transfer":
            if t["asset_id"] == asset_id:
                balance -= t["amount"]
            if t.get("to_asset_id") == asset_id:
                balance += t["amount"]
    return balance


categories = get_categories()
assets = get_assets()
category_options = {c["name"]: c["id"] for c in categories}
asset_options = {a["name"]: a["id"] for a in assets}

tab_list, tab_add, tab_edit, tab_assets = st.tabs(["거래 내역", "거래 추가", "정정", "자산"])

with tab_list:
    transactions = get_transactions()
    if transactions:
        st.dataframe(transactions, use_container_width=True)
        total_expense = sum(t["amount"] for t in transactions if t["type"] == "expense")
        total_income = sum(t["amount"] for t in transactions if t["type"] == "income")
        col1, col2 = st.columns(2)
        col1.metric("총 지출", f"{total_expense:,}원")
        col2.metric("총 수입", f"{total_income:,}원")
    else:
        st.info("아직 거래 내역이 없습니다.")

with tab_add:
    with st.form("add_transaction"):
        t_date = st.date_input("날짜", value=date.today())
        title = st.text_input("항목명")
        amount = st.number_input("금액", min_value=0, step=100)
        t_type = st.selectbox("구분", ["expense", "income", "transfer"])
        category_name = st.selectbox("카테고리", list(category_options.keys()) or ["(없음)"])
        asset_name = st.selectbox("결제수단 / 보내는 계좌", list(asset_options.keys()) or ["(없음)"])
        to_asset_name = st.selectbox(
            "받는 계좌 (이체일 때만)", ["(해당없음)"] + list(asset_options.keys())
        )
        memo = st.text_input("메모")
        submitted = st.form_submit_button("저장")
        if submitted:
            payload = {
                "date": datetime.combine(t_date, datetime.min.time()).isoformat(),
                "title": title,
                "amount": int(amount),
                "type": t_type,
                "category_id": category_options.get(category_name),
                "asset_id": asset_options.get(asset_name),
                "to_asset_id": asset_options.get(to_asset_name) if t_type == "transfer" else None,
                "source": "manual",
                "memo": memo,
                "confirmed": True,
            }
            r = requests.post(f"{API_URL}/transactions/", json=payload)
            if r.ok:
                st.success("저장되었습니다.")
                st.rerun()
            else:
                st.error(r.text)

with tab_edit:
    transactions = get_transactions()
    if transactions:
        labels = {
            f'{t["id"]} · {t["date"][:10]} · {t["title"]} · {t["amount"]:,}원': t
            for t in transactions
        }
        selected_label = st.selectbox("수정할 거래 선택", list(labels.keys()))
        selected = labels[selected_label]
        with st.form("edit_transaction"):
            amount = st.number_input("금액", value=selected["amount"], step=100)
            title = st.text_input("항목명", value=selected["title"])
            confirmed = st.checkbox("확인됨", value=selected["confirmed"])
            submitted = st.form_submit_button("수정 저장")
            if submitted:
                payload = {"amount": int(amount), "title": title, "confirmed": confirmed}
                r = requests.patch(f"{API_URL}/transactions/{selected['id']}", json=payload)
                if r.ok:
                    st.success("수정되었습니다.")
                    st.rerun()
                else:
                    st.error(r.text)
    else:
        st.info("수정할 거래가 없습니다.")

with tab_assets:
    if assets:
        transactions = get_transactions()
        display_assets = [
            {**a, "현재 잔액": compute_current_balance(a["id"], a["balance"], transactions)}
            for a in assets
        ]
        st.dataframe(display_assets, use_container_width=True)
        total_balance = sum(d["현재 잔액"] for d in display_assets)
        st.metric("총 자산", f"{total_balance:,}원")
    else:
        st.info("등록된 자산이 없습니다.")
