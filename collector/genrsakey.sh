#!/bin/bash

# Example usage: sh genrsakey.sh 2048
KEY_SIZE="${1:-2048}"

openssl genrsa -out private_key.pem "$KEY_SIZE"
openssl rsa -in private_key.pem -pubout -out public_key.pem
