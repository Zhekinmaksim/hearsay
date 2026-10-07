#!/usr/bin/env python3
"""Package equivalent Python source for deployment within Bradbury's gas cap.

The checked-in contract remains readable. Python's AST writer preserves code
and prompt string values; only documentation and whitespace are removed. A
reversible string dictionary reduces calldata without requiring binary modules
in GenVM. The resulting public schema is checked before deployment.
"""
import ast
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import tokenize

ROOT = Path(__file__).resolve().parent.parent


class RemoveDocumentation(ast.NodeTransformer):
    def strip(self, node):
        self.generic_visit(node)
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:] or [ast.Pass()]
        return node
    visit_Module = strip
    visit_ClassDef = strip
    visit_FunctionDef = strip
    visit_AsyncFunctionDef = strip


def compact(source):
    output, level, start, previous = [], 0, True, None
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type in (tokenize.COMMENT, tokenize.NL, tokenize.ENDMARKER):
            continue
        if token.type == tokenize.INDENT:
            level += 1
            continue
        if token.type == tokenize.DEDENT:
            level -= 1
            continue
        if token.type == tokenize.NEWLINE:
            output.append("\n")
            start, previous = True, None
            continue
        if start:
            output.append("\t" * level)
            start = False
        if previous is not None and (
            (previous.type in (tokenize.NAME, tokenize.NUMBER) and token.type in (tokenize.NAME, tokenize.NUMBER))
            or (previous.type == token.type == tokenize.OP and previous.string + token.string in tokenize.EXACT_TOKEN_TYPES)
        ):
            output.append(" ")
        output.append(token.string)
        previous = token
    result = "".join(output)
    assert ast.dump(ast.parse(source), include_attributes=False) == ast.dump(ast.parse(result), include_attributes=False)
    return result


def encode_dictionary(source):
    encoded, dictionary = source, []
    for index in range(120):
        candidates = Counter(encoded[pos:pos + size] for size in (3, 5, 8, 12, 20, 32) for pos in range(len(encoded) - size + 1))
        top = sorted(candidates, key=lambda token: (len(token.encode()) - 2) * candidates[token], reverse=True)[:250]
        saving, token = max(((len(token.encode()) - 2) * encoded.count(token) - len(json.dumps(token, ensure_ascii=False).encode()) - 1, token) for token in top)
        if saving <= 0:
            break
        marker = chr(256 + index)
        assert marker not in source
        encoded = encoded.replace(token, marker)
        dictionary.append(token)
    restored = encoded
    for index in reversed(range(len(dictionary))):
        restored = restored.replace(chr(256 + index), dictionary[index])
    assert restored == source
    return encoded, dictionary


def build():
    source = (ROOT / "contracts/hearsay.py").read_text()
    tree = ast.fix_missing_locations(RemoveDocumentation().visit(ast.parse(source)))
    stripped = ast.unparse(tree) + "\n"
    # Compare executable ASTs, including all embedded judge prompts.
    assert ast.dump(RemoveDocumentation().visit(ast.parse(stripped)), include_attributes=False) == ast.dump(tree, include_attributes=False)
    encoded, dictionary = encode_dictionary(compact(stripped))
    packed = (source.splitlines()[0] + "\n"
              + "_hs_source_hash=" + repr(hashlib.sha256(source.encode()).hexdigest()) + "\n"
              + "_hs_code=" + json.dumps(encoded, ensure_ascii=False) + "\n"
              + "_hs_dict=" + repr(dictionary) + "\n"
              + "for _hs_i in range(len(_hs_dict)-1,-1,-1):\n"
              + " _hs_code=_hs_code.replace(chr(256+_hs_i),_hs_dict[_hs_i])\n"
              + "exec(_hs_code,globals())\n")
    comments = []
    for line in packed.splitlines():
        if not line.startswith("#"):
            break
        comments.append(line[1:])
    # GenVM concatenates leading comments into one runner JSON document.
    assert json.loads("\n".join(comments)) == json.loads(source.splitlines()[0][1:])
    out = ROOT / "runs/deploy/hearsay.py"
    out.parent.mkdir(parents=True, exist_ok=True)
    (out.parent / "hearsay-source.py").write_text(source.splitlines()[0] + "\n" + stripped)
    out.write_text(packed)
    print("%s: %d -> %d bytes, sha256 %s" % (out.relative_to(ROOT), len(source.encode()), len(packed.encode()), hashlib.sha256(packed.encode()).hexdigest()))


if __name__ == "__main__":
    build()
