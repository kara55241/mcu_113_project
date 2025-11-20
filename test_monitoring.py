"""
測試監控系統功能
"""
import sys
import os

# 設置 Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

import django
django.setup()

def test_checkpoint_parser():
    """測試 CheckpointParser"""
    print("\n" + "="*60)
    print("Test: CheckpointParser")
    print("="*60)

    try:
        from monitoring_api.utils.checkpoint_parser import CheckpointParser

        parser = CheckpointParser()
        print(f"[OK] CheckpointParser loaded")
        print(f"[OK] AGENT_DISPLAY_NAMES: {len(parser.AGENT_DISPLAY_NAMES)} entries")
        print(f"[OK] TOOL_AGENT_MAP: {len(parser.TOOL_AGENT_MAP)} entries")

        # 檢查關鍵節點
        nodes = ['supervisor', 'chronic_agent', 'cardiovascular_agent', 'fact_check_agent']
        all_found = True
        for node in nodes:
            if node in parser.AGENT_DISPLAY_NAMES:
                print(f"[OK] Node '{node}' -> '{parser.AGENT_DISPLAY_NAMES[node]}'")
            else:
                print(f"[ERROR] Node '{node}' not found")
                all_found = False

        return all_found

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

def test_monitor_command():
    """測試 monitor_agents 命令"""
    print("\n" + "="*60)
    print("Test: monitor_agents command")
    print("="*60)

    try:
        from myapp.management.commands.monitor_agents import DatabaseMonitor

        monitor = DatabaseMonitor()
        print(f"[OK] DatabaseMonitor created")
        print(f"[OK] Database path: {monitor.db_path}")

        # 測試連接
        conn = monitor.connect()
        if conn:
            print("[OK] Database connection successful")

            # 測試查詢
            checkpoints = monitor.get_recent_checkpoints(limit=10)
            print(f"[OK] Retrieved {len(checkpoints)} recent checkpoints")

            conn.close()
            return True
        else:
            print("[ERROR] Database connection failed")
            return False

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_files():
    """測試資料庫檔案存在"""
    print("\n" + "="*60)
    print("Test: Database files")
    print("="*60)

    import os

    files_to_check = [
        "./agent_checkpoint_new.sqlite",
        "./db.sqlite3"
    ]

    all_exist = True
    for filepath in files_to_check:
        if os.path.exists(filepath):
            size = os.path.getsize(filepath) / (1024 * 1024)  # MB
            print(f"[OK] {filepath} exists ({size:.2f} MB)")
        else:
            print(f"[ERROR] {filepath} not found")
            all_exist = False

    return all_exist

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Testing Monitoring System")
    print("="*60)

    results = []

    # Test 1: Database files
    print("\n[1/3] Testing database files...")
    results.append(("Database Files", test_database_files()))

    # Test 2: CheckpointParser
    print("\n[2/3] Testing CheckpointParser...")
    results.append(("CheckpointParser", test_checkpoint_parser()))

    # Test 3: Monitor command
    print("\n[3/3] Testing monitor command...")
    results.append(("Monitor Command", test_monitor_command()))

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] All monitoring tests passed!")
        sys.exit(0)
    else:
        print(f"\n[FAILURE] {total - passed} test(s) failed!")
        sys.exit(1)
