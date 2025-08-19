"""A simple pipe-based RPN calculator with base-62 numbers.

The calculator reads tokens from standard input separated by whitespace and
performs stack-based evaluation. Numbers are interpreted as base-62 using the
character set ``0-9A-Za-z``. Arithmetic operators ``+``, ``-``, ``*`` and ``/``
operate on the top two stack values. ``dup`` duplicates the top stack value.

Custom functions can be defined using the ``fn`` keyword::

    fn inc 1 + ; 3 inc

which pushes ``4`` onto the stack.

The resulting stack is printed as base-62 numbers separated by spaces.
"""

from __future__ import annotations

from typing import Dict, Iterable, List

DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def b62_to_int(value: str) -> int:
    """Convert a base-62 encoded string to an integer."""
    total = 0
    for char in value:
        total = total * 62 + DIGITS.index(char)
    return total


def int_to_b62(value: int) -> str:
    """Convert an integer to a base-62 encoded string."""
    if value == 0:
        return "0"
    digits: List[str] = []
    n = value
    while n > 0:
        n, rem = divmod(n, 62)
        digits.append(DIGITS[rem])
    return "".join(reversed(digits))


def evaluate(tokens: Iterable[str]) -> List[int]:
    """Evaluate a sequence of tokens and return the resulting stack."""
    stack: List[int] = []
    functions: Dict[str, List[str]] = {}
    tokens = list(tokens)
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "fn":
            if i + 2 >= len(tokens):
                raise ValueError("Malformed function definition")
            name = tokens[i + 1]
            body: List[str] = []
            j = i + 2
            while j < len(tokens) and tokens[j] != ";":
                body.append(tokens[j])
                j += 1
            if j == len(tokens):
                raise ValueError("Function definition missing terminator ';'")
            functions[name] = body
            i = j + 1
            continue
        if token in functions:
            # insert function body into token stream after current position
            tokens[i:i + 1] = functions[token]
            continue
        if token in {"+", "-", "*", "/"}:
            b = stack.pop()
            a = stack.pop()
            if token == "+":
                stack.append(a + b)
            elif token == "-":
                stack.append(a - b)
            elif token == "*":
                stack.append(a * b)
            else:
                stack.append(a // b)
        elif token == "dup":
            stack.append(stack[-1])
        else:
            stack.append(b62_to_int(token))
        i += 1
    return stack


def main() -> None:
    import sys

    tokens = sys.stdin.read().split()
    stack = evaluate(tokens)
    print(" ".join(int_to_b62(n) for n in stack))


if __name__ == "__main__":
    main()
