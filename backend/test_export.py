import requests
import sys

def test_export():
    print("Fetching projects...")
    try:
        res = requests.get("http://localhost:8000/api/v1/projects/")
        if res.status_code == 200:
            projects = res.json()
            if not projects:
                print("No projects found.")
                return
            
            project_id = projects[0]["id"]
            print(f"Testing export for project {project_id}")
            
            export_url = f"http://localhost:8000/api/v1/projects/{project_id}/projections/export"
            print(f"GET {export_url}")
            
            export_res = requests.get(export_url)
            print(f"Status: {export_res.status_code}")
            
            if export_res.status_code != 200:
                print(f"Error Response:\n{export_res.text}")
            else:
                print(f"Success! Content length: {len(export_res.content)} bytes")
        else:
            print(f"Failed to fetch projects: {res.status_code}\n{res.text}")
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    test_export()
