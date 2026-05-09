"""NLP Processor — primary entry point."""
from src.handler import Handler


def main():
    handler = Handler()
    handler.start()


if __name__ == "__main__":
    main()
