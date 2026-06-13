import subprocess
import sys

COMMANDS = [
    ["python", "fetch_espn_worldcup.py"],
    ["python", "parse_espn.py"],
    ["python", "update_fifa_ratings.py"],
    ["python", "simulate_tournament.py"],
]


def run_command(command):
    print("\nRunning:", " ".join(command))
    print("-" * 80)

    result = subprocess.run(command)

    if result.returncode != 0:
        print("\nCommand failed:", " ".join(command))
        sys.exit(result.returncode)


def main():
    for command in COMMANDS:
        run_command(command)

    print("\nPipeline completed successfully.")


if __name__ == "__main__":
    main()