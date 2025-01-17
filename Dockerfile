FROM python:3.10

# set the working directory
WORKDIR /app

# install dependencies
COPY ./requirements.txt /app
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# copy the scripts to the folder
COPY . /app

ENV TIMESCALEDB_PROVIDER="postgres"

ENV TIMESCALEDB_USER="postgres"

ENV TIMESCALEDB_PASSWORD="password"

ENV TIMESCALEDB_HOST="172.17.0.1"

ENV TIMESCALEDB_DATABASE="postgres"

ENV LOGGER_CONFIGURATION_FILE="./configs/log.json"

ENV SECRET_KEY="09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"

ENV MONGODB_USER=""

ENV MONGODB_PASSWORD=""

ENV MONGODB_HOST="localhost"

# start the server
CMD ["uvicorn", "main:APP", "--host", "0.0.0.0", "--port", "8888"]