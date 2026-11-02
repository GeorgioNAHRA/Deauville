import argparse

from deauville.errors import FestivalError
from deauville.storage import DEFAULT_DATA, JsonStorage


def print_programme(performances: list[dict]) -> None:
    if not performances:
        print("No performances.")
    for performance in performances:
        print(
            f"{performance['start'].replace('T', ' ')} - "
            f"{performance['end'].replace('T', ' ')} | "
            f"{performance['venue_name']} | {performance['title']}"
        )
        print(f"  {performance['summary']}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Deauville Festival programme")
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="Festival JSON file")
    commands = parser.add_subparsers(dest="command")
    programme = commands.add_parser("programme", help="Show one festival day")
    programme.add_argument("day", help="YYYY-MM-DD")
    programme.add_argument("--venue", help="Venue slug")
    commands.add_parser("artists", help="List artists and their number of shows")
    now = commands.add_parser("now", help="Show current and next performances")
    now.add_argument("--at", help="YYYY-MM-DDTHH:MM, in local festival time")
    serve = commands.add_parser("serve", help="Start the website and admin")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    try:
        festival = JsonStorage(args.data).load()
        if args.command == "programme":
            print_programme(festival.programme(args.day, args.venue))
        elif args.command == "artists":
            for artist in festival.artists():
                count = len(festival.artist(artist["slug"])["performances"])
                print(f"{artist['name']}: {count} show(s)")
        elif args.command == "now":
            result = festival.now(args.at)
            print(f"On stage at {result['at']}:")
            print_programme(result["now_playing"])
            print("Up next:")
            print_programme(result["up_next"])
        elif args.command == "serve":
            import uvicorn

            from deauville.api import create_app

            uvicorn.run(create_app(args.data), host=args.host, port=args.port)
        else:
            info = festival.information()
            print(info["name"])
            print(f"{info['first_day']} to {info['last_day']}")
            print("Use --help to see the available commands.")
    except FestivalError as error:
        parser.exit(1, f"Error: {error}\n")
