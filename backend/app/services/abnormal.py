"""不符合项业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "abnormal"
REQUIRED_FIELDS = ["不符合编号", "发现环节", "不符合描述"]
OPTIONAL_FIELDS = ["严重程度"]
DISPOSAL_FIELDS = ["原因分析", "纠正措施", "验证人员"]
STATUS_ORDER = ["待分析", "待纠正", "待验证", "已关闭"]
CLOSED_STATUS = STATUS_ORDER[-1]

# 每个动作只能从指定前置状态发起，且各自只负责落库自己的字段：
# 处置结论（处置状态）、原因分析、纠正措施分开保存，互不覆盖。
ACTION_RULES = {
    "分析原因": {"expect": "待分析", "target": "待纠正", "fields": ["原因分析"]},
    "实施纠正": {"expect": "待纠正", "target": "待验证", "fields": ["纠正措施"]},
    "验证关闭": {"expect": "待验证", "target": "已关闭", "fields": ["验证人员"]},
}


class AbnormalService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("不符合编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS + OPTIONAL_FIELDS})
        # 处置字段各自独立，从空开始，只由对应动作写入
        for field in DISPOSAL_FIELDS:
            entry[field] = ""
        entry["status"] = STATUS_ORDER[0]
        entry["处置状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"不符合项 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于不符合项可执行范围"
        current = str(entry.get("status") or "")
        if current == CLOSED_STATUS:
            return None, "不符合项已关闭，只能查询，不能再改动"
        rule = ACTION_RULES[action]
        if current != rule["expect"]:
            return None, f"当前处置状态为「{current}」，不能执行「{action}」"
        # 只落库当前动作负责的字段，且只落在这一条记录上；
        # 提交为空时保留原值，原值也为空则拦下并说明原因。
        for field in rule["fields"]:
            incoming = str(values.get(field) or "").strip()
            if incoming:
                entry[field] = incoming
            if not str(entry.get(field) or "").strip():
                return None, f"{field}为空，不能{action}：请先填写{field}"
        target = str(rule["target"])
        entry["status"] = target
        # 处置结论跟着状态走，列表、详情、纠正弹窗读的都是这同一个字段
        entry["处置状态"] = target
        entry["pending"] = target != CLOSED_STATUS
        entry["abnormal"] = False
        return entry, f"不符合项已{action}"
