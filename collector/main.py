import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="PNLS collector service")
    parser.add_argument(
        "-i",
        "--interface",
        default=None,
        help="Base wireless interface name (e.g. wlan1) that will be used to perform monitoring.",
    )
    parser.add_argument(
        "--channel-hopping",
        dest="channel_hopping",
        action="store_true",
        default=False,
        help="Enable channel hopping (disabled by default).",
    )
    return parser.parse_args()


def main():
    from collector.sniffer import start

    args = parse_args()
    start(interface=args.interface, channel_hopping=args.channel_hopping)


if __name__ == "__main__":
    main()
