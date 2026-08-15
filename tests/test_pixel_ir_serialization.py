from __future__ import annotations

from copy import deepcopy
import unittest

from tracepixel.model import (
    PIXEL_PROGRAM_SCHEMA_V1,
    PixelProgramSerializationError,
    PixelProgramValidationError,
    deserialize_pixel_program,
    execute_pixel_program,
    serialize_pixel_program,
)


def program_with_scrambled_keys() -> dict[str, object]:
    return {
        "operations": [
            {
                "pixels": [
                    [0, 0, 1, 2, 3, 4],
                    [1, 0, 9, 8, 7, 6],
                    [0, 0, 5, 6, 7, 8],
                ],
                "op": "set_pixels",
            },
            {
                "pixels": [
                    [1, 1, 20, 21, 22, 23],
                    [1, 0, 10, 11, 12, 13],
                ],
                "op": "set_pixels",
            },
        ],
        "canvas": {"height": 2, "width": 2},
        "schema": PIXEL_PROGRAM_SCHEMA_V1,
    }


class PixelIrSerializationTests(unittest.TestCase):
    def test_canonical_bytes_are_compact_sorted_utf8_and_do_not_mutate_input(self) -> None:
        program = program_with_scrambled_keys()
        before = deepcopy(program)

        payload = serialize_pixel_program(program)

        self.assertEqual(
            payload,
            b'{"canvas":{"height":2,"width":2},"operations":[{"op":"set_pixels","pixels":[[0,0,1,2,3,4],[1,0,9,8,7,6],[0,0,5,6,7,8]]},{"op":"set_pixels","pixels":[[1,1,20,21,22,23],[1,0,10,11,12,13]]}],"schema":"tracepixel.pixel-program.v1"}',
        )
        self.assertEqual(program, before)
        self.assertNotIn(b" ", payload)
        self.assertFalse(payload.endswith(b"\n"))

    def test_object_insertion_order_does_not_change_canonical_bytes(self) -> None:
        first = program_with_scrambled_keys()
        second = {
            "schema": first["schema"],
            "canvas": {"width": 2, "height": 2},
            "operations": [
                {"op": operation["op"], "pixels": deepcopy(operation["pixels"])}
                for operation in first["operations"]  # type: ignore[union-attr]
            ],
        }

        self.assertEqual(
            serialize_pixel_program(first),
            serialize_pixel_program(second),
        )

    def test_round_trip_is_canonical_and_replay_equivalent(self) -> None:
        program = program_with_scrambled_keys()
        payload = serialize_pixel_program(program)

        decoded = deserialize_pixel_program(payload)

        self.assertEqual(serialize_pixel_program(decoded), payload)
        self.assertEqual(
            execute_pixel_program(decoded).rgba_bytes(),
            execute_pixel_program(program).rgba_bytes(),
        )
        self.assertEqual(execute_pixel_program(decoded).get_pixel(0, 0), (5, 6, 7, 8))

    def test_decoder_accepts_noncanonical_json_but_reserializes_canonically(self) -> None:
        payload = (
            b'{"schema":"tracepixel.pixel-program.v1", '
            b'"canvas":{"width":1,"height":1}, "operations":[]}'
        )

        decoded = deserialize_pixel_program(payload)

        self.assertEqual(
            serialize_pixel_program(decoded),
            b'{"canvas":{"height":1,"width":1},"operations":[],"schema":"tracepixel.pixel-program.v1"}',
        )

    def test_invalid_wire_data_has_stable_serialization_errors(self) -> None:
        cases = (
            (bytearray(b"{}"), "invalid_type"),
            (b"{", "invalid_json"),
            (b"\xff", "invalid_json"),
        )
        for payload, code in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(PixelProgramSerializationError) as caught:
                    deserialize_pixel_program(payload)
                self.assertEqual(caught.exception.code, code)

    def test_semantically_invalid_decoded_program_uses_validation_error(self) -> None:
        with self.assertRaises(PixelProgramValidationError) as caught:
            deserialize_pixel_program(
                b'{"canvas":{"height":1,"width":1},"operations":[],"schema":"other"}'
            )

        self.assertEqual(caught.exception.code, "unsupported_schema")

    def test_serializer_validates_before_emitting_bytes(self) -> None:
        program = program_with_scrambled_keys()
        program["operations"][0]["pixels"][0][2] = 256  # type: ignore[index]

        with self.assertRaises(PixelProgramValidationError):
            serialize_pixel_program(program)


if __name__ == "__main__":
    unittest.main()
