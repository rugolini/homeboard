FROM python:3.12-alpine
RUN apk add --no-cache openssh-client tzdata && pip install --no-cache-dir pg8000==1.31.2
WORKDIR /app
COPY collector/homeboard /app/homeboard
COPY web /app/web
RUN adduser -D -u 10001 homeboard
USER homeboard
EXPOSE 8080
CMD ["python", "-m", "homeboard.main"]
