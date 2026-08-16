from __future__ import annotations

import unittest

import tracepixel.agent.codex_cli as codex_cli


class CodexOutputSchemaTests(unittest.TestCase):
    def test_const_string_fields_declare_explicit_types(self) -> None:
        schema = codex_cli._CODEX_OUTPUT_SCHEMA
        root_properties = schema["properties"]
        payload = root_properties["payload"]
        payload_properties = payload["properties"]
        operation = payload_properties["operations"]["items"]

        self.assertEqual(root_properties["schema"]["type"], "string")
        self.assertEqual(root_properties["kind"]["type"], "string")
        self.assertEqual(payload_properties["schema"]["type"], "string")
        self.assertEqual(operation["properties"]["op"]["type"], "string")

    def test_all_schema_objects_remain_closed_and_required(self) -> None:
        schema = codex_cli._CODEX_OUTPUT_SCHEMA
        payload = schema["properties"]["payload"]
        canvas = payload["properties"]["canvas"]
        operation = payload["properties"]["operations"]["items"]

        for value in (schema, payload, canvas, operation):
            self.assertFalse(value["additionalProperties"])
            self.assertEqual(set(value["required"]), set(value["properties"]))


if __name__ == "__main__":
    unittest.main()
