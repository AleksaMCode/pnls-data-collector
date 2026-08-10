#!/bin/bash

sudo airmon-ng start wlan1
sudo python3 -m collector.main
