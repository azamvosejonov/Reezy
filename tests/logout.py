import unittest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from routers.accounts import router

# Create a FastAPI app and include the router for testing
app = FastAPI()
app.include_router(router)

# Table-Driven Test Cases
test_cases = [
    {
        "name": "Successful logout",
        "expected_status_code": 200,
        "expected_response": {"message": "Logout successful"}
    }
]

class TestLogoutEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_logout(self):
        for case in test_cases:
            with self.subTest(case["name"]):
                response = self.client.post("/logout")
                self.assertEqual(response.status_code, case["expected_status_code"])
                self.assertEqual(response.json(), case["expected_response"])

if __name__ == "__main__":
    unittest.main()