# mospi-gateway — dependency-free stdlib service; plain python base is enough.
FROM python:3.12-slim
WORKDIR /app
COPY app.py /app/app.py
ENV PORT=8107
EXPOSE 8107
CMD ["python", "app.py"]
