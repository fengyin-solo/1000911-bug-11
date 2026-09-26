"""不符合项业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "abnormal"
REQUIRED_FIELDS = ["不符合编号", "发现环节", "不符合描述"]
OPTIONAL_FIELDS = ["严重程度"]
# 处置过程字段：每个动作只负责写自己的字段，三者分开保存、互不覆盖
DISPOSITION_FIELDS = ["原因分析", "纠正措施", "验证人员"]
STATUS_ORDER = ["待分析", "待纠正", "待验证", "已关闭"]
CLOSED = STATUS_ORDER[-1]
# 动作 -> 负责字段 / 前置状态 / 目标状态；顺序不可跳跃
ACTION_RULES = {
    "分析原因": {"field": "原因分析", "expect": "待分析", "target": "待纠正"},
    "实施纠正": {"field": "纠正措施", "expect": "待纠正", "target": "待验证"},
    "验证关闭": {"field": "验证人员", "expect": "待验证", "target": "已关闭"},
}
# 当前状态 -> 该状态下唯一可执行的动作
EXPECTED_ACTION = {rule["expect"]: action for action, rule in ACTION_RULES.items()}


def _sync_conclusion(entry: dict[str, Any]) -> dict[str, Any]:
    """处置结论（列表里的「处置状态」列）始终与内部状态一致。

    列表、详情、纠正弹窗读的都是这条记录，结论只能有一个来源，
    避免出现「列表停在待验证、弹窗里又是另一个结论」。
    """
    entry["处置状态"] = str(entry.get("status") or STATUS_ORDER[0])
    return entry


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
        return [_sync_conclusion(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return _sync_conclusion(entry)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        problems = [f"缺少必填字段：{field}" for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        code = str(values.get("不符合编号") or "").strip()
        if code and any(str(row.get("不符合编号", "")) == code for row in store.rows(MODULE)):
            problems.append(f"不符合编号 {code} 已存在，原因分析与纠正措施只能落在各自编号上")
        if problems:
            return None, problems
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS + OPTIONAL_FIELDS})
        for field in DISPOSITION_FIELDS:
            entry[field] = ""
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return _sync_conclusion(entry), []

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
        current = str(entry.get("status") or STATUS_ORDER[0])
        code = str(entry.get("不符合编号") or entry_id)
        if current == CLOSED:
            return None, f"不符合项 {code} 已关闭，只能查看，不能再改动"
        rule = ACTION_RULES[action]
        if current != rule["expect"]:
            expect_action = EXPECTED_ACTION.get(current, "分析原因")
            return None, f"不符合项 {code} 当前状态为「{current}」，应先执行「{expect_action}」，不能执行「{action}」"
        field = str(rule["field"])
        value = str(values.get(field) or "").strip()
        if not value:
            if action == "验证关闭":
                return None, f"验证人员为空，不允许关闭不符合项 {code}：请先填写验证人员"
            return None, f"{field}为空，不允许{action}：请先填写{field}"
        # 只把本动作负责的字段写到这一条记录上，不碰其他字段、更不碰其他编号
        entry[field] = value
        entry["status"] = rule["target"]
        entry["pending"] = rule["target"] != CLOSED
        entry["abnormal"] = False
        _sync_conclusion(entry)
        return entry, f"不符合项 {code} 已{action}"
