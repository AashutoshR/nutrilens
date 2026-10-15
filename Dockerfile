# NutriLens for hosting (Render, Fly, any Docker host).
# Photo recognition uses Google Gemini (set GEMINI_API_KEY); nutrition and recipes come from the bundled lite data.

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/data-lite ./data-lite
RUN mkdir -p data \
 && gunzip -c data-lite/foods.db.gz > data/foods.db \
 && gunzip -c data-lite/recipes.db.gz > data/recipes.db \
 && rm -rf data-lite
COPY --from=web /web/dist /app/frontend/dist

# Hosted mode: private data per visitor, admin settings off, Gemini for photos.
ENV NUTRILENS_PUBLIC=1 \
    NUTRILENS_PROVIDER=gemini \
    NUTRILENS_DB=/app/backend/nutrilens.db
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
