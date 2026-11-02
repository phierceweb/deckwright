"""deckwright-style names for glyphs the vendored set calls something else.

Hyphenated spellings already resolve on their own, so an alias earns its place only
where the word an author reaches for is a different word.

- :data:`OVERRIDES` runs *before* the set, for names whose same-named glyph draws
  something else entirely.
- :data:`ALIASES` runs *after* everything has missed, so it can never shadow a name
  that already resolves.
"""

from __future__ import annotations

OVERRIDES: dict[str, str] = {
    # `arrow_left`/`arrow_right` are the small carets; the shafted pair is back/forward.
    "arrow-left": "arrow_back",
    "arrow-right": "arrow_forward",
    # `globe` is a filled continent disc; `language` is the meridian grid.
    "globe": "language",
    # `pin` is a keypad for a PIN code, not a map pin.
    "pin": "location_on",
}

ALIASES: dict[str, str] = {
    # Marks and shapes
    "plus": "add",
    "minus": "remove",
    "arrow-up": "arrow_upward",
    "arrow-down": "arrow_downward",
    # Unreached when drawing — `place_icon` prefers the preset; kept so `load()`
    # still answers what the name means.
    "ring": "trip_origin",
    "triangle": "change_history",
    "grid": "grid_view",
    # Everyday objects
    "user": "person",
    "users": "group",
    "gear": "settings",
    "bell": "notifications",
    "clock": "schedule",
    "calendar": "calendar_today",
    "document": "note",
    "eye": "visibility",
    "heart": "favorite",
    # Direction of travel
    "growth": "trending_up",
    "decline": "trending_down",
    "steady": "trending_flat",
    "momentum": "rocket_launch",
    # Money
    "revenue": "attach_money",
    "cost": "request_quote",
    "budget": "account_balance_wallet",
    "bank": "account_balance",
    "invoice": "receipt_long",
    "pricing": "sell",
    # Plans and progress
    "roadmap": "route",
    "milestone": "flag_circle",
    "award": "workspace_premium",
    "blocker": "block",
    "decision": "call_split",
    "phase": "linear_scale",
    "backlog": "pending_actions",
    # People
    "team": "groups",
    "audience": "groups_3",
    "customer": "support_agent",
    "hire": "person_add",
    "org-chart": "account_tree",
    "role": "badge",
    "profile": "account_circle",
    "meeting": "groups",
    # Engineering
    "bug": "bug_report",
    "deploy": "rocket_launch",
    "release": "new_releases",
    "test": "science",
    "pipeline": "conveyor_belt",
    "server": "dns",
    "network": "lan",
    "version": "history",
    "alert": "notification_important",
    "log": "article",
    "config": "tune",
    "toggle": "toggle_on",
    "integration": "integration_instructions",
    "console": "terminal",
    "payload": "data_object",
    # Models and agents
    "ai": "auto_awesome",
    "agent": "smart_toy",
    "brain": "psychology",
    "prompt": "chat_bubble",
    "model": "deployed_code",
    "embedding": "scatter_plot",
    # Data. Chosen by silhouette: `pie_chart` is a segmented disc, not a cut wedge.
    "chart-bar": "bar_chart_4_bars",
    "chart-line": "show_chart",
    "chart-pie": "incomplete_circle",
    "chart-area": "area_chart",
    "chart-scatter": "scatter_plot",
    "chart-bubble": "bubble_chart",
    "chart-donut": "donut_large",
    "chart-stacked": "stacked_bar_chart",
    "chart-waterfall": "waterfall_chart",
    "chart-candlestick": "candlestick_chart",
    "chart-gauge": "speed",
    "metric": "query_stats",
    "ranking": "leaderboard",
    "forecast": "insights",
    "query": "manage_search",
    "export": "file_download",
    "import": "file_upload",
    "spreadsheet": "table_chart",
    # Talking
    "message": "chat_bubble",
    "email": "mail",
    "phone": "call",
    "video": "videocam",
    "announcement": "campaign",
    # Outcome
    "success": "check_circle",
    "failure": "cancel",
    "approve": "thumb_up",
    "reject": "thumb_down",
    "question": "help",
    "todo": "checklist",
    # Trust
    "audit": "fact_check",
    "compliance": "verified_user",
    "permission": "admin_panel_settings",
    "encryption": "encrypted",
    "governance": "policy",
    "legal": "gavel",
    # Where
    "office": "apartment",
    "world": "public",
    "research": "travel_explore",
    "learning": "school",
    # When
    "deadline": "alarm",
    "duration": "timer",
}
