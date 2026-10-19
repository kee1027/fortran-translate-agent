import unittest

from scripts.validate_dataset import validate_record


def valid_record() -> dict:
    return {
        "id": "f2cpp-000001",
        "source": "synthetic",
        "license": "synthetic",
        "fortran_dialect": "f90",
        "features": ["do-loop", "array"],
        "input_fortran": "program hello\nend program hello\n",
        "output_cpp": "int main() { return 0; }\n",
        "notes": "minimal sample",
        "unsupported": [],
        "compile_info": {
            "fortran": "gfortran -std=f2008 main.f90 -o main",
            "cpp": "g++ -std=c++17 main.cpp -o main",
        },
        "tests": [
            {
                "name": "basic",
                "input": "",
                "expected": "",
                "comparison": "text",
                "rel_tolerance": 1.0e-9,
                "abs_tolerance": 1.0e-12,
            }
        ],
        "validation": {
            "fortran_ok": True,
            "cpp_ok": True,
            "tests_ok": True,
            "reviewed": False,
        },
        "split": "train",
    }


class ValidateRecordTests(unittest.TestCase):
    def test_valid_record(self) -> None:
        self.assertEqual(validate_record(valid_record()), [])

    def test_missing_field(self) -> None:
        record = valid_record()
        del record["input_fortran"]
        self.assertIn("missing required field: input_fortran", validate_record(record))

    def test_invalid_split(self) -> None:
        record = valid_record()
        record["split"] = "holdout"
        self.assertTrue(any(error.startswith("split must be") for error in validate_record(record)))

    def test_tests_required_when_tests_ok(self) -> None:
        record = valid_record()
        record["tests"] = []
        errors = validate_record(record)
        self.assertIn("tests must be a non-empty list", errors)
        self.assertIn("validation.tests_ok=true requires at least one test", errors)


if __name__ == "__main__":
    unittest.main()
