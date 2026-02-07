import argparse
import json

from yaspin import yaspin


def parse_args():
    parser = argparse.ArgumentParser(
        description="Search for a specific date in the timestamp field of a JSON file."
    )
    parser.add_argument(
        "-d",
        "--date",
        type=str,
        required=True,
        help="The date to search for in the format YYYY-MM-DD.",
    )
    parser.add_argument(
        "-f", "--file", type=str, required=True, help="The JSON file to process."
    )
    return parser.parse_args()


@yaspin(text="Counting number of data for specific date")
def data_counter():
    args = parse_args()
    search_date = args.date
    file_name = args.file

    count = 0

    with open(file_name, "r") as file:
        for line in file:
            data = json.loads(line.strip())
            timestamp = data.get("timestamp")

            if timestamp and timestamp[:10] == search_date:
                count += 1

    print(f"Number of matching timestamps: {count}")


if __name__ == "__main__":
    # This is used to get a count of data that will be imported.
    data_counter()
