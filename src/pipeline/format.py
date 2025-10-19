from typing import List

from pydantic import BaseModel

from src.pipeline.prompt import group_cn_name


class ReferenceGroup(BaseModel):
    name: str
    items: List[str] = []


class MarkdownDoc(BaseModel):
    question: str
    answer_markdown: str
    references: List[ReferenceGroup] = []


def build_markdown(doc: MarkdownDoc) -> str:
    lines: List[str] = []
    lines.append(f"# 问题\n\n{doc.question}\n")
    lines.append(f"# 回答\n\n{doc.answer_markdown}\n")
    lines.append("# 引用处\n")
    for grp in doc.references:
        gname = group_cn_name(grp.name)
        lines.append(f"## {gname}\n")
        if not grp.items:
            lines.append("- 该组未检索到相关内容\n")
        else:
            for ref in grp.items:
                lines.append(f"- {ref}\n")
    return "".join(lines)


__all__ = [
    "MarkdownDoc",
    "ReferenceGroup",
    "build_markdown",
]