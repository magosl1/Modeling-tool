import sys
from app.db.base import SessionLocal
from app.models.project import Project
from app.api.routes.projections import export_projections

def test_internal_export():
    db = SessionLocal()
    try:
        project = db.query(Project).first()
        if not project:
            print("No project found.")
            return

        print(f"Testing export for internal project {project.id}")
        
        # We need a mock user that matches the project user_id
        class MockUser:
            def __init__(self, uid):
                self.id = uid
        
        mock_user = MockUser(project.user_id)
        
        try:
            res = export_projections(project_id=project.id, db=db, current_user=mock_user)
            print("Export returned successfully.")
            import os
            # Save it temporarily
            with open("test_export.xlsx", "wb") as f:
                f.write(res.body)
            print(f"Saved to test_export.xlsx, size: {os.path.getsize('test_export.xlsx')} bytes")
        except Exception as e:
            import traceback
            traceback.print_exc()

    finally:
        db.close()

if __name__ == "__main__":
    test_internal_export()
