import sys
import traceback

try:
    print("Step 1: Testing basic import...")
    from app.services.graph.career_path_neo4j import CareerPathService
    print("Step 1 OK: CareerPathService imported")
except Exception as e:
    print(f"Step 1 FAILED: {e}")
    traceback.print_exc()

try:
    print("\nStep 2: Testing recommendation service...")
    from app.services.career_goal_recommendation_service import CareerGoalRecommendationService
    print("Step 2 OK: CareerGoalRecommendationService imported")
except Exception as e:
    print(f"Step 2 FAILED: {e}")
    traceback.print_exc()

try:
    print("\nStep 3: Testing model import...")
    from app.models.career import CareerPathTask
    print("Step 3 OK: CareerPathTask imported")
    print(f"  Fields: related_skills={hasattr(CareerPathTask, 'related_skills')}")
    print(f"  Fields: difficulty_level={hasattr(CareerPathTask, 'difficulty_level')}")
    print(f"  Fields: is_completed={hasattr(CareerPathTask, 'is_completed')}")
except Exception as e:
    print(f"Step 3 FAILED: {e}")
    traceback.print_exc()

try:
    print("\nStep 4: Testing API import...")
    from app.api.students_clean import router
    print("Step 4 OK: students_clean router imported")
except Exception as e:
    print(f"Step 4 FAILED: {e}")
    traceback.print_exc()

try:
    print("\nStep 5: Testing main app import...")
    from app.main import app
    print(f"Step 5 OK: app imported, routes={len(app.routes)}")
    routes_with_career = [r for r in app.routes if hasattr(r, 'path') and 'career' in str(r.path)]
    print(f"  Career-related routes: {len(routes_with_career)}")
    for r in routes_with_career[:10]:
        print(f"    {r.methods} {r.path}")
except Exception as e:
    print(f"Step 5 FAILED: {e}")
    traceback.print_exc()

print("\n=== Import check complete ===")
