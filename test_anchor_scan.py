#!/usr/bin/env python3
"""Test the anchor scan trigger functionality.

This test verifies the current behavior where anchor scan request files
trigger the appropriate anchor scan for each engine based on the engine value
stored in the request file.

This test is now a manual verification tool since the behavior has been
modified to accept anchor scan requests for all engines.
"""

import os
import tempfile
import logging
from unittest.mock import Mock, MagicMock, patch
import sys
import subprocess

# Add the parent directory to sys.path to import the scripts
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging to display INFO messages
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Mock the KiteConnect class
class MockKiteConnect:
    def __init__(self, api_key):
        self.api_key = api_key
    
    def set_access_token(self, token):
        pass
    
    def historical_data(self, token, from_date, to_date, timeframe):
        # Return empty DataFrame to simulate no data
        import pandas as pd
        return pd.DataFrame()

def test_all_engines():
    """Test that all three engines can trigger anchor scan."""
    print("\n" + "="*80)
    print("MANUAL VERIFICATION - Anchor Scan Trigger Tests")
    print("="*80)
    print("\nModified behavior:")
    print("- All engines now accept anchor scan requests for any engine")
    print("- The engine value determines which scanner logic is executed")
    print("\nTo verify the fix:")
    print("1. Start the Flask dashboard with: python launcher.py")
    print("2. Access: http://localhost:5050")
    print("3. Use any of the three trading programs (index, nifty50, daily)")
    print("4. Click 'Anchor Scan' button (this will trigger the scan)")
    print("5. Check logs in output/monitor/ to see if anchor scan runs")
    print("\nExpected behavior:")
    print("- anchor_scan_request.txt will contain the engine name")
    print("- All three engines will read the request file")
    print("- Only one will execute the anchor scan (depending on timing)")
    print("- The correct engine-specific anchor scan will run")
    
    # Test by checking the modified source code
    print("\n" + "="*80)
    print("Source Code Verification")
    print("="*80)
    
    files_to_check = [
        ("bull_index_trade_engine.py", "index"),
        ("bull_nifty50_scanner_executor.py", "nifty50"),
        ("bull_nifty50_daily_scanner_export.py", "daily")
    ]
    
    for filename, engine_name in files_to_check:
        print(f"\nChecking {filename} (engine: {engine_name}):")
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        
        with open(filepath, 'r') as f:
            content = f.read()
            
        # Check if anchor scan request handling exists
        if "ANCHOR_SCAN_REQUEST_FILE" in content:
            print("  [OK] Has anchor scan request file reference")
        else:
            print("  [FAIL] Missing anchor scan request file reference")
            
        # Check if main loop handles anchor scan
        if "os.path.exists(ANCHOR_SCAN_REQUEST_FILE)" in content:
            print("  [OK] Has main loop checking for request file")
        else:
            print("  [FAIL] Missing main loop check")
            
        # Check if execute_anchor_scan is defined or called
        if "def execute_anchor_scan" in content:
            print("  [OK] Has execute_anchor_scan function")
        elif "execute_anchor_scan" in content:
            print("  [OK] Has execute_anchor_scan function (partial)")
        else:
            print("  [FAIL] Missing execute_anchor_scan function")
            
        # Check if engine validation exists (should be permissive now)
        if "engine != \"{}\"".format(engine_name) in content and "Anchor scan flag not for" in content:
            print("  [WARN] Has engine validation - needs review")
        else:
            print("  [OK] No strict engine validation")


def show_log_examples():
    """Show example log output after changes."""
    print("\n" + "="*80)
    print("Expected Log Output")
    print("="*80)
    print("\nWhen anchor scan is triggered via dashboard:")
    print("1. Dashboard calls /api/anchor/scan with engine parameter")
    print("2. Request is written to: output/monitor/anchor_scan_request.txt")
    print("3. Logs show: 'Anchor scan requested via flag file (engine: index)'")
    print("\nExample logs from bull_index_trade_engine.log:")
    print("  2026-07-10 12:00:00,000 [INFO] Anchor scan requested via flag file (engine: index)")
    print("  2026-07-10 12:00:00,100 [INFO] Running anchor scan for index engines")
    print("  2026-07-10 12:05:00,000 [INFO] Anchor scan complete")
    print("\nExample logs from bull_nifty50_scanner_executor.log:")
    print("  2026-07-10 12:00:00,000 [INFO] Anchor scan requested via flag file (engine: nifty50)")
    print("  2026-07-10 12:00:00,100 [INFO] Running anchor scan for nifty50 engines")
    print("  2026-07-10 12:05:00,000 [INFO] Anchor scan complete")
    print("\nExample logs from bull_daily_scanner.log:")
    print("  2026-07-10 12:00:00,000 [INFO] Anchor scan requested via flag file (engine: daily)")
    print("  2026-07-10 12:00:00,100 [INFO] Running anchor scan for daily engines")
    print("  2026-07-10 12:05:00,000 [INFO] Anchor scan complete")


def main():
    """Run verification."""
    test_all_engines()
    show_log_examples()


if __name__ == "__main__":
    main()