FROM python:3.10-bookworm 

RUN pip install waitress

WORKDIR /app
COPY . .
RUN pip install -e .
RUN python -c "import secrets; print(secrets.token_hex())" > config.py
RUN flask --app cherum db:create

CMD ["waitress-serve", "--port=80", "--call", "cherum:create_app"]

