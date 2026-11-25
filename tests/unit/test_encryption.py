import unittest

from Crypto.PublicKey import RSA

from util.util import base64_decode, base64_encode, decrypt_data, encrypt_data


class TestRSAEncryption(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.private_key = RSA.generate(2_048)
        cls.public_key = cls.private_key.publickey()

    def test_encryption(self):
        original_data = "This is a secret message."

        encrypted_data = encrypt_data(self.public_key, original_data)
        decrypted_data = decrypt_data(self.private_key, encrypted_data)

        self.assertEqual(decrypted_data, original_data)

    def test_base64_encoding_binary(self):
        data = b"Some binary data to encode"

        encoded_data = base64_encode(data)
        decoded_data = base64_decode(encoded_data)

        self.assertEqual(decoded_data, data)

    def test_base64_encoding_string(self):
        original_data = "Hello, World!"

        byte_data = original_data.encode("utf-8")
        encoded_data = base64_encode(byte_data)
        decoded_data = base64_decode(encoded_data)

        self.assertEqual(decoded_data, byte_data)


if __name__ == "__main__":
    unittest.main()
