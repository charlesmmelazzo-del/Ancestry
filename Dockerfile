# Quesenberry & Harvey Family — single-container Flask deployment
#
#  - Builds the static site at image build time (python3 build.py → /public)
#  - Serves /public + /submit + /admin via Flask + gunicorn at runtime
#
# Submissions persist via a Railway Volume mounted at /data.

FROM python:3.12-slim

WORKDIR /app

# Install Python deps first (cached layer)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source and build the static site
COPY . .
RUN python3 build.py

# Persistent storage for submissions (mount Railway Volume here)
RUN mkdir -p /data/submissions/uploads
ENV SUBMISSIONS_DIR=/data/submissions
ENV PORT=8080
EXPOSE 8080

# Gunicorn: 2 workers, 60s timeout, bind to Railway-provided $PORT
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 60 app:app"]
