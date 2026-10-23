import urllib.request
import urllib.error
import json

payload = {
    "bug_id": "B001",
    "language": "python"
}

req = urllib.request.Request(
    "http://127.0.0.1:8000/evaluation/run-paired",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "Origin": "http://localhost:5173"
    }
)

try:
    with urllib.request.urlopen(req) as resp:
        print("STATUS:", resp.status)
        print("HEADERS:", resp.headers)
        print("BODY:", resp.read().decode("utf-8")[:300])
except urllib.error.HTTPError as e:
    print("HTTP ERROR:", e.code)
    print("HEADERS:", e.headers)
    print("BODY:", e.read().decode("utf-8"))
except Exception as e:
    print("ERROR:", e)
