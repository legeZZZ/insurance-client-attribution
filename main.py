"""Repository-level entry point for the attribution runtime."""

from goai_control_tower.cli import main as runtime_main


def main() -> int:
    return runtime_main()


if __name__ == "__main__":
    raise SystemExit(main())
