def encode(text: str, shift: int) -> str:
    out = []
    for ch in text:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            # BUG: no modulo, so shifting past 'z' escapes the alphabet.
            out.append(chr(base + (ord(ch) - base) + shift))
        else:
            out.append(ch)
    return "".join(out)
