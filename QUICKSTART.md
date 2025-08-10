# Quickstart for UME

This quickstart shows how to run a simple producer and consumer locally.

## Prerequisites

- Python 3.10+
- Docker (optional for Redpanda)

## Steps

1. Clone the repository and navigate into it:
   ```
   git clone https://github.com/d0tTino/UME.git
   cd UME
   ```

2. Create a virtual environment and install dependencies:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

3. Run Redpanda in Docker (or use another Kafka-compatible broker):
   ```
   docker run -d -p 9092:9092 -p 9644:9644 --name redpanda docker.redpanda.com/vectorized/redpanda:latest redpanda start
   ```

4. Start a sample producer:
   ```
   python examples/producer.py --topic test --message "hello world"
   ```

5. In another terminal, start a sample consumer:
   ```
   python examples/consumer.py --topic test
   ```

You should see the message appear in the consumer's output, which verifies the basic data flow.
