import os


def makepipe(name):
    try:
        os.mkfifo(name)
    except FileExistsError:
        pass
    except OSError:
        print("Failed to create pipe")
        exit(1)
