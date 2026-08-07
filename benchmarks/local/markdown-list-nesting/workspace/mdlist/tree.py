from mdlist.tokenize import Item, tokenize


def build_tree(source: str) -> list:
    """Return nested nodes: {"text": ..., "children": [...]}."""
    items = tokenize(source)
    roots: list = []
    stack: list = []   # (indent, node) for the open ancestors
    for item in items:
        node = {"text": item.text, "children": []}
        # BUG: a single pop only closes one level, so an item that dedents past
        # several levels lands under whichever ancestor happens to be on top
        # rather than under its real parent.
        if stack and item.indent <= stack[-1][0]:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            roots.append(node)
        stack.append((item.indent, node))
    return roots
