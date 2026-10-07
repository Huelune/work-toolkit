import argparse
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import func_diff as fdf  # noqa: E402


def names(src):
    return fdf.find_functions(src.splitlines())


class ScannerTest(unittest.TestCase):
    def test_plain_and_static(self):
        src = "int g;\n\nint add(int a, int b)\n{\n  return a + b;\n}\nstatic void helper(void) { }\n"
        self.assertEqual(names(src), [("add", 3, 6), ("helper", 7, 7)])

    def test_simulink_style(self):
        src = ("/* Model step function */\n"
               "void Model_step(void)\n"
               "{\n"
               "  if (x) {\n"
               "    y = 1;\n"
               "  }\n"
               "}\n")
        self.assertEqual(names(src), [("Model_step", 2, 7)])

    def test_macro_and_extension_signatures(self):
        src = ("FUNC(void, RTE_CODE) Rte_Foo(void)\n{\n}\n"
               "__interrupt void ISR_Timer(void) {\n}\n")
        self.assertEqual(names(src), [("Rte_Foo", 1, 3), ("ISR_Timer", 4, 5)])

    def test_ifdef_split_signature(self):
        src = "#ifdef A\nvoid f(int a)\n#else\nvoid f(void)\n#endif\n{\n}\n"
        self.assertEqual(names(src), [("f", 2, 7)])

    def test_truncated_literal_at_eof(self):
        self.assertEqual(fdf.mask_c("x = '\\"), "x =   ")
        self.assertEqual(fdf.mask_c('x = "\\'), "x =   ")
        self.assertEqual(names("void f(void)\n{\n}\nx = '\\"), [("f", 1, 3)])

    def test_not_functions(self):
        src = ("void proto(void);\n"
               "void (*fp)(int);\n"
               "int arr[] = { 1, 2 };\n"
               "struct S { int a; } s = { 0 };\n"
               "typedef struct { int b; } T;\n"
               "struct P __attribute__((packed)) { int c; };\n"
               "enum E { A, B };\n")
        self.assertEqual(names(src), [])

    def test_braces_in_comments_strings_and_macros(self):
        src = ('#define BLOCK() do { \\\n'
               '    x(); } while (0)\n'
               'void f(int a /* { */)\n'
               '{\n'
               '  const char *s = "}\\"{";\n'
               "  char c = '}';\n"
               '  // }\n'
               '}\n')
        self.assertEqual(names(src), [("f", 3, 8)])

    def test_unbalanced_returns_none(self):
        self.assertIsNone(names("#ifdef A\nvoid f(int a) {\n#else\nvoid f(void) {\n#endif\n}\n"))
        self.assertIsNone(names("void f(void) {\n}\n}\n"))

    def test_split_units(self):
        src = "int g;\nvoid f(void) {\n}\n#if A\nvoid f(void) {\n}\n#endif\n"
        u = fdf.split_units(src.splitlines())
        self.assertEqual(list(u), [fdf.FUNC_OUTSIDE, "f", "f#2"])
        self.assertEqual(u[fdf.FUNC_OUTSIDE], [1, 4, 7])
        self.assertEqual(u["f"], [2, 3])
        self.assertEqual(u["f#2"], [5, 6])

    def test_comment_continues_from_directive(self):
        src = "#define X 1 /* a\n b */\nvoid f(void)\n{\n}\n"
        self.assertEqual(names(src), [("f", 3, 5)])

    def test_trailing_attribute(self):
        src = 'void f(void) __attribute__((section(".x")))\n{\n}\nint g(int a) __declspec(noinline)\n{\n}\n'
        self.assertEqual(names(src), [("f", 1, 3), ("g", 4, 6)])

    def test_directive_comment_then_continuation(self):
        self.assertEqual(names("#define M(x) /* c */ \\\n  do { x } while(0)\nvoid f(void)\n{\n}\n"), [("f", 3, 5)])
        self.assertEqual(names("#define M(x) /* c */ {\nvoid f(void)\n{\n}\n"), [("f", 2, 4)])

    def test_comment_markers_inside_directive_strings(self):
        src = ('#define S "/*"\nvoid f(void)\n{\n}\n'
               '#endif // see /* x\nvoid g(void)\n{\n}\n'
               '#include "a/*b"\nvoid h(void)\n{\n}\n')
        self.assertEqual(names(src), [("f", 2, 4), ("g", 6, 8), ("h", 10, 12)])

    def test_unterminated_quotes(self):
        self.assertEqual(names("#error don't do this\nvoid f(void)\n{\n}\n"), [("f", 2, 4)])
        self.assertEqual(names("#if 0\nx = 'a\n#define X {\n#endif\nint y;\nvoid g(void)\n{\n}\n"), [("g", 6, 8)])


class ListTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_excel_layout(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        for row in [("파일명", "함수명"), ("motor.c", "Motor_Init"), (None, "Motor_Step"),
                    ("sensor.c", "Sensor_Read"), ("sensor.c", "(함수 외)"), (None, None),
                    ("util.c", None), ("motor.c", "Motor_Stop")]:
            ws.append(row)
        ws.merge_cells("A2:A3")
        p = Path(self.tmp.name, "list.xlsx")
        wb.save(p)
        self.assertEqual(fdf.load_func_list(p), {
            "motor.c": {"Motor_Init", "Motor_Step", "Motor_Stop"},
            "sensor.c": {"Sensor_Read", fdf.FUNC_OUTSIDE},
            "util.c": None})

    def test_text_layout(self):
        p = Path(self.tmp.name, "list.txt")
        p.write_text("파일,함수\nmotor.c,Motor_Init\n,Motor_Step\n# 주석\nutil.c\nutil.c,Ignored\n",
                     encoding="utf-8")
        self.assertEqual(fdf.load_func_list(p), {"motor.c": {"Motor_Init", "Motor_Step"}, "util.c": None})


if __name__ == "__main__":
    unittest.main()
