"""风险评估问卷定义。"""
from __future__ import annotations

QUESTIONS: list[dict] = [
    {
        "id": "experience",
        "text": "您的投资经验有多长？",
        "options": [
            {"label": "没有投资经验", "score": 5},
            {"label": "1-3年", "score": 10},
            {"label": "3-5年", "score": 15},
            {"label": "5年以上", "score": 20},
        ],
    },
    {
        "id": "loss_tolerance",
        "text": "您能承受的最大投资亏损是多少？",
        "options": [
            {"label": "不能接受任何亏损", "score": 5},
            {"label": "亏损10%以内", "score": 10},
            {"label": "亏损20%以内", "score": 15},
            {"label": "亏损30%以内", "score": 18},
            {"label": "亏损30%以上也能接受", "score": 20},
        ],
    },
    {
        "id": "investment_horizon",
        "text": "您的投资期限预期是多长？",
        "options": [
            {"label": "1年以内", "score": 5},
            {"label": "1-3年", "score": 10},
            {"label": "3-5年", "score": 15},
            {"label": "5年以上", "score": 20},
        ],
    },
    {
        "id": "income_stability",
        "text": "您的收入来源稳定程度如何？",
        "options": [
            {"label": "不太稳定", "score": 5},
            {"label": "比较稳定", "score": 10},
            {"label": "非常稳定，且有较多储蓄", "score": 20},
        ],
    },
    {
        "id": "investment_goal",
        "text": "您的主要投资目标是什么？",
        "options": [
            {"label": "保值，跑赢通胀即可", "score": 5},
            {"label": "稳健增值，追求中等收益", "score": 10},
            {"label": "积极增值，愿意承担较大波动", "score": 15},
            {"label": "追求高收益，能承受大幅波动", "score": 20},
        ],
    },
]
