"""
Markdown -> hierarchical tree parser.

NOT a generic markdown parser (explicitly out of scope). This targets the
heading-driven structure of the CT-200 manual specifically: ATX headings
(`#`, `##`, ...) define the tree; everything between one heading and the
next is that heading's body.

KNOWN IRREGULARITIES THIS HANDLES (update this list once you've actually
read data/ct200_manual.md — this is a starting set, not the final one):

1. Duplicate headings under the same parent
   e.g. two "## Notes" sections under the same "# Calibration" parent.
   -> Each becomes a DISTINCT node. logical_key is disambiguated with a
      "#2", "#3", ... suffix in encounter order, so two nodes never collide.
      A plain heading-text match would have silently merged them.

2. Skipped heading levels (e.g. "#" directly followed by "###", no "##")
   -> We do NOT silently nest the "###" under the "#" as if it were a
      normal child. We attach it to the nearest preceding heading with a
      LOWER level (standard "nearest ancestor" rule) and flag it via
      `skipped_level=True` on the node so it's visible for review, rather
      than pretending the document's structure is cleaner than it is.

3. Empty sections (a heading immediately followed by another heading,
   no body text)
   -> body = "", not None. Still hashed and still a real node.

4. Leading document content before the first heading
   -> collected into a synthetic root-level node ("_preamble") rather than
      silently dropped.

If your first parsing attempt didn't handle one of these (or something else
in the real file), that's exactly the kind of thing to write up in the
approach doc: what broke, how you noticed (a failing test? a node with an
obviously wrong parent? a duplicate ID collision?), and how you fixed it.
"""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


@dataclass
class RawNode:
    heading: str
    level: int
    body_lines: list = field(default_factory=list)
    parent: Optional["RawNode"] = None
    children: list = field(default_factory=list)
    order_index: int = 0
    skipped_level: bool = False
    logical_key: str = ""
    content_hash: str = ""

    @property
    def body(self) -> str:
        return "\n".join(self.body_lines).strip()


def content_hash(heading: str, body: str) -> str:
    """Hash over heading+body so a heading-only rename still changes the hash
    (matters for staleness detection: heading text changing IS a change)."""
    payload = f"{heading}\n{body}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_markdown_tree(text: str) -> RawNode:
    """Parse `text` into a tree of RawNode under a synthetic virtual root
    (level 0, heading='_root')."""
    root = RawNode(heading="_root", level=0)
    preamble = RawNode(heading="_preamble", level=1, parent=root, order_index=0)
    root.children.append(preamble)

    stack = [root]  # stack of ancestors, stack[-1] is current deepest open node
    current = preamble
    sibling_counters: dict = {}  # (parent_id, heading) -> count, for dup disambiguation

    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if not m:
            current.body_lines.append(line)
            continue

        level = len(m.group(1))
        heading = m.group(2).strip()

        # Pop the stack until we find a parent with level < this node's level.
        # This is what makes skipped-level headings attach sensibly instead
        # of crashing or silently becoming children of the wrong ancestor.
        skipped = False
        while stack and stack[-1].level >= level and stack[-1] is not root:
            stack.pop()
        parent = stack[-1]
        if parent is not root and level - parent.level > 1:
            skipped = True

        order = len(parent.children)
        node = RawNode(heading=heading, level=level, parent=parent, order_index=order,
                        skipped_level=skipped)
        parent.children.append(node)
        stack.append(node)
        current = node

    _assign_logical_keys(root, path_prefix="")
    _finalize_hashes(root)
    return root


def _assign_logical_keys(node: RawNode, path_prefix: str):
    """Build logical_key = heading path from root, disambiguating duplicate
    sibling headings with a '#2', '#3', ... suffix (encounter order)."""
    seen_counts: dict = {}
    for child in node.children:
        base_key = f"{path_prefix}/{child.heading}" if path_prefix else child.heading
        seen_counts[child.heading] = seen_counts.get(child.heading, 0) + 1
        n = seen_counts[child.heading]
        child.logical_key = base_key if n == 1 else f"{base_key}#{n}"
        _assign_logical_keys(child, child.logical_key)


def _finalize_hashes(node: RawNode):
    for child in node.children:
        child.content_hash = content_hash(child.heading, child.body)
        _finalize_hashes(child)


def flatten(root: RawNode) -> list:
    """Depth-first flatten, skipping the synthetic root but keeping preamble."""
    out = []

    def walk(n: RawNode):
        if n.heading != "_root":
            out.append(n)
        for c in n.children:
            walk(c)

    walk(root)
    return out