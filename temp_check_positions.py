import json, sys
d = json.load(sys.stdin)
print("API Response Check:")
print(f"  positions (from trade_db): {list(d.get('positions',{}).keys())}")
print(f"  all_trades count: {len(d.get('all_trades',[]))}")
for t in d.get('all_trades',[]):
    print(f"    ID={t.get('id')} Sym={t.get('symbol')} Status={t.get('status')} Engine={t.get('engine')}")
print(f"  kite_positions count: {len(d.get('kite_positions',[]))}")
for kp in d.get('kite_positions',[]):
    print(f"    Contract={kp.get('contract')} qty={kp.get('quantity')}")
print()
print("Now check the HTML that JS should produce:")
html = '<p class="empty-state">No positions match filter</p>'
positions_html = d.get('positions', {})
all_trades = d.get('all_trades', [])
kite_pos = d.get('kite_positions', [])
print(f"  kite_pos has data: {len(kite_pos) > 0}")
print(f"  all_trades has data: {len(all_trades) > 0}")
# Simulate the JS filter logic
positionFilter = 'active'
merged = []
seen = set()
for kp in kite_pos:
    seen.add(kp.get('contract', ''))
    merged.append({'symbol': kp.get('contract', ''), 'source': 'kite'})
for t in all_trades:
    contract = t.get('contract') or t.get('symbol') or ''
    if contract in seen:
        continue
    st = (t.get('status') or '').lower()
    if positionFilter == 'active' and st != 'active':
        continue
    merged.append({'symbol': t.get('symbol', ''), 'source': 'db', 'status': st})
print(f"  merged positions after filter: {len(merged)}")
for m in merged:
    print(f"    Sym={m.get('symbol')} Source={m.get('source')} Status={m.get('status','')}")
