# src/backend/Dockerfile
FROM python:3.11-slim

# Install system packages (LaTeX, tesseract, poppler etc. — adjust as needed)
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential \
      wget \
      fontconfig \
      fonts-dejavu-core \
      poppler-utils \
      tesseract-ocr \
      libleptonica-dev \
      texlive-xetex \
      texlive-latex-recommended \
      texlive-latex-extra \
      texlive-fonts-recommended \
      texlive-fonts-extra \
      texlive-lang-all \
      ghostscript \
      texlive-plain-generic \
      lmodern \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy requirements (now in src/backend)
COPY requirements.txt /app/requirements.txt

# install python deps
RUN pip install --no-cache-dir -r /app/requirements.txt

# copy backend app (everything inside src/backend will be included since context is src/backend)
COPY . /app

# ensure exports dir exists
RUN mkdir -p /app/data/exports

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
    