python -m venv venv
python -m pip install -r requirements.txt

cp .env.example .env
# edit .env: set FLASK_SECRET_KEY, and STORE_API_BASE_URL if store-api isn't on
# localhost:8000 (see ../store-api - must be running, e.g. `docker compose up`)

python app.py