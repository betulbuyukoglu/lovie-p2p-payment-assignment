import argparse

from core.db import SessionLocal
from services.request_service import expire_due_requests


def run_once() -> int:
    session = SessionLocal()
    try:
        n = expire_due_requests(session)
        session.commit()
        return n
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def loop_main(interval_sec: int) -> None:
    import time

    while True:
        run_once()
        time.sleep(interval_sec)


def main() -> None:
    parser = argparse.ArgumentParser(description="Süresi dolan talepleri EXPIRED yapar.")
    parser.add_argument("--loop", action="store_true", help="Periyodik çalıştır")
    parser.add_argument("--interval", type=int, default=60, help="Saniye (varsayılan 60)")
    args = parser.parse_args()
    if args.loop:
        loop_main(args.interval)
    else:
        n = run_once()
        print(f"Güncellenen talep sayısı: {n}")


if __name__ == "__main__":
    main()
