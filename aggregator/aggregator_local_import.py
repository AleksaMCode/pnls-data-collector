import argparse

from aggregator.core.orm.helpers import import_data_local


def parse_args():
    parser = argparse.ArgumentParser(
        description="Import local device data from a a JSON file."
    )

    parser.add_argument(
        "-f", "--file", type=str, required=True, help="The JSON file to process."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    import_data_local(args.file)
