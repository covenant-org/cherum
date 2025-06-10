import os
from time import sleep
import requests
import argparse
from utils import makepipe


def poll(url, token, on_error="loiter"):
    try:
        return requests.get(
            f"{url}/fetch",
            headers={"Authorization": "Bearer " + token}
        ).json()
    except requests.exceptions.ConnectionError:
        print("Connection error")
        return {"done": False, "command": on_error}


def mark_done(url, token, id):
    return requests.post(
        f"{url}/done/{id}",
        headers={"Authorization": "Bearer " + token}
    ).json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--url", default="http://localhost:5000")
    parser.add_argument("-p", "--pipe", default="./comms.pipe")
    parser.add_argument("-e", "--on_error", default="loiter")
    args = parser.parse_args()
    print(f"Polling {args.url}")
    token = os.environ.get("TOKEN")
    makepipe(args.pipe)
    while True:
        sleep(0.2)
        res = poll(args.url, token, args.on_error)
        print(res)
        if res["done"]:
            continue
        with open(args.pipe, 'w') as f:
            if res["command"] == "land":
                f.write("l")
            elif res["command"] == "loiter":
                f.write("h")
            elif res["command"] == "rtl":
                f.write("r")
        if "id" in res and res["id"] is not None:
            mark_done(args.url, token, res["id"])


if __name__ == "__main__":
    main()
