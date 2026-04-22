import sys
import traceback

print("=== Starting import test ===")

try:
    from app.main import app
    print(f"App loaded OK: {len(app.routes)} routes")
    
    career_routes = [r for r in app.routes if hasattr(r, 'path') and 'career' in str(r.path)]
    print(f"Career routes: {len(career_routes)}")
    for r in career_routes:
        methods = getattr(r, 'methods', set())
        print(f"  {methods} {r.path}")
    
    print("\n=== Test complete ===")
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)
