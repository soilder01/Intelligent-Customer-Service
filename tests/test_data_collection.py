import unittest

from scripts.collect_public_knowledge import extract_text_from_html, normalize_text


class DataCollectionTextTests(unittest.TestCase):
    def test_normalize_text_removes_extra_whitespace(self):
        self.assertEqual(normalize_text("  A\t B\n\n\n C  "), "A B\nC")

    def test_extract_text_from_html_skips_script_and_style(self):
        html = """
        <html>
          <head><style>.x{color:red}</style><script>alert('x')</script></head>
          <body><h1>标题</h1><p>第一段</p><div>第二段</div></body>
        </html>
        """
        text = extract_text_from_html(html)
        self.assertIn("标题", text)
        self.assertIn("第一段", text)
        self.assertIn("第二段", text)
        self.assertNotIn("alert", text)
        self.assertNotIn("color:red", text)


if __name__ == "__main__":
    unittest.main()
