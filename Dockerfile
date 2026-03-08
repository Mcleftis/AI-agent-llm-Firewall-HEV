
FROM python:3.9-slim


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app



RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*


RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable




COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .


EXPOSE 8501


CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]

# Χρησιμοποιούμε Python 3.10
FROM python:3.10-slim

# Εγκατάσταση απαραίτητων εργαλείων για το compile της C++
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Αντιγραφή των αρχείων
COPY . .

# Compile της C++ σε Shared Object (.so) για Linux
RUN g++ -O3 -shared -fPIC -o cpp_firewall/firewall.so cpp_firewall/firewall.cpp

# Εγκατάσταση Python requirements
RUN pip install --no-cache-dir -r requirements.txt

# Άνοιγμα του Port 8000
EXPOSE 8000

# Εκκίνηση του Server
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]