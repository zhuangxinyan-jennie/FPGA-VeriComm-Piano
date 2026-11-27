import unittest

from host.pc_keyboard.fifo_sequence import (
    strobe_command_tx_u64_list,
    strobe_command_tx_words,
)


class FifoSequenceTests(unittest.TestCase):
    def test_command_holds_data_stable_around_single_strobe_pulse(self) -> None:
        sequence = strobe_command_tx_u64_list(key_id=2, key_on=1)

        self.assertEqual(sequence, [37, 37, 37, 101, 37])

    def test_word_sequence_preserves_each_64_bit_transaction_step(self) -> None:
        word_sequence = strobe_command_tx_words(key_id=2, key_on=1)

        self.assertEqual(
            word_sequence,
            [
                [37, 0, 0, 0],
                [37, 0, 0, 0],
                [37, 0, 0, 0],
                [101, 0, 0, 0],
                [37, 0, 0, 0],
            ],
        )


if __name__ == "__main__":
    unittest.main()
