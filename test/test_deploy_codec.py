"""The deployment wrapper must restore executable source byte for byte."""
import ast
import hashlib
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_deploy import RemoveDocumentation, compact, pack_lzss


class DeploymentCodec(unittest.TestCase):
    def decode(self, text):
        packed = pack_lzss(text, '# {"Depends":"test-only"}', 'test-hash')
        scope = {}
        exec(packed.rsplit('exec(_hs_code,globals())', 1)[0], scope)
        self.assertEqual(scope['_hs_code'], text)
        return packed

    def test_empty_and_short_literal_blocks(self):
        for text in ('', 'x', 'abc', 'abcde', ''.join(chr(i) for i in range(256))):
            self.decode(text)

    def test_overlapping_matches_and_long_distance_windows(self):
        self.decode('a' * 100_000 + 'xyz' * 1000)

    def test_unicode_quotes_and_decoder_variable_names_are_data(self):
        self.decode('"\'\\\n\x00 Привет 世界 _hs_code >>> <<< ' * 100)

    def test_literal_boundaries_and_seeded_random_data(self):
        rng = random.Random(42)
        for size in (127, 128, 129, 4096):
            self.decode(''.join(chr(rng.randrange(32, 127)) for _ in range(size)))

    def test_actual_contract_restores_identical_ast_and_pinned_source(self):
        source = (ROOT / 'contracts/hearsay.py').read_text()
        tree = ast.fix_missing_locations(RemoveDocumentation().visit(ast.parse(source)))
        stripped = ast.unparse(tree) + '\n'
        code = compact(stripped)
        packed = pack_lzss(code, source.splitlines()[0], hashlib.sha256(source.encode()).hexdigest())
        scope = {}
        exec(packed.rsplit('exec(_hs_code,globals())', 1)[0], scope)
        self.assertEqual(ast.dump(ast.parse(scope['_hs_code'])), ast.dump(ast.parse(stripped)))
        self.assertEqual(scope['_hs_source_hash'], hashlib.sha256(source.encode()).hexdigest())
        self.assertLess(len(packed.encode()), 18_000, 'recheck deployment gas before increasing this budget')


if __name__ == '__main__':
    unittest.main()
