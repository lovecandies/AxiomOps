import httpx


def main() -> None:
    response = httpx.post(
        "http://127.0.0.1:18002/admin/faults/reset",
        timeout=5.0,
    )
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()
