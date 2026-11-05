import uvicorn


def main() -> None:
    uvicorn.run("hue_beatsync.server.main:app", host="127.0.0.1", port=8765)


if __name__ == "__main__":
    main()
