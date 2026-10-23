#!/usr/bin/env python3
"""Package equivalent Python source for deployment within Bradbury's gas cap.

The checked-in contract remains readable. Python's AST writer preserves code
and prompt string values; only documentation and whitespace are removed. Reversible dictionary and LZSS codecs reduce calldata without requiring binary
modules in GenVM. The resulting public schema is checked before deployment.
"""
import ast
import argparse
import base64
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


def compress_lzss(data):
    """Small reversible byte codec; the on-chain decoder uses Python builtins."""
    positions, result, literals = {}, bytearray(), bytearray()

    def flush():
        while literals:
            chunk = literals[:128]
            del literals[:128]
            result.append(len(chunk) - 1)
            result.extend(chunk)

    index = 0
    while index < len(data):
        length, distance = 0, 0
        for old in reversed(positions.get(data[index:index + 3], [])[-64:]):
            if index - old > 65535:
                break
            size = 0
            while size < 130 and index + size < len(data) and data[old + size] == data[index + size]:
                size += 1
            if size > length:
                length, distance = size, index - old
        used = length if length >= 4 else 1
        if length >= 4:
            flush()
            result.extend((128 + length - 3, distance >> 8, distance & 255))
        else:
            literals.append(data[index])
            if len(literals) == 128:
                flush()
        for pos in range(index, index + used):
            positions.setdefault(data[pos:pos + 3], []).append(pos)
        index += used
    flush()
    return bytes(result)


def pack_lzss(code, header, source_hash):
    raw = code.encode()
    compressed = compress_lzss(raw)
    alphabet = base64._b85alphabet.decode()
    payload = base64.b85encode(compressed, pad=True).decode()
    packed = (header + "\n_hs_source_hash=" + repr(source_hash) + "\n"
              + "_hs_alphabet=" + repr(alphabet) + "\n_hs_payload=" + repr(payload) + "\n"
              + "_hs_data=bytearray()\n"
              + "for _hs_i in range(0,len(_hs_payload),5):\n"
              + " _hs_word=0\n"
              + " for _hs_c in _hs_payload[_hs_i:_hs_i+5]:_hs_word=_hs_word*85+_hs_alphabet.index(_hs_c)\n"
              + " _hs_data.extend(_hs_word.to_bytes(4,'big'))\n"
              + "_hs_data=_hs_data[:" + str(len(compressed)) + "]\n"
              + "_hs_out=bytearray()\n_hs_i=0\n"
              + "while _hs_i<len(_hs_data):\n"
              + " _hs_tag=_hs_data[_hs_i];_hs_i+=1\n"
              + " if _hs_tag<128:\n"
              + "  _hs_n=_hs_tag+1;_hs_out.extend(_hs_data[_hs_i:_hs_i+_hs_n]);_hs_i+=_hs_n\n"
              + " else:\n"
              + "  _hs_d=_hs_data[_hs_i]*256+_hs_data[_hs_i+1];_hs_i+=2\n"
              + "  for _hs_j in range(_hs_tag-128+3):_hs_out.append(_hs_out[-_hs_d])\n"
              + "_hs_code=bytes(_hs_out).decode()\nexec(_hs_code,globals())\n")
    # Run the exact decoder, without executing the restored contract.
    scope = {}
    exec(packed.rsplit("exec(_hs_code,globals())", 1)[0], scope)
    assert scope['_hs_code'] == code
    return packed


def build(output=None, codec="dictionary"):
    source = (ROOT / "contracts/hearsay.py").read_text()
    tree = ast.fix_missing_locations(RemoveDocumentation().visit(ast.parse(source)))
    stripped = ast.unparse(tree) + "\n"
    # Compare executable ASTs, including all embedded judge prompts.
    assert ast.dump(RemoveDocumentation().visit(ast.parse(stripped)), include_attributes=False) == ast.dump(tree, include_attributes=False)
    code = compact(stripped)
    if codec == "lzss":
        packed = pack_lzss(code, source.splitlines()[0], hashlib.sha256(source.encode()).hexdigest())
    else:
        encoded, dictionary = encode_dictionary(code)
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
    out = Path(output).resolve() if output else ROOT / "runs/deploy/hearsay.py"
    out.parent.mkdir(parents=True, exist_ok=True)
    (out.parent / "hearsay-source.py").write_text(source.splitlines()[0] + "\n" + stripped)
    out.write_text(packed)
    print("%s: %d -> %d bytes, sha256 %s" % (out.relative_to(ROOT), len(source.encode()), len(packed.encode()), hashlib.sha256(packed.encode()).hexdigest()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="separate output path for a new deployment")
    parser.add_argument("--codec", choices=("dictionary", "lzss"), default="dictionary")
    args = parser.parse_args()
    build(args.out, args.codec)
