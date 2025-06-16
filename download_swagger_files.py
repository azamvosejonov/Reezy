import os
import requests

def download_file(url, path):
    response = requests.get(url)
    response.raise_for_status()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(response.content)

# Download Swagger UI files
swagger_ui_version = "4.15.5"
swagger_files = [
    (f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{swagger_ui_version}/swagger-ui-bundle.js", "static/swagger-ui-bundle.js"),
    (f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{swagger_ui_version}/swagger-ui.css", "static/swagger-ui.css"),
    (f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{swagger_ui_version}/swagger-ui-standalone-preset.js", "static/swagger-ui-standalone-preset.js"),
    (f"https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js", "static/redoc.standalone.js")
]

print("Downloading Swagger UI files...")
for url, path in swagger_files:
    print(f"Downloading {url} to {path}")
    download_file(url, path)

print("\nAll files downloaded successfully!")
print("You can now access the Swagger UI at: http://localhost:8000/docs")
print("And the ReDoc at: http://localhost:8000/redoc")
