# ==========================================
# STAGE 1: Builder (Compile dependencies)
# ==========================================
FROM python:3.11-slim AS builder

# Αποτροπή δημιουργίας .pyc αρχείων και buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Εγκατάσταση C++ compiler και εργαλείων
RUN apt-get update && apt-get install -y --no-install-recommends \
    g++ \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Δημιουργία Python Wheels για βέλτιστο caching
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# ==========================================
# STAGE 2: Production (Lean & Secure)
# ==========================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Εγκατάσταση ΜΟΝΟ των απαραίτητων runtime βιβλιοθηκών για τη C++ (OpenMP)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Security: Δημιουργία Non-Root χρήστη
RUN addgroup --system hevgroup && adduser --system --group hevuser

WORKDIR /app

# Εγκατάσταση των dependencies από το builder stage
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Αντιγραφή όλου του κώδικα
COPY . .

# Ασφαλές, in-container compilation της C++ για απόλυτη συμβατότητα OS/GLIBC
RUN g++ -shared -fPIC -o testing/unit/physics.so cpp_core/physics_solver.cpp -fopenmp && \
    g++ -shared -fPIC -o cpp_core/cpp_firewall/firewall.so cpp_core/cpp_firewall/firewall.cpp

# Αλλαγή δικαιωμάτων στον ασφαλή χρήστη
RUN chown -R hevuser:hevgroup /app

# Υποβιβασμός δικαιωμάτων - Τρέχουμε πλέον ως hevuser
USER hevuser

# Έκθεση της πόρτας του API
EXPOSE 8000

# Εκκίνηση του Enterprise Backend (API Server)
CMD ["python", "api_server.py"]