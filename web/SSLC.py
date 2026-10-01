"""SSLC 실행 진입점: 로컬 실행과 Gunicorn의 SSLC:app에서 사용."""
import sys

from app import create_app
from app.db import seed_data

app = create_app()

if __name__ == "__main__":
    if "--init-db" in sys.argv:
        with app.app_context():
            seed_data()
        print("Initialized demo accounts and notices.")
    else:
        app.run(host="127.0.0.1", port=8000, debug=False)
