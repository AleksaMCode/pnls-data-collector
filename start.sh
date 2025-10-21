#!/bin/bash

sudo airmon-ng start wlan1
# Should be abs path
sudo python3 sniffer.py