"""One slide per CJK script: a title, running copy, a card and a table, each set with the
theme's own face for that script and broken where the language allows."""

from __future__ import annotations

from typing import Any

# lang, title, paragraph, card heading, card body, table header, table rows
_COPY = {
    "cjk-ja": (
        "ja",
        "四半期の売上は前年を上回りました",
        "「新しい製品」の導入で、顧客数は前年同期比で二割増えました。問い合わせは減っています。",
        "次の一歩",
        "来期は販売地域を広げます。",
        ["地域", "成長率"],
        [["東日本", "12%"], ["西日本", "8%"]],
    ),
    "cjk-zh-hans": (
        "zh-Hans",
        "季度收入超过去年同期",
        "新产品上线后，客户数量同比增长了百分之二十。客服咨询量有所下降。",
        "下一步",
        "下季度将扩大销售区域。",
        ["地区", "增长率"],
        [["华东", "12%"], ["华南", "8%"]],
    ),
    "cjk-zh-hant": (
        "zh-Hant",
        "季度營收超越去年同期",
        "新產品上線後，客戶數量年增百分之二十。客服詢問量有所下降。",
        "下一步",
        "下季將擴大銷售區域。",
        ["地區", "成長率"],
        [["北部", "12%"], ["南部", "8%"]],
    ),
    "cjk-ko": (
        "ko",
        "분기 매출이 전년을 넘어섰습니다",
        "신제품 출시 후 고객 수가 전년 동기 대비 20% 늘었습니다. 고객 문의는 줄고 있습니다.",
        "다음 단계",
        "다음 분기에는 판매 지역을 넓힙니다.",
        ["지역", "성장률"],
        [["수도권", "12%"], ["영남", "8%"]],
    ),
}


def script_slides() -> dict[str, dict[str, Any]]:
    """Every exercise in this family, keyed by name."""
    return {
        name: {
            "lang": lang,
            "title": title,
            "place": [
                {"at": {"cols": "left-half"}, "prose": {"paragraphs": [paragraph]}},
                {
                    "at": {"cols": "right-half", "rows": "top-half"},
                    "card": {"heading": heading, "body": body},
                },
                {
                    "at": {"cols": "right-half", "rows": "bottom-half"},
                    "table": {"header": header, "rows": rows},
                },
            ],
        }
        for name, (lang, title, paragraph, heading, body, header, rows) in _COPY.items()
    }
