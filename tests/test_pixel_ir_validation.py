from __future__ import annotations

from copy import deepcopy
import unittest

from tracepixel.model import (
    PIXEL_PROGRAM_SCHEMA_V1,
    PixelProgramValidationError,
    validate_pixel_program,
)


def valid_program() -> dict[str, object]:
    return {
        "schema": PIXEL_PROGRAM_SCHEMA_V1,
        "canvas": {"width": 2, "height": 2},
        "operations": [
            {
                "op": "set_pixels",
                "pixels": [
                    [0, 0, 1, 2, 3, 4],
                    [1, 1, 255, 254, 253, 252],
                    [0, 0, 5, 6, 7, 8],
                ],
            }
        ],
    }


class PixelIrValidationTests(unittest.TestCase):
    def assert_rejected(
        self,
        program: object,
        code: str,
        path: str,
    ) -> PixelProgramValidationError:
        with self.assertRaises(PixelProgramValidationError) as caught:
            validate_pixel_program(program)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.path, path)
        return caught.exception

    def test_valid_program_is_accepted_without_copying_or_reordering(self) -> None:
        program = valid_program()
        before = deepcopy(program)

        validated = validate_pixel_program(program)

        self.assertIs(validated, program)
        self.assertEqual(program, before)
        pixels = program["operations"][0]["pixels"]  # type: ignore[index]
        self.assertEqual(pixels[0], [0, 0, 1, 2, 3, 4])
        self.assertEqual(pixels[2], [0, 0, 5, 6, 7, 8])

    def test_closed_structure_and_supported_discriminators_are_enforced(self) -> None:
        missing = valid_program()
        del missing["operations"]
        self.assert_rejected(missing, "invalid_fields", "$")

        extra = valid_program()
        extra["metadata"] = {}
        self.assert_rejected(extra, "invalid_fields", "$")

        wrong_schema = valid_program()
        wrong_schema["schema"] = "tracepixel.pixel-program.v2"
        self.assert_rejected(wrong_schema, "unsupported_schema", "$.schema")

        wrong_op = valid_program()
        wrong_op["operations"][0]["op"] = "fill"  # type: ignore[index]
        self.assert_rejected(
            wrong_op,
            "unsupported_operation",
            "$.operations[0].op",
        )

    def test_canvas_semantics_reuse_p1_exact_integer_and_size_contract(self) -> None:
        for width in (True, 0, 4097):
            program = valid_program()
            program["canvas"]["width"] = width  # type: ignore[index]
            self.assert_rejected(program, "invalid_canvas", "$.canvas")

    def test_pixel_shape_coordinate_and_rgba_ranges_are_rejected(self) -> None:
        malformed = valid_program()
        malformed["operations"][0]["pixels"][0] = [0, 0, 1, 2, 3]  # type: ignore[index]
        self.assert_rejected(
            malformed,
            "invalid_edit",
            "$.operations[0].pixels[0]",
        )

        for coordinate in (True, -1, 2):
            program = valid_program()
            program["operations"][0]["pixels"][0][0] = coordinate  # type: ignore[index]
            self.assert_rejected(
                program,
                "invalid_coordinate",
                "$.operations[0].pixels[0]",
            )

        for channel in (True, -1, 256):
            program = valid_program()
            program["operations"][0]["pixels"][0][2] = channel  # type: ignore[index]
            self.assert_rejected(
                program,
                "invalid_color",
                "$.operations[0].pixels[0]",
            )

    def test_json_object_and_array_types_are_exact(self) -> None:
        tuple_edit = valid_program()
        tuple_edit["operations"][0]["pixels"][0] = (0, 0, 1, 2, 3, 4)  # type: ignore[index]
        self.assert_rejected(
            tuple_edit,
            "invalid_type",
            "$.operations[0].pixels[0]",
        )

        tuple_operations = valid_program()
        tuple_operations["operations"] = tuple(tuple_operations["operations"])  # type: ignore[arg-type]
        self.assert_rejected(tuple_operations, "invalid_type", "$.operations")

    def test_rejection_is_side_effect_free_for_input(self) -> None:
        program = valid_program()
        program["operations"][0]["pixels"][1][2] = 999  # type: ignore[index]
        before = deepcopy(program)

        self.assert_rejected(
            program,
            "invalid_color",
            "$.operations[0].pixels[1]",
        )
        self.assertEqual(program, before)


if __name__ == "__main__":
    unittest.main()
