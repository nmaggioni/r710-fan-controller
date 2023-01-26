FROM python:3.11-bullseye

ENV PYTHONUNBUFFERED=1

RUN mkdir /root/.ssh && echo "Host *\n  StrictHostKeyChecking accept-new" > /root/.ssh/config

RUN apt-get update \
    && apt-get install -y \
        build-essential \
        libsensors4-dev \
        ipmitool \
        openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "./fan_control.py"]
