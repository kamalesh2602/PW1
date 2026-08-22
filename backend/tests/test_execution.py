import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_python_successful_execution():
    payload = {
        "language": "python",
        "code": "def main():\n    print('Hello Python Test')\n\nmain()"
    }
    response = client.post("/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["language"] == "python"
    assert "Hello Python Test" in data["stdout"]
    assert data["exit_code"] == 0
    assert data["execution_time"] >= 0.0


def test_python_runtime_error():
    payload = {
        "language": "python",
        "code": "print(1 / 0)"
    }
    response = client.post("/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "runtime_error"
    assert data["language"] == "python"
    assert "ZeroDivisionError" in data["stderr"]
    assert data["exit_code"] != 0


def test_python_syntax_error():
    payload = {
        "language": "python",
        "code": "def foo("
    }
    response = client.post("/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "runtime_error"
    assert "SyntaxError" in data["stderr"]


def test_java_successful_execution():
    payload = {
        "language": "java",
        "code": "public class Main { public static void main(String[] args) { System.out.println(\"Hello Java Test\"); } }"
    }
    response = client.post("/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["language"] == "java"
    assert "Hello Java Test" in data["stdout"]
    assert data["exit_code"] == 0


def test_java_compilation_error():
    payload = {
        "language": "java",
        "code": "public class Main { public static void main(String[] args) { System.out.println(\"Missing Semicolon\") } }"
    }
    response = client.post("/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "compile_error"
    assert data["language"] == "java"
    assert "error:" in data["stderr"].lower() or "javac" in data["stderr"].lower()


def test_python_timeout():
    payload = {
        "language": "python",
        "code": "import time\ntime.sleep(10)"
    }
    response = client.post("/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "timeout"
    assert "exceeded" in data["stderr"].lower()


def test_invalid_language():
    payload = {
        "language": "cpp",
        "code": "int main() { return 0; }"
    }
    response = client.post("/execute", json=payload)
    assert response.status_code == 422 # Pydantic validation error for invalid enum
