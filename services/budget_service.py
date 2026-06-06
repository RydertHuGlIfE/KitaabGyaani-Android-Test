import os
import json
import uuid
from datetime import date as dt_date

BUDGET_FILE = "budget_data.json"

def get_budget_data() -> dict:
    if not os.path.exists(BUDGET_FILE):
        default_data = {
            "monthly_limit": 500.0,
            "expenses": []
        }
        save_budget_data(default_data)
        return default_data
    try:
        with open(BUDGET_FILE, "r") as f:
            return json.load(f)
    except Exception:
        default_data = {
            "monthly_limit": 500.0,
            "expenses": []
        }
        save_budget_data(default_data)
        return default_data

def save_budget_data(data: dict):
    with open(BUDGET_FILE, "w") as f:
        json.dump(data, f, indent=2)

def set_monthly_limit(limit: float) -> dict:
    data = get_budget_data()
    data["monthly_limit"] = float(limit)
    save_budget_data(data)
    return data

def add_expense(amount: float, category: str = "Others", merchant: str = "Unknown", date_str: str = None, description: str = "") -> dict:
    data = get_budget_data()
    if not date_str:
        date_str = dt_date.today().isoformat()
    expense = {
        "id": str(uuid.uuid4()),
        "amount": float(amount),
        "category": category,
        "merchant": merchant,
        "date": date_str,
        "description": description
    }
    data["expenses"].append(expense)
    save_budget_data(data)
    return expense

def get_budget_summary() -> dict:
    data = get_budget_data()
    limit = data.get("monthly_limit", 500.0)
    expenses = data.get("expenses", [])
    
    total_spent = sum(e["amount"] for e in expenses)
    remaining = limit - total_spent
    
    # Group by category
    by_category = {}
    for e in expenses:
        cat = e.get("category", "Others")
        by_category[cat] = by_category.get(cat, 0.0) + e["amount"]
        
    return {
        "limit": limit,
        "total_spent": total_spent,
        "remaining": remaining,
        "by_category": by_category,
        "expense_count": len(expenses)
    }

def get_budget_summary_text() -> str:
    summary = get_budget_summary()
    txt = f"--- CURRENT BUDGET STATUS ---\n"
    txt += f"Monthly Budget Limit: ₹{summary['limit']:.2f}\n"
    txt += f"Total Spent: ₹{summary['total_spent']:.2f}\n"
    txt += f"Remaining Balance: ₹{summary['remaining']:.2f}\n"
    txt += f"Total Expenses Logged: {summary['expense_count']}\n"
    if summary['by_category']:
        txt += "Spending by Category:\n"
        for cat, amt in summary['by_category'].items():
            txt += f"  - {cat}: ₹{amt:.2f}\n"
    txt += "-----------------------------"
    return txt
