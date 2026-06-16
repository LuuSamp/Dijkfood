FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app \
    STREAMLIT_SERVER_PORT=8000 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_CORS=false \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false \
    STREAMLIT_SERVER_BASE_URL_PATH=dashboard

COPY dashboard/requirements.txt ./dashboard/requirements.txt
RUN pip install --no-cache-dir -r dashboard/requirements.txt

COPY dashboard/app.py ./dashboard/app.py
COPY dashboard/.streamlit ./dashboard/.streamlit
COPY ml/__init__.py ./ml/__init__.py
COPY ml/batch_output.py ./ml/batch_output.py

WORKDIR /app/dashboard
EXPOSE 8000

CMD ["streamlit", "run", "app.py"]
