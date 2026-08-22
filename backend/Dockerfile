FROM eclipse-temurin:17-jdk-alpine

RUN apk add --no-cache python3 py3-pip

RUN java -version && javac -version && python3 --version

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]