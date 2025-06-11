import os
import requests
import argparse
from time import sleep


def send_msg(url, msg="", token=""):
    try:
        return requests.post(f"{url}/telemetry", headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json"
        }, data=msg)
    except Exception as e:
        print(e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--pipe", default="./tele.pipe")
    parser.add_argument("-u", "--url", default="http://localhost:5000")
    args = parser.parse_args()

    token = os.environ.get("TOKEN")
    while True:
        with open(args.pipe, "r") as f:
            try:
                i = 0
                while i < 100:
                    line = f.readline(2048)
                    i += 1
                    if line:
                        send_msg(args.url, line, token)
            except Exception as e:
                print(e)


if __name__ == "__main__":
    main()
