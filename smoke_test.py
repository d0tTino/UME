import subprocess
import sys
import time
import os

"""
A minimal smoke test for UME.

This script launches a local Redpanda broker (via Docker), then runs a producer and
consumer from the examples directory. It checks that a test message is received.

Note: This is a simple demonstration and may need adjustments based on the actual
structure of the examples in the UME repository.
"""


def run_command(cmd, cwd=None, timeout=30):
    """Run a subprocess command and return its output."""
    process = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        out, err = process.communicate()
    return out.decode(), err.decode()


def main():
    # Start Redpanda broker
    broker = subprocess.Popen([
        "docker", "run", "--rm", "-p", "9092:9092", "-p", "9644:9644",
        "docker.redpanda.com/vectorized/redpanda:latest", "redpanda", "start"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Give the broker time to start
    time.sleep(8)

    # Run a producer
    prod_cmd = [sys.executable, "examples/producer.py", "--topic", "smoke", "--message", "hello"]
    consumer_cmd = [sys.executable, "examples/consumer.py", "--topic", "smoke"]

    # Start consumer first to capture messages
    consumer = subprocess.Popen(consumer_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Give consumer time to connect
    time.sleep(1)
    # Run producer
    prod_out, prod_err = run_command(prod_cmd)
    # Wait a bit for consumer to receive message
    time.sleep(5)
    # Read consumer output
    cons_out, cons_err = consumer.communicate(timeout=10)

    # Stop the broker
    broker.terminate()

    if "hello" in cons_out.decode():
        print("smoke test passed")
    else:
        print("smoke test failed")
        print("Producer output:\n", prod_out)
        print("Producer error:\n", prod_err)
        print("Consumer output:\n", cons_out.decode())
        print("Consumer error:\n", cons_err.decode())


if __name__ == "__main__":
    main()
