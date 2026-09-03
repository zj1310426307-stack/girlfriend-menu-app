FROM python:3.12.11-slim-bookworm

# Keep the container deterministic and let CloudBase override PORT when its
# runtime provides a different service port.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=80

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY . ./

EXPOSE 80

# serve.py performs the same migration/reference-data fast path used by the
# proven Render Free deployment before starting Uvicorn.
CMD ["python", "serve.py"]
