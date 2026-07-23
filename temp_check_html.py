import sys
html = sys.stdin.read()
checks = [
    ("log-body", "log-body" in html),
    ("logFilter", "logFilter" in html),
    ("toggleCardLive", "toggleCardLive" in html),
    ("live-toggle-index", "live-toggle-index" in html),
    ("live-toggle-nifty50", "live-toggle-nifty50" in html),
    ("scan-tab-left", "scan-tab-left" in html),
    ("active-positions-body", "active-positions-body" in html),
    ("prog-live-toggle", "prog-live-toggle" in html),
    ("record_executed_pattern", "record_executed_pattern" in html),
]
for name, found in checks:
    print(f"  {name}: {'FOUND' if found else 'MISSING'}")
print(f"\nTotal length: {len(html)} chars")
print(f"Body tag: {'<body' in html}")
print(f"renderReport: {'renderReport' in html}")
