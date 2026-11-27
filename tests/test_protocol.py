import unittest

from host.pc_keyboard.codec import (
    decode_rx_u64,
    encode_tx_u64,
    parse_rabbit_read_line,
    u64_from_4xu16,
    u64_to_4xu16,
    u64_to_rabbit_binary_line,
)


class ProtocolTests(unittest.TestCase):
    def test_encode_tx_places_command_fields_in_vericomm_bits(self) -> None:
        self.assertEqual(encode_tx_u64(key_id=10, key_on=1, cmd_strobe=1), 117)

    def test_decode_rx_recovers_led_frequency_and_timestamp(self) -> None:
        rx_word = 0b100001 | (440 << 12) | (0x1234 << 28)

        decoded = decode_rx_u64(rx_word)

        self.assertEqual(decoded["led"], [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0])
        self.assertEqual(decoded["freq_hz"], 440)
        self.assertEqual(decoded["last_event_ts"], 0x1234)

    def test_u64_round_trips_through_four_little_endian_u16_words(self) -> None:
        value = 0x0123456789ABCDEF

        words = u64_to_4xu16(value)

        self.assertEqual(words, [0xCDEF, 0x89AB, 0x4567, 0x0123])
        self.assertEqual(u64_from_4xu16(words), value)

    def test_rabbit_binary_line_is_64_bits_and_round_trips(self) -> None:
        value = 0xA5A5

        line = u64_to_rabbit_binary_line(value)

        self.assertEqual(len(line), 64)
        self.assertTrue(line.endswith("1010010110100101"))
        self.assertEqual(parse_rabbit_read_line(line), value)

    def test_rabbit_parser_rejects_non_64_bit_lines(self) -> None:
        with self.assertRaisesRegex(ValueError, "expect 64 binary chars"):
            parse_rabbit_read_line("1010")


if __name__ == "__main__":
    unittest.main()
