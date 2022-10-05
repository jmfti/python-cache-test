FROM python:3.10

RUN apt-get update && apt-get install git -y && mkdir -p /app

WORKDIR /app

ENV PYTHONPATH=/app

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

# RUN git clone https://source/repository.git .

# RUN pip install -r requirements.txt
