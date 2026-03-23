from fund_analyzer.config import load_config
from fund_analyzer.database import create_session_factory
from sqlalchemy import text

settings = load_config("config/settings.yaml")
session = create_session_factory(settings)()

tables = [
    "fund_info", "fund_nav", "index_quote",
    "portfolio_position", "portfolio_transaction",
    "strategy_signal", "dip_plan",
]

for t in tables:
    count = session.execute(text(f"SELECT count(*) FROM {t}")).scalar()
    print(f"{t}: {count}")

# 样本数据
print("\n--- fund_info 样本 ---")
rows = session.execute(text("SELECT fund_code, fund_name, fund_type, fund_size FROM fund_info LIMIT 5")).fetchall()
for r in rows:
    print(r)

print("\n--- fund_nav 样本 ---")
rows = session.execute(text("SELECT fund_code, date, nav FROM fund_nav LIMIT 5")).fetchall()
for r in rows:
    print(r)

print("\n--- index_quote 样本 ---")
rows = session.execute(text("SELECT index_code, date, close FROM index_quote LIMIT 5")).fetchall()
for r in rows:
    print(r)
