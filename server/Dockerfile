FROM python:3.10-bookworm 

RUN pip install waitress

WORKDIR /app
COPY . .
RUN pip install -e .
RUN flask --app cherum db:create

CMD ["waitress-serve", "--port=80", "--call", "cherum:create_app"]

