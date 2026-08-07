def encode(text: str, shift: int) -> str:
    out = []
    for ch in text:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            # Modulo keeps the shift inside the 26-letter alphabet, and handles
            # negative shifts as well.
            out.append(chr(base + (ord(ch) - base + shift) % 26))
        else:
            out.append(ch)
    return "".join(out)
