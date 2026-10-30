
from flask import Flask, render_template, request, redirect, url_for, abort
import sqlite3
from pathlib import Path
from datetime import date
from collections import defaultdict

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "money.db"


# 連接資料庫
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# 建立資料表
def init_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                note TEXT
            )
        """)


# 讀取及檢查表單資料
def read_form():
    record_type = request.form.get("type", "")
    category = request.form.get("category", "").strip()
    date_text = request.form.get("date", "")
    note = request.form.get("note", "").strip()

    try:
        amount = int(request.form.get("amount", ""))
        date.fromisoformat(date_text)
    except ValueError:
        abort(400, description="請輸入有效的金額與日期")

    if record_type not in ("income", "expense"):
        abort(400, description="收支類型錯誤")

    if amount <= 0 or not category or len(note) > 200:
        abort(400, description="請完整填寫正確的記帳資料")

    return record_type, amount, category, date_text, note


# 首頁與每月統計
@app.route("/")
def home():
    today = date.today()

    year_text = request.args.get("year", str(today.year))
    month_text = request.args.get("month", str(today.month))

    try:
        year = int(year_text)
        month = int(month_text)

        if not (1 <= year <= 9999 and 1 <= month <= 12):
            raise ValueError

    except ValueError:
        abort(400, description="請選擇正確的年份與月份")

    month_prefix = f"{year:04d}-{month:02d}"

    # 查詢選定月份的紀錄
    with get_db_connection() as conn:
        records = conn.execute("""
            SELECT * FROM records
            WHERE substr(date, 1, 7) = ?
            ORDER BY date DESC, id DESC
        """, (month_prefix,)).fetchall()

    # 計算收支
    total_income = sum(
        record["amount"]
        for record in records
        if record["type"] == "income"
    )

    total_expense = sum(
        record["amount"]
        for record in records
        if record["type"] == "expense"
    )

    balance = total_income - total_expense

    # 計算各分類支出
    category_totals = defaultdict(int)

    for record in records:
        if record["type"] == "expense":
            category_totals[record["category"]] += record["amount"]

    category_labels = list(category_totals.keys())
    category_values = list(category_totals.values())

    # 計算各分類金額與百分比
    category_stats = []

    for category, amount in category_totals.items():
        percentage = (
            round(amount / total_expense * 100, 1)
            if total_expense > 0
            else 0
        )

        category_stats.append({
            "name": category,
            "amount": amount,
            "percentage": percentage
        })

    category_stats.sort(
        key=lambda item: item["amount"],
        reverse=True
    )

    return render_template(
        "index.html",
        records=records,
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        year=year,
        month=month,
        category_labels=category_labels,
        category_values=category_values,
        category_stats=category_stats
    )


# 新增紀錄
@app.route("/add", methods=["POST"])
def add_record():
    data = read_form()

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO records (type, amount, category, date, note)
            VALUES (?, ?, ?, ?, ?)
        """, data)

    record_date = date.fromisoformat(data[3])

    return redirect(url_for(
        "home",
        year=record_date.year,
        month=record_date.month
    ))


# 編輯紀錄
@app.route("/edit/<int:record_id>", methods=["GET", "POST"])
def edit_record(record_id):
    with get_db_connection() as conn:
        record = conn.execute(
            "SELECT * FROM records WHERE id = ?",
            (record_id,)
        ).fetchone()

    if record is None:
        abort(404, description="找不到這筆記帳紀錄")

    if request.method == "POST":
        data = read_form()

        with get_db_connection() as conn:
            conn.execute("""
                UPDATE records
                SET type = ?, amount = ?, category = ?, date = ?, note = ?
                WHERE id = ?
            """, (*data, record_id))

        record_date = date.fromisoformat(data[3])

        return redirect(url_for(
            "home",
            year=record_date.year,
            month=record_date.month
        ))

    return render_template("edit.html", record=record)


# 刪除紀錄
@app.route("/delete/<int:record_id>", methods=["POST"])
def delete_record(record_id):
    with get_db_connection() as conn:
        record = conn.execute(
            "SELECT date FROM records WHERE id = ?",
            (record_id,)
        ).fetchone()

        if record is None:
            abort(404, description="找不到這筆記帳紀錄")

        conn.execute(
            "DELETE FROM records WHERE id = ?",
            (record_id,)
        )

    record_date = date.fromisoformat(record["date"])

    return redirect(url_for(
        "home",
        year=record_date.year,
        month=record_date.month
    ))


# 初始化資料庫
init_db()


# 啟動 Flask
if __name__ == "__main__":
    app.run(debug=False)
