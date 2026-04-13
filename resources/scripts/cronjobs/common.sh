#!/bin/bash

# Loop until there is an internet connection
wait_for_network() {
    local host="${1:-cern.ch}"
    local interval="${2:-5}"
    until ping -c 1 "$host" >/dev/null 2>&1; do
        sleep "$interval"
    done
}