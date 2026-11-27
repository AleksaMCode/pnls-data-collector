"""The throwaway RSA key pair the tests use in place of the services' key files."""

from functools import cache


@cache
def test_rsa_key():
    """Generated once per test run and never committed. The collector encrypts with its public
    part and the aggregator decrypts with the private part, as with the real key files.
    """
    from Crypto.PublicKey import RSA

    return RSA.generate(2048)
